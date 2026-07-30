// tb_addr_gen.v
// Walks all 3 stages x 4 counters and checks that the addresses and
// twiddle powers match the reference table exactly.

`timescale 1ns/1ps

module tb_addr_gen;

    reg  [1:0] stage, counter;     // drive the DUT's inputs
    wire [2:0] idx1, idx2, twpow;  // observe the DUT's outputs
    integer errors = 0;            // running count of mismatches

    // Device under test
    ntt_addr_gen dut (
        .stage(stage), .counter(counter),
        .idx1(idx1), .idx2(idx2), .twpow(twpow)
    );

    // check() drives one (stage, counter) combination, waits for the
    // combinational logic to settle, then compares every output against
    // the expected value.
    task check(input [1:0] s, input [1:0] c,
               input [2:0] e_idx1, input [2:0] e_idx2, input [2:0] e_twpow);
        begin
            stage = s; counter = c;
            #1; // no clock here - ntt_addr_gen is purely combinational,
                // so this tiny delay just lets the simulator settle the
                // logic before the outputs are sampled
            if (idx1 !== e_idx1 || idx2 !== e_idx2 || twpow !== e_twpow) begin
                $display("FAIL: stage=%0d counter=%0d -> got (%0d,%0d,tw^%0d), expected (%0d,%0d,tw^%0d)",
                          s, c, idx1, idx2, twpow, e_idx1, e_idx2, e_twpow);
                errors = errors + 1;
            end else begin
                $display("PASS: stage=%0d counter=%0d -> pair(%0d,%0d) tw=omega^%0d",
                          s, c, idx1, idx2, twpow);
            end
        end
    endtask

    initial begin
        // Stage 1
        check(0,0, 0,4,0); check(0,1, 1,5,1); check(0,2, 2,6,2); check(0,3, 3,7,3);
        // Stage 2
        check(1,0, 0,2,0); check(1,1, 1,3,2); check(1,2, 4,6,0); check(1,3, 5,7,2);
        // Stage 3
        check(2,0, 0,1,0); check(2,1, 2,3,0); check(2,2, 4,5,0); check(2,3, 6,7,0);

        if (errors == 0) $display("\nALL TESTS PASSED");
        else $display("\n%0d TEST(S) FAILED", errors);
        $finish;
    end

endmodule
