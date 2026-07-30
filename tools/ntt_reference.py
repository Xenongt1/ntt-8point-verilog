#!/usr/bin/env python3
"""
Software reference model for the 8-point NTT (n=8, q=17, omega=9).

Run from the repository root:

    python3 tools/ntt_reference.py

It does three things:

  1. Computes the ground-truth NTT straight from the definition,
     X[k] = sum_j x[j] * omega^(j*k) mod q, with no butterfly structure
     involved at all.
  2. Runs the butterfly schedule the hardware implements and confirms it
     reproduces that ground truth under bit-reversed output indexing.
  3. Reads the actual hardware output from output/output.mem, if present,
     and checks it too.

This is the model the RTL was validated against before any Verilog was
written, and it is what makes the "correct" claim in the README checkable
rather than asserted.
"""

Q = 17          # prime modulus
OMEGA = 9       # primitive 8th root of unity mod 17
N = 8           # transform size
BITS = 3        # log2(N)


def bit_reverse(i, bits=BITS):
    """Reverse the low `bits` bits of i. For N=8: 1 (001) -> 4 (100)."""
    return int(format(i, f"0{bits}b")[::-1], 2)


def ntt_by_definition(x):
    """Ground truth. O(n^2), no butterflies, no orderings to get wrong."""
    return [sum(x[j] * pow(OMEGA, j * k, Q) for j in range(N)) % Q
            for k in range(N)]


# The exact (index_1, index_2, twiddle_power) schedule encoded in
# rtl/ntt_addr_gen.v, stage by stage.
SCHEDULE = [
    [(0, 4, 0), (1, 5, 1), (2, 6, 2), (3, 7, 3)],   # stage 1, distance 4
    [(0, 2, 0), (1, 3, 2), (4, 6, 0), (5, 7, 2)],   # stage 2, distance 2
    [(0, 1, 0), (2, 3, 0), (4, 5, 0), (6, 7, 0)],   # stage 3, distance 1
]


def butterfly_gs(a, b, tw):
    """Gentleman-Sande, as implemented in rtl/ntt_butterfly.v.
    Twiddle is applied to the difference, after the subtraction."""
    return (a + b) % Q, ((a - b) * tw) % Q


def butterfly_ct(a, b, tw):
    """Cooley-Tukey. Twiddle is applied to b, before add and subtract.
    Included to show it is NOT compatible with the schedule above."""
    return (a + b * tw) % Q, (a - b * tw) % Q


def run_schedule(x, butterfly):
    """Walk the 12 butterflies in place, exactly as the FSM does."""
    m = list(x)
    for stage in SCHEDULE:
        for i, j, power in stage:
            m[i], m[j] = butterfly(m[i], m[j], pow(OMEGA, power, Q))
    return m


def read_mem(path):
    """Read a $readmemb/$writememb file: one binary value per line.
    Skips blank lines and the '// 0x...' address comments Icarus emits."""
    values = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            values.append(int(line, 2))
    return values


def main():
    x = [1, 2, 3, 4, 5, 6, 7, 8]

    # --- sanity check the parameters themselves ---
    assert pow(OMEGA, N, Q) == 1, "omega^8 must be 1 mod q"
    assert all(pow(OMEGA, k, Q) != 1 for k in range(1, N)), \
        "omega must be a PRIMITIVE 8th root: no smaller power may equal 1"
    print(f"omega={OMEGA} is a primitive {N}th root of unity mod q={Q}: verified")
    print(f"twiddles omega^0..omega^7 mod {Q} = "
          f"{[pow(OMEGA, k, Q) for k in range(N)]}\n")

    natural = ntt_by_definition(x)
    expected = [natural[bit_reverse(i)] for i in range(N)]

    print(f"input                          : {x}")
    print(f"NTT by definition, natural order: {natural}")
    print(f"same values, bit-reversed order : {expected}\n")

    gs = run_schedule(x, butterfly_gs)
    ct = run_schedule(x, butterfly_ct)

    print(f"schedule + Gentleman-Sande (RTL): {gs}  "
          f"{'MATCHES bit-reversed NTT' if gs == expected else 'MISMATCH'}")
    print(f"schedule + Cooley-Tukey         : {ct}  "
          f"{'matches' if ct == expected else 'does NOT produce a valid NTT'}")
    print("\nThe distance-4-first schedule is decimation-in-frequency, which")
    print("requires the Gentleman-Sande butterfly. See README, 'Butterfly form'.\n")

    print("index mapping (bit-reversal):")
    for i in range(N):
        r = bit_reverse(i)
        print(f"  output[{i}] = X[{r}] = {natural[r]:2d}   "
              f"({i:03b} -> {r:03b})")

    # --- compare against the real hardware output, if it exists ---
    try:
        hw = read_mem("output/output.mem")
    except FileNotFoundError:
        print("\noutput/output.mem not found - run 'bash run.sh' first "
              "to compare against the hardware.")
        return 0

    print(f"\nhardware output/output.mem      : {hw}")
    if hw == expected:
        print("HARDWARE MATCHES THE REFERENCE MODEL - PASS")
        return 0
    print("HARDWARE DOES NOT MATCH THE REFERENCE MODEL - FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
