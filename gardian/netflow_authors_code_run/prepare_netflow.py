"""Data preparation only (no change to the authors' code).

Merge NF-UNSW-NB15-v3 and NF-BoT-IoT-v3 into one CSV with the paper's classes
(Benign, DoS, DDoS, Reconnaissance), sampling at most CAP rows per (dataset, class).
Drops IPv4 addresses and the binary 'Label' column (it equals Attack != Benign, so
keeping it as a numeric feature would leak the target).
"""
import pyarrow.parquet as pq
import pandas as pd

CAP = 150_000
CLASSES = ["Benign", "DoS", "DDoS", "Reconnaissance"]
parts = []
for name in ["NF-UNSW-NB15-v3", "NF-BoT-IoT-v3"]:
    path = f"/home/user/netflow/{name}.parquet"
    attack = pq.read_table(path, columns=["Attack"]).to_pandas()["Attack"]
    keep = (attack[attack.isin(CLASSES)].groupby(attack, group_keys=False)
                  .apply(lambda g: g.sample(min(len(g), CAP), random_state=42)).index.sort_values())
    # read row groups one at a time and keep only the sampled rows (memory-safe)
    f, rows, start = pq.ParquetFile(path), [], 0
    for i in range(f.num_row_groups):
        rg = f.read_row_group(i).to_pandas()
        sel = keep[(keep >= start) & (keep < start + len(rg))] - start
        rows.append(rg.iloc[sel])
        start += len(rg)
    df = pd.concat(rows).drop(columns=["IPV4_SRC_ADDR", "IPV4_DST_ADDR", "Label"])
    print(name, df["Attack"].value_counts().to_dict())
    parts.append(df)
out = pd.concat(parts, ignore_index=True).sample(frac=1, random_state=42)
out.to_csv("/home/user/netflow/NF-v3-UNSW-BoT.csv", index=False)
print("written", out.shape, out["Attack"].value_counts().to_dict())
