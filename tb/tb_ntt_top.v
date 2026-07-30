// tb_ntt_top.v
//
// Full-system test:
//   1. Load the 8 input values from a text file (input/input.mem)
//   2. Reset the design, pulse start
//   3. Let the FSM run all 3 stages (12 clock cycles)
//   4. Wait for done, unpack the result
//   5. Compare against the expected output [2, 13, 12, 14, 1, 6, 3, 8]

`timescale 1ns/1ps

module tb_ntt_top;

    reg         clk;
    reg         rst;
    reg         start;
    reg  [39:0] input_bus;
    wire        done;
    wire [39:0] output_bus;

    reg  [4:0]  mem_in  [0:7];   // loaded from the input file
    reg  [4:0]  mem_out [0:7];   // unpacked from output_bus for checking
    reg  [4:0]  expected [0:7];  // reference answer

    integer i;
    integer errors;

    // ---- Device under test ----
    ntt_top dut (
        .clk(clk), .rst(rst), .start(start),
        .input_bus(input_bus),
        .done(done), .output_bus(output_bus)
    );

    // ---- Clock generation: 10ns period ----
    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        // Load input vector from the text file
        $readmemb("input/input.mem", mem_in);

        // Set up the expected answer
        expected[0] = 5'd2;  expected[1] = 5'd13; expected[2] = 5'd12; expected[3] = 5'd14;
        expected[4] = 5'd1;  expected[5] = 5'd6;  expected[6] = 5'd3;  expected[7] = 5'd8;

        // Pack the loaded input into the bus format ntt_top expects
        input_bus = 40'd0;
        for (i = 0; i < 8; i = i + 1)
            input_bus[i*5 +: 5] = mem_in[i];

        $display("Loaded input: %0d %0d %0d %0d %0d %0d %0d %0d",
                  mem_in[0], mem_in[1], mem_in[2], mem_in[3],
                  mem_in[4], mem_in[5], mem_in[6], mem_in[7]);

        // Reset
        rst = 1'b1; start = 1'b0;
        @(posedge clk); @(posedge clk);
        rst = 1'b0;

        // Pulse start for exactly one cycle
        @(posedge clk);
        start = 1'b1;
        @(posedge clk);
        start = 1'b0;

        // Wait for the FSM to finish (up to a generous timeout)
        wait (done == 1'b1);
        @(posedge clk); // let output_bus settle post-done

        // Unpack the output bus back into individual values
        for (i = 0; i < 8; i = i + 1)
            mem_out[i] = output_bus[i*5 +: 5];

        $display("NTT output:   %0d %0d %0d %0d %0d %0d %0d %0d",
                  mem_out[0], mem_out[1], mem_out[2], mem_out[3],
                  mem_out[4], mem_out[5], mem_out[6], mem_out[7]);

        // Check against the expected reference answer
        errors = 0;
        for (i = 0; i < 8; i = i + 1) begin
            if (mem_out[i] !== expected[i]) begin
                $display("FAIL at position %0d: got %0d, expected %0d",
                          i, mem_out[i], expected[i]);
                errors = errors + 1;
            end
        end

        if (errors == 0)
            $display("\nALL 8 OUTPUTS MATCH THE HAND-VERIFIED RESULT - PASS");
        else
            $display("\n%0d POSITION(S) MISMATCHED - FAIL", errors);

        // Write the result out to a text file in the same 5-bit binary
        // format as the input, demonstrating the full file-in to file-out
        // path rather than console output alone.
        $writememb("output/output.mem", mem_out);
        $display("Output written to output/output.mem");

        $finish;
    end

    // Safety timeout in case done never asserts
    initial begin
        #1000;
        if (!done) begin
            $display("TIMEOUT: done never asserted");
            $finish;
        end
    end

endmodule
