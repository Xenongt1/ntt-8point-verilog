// tb_butterfly.v
//
// Standalone test of JUST the butterfly unit, before it's wired into
// anything bigger. Feeds in the exact 4 stage-1 pairs you already
// verified by hand, and checks the outputs match.

`timescale 1ns/1ps

module tb_butterfly;

    reg  [4:0] a, b, tw;   // drive the DUT's inputs
    wire [4:0] u, v;       // observe the DUT's outputs

    integer errors = 0;    // running count of mismatches

    // dut = "device under test" - the butterfly module we're checking
    ntt_butterfly dut (
        .a(a), .b(b), .tw(tw),
        .u(u), .v(v)
    );

    // check() drives one (a, b, tw) triple in and compares both outputs
    // against the values you already worked out by hand for that pair.
    task check(input [4:0] a_in, input [4:0] b_in, input [4:0] tw_in,
               input [4:0] u_expected, input [4:0] v_expected);
        begin
            a = a_in; b = b_in; tw = tw_in;
            #1; // ntt_butterfly is purely combinational (no clock), so
                // this tiny delay just lets the simulator settle the
                // logic before we read u and v
            if (u !== u_expected || v !== v_expected) begin
                $display("FAIL: a=%0d b=%0d tw=%0d -> got u=%0d v=%0d, expected u=%0d v=%0d",
                          a_in, b_in, tw_in, u, v, u_expected, v_expected);
                errors = errors + 1;
            end else begin
                $display("PASS: a=%0d b=%0d tw=%0d -> u=%0d v=%0d",
                          a_in, b_in, tw_in, u, v);
            end
        end
    endtask

    initial begin
        // Stage 1 pairs, hand-verified earlier:
        check(1, 5, 1,  6, 13);   // pair (0,4), tw=omega^0=1
        check(2, 6, 9,  8, 15);   // pair (1,5), tw=omega^1=9
        check(3, 7, 13, 10, 16);  // pair (2,6), tw=omega^2=13
        check(4, 8, 15, 12, 8);   // pair (3,7), tw=omega^3=15

        if (errors == 0)
            $display("\nALL TESTS PASSED");
        else
            $display("\n%0d TEST(S) FAILED", errors);

        $finish;
    end

endmodule
