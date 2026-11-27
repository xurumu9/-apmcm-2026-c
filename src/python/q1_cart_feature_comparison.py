"""Compare CART feature sets with grouped nested validation; exploratory."""
import csv
import hashlib
import json
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier
from q1_structure_rule import INPUT, LABELS, OUTPUT, git_commit, present

COMMON = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")


def model(depth, leaf):
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                         DecisionTreeClassifier(criterion="gini", max_depth=depth,
                                                min_samples_leaf=leaf, random_state=42))


def metrics(y, predicted, difficult):
    return dict(accuracy=accuracy_score(y, predicted), balanced_accuracy=balanced_accuracy_score(y, predicted),
                macro_f1=f1_score(y, predicted, labels=LABELS, average="macro", zero_division=0),
                confusion_matrix=confusion_matrix(y, predicted, labels=LABELS).tolist(),
                pulse_missing_mod_n=int(difficult.sum()),
                pulse_missing_mod_correct=int(((predicted == "mod") & difficult).sum()))


def main():
    rows = []
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"Date", "CallType", "F02", "PulseRate", *COMMON}.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns")
        for line, row in enumerate(reader, 2):
            label, date = row["CallType"].strip().lower(), row["Date"].strip()
            if label not in LABELS or not date:
                raise ValueError(f"Invalid call type or date at line {line}")
            values = [float(row[name]) for name in COMMON]
            if not np.isfinite(values).all() or values[1] <= 0 or values[4] <= 0:
                raise ValueError(f"Invalid feature or ratio denominator at line {line}")
            h_f02 = present(row["F02"], "F02", line)
            h_pulse = present(row["PulseRate"], "PulseRate", line)
            rows.append((values, label, date, h_f02, h_pulse,
                         float(row["F02"]) if h_f02 else np.nan,
                         float(row["PulseRate"]) if h_pulse else np.nan))
    if not rows:
        raise ValueError("No observations")
    raw = np.asarray([row[0] for row in rows]); y = np.asarray([row[1] for row in rows])
    dates = np.asarray([row[2] for row in rows]); flags = np.asarray([[row[3], row[4]] for row in rows], dtype=float)
    conditional = np.asarray([[row[5], row[6]] for row in rows]); difficult = (y == "mod") & (flags[:, 1] == 0)
    engineered = np.column_stack((raw[:, 2] / raw[:, 1], raw[:, 3] / raw[:, 1],
                                  raw[:, 4] / raw[:, 1], raw[:, 5] / raw[:, 1],
                                  raw[:, 5] - raw[:, 3], (raw[:, 5] - raw[:, 3]) / raw[:, 4],
                                  raw[:, 4] - raw[:, 3], raw[:, 5] - raw[:, 4]))
    sets = {"base": np.column_stack((raw, flags)),
            "engineered": np.column_stack((raw, flags, engineered)),
            "engineered+values": np.column_stack((raw, flags, engineered, conditional))}
    outer = list(LeaveOneGroupOut().split(raw, y, dates))
    fixed = {}
    for name, x in sets.items():
        predicted = np.empty(len(y), dtype="<U4")
        for train, test in outer:
            predicted[test] = model(3, 3).fit(x[train], y[train]).predict(x[test])
        fixed[name] = metrics(y, predicted, difficult)
    configs = [(name, depth, leaf) for name in sets for depth in (2, 3, 4) for leaf in (3, 5)]
    predicted = np.empty(len(y), dtype="<U4"); selected = []
    for train, test in outer:
        inner = list(GroupKFold(n_splits=4).split(raw[train], y[train], dates[train]))
        best_score, best_config = -1.0, None
        for name, depth, leaf in configs:
            x = sets[name]; inner_prediction = np.empty(len(train), dtype="<U4")
            for fit_idx, val_idx in inner:
                inner_prediction[val_idx] = model(depth, leaf).fit(x[train[fit_idx]], y[train[fit_idx]]).predict(x[train[val_idx]])
            score = f1_score(y[train], inner_prediction, labels=LABELS, average="macro", zero_division=0)
            if score > best_score + 1e-12:
                best_score, best_config = score, (name, depth, leaf)
        name, depth, leaf = best_config
        predicted[test] = model(depth, leaf).fit(sets[name][train], y[train]).predict(sets[name][test])
        selected.append(f"{name}:depth={depth}:min_leaf={leaf}")
    result = dict(run_id=datetime.now(timezone.utc).strftime("q1_cart_features_%Y%m%dT%H%M%SZ"),
                  input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  shared_code_sha256=hashlib.sha256(Path(__file__).with_name("q1_structure_rule.py").read_bytes()).hexdigest(),
                  git_head=git_commit(), code_state="See code hashes; working tree may differ from HEAD.",
                  features=dict(common=list(COMMON), flags=["F02_recorded", "PulseRate_recorded"],
                                engineered=["Fpeak/F01", "Q25/F01", "Q50/F01", "Q75/F01", "Q75-Q25", "(Q75-Q25)/Q50", "Q50-Q25", "Q75-Q50"],
                                conditional_values=["F02", "PulseRate"]),
                  fixed_model=dict(criterion="gini", max_depth=3, min_samples_leaf=3, random_state=42),
                  fixed_results=fixed, nested_date_results=metrics(y, predicted, difficult),
                  selection=dict(outer="leave one date out", inner="GroupKFold(4), training dates only",
                                 score="pooled inner out-of-fold macro-F1", configurations=len(configs),
                                 tie_break="first grid configuration", selected_counts=dict(Counter(selected))),
                  preprocessing="median imputation fitted within each training fold; original input unchanged",
                  limitations="Exploratory same dataset and structure indicators may encode label or measurement; unknown individual identity; no independent audio validation.",
                  versions=dict(python=platform.python_version(), numpy=np.__version__, sklearn=sklearn.__version__))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "cart_feature_comparison_metadata.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
