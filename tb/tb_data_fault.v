`timescale 1ns/1ps

module tb_data_fault;
    reg clk = 0;
    reg rst = 1;
    reg start = 0;

    wire done;
    wire [39:0] out_bus;

    localparam [39:0] EXPECTED =
        {5'd8,5'd3,5'd6,5'd1,5'd14,5'd12,5'd13,5'd2};

    ntt_top dut (
        .clk(clk),
        .rst(rst),
        .start(start),
        .input_bus({5'd8,5'd7,5'd6,5'd5,5'd4,5'd3,5'd2,5'd1}),
        .done(done),
        .output_bus(out_bus)
    );

    always #5 clk = ~clk;

    task run_case(input integer inject_fault);
        integer cycles;
        begin
            // Drive reset/start away from the rising capture edge.
            @(negedge clk);
            rst = 1;
            start = 0;
            repeat (2) @(negedge clk);

            rst = 0;
            start = 1;
            @(negedge clk);
            start = 0;
            cycles = 0;

            $display("\nCASE fault_enabled=%0d", inject_fault);

            while ((done !== 1'b1) && (cycles < 40)) begin
                // Corrupt one data bit before the ninth butterfly.
                if (inject_fault && cycles == 8) begin
                    if (dut.stage !== 2'b10 ||
                        dut.mem[1] !== 5'd3)
                        $fatal(1, "Unexpected state before data injection");

                    $display("BEFORE FAULT: mem[1]=%0d", dut.mem[1]);
                    dut.mem[1] = dut.mem[1] ^ 5'b00001;
                    #1;
                    $display("AFTER FAULT: mem[1]=%0d", dut.mem[1]);
                end

                @(posedge clk);
                #1;
                cycles = cycles + 1;

                if (inject_fault && cycles >= 8 && cycles <= 13)
                    $display("TRACE completed_cycles=%0d stage=%0d counter=%0d mem[0]=%0d done=%b",
                             cycles, dut.stage, dut.counter,
                             dut.mem[0], done);

                @(negedge clk);
            end

            $display("RESULT done=%b cycles=%0d matches_reference=%b",
                     done, cycles, out_bus === EXPECTED);

            $display("OUTPUT mem[0..7]: %0d %0d %0d %0d %0d %0d %0d %0d",
                     out_bus[4:0], out_bus[9:5],
                     out_bus[14:10], out_bus[19:15],
                     out_bus[24:20], out_bus[29:25],
                     out_bus[34:30], out_bus[39:35]);

            if (!inject_fault &&
                ((done !== 1'b1) || (out_bus !== EXPECTED) ||
                 (cycles != 12)))
                $fatal(1, "Baseline failed; stop before interpreting faults");
        end
    endtask

    initial begin
        run_case(0);
        run_case(1);
        $finish;
    end
endmodule
