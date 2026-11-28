"""Standard-library Q3 release verification and explicit frozen-context replay.

verify: no raw data, dependencies, model fitting or result writes required.
check-context: verify private historical inputs; never downloads/copies them.
run-final: only after a successful context check, replay approved four steps.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RELEASE=ROOT/'experiments/reports/q3_release'


def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def validate_manifest(base,manifest):
    """Reject traversal and hash/size mismatches; return issues without mutation."""
    base=Path(base).resolve();issues=[]
    for item in manifest['files']:
        rel=item['path'];p=(base/rel).resolve()
        if not p.is_relative_to(base):issues.append(f'OUTSIDE_ROOT {rel}');continue
        if not p.is_file():issues.append(f'MISSING {rel}');continue
        if p.stat().st_size!=item['bytes'] or digest(p)!=item['sha256']:issues.append(f'HASH_MISMATCH {rel}')
    return issues


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['verify','check-context','run-final'])
    parser.add_argument('--output',type=Path,help='New final-revision directory; must not already exist')
    args=parser.parse_args(argv)
    filename='release_manifest.json' if args.command=='verify' else 'private_context_manifest.json'
    manifest=json.loads((RELEASE/filename).read_text(encoding='utf-8'))
    base=RELEASE if args.command=='verify' else ROOT
    issues=validate_manifest(base,manifest)
    if issues:
        print('\n'.join(issues));print('NOT READY: restore the documented inputs; no model was run.')
        return 2
    print(f'PASS {args.command}: {len(manifest["files"])} files match SHA-256')
    if args.command!='run-final':return 0
    output=(args.output or ROOT/'results/q3/final_revision'/datetime.now(timezone.utc).strftime('q3_replay_%Y%m%dT%H%M%SZ')).resolve()
    if not output.is_relative_to(ROOT/'results/q3/final_revision'):
        parser.error('--output must remain inside results/q3/final_revision')
    if output.exists():parser.error('--output already exists; historical outputs are never overwritten')
    for step in range(1,5):
        subprocess.run([sys.executable,'-B',str(ROOT/'src/python/q3_final_revision.py'),str(step),'--run',str(output)],cwd=ROOT,check=True)
    print('Final revision replay complete:',output)
    return 0


if __name__=='__main__':raise SystemExit(main())
