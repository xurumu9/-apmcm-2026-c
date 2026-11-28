"""Produce a table for all Data01 acoustic features, retaining missingness."""
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from q1_structure_rule import INPUT, LABELS, OUTPUT, git_commit, present

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ("Duration", "F01", "F02", "Fpeak", "Q25", "Q50", "Q75", "PulseRate")
TEST_TABLE = OUTPUT / "acoustic_results_table.csv"
TEST_META = OUTPUT / "acoustic_tests_metadata.json"


def quantile(values, p):
    values = sorted(values)
    position = (len(values) - 1) * p
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def main():
    input_hash = hashlib.sha256(INPUT.read_bytes()).hexdigest()
    test_meta = json.loads(TEST_META.read_text(encoding="utf-8"))
    upstream_script = ROOT / "src/python/q1_acoustic_tests.py"
    if test_meta["input_sha256"] != input_hash:
        raise ValueError("Existing statistical results use a different input; regenerate them first")
    if test_meta["script_sha256"] != hashlib.sha256(upstream_script.read_bytes()).hexdigest():
        raise ValueError("Existing statistical results use a different code version; regenerate them first")
    with TEST_TABLE.open(encoding="utf-8", newline="") as stream:
        tests = {row["feature"]: row for row in csv.DictReader(stream)}
    if set(tests) != set(FEATURES) - {"F02", "PulseRate"}:
        raise ValueError("Unexpected set of upstream tests")
    if any(row["run_id"] != test_meta["run_id"] for row in tests.values()):
        raise ValueError("Statistics table and metadata have different run IDs")
    data = {(feature, label): [] for feature in FEATURES for label in LABELS}
    totals = {label: 0 for label in LABELS}
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"CallType", *FEATURES}.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns")
        for line, row in enumerate(reader, 2):
            label = row["CallType"].strip().lower()
            if label not in LABELS:
                raise ValueError(f"Unknown call type at line {line}")
            totals[label] += 1
            for feature in FEATURES:
                if present(row[feature], feature, line):
                    data[feature, label].append(float(row[feature]))
    if any(n == 0 for n in totals.values()):
        raise ValueError("Expected all three call types")
    run_id = datetime.now(timezone.utc).strftime("q1_feature_table_%Y%m%dT%H%M%SZ")
    output = []
    for feature in FEATURES:
        row = dict(run_id=run_id, feature=feature, unit="s" if feature == "Duration" else "Hz")
        for label in LABELS:
            values = data[feature, label]
            row[f"{label}_n"] = len(values)
            row[f"{label}_missing"] = totals[label] - len(values)
            for key, q in (("q1", 0.25), ("median", 0.5), ("q3", 0.75)):
                row[f"{label}_{key}"] = quantile(values, q) if values else ""
        test = tests.get(feature)
        for key in ("statistic_h", "overall_p", "overall_p_holm",
                    "flat_vs_mod_p_holm", "flat_vs_mod_rank_biserial",
                    "flat_vs_tv_p_holm", "flat_vs_tv_rank_biserial",
                    "mod_vs_tv_p_holm", "mod_vs_tv_rank_biserial"):
            row[key] = test[key] if test else ""
        row["test_status"] = "six_common_features" if test else "not_tested_three_groups"
        output.append(row)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "all_acoustic_features_table.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    meta = dict(run_id=run_id, input_sha256=input_hash,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                shared_code_sha256=hashlib.sha256(Path(__file__).with_name("q1_structure_rule.py").read_bytes()).hexdigest(),
                upstream_run_id=test_meta["run_id"], upstream_code_sha256=test_meta["script_sha256"],
                upstream_table_sha256=hashlib.sha256(TEST_TABLE.read_bytes()).hexdigest(),
                git_head=git_commit(), code_state="See script hashes; working tree may differ from HEAD.",
                quantile_method="linear", missing_markers=["", "NA", "NaN", "null"],
                limitations="F02 and PulseRate not tested across three groups; structural missingness is not zero.",
                python=platform.python_version())
    (OUTPUT / "all_acoustic_features_metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
