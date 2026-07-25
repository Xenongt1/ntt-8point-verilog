// ntt_butterfly.v
//
// This is the ONE arithmetic unit that gets reused for every butterfly,
// across all 3 stages. Nothing here knows or cares which stage or which
// pair it's being used for - it just takes two operands and a twiddle
// factor, and produces u and v, exactly like the diagrams:
//
//   u = (a + b) mod q                (sum path, no twiddle)
//   v = ((a - b) * tw) mod q         (difference path, twiddled)
//
// q = 17 fits in 5 bits (0..16), so all data ports are 5 bits wide.
// This directly implements the "Minimal Hardware Architecture" recipe
// from the task doc: add-then-conditionally-subtract for the adder,
// subtract-then-conditionally-add for the subtractor, and a reduce
// step after the multiply.

module ntt_butterfly #(
    parameter Q = 17          // the modulus, parameterized so it's easy
                               // to point at during the interview when
                               // discussing "what would change for a
                               // bigger prime"
)(
    input  wire [4:0] a,       // first operand  (a[i]   in our notation)
    input  wire [4:0] b,       // second operand (a[i+d] in our notation)
    input  wire [4:0] tw,      // twiddle factor for this butterfly (0..16)
    output wire [4:0] u,       // sum output   (goes to position i)
    output wire [4:0] v        // twiddled difference output (goes to i+d)
);

    // ---- Modular adder: u = (a + b) mod q ----
    // a and b are both at most 16, so a+b is at most 32, which needs 6
    // bits to hold safely without overflow before we reduce it.
    wire [5:0] sum_raw = a + b;

    // Since max sum is 32 and q=17, at most ONE subtraction of q is ever
    // needed to bring it back into range - no loop required in hardware.
    assign u = (sum_raw >= Q) ? (sum_raw - Q) : sum_raw[4:0];

    // ---- Modular subtractor: diff = (a - b) mod q ----
    // Use a signed 6-bit wire so we can detect a negative result cleanly.
    wire signed [5:0] diff_raw = $signed({1'b0, a}) - $signed({1'b0, b});

    // a,b are both in 0..16, so diff_raw is always between -16 and +16.
    // If it went negative, a single "+ q" brings it back into 0..16 -
    // this is exactly the "+17 if negative" rule done by hand throughout.
    wire [4:0] diff_mod = (diff_raw < 0) ? (diff_raw + Q) : diff_raw[4:0];

    // ---- Modular multiplier: v = (diff_mod * tw) mod q ----
    // diff_mod and tw are both at most 16, so the raw product can be up
    // to 16*16 = 256, which needs 9 bits. Unlike the adder/subtractor,
    // a single conditional subtraction isn't enough to reduce this (you
    // might need to subtract q up to ~15 times in the worst case), so
    // we use the % operator here as the "simple logic" the task doc
    // explicitly allows for a small q=17. NOTE: for a large cryptographic
    // prime, this behavioral % would need to be replaced with a real
    // reduction circuit (e.g. Barrett or Montgomery reduction) - that
    // trade-off is worth raising directly in the interview.
    wire [8:0] prod_raw = diff_mod * tw;
    assign v = prod_raw % Q;

endmodule
