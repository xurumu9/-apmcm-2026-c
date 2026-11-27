"""Evaluate a structural rule on Data01; this is not independent validation."""

import csv
import hashlib
import json
import math
import platform
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv"
OUTPUT = ROOT / "results/q1"
LABELS = ("flat", "mod", "tv")
MISSING = {"", "na", "nan", "null"}


def present(value, field, line):
    """Recognize documented missing markers; reject invalid numeric values."""
    value = value.strip()
    if value.lower() in MISSING:
        return False
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field} on CSV line {line}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Non-finite {field} on CSV line {line}")
    return True


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    counts = Counter()
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"CallType", "F02", "PulseRate"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing required columns: {required - set(reader.fieldnames or [])}")
        for line, row in enumerate(reader, start=2):
            actual = row["CallType"].strip().lower()
            if actual not in LABELS:
                raise ValueError(f"Unknown CallType on CSV line {line}: {actual!r}")
            has_f02 = present(row["F02"], "F02", line)
            has_pulse = present(row["PulseRate"], "PulseRate", line)
            predicted = "tv" if has_f02 else "mod" if has_pulse else "flat"
            counts[(actual, predicted)] += 1

    n = sum(counts.values())
    if not n:
        raise ValueError("No records found")
    true_totals = {a: sum(counts[a, b] for b in LABELS) for a in LABELS}
    predicted_totals = {b: sum(counts[a, b] for a in LABELS) for b in LABELS}
    if any(not true_totals[a] for a in LABELS):
        raise ValueError("All three call types must be present for macro metrics")
    accuracy = sum(counts[a, a] for a in LABELS) / n
    expected = sum(true_totals[a] * predicted_totals[a] for a in LABELS) / n**2
    kappa = (accuracy - expected) / (1 - expected) if expected != 1 else None
    recalls = {a: counts[a, a] / true_totals[a] for a in LABELS}
    f1 = {
        a: (2 * counts[a, a] / (true_totals[a] + predicted_totals[a]))
        if true_totals[a] + predicted_totals[a] else 0.0
        for a in LABELS
    }
    run_id = datetime.now(timezone.utc).strftime("q1_structure_%Y%m%dT%H%M%SZ")
    metadata = {
        "run_id": run_id,
        "input": INPUT.relative_to(ROOT).as_posix(),
        "input_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_head": git_commit(),
        "code_state": "See script_sha256; script may be uncommitted or differ from git_head.",
        "cleaning": "No modification; empty, NA, NaN and null treated as missing.",
        "rule": "F02 present -> tv; else PulseRate present -> mod; else flat",
        "validation": "In-sample agreement of an exploratory rule; not independent test or audio classification.",
        "assumptions": "Recorded presence represents independently available structural information; missing measurement may violate this.",
        "seed": None,
        "dependencies": {"python": platform.python_version(), "external": []},
        "n": n,
        "accuracy": accuracy,
        "balanced_accuracy": sum(recalls.values()) / len(LABELS),
        "macro_f1": sum(f1.values()) / len(LABELS),
        "cohen_kappa": kappa,
        "recall_by_class": recalls,
        "f1_by_class": f1,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "structure_rule_confusion.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["run_id", "actual", "predicted", "count"])
        for actual in LABELS:
            for predicted in LABELS:
                writer.writerow([run_id, actual, predicted, counts[actual, predicted]])
    (OUTPUT / "structure_rule_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
