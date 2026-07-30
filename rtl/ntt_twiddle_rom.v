// ntt_twiddle_rom.v
//
// ROM-based twiddle storage for omega=9, q=17:
//   omega^0=1, omega^1=9, omega^2=13, omega^3=15,
//   omega^4=16, omega^5=8, omega^6=4, omega^7=2
//
// All 8 values are precomputed and looked up by index. No multiplication
// happens at runtime to create a twiddle value.

module ntt_twiddle_rom (
    input  wire [2:0] power,   // which power of omega (0..7)
    output reg  [4:0] tw       // omega^power mod 17
);

    always @(*) begin
        case (power)
            3'd0: tw = 5'd1;
            3'd1: tw = 5'd9;
            3'd2: tw = 5'd13;
            3'd3: tw = 5'd15;
            3'd4: tw = 5'd16;
            3'd5: tw = 5'd8;
            3'd6: tw = 5'd4;
            3'd7: tw = 5'd2;
            default: tw = 5'd0; // unreachable, but keeps synthesis clean
        endcase
    end

endmodule
