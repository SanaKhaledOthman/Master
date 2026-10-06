"""G1: explanation-gated pseudo-labels for continual zero-day intrusion detection.

Base learner: the unmodified PseudoFilter v9 pipeline (Afzaal et al., built on AOC-IDS),
loaded by upstream.py. Only the online update rule (which pseudo-labels enter
retraining) changes between gates:

  none         accept every prediction (AOC-IDS behaviour)
  pseudofilter upstream rule, called unchanged: confidence >= 0.85 and enc/dec agreement;
               rejected samples are still added, labelled normal (upstream semantics)
  conf_drop    the same confidence/agreement test, but rejected samples are dropped
  xai          explanation gate only (below); rejected samples are dropped
  conf_xai     conf_drop AND xai

Explanation gate. For every candidate x with predicted class c, we compute an expected-
gradients SHAP attribution of each head's logit (encoder head and decoder head),
with a background drawn from the trusted labelled set X0. x is accepted when
  1. its encoder-head attribution is closer to the class-c prototype than to the
     other class's prototype by at least tau_c, and
  2. its encoder- and decoder-head attributions agree (cosine >= tau_agree).
Prototypes are mean attributions of correctly classified X0 samples, recomputed
before every update. Thresholds are the q-quantile of the same scores on those X0
samples, so a pseudo-label is accepted only if its explanation is at least as typical
as the bottom q of truly labelled examples. Prototypes use only ground-truth X0, so
poisoned pseudo-labels cannot shift them.

Zero-day protocol. One attack category (--zero_day) is removed from the labelled set
X0. It appears in the unlabelled stream only after --zd_start of the stream has passed.
The test set is the official UNSW-NB15 test partition. Zero-day recall is measured on
its test samples of that category.
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from upstream import load_pseudofilter

GATES = ["none", "pseudofilter", "conf_drop", "xai", "conf_xai"]


# ── data ────────────────────────────────────────────────────────────────
def load_data(pf, cfg):
    """Upstream preprocessing, plus attack_cat read from the same files in the same order."""
    X_tr, y_tr, X_te, y_te = pf.load_unsw(cfg)
    tr = pd.read_csv(cfg.TRAIN_PATH, usecols=["attack_cat"])
    te = pd.read_csv(cfg.TEST_PATH, usecols=["attack_cat"])
    if len(tr) < len(te):  # upstream swaps the files in this case
        tr, te = te, tr
    cat = lambda d: d["attack_cat"].fillna("Normal").str.strip().values
    return X_tr, y_tr, cat(tr), X_te, y_te, cat(te)


def make_stream(y, cats, zero_day, init_ratio, zd_start, seed):
    """X0: init_ratio of the non-zero-day rows. Stream: the rest, with zero-day rows
    inserted at random positions after the first zd_start of the stream."""
    rng = np.random.default_rng(seed)
    known = np.flatnonzero(cats != zero_day)
    zd = rng.permutation(np.flatnonzero(cats == zero_day))
    known = rng.permutation(known)
    # stratify X0 on the binary label like upstream
    idx0 = np.concatenate([known[y[known] == k][: int(round(init_ratio * np.sum(y[known] == k)))]
                           for k in (0, 1)])
    rest = np.setdiff1d(known, idx0)
    rest = rng.permutation(rest)
    cut = int(zd_start * (len(rest) + len(zd)))
    head, tail = rest[:cut], rest[cut:]
    tail = rng.permutation(np.concatenate([tail, zd]))
    return rng.permutation(idx0), np.concatenate([head, tail])


# ── explanations ────────────────────────────────────────────────────────
def expected_gradients(model, X, background, n_samples, seed):
    """Expected-gradients SHAP (as in shap.GradientExplainer) of both head logits.

    Returns (attr_enc, attr_dec), each [n, d], for the logit of class 'attack'.
    """
    g = torch.Generator(device=X.device).manual_seed(seed)
    n, d = X.shape
    xr = X.repeat_interleave(n_samples, 0)
    ref = background[torch.randint(len(background), (len(xr),), generator=g, device=X.device)]
    alpha = torch.rand(len(xr), 1, generator=g, device=X.device)
    pts = (ref + alpha * (xr - ref)).requires_grad_(True)
    _, _, le, ld = model(pts)
    ge, = torch.autograd.grad(le.sum(), pts, retain_graph=True)
    gd, = torch.autograd.grad(ld.sum(), pts)
    delta = xr - ref
    a_e = (ge * delta).view(n, n_samples, d).mean(1)
    a_d = (gd * delta).view(n, n_samples, d).mean(1)
    return a_e.detach(), a_d.detach()


def explain(model, X, background, n_samples, seed, chunk=1024):
    model.eval()
    out_e, out_d = [], []
    for s in range(0, len(X), chunk):
        a_e, a_d = expected_gradients(model, X[s:s + chunk], background, n_samples, seed + s)
        out_e.append(a_e)
        out_d.append(a_d)
    return torch.cat(out_e), torch.cat(out_d)


def unit(a):
    return a / (a.norm(dim=1, keepdim=True) + 1e-12)


class XAIGate:
    """Explanation-consistency gate calibrated on the trusted labelled set X0."""

    def __init__(self, X0, y0, q, n_samples, n_ref, n_bg, seed):
        self.X0, self.y0 = X0, y0
        self.q, self.n_samples, self.n_ref, self.n_bg, self.seed = q, n_samples, n_ref, n_bg, seed
        self.rng = np.random.default_rng(seed)

    def _scores(self, a_e, a_d, pred, protos):
        """Prototype margin and enc/dec explanation agreement. Attribution sign is flipped
        for class 0 so that 'evidence for the predicted class' is positive."""
        sign = torch.where(pred == 1, 1.0, -1.0).unsqueeze(1)
        e, dd = unit(a_e * sign), unit(a_d * sign)
        own = (e * protos[pred]).sum(1)
        other = (e * protos[1 - pred]).sum(1)
        return own - other, (e * dd).sum(1)

    def calibrate(self, model, predict):
        dev = next(model.parameters()).device
        ref = self.rng.choice(len(self.X0), size=min(self.n_ref, len(self.X0)), replace=False)
        bg = self.rng.choice(len(self.X0), size=min(self.n_bg, len(self.X0)), replace=False)
        self.background = torch.as_tensor(self.X0[bg], dtype=torch.float32, device=dev)
        Xr = self.X0[ref]
        yr = self.y0[ref]
        pr = predict(Xr)
        ok = pr == yr  # prototypes from correctly classified ground-truth samples only
        a_e, a_d = explain(model, torch.as_tensor(Xr[ok], dtype=torch.float32, device=dev),
                           self.background, self.n_samples, self.seed)
        y_ok = torch.as_tensor(yr[ok], device=dev)
        sign = torch.where(y_ok == 1, 1.0, -1.0).unsqueeze(1)
        e = unit(a_e * sign)
        self.protos = torch.stack([unit(e[y_ok == k].mean(0, keepdim=True))[0] for k in (0, 1)])
        margin, agree = self._scores(a_e, a_d, y_ok, self.protos)
        self.tau = torch.stack([torch.quantile(margin[y_ok == k], self.q) for k in (0, 1)])
        self.tau_agree = torch.quantile(agree, self.q)

    def accept(self, model, X, pred):
        dev = self.background.device
        a_e, a_d = explain(model, torch.as_tensor(X, dtype=torch.float32, device=dev),
                           self.background, self.n_samples, self.seed + 7)
        p = torch.as_tensor(pred, device=dev)
        margin, agree = self._scores(a_e, a_d, p, self.protos)
        ok = (margin >= self.tau[p]) & (agree >= self.tau_agree)
        return ok.cpu().numpy()


# ── learner with a pluggable gate ───────────────────────────────────────
def make_learner_class(pf):
    class GatedAOCIDS(pf.ImprovedAOCIDS):
        def __init__(self, input_dim, cfg, gate, xai_gate=None):
            super().__init__(input_dim, cfg)
            self.gate, self.xai_gate = gate, xai_gate

        def online_update(self, X_batch, X_full, y_full):
            """Returns preds, n_accepted, X_new, y_new, added (mask of batch rows that
            entered training) and clean (their labels before the noise flips)."""
            preds, pred_en, pred_de, confs = self._predict(X_batch)
            if self.gate == "pseudofilter":  # upstream rule, unchanged
                # Recompute upstream's labels for logging (_predict is deterministic here).
                clean = preds.copy()
                clean[~((confs >= self.cfg.CONFIDENCE_THR) & (pred_en == pred_de))] = 0
                preds, n_acc, X_new, y_new = super().online_update(X_batch, X_full, y_full)
                return preds, n_acc, X_new, y_new, np.ones(len(preds), bool), clean
            accept = np.ones(len(preds), bool)
            if self.gate in ("conf_drop", "conf_xai"):
                accept &= (confs >= self.cfg.CONFIDENCE_THR) & (pred_en == pred_de)
            if self.gate in ("xai", "conf_xai"):
                self.xai_gate.calibrate(self.model, lambda X: self._predict(X)[0])
                accept &= self.xai_gate.accept(self.model, X_batch, preds)
            pseudo = preds[accept].copy()
            # same label-noise injection as upstream, applied to the accepted labels
            flip = np.random.choice(len(pseudo), size=int(self.cfg.LAMBDA_FLIP * len(pseudo)),
                                    replace=False)
            pseudo[flip] = 1 - pseudo[flip]
            X_new = np.vstack([X_full, X_batch[accept]])
            y_new = np.concatenate([y_full, pseudo])
            self._train(X_new, y_new, self.cfg.EPOCH1)
            return preds, int(accept.sum()), X_new, y_new, accept, preds[accept]

    return GatedAOCIDS


def evaluate(model, X_te, y_te, cat_te, zero_day):
    preds = model._predict(X_te)[0]
    zd = cat_te == zero_day
    known_att = (y_te == 1) & ~zd
    return {
        "acc": accuracy_score(y_te, preds) * 100,
        "f1": f1_score(y_te, preds, zero_division=0) * 100,
        "precision": precision_score(y_te, preds, zero_division=0) * 100,
        "recall": recall_score(y_te, preds, zero_division=0) * 100,
        "zd_recall": preds[zd].mean() * 100,
        "known_attack_recall": preds[known_att].mean() * 100,
        "fpr": preds[y_te == 0].mean() * 100,
    }


def run(pf, data, gate, zero_day, seed, args):
    X_tr, y_tr, cat_tr, X_te, y_te, cat_te = data
    cfg = pf.Config()
    if args.quick:
        cfg.EPOCH0, cfg.EPOCH1, cfg.UPDATE_EVERY = 10, 1, 8000
    np.random.seed(seed * 42)
    torch.manual_seed(seed * 42)
    idx0, stream = make_stream(y_tr, cat_tr, zero_day, cfg.INIT_RATIO, args.zd_start, seed)
    X0, y0 = X_tr[idx0], y_tr[idx0]
    xai_gate = XAIGate(X0, y0, args.q, args.eg_samples, args.n_ref, args.n_bg, seed) \
        if gate in ("xai", "conf_xai") else None
    model = make_learner_class(pf)(X_tr.shape[1], cfg, gate, xai_gate)
    model.fit_initial(X0, y0)
    log = [{"batch": 0, **evaluate(model, X_te, y_te, cat_te, zero_day)}]
    print(f"  [{gate}] after init  acc={log[0]['acc']:.2f} zd_recall={log[0]['zd_recall']:.2f}")
    X_lab, y_lab = X0.copy(), y0.copy()
    n_batches = len(stream) // cfg.UPDATE_EVERY
    for b in range(n_batches):
        t0 = time.time()
        ib = stream[b * cfg.UPDATE_EVERY:(b + 1) * cfg.UPDATE_EVERY]
        preds, n_acc, X_lab, y_lab, added, clean = model.online_update(X_tr[ib], X_lab, y_lab)
        truth, is_zd = y_tr[ib][added], cat_tr[ib][added] == zero_day
        prec = lambda m: float((clean[m] == truth[m]).mean() * 100) if m.any() else float("nan")
        row = {
            "batch": b + 1,
            "n_accepted": n_acc,  # passed the gate
            "n_added": int(added.sum()),  # entered training (pseudofilter: all, rejected as normal)
            "label_precision": prec(np.ones(len(clean), bool)),  # before the noise flips
            "label_precision_normal": prec(clean == 0),
            "label_precision_attack": prec(clean == 1),
            "batch_pred_accuracy": float((preds == y_tr[ib]).mean() * 100),
            "zd_in_batch": int((cat_tr[ib] == zero_day).sum()),
            "zd_added_as_normal": int(((clean == 0) & is_zd).sum()),  # poisoned
            "zd_added_as_attack": int(((clean == 1) & is_zd).sum()),
            "zd_rejected": int((cat_tr[ib] == zero_day).sum() - is_zd.sum()),
            "seconds": time.time() - t0,
            **evaluate(model, X_te, y_te, cat_te, zero_day),
        }
        log.append(row)
        print(f"  [{gate} {b + 1:>2}/{n_batches}] acc={row['acc']:.2f} zd_recall={row['zd_recall']:.2f} "
              f"added={row['n_added']} label_prec={row['label_precision']:.1f} "
              f"zd normal/attack/rejected={row['zd_added_as_normal']}/{row['zd_added_as_attack']}"
              f"/{row['zd_rejected']} ({row['seconds']:.0f}s)")
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gates", nargs="+", default=GATES, choices=GATES)
    ap.add_argument("--zero_day", nargs="+", default=["DoS"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--zd_start", type=float, default=0.3)
    ap.add_argument("--q", type=float, default=0.10, help="XAI threshold quantile")
    ap.add_argument("--eg_samples", type=int, default=16, help="expected-gradients samples")
    ap.add_argument("--n_ref", type=int, default=3000, help="X0 samples for prototypes")
    ap.add_argument("--n_bg", type=int, default=256, help="background samples")
    ap.add_argument("--quick", action="store_true", help="smoke test: fewer epochs and batches")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    torch.set_num_threads(int(os.environ.get("THREADS", torch.get_num_threads())))
    pf = load_pseudofilter()
    data = load_data(pf, pf.Config())
    os.makedirs(args.out, exist_ok=True)
    for zd in args.zero_day:
        assert zd in set(data[2]), f"unknown attack_cat {zd}"
        for seed in args.seeds:
            for gate in args.gates:
                name = f"{zd}_seed{seed}_{gate}{'_quick' if args.quick else ''}"
                path = os.path.join(args.out, name + ".csv")
                if os.path.exists(path):
                    print("skip", path)
                    continue
                print(f"\n=== zero-day={zd} seed={seed} gate={gate}")
                log = run(pf, data, gate, zd, seed, args)
                pd.DataFrame(log).to_csv(path, index=False)
    with open(os.path.join(args.out, "config_last_run.json"), "w") as f:
        json.dump(vars(args), f, indent=1)


if __name__ == "__main__":
    main()
