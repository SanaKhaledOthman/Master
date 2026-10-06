#!/usr/bin/env bash
# Downloads the two upstream codebases (pinned commits, never modified) and UNSW-NB15.
# Nothing is copied into this repository: neither upstream repo has a license.
set -euo pipefail
# Defaults: next to the repository checkout, outside it.
OUTSIDE=$(cd "$(dirname "$0")/../.." && pwd)
UPSTREAM=${UPSTREAM:-$OUTSIDE/g1_upstream}
DATA=${DATA:-$OUTSIDE/unsw_raw}
mkdir -p "$UPSTREAM" "$DATA"

clone() {  # url dir commit
  [ -d "$UPSTREAM/$2" ] || git clone -q "$1" "$UPSTREAM/$2"
  git -C "$UPSTREAM/$2" checkout -q "$3"
}
clone https://github.com/xinchen930/AOC-IDS.git AOC-IDS 41bfd75153df4c65d37be619385c25c422afb3c1
clone https://github.com/danishmemon847/AOC-IDS-Pipeline.git AOC-IDS-Pipeline d8436331320e274e0e0e268bd085eebfd1069b3a

# Official UNSW-NB15 partition with attack_cat. The Hugging Face mirror has the
# two file names swapped (its test.csv is the 175,341-row training set).
HF=https://huggingface.co/datasets/Mireu-Lab/UNSW-NB15/resolve/main
[ -f "$DATA/UNSW_NB15_training-set.csv" ] || curl -sSL -o "$DATA/UNSW_NB15_training-set.csv" "$HF/test.csv"
[ -f "$DATA/UNSW_NB15_testing-set.csv" ]  || curl -sSL -o "$DATA/UNSW_NB15_testing-set.csv"  "$HF/train.csv"

sha256sum -c - <<SUMS
16b6a333001ecf13467ab118fb3e66c4c2251c9db3e3799a5950e408d0543eeb  $UPSTREAM/AOC-IDS-Pipeline/unsw_improvement_2.py
03b13d52e53f73b6553a34a1984577bea9aeae2831a34e8cfade5155c392ab5f  $UPSTREAM/AOC-IDS/online_training.py
05a111c80485bdd6546820ab908ceac99c0e204821630936acc602b0bad5db51  $UPSTREAM/AOC-IDS/utils.py
bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa  $DATA/UNSW_NB15_training-set.csv
734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559  $DATA/UNSW_NB15_testing-set.csv
SUMS
echo "UPSTREAM=$UPSTREAM DATA=$DATA ready"
