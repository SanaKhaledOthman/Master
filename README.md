# Self-Adaptive IDS for Zero-Day Attacks Using Deep Q-Networks — reproduction

A from-scratch PyTorch reproduction of

> M. Alkasassbeh, E. H. Omoush, M. Almseidin, A. Aldweesh,
> **"A Self-Adaptive Intrusion Detection System for Zero-Day Attacks Using Deep Q-Networks"**,
> *IEEE Access*, vol. 13, pp. 174280–174296, 2025. doi:10.1109/ACCESS.2025.3617792

The paper treats network-flow classification on the UGRansome dataset as a reinforcement-learning
problem. Each flow is a state, the predicted class is the action, and an asymmetric reward penalises
missed ransomware. A DQN agent learns the policy. The paper has no public code, so everything here
follows the description in the paper.

## Quick start

```bash
pip install -r requirements.txt
python run_experiments.py                       # all 4 experiments × 5 seeds (~25 min on 4 CPU cores)
python run_experiments.py --exp 2 --seeds 0     # a single run
```

Outputs are written to `results/`:

| File | Content |
|---|---|
| `summary.md` / `summary.json` | paper vs. reproduced accuracy / F1 for every experiment and seed |
| `expN_confusion_matrix.png` | confusion matrix of the best seed (paper Fig. 6, 7, 9, 11) |
| `expN_loss_curve.png` | mean TD loss per episode (paper Fig. 5, 8, 10, 12) |
| `expN_classification_report.txt` | precision / recall / F1 / support (paper Tables 4–7) |

## Repository layout

```
data/ugransome_final2.csv   UGRansome "final(2).csv" (149,043 flows × 14 columns)
dqn_ids/data.py             preprocessing + random / zero-day splits
dqn_ids/env.py              classification-as-RL environment + reward tables
dqn_ids/agent.py            Q-network, replay buffer, DQN agent, Algorithm 1 training loop
run_experiments.py          runs Exp 1–4, writes metrics and figures
```

## What was implemented (mapping to the paper)

| Paper | Implementation |
|---|---|
| Dataset: UGRansome, 149,043 flows, labels A / S / SS (Table 1, Fig. 1) | `data/ugransome_final2.csv`, the Kaggle `final(2).csv`. Label counts match exactly: S = 66,380, A = 42,561, SS = 40,102 |
| Remove incomplete records; drop `SeedAddress`, `ExpAddress`, `IPaddress`; label-encode `Protocol`, `Flag`, `Family`, `Threats`; Min-Max to [0, 1] (Sec. IV-A, Fig. 3) | `dqn_ids/data.py` |
| Features: Time, Protocol, Flag, Family, Clusters, Threats, USD, BTC (Table 1) | default `--features table1`; `--features all` also keeps `Netflow_Bytes` and `Port` |
| Binary: S = benign, A + SS = ransomware | `task="binary"` |
| Random 70/30 stratified split (Exp 1, 3) | `train_test_split(..., stratify=Prediction)`. The test set has 44,713 rows, matching the paper |
| Zero-day family split (Exp 2, 4) | see below |
| Reward TP +1.0, TN +0.1, FP −0.5, FN −1.0 (Table 2) | `env.BINARY_REWARD` |
| MLP d → 64 → 64 → \|A\|, ReLU, linear output (Eq. 2) | `agent.QNetwork` |
| Policy + target network; target synced at the end of each episode | `DQNAgent.update_target()` |
| lr 0.001, γ 0.99, batch 64, 10 episodes × 20,000 steps, ε 1.0 → 0.1 with ×0.995 decay per step, MSE, replay 10⁵, Adam (Table 3) | `agent.DQNConfig` |
| Algorithm 1: ε-greedy act → reward → s′ = next sample → store → sample minibatch → TD target → MSE update → decay ε | `agent.train()` |

### Recovering the zero-day family splits

The paper says ransomware families were split 70/30 into disjoint train and test sets. It does not
say which families went where, but it does report the exact test-set supports. I enumerated all
2¹⁷ subsets of the 17 families. In each case exactly one subset matches the reported supports, so
the splits below should be identical to the paper's:

| Experiment | Held-out (test) families | Test support (paper = reproduced) |
|---|---|---|
| Exp 2, binary | Cryptohitman, DMALocker, JigSaw, Locky, TowerWeb, WannaCry | 74,759 (Benign 33,384 / Ransomware 41,375) |
| Exp 4, multiclass | APT, EDA2, Globe, JigSaw, Razy, SamSam | 64,388 (A 19,428 / S 28,438 / SS 16,522) |

In both cases 6 of the 17 families (≈ 30 %) are held out.

### Choices the paper leaves open

| Item | Default used here | Option |
|---|---|---|
| Multiclass reward (only "positive if correct, negative otherwise") | +1 correct / −1 wrong | `--multiclass-reward asymmetric` (Table 2 generalised to 3 classes) |
| Order of samples within an episode | 20,000 flows drawn uniformly from the training set | – |
| Min-Max scaler fit | training split only (no test leakage) | `--scale-on all` |
| Feature set | Table 1 (8 features) | `--features all` (10 features) |
| Seeds / "best run" | the paper reports its best run; we report the best seed **and** the mean ± std over seeds | `--seeds` |

## Results

RESULTS_PLACEHOLDER

## Notes

- **Dataset source.** Kaggle (`nkongolo/ugransome-dataset`) is the official host. The copy in
  `data/` is the identical `final(2).csv` (149,043 rows, MD5 `0f08326d264a8ba49825e6af779a3c04`),
  taken from a public GitHub mirror.
- **`Family` is an input feature.** In the zero-day splits, the label-encoded value of an unseen
  family never appears during training. This follows the paper's feature list (Table 1).
- **Hardware.** The paper used an i7-8565U CPU and an MX250 GPU. These runs are CPU-only, at about
  4–5 min per experiment per seed.
