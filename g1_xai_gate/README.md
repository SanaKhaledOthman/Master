# G1: explanation-gated pseudo-labels for zero-day continual NIDS

Gap G1 from `reviews/zero-day-unsup-drl-cl-xai/gap_duplication_results.txt`: explanations
decide whether an automatically labelled sample may enter continual retraining.

## Base and baseline (upstream code is never modified)

| Role | Code | Pinned commit |
|---|---|---|
| Base framework | AOC-IDS (Zhang et al., INFOCOM 2024), [xinchen930/AOC-IDS](https://github.com/xinchen930/AOC-IDS) | `41bfd75` |
| Baseline and base learner | PseudoFilter + MixupAug + LiteAE (Afzaal et al. 2026), [danishmemon847/AOC-IDS-Pipeline](https://github.com/danishmemon847/AOC-IDS-Pipeline), last section of `unsw_improvement_2.py` | `d843633` |

Neither repository has a license, so neither is copied here. `setup.sh` clones both
next to this repository, checks the SHA-256 of every upstream file used, and downloads
the official UNSW-NB15 partition with `attack_cat` from Hugging Face
(`Mireu-Lab/UNSW-NB15`, whose two file names are swapped).

`upstream.py` executes the PseudoFilter section of the upstream file unchanged. It runs
under a module name other than `__main__`, so the Colab main block is skipped. The only
setting changed is `Config.TRAIN_PATH` / `TEST_PATH`, set at run time.

## Files

| File | What it does |
|---|---|
| `setup.sh` | Clones the upstream code, downloads the data and checks the hashes |
| `upstream.py` | Loads the unmodified PseudoFilter pipeline |
| `reproduce_pseudofilter.py` | Runs the upstream PseudoFilter experiment (paper: 90.76% accuracy, 91.40% F1) |
| `g1_experiment.py` | The G1 experiment: zero-day stream, five pseudo-label gates, logging |
| `run_all.sh` | Every run behind the results below |
| `results/` | Per-batch CSV logs, run logs and `RESULTS.md` |

AOC-IDS itself is reproduced by running its script unchanged inside its own folder. It
needs the versions pinned in its `requirements.txt`: with PyTorch 2.x it crashes at the
first online update.

```bash
uv venv -p python3.10 ../../aoc_env
VIRTUAL_ENV=../../aoc_env uv pip install torch==1.13.1 numpy==1.23.5 pandas==1.5.3 scikit-learn==1.2.1 scipy==1.10.0
cd ../../g1_upstream/AOC-IDS
../../aoc_env/bin/python online_training.py --dataset unsw --epochs 800 --epoch_1 1 --flip_percent 0.05 --sample_interval 2784
```

## Zero-day protocol

* One attack category is removed from the labelled start set X0 (20% of the remaining
  training rows, stratified like upstream).
* That category appears in the unlabelled stream only after the first 30% of it
  (`--zd_start`).
* The model updates every 2,784 flows, exactly as upstream: it pseudo-labels the batch,
  a gate decides which labels enter, it injects 5% label flips (upstream), then retrains
  for 3 epochs.
* Evaluation uses the official UNSW-NB15 test partition, after every batch.

To choose the zero-day class, a model was trained on X0 with each category held out.
Its recall on that unseen category:

| Held-out category | Fuzzers | Exploits | Recon. | Generic | Analysis | Worms | Shellcode | DoS | Backdoor |
|---|---|---|---|---|---|---|---|---|---|
| Zero-day recall (%) | **32.9** | **87.1** | 94.8 | 95.2 | 95.4 | 95.5 | 95.8 | 98.5 | 99.5 |

Most UNSW-NB15 attack categories are caught without ever being seen, so they are not
real zero-days for this detector. The experiments therefore use **Fuzzers** (hard) and
**Exploits** (medium).

## Gates

| Gate | Rule | Rejected samples |
|---|---|---|
| `none` | accept every prediction (AOC-IDS) | — |
| `pseudofilter` | upstream rule, called unchanged: confidence ≥ 0.85 and the encoder and decoder heads agree | added, **labelled normal** (upstream) |
| `conf_drop` | the same rule | dropped |
| `xai` | explanation gate | dropped |
| `conf_xai` | `conf_drop` and `xai` | dropped |

**Explanation gate.**
* Each candidate gets an expected-gradients SHAP attribution (the estimator behind
  `shap.GradientExplainer`) for both head logits, with a background drawn from X0.
* The sample is accepted only if both hold:
  1. its attribution is closer to the predicted class's prototype than to the other
     class's, by at least τ_c;
  2. its encoder- and decoder-head attributions agree (cosine ≥ τ_agree).
* Prototypes and thresholds come only from correctly classified ground-truth X0 samples,
  recomputed before every update. τ is the 10th percentile (`--q`) of the same score
  on X0.
* So a pseudo-label passes only if its explanation looks like those of real labelled
  traffic. Poisoned pseudo-labels cannot move the prototypes.

## Logged per batch

* Test metrics: accuracy, F1, precision, recall, zero-day recall, known-attack recall,
  false-positive rate.
* Labels that entered training:
  * label precision before the upstream noise flips, overall and per class;
  * zero-day samples added as normal (poisoning);
  * zero-day samples added as attack;
  * zero-day samples rejected.

## Run

```bash
./setup.sh
python g1_experiment.py --quick --zero_day Fuzzers   # smoke test, ~5 min on CPU
THREADS=2 ./run_all.sh                               # full runs, several hours on CPU
```

Results: [`results/RESULTS.md`](results/RESULTS.md).
