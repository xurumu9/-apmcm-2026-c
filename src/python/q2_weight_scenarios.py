"""Summarize selected weight scenarios, explicitly not confidence intervals."""
import csv
import hashlib
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'experiments' / 'reports'
SOURCE = REPORT / 'q2_candidate_weight_sensitivity.csv'
DEST = REPORT / 'q2_weight_scenario_ranges.csv'
META = REPORT / 'q2_weight_scenario_metadata.json'
CALLS = ('flat', 'mod', 'tv')
THRESHOLDS = ('0.3', '0.5', '0.7')
WEIGHTS = ('equal', 'spectrogram_priority', 'spectrum_priority', 'envelope_priority')

def main():
    with SOURCE.open(encoding='utf-8', newline='') as f:
        records = list(csv.DictReader(f))
    result = []
    for call in CALLS:
        for threshold in THRESHOLDS:
            group = [r for r in records if r['call_type'] == call and r['threshold'] == threshold
                     and r['scenario'].startswith('isotonic_')]
            expected = {'isotonic_' + x for x in WEIGHTS}
            if len(group) != 4 or {r['scenario'] for r in group} != expected:
                raise ValueError(f'Expected four unique weight settings: {call}, {threshold}')
            statuses = {r['status'] for r in group}
            if not statuses <= {'within_range', 'not_met_at_4m', 'at_least_256m'}:
                raise ValueError(f'Unrecognized boundary status: {statuses}')
            values = [float(r['radius_m']) for r in group if r['status'] == 'within_range']
            equal = next(r for r in group if r['scenario'] == 'isotonic_equal')
            lower_status = 'not_met_at_4m' if 'not_met_at_4m' in statuses else 'within_range'
            upper_status = 'at_least_256m' if 'at_least_256m' in statuses else 'within_range'
            lower = '' if lower_status != 'within_range' or not values else min(values)
            upper = '' if upper_status != 'within_range' or not values else max(values)
            result.append([call, threshold, equal['radius_m'], equal['status'], lower, lower_status,
                           upper, upper_status, len(group), 'weight_scenario_range_not_confidence_interval'])
    with DEST.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['call_type', 'threshold', 'equal_weight_radius_m', 'equal_status',
                    'min_observed_scenario_m', 'min_status', 'max_observed_scenario_m',
                    'max_status', 'scenario_count', 'interpretation'])
        w.writerows(result)
    meta = {'run_id': 'q2_weight_scenario_v1', 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'python': platform.python_version(), 'method': 'isotonic', 'weight_schemes': list(WEIGHTS),
            'confidence_interval': False, 'sampling_uncertainty_estimated': False}
    META.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(result)} descriptive scenario rows')

if __name__ == '__main__':
    main()
