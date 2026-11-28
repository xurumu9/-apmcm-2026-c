"""Exact expected performance under hypothetical test-time indicator flips."""
import csv
import hashlib
import itertools
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.tree import DecisionTreeClassifier
from q1_structure_rule import INPUT, LABELS, OUTPUT, git_commit, present

COMMON = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")
RATES = (0.01, 0.05, 0.10)


def main():
    records = []
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"Date", "CallType", "F02", "PulseRate", *COMMON}.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns")
        for line, row in enumerate(reader, 2):
            label, date = row["CallType"].strip().lower(), row["Date"].strip()
            if label not in LABELS or not date:
                raise ValueError(f"Invalid label or date at line {line}")
            features = [float(row[name]) for name in COMMON]
            if not np.isfinite(features).all():
                raise ValueError(f"Invalid common feature at line {line}")
            has_f02 = present(row["F02"], "F02", line)
            has_pulse = present(row["PulseRate"], "PulseRate", line)
            records.append((features, label, date, has_f02, has_pulse))
    if not records:
        raise ValueError("No observations")
    x = np.asarray([r[0] for r in records]); y = np.asarray([r[1] for r in records])
    dates = np.asarray([r[2] for r in records]); f02 = np.asarray([r[3] for r in records])
    pulse = np.asarray([r[4] for r in records]); predictions = np.empty((len(y), 2, 2), dtype="<U4")
    for train, test in LeaveOneGroupOut().split(x, y, dates):
        train_mask = ~f02[train]
        train_y = y[train[train_mask]]
        if set(train_y) != {"flat", "mod"}:
            raise ValueError("Training fold lacks flat or mod")
        train_x = np.column_stack((x[train[train_mask]], pulse[train[train_mask]].astype(int)))
        model = DecisionTreeClassifier(criterion="gini", max_depth=3, min_samples_leaf=3, random_state=42)
        model.fit(train_x, train_y)
        for f_flip, p_flip in itertools.product((0, 1), repeat=2):
            hypothetical_f02 = np.logical_xor(f02[test], bool(f_flip))
            hypothetical_pulse = np.logical_xor(pulse[test], bool(p_flip))
            pred = np.full(len(test), "tv", dtype="<U4")
            remaining = ~hypothetical_f02
            if remaining.any():
                test_x = np.column_stack((x[test[remaining]], hypothetical_pulse[remaining].astype(int)))
                pred[remaining] = model.predict(test_x)
            predictions[test, f_flip, p_flip] = pred

    reference = json.loads((OUTPUT / "cart_fixed_gate_metadata.json").read_text(encoding="utf-8"))
    input_hash = hashlib.sha256(INPUT.read_bytes()).hexdigest()
    baseline_script = Path(__file__).with_name("q1_cart_fixed_gate.py")
    if reference["input_sha256"] != input_hash or reference["script_sha256"] != hashlib.sha256(baseline_script.read_bytes()).hexdigest():
        raise ValueError("Baseline results differ from current data or code; regenerate and review")
    baseline = confusion_matrix(y, predictions[:, 0, 0], labels=LABELS).tolist()
    if baseline != reference["confusion_matrix"]:
        raise ValueError("Reconstructed baseline does not match the fixed-gate result")
    scenario_specs = [("baseline", 0.0, 0.0)]
    for rate in RATES:
        scenario_specs.extend((("f02_only", rate, 0.0), ("pulse_only", 0.0, rate),
                               ("both_independent", rate, rate)))
    run_id = datetime.now(timezone.utc).strftime("q1_structure_sensitivity_%Y%m%dT%H%M%SZ")
    output = []
    for scenario, q_f02, q_pulse in scenario_specs:
        per_sample = np.zeros(len(y), dtype=float)
        for f_flip, p_flip in itertools.product((0, 1), repeat=2):
            probability = (q_f02 if f_flip else 1 - q_f02) * (q_pulse if p_flip else 1 - q_pulse)
            per_sample += probability * (predictions[:, f_flip, p_flip] == y)
        recalls = {label: float(per_sample[y == label].mean()) for label in LABELS}
        output.append(dict(run_id=run_id, scenario=scenario, f02_flip_probability=q_f02,
                           pulse_flip_probability=q_pulse, n=len(y),
                           expected_correct=float(per_sample.sum()), expected_accuracy=float(per_sample.mean()),
                           expected_flat_recall=recalls["flat"], expected_mod_recall=recalls["mod"],
                           expected_tv_recall=recalls["tv"],
                           expected_balanced_accuracy=sum(recalls.values()) / len(LABELS)))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "structure_sensitivity_scenarios.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=output[0].keys())
        writer.writeheader(); writer.writerows(output)
    meta = dict(run_id=run_id, input_sha256=input_hash,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                baseline_script_sha256=reference["script_sha256"], baseline_run_id=reference["run_id"],
                shared_code_sha256=hashlib.sha256(Path(__file__).with_name("q1_structure_rule.py").read_bytes()).hexdigest(),
                git_head=git_commit(), code_state="See code hashes; working tree may differ from HEAD.",
                method="Exact expectation across 4 independent test-time F02/pulse indicator-flip combinations per sample, using unchanged fold-specific trained trees.",
                preprocessing="Original data and training indicators unchanged; test feature values unchanged.",
                assumptions="Symmetric false-positive/false-negative flip probability; both indicators independent within sample; rates are scenarios, not measured error rates.",
                limitations="Results conditional on these Data01 observations and post-hoc fixed model; no sampling CI, no individual-group guarantee, no independent unknown-audio validation; field missingness is not proven structure absence.",
                rates=list(RATES), versions=dict(python=platform.python_version(), numpy=np.__version__, sklearn=sklearn.__version__))
    (OUTPUT / "structure_sensitivity_metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    for row in output:
        print(row["scenario"], row["f02_flip_probability"], row["pulse_flip_probability"],
              "expected accuracy", round(row["expected_accuracy"], 6),
              "class recalls", round(row["expected_flat_recall"], 4),
              round(row["expected_mod_recall"], 4), round(row["expected_tv_recall"], 4))


if __name__ == "__main__":
    main()
