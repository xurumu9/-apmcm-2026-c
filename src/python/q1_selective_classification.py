"""Compare the full structural rule and an abstaining variant on Data01."""
import csv
import hashlib
import json
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from q1_structure_rule import INPUT, LABELS, OUTPUT, git_commit, present


def main():
    full = Counter()
    selective = Counter()
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"CallType", "F02", "PulseRate"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns")
        for line, row in enumerate(reader, 2):
            actual = row["CallType"].strip().lower()
            if actual not in LABELS:
                raise ValueError(f"Unknown CallType on CSV line {line}")
            has_f02 = present(row["F02"], "F02", line)
            has_pulse = present(row["PulseRate"], "PulseRate", line)
            full[actual, "tv" if has_f02 else "mod" if has_pulse else "flat"] += 1
            selective[actual, "tv" if has_f02 else "mod" if has_pulse else "abstain"] += 1
    total = sum(full.values())
    if not total:
        raise ValueError("No observations")
    covered = sum(selective[a, b] for a in LABELS for b in LABELS)
    correct_covered = sum(selective[a, a] for a in LABELS)
    full_correct = sum(full[a, a] for a in LABELS)
    by_class = {}
    for actual in LABELS:
        n = sum(full[actual, pred] for pred in LABELS)
        class_covered = sum(selective[actual, pred] for pred in LABELS)
        by_class[actual] = dict(n=n, covered=class_covered, abstained=selective[actual, "abstain"],
                                coverage=class_covered / n if n else None)
    meta = {
        "run_id": datetime.now(timezone.utc).strftime("q1_selective_%Y%m%dT%H%M%SZ"),
        "input_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_code_sha256": hashlib.sha256(Path(__file__).with_name("q1_structure_rule.py").read_bytes()).hexdigest(),
        "git_head": git_commit(),
        "code_state": "See code hashes; working tree may differ from HEAD.",
        "n": total,
        "full_rule_correct": full_correct,
        "full_rule_agreement": full_correct / total,
        "selective_covered": covered,
        "selective_abstained": total - covered,
        "selective_coverage": covered / total,
        "selective_correct": correct_covered,
        "selective_agreement_among_covered": correct_covered / covered if covered else None,
        "per_class": by_class,
        "validation": "Same-table exploratory agreement, not independent test or unknown-audio accuracy.",
        "limitation": "Recording status may reflect label definition or measurement process; abstention is not a calibrated uncertainty estimate.",
        "dependencies": {"python": platform.python_version(), "external": []},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "selective_classification_counts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["run_id", "rule", "actual", "predicted", "count"])
        for name, counts, preds in (("full", full, LABELS), ("selective", selective, (*LABELS, "abstain"))):
            for actual in LABELS:
                for predicted in preds:
                    writer.writerow([meta["run_id"], name, actual, predicted, counts[actual, predicted]])
    (OUTPUT / "selective_classification_metadata.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
