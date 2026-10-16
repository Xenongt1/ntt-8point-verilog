#!/usr/bin/env python3
"""Offline candidate selection. Does not implement a fault-tolerant checker."""
import argparse
import csv
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path


def reference(x):
    return [sum(x[j] * pow(9, j * int(f'{i:03b}'[::-1], 2), 17)
                for j in range(8)) % 17 for i in range(8)]


def read_campaign(folder):
    meta = json.loads((folder / 'metadata.json').read_text())
    vectors = {v['id']: v for v in meta['vectors']}
    refs = {i: reference(v['input']) for i, v in vectors.items()}
    for i, v in vectors.items():
        if refs[i] != v['expected']:
            raise ValueError(f'Reference mismatch for input {i}')
    seen = set()
    masks = Counter()
    counts = Counter()
    with (folder / 'faults.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            if any(row.get(k) in (None, '') for k in ('vector', 'target', 'bit', 'cycle', 'before', 'after', 'done', 'elapsed', 'output_hex')):
                raise ValueError('INCOMPLETE or malformed CSV row. No rankings produced.')
            vi, t, b, c = (int(row[k]) for k in ('vector', 'target', 'bit', 'cycle'))
            key = vi, t, b, c
            if (vi not in vectors or not 0 <= t < 11 or
                not 0 <= b < (2 if t < 3 else 5) or not 0 <= c < 12 or key in seen):
                raise ValueError(f'Invalid/duplicate case {key}')
            seen.add(key)
            if int(row['after']) != int(row['before']) ^ (1 << b):
                raise ValueError(f'Invalid injection {key}')
            counts['cases'] += 1
            if row['done'] != '1':
                counts['no_done'] += 1
                continue
            if any(x in row['output_hex'].lower() for x in 'xz'):
                counts['unknown_output'] += 1
                continue
            value = int(row['output_hex'], 16)
            actual = [(value >> (5*i)) & 31 for i in range(8)]
            mask = sum(1 << i for i in range(8) if actual[i] != refs[vi][i])
            if not mask:
                counts['correct_completed'] += 1
                continue
            counts['wrong_completed'] += 1
            if int(row['elapsed']) == 12 and all(x < 17 for x in actual):
                masks[mask] += 1
                counts['wrong_passing_timing_range'] += 1
    expected = len(vectors) * 46 * 12
    if len(seen) != expected:
        raise ValueError(f'INCOMPLETE CSV: {len(seen)} cases, expected {expected}. No rankings produced.')
    return meta, masks, counts


def score(positions, masks):
    check_mask = sum(1 << i for i in positions)
    caught = sum(n for mask, n in masks.items() if mask & check_mask)
    return caught, sum(masks.values()) - caught


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, default=Path('fault-injection/results_selection_32'))
    parser.add_argument('--validation', type=Path)
    args = parser.parse_args()
    meta, masks, counts = read_campaign(args.selection)
    candidates = [p for size in (1, 2) for p in itertools.combinations(range(8), size)]
    ranked = sorted(candidates, key=lambda p: (-score(p, masks)[0], len(p), p))
    print('OFFLINE COVERAGE ONLY: expected check values assumed correct in this analysis.')
    print('Hardware checker, checker faults, area and physical EMFI are NOT evaluated.')
    print('Selection campaign:', dict(counts))
    print('\nPositions refer to hardware output order, not natural NTT order.')
    print('positions   additionally_detected   remaining_undetected')
    for p in ranked:
        caught, remaining = score(p, masks)
        print(f'{str(p):12} {caught:20} {remaining:22}')
    chosen = {str(size): next(p for p in ranked if len(p) == size) for size in (1, 2)}
    report = {'scope': 'Ideal comparison coverage after timing/range filtering, not hardware protection',
              'counts': dict(counts), 'selected': chosen,
              'csv_sha256': hashlib.sha256((args.selection / 'faults.csv').read_bytes()).hexdigest(),
              'candidates': [{'positions': p, 'caught': score(p, masks)[0],
                              'remaining': score(p, masks)[1]} for p in ranked]}
    if args.validation:
        vm, vmask, vc = read_campaign(args.validation)
        if meta['rtl_sha256'] != vm['rtl_sha256']:
            raise ValueError('RTL hashes differ between campaigns')
        training_inputs = {tuple(v['input']) for v in meta['vectors']}
        if any(tuple(v['input']) in training_inputs for v in vm['vectors']):
            raise ValueError('Validation inputs overlap selection inputs')
        print('\nVALIDATION: fixed selection choices, no re-ranking:', dict(vc))
        report['validation'] = {'counts': dict(vc), 'fixed_choices': {}}
        for size, p in chosen.items():
            caught, remaining = score(p, vmask)
            print(f'{p}: additionally detected={caught}, remaining={remaining}')
            report['validation']['fixed_choices'][size] = {'positions': p, 'caught': caught, 'remaining': remaining}
    output = args.selection / 'check_coverage.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('\nSaved:', output)


if __name__ == '__main__':
    main()
