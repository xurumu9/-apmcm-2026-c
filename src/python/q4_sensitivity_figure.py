"""Plot selected Q4 sensitivity scenarios after running q4_scenarios.py."""
import csv
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "apmcm_q4_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/q4/scenario_summary.csv"
DESTINATION = ROOT / "figures/q4_sensitivity.png"
with SOURCE.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

def get(call, distance, threshold, reduction, weight, fraction, field):
    matches = [r for r in rows if r["call_type"] == call and r["context"] == "after"
               and int(r["distance_m"]) == distance and float(r["threshold"]) == threshold
               and float(r["reduction"]) == reduction and r["weight_scenario"] == weight
               and float(r["fraction_given_any"]) == fraction]
    if len(matches) != 1:
        raise ValueError(f"Expected one scenario, got {len(matches)}")
    return float(matches[0][field])

def smooth_score(call, distance, reduction, weight):
    fidelity = get(call, distance, .5, reduction, weight, .5, "q2_fidelity") * (1-reduction)
    factor = min(1., max(0., (fidelity-.45)/.1))
    return factor * get(call, distance, .5, reduction, weight, .5, "raw_behavior_score")

calls = ("flat", "mod", "tv")
colors = ("#4C78A8", "#E0903B", "#559A75")
fig, axes = plt.subplots(1, 3, figsize=(12.4, 4.1), constrained_layout=True)
x = np.arange(4)
weights = ("equal", "head_focus", "vocal_focus", "approach_focus")
for i, (call, color) in enumerate(zip(calls, colors)):
    vals = [smooth_score(call, 50, 0, w) for w in weights]
    axes[0].plot(x, vals, marker="o", color=color, label=call)
axes[0].set_xticks(x, ["Equal", "Head", "Vocal", "Approach"], rotation=25, ha="right")
axes[0].set_ylabel("Scenario score")
axes[0].set_title("A  Behavior weights (50 m)", loc="left")

fractions = (.25, .5, .75)
for call, color in zip(calls, colors):
    vals = [get(call, 50, .5, 0, "equal", p, "scenario_expected_responder_count") for p in fractions]
    axes[1].plot(np.array(fractions)*100, vals, marker="o", color=color)
axes[1].set_xticks([25, 50, 75])
axes[1].set_xlabel("Assumed participating fraction (%)")
axes[1].set_ylabel("Scenario expected responders")
axes[1].set_title("B  Participation (50 m)", loc="left")

reductions = (0, .05, .10, .15, .20)
for call, color in zip(calls, colors):
    vals = [smooth_score(call, 150, r, "equal") for r in reductions]
    axes[2].plot(np.array(reductions)*100, vals, marker="o", color=color)
axes[2].set_xticks([0, 5, 10, 15, 20])
axes[2].set_xlabel("Assumed fidelity reduction (%)")
axes[2].set_ylabel("Scenario score")
axes[2].set_title("C  Fidelity reduction (150 m)", loc="left")
for ax in axes:
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(direction="out")
axes[0].legend(frameon=False, loc="upper right")
fig.savefig(DESTINATION, dpi=300)
plt.close(fig)
print(f"Saved {DESTINATION}")
