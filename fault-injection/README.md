# Fault-injection experiments on the 8-point NTT

These experiments ask how a single stored-bit fault changes the result of
the NTT accelerator in [`../rtl/`](../rtl), and whether a small output check
can catch it. All faults are **simulated bit flips in RTL registers**, not
physical EM attacks. Nothing in `rtl/` is modified.

## Layout

```
fault-injection/
├── README.md                         - this file
├── scripts/
│   ├── run_fault_sweep.py            - 32-input selection sweep; also holds
│   │                                   the Python NTT reference and the
│   │                                   sweep testbench template
│   ├── compare_checks.py             - ranks which output positions to check;
│   │                                   scores fixed choices on validation data
│   ├── run_validation_sweep.py       - held-out sweep on new random inputs
│   └── run_checker_experiment.py     - RTL output checker + checker faults
├── tb/
│   ├── tb_stage_fault.v              - one stage-register bit flip, traced
│   └── tb_data_fault.v               - one data-register bit flip, traced
├── logs/                             - output of the two traced testbenches,
│                                       plus the RTL commit they ran against
├── results_selection_32/             - 32-input sweep and position ranking
├── results_validation_20261015_512/  - 512-input held-out validation
└── results_checker_20261016_128/     - RTL checker experiment (128 inputs),
                                        including ntt_output_checker.v
```

Each results folder holds the generated testbench, inputs and expected
outputs, `metadata.json` (inputs, seed, RTL and script hashes),
`simulator_version.txt`, the simulation log, the raw `faults.csv` and the
summary.

## Fault model

- One bit flip per run, applied by the testbench at one of the 12 butterfly
  cycles.
- Targets: all 46 stored bits of `ntt_top`: `state` (2), `stage` (2),
  `counter` (2) and the 8 x 5-bit register file `mem` (40).
- Correct results come from the NTT's mathematical definition in Python
  (`reference()` in `scripts/run_fault_sweep.py`), not from the RTL.
- Each run is classified by: did it finish within 40 cycles, did it finish in
  the normal 12 cycles, and is the output correct. The "timing and range"
  filter keeps outputs that finished in 12 cycles with every value in 0..16.

## Results

| Experiment | Inputs | Fault cases | Result |
| --- | --- | --- | --- |
| Selection sweep | 32 (14 edge cases, 18 random, seed 20261013) | 17,664 | 14,493 wrong outputs pass timing and range; all come from `mem` faults |
| Position ranking | same | same | Checking hardware positions (3, 6) catches 11,157 of them; (3, 7) ties |
| Held-out validation | 512 new random (seed 20261015) | 282,624 | (3, 6) catches 177,773 of 230,620 (77.1%) |
| RTL checker, accelerator faults | 128 new random (seed 20261016) | 70,656 | 44,509 of 57,825 caught, 13,316 missed |
| RTL checker, checker faults only | same | 15,360 | all 15,360 correct results rejected (false alarms) |
| RTL checker, both faulted | same | 70,656 | 1,591 of 57,825 missed |
| RTL checker, decision forced to accept | same | 70,656 | all 57,825 pass |

Positions refer to the hardware's bit-reversed output order: hardware
position 3 is X[6] and position 6 is X[3]. The checker
(`results_checker_20261016_128/ntt_output_checker.v`) computes both values
directly from the input bus as weighted sums mod 17 and stores them in two
5-bit registers.

Two single-fault traces are in `logs/`. A `stage` flip from 2 to 3 (an
unused value; the address generator falls to its default pair (0,0)) makes
the run take 24 cycles and return a wrong result. A `mem[1]` flip returns a
wrong result in the normal 12 cycles.

## Limits

- Single bit flips in registers only: no multi-bit faults, no faults in
  combinational logic or the twiddle ROM.
- Checker input capture, the checker's arithmetic, clock, reset, start and the
  shared input bus are not faulted. In the both-faulted mode, the checker bit
  is chosen by a fixed rule, `(vector + 3*target + bit + cycle) % 10`, not
  every combination.
- Timing and range filters are applied offline, not in hardware.
- Every fault case is counted equally, so the rates are counts over simulated
  cases, not probabilities of a real attack succeeding.
- No synthesis, area or timing results, and no cryptographic exploit.

## Reproduce

Requires Python 3 and Icarus Verilog. Run from the **repository root** (the
scripts read `rtl/` from there). Each script refuses to overwrite an existing
results folder, so rename it first or use a new seed.

```bash
python3 fault-injection/scripts/run_fault_sweep.py
python3 fault-injection/scripts/compare_checks.py
python3 fault-injection/scripts/run_validation_sweep.py --vectors 512 --seed 20261015
python3 fault-injection/scripts/compare_checks.py \
    --selection fault-injection/results_selection_32 \
    --validation fault-injection/results_validation_20261015_512
python3 fault-injection/scripts/run_checker_experiment.py --vectors 128 --seed 20261016
```

Single-fault traces:

```bash
iverilog -g2012 -s tb_stage_fault -o sim_stage_fault rtl/ntt_butterfly.v \
    rtl/ntt_twiddle_rom.v rtl/ntt_addr_gen.v rtl/ntt_top.v \
    fault-injection/tb/tb_stage_fault.v
vvp sim_stage_fault

iverilog -g2012 -s tb_data_fault -o sim_data_fault rtl/ntt_butterfly.v \
    rtl/ntt_twiddle_rom.v rtl/ntt_addr_gen.v rtl/ntt_top.v \
    fault-injection/tb/tb_data_fault.v
vvp sim_data_fault
```

### Note on recorded paths and hashes

The committed results were produced before this folder was reorganised,
when the scripts lived in `research/` and wrote to `research_results/`,
`research_validation_20261015_512/` and `research_checker_20261016_128/`.
The generated testbenches, logs and `metadata.json` files inside each
results folder still show those old paths. The only change to the scripts
since then is those folder paths, but that changes their SHA-256, so the
`script_sha256` values in the metadata match the scripts as of commit
`1842576`, not the current ones. Rerunning the selection sweep with the
current scripts reproduces `results_selection_32/faults.csv` byte for byte.
