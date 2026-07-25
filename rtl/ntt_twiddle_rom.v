// ntt_twiddle_rom.v
//
// Stores the twiddle table you verified by hand:
//   omega^0=1, omega^1=9, omega^2=13, omega^3=15,
//   omega^4=16, omega^5=8, omega^6=4, omega^7=2
//
// This is "ROM-based twiddle storage" from the task requirements -
// precomputed once (in software, by us), then just looked up by index
// in hardware. No multiplication ever happens to CREATE these values
// at runtime; they're baked in.

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
