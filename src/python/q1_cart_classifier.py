"""Exploratory CART classifier on six acoustic features and recording indicators."""
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold, cross_val_predict
from sklearn.tree import DecisionTreeClassifier, export_text
from q1_structure_rule import INPUT, LABELS, OUTPUT, git_commit, present

FEATURES = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")
FEATURE_NAMES = (*FEATURES, "f02_observed", "pulse_observed")


def main():
    rows = []
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"Date", "CallType", "F02", "PulseRate", *FEATURES}.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns")
        for line, row in enumerate(reader, 2):
            label, date = row["CallType"].strip().lower(), row["Date"].strip()
            if label not in LABELS or not date:
                raise ValueError(f"Invalid type or date at line {line}")
            values = [float(row[name]) for name in FEATURES]
            if not np.isfinite(values).all():
                raise ValueError(f"Invalid common acoustic feature at line {line}")
            f02 = present(row["F02"], "F02", line)
            pulse = present(row["PulseRate"], "PulseRate", line)
            rows.append((values + [int(f02), int(pulse)], label, date, pulse))
    if not rows:
        raise ValueError("No observations")
    x = np.asarray([row[0] for row in rows]); y = np.asarray([row[1] for row in rows])
    groups = np.asarray([row[2] for row in rows]); pulse = np.asarray([row[3] for row in rows])
    model = DecisionTreeClassifier(criterion="gini", max_depth=3, min_samples_leaf=3, random_state=42)
    predicted = cross_val_predict(model, x, y, groups=groups, cv=LeaveOneGroupOut(), method="predict")
    metrics = dict(accuracy=accuracy_score(y, predicted), balanced_accuracy=balanced_accuracy_score(y, predicted),
                   macro_f1=f1_score(y, predicted, average="macro"),
                   confusion_matrix=confusion_matrix(y, predicted, labels=LABELS).tolist(),
                   pulse_missing_mod_n=int(((y == "mod") & ~pulse).sum()),
                   pulse_missing_mod_correct=int(((y == "mod") & ~pulse & (predicted == "mod")).sum()))
    fold_results = []
    for seed in (1, 2, 3, 4, 42):
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        p = cross_val_predict(model, x, y, cv=cv, method="predict")
        fold_results.append(dict(seed=seed, accuracy=accuracy_score(y, p),
                                 macro_f1=f1_score(y, p, average="macro")))
    model.fit(x, y)
    meta = dict(run_id=datetime.now(timezone.utc).strftime("q1_cart_%Y%m%dT%H%M%SZ"),
                input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                shared_code_sha256=hashlib.sha256(Path(__file__).with_name("q1_structure_rule.py").read_bytes()).hexdigest(),
                git_head=git_commit(), code_state="See code hashes; working tree may differ from HEAD.",
                features=list(FEATURE_NAMES), labels=list(LABELS),
                parameters=dict(criterion="gini", max_depth=3, min_samples_leaf=3, random_state=42),
                date_leave_one_group_out=metrics, random_stratified_5fold=fold_results,
                full_data_tree=export_text(model, feature_names=list(FEATURE_NAMES), decimals=3),
                limitations="Exploratory model chosen on this dataset; date is not individual ID; recording indicators may encode label/measurement process; no independent audio test.",
                versions=dict(python=platform.python_version(), numpy=np.__version__, sklearn=sklearn.__version__))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "cart_classifier_metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
