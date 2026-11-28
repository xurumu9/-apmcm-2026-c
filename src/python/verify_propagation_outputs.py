"""Independently check Q2 raw-to-long-to-summary values and provenance.

This is a data integrity check, not a validation of a scientific model.
It never writes files. Run from anywhere after generating Q2 outputs.
"""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISTANCES = (4, 8, 16, 32, 64, 128, 256)
FILES = {3: ('flat', 'spectrogram'), 4: ('mod', 'spectrogram'), 5: ('tv', 'spectrogram'),
         6: ('flat', 'amplitude_spectrum'), 7: ('mod', 'amplitude_spectrum'),
         8: ('tv', 'amplitude_spectrum'), 9: ('flat', 'envelope'),
         10: ('mod', 'envelope'), 11: ('tv', 'envelope')}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def require(condition, message):
    if not condition: raise ValueError(message)

def main():
    source = ROOT / 'data/raw/propagation'
    longpath = ROOT / 'data/processed/propagation_long.csv'
    summarypath = ROOT / 'experiments/reports/q2_2_descriptive_summary.csv'
    reports = ROOT / 'experiments/reports'
    raw = {}; counts = {}
    audit = json.loads((reports / 'q2_1_audit_summary.json').read_text(encoding='utf-8'))
    hashes = {entry['file']: entry['sha256'] for entry in audit['files']}
    for num, (call, metric) in FILES.items():
        paths = list(source.glob(f'Data{num:02d}_*.csv'))
        require(len(paths) == 1, f'Data{num:02d}: expected one raw file')
        p = paths[0]
        require(hashes.get(p.name) == sha(p), f'Raw file hash mismatch: {p.name}')
        with p.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            require(reader.fieldnames == [f'{d}m' for d in DISTANCES], f'Unexpected columns: {p.name}')
            for row_id, row in enumerate(reader, 1):
                for d in DISTANCES:
                    value = (row[f'{d}m'] or '').strip()
                    if value.upper() in ('', 'NA', 'NAN'): value = ''
                    key = (p.name, row_id, d)
                    raw[key] = (call, metric, value)
                    counts.setdefault((call, metric, d), []).append(value)
    remaining = dict(raw); long_count = 0
    with longpath.open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            key = (row['source_file'], int(row['source_row_id']), int(row['distance_m']))
            require(key in remaining, f'Duplicate or unknown long-table key: {key}')
            call, metric, value = remaining.pop(key)
            require((row['call_type'], row['metric'], row['correlation'], row['missing']) ==
                    (call, metric, value, '0' if value else '1'), f'Row mismatch: {key}')
            long_count += 1
    require(not remaining and long_count == len(raw), 'Long table is missing source cells')
    seen = set()
    with summarypath.open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            key = (row['call_type'], row['metric'], int(row['distance_m']))
            require(key in counts and key not in seen, f'Duplicate or unknown summary group: {key}')
            seen.add(key)
            vals = [float(x) for x in counts[key] if x]
            require(int(row['total_n']) == len(counts[key]) and int(row['valid_n']) == len(vals)
                    and int(row['missing_n']) == len(counts[key]) - len(vals), f'Count mismatch: {key}')
            require(len(vals) >= 2 and math.isclose(float(row['mean']), statistics.mean(vals), abs_tol=1e-12)
                    and math.isclose(float(row['sample_sd']), statistics.stdev(vals), abs_tol=1e-12),
                    f'Mean or SD mismatch: {key}')
    require(seen == set(counts), 'Summary lacks one or more groups')
    d = json.loads((reports / 'q2_2_descriptive_metadata.json').read_text(encoding='utf-8'))
    v = json.loads((reports / 'q2_dispersion_metadata.json').read_text(encoding='utf-8'))
    require(d['input_sha256'] == sha(longpath), 'Descriptive input hash mismatch')
    require(d['script_sha256'] == sha(ROOT / 'src/python/propagation_describe.py'), 'Descriptive script hash mismatch')
    require(v['input_sha256'] == sha(summarypath), 'Dispersion input hash mismatch')
    require(v['script_sha256'] == sha(ROOT / 'src/python/propagation_dispersion.py'), 'Dispersion script hash mismatch')
    require(audit['script_sha256'] == sha(ROOT / 'src/python/propagation_audit.py'), 'Audit script hash mismatch')
    print(f'PASS: {len(FILES)} source files, {long_count} source cells and {len(seen)} summary groups; provenance hashes match.')

if __name__ == '__main__': main()
