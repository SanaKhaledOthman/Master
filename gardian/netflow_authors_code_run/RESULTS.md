# GARDIAN: authors' code on NetFlow v3 (unmodified)

**Code.** [hanisami/nids_continual_learning](https://github.com/hanisami/nids_continual_learning/tree/2aad9eb710781fe24a1d198aaa68462b70e0759d),
commit `2aad9eb`. No file was changed. The code is not copied here (the repository has no license);
`run_authors_code.sh` downloads it.

**Data.** NF-UNSW-NB15-v3 and NF-BoT-IoT-v3 from Hugging Face (`keys-i/netFlow`), merged by
`prepare_netflow.py`:

* 675,043 flows in four classes: Benign 201,989, Reconnaissance 167,074, DoS 155,980, DDoS 150,000.
* At most 150k rows are sampled per dataset and class.
* The IP addresses and the binary `Label` column are dropped. `Label` would otherwise leak the
  target, because the authors' preprocessing keeps every numeric column as a feature.

**Commands.** The authors' README example, with DDoS as the unseen class:

```bash
python src/data/preprocessing.py NF-v3-UNSW-BoT.csv --class_col Attack --save_dir preprocessed --parquet --chunksize 200000
cd src && python main.py --data_root .. --target_class DDoS --seen_cap_total 200000 \
  --seen_cap_per_class 30000 --unseen_cap 80000 --test_cap_per_class 5000 --ppo_steps 20000 \
  --gan_epochs 10 --mlp_epochs 2 --run_cgan_diagnostics --run_rl_diagnostics
```

The run took 21 min on 4 CPU cores.

## Classifier before and after PPO-driven continual learning

Accuracy and per-class recall on the full test split (135,009 flows):

| | Accuracy | Benign | DDoS (unseen) | DoS | Reconnaissance |
|---|---|---|---|---|---|
| Pretrained MLP | 0.729 | 0.924 | **0.000** | 0.962 | 0.931 |
| After GARDIAN | 0.793 | 0.961 | **0.258** | 0.959 | 0.916 |

On the run's own evaluation set (19,001 flows), accuracy is 0.724 before and 0.786 after, with a
peak of 0.836 at PPO step 10,240. See `curve_metrics.png`.

## CGAN diagnostics (DDoS), cf. paper Table 2

| Metric | Value |
|---|---|
| Diversity ratio | 0.741 |
| Feature mean abs. diff | 0.0064 |
| Feature std abs. diff | 0.0136 |
| Generated-to-real NN distance | 0.071 |
| CGAN training time | 29.6 s |
| Generation time (2000 samples) | 0.0044 s |

## RL diagnostics, cf. paper Table 3

| Metric | Value |
|---|---|
| Total PPO time | 1177 s |
| Mean / max policy inference time | 2.0 / 70.8 ms |
| Mean retraining-round time | 0.056 s |
| Policy decisions (all without manual override) | 20,000 (autonomy rate 1.00) |
| Mean samples per round (CGAN / replay) | 17.5 (10.1 / 7.4) |
| Final round: total samples, CGAN fraction | 19, 0.63 |

## Notes

* This is not an exact reproduction of the paper:
  * it uses NetFlow **v3** and only 2 of the 4 datasets;
  * the paper does not give the command behind its reported numbers.
* With the README's settings the efficiency penalty is off (`--reward_beta 0.0` is the default).
* The authors' code has no Layer 1 (MAE + DBSCAN). Its CGAN is trained directly on the true DDoS
  samples.

## Files

* `run_authors_code.sh`: downloads the authors' code (commit `2aad9eb`) and the data, then repeats every step of this run
* `prepare_netflow.py`: our data-preparation script (the only code we wrote for this run)
* `curve_return.png`: PPO episodic return
* `curve_metrics.png`: accuracy and F1 during training
* `pca_real_vs_generated.png`: CGAN real vs generated samples (cf. Fig. 7)
* `sample_selection_over_rounds.png`: samples chosen per round (cf. Fig. 8)
* `cgan_metrics.json`, `rl_metrics.json`, `run.log`: raw outputs
