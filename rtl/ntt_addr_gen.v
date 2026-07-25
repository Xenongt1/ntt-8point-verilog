// ntt_addr_gen.v
//
// This is a direct hardware lookup of the exact table you built by hand
// (the pair-and-twiddle table). Rather than computing "distance",
// "block_start", etc. with actual divide/modulo hardware (which is
// overkill for a fixed n=8), we hardcode the 12 known butterfly
// operations across the 3 stages as a small combinational ROM/case
// statement. This is a deliberate simplicity choice worth mentioning in
// the interview: it's cheap and easy to verify for a fixed, small n,
// but doesn't automatically generalize to n=16, 32, etc. - a real
// arithmetic address generator (using the i*(n/block_size) formula)
// would be needed for that, and is a natural "future work" extension.
//
// stage:   0 = stage 1 (distance 4)
//          1 = stage 2 (distance 2)
//          2 = stage 3 (distance 1)
// counter: 0..3, which of the 4 butterflies within that stage

module ntt_addr_gen (
    input  wire [1:0] stage,
    input  wire [1:0] counter,
    output reg  [2:0] idx1,
    output reg  [2:0] idx2,
    output reg  [2:0] twpow
);

    always @(*) begin
        case ({stage, counter})
            // Stage 1 (distance 4): pairs (0,4)(1,5)(2,6)(3,7), tw = omega^0..3
            4'b00_00: begin idx1=0; idx2=4; twpow=0; end
            4'b00_01: begin idx1=1; idx2=5; twpow=1; end
            4'b00_10: begin idx1=2; idx2=6; twpow=2; end
            4'b00_11: begin idx1=3; idx2=7; twpow=3; end

            // Stage 2 (distance 2): pairs (0,2)(1,3)(4,6)(5,7), tw = omega^0,2,0,2
            4'b01_00: begin idx1=0; idx2=2; twpow=0; end
            4'b01_01: begin idx1=1; idx2=3; twpow=2; end
            4'b01_10: begin idx1=4; idx2=6; twpow=0; end
            4'b01_11: begin idx1=5; idx2=7; twpow=2; end

            // Stage 3 (distance 1): pairs (0,1)(2,3)(4,5)(6,7), tw = omega^0 (all)
            4'b10_00: begin idx1=0; idx2=1; twpow=0; end
            4'b10_01: begin idx1=2; idx2=3; twpow=0; end
            4'b10_10: begin idx1=4; idx2=5; twpow=0; end
            4'b10_11: begin idx1=6; idx2=7; twpow=0; end

            default: begin idx1=0; idx2=0; twpow=0; end
        endcase
    end

endmodule
