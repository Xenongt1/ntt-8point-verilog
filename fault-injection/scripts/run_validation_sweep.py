#!/usr/bin/env python3
"""New-input validation campaign using the original RTL injection schedule."""
import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import run_fault_sweep as original
from compare_checks import read_campaign


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vectors', type=int, default=512)
    p.add_argument('--seed', type=int, default=20261015)
    p.add_argument('--selection', type=Path, default=Path('fault-injection/results_selection_32'))
    a = p.parse_args()
    if not 1 <= a.vectors <= 100000:
        sys.exit('Choose between 1 and 100000 validation vectors.')
    selection, _, _ = read_campaign(a.selection)
    rtl = [Path('rtl') / name for name in original.RTL_NAMES]
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in rtl}
    if hashes != selection['rtl_sha256']:
        sys.exit('RTL has changed since the selection campaign. Stop and review.')
    for tool in ('iverilog', 'vvp'):
        if not shutil.which(tool):
            sys.exit(f'Missing {tool}')
    out = Path(f'fault-injection/results_validation_{a.seed}_{a.vectors}')
    if out.exists():
        sys.exit(f'{out} already exists; preserving it. Use another seed for a new campaign.')
    rng = random.Random(a.seed)
    seen = {tuple(v['input']) for v in selection['vectors']}
    vectors = []
    while len(vectors) < a.vectors:
        x = tuple(rng.randrange(17) for _ in range(8))
        if x in seen:
            continue
        seen.add(x)
        vectors.append({'id': len(vectors), 'name': f'held_out_{len(vectors)}',
                        'input': list(x), 'expected': original.reference(x)})
    out.mkdir()
    for name, key in (('inputs.hex', 'input'), ('expected.hex', 'expected')):
        (out / name).write_text(''.join(f"{original.pack(v[key]):010x}\n" for v in vectors))
    bench = original.TESTBENCH.replace('fault-injection/results_selection_32/', out.as_posix() + '/')
    (out / 'tb_fault_sweep.v').write_text(bench)
    meta = dict(selection)
    meta.update(started_utc=datetime.now(timezone.utc).isoformat(), random_seed=a.seed,
                vectors=vectors, rtl_sha256=hashes, selection_campaign=str(a.selection),
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                base_script_sha256=hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest())
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
    version = subprocess.run(['iverilog', '-V'], capture_output=True, text=True)
    (out / 'simulator_version.txt').write_text(version.stdout + version.stderr)
    cmd = ['iverilog', '-g2012', '-s', 'tb_fault_sweep',
           f'-Ptb_fault_sweep.NVECT={a.vectors}', '-o', str(out / 'sweep.vvp')]
    cmd += [str(path) for path in rtl] + [str(out / 'tb_fault_sweep.v')]
    compiled = subprocess.run(cmd, capture_output=True, text=True)
    (out / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        sys.exit(f'Compilation failed: see {out}/compile.log')
    print(f'{a.vectors} new baselines; {a.vectors * 552:,} single-bit fault cases.', flush=True)
    print('Progress is printed after each baseline; old results remain unchanged.', flush=True)
    with (out / 'simulation.log').open('w') as log:
        proc = subprocess.Popen(['vvp', str(out / 'sweep.vvp')], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        baseline_count = 0
        complete = False
        for line in proc.stdout:
            log.write(line)
            if 'BASELINE PASS' in line:
                baseline_count += 1
                print(f'Baseline {baseline_count}/{a.vectors} passed', flush=True)
            if f'COMPLETE vectors={a.vectors} fault_cases={a.vectors * 552}' in line:
                complete = True
        code = proc.wait()
    if code or not complete or baseline_count != a.vectors:
        sys.exit(f'Run failed or incomplete: inspect {out}/simulation.log')
    _, _, counts = read_campaign(out)
    print('Validated complete campaign:', dict(counts))
    print('Now run:')
    print(f'python3 fault-injection/scripts/compare_checks.py --selection {a.selection} --validation {out}')


if __name__ == '__main__':
    main()
