#!/usr/bin/env bash
# Full experiment (upstream PseudoFilter config). Logs and CSVs go to $OUT.
set -euo pipefail
cd "$(dirname "$0")"
OUT=${OUT:-results}
mkdir -p "$OUT"
python -u g1_experiment.py --zero_day Fuzzers --seeds 0 1 2 --out "$OUT" 2>&1 | tee -a "$OUT/g1_fuzzers.log"
python -u reproduce_pseudofilter.py 2>&1 | tee "$OUT/pseudofilter_reproduction.log"
python -u g1_experiment.py --zero_day Exploits --seeds 0 1 2 --out "$OUT" 2>&1 | tee -a "$OUT/g1_exploits.log"
