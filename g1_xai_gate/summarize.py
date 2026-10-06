"""Summarise per-batch CSV logs into tables and curves.

Usage: python summarize.py RESULTS_DIR
"""
import glob
import os
import re
import sys

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

GATES = ["none", "pseudofilter", "conf_drop", "xai", "conf_xai"]

out = sys.argv[1] if len(sys.argv) > 1 else "results"
rows = []
for f in glob.glob(os.path.join(out, "*_seed*_*.csv")):
    m = re.match(r"(.+)_seed(\d+)_(.+)\.csv", os.path.basename(f))
    if not m or m.group(3).endswith("quick"):
        continue
    zd, seed, gate = m.group(1), int(m.group(2)), m.group(3)
    d = pd.read_csv(f)
    s = d.iloc[1:]
    zd_seen = s.zd_in_batch.sum()
    rows.append({
        "zero_day": zd, "seed": seed, "gate": gate,
        "final_acc": d.acc.iloc[-1], "final_f1": d.f1.iloc[-1],
        "final_zd_recall": d.zd_recall.iloc[-1], "final_fpr": d.fpr.iloc[-1],
        "min_acc": d.acc.min(), "init_acc": d.acc.iloc[0], "init_zd_recall": d.zd_recall.iloc[0],
        "label_precision": (s.label_precision * s.n_added).sum() / s.n_added.sum(),
        "added_pct": 100 * s.n_added.sum() / (len(s) * 2784),
        "zd_poisoned_pct": 100 * s.zd_added_as_normal.sum() / zd_seen,
        "zd_as_attack_pct": 100 * s.zd_added_as_attack.sum() / zd_seen,
        "zd_rejected_pct": 100 * s.zd_rejected.sum() / zd_seen,
    })
    rows[-1]["_log"] = d
if not rows:
    sys.exit("no full-run CSVs found")
df = pd.DataFrame(rows)
cols = ["final_acc", "final_f1", "final_zd_recall", "final_fpr", "min_acc", "label_precision",
        "added_pct", "zd_poisoned_pct", "zd_as_attack_pct", "zd_rejected_pct"]

lines = []
for zd, g in df.groupby("zero_day"):
    agg = g.groupby("gate")[cols].agg(["mean", "std"])
    agg = agg.reindex([x for x in GATES if x in agg.index])
    seeds = sorted(int(x) for x in g.seed.unique())
    lines.append(f"\n### Zero-day = {zd} (seeds {seeds}; after init: acc "
                 f"{g.init_acc.mean():.2f}, zero-day recall {g.init_zd_recall.mean():.2f})\n")
    lines.append("| Gate | Final acc | Final F1 | Zero-day recall | FPR | Min acc | Label precision "
                 "| Added % | Zero-day added as normal % | as attack % | rejected % |")
    lines.append("|" + "---|" * 11)
    for gate, r in agg.iterrows():
        cell = lambda c: f"{r[(c, 'mean')]:.2f} ± {0 if pd.isna(r[(c, 'std')]) else r[(c, 'std')]:.2f}"
        lines.append(f"| {gate} | " + " | ".join(cell(c) for c in cols) + " |")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for gate in [x for x in GATES if x in set(g.gate)]:
        logs = [r["_log"] for r in rows if r["zero_day"] == zd and r["gate"] == gate]
        mean = sum(x[["acc", "zd_recall"]].reset_index(drop=True) for x in logs) / len(logs)
        axes[0].plot(mean.acc, label=gate)
        axes[1].plot(mean.zd_recall, label=gate)
        poison = sum(x.zd_added_as_normal.fillna(0).cumsum().reset_index(drop=True) for x in logs) / len(logs)
        axes[2].plot(poison, label=gate)
    for ax, t in zip(axes, ["Test accuracy (%)", "Zero-day recall (%)",
                            "Cumulative zero-day samples added as normal"]):
        ax.set_title(t)
        ax.set_xlabel("update batch")
    axes[0].legend()
    fig.suptitle(f"Zero-day = {zd}, mean over seeds {seeds}")
    fig.tight_layout()
    fig.savefig(os.path.join(out, f"curves_{zd}.png"), dpi=110)

table = "\n".join(lines)
open(os.path.join(out, "summary_tables.md"), "w").write(table + "\n")
df.drop(columns="_log").to_csv(os.path.join(out, "summary_per_run.csv"), index=False)
print(table)
