"""Exploratory within-Mod missingness diagnosis; no classifier is fitted."""
import csv
import hashlib
import itertools
import json
import math
import os
import platform
import subprocess
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "apmcm_mod_diagnostic"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv"
FEATURES = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")
SEED, PERMUTATIONS = 20261127, 20000


def holm(values):
    order = np.argsort(values)
    result = np.empty(len(values))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(values) - rank) * values[i]))
        result[i] = running
    return result


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f))
    rows = [(i, r) for i, r in enumerate(all_rows, 1) if r["CallType"].strip().lower() == "mod"]
    x = np.array([[float(r[k]) for k in FEATURES] for _, r in rows])
    missing = np.array([r["PulseRate"].strip().lower() in {"", "na", "nan", "null"} for _, r in rows])
    dates = np.array([r["Date"].strip() for _, r in rows])
    ids = np.array([i for i, _ in rows])
    assert x.shape == (40, 6) and missing.sum() == 6 and np.isfinite(x).all()
    run_id = datetime.now(timezone.utc).strftime("mod_heterogeneity_%Y%m%dT%H%M%SZ")
    out = ROOT / "results/q1" / run_id
    out.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(SEED)
    blocks = [np.flatnonzero(dates == d) for d in np.unique(dates)]
    assignments = []
    possibilities = 1
    for block in blocks:
        k = int(missing[block].sum())
        possibilities *= math.comb(len(block), k)
        assignments.append(list(itertools.combinations(block, k)))
    assert possibilities <= 100000, "Restricted exact enumeration too large"
    restricted = np.array([sum((list(part) for part in parts), [])
                           for parts in itertools.product(*assignments)], dtype=int)
    unrestricted = np.array([rng.choice(len(x), int(missing.sum()), replace=False)
                             for _ in range(PERMUTATIONS)])
    ranks = np.column_stack([rankdata(x[:, j]) for j in range(6)])
    observed = ranks[missing].sum(axis=0)
    center = missing.sum() * (len(x) + 1) / 2
    block_center = sum(ranks[b].sum(axis=0) * missing[b].mean() for b in blocks)
    p_unrestricted = (1 + (np.abs(ranks[unrestricted].sum(axis=1) - center)
                          >= np.abs(observed - center) - 1e-9).sum(axis=0)) / (PERMUTATIONS + 1)
    p_restricted = (np.abs(ranks[restricted].sum(axis=1) - block_center)
                    >= np.abs(observed - block_center) - 1e-9).mean(axis=0)
    summary, tests = [], []
    for j, name in enumerate(FEATURES):
        for group, mask in [("recorded", ~missing), ("missing", missing)]:
            v = x[mask, j]
            q1, median, q3 = np.quantile(v, [.25, .5, .75])
            summary.append(dict(feature=name, group=group, n=len(v), minimum=v.min(),
                                q1=q1, median=median, q3=q3, maximum=v.max()))
        u = observed[j] - missing.sum() * (missing.sum() + 1) / 2
        tests.append(dict(feature=name, rank_biserial_missing_vs_recorded=2*u/(6*34)-1,
                          unrestricted_p=p_unrestricted[j], unrestricted_holm=holm(p_unrestricted)[j],
                          date_exact_p=p_restricted[j], date_exact_holm=holm(p_restricted)[j]))
    write_csv(out / "feature_summary.csv", summary)
    write_csv(out / "exploratory_tests.csv", tests)
    date_rows = [dict(date=d, n_recorded=int(np.sum((dates == d) & ~missing)),
                      n_missing=int(np.sum((dates == d) & missing)))
                 for d in sorted(set(dates), key=lambda s: datetime.strptime(s, "%d/%m/%Y"))]
    write_csv(out / "date_counts.csv", date_rows)
    # Use the 34 recorded Mod as the fixed descriptive reference; no classifier.
    reference = x[~missing]
    mean, scale = reference.mean(axis=0), reference.std(axis=0, ddof=1)
    assert np.all(scale > 0)
    z = (x-mean)/scale
    _, singular, vt = np.linalg.svd(z[~missing], full_matrices=False)
    explained = singular**2 / (singular**2).sum()
    scores = z @ vt.T
    ref_ids = ids[~missing]
    distances = np.linalg.norm(z[:, None, :] - z[~missing][None, :, :], axis=2)
    for i in np.flatnonzero(~missing):
        distances[i, ref_ids == ids[i]] = np.inf
    q1, q3 = np.quantile(reference, [.25, .75], axis=0)
    diagnostic = []
    for i, (row_id, row) in enumerate(rows):
        nearest = int(np.argmin(distances[i]))
        item = dict(source_row_id=row_id, date=row["Date"], location=row["Location"],
                    group="missing" if missing[i] else "recorded", nearest_recorded_row=int(ref_ids[nearest]),
                    nearest_distance=float(distances[i, nearest]), centroid_distance=float(np.linalg.norm(z[i])),
                    n_features_within_recorded_range=int(((x[i]>=reference.min(0)) & (x[i]<=reference.max(0))).sum()),
                    n_features_within_recorded_iqr=int(((x[i]>=q1)&(x[i]<=q3)).sum()))
        for j, name in enumerate(FEATURES):
            item[name] = x[i, j]
            item[name+"_z"] = z[i, j]
            item[name+"_within_range"] = bool(reference[:, j].min()<=x[i,j]<=reference[:, j].max())
            item["pc"+str(j+1)] = scores[i,j]
        diagnostic.append(item)
    write_csv(out / "sample_diagnostics.csv", diagnostic)
    write_csv(out / "pca_loadings.csv", [dict(feature=f, **{"pc"+str(k+1):vt[k,j] for k in range(6)})
                                         for j,f in enumerate(FEATURES)])
    fig, axes = plt.subplots(2,3,figsize=(12,7),layout="constrained")
    for j, ax in enumerate(axes.flat):
        ax.boxplot([reference[:,j], x[missing,j]], positions=[0,1], widths=.4, showfliers=False)
        for a,mask in enumerate([~missing, missing]):
            ax.scatter(a+rng.uniform(-.08,.08,mask.sum()), x[mask,j],s=22,alpha=.7)
        ax.set_xticks([0,1],["Recorded (n=34)","Missing (n=6)"])
        ax.set_title(FEATURES[j]);ax.set_ylabel("s" if j==0 else "Hz")
    fig.savefig(out/"feature_distributions.png",dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,5),layout="constrained")
    for mask,label,marker in [(~missing,"PulseRate recorded (34)","o"),(missing,"PulseRate missing (6)","^")]:
        ax.scatter(scores[mask,0],scores[mask,1],label=label,marker=marker)
    for i in np.flatnonzero(missing):
        offset = (-25, -12) if ids[i] == 107 else (4, 4)
        ax.annotate(str(ids[i]),scores[i,:2],xytext=offset,textcoords="offset points")
    ax.set_xlabel(f"PC1 ({explained[0]:.1%})");ax.set_ylabel(f"PC2 ({explained[1]:.1%})")
    ax.legend();ax.set_title("PCA fitted on recorded Mod; descriptive projection")
    fig.savefig(out/"pca_projection.png",dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,5),layout="constrained")
    for a,mask in enumerate([~missing,missing]):
        ax.scatter(a+rng.uniform(-.06,.06,mask.sum()), distances[mask].min(axis=1),s=35)
    for i in np.flatnonzero(missing):
        ax.annotate(str(ids[i]),(1.1,distances[i].min()),fontsize=9)
    ax.set_xticks([0,1],["Recorded (self excluded)","Missing"])
    ax.set_ylabel("Nearest recorded-Mod distance (6 standardized features)")
    ax.set_title("Descriptive nearest-neighbor distances; no outlier cutoff")
    fig.savefig(out/"nearest_distances.png",dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4),layout="constrained")
    idx=np.arange(len(date_rows));a=[r['n_recorded'] for r in date_rows];b=[r['n_missing'] for r in date_rows]
    ax.bar(idx,a,label="Recorded");ax.bar(idx,b,bottom=a,label="Missing")
    ax.set_xticks(idx,[r['date'] for r in date_rows],rotation=55,ha="right")
    ax.set_ylabel("Mod recordings");ax.legend()
    fig.savefig(out/"date_distribution.png",dpi=180);plt.close(fig)
    media=[]
    for p in sorted((ROOT/'data/raw/media').glob('*.wav')):
        with wave.open(str(p),'rb') as w:
            media.append(dict(file=p.name,channels=w.getnchannels(),rate_hz=w.getframerate(),
                              duration_s=w.getnframes()/w.getframerate()))
    try:
        head=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.CalledProcessError):head=None
    meta=dict(run_id=run_id,seed=SEED,permutations=PERMUTATIONS,date_assignments=possibilities,
              input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),git_head=head,
              code_state="Diagnostic script may be uncommitted; identify by script hash.",
              versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__),
              scaling="Recorded Mod mean and sample SD; PCA fitted only to 34 recorded Mod.",
              explained_variance_ratio=explained.tolist(),reference_mean=mean.tolist(),reference_sd=scale.tolist(),
              tests="Two-sided absolute pooled-rank sum deviations. Unrestricted Monte Carlo plus-one; date-restricted exact enumeration. Holm across six features separately per family.",
              limitations="Exploratory missingness association, no causal inference or equivalence/subtype claim. Date not individual identity; within-date exchangeability unconfirmed. PCA and distances descriptive, not CV or outlier tests.",
              media=media,raw_columns=list(all_rows[0]))
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('OUTPUT',out)
    print('TESTS',json.dumps(tests))
    print('MISSING_DIAG',json.dumps([r for r in diagnostic if r['group']=='missing']))
    print('PCA',explained.tolist(),'date assignments',possibilities)
    print('REFERENCE NN',np.quantile(distances[~missing].min(axis=1),[0,.25,.5,.75,1]).tolist())
    print('DATES',json.dumps(date_rows))


if __name__ == '__main__':
    main()
