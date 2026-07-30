// ntt_butterfly.v
//
// The single arithmetic unit reused for every butterfly across all 3
// stages. It is stateless and stage-agnostic: given two operands and a
// twiddle factor, it produces
//
//   u = (a + b) mod q                (sum path, no twiddle)
//   v = ((a - b) * tw) mod q         (difference path, twiddled)
//
// q = 17 fits in 5 bits (0..16), so all data ports are 5 bits wide.
// Reduction is add-then-conditionally-subtract for the adder,
// subtract-then-conditionally-add for the subtractor, and an explicit
// reduce step after the multiply.

module ntt_butterfly #(
    parameter Q = 17           // the modulus
)(
    input  wire [4:0] a,       // first operand  (a[i])
    input  wire [4:0] b,       // second operand (a[i+d])
    input  wire [4:0] tw,      // twiddle factor for this butterfly (0..16)
    output wire [4:0] u,       // sum output   (goes to position i)
    output wire [4:0] v        // twiddled difference output (goes to i+d)
);

    // ---- Modular adder: u = (a + b) mod q ----
    // a and b are both at most 16, so a+b is at most 32, which needs 6
    // bits to hold safely without overflow before reduction.
    wire [5:0] sum_raw = a + b;

    // Since max sum is 32 and q=17, at most ONE subtraction of q is ever
    // needed to bring it back into range - no loop required in hardware.
    assign u = (sum_raw >= Q) ? (sum_raw - Q) : sum_raw[4:0];

    // ---- Modular subtractor: diff = (a - b) mod q ----
    // A signed 6-bit wire allows a negative result to be detected cleanly.
    wire signed [5:0] diff_raw = $signed({1'b0, a}) - $signed({1'b0, b});

    // a,b are both in 0..16, so diff_raw is always between -16 and +16.
    // If it went negative, a single "+ q" brings it back into 0..16.
    wire [4:0] diff_mod = (diff_raw < 0) ? (diff_raw + Q) : diff_raw[4:0];

    // ---- Modular multiplier: v = (diff_mod * tw) mod q ----
    // diff_mod and tw are both at most 16, so the raw product can reach
    // 16*16 = 256, which needs 9 bits. Unlike the adder and subtractor, a
    // single conditional subtraction is not sufficient here - the worst
    // case would require subtracting q roughly 15 times - so reduction
    // uses the % operator.
    //
    // This is only reasonable because q=17 is small. For a
    // cryptographically-sized prime, this behavioral % must be replaced
    // with a real reduction circuit (Barrett or Montgomery reduction).
    wire [8:0] prod_raw = diff_mod * tw;
    assign v = prod_raw % Q;

endmodule
