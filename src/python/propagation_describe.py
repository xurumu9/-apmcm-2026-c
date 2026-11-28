"""Describe and plot observed propagation correlations; no model is fitted.

Inputs: data/processed/propagation_long.csv (run propagation_audit.py first).
Outputs: aggregate report and a figure; raw and row-level data are not shared.
Requires matplotlib. No assumption of independent rows or cross-file pairing.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'data/processed/propagation_long.csv'
REPORTS = ROOT / 'experiments/reports'
FIGURES = ROOT / 'figures/q2'
CALLS = ('flat', 'mod', 'tv')
DISTANCES = (4, 8, 16, 32, 64, 128, 256)
METRICS = ('spectrogram', 'amplitude_spectrum', 'envelope')
LABELS = ('Spectrogram', 'Amplitude spectrum', 'Amplitude envelope')
COLORS = ('#0072B2', '#D55E00', '#009E73')
MARKERS = ('o', 's', '^')

def main():
    if not INPUT.is_file():
        raise FileNotFoundError('Run src/python/propagation_audit.py first')
    groups = {(c, m, d): [] for c in CALLS for m in METRICS for d in DISTANCES}
    totals = dict.fromkeys(groups, 0)
    with INPUT.open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            key = (row['call_type'], row['metric'], int(row['distance_m']))
            if key not in groups:
                raise ValueError(f'Unexpected group: {key}')
            totals[key] += 1
            if row['missing'] == '1':
                if row['correlation']:
                    raise ValueError('Missing marker conflicts with value')
            elif row['missing'] == '0':
                value = float(row['correlation'])
                if not 0 <= value <= 1:
                    raise ValueError('Correlation outside [0, 1]')
                groups[key].append(value)
            else:
                raise ValueError('Unexpected missing flag')
    records = []
    for key, values in groups.items():
        if len(values) < 2:
            raise ValueError(f'Insufficient observations: {key}')
        c, m, d = key
        records.append({'call_type': c, 'metric': m, 'distance_m': d,
                        'total_n': totals[key], 'valid_n': len(values),
                        'missing_n': totals[key] - len(values),
                        'mean': statistics.mean(values), 'sample_sd': statistics.stdev(values)})
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    with (REPORTS / 'q2_2_descriptive_summary.csv').open('w', encoding='utf-8', newline='') as f:
        # Match the repository's *.csv eol=lf rule so hashes survive Git checkout.
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(records)
    lookup = {(r['call_type'], r['metric'], r['distance_m']): r for r in records}
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5), sharey=True, layout='constrained')
    for axis, call in zip(axes, CALLS):
        for metric, label, color, marker in zip(METRICS, LABELS, COLORS, MARKERS):
            subset = [lookup[(call, metric, d)] for d in DISTANCES]
            axis.plot(DISTANCES, [r['mean'] for r in subset], color=color,
                      marker=marker, linewidth=1.7, markersize=5, label=label)
        axis.set_title({'flat': 'Flat', 'mod': 'Modulated', 'tv': 'Two-voice'}[call], weight='bold')
        axis.set_xlim(0, 270); axis.set_ylim(0, 1)
        axis.set_xticks([4, 32, 64, 128, 256]); axis.grid(alpha=.2)
        axis.set_xlabel('Distance (m)')
    axes[0].set_ylabel('Correlation with 1 m reference')
    axes[0].legend(loc='lower left', fontsize=8, frameon=True)
    fig.suptitle('Observed mean correlation by call type and distance', weight='bold')
    fig.savefig(FIGURES / 'propagation_observed_means.png', dpi=200)
    plt.close(fig)
    metadata = {'run_id': 'q2_2_descriptive_v1', 'cleaning_version': 'q2_1_v1',
                'input_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
                'distances_m': list(DISTANCES), 'interval': 'none',
                'n_groups': len(records), 'random_seed': None}
    (REPORTS / 'q2_2_descriptive_metadata.json').write_text(
        json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(records)} groups and 1 figure')

if __name__ == '__main__':
    main()
