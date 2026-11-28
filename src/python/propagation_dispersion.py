"""Display group mean and sample SD, using the Q2 descriptive summary only.

The error bars describe dispersion among correlation values, not confidence
intervals. The correlations share recordings and are not independent samples.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'experiments/reports/q2_2_descriptive_summary.csv'
OUT = ROOT / 'figures/q2/propagation_mean_sd.png'
META = ROOT / 'experiments/reports/q2_dispersion_metadata.json'
DISTANCES = (4, 8, 16, 32, 64, 128, 256)
CALLS = (('flat', 'Flat'), ('mod', 'Modulated'), ('tv', 'Two-voice'))
METRICS = (('spectrogram', 'Spectrogram'), ('amplitude_spectrum', 'Amplitude spectrum'),
           ('envelope', 'Amplitude envelope'))

def main():
    data = {}
    with SOURCE.open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            key = (row['call_type'], row['metric'], int(row['distance_m']))
            if key in data:
                raise ValueError(f'Duplicate group: {key}')
            mean, sd, n = float(row['mean']), float(row['sample_sd']), int(row['valid_n'])
            if not math.isfinite(mean) or not math.isfinite(sd) or not 0 <= mean <= 1 or sd < 0 or n < 2:
                raise ValueError(f'Invalid summary: {key}')
            data[key] = (mean, sd, n)
    expected = {(c, m, d) for c, _ in CALLS for m, _ in METRICS for d in DISTANCES}
    if set(data) != expected:
        raise ValueError('Expected exactly 63 unique call × metric × distance groups')
    lower = min(0, min(m-s for m,s,n in data.values()) - .03)
    upper = max(1, max(m+s for m,s,n in data.values()) + .03)
    fig, axes = plt.subplots(3, 3, figsize=(12.5, 10.8), sharex=True, sharey=True,
                             layout='constrained')
    for i, (call, call_label) in enumerate(CALLS):
        for j, (metric, metric_label) in enumerate(METRICS):
            ax = axes[i][j]
            pts = [data[(call, metric, d)] for d in DISTANCES]
            ax.errorbar(DISTANCES, [p[0] for p in pts], yerr=[p[1] for p in pts],
                        color='#176da0', marker='o', linestyle='none', capsize=3,
                        markersize=4, linewidth=1.2)
            ax.set_xscale('log', base=2)
            ax.set_xticks(DISTANCES, [str(d) for d in DISTANCES])
            ax.set_ylim(lower, upper)
            ax.grid(axis='y', alpha=.22)
            ns = [p[2] for p in pts]
            ax.set_title(f'{call_label} | {metric_label}\nn = {min(ns)}–{max(ns)} correlation values', fontsize=10)
            if j == 0: ax.set_ylabel('Correlation with 1 m reference')
            if i == 2: ax.set_xlabel('Distance (m; log₂ scale)')
    fig.suptitle('Observed means and sample standard deviations', weight='bold', fontsize=15)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=180)
    plt.close(fig)
    metadata = {'run_id': 'q2_dispersion_v1', 'input_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
                'error_bars': 'sample SD; not a confidence interval', 'x_scale': 'log2',
                'group_count': len(data), 'random_seed': None}
    META.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {OUT.relative_to(ROOT)}; {len(data)} groups')

if __name__ == '__main__':
    main()
