"""Compare hard and illustrative smooth fidelity gates on existing Q4 scenarios."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/q4/scenario_summary.csv"
DESTINATION = ROOT / "results/q4/gate_sensitivity.csv"

with SOURCE.open(encoding="utf-8", newline="") as f:
    records = list(csv.DictReader(f))

result = []
for row in records:
    if row["weight_scenario"] != "equal" or float(row["fraction_given_any"]) != .5:
        continue
    fidelity = float(row["q2_fidelity"]) * (1-float(row["reduction"]))
    threshold = float(row["threshold"])
    score = float(row["raw_behavior_score"])
    any_probability = float(row["p_any_original_marker"])
    hard = float(fidelity >= threshold)
    assert abs(float(row["scenario_score"]) - hard*score) < 1e-10
    for width in (.05, .1, .2):
        # width is total transition width; linear ramp from T-width/2 to T+width/2.
        soft = min(1., max(0., (fidelity-(threshold-width/2))/width))
        result.append({"call_type":row["call_type"],"context":row["context"],
                       "distance_m":row["distance_m"],"joint_support":row["joint_support"],
                       "threshold":threshold,"reduction":row["reduction"],
                       "adjusted_fidelity":fidelity,"transition_width":width,
                       "hard_gate":hard,"smooth_gate":soft,"hard_score":hard*score,
                       "smooth_score":soft*score,
                       "hard_scenario_expected_responders":8*.5*any_probability*hard,
                       "smooth_scenario_expected_responders":8*.5*any_probability*soft})
assert len(result) == 27*3*5*3
with DESTINATION.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(result[0]))
    writer.writeheader()
    writer.writerows(result)
print(f"Wrote {len(result)} rows to {DESTINATION}")
