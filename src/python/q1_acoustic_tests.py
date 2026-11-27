"""Describe six common acoustic variables and run exploratory rank tests."""

import csv
import hashlib
import itertools
import json
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "apmcm_q1_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy.stats import kruskal, rankdata

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv"
OUT = ROOT / "results/q1"
FIGURE = ROOT / "figures/q1_fpeak_distribution.png"
FEATURES = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")
GROUPS = ("flat", "mod", "tv")
SEED = 20261127
PERMUTATIONS = 20_000


def holm(pvalues):
    """Holm step-down correction within a specified family of tests."""
    pvalues = np.asarray(pvalues, dtype=float)
    order = np.argsort(pvalues)
    adjusted = np.empty(len(pvalues))
    maximum = 0.0
    for rank, index in enumerate(order):
        maximum = max(maximum, min(1.0, (len(pvalues) - rank) * pvalues[index]))
        adjusted[index] = maximum
    return adjusted


def load_data():
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"CallType", *FEATURES}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns")
        data = {(feature, group): [] for feature in FEATURES for group in GROUPS}
        for line, row in enumerate(reader, 2):
            group = row["CallType"].strip().lower()
            if group not in GROUPS:
                raise ValueError(f"Unknown class at CSV line {line}")
            for feature in FEATURES:
                raw = row[feature].strip()
                if raw.lower() in {"", "na", "nan", "null"}:
                    continue
                value = float(raw)
                if not np.isfinite(value):
                    raise ValueError(f"Non-finite {feature} at line {line}")
                data[feature, group].append(value)
    return {key: np.asarray(values, dtype=float) for key, values in data.items()}


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No data to write: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_fpeak(data):
    values = [data["Fpeak", group] for group in GROUPS]
    fig, ax = plt.subplots(figsize=(5.5, 4.0), layout="constrained")
    ax.boxplot(values, positions=[1, 2, 3], widths=0.32, showfliers=False,
               patch_artist=True, boxprops={"facecolor": "white", "color": "black"},
               medianprops={"color": "black", "linewidth": 1.5},
               whiskerprops={"color": "black"}, capprops={"color": "black"})
    rng = np.random.default_rng(SEED)
    for i, array in enumerate(values, 1):
        ax.scatter(i + rng.uniform(-0.08, 0.08, len(array)), array,
                   s=13, c="0.25", alpha=0.65, edgecolors="none", zorder=3)
    ax.set_xticks([1, 2, 3], [f"{group}\n(n = {len(array)})" for group, array in zip(GROUPS, values)])
    ax.set_ylabel("Peak frequency (Hz)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(direction="out")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, dpi=300)
    plt.close(fig)


def main():
    data = load_data()
    if any(len(data[feature, group]) == 0 for feature in FEATURES for group in GROUPS):
        raise ValueError("Every tested feature requires observations in each group")
    run_id = datetime.now(timezone.utc).strftime("q1_acoustics_%Y%m%dT%H%M%SZ")
    rng = np.random.default_rng(SEED)
    summary, overall, pairs = [], [], []
    for feature in FEATURES:
        for group in GROUPS:
            array = data[feature, group]
            q1, med, q3 = np.quantile(array, [0.25, 0.5, 0.75], method="linear")
            summary.append(dict(run_id=run_id, feature=feature, call_type=group, n=len(array),
                                median=med, q1=q1, q3=q3, minimum=array.min(), maximum=array.max()))
        test = kruskal(*(data[feature, group] for group in GROUPS))
        overall.append(dict(run_id=run_id, feature=feature, statistic_h=test.statistic,
                            p_value=test.pvalue, p_adjusted=None, method="Kruskal-Wallis"))
        for first, second in itertools.combinations(GROUPS, 2):
            a, b = data[feature, first], data[feature, second]
            n1, n2 = len(a), len(b)
            ranks = rankdata(np.concatenate((a, b)), method="average")
            center = n1 * (len(ranks) + 1) / 2
            observed = abs(ranks[:n1].sum() - center)
            extreme = sum(abs(ranks[rng.permutation(len(ranks))[:n1]].sum() - center)
                          >= observed - 1e-10 for _ in range(PERMUTATIONS))
            u = ranks[:n1].sum() - n1 * (n1 + 1) / 2
            pairs.append(dict(run_id=run_id, feature=feature, group_1=first, group_2=second,
                              n_1=n1, n_2=n2, p_value=(extreme + 1) / (PERMUTATIONS + 1),
                              p_adjusted=None, rank_biserial=2 * u / (n1 * n2) - 1,
                              permutations=PERMUTATIONS, extreme=extreme))
    for rows in (overall, pairs):
        for row, value in zip(rows, holm([row["p_value"] for row in rows])):
            row["p_adjusted"] = value
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "feature_summary.csv", summary)
    write_csv(OUT / "acoustic_kruskal_wallis.csv", overall)
    write_csv(OUT / "acoustic_pairwise_permutation.csv", pairs)
    combined = []
    for test in overall:
        feature = test["feature"]
        row = dict(run_id=run_id, feature=feature)
        for item in (s for s in summary if s["feature"] == feature):
            group = item["call_type"]
            for key in ("n", "median", "q1", "q3"):
                row[f"{group}_{key}"] = item[key]
        row.update(statistic_h=test["statistic_h"], overall_p=test["p_value"],
                   overall_p_holm=test["p_adjusted"])
        for item in (p for p in pairs if p["feature"] == feature):
            prefix = f"{item['group_1']}_vs_{item['group_2']}"
            row[f"{prefix}_p_holm"] = item["p_adjusted"]
            row[f"{prefix}_rank_biserial"] = item["rank_biserial"]
        combined.append(row)
    write_csv(OUT / "acoustic_results_table.csv", combined)
    plot_fpeak(data)
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    metadata = dict(run_id=run_id, input=INPUT.relative_to(ROOT).as_posix(),
                    input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    git_head=head, code_state="See script_sha256; working tree may differ from HEAD.",
                    seed=SEED, permutations=PERMUTATIONS, quantile_method="linear",
                    preprocessing="Complete values per feature; missing not replaced; original data unmodified.",
                    test_families="Holm separately for 6 overall tests and 18 pairwise tests.",
                    permutation="Two-sided absolute rank-sum deviation; plus-one Monte Carlo correction.",
                    limitation="Independence/exchangeability of individual calls is not confirmed.",
                    versions=dict(python=platform.python_version(), numpy=np.__version__,
                                  scipy=scipy.__version__, matplotlib=matplotlib.__version__))
    (OUT / "acoustic_tests_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    for item in overall:
        print(item["feature"], "H=", round(item["statistic_h"], 4), "Holm p=", round(item["p_adjusted"], 6))


if __name__ == "__main__":
    main()
