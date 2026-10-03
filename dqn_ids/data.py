"""UGRansome loading, preprocessing and the four train/test splits used in the paper.

Paper Sec. IV-A:
  1. remove incomplete records
  2. drop high-cardinality identifiers (SeedAddress, ExpAddress, IPaddress)
  3. label-encode categorical attributes (Protocol, Flag, Family, Threats)
  4. stratified sampling for the random splits
  5. Min-Max scaling to [0, 1]
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

DEFAULT_CSV = "data/ugransome_final2.csv"

# The Kaggle CSV keeps the original typos "Protcol" and "SeddAddress".
HIGH_CARDINALITY = ["SeddAddress", "ExpAddress", "IPaddress"]
CATEGORICAL = ["Protcol", "Flag", "Family", "Threats"]
LABEL = "Prediction"

# Table 1 "Selected Features".
FEATURES_TABLE1 = ["Time", "Protcol", "Flag", "Family", "Clusters", "Threats", "USD", "BTC"]
# Everything left after removing the high-cardinality identifiers (Sec. IV-A text).
FEATURES_ALL = ["Time", "Protcol", "Flag", "Family", "Clusters", "BTC", "USD",
                "Netflow_Bytes", "Threats", "Port"]
FEATURE_SETS = {"table1": FEATURES_TABLE1, "all": FEATURES_ALL}

MULTICLASS_LABELS = ["A", "S", "SS"]  # alphabetical, as in the paper's Fig. 9 / 11
BINARY_LABELS = ["Benign", "Ransomware"]  # S -> 0, A/SS -> 1

# Ransomware families held out for testing in the zero-day experiments.
# The paper does not list them, but each set is the unique subset of families
# whose rows reproduce the test-set support reported in Table 5 / Table 7
# (Exp 2: 74,759 rows with 33,384 benign; Exp 4: A=19,428, S=28,438, SS=16,522).
ZERO_DAY_TEST_FAMILIES = {
    "binary": ["Cryptohitman", "DMALocker", "JigSaw", "Locky", "TowerWeb", "WannaCry"],
    "multiclass": ["APT", "EDA2", "Globe", "JigSaw", "Razy", "SamSam"],
}


@dataclass
class Split:
    X_train: np.ndarray
    y_train: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    class_names: list
    train_families: list
    test_families: list


def load(csv_path=DEFAULT_CSV):
    df = pd.read_csv(csv_path)
    df = df.dropna().reset_index(drop=True)
    df = df.drop(columns=HIGH_CARDINALITY)
    for col in CATEGORICAL:
        df[col + "_raw"] = df[col]
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))
    return df


def make_split(df, task, split, features="all", test_size=0.3, seed=42,
               scale_on="train"):
    """task: 'binary' | 'multiclass'; split: 'random' | 'zeroday'."""
    cols = FEATURE_SETS[features]
    if task == "binary":
        y = (df[LABEL] != "S").astype(np.int64).to_numpy()
        class_names = BINARY_LABELS
    else:
        y = df[LABEL].map({c: i for i, c in enumerate(MULTICLASS_LABELS)}).to_numpy()
        class_names = MULTICLASS_LABELS
    X = df[cols].to_numpy(dtype=np.float64)
    families = df["Family_raw"].to_numpy()

    if split == "random":
        idx = np.arange(len(df))
        # Stratify on the 3 original labels (matches the paper's test supports).
        tr, te = train_test_split(idx, test_size=test_size, random_state=seed,
                                  stratify=df[LABEL].to_numpy())
    elif split == "zeroday":
        test_fams = set(ZERO_DAY_TEST_FAMILIES[task])
        mask = np.isin(families, list(test_fams))
        tr, te = np.where(~mask)[0], np.where(mask)[0]
    else:
        raise ValueError(split)

    scaler = MinMaxScaler()
    scaler.fit(X[tr] if scale_on == "train" else X)
    Xs = scaler.transform(X).astype(np.float32)
    return Split(Xs[tr], y[tr], Xs[te], y[te], class_names,
                 sorted(set(families[tr])), sorted(set(families[te])))
