# Self-Adaptive IDS for Zero-Day Attacks Using Deep Q-Networks — reproduction

A from-scratch PyTorch reproduction of

> M. Alkasassbeh, E. H. Omoush, M. Almseidin, A. Aldweesh,
> **"A Self-Adaptive Intrusion Detection System for Zero-Day Attacks Using Deep Q-Networks"**,
> *IEEE Access*, vol. 13, pp. 174280–174296, 2025. doi:10.1109/ACCESS.2025.3617792

The paper treats network-flow classification on the UGRansome dataset as a reinforcement-learning
problem. Each flow is a state, the predicted class is the action, and an asymmetric reward penalises
missed ransomware. A DQN agent learns the policy. The paper has no public code, so everything here
follows the description in the paper.

## Architecture of the proposed DQN-based IDS

The diagrams below show the paper's method at three levels: the end-to-end pipeline, the
Q-network layers, and the DQN training loop (Algorithm 1). They render on GitHub. PNG copies are in
`docs/` ([pipeline](docs/pipeline.png), [layers](docs/q_network_layers.png), [training loop](docs/dqn_training_loop.png)).

### 1. End-to-end pipeline (paper Sec. IV, Fig. 3, Fig. 4)

```mermaid
flowchart LR
    A["UGRansome CSV<br/>149,043 flows × 14 cols<br/>labels A / S / SS"] --> B

    subgraph B["Preprocessing (Fig. 3)"]
        direction TB
        B1["1. Remove incomplete records"] --> B2["2. Drop high-cardinality IDs<br/>SeedAddress, ExpAddress, IPaddress"]
        B2 --> B3["3. Label-encode<br/>Protocol, Flag, Family, Threats"]
        B3 --> B4["4. Min-Max scale to 0..1"]
    end

    B --> C{"Split strategy"}
    C -->|"Random 70/30 stratified"| D1["Exp 1 binary<br/>Exp 3 multiclass"]
    C -->|"Zero-day: unseen families in test"| D2["Exp 2 binary<br/>Exp 4 multiclass"]

    D1 --> E
    D2 --> E

    subgraph E["RL environment"]
        direction TB
        E1["State s_t = flow feature vector x_t"]
        E2["Action a_t = predicted class"]
        E3["Reward r_t from Table 2<br/>TP +1.0 · TN +0.1 · FP −0.5 · FN −1.0"]
        E4["Next state s_t+1 = next flow"]
    end

    E <-->|"s_t, r_t / a_t"| F["DQN agent<br/>policy net + target net<br/>+ replay buffer"]
    F --> G["Trained Q-network<br/>a = argmax Q(s, a)"]
    G --> H["Evaluation on test set<br/>accuracy, precision, recall, F1,<br/>confusion matrix"]
```

### 2. Q-network layers (paper Eq. 2, Sec. IV-A)

`Q(s) = W3 · ReLU(W2 · ReLU(W1 · s + b1) + b2) + b3`

```mermaid
flowchart LR
    I["<b>Input layer</b><br/>d = 10 features<br/>Time, Protocol, Flag, Family,<br/>Clusters, BTC, USD, Netflow_Bytes,<br/>Threats, Port"]
    H1["<b>Hidden layer 1</b><br/>Fully connected, 64 neurons<br/>W1 ∈ R^64×d<br/>ReLU"]
    H2["<b>Hidden layer 2</b><br/>Fully connected, 64 neurons<br/>W2 ∈ R^64×64<br/>ReLU"]
    O["<b>Output layer</b><br/>Linear, no activation<br/>one Q-value per action<br/>binary: 2 · multiclass: 3"]
    A["<b>Action</b><br/>argmax over Q-values<br/>Benign / Ransomware<br/>or A / S / SS"]
    I --> H1 --> H2 --> O --> A
```

| Layer | Type | Shape | Activation | Parameters (d = 10, binary) |
|---|---|---|---|---|
| Input | flow feature vector | d = 10 (8 with `--features table1`) | – | – |
| Hidden 1 | Linear | d → 64 | ReLU | 10·64 + 64 = 704 |
| Hidden 2 | Linear | 64 → 64 | ReLU | 64·64 + 64 = 4,160 |
| Output | Linear | 64 → \|A\| (2 or 3) | identity | 64·2 + 2 = 130 (multiclass 195) |
| **Total** | | | | **4,994** (multiclass 5,059) |

The target network Q(s, a; θ⁻) is an identical copy of these layers. Its weights are copied from
the policy network at the end of every episode.

### 3. DQN training loop (paper Eq. 1, Algorithm 1, Table 3)

```mermaid
flowchart TB
    S["Observe state s_t<br/>(one network flow)"] --> EG{"ε-greedy<br/>ε: 1.0 → 0.1, ×0.995 per step"}
    EG -->|"probability ε"| R1["Random action"]
    EG -->|"probability 1−ε"| R2["argmax_a Q_policy(s_t, a)"]
    R1 --> ENV
    R2 --> ENV
    ENV["Environment<br/>reward r_t from Table 2<br/>next flow s_t+1"] --> M[("Replay buffer<br/>capacity 10^5<br/>(s, a, r, s', done)")]
    M -->|"sample minibatch B = 64"| T["TD target<br/>y = r + γ · max_a' Q_target(s', a')<br/>γ = 0.99"]
    T --> L["MSE loss<br/>(y − Q_policy(s, a))²"]
    L --> OPT["Adam, lr = 0.001<br/>update policy net θ"]
    OPT --> S
    OPT -.->|"end of each episode<br/>(20,000 steps, 10 episodes)"| TG["Target net θ⁻ ← θ"]
    TG -.-> T
```

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
gardian/GARDIAN.ipynb       GARDIAN (Sami et al., JISA 2026) implementation, executed
```

## What was implemented (mapping to the paper)

| Paper | Implementation |
|---|---|
| Dataset: UGRansome, 149,043 flows, labels A / S / SS (Table 1, Fig. 1) | `data/ugransome_final2.csv`, the Kaggle `final(2).csv`. Label counts match exactly: S = 66,380, A = 42,561, SS = 40,102 |
| Remove incomplete records; drop `SeedAddress`, `ExpAddress`, `IPaddress`; label-encode `Protocol`, `Flag`, `Family`, `Threats`; Min-Max to [0, 1] (Sec. IV-A, Fig. 3) | `dqn_ids/data.py` |
| Features: all columns left after dropping the 3 high-cardinality IDs (Sec. IV-A text) | default `--features all` (10 features). `--features table1` uses the 8 features listed in Table 1, which omits `Netflow_Bytes` and `Port` |
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
| Feature set | all 10 remaining features (Sec. IV-A text). Matches the paper best, see the sweep below | `--features table1` (8 features in Table 1) |
| Seeds / "best run" | the paper reports its best run; we report the best seed **and** the mean ± std over seeds | `--seeds` |

## Results

Default configuration: Table 3 hyperparameters, all 10 remaining features, scaler fit on the
training split only, seeds 0–2. Regenerate with `python run_experiments.py --seeds 0 1 2`. Every
number below is in `results/`.

| Exp | Setting | Paper accuracy | Reproduced, best seed | Reproduced, mean ± std | Paper macro-F1 | Reproduced macro-F1 |
|---|---|---|---|---|---|---|
| 1 | Binary (Random Split) | 97.6% | **97.7%** | 97.4% ± 0.2% | 0.98 | 0.98 |
| 2 | Binary (Zero-Day Family Split) | 95.9% | **93.2%** | 91.7% ± 1.4% | 0.96 | 0.93 |
| 3 | Multiclass (Random Split) | 97.0% | **97.6%** | 97.6% ± 0.1% | 0.97 | 0.98 |
| 4 | Multiclass (Zero-Day Family Split) | 92.0% | **93.0%** | 92.6% ± 0.4% | 0.92 | 0.93 |

### Per-class recall (best seed)

| Exp | Paper | Reproduced |
|---|---|---|
| 1 | Benign 0.95 / Ransomware 1.00 | Benign 0.95 / Ransomware 1.00 |
| 2 | Benign 0.93 / Ransomware 0.99 | Benign 0.88 / Ransomware 0.98 |
| 3 | A 0.94 / S 0.97 / SS 0.99 | A 0.97 / S 0.97 / SS 0.99 |
| 4 | A 0.90 / S 0.89 / SS 0.99 | A 0.90 / S 0.92 / SS 0.98 |

### Confusion matrices (rows = true, cols = predicted)

| Exp | Paper | Reproduced (best seed) |
|---|---|---|
| 1 | `[[18893, 1021], [65, 24734]]` | `[[18986, 928], [95, 24704]]` |
| 2 | `[[30891, 2493], [570, 40805]]` | `[[29250, 4134], [918, 40457]]` |
| 3 | `[[12050, 450, 268], [416, 19238, 260], [42, 49, 11940]]` | `[[12403, 219, 146], [391, 19368, 155], [65, 98, 11868]]` |
| 4 | `[[17511, 1131, 786], [1723, 25392, 1323], [76, 47, 16399]]` | `[[17516, 1037, 875], [1326, 26092, 1020], [177, 82, 16263]]` |

### Figures

| | Confusion matrix | Loss curve |
|---|---|---|
| Exp 1 | ![](results/exp1_confusion_matrix.png) | ![](results/exp1_loss_curve.png) |
| Exp 2 | ![](results/exp2_confusion_matrix.png) | ![](results/exp2_loss_curve.png) |
| Exp 3 | ![](results/exp3_confusion_matrix.png) | ![](results/exp3_loss_curve.png) |
| Exp 4 | ![](results/exp4_confusion_matrix.png) | ![](results/exp4_loss_curve.png) |

### Sensitivity to the choices the paper leaves open

The table gives best-seed / mean accuracy over seeds 0–2. The first row is the default.

| Features | Scaler fit on | Exp 1 (paper 97.6) | Exp 2 (paper 95.9) | Exp 3 (paper 97.0) | Exp 4 (paper 92.0) |
|---|---|---|---|---|---|
| 10 (all) | train | 97.7% / 97.4% | 93.2% / 91.7% | 97.6% / 97.6% | 93.0% / 92.6% |
| 10 (all) | all | 97.7% / 97.4% | 92.5% / 91.7% | 97.6% / 97.6% | 92.7% / 92.5% |
| 8 (Table 1) | train | 96.9% / 96.7% | 91.3% / 90.6% | 97.2% / 97.0% | 94.0% / 93.6% |
| 8 (Table 1) | all | 96.9% / 96.7% | 93.2% / 91.7% | 97.2% / 97.0% | 94.0% / 93.9% |

### Discussion

- **Exp 1 and Exp 3 (random splits) reproduce.** Exp 1 reaches 97.7 % vs 97.6 %, and its confusion matrix is almost the same as the paper's Fig. 6: 928 vs 1,021 false positives and 95 vs 65 missed ransomware. Exp 3 is 0.6 pts above the paper.
- **The loss curves match the paper's shape.** In the binary experiments the TD loss jumps from ≈0.06 to ≈0.22–0.25 after the first target-network sync and then plateaus (paper Fig. 5/8). This comes from the γ = 0.99 bootstrap. In multiclass the loss decreases steadily, as in Fig. 10/12.
- **Exp 4 (multiclass zero-day) reproduces.** It reaches 93.0 % vs 92.0 %. SS recall is 0.98 (paper 0.99), and S and A are the harder classes, as in the paper.
- **Exp 2 (binary zero-day) is the remaining gap.** It reaches 93.2 % vs the paper's 95.9 %. The error pattern is the same: ransomware recall is 0.98 vs 0.99, and most errors are benign flows from unseen families flagged as ransomware (benign recall 0.88 vs 0.93). This experiment has the highest seed variance (±1.4 pts). The paper reports its best run, so more seeds or unreported details (sample order, seeds) plausibly explain the rest.
- Using the 8 Table-1 features instead of all 10 costs about 0.7 pts on the random splits. Fitting the scaler on all data instead of only the training split makes little difference.

## GARDIAN notebook

`gardian/GARDIAN.ipynb` implements GARDIAN from H. Sami et al., "Deep reinforcement learning for
autonomous and continual network intrusion detection", *JISA* 102 (2026) 104594. The notebook covers:

- Layer 1: a multi-head autoencoder flags emerging patterns, and DBSCAN with semi-supervised labelling assigns their labels.
- Layer 2: a CGAN and a replay buffer supply retraining data, and a PPO agent decides when to fine-tune the MLP classifier and with how many samples.
- Experiments: an ablation (CGAN only / buffer only), the paper's diagnostics, and a reward-sensitivity sweep.

It runs on the bundled UGRansome CSV, where the six held-out ransomware families act as the
emerging patterns. It also has a loader for the paper's NetFlow-v2 CSVs. Run it with
`jupyter notebook gardian/GARDIAN.ipynb` (about 10 min on 4 CPU cores). Section 16 of the notebook
summarises what we observed.

## Notes

- **Dataset source.** Kaggle (`nkongolo/ugransome-dataset`) is the official host. The copy in
  `data/` is the identical `final(2).csv` (149,043 rows, MD5 `0f08326d264a8ba49825e6af779a3c04`),
  taken from a public GitHub mirror.
- **`Family` is an input feature.** In the zero-day splits, the label-encoded value of an unseen
  family never appears during training. This follows the paper's feature list (Table 1).
- **Hardware.** The paper used an i7-8565U CPU and an MX250 GPU. These runs are CPU-only, at about
  4–5 min per experiment per seed.
