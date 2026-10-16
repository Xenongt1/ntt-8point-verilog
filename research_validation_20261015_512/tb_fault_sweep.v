
`timescale 1ns/1ps
module tb_fault_sweep;
    parameter NVECT = 32;
    parameter LIMIT = 40;
    reg clk = 0, rst = 1, start = 0;
    reg [39:0] input_bus;
    wire done;
    wire [39:0] output_bus;
    reg [39:0] inputs [0:NVECT-1];
    reg [39:0] expected [0:NVECT-1];
    integer vi, target, bitn, injection_cycle, fd, total;
    integer elapsed, finished, value_before, value_after;
    reg [39:0] observed;

    ntt_top dut(.clk(clk), .rst(rst), .start(start),
                .input_bus(input_bus), .done(done), .output_bus(output_bus));
    always #5 clk = ~clk;

    task run_case(input integer t, input integer b, input integer c);
        integer cycles;
        begin
            @(negedge clk);
            rst = 1; start = 0;
            repeat (2) @(negedge clk);
            rst = 0; start = 1;
            @(negedge clk);
            start = 0;
            cycles = 0;
            value_before = -1; value_after = -1;

            while ((done !== 1'b1) && (cycles < LIMIT)) begin
                if (t >= 0 && cycles == c) begin
                    case (t)
                        0: begin
                            value_before = dut.state;
                            dut.state = dut.state ^ (2'b01 << b);
                            value_after = dut.state;
                        end
                        1: begin
                            value_before = dut.stage;
                            dut.stage = dut.stage ^ (2'b01 << b);
                            value_after = dut.stage;
                        end
                        2: begin
                            value_before = dut.counter;
                            dut.counter = dut.counter ^ (2'b01 << b);
                            value_after = dut.counter;
                        end
                        default: begin
                            value_before = dut.mem[t-3];
                            dut.mem[t-3] = dut.mem[t-3] ^ (5'b00001 << b);
                            value_after = dut.mem[t-3];
                        end
                    endcase
                end
                @(posedge clk);
                #1;
                cycles = cycles + 1;
                @(negedge clk);
            end
            elapsed = cycles;
            finished = (done === 1'b1);
            observed = output_bus;
        end
    endtask

    initial begin
        $readmemh("research_validation_20261015_512/inputs.hex", inputs);
        $readmemh("research_validation_20261015_512/expected.hex", expected);
        fd = $fopen("research_validation_20261015_512/faults.csv", "w");
        if (!fd) $fatal(1, "Cannot open CSV output");
        $fdisplay(fd, "vector,target,bit,cycle,before,after,done,elapsed,output_hex");
        total = 0;
        for (vi = 0; vi < NVECT; vi = vi + 1) begin
            input_bus = inputs[vi];
            run_case(-1, 0, -1);
            if (!finished || elapsed != 12 || observed !== expected[vi])
                $fatal(1, "BASELINE FAILED vector=%0d done=%0d cycles=%0d observed=%h expected=%h",
                       vi, finished, elapsed, observed, expected[vi]);
            $display("BASELINE PASS vector=%0d cycles=%0d", vi, elapsed);

            for (target = 0; target < 11; target = target + 1)
                for (bitn = 0; bitn < ((target < 3) ? 2 : 5); bitn = bitn + 1)
                    for (injection_cycle = 0; injection_cycle < 12;
                         injection_cycle = injection_cycle + 1) begin
                        run_case(target, bitn, injection_cycle);
                        if (value_before < 0 || value_after < 0)
                            $fatal(1, "Injection was not recorded");
                        $fdisplay(fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%010h",
                                  vi, target, bitn, injection_cycle,
                                  value_before, value_after, finished, elapsed, observed);
                        total = total + 1;
                    end
        end
        $fclose(fd);
        $display("COMPLETE vectors=%0d fault_cases=%0d", NVECT, total);
        $finish;
    end
endmodule
