"""Reproduce the PseudoFilter + MixupAug + LiteAE result (paper: ~90.8% accuracy).

Runs the upstream main block's steps with the upstream functions and Config.
Usage: python reproduce_pseudofilter.py [--runs 5]
"""
import argparse

from upstream import load_pseudofilter

ap = argparse.ArgumentParser()
ap.add_argument("--runs", type=int, default=None, help="default: upstream Config.RUNS (5)")
args = ap.parse_args()

pf = load_pseudofilter()
cfg = pf.Config()
if args.runs is not None:
    cfg.RUNS = args.runs
print(f"Device : {cfg.DEVICE}")
X_train, y_train, X_test, y_test = pf.load_unsw(cfg)
finals, bests = [], []
for run in range(cfg.RUNS):
    print(f"\n{'═' * 50}  Run {run + 1}/{cfg.RUNS}")
    f, b = pf.run_once(X_train, y_train, X_test, y_test, cfg, run_id=run)
    finals.append(f)
    bests.append(b)
pf.print_table(finals, bests)
