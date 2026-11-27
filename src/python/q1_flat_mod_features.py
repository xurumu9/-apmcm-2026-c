"""Compare common acoustic features for flat/mod, including date-restricted permutations."""
import csv
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import mannwhitneyu, rankdata

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv"
OUT = ROOT / "results/q1"
FEATURES = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")
SEED, PERMUTATIONS = 20261127, 20_000


def holm(values):
    order = np.argsort(values)
    result = np.empty(len(values))
    last = 0.0
    for k, idx in enumerate(order):
        last = max(last, min(1.0, (len(values) - k) * values[idx]))
        result[idx] = last
    return result


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"Date", "CallType", *FEATURES}.issubset(reader.fieldnames or []):
            raise ValueError("Required columns missing")
        rows = [row for row in reader if row["CallType"].strip() in {"flat", "mod"}]
    x = np.asarray([[float(row[name]) for name in FEATURES] for row in rows])
    if not np.isfinite(x).all():
        raise ValueError("Non-finite acoustic feature")
    is_flat = np.asarray([row["CallType"].strip() == "flat" for row in rows])
    dates = np.asarray([row["Date"].strip() for row in rows])
    if not len(rows) or not is_flat.any() or is_flat.all() or np.any(dates == ""):
        raise ValueError("Missing call type or date")
    blocks = [np.flatnonzero(dates == day) for day in np.unique(dates)]
    mixed = [indices for indices in blocks if 0 < is_flat[indices].sum() < len(indices)]
    rng = np.random.default_rng(SEED)
    run_id = datetime.now(timezone.utc).strftime("q1_flat_mod_%Y%m%dT%H%M%SZ")
    output = []
    for j, feature in enumerate(FEATURES):
        flat, mod = x[is_flat, j], x[~is_flat, j]
        test = mannwhitneyu(flat, mod, alternative="two-sided", method="asymptotic")
        ranks = rankdata(x[:, j], method="average")
        expectation = sum(ranks[indices].sum() * is_flat[indices].mean() for indices in blocks)
        observed = abs(ranks[is_flat].sum() - expectation)
        extreme = 0
        for _ in range(PERMUTATIONS):
            total = sum(rng.permutation(is_flat[indices]) @ ranks[indices] for indices in blocks)
            extreme += abs(total - expectation) >= observed - 1e-9
        flat_q = np.quantile(flat, [0.25, 0.5, 0.75], method="linear")
        mod_q = np.quantile(mod, [0.25, 0.5, 0.75], method="linear")
        output.append(dict(run_id=run_id, feature=feature, flat_n=len(flat), mod_n=len(mod),
                           flat_q1=flat_q[0], flat_median=flat_q[1], flat_q3=flat_q[2],
                           mod_q1=mod_q[0], mod_median=mod_q[1], mod_q3=mod_q[2],
                           u_flat=test.statistic, rank_biserial=2 * test.statistic / (len(flat) * len(mod)) - 1,
                           mw_p=test.pvalue, mw_holm=None, date_permutation_p=(extreme + 1) / (PERMUTATIONS + 1),
                           date_extreme=extreme, date_holm=None))
    for pfield, adjusted in (("mw_p", "mw_holm"), ("date_permutation_p", "date_holm")):
        for row, value in zip(output, holm([row[pfield] for row in output])):
            row[adjusted] = value
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "flat_mod_feature_comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    meta = dict(run_id=run_id, input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), git_head=head,
                code_state="See script_sha256; working tree may differ from HEAD.",
                n_flat=int(is_flat.sum()), n_mod=int((~is_flat).sum()), dates=len(blocks),
                mixed_dates=len(mixed), mixed_date_observations=sum(len(i) for i in mixed),
                seed=SEED, permutations=PERMUTATIONS,
                test="Mann-Whitney asymptotic two-sided; pooled-rank sum with two-sided permutations within date, plus-one correction.",
                corrections="Holm across six features separately for each test family.",
                limitations="Restricted permutation assumes exchangeability within date; date is not individual identity; observational data do not establish causal effect.",
                versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__))
    (OUT / "flat_mod_feature_metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    for row in output:
        print(row["feature"], "rank-biserial", round(row["rank_biserial"], 3),
              "MW Holm", round(row["mw_holm"], 5), "date Holm", round(row["date_holm"], 5))


if __name__ == "__main__":
    main()
