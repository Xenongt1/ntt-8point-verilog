#!/usr/bin/env python3
"""Run a reproducible, single-bit RTL fault experiment on the 8-point NTT.

Run from the repository root: python3 fault-injection/scripts/run_fault_sweep.py
Requires Python 3, iverilog and vvp. Uses only the Python standard library.
Does not modify RTL. Generated files and raw results go to
fault-injection/results_selection_32/.
"""
import csv
import hashlib
import json
import random
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEED = 20261013
TIMEOUT_CYCLES = 40
RTL_NAMES = ["ntt_butterfly.v", "ntt_twiddle_rom.v", "ntt_addr_gen.v", "ntt_top.v"]


def test_vectors():
    named = [
        ("all_zero", [0] * 8),
        ("all_one", [1] * 8),
        ("all_sixteen", [16] * 8),
        ("ascending", list(range(1, 9))),
        ("descending", list(range(8, 0, -1))),
        ("alternating", [0, 16] * 4),
    ]
    for i in range(8):
        named.append((f"unit_{i}", [int(j == i) for j in range(8)]))
    rng = random.Random(SEED)
    for i in range(18):
        named.append((f"random_{i:02d}", [rng.randrange(17) for _ in range(8)]))
    return named


def reference(x):
    # Direct mathematical definition, independent of RTL butterfly scheduling.
    natural = [sum(x[j] * pow(9, j * k, 17) for j in range(8)) % 17
               for k in range(8)]
    return [natural[int(f"{i:03b}"[::-1], 2)] for i in range(8)]


def pack(values):
    return sum(value << (5 * i) for i, value in enumerate(values))


TESTBENCH = r'''
`timescale 1ns/1ps
module tb_fault_sweep;
    parameter NVECT = 32;
    parameter LIMIT = 40;
    reg clk = 0, rst = 1, start = 0;
    reg [39:0] input_bus;
    wire done;
    wire [39:0] output_bus;
    reg [39:0] inputs [0:NVECT-1];
    reg [39:0] expected [0:NVECT-1];
    integer vi, target, bitn, injection_cycle, fd, total;
    integer elapsed, finished, value_before, value_after;
    reg [39:0] observed;

    ntt_top dut(.clk(clk), .rst(rst), .start(start),
                .input_bus(input_bus), .done(done), .output_bus(output_bus));
    always #5 clk = ~clk;

    task run_case(input integer t, input integer b, input integer c);
        integer cycles;
        begin
            @(negedge clk);
            rst = 1; start = 0;
            repeat (2) @(negedge clk);
            rst = 0; start = 1;
            @(negedge clk);
            start = 0;
            cycles = 0;
            value_before = -1; value_after = -1;

            while ((done !== 1'b1) && (cycles < LIMIT)) begin
                if (t >= 0 && cycles == c) begin
                    case (t)
                        0: begin
                            value_before = dut.state;
                            dut.state = dut.state ^ (2'b01 << b);
                            value_after = dut.state;
                        end
                        1: begin
                            value_before = dut.stage;
                            dut.stage = dut.stage ^ (2'b01 << b);
                            value_after = dut.stage;
                        end
                        2: begin
                            value_before = dut.counter;
                            dut.counter = dut.counter ^ (2'b01 << b);
                            value_after = dut.counter;
                        end
                        default: begin
                            value_before = dut.mem[t-3];
                            dut.mem[t-3] = dut.mem[t-3] ^ (5'b00001 << b);
                            value_after = dut.mem[t-3];
                        end
                    endcase
                end
                @(posedge clk);
                #1;
                cycles = cycles + 1;
                @(negedge clk);
            end
            elapsed = cycles;
            finished = (done === 1'b1);
            observed = output_bus;
        end
    endtask

    initial begin
        $readmemh("fault-injection/results_selection_32/inputs.hex", inputs);
        $readmemh("fault-injection/results_selection_32/expected.hex", expected);
        fd = $fopen("fault-injection/results_selection_32/faults.csv", "w");
        if (!fd) $fatal(1, "Cannot open CSV output");
        $fdisplay(fd, "vector,target,bit,cycle,before,after,done,elapsed,output_hex");
        total = 0;
        for (vi = 0; vi < NVECT; vi = vi + 1) begin
            input_bus = inputs[vi];
            run_case(-1, 0, -1);
            if (!finished || elapsed != 12 || observed !== expected[vi])
                $fatal(1, "BASELINE FAILED vector=%0d done=%0d cycles=%0d observed=%h expected=%h",
                       vi, finished, elapsed, observed, expected[vi]);
            $display("BASELINE PASS vector=%0d cycles=%0d", vi, elapsed);

            for (target = 0; target < 11; target = target + 1)
                for (bitn = 0; bitn < ((target < 3) ? 2 : 5); bitn = bitn + 1)
                    for (injection_cycle = 0; injection_cycle < 12;
                         injection_cycle = injection_cycle + 1) begin
                        run_case(target, bitn, injection_cycle);
                        if (value_before < 0 || value_after < 0)
                            $fatal(1, "Injection was not recorded");
                        $fdisplay(fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%010h",
                                  vi, target, bitn, injection_cycle,
                                  value_before, value_after, finished, elapsed, observed);
                        total = total + 1;
                    end
        end
        $fclose(fd);
        $display("COMPLETE vectors=%0d fault_cases=%0d", NVECT, total);
        $finish;
    end
endmodule
'''


def classify(row, expected):
    if row["done"] != "1":
        return "no_done_within_40_cycles", None
    if any(c in row["output_hex"].lower() for c in "xz"):
        return "unknown_output", None
    actual = int(row["output_hex"], 16)
    on_time = int(row["elapsed"]) == 12
    correct = actual == pack(expected)
    category = ("correct_output" if correct else "wrong_output")
    category += "_on_time" if on_time else "_wrong_time"
    range_bad = any(((actual >> (5 * i)) & 31) >= 17 for i in range(8))
    return category, range_bad


def main():
    root = Path.cwd()
    rtl = [root / "rtl" / name for name in RTL_NAMES]
    if not all(path.is_file() for path in rtl):
        sys.exit("Run this script from the ntt-8point-verilog repository root.")
    for tool in ("iverilog", "vvp"):
        if shutil.which(tool) is None:
            sys.exit(f"Required tool not found: {tool}")
    out = root / "fault-injection" / "results_selection_32"
    out.mkdir(exist_ok=True)
    if (out / "faults.csv").exists():
        sys.exit("fault-injection/results_selection_32/faults.csv already exists. Rename that folder before rerunning to preserve that run.")
    vectors = test_vectors()
    references = [reference(x) for _, x in vectors]
    assert len(vectors) == 32
    assert reference(list(range(1, 9))) == [2, 13, 12, 14, 1, 6, 3, 8]
    assert reference([0] * 8) == [0] * 8
    (out / "inputs.hex").write_text("".join(f"{pack(x):010x}\n" for _, x in vectors))
    (out / "expected.hex").write_text("".join(f"{pack(x):010x}\n" for x in references))
    (out / "tb_fault_sweep.v").write_text(TESTBENCH)
    version = subprocess.run(["iverilog", "-V"], capture_output=True, text=True)
    (out / "simulator_version.txt").write_text(version.stdout + version.stderr)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    metadata = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "rtl_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "random_seed": SEED,
        "timeout_cycles": TIMEOUT_CYCLES,
        "fault_model": "One stored register bit toggled at a falling edge before selected butterfly 0..11; not a physical EMFI model.",
        "scope": "state[1:0], stage[1:0], counter[1:0], mem[0..7][4:0]. Excludes done, clock, combinational logic and external signals.",
        "vectors": [{"id": i, "name": name, "input": x, "expected": references[i]}
                    for i, (name, x) in enumerate(vectors)],
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    binary = out / "sweep.vvp"
    compile_cmd = ["iverilog", "-g2012", "-s", "tb_fault_sweep", "-o", str(binary)]
    compile_cmd += [str(p) for p in rtl] + [str(out / "tb_fault_sweep.v")]
    print("Checking 32 normal runs and running 17,664 single-bit fault cases...", flush=True)
    compiled = subprocess.run(compile_cmd, capture_output=True, text=True)
    (out / "compile.log").write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        sys.exit("Compilation failed. Share fault-injection/results_selection_32/compile.log.")
    simulation = subprocess.run(["vvp", str(binary)], capture_output=True, text=True)
    (out / "simulation.log").write_text(simulation.stdout + simulation.stderr)
    if simulation.returncode or "COMPLETE vectors=32 fault_cases=17664" not in simulation.stdout:
        sys.exit("Simulation did not complete successfully. Share fault-injection/results_selection_32/simulation.log.")
    if simulation.stdout.count("BASELINE PASS") != 32:
        sys.exit("Expected 32 baseline passes; inspect simulation.log.")

    counts = Counter()
    by_group = defaultdict(Counter)
    by_vector = defaultdict(Counter)
    expected_keys = {(v, t, b, c) for v in range(32) for t in range(11)
                     for b in range(2 if t < 3 else 5) for c in range(12)}
    seen = set()
    with (out / "faults.csv").open(newline="") as fh:
        for row in csv.DictReader(fh):
            vi, target, bit, cycle = [int(row[k]) for k in ("vector", "target", "bit", "cycle")]
            key = (vi, target, bit, cycle)
            if key not in expected_keys or key in seen:
                sys.exit(f"Unexpected or duplicate case: {key}")
            seen.add(key)
            if int(row["after"]) != (int(row["before"]) ^ (1 << bit)):
                sys.exit(f"Injection did not toggle exactly the selected bit: {key}")
            category, range_bad = classify(row, references[vi])
            group = ["state", "stage", "counter"][target] if target < 3 else "mem"
            for counter in (counts, by_group[group], by_vector[vi]):
                counter["cases"] += 1
                counter[category] += 1
                if category.startswith("wrong_output"):
                    counter["wrong_completed_outputs"] += 1
                    if range_bad:
                        counter["wrong_completed_outputs_out_of_range"] += 1
                    if category == "wrong_output_on_time" and not range_bad:
                        counter["wrong_outputs_passing_timing_and_range"] += 1
    if seen != expected_keys:
        sys.exit(f"Missing cases: {len(expected_keys - seen)}")
    summary = {
        "baseline_passes": 32,
        "overall": dict(counts),
        "by_register_group": {k: dict(v) for k, v in by_group.items()},
        "by_vector": {str(k): dict(v) for k, v in by_vector.items()},
        "interpretation": "Counts over this specified campaign, not physical fault probabilities. Timing/range detection is inferred from results; no detector was added to RTL. A 40-cycle timeout is not proof of permanent nontermination.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["BASELINES: 32/32 matched the mathematical reference in 12 cycles.",
             f"FAULT CASES: {counts['cases']}"]
    for label in ("correct_output_on_time", "correct_output_wrong_time",
                  "wrong_output_on_time", "wrong_output_wrong_time",
                  "no_done_within_40_cycles", "unknown_output"):
        lines.append(f"{label}: {counts[label]}")
    lines += ["", "Wrong outputs passing BOTH timing and final-output-range checks:"]
    for group in ("state", "stage", "counter", "mem"):
        counter = by_group[group]
        lines.append(f"  {group}: {counter['wrong_outputs_passing_timing_and_range']} / {counter['cases']} injected cases")
    lines += ["", "Raw data: fault-injection/results_selection_32/faults.csv",
              "Details: fault-injection/results_selection_32/summary.json",
              "Run identity and inputs: fault-injection/results_selection_32/metadata.json"]
    report = "\n".join(lines) + "\n"
    (out / "summary.txt").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
