"""Create the paper's eight-panel acoustic-feature comparison from Data01."""
import csv
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "apmcm_q1_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv"
OUTPUT = ROOT / "figures/q1_acoustic_features.png"
GROUPS = ("flat", "mod", "tv")
COLORS = ("#4C78A8", "#E0903B", "#559A75")
FEATURES = (("Duration", "Duration (s)"), ("F01", "F01 (Hz)"),
            ("F02", "F02 (Hz)"), ("Fpeak", "Fpeak (Hz)"),
            ("Q25", "Q25 (Hz)"), ("Q50", "Q50 (Hz)"),
            ("Q75", "Q75 (Hz)"), ("PulseRate", "Pulse rate (Hz)"))

values = {(name, group): [] for name, _ in FEATURES for group in GROUPS}
with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
    for row in csv.DictReader(stream):
        group = row["CallType"].strip().lower()
        if group not in GROUPS:
            raise ValueError(f"Unexpected call type: {group}")
        for name, _ in FEATURES:
            raw = row[name].strip()
            if raw.lower() not in ("", "na", "nan", "null"):
                number = float(raw)
                if not np.isfinite(number):
                    raise ValueError(f"Invalid value for {name}")
                values[name, group].append(number)

fig, axes = plt.subplots(2, 4, figsize=(12, 5.8), constrained_layout=True)
rng = np.random.default_rng(20261127)
for ax, (name, label) in zip(axes.flat, FEATURES):
    for pos, (group, color) in enumerate(zip(GROUPS, COLORS), 1):
        sample = values[name, group]
        if sample:
            ax.boxplot([sample], positions=[pos], widths=.35, showfliers=False,
                       patch_artist=True, boxprops={"facecolor": color, "alpha": .35, "color": "black"},
                       medianprops={"color": "black", "linewidth": 1.3},
                       whiskerprops={"color": "black"}, capprops={"color": "black"})
            ax.scatter(pos + rng.uniform(-.09, .09, len(sample)), sample,
                       s=10, color=color, alpha=.65, edgecolors="none")
    ax.set_xticks([1, 2, 3], [f"{g}\n(n={len(values[name, g])})" for g in GROUPS])
    ax.set_ylabel(label)
    ax.set_xlim(.5, 3.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(direction="out", labelsize=8)
fig.savefig(OUTPUT, dpi=300)
plt.close(fig)
print(f"Saved {OUTPUT}")
