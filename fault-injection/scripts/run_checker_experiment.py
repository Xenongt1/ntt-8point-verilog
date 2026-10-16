#!/usr/bin/env python3
"""RTL output-check experiment; bounded digital faults, not physical EMFI."""
import argparse
import csv
import hashlib
import json
import random
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
import run_fault_sweep as old

CHECKER = r'''
module ntt_output_checker(input wire clk, rst, start,
    input wire [39:0] input_bus, output_bus,
    output wire match);
    reg [4:0] check3, check6;
    function automatic [4:0] coefficient(input integer k, j);
        integer v, n;
        begin
            v = 1;
            for (n = 0; n < k*j; n = n + 1) v = (v*9) % 17;
            coefficient = v;
        end
    endfunction
    function automatic [4:0] direct_value(input [39:0] x, input integer k);
        integer j;
        reg [15:0] total;
        begin
            total = 0;
            for (j = 0; j < 8; j = j + 1)
                total = total + x[j*5 +: 5] * coefficient(k,j);
            direct_value = total % 17;
        end
    endfunction
    always @(posedge clk) begin
        if (rst) begin check3 <= 0; check6 <= 0; end
        else if (start) begin
            // Hardware output 3 = X[6]; hardware output 6 = X[3].
            check3 <= direct_value(input_bus, 6);
            check6 <= direct_value(input_bus, 3);
        end
    end
    assign match = (output_bus[15 +: 5] == check3) &&
                   (output_bus[30 +: 5] == check6);
endmodule
'''


def make_bench(folder):
    tb = old.TESTBENCH.replace('fault-injection/results_selection_32/', folder + '/')
    tb = tb.replace('integer elapsed, finished, value_before, value_after;', '''
    integer elapsed, finished, value_before, value_after;
    integer mode, cb;
    wire pair_match;
    ntt_output_checker checker_inst(.clk(clk), .rst(rst), .start(start),
        .input_bus(input_bus), .output_bus(output_bus), .match(pair_match));
    task toggle_check(input integer bit_index);
        reg [4:0] old_check;
        begin
            old_check = (bit_index < 5) ? checker_inst.check3 : checker_inst.check6;
            if (bit_index < 5)
                checker_inst.check3 = checker_inst.check3 ^ (5'b1 << bit_index);
            else
                checker_inst.check6 = checker_inst.check6 ^ (5'b1 << (bit_index-5));
            if (bit_index < 5) begin
                if (checker_inst.check3 !== (old_check ^ (5'b1 << bit_index)))
                    $fatal(1, "CHECKER INJECTION FAILED");
            end else if (checker_inst.check6 !== (old_check ^ (5'b1 << (bit_index-5))))
                $fatal(1, "CHECKER INJECTION FAILED");
        end
    endtask
    ''')
    tb = tb.replace('if (t >= 0 && cycles == c) begin', '''
                if (mode == 1 && cycles == c) toggle_check(cb);
                if (t >= 0 && cycles == c) begin
                    if (mode == 2) toggle_check(cb);
    ''')
    tb = tb.replace('observed = output_bus;', '''observed = output_bus;
            // Deliberate second fault in the comparison decision at observation.
            // This is a bypass demonstration, not a claim about EM feasibility.
            if (mode == 3) begin force pair_match = 1'b1; #1; end''')
    first = tb.index('        $fdisplay(fd, "vector,target')
    last = tb.index('        $fclose(fd);', first)
    tb = tb[:first] + r'''
        $fdisplay(fd, "mode,vector,target,bit,cycle,checker_bit,done,elapsed,output_hex,pair_match,check3,check6");
        total = 0;
        for (vi = 0; vi < NVECT; vi = vi + 1) begin
            input_bus = inputs[vi];
            mode = 0;
            run_case(-1, 0, -1);
            if (!finished || elapsed != 12 || observed !== expected[vi] || pair_match !== 1'b1)
                $fatal(1, "BASELINE FAILED vector=%0d match=%b", vi, pair_match);
            if (checker_inst.check3 !== expected[vi][15 +: 5] ||
                checker_inst.check6 !== expected[vi][30 +: 5])
                $fatal(1, "CHECKER REFERENCE FAILED");
            $display("BASELINE PASS vector=%0d", vi);
            for (mode = 0; mode < 4; mode = mode + 1) begin
                if (mode == 1) begin
                    for (cb = 0; cb < 10; cb = cb + 1)
                        for (injection_cycle = 0; injection_cycle < 12; injection_cycle = injection_cycle + 1) begin
                            run_case(-1, 0, injection_cycle);
                            record_case(-1, -1, injection_cycle);
                        end
                end else begin
                    for (target = 0; target < 11; target = target + 1)
                        for (bitn = 0; bitn < ((target < 3) ? 2 : 5); bitn = bitn + 1)
                            for (injection_cycle = 0; injection_cycle < 12; injection_cycle = injection_cycle + 1) begin
                                // One reproducible sampled checker bit per accelerator fault.
                                cb = (vi + target*3 + bitn + injection_cycle) % 10;
                                run_case(target, bitn, injection_cycle);
                                if (value_before < 0 || value_after != (value_before ^ (1 << bitn)))
                                    $fatal(1, "INJECTION FAILED");
                                record_case(target, bitn, injection_cycle);
                                if (mode == 3) begin release pair_match; #1; end
                            end
                end
            end
        end
''' + tb[last:]
    insertion = tb.index('    initial begin')
    tb = tb[:insertion] + r'''
    task record_case(input integer t, b, c);
        begin
            $fdisplay(fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%010h,%b,%0d,%0d",
                mode, vi, t, b, c, cb, finished, elapsed, observed, pair_match,
                checker_inst.check3, checker_inst.check6);
            total = total + 1;
        end
    endtask
''' + tb[insertion:]
    return tb


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vectors', type=int, default=128)
    p.add_argument('--seed', type=int, default=20261016)
    a = p.parse_args()
    if not 1 <= a.vectors <= 4096:
        sys.exit('Choose 1..4096 vectors.')
    for tool in ('iverilog', 'vvp'):
        if not shutil.which(tool): sys.exit(f'Missing {tool}')
    rtl = [Path('rtl') / n for n in old.RTL_NAMES]
    if not all(f.exists() for f in rtl): sys.exit('Run from the repository root.')
    out = Path(f'fault-injection/results_checker_{a.seed}_{a.vectors}')
    if out.exists(): sys.exit(f'{out} exists; preserving it. Choose a different seed.')
    # New unique random inputs; avoid input vectors in earlier campaign metadata.
    exclude = set()
    for f in Path('fault-injection').glob('results_*/metadata.json'):
        for v in json.loads(f.read_text()).get('vectors', []): exclude.add(tuple(v['input']))
    rng = random.Random(a.seed)
    vectors = []
    while len(vectors) < a.vectors:
        x = tuple(rng.randrange(17) for _ in range(8))
        if x not in exclude:
            exclude.add(x)
            vectors.append({'id':len(vectors), 'input':list(x), 'expected':old.reference(x)})
    out.mkdir()
    (out / 'ntt_output_checker.v').write_text(CHECKER)
    (out / 'tb_fault_sweep.v').write_text(make_bench(out.as_posix()))
    for filename, field in [('inputs.hex','input'), ('expected.hex','expected')]:
        (out / filename).write_text(''.join(f"{old.pack(v[field]):010x}\n" for v in vectors))
    meta = {'vectors':vectors, 'seed':a.seed,
            'rtl_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in rtl},
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'base_script_sha256':hashlib.sha256(Path(old.__file__).read_bytes()).hexdigest(),
            'modes':{'0':'one accelerator stored-bit flip',
                     '1':'one checker stored-bit flip',
                     '2':'accelerator bit + one sampled checker bit, same falling edge',
                     '3':'accelerator bit + comparison decision forced to match at observation'},
            'limits':'Checker input capture and combinational arithmetic not faulted. Clock, reset, start, shared input bus and external consumer excluded. Timing/range filters remain offline. No synthesis, area, timing closure, physical fault probabilities or cryptographic exploit demonstrated.'}
    (out / 'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    cmd = ['iverilog','-g2012','-s','tb_fault_sweep',f'-Ptb_fault_sweep.NVECT={a.vectors}',
           '-o',str(out/'sim.vvp')] + [str(f) for f in rtl] + [str(out/'ntt_output_checker.v'),str(out/'tb_fault_sweep.v')]
    c = subprocess.run(cmd,capture_output=True,text=True)
    (out/'compile.log').write_text(c.stdout+c.stderr)
    if c.returncode: sys.exit(f'Compilation failed. Share {out}/compile.log')
    total = a.vectors * (552*3+120)
    print(f'Running {a.vectors} baselines and {total:,} fault experiments.',flush=True)
    baselines = 0
    complete = False
    with (out/'simulation.log').open('w') as log:
        sim = subprocess.Popen(['vvp',str(out/'sim.vvp')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in sim.stdout:
            log.write(line)
            if 'BASELINE PASS' in line:
                baselines += 1
                if baselines % 16 == 0 or baselines == a.vectors: print(f'Baseline {baselines}/{a.vectors}',flush=True)
            if f'COMPLETE vectors={a.vectors} fault_cases={total}' in line: complete=True
        code=sim.wait()
    if code or not complete or baselines != a.vectors: sys.exit(f'Run failed. Share {out}/simulation.log')
    counts=defaultdict(Counter)
    seen=set()
    with (out/'faults.csv').open() as f:
        for r in csv.DictReader(f):
            m,vi,t,b,cy,cb=(int(r[k]) for k in ('mode','vector','target','bit','cycle','checker_bit'))
            key=(m,vi,t,b,cy,cb)
            if key in seen: raise ValueError('Duplicate case')
            seen.add(key)
            c=counts[m];c['cases']+=1
            if r['done']!='1': c['timeout']+=1;continue
            if any(k in r['output_hex'].lower() for k in 'xz') or r['pair_match'] not in ('0','1'):
                c['unknown']+=1;continue
            value=int(r['output_hex'],16)
            wrong=value != old.pack(vectors[vi]['expected'])
            match=r['pair_match']=='1'
            c[('wrong' if wrong else 'correct')+('_accepted_by_pair' if match else '_rejected_by_pair')]+=1
            # These two filters are assessed offline, as in previous campaigns.
            eligible=int(r['elapsed'])==12 and all(((value>>(5*i))&31)<17 for i in range(8))
            if wrong and eligible:
                c['wrong_passing_timing_range']+=1
                c['remaining_after_pair' if match else 'additionally_detected_by_pair']+=1
    if len(seen)!=total: raise ValueError('Incomplete CSV')
    for m in range(4):
        if counts[m]['cases']!=a.vectors*(120 if m==1 else 552): raise ValueError('Wrong mode count')
    # Intended fault-model sanity checks; failure stops interpretation.
    if counts[1]['wrong_accepted_by_pair'] or counts[1]['wrong_rejected_by_pair']:
        raise ValueError('Checker-only faults unexpectedly changed accelerator output')
    if counts[3]['wrong_rejected_by_pair'] or counts[3]['correct_rejected_by_pair']:
        raise ValueError('Forced-match experiment did not force acceptance')
    summary={'baselines':baselines,'counts':{str(k):dict(v) for k,v in counts.items()},'limits':meta['limits']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    for m in range(4):
        print('\nMODE',m,meta['modes'][str(m)])
        print(json.dumps(dict(counts[m]),indent=2))
    print('\nResults:',out/'summary.json')
    print('Timing/range are offline filters. Pair comparison is implemented in RTL.')
    print('Mode 3 is a deliberate bypass demonstration, not a physical attack success rate.')


if __name__=='__main__':main()
