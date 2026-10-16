
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
    integer mode, cb;
    wire pair_match;
    ntt_output_checker checker_inst(.clk(clk), .rst(rst), .start(start),
        .input_bus(input_bus), .output_bus(output_bus), .match(pair_match));
    task toggle_check(input integer bit_index);
        reg [4:0] old_check;
        begin
            old_check = (bit_index < 5) ? checker_inst.check3 : checker_inst.check6;
            if (bit_index < 5)
                checker_inst.check3 = checker_inst.check3 ^ (5'b1 << bit_index);
            else
                checker_inst.check6 = checker_inst.check6 ^ (5'b1 << (bit_index-5));
            if (bit_index < 5) begin
                if (checker_inst.check3 !== (old_check ^ (5'b1 << bit_index)))
                    $fatal(1, "CHECKER INJECTION FAILED");
            end else if (checker_inst.check6 !== (old_check ^ (5'b1 << (bit_index-5))))
                $fatal(1, "CHECKER INJECTION FAILED");
        end
    endtask
    
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
                
                if (mode == 1 && cycles == c) toggle_check(cb);
                if (t >= 0 && cycles == c) begin
                    if (mode == 2) toggle_check(cb);
    
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
            // Deliberate second fault in the comparison decision at observation.
            // This is a bypass demonstration, not a claim about EM feasibility.
            if (mode == 3) begin force pair_match = 1'b1; #1; end
        end
    endtask


    task record_case(input integer t, b, c);
        begin
            $fdisplay(fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%010h,%b,%0d,%0d",
                mode, vi, t, b, c, cb, finished, elapsed, observed, pair_match,
                checker_inst.check3, checker_inst.check6);
            total = total + 1;
        end
    endtask
    initial begin
        $readmemh("research_checker_20261016_128/inputs.hex", inputs);
        $readmemh("research_checker_20261016_128/expected.hex", expected);
        fd = $fopen("research_checker_20261016_128/faults.csv", "w");
        if (!fd) $fatal(1, "Cannot open CSV output");

        $fdisplay(fd, "mode,vector,target,bit,cycle,checker_bit,done,elapsed,output_hex,pair_match,check3,check6");
        total = 0;
        for (vi = 0; vi < NVECT; vi = vi + 1) begin
            input_bus = inputs[vi];
            mode = 0;
            run_case(-1, 0, -1);
            if (!finished || elapsed != 12 || observed !== expected[vi] || pair_match !== 1'b1)
                $fatal(1, "BASELINE FAILED vector=%0d match=%b", vi, pair_match);
            if (checker_inst.check3 !== expected[vi][15 +: 5] ||
                checker_inst.check6 !== expected[vi][30 +: 5])
                $fatal(1, "CHECKER REFERENCE FAILED");
            $display("BASELINE PASS vector=%0d", vi);
            for (mode = 0; mode < 4; mode = mode + 1) begin
                if (mode == 1) begin
                    for (cb = 0; cb < 10; cb = cb + 1)
                        for (injection_cycle = 0; injection_cycle < 12; injection_cycle = injection_cycle + 1) begin
                            run_case(-1, 0, injection_cycle);
                            record_case(-1, -1, injection_cycle);
                        end
                end else begin
                    for (target = 0; target < 11; target = target + 1)
                        for (bitn = 0; bitn < ((target < 3) ? 2 : 5); bitn = bitn + 1)
                            for (injection_cycle = 0; injection_cycle < 12; injection_cycle = injection_cycle + 1) begin
                                // One reproducible sampled checker bit per accelerator fault.
                                cb = (vi + target*3 + bitn + injection_cycle) % 10;
                                run_case(target, bitn, injection_cycle);
                                if (value_before < 0 || value_after != (value_before ^ (1 << bitn)))
                                    $fatal(1, "INJECTION FAILED");
                                record_case(target, bitn, injection_cycle);
                                if (mode == 3) begin release pair_match; #1; end
                            end
                end
            end
        end
        $fclose(fd);
        $display("COMPLETE vectors=%0d fault_cases=%0d", NVECT, total);
        $finish;
    end
endmodule
