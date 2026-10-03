"""Reproduce the four experiments of
"A Self-Adaptive Intrusion Detection System for Zero-Day Attacks Using Deep Q-Networks"
(Alkasassbeh et al., IEEE Access 2025).

  Exp 1  binary,     random 70/30 stratified split
  Exp 2  binary,     zero-day family split
  Exp 3  multiclass, random 70/30 stratified split
  Exp 4  multiclass, zero-day family split

Usage:  python run_experiments.py                # all experiments, seeds 0-4
        python run_experiments.py --exp 1 2 --seeds 0
"""
import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score, classification_report,
                             confusion_matrix, f1_score)

from dqn_ids.agent import DQNAgent, DQNConfig, train
from dqn_ids.data import DEFAULT_CSV, load, make_split
from dqn_ids.env import FlowClassificationEnv, reward_matrix

EXPERIMENTS = {
    1: ("binary", "random", "Binary (Random Split)"),
    2: ("binary", "zeroday", "Binary (Zero-Day Family Split)"),
    3: ("multiclass", "random", "Multiclass (Random Split)"),
    4: ("multiclass", "zeroday", "Multiclass (Zero-Day Family Split)"),
}

# Numbers reported in the paper (Tables 4-8).
PAPER = {
    1: {"accuracy": 0.976, "f1_macro": 0.98},
    2: {"accuracy": 0.959, "f1_macro": 0.96},
    3: {"accuracy": 0.970, "f1_macro": 0.97},
    4: {"accuracy": 0.920, "f1_macro": 0.92},
}


def run_one(exp, seed, args):
    torch.set_num_threads(1)
    task, split_kind, title = EXPERIMENTS[exp]
    df = load(args.csv)
    sp = make_split(df, task, split_kind, features=args.features, seed=args.split_seed,
                    scale_on=args.scale_on)
    cfg = DQNConfig(gamma=args.gamma, episodes=args.episodes,
                    steps_per_episode=args.steps)
    R = reward_matrix(task, args.multiclass_reward)
    rng = np.random.default_rng(seed)
    env = FlowClassificationEnv(sp.X_train, sp.y_train, R, cfg.steps_per_episode, rng)
    agent = DQNAgent(sp.X_train.shape[1], len(sp.class_names), cfg, seed=seed)

    t0 = time.time()
    tag = f"[exp{exp} seed{seed}]"
    losses = train(agent, env, log=lambda m: print(tag, m, flush=True))
    train_time = time.time() - t0

    t0 = time.time()
    pred = agent.predict(sp.X_test)
    infer_ms = (time.time() - t0) * 1000 / len(sp.X_test)

    rep = classification_report(sp.y_test, pred, target_names=sp.class_names,
                                digits=4, output_dict=True, zero_division=0)
    res = {
        "exp": exp, "seed": seed, "title": title,
        "accuracy": accuracy_score(sp.y_test, pred),
        "f1_macro": f1_score(sp.y_test, pred, average="macro"),
        "f1_weighted": f1_score(sp.y_test, pred, average="weighted"),
        "report": rep,
        "report_text": classification_report(sp.y_test, pred, target_names=sp.class_names,
                                             digits=2, zero_division=0),
        "confusion_matrix": confusion_matrix(sp.y_test, pred).tolist(),
        "class_names": sp.class_names,
        "losses": losses,
        "n_train": len(sp.y_train), "n_test": len(sp.y_test),
        "train_families": sp.train_families, "test_families": sp.test_families,
        "train_time_s": train_time, "inference_ms_per_sample": infer_ms,
    }
    print(f"{tag} accuracy={res['accuracy']:.4f} f1_macro={res['f1_macro']:.4f}", flush=True)
    return res


def plot(res, out_dir):
    title = f"Experiment {res['exp']}: {res['title']}"
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    ConfusionMatrixDisplay(np.array(res["confusion_matrix"]),
                           display_labels=res["class_names"]).plot(ax=ax, cmap="Blues",
                                                                   values_format="d")
    ax.set_title(f"{title}\nConfusion Matrix", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, f"exp{res['exp']}_confusion_matrix.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    ax.plot(range(len(res["losses"])), res["losses"], marker="o")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Average MSE loss")
    ax.set_title(f"{title}\nDQN Loss Curve", fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, f"exp{res['exp']}_loss_curve.png"), dpi=130)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=DEFAULT_CSV)
    p.add_argument("--exp", type=int, nargs="+", default=[1, 2, 3, 4])
    p.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    p.add_argument("--split-seed", type=int, default=42)
    p.add_argument("--features", choices=["table1", "all"], default="all")
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--episodes", type=int, default=10)
    p.add_argument("--steps", type=int, default=20_000)
    p.add_argument("--multiclass-reward", choices=["symmetric", "asymmetric"],
                   default="symmetric")
    p.add_argument("--scale-on", choices=["train", "all"], default="train")
    p.add_argument("--workers", type=int, default=os.cpu_count())
    p.add_argument("--out", default="results")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    jobs = [(e, s) for e in args.exp for s in args.seeds]
    with ProcessPoolExecutor(args.workers) as ex:
        results = list(ex.map(run_one, *zip(*jobs), [args] * len(jobs)))

    summary = {"config": vars(args), "experiments": {}}
    lines = ["| Exp | Setting | Paper Acc | Paper F1 | Best-seed Acc | Best-seed F1 (macro) "
             "| Mean ± std Acc (all seeds) |",
             "|---|---|---|---|---|---|---|"]
    for e in args.exp:
        runs = [r for r in results if r["exp"] == e]
        best = max(runs, key=lambda r: r["accuracy"])
        accs = np.array([r["accuracy"] for r in runs])
        plot(best, args.out)
        with open(os.path.join(args.out, f"exp{e}_classification_report.txt"), "w") as f:
            f.write(f"Experiment {e}: {best['title']} (best seed = {best['seed']})\n")
            f.write(f"train={best['n_train']} test={best['n_test']}\n")
            f.write(f"test families: {best['test_families']}\n\n")
            f.write(best["report_text"])
        summary["experiments"][e] = {
            "title": best["title"], "paper": PAPER[e],
            "best": {k: best[k] for k in ("seed", "accuracy", "f1_macro", "f1_weighted",
                                          "confusion_matrix", "losses", "report",
                                          "n_train", "n_test", "test_families",
                                          "train_time_s", "inference_ms_per_sample")},
            "all_seeds": [{"seed": r["seed"], "accuracy": r["accuracy"],
                           "f1_macro": r["f1_macro"]} for r in runs],
            "mean_accuracy": accs.mean(), "std_accuracy": accs.std(),
        }
        lines.append(f"| {e} | {best['title']} | {PAPER[e]['accuracy']:.1%} | "
                     f"{PAPER[e]['f1_macro']:.2f} | {best['accuracy']:.1%} | "
                     f"{best['f1_macro']:.2f} | {accs.mean():.1%} ± {accs.std():.1%} |")
    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(args.out, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
