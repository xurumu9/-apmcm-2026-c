"""Prepare a traceable long table and a compact audit of Data03–Data11.

Run from any directory: python src/python/propagation_audit.py
Inputs are read from data/raw/propagation and are never modified.
The source row ID is a CSV data-row number, not an independent sample ID.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'data' / 'raw' / 'propagation'
OUTPUT = ROOT / 'data' / 'processed' / 'propagation_long.csv'
REPORT = ROOT / 'experiments' / 'reports' / 'q2_1_audit_summary.json'
DISTANCES = (4, 8, 16, 32, 64, 128, 256)
MAPPING = {
    3: ('flat', 'spectrogram'), 4: ('mod', 'spectrogram'), 5: ('tv', 'spectrogram'),
    6: ('flat', 'amplitude_spectrum'), 7: ('mod', 'amplitude_spectrum'),
    8: ('tv', 'amplitude_spectrum'), 9: ('flat', 'envelope'),
    10: ('mod', 'envelope'), 11: ('tv', 'envelope'),
}

def audit():
    records, files = [], []
    for number, (call_type, metric) in MAPPING.items():
        paths = sorted(INPUT.glob(f'Data{number:02d}_*.csv'))
        if len(paths) != 1:
            raise ValueError(f'Expected exactly one Data{number:02d} CSV, found {len(paths)} in {INPUT}')
        path = paths[0]
        raw = path.read_bytes()
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            expected = [f'{d}m' for d in DISTANCES]
            if reader.fieldnames != expected:
                raise ValueError(f'{path.name}: unexpected columns {reader.fieldnames}')
            rows = list(reader)
        summary = {str(d): {'valid_n': 0, 'missing_n': 0, 'min': None, 'max': None} for d in DISTANCES}
        for index, row in enumerate(rows, 1):
            for d in DISTANCES:
                raw_value = (row[f'{d}m'] or '').strip()
                missing = raw_value.upper() in ('', 'NA', 'NAN')
                value = None if missing else float(raw_value)
                if value is not None and not 0 <= value <= 1:
                    raise ValueError(f'{path.name}: row {index}, {d}m has invalid correlation {raw_value!r}')
                group = summary[str(d)]
                if missing:
                    group['missing_n'] += 1
                else:
                    group['valid_n'] += 1
                    group['min'] = value if group['min'] is None else min(group['min'], value)
                    group['max'] = value if group['max'] is None else max(group['max'], value)
                records.append([call_type, metric, d, index, raw_value if not missing else '', int(missing), path.name])
        files.append({'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                      'data_rows': len(rows), 'by_distance': summary})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['call_type', 'metric', 'distance_m', 'source_row_id', 'correlation', 'missing', 'source_file'])
        writer.writerows(records)
    report = {'run_id': 'q2_1_audit_v1', 'cleaning_version': 'q2_1_v1',
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'python_version': platform.python_version(), 'dependencies': 'Python standard library',
              'source_row_id': '1-based data row within the source CSV; not a pairing identifier',
              'missing_rule': 'empty, NA or NaN => missing; no imputation',
              'distance_m': list(DISTANCES), 'long_rows_including_missing': len(records),
              'files': files}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(records)} rows to {OUTPUT.relative_to(ROOT)} and {REPORT.relative_to(ROOT)}')

if __name__ == '__main__':
    audit()
