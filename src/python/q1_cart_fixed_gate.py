"""Exploratory fixed-F02 gate followed by a CART binary classifier."""
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.tree import DecisionTreeClassifier
from q1_structure_rule import INPUT, LABELS, OUTPUT, git_commit, present

COMMON = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")


def main():
    records = []
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"Date", "CallType", "F02", "PulseRate", *COMMON}.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns")
        for line, row in enumerate(reader, 2):
            label, date = row["CallType"].strip().lower(), row["Date"].strip()
            if label not in LABELS or not date:
                raise ValueError(f"Invalid type or date at line {line}")
            values = [float(row[c]) for c in COMMON]
            if not np.isfinite(values).all():
                raise ValueError(f"Invalid common feature at line {line}")
            f02 = present(row["F02"], "F02", line)
            pulse = present(row["PulseRate"], "PulseRate", line)
            records.append((values + [int(pulse)], label, date, f02, pulse))
    if not records:
        raise ValueError("No observations")
    x = np.asarray([r[0] for r in records]); y = np.asarray([r[1] for r in records])
    groups = np.asarray([r[2] for r in records]); has_f02 = np.asarray([r[3] for r in records])
    has_pulse = np.asarray([r[4] for r in records]); predicted = np.empty(len(y), dtype="<U4")
    for train, test in LeaveOneGroupOut().split(x, y, groups):
        predicted[test[has_f02[test]]] = "tv"
        test_remaining = test[~has_f02[test]]
        if not len(test_remaining):
            continue
        train_remaining = train[~has_f02[train]]
        if set(y[train_remaining]) != {"flat", "mod"}:
            raise ValueError("Training split lacks a binary class")
        tree = DecisionTreeClassifier(criterion="gini", max_depth=3, min_samples_leaf=3, random_state=42)
        predicted[test_remaining] = tree.fit(x[train_remaining], y[train_remaining]).predict(x[test_remaining])
    meta = dict(run_id=datetime.now(timezone.utc).strftime("q1_cart_fixed_gate_%Y%m%dT%H%M%SZ"),
                input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                shared_code_sha256=hashlib.sha256(Path(__file__).with_name("q1_structure_rule.py").read_bytes()).hexdigest(),
                git_head=git_commit(), code_state="See code hashes; working tree may differ from HEAD.",
                first_stage="F02 recorded -> tv; no F02 -> binary CART",
                features=list(COMMON) + ["pulse_recorded"],
                parameters=dict(criterion="gini", max_depth=3, min_samples_leaf=3, random_state=42),
                validation="Leave-one-date-out for CART; first-stage F02 gate is fixed after examining the same dataset.",
                accuracy=accuracy_score(y, predicted), balanced_accuracy=balanced_accuracy_score(y, predicted),
                macro_f1=f1_score(y, predicted, labels=LABELS, average="macro"),
                label_order=list(LABELS), confusion_matrix=confusion_matrix(y, predicted, labels=LABELS).tolist(),
                missing_pulse_mod_n=int(((y == "mod") & ~has_pulse).sum()),
                missing_pulse_mod_correct=int(((y == "mod") & ~has_pulse & (predicted == "mod")).sum()),
                limitations="F02 recording may encode label or measurement process; selection is post hoc; date is not individual; no independent audio validation.",
                versions=dict(python=platform.python_version(), numpy=np.__version__, sklearn=sklearn.__version__))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "cart_fixed_gate_metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
