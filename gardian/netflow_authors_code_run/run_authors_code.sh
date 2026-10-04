#!/usr/bin/env bash
# Reproduces the results in this folder with the GARDIAN authors' code, unmodified.
# Code: https://github.com/hanisami/nids_continual_learning (commit 2aad9eb, no license file,
# so it is downloaded here rather than copied into this repository).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:-$HOME/gardian_work}"
mkdir -p "$WORK/netflow"

# 1. Authors' code at the exact commit used
git clone https://github.com/hanisami/nids_continual_learning "$WORK/gardian_original"
git -C "$WORK/gardian_original" checkout 2aad9eb710781fe24a1d198aaa68462b70e0759d
pip install -r "$WORK/gardian_original/requirements.txt" pyarrow

# 2. NetFlow v3 data from Hugging Face (keys-i/netFlow)
for f in NF-UNSW-NB15-v3 NF-BoT-IoT-v3; do
  curl -L -o "$WORK/netflow/$f.parquet" \
    "https://huggingface.co/datasets/keys-i/netFlow/resolve/main/data/$f.parquet"
done

# 3. Data preparation (our script; writes NF-v3-UNSW-BoT.csv)
sed "s#/home/user/netflow#$WORK/netflow#g" "$HERE/prepare_netflow.py" > "$WORK/netflow/prepare_netflow.py"
python "$WORK/netflow/prepare_netflow.py"

# 4. Authors' preprocessing and pipeline, exactly as in their README (DDoS = unseen class)
cd "$WORK/gardian_original"
python src/data/preprocessing.py "$WORK/netflow/NF-v3-UNSW-BoT.csv" --class_col Attack \
  --save_dir preprocessed --parquet --chunksize 200000
cd src
python main.py --data_root .. --target_class DDoS --seen_cap_total 200000 \
  --seen_cap_per_class 30000 --unseen_cap 80000 --test_cap_per_class 5000 --ppo_steps 20000 \
  --gan_epochs 10 --mlp_epochs 2 --run_cgan_diagnostics --run_rl_diagnostics
echo "Results: $WORK/gardian_original/src/outputs/"
