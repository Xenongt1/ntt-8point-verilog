// ntt_addr_gen.v
//
// Combinational lookup of which two register-file positions and which
// twiddle power each butterfly needs.
//
// Rather than computing distance and block_start with divide/modulo
// hardware, the 12 butterfly operations across the 3 stages are encoded
// directly as a case statement. For a fixed n=8 this is cheap and
// exhaustively verifiable. It does not generalize to n=16 or n=32, which
// would need arithmetic address generation using
// twiddle_power = i * (n / block_size) - see README "Future work".
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
