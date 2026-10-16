
module ntt_output_checker(input wire clk, rst, start,
    input wire [39:0] input_bus, output_bus,
    output wire match);
    reg [4:0] check3, check6;
    function automatic [4:0] coefficient(input integer k, j);
        integer v, n;
        begin
            v = 1;
            for (n = 0; n < k*j; n = n + 1) v = (v*9) % 17;
            coefficient = v;
        end
    endfunction
    function automatic [4:0] direct_value(input [39:0] x, input integer k);
        integer j;
        reg [15:0] total;
        begin
            total = 0;
            for (j = 0; j < 8; j = j + 1)
                total = total + x[j*5 +: 5] * coefficient(k,j);
            direct_value = total % 17;
        end
    endfunction
    always @(posedge clk) begin
        if (rst) begin check3 <= 0; check6 <= 0; end
        else if (start) begin
            // Hardware output 3 = X[6]; hardware output 6 = X[3].
            check3 <= direct_value(input_bus, 6);
            check6 <= direct_value(input_bus, 3);
        end
    end
    assign match = (output_bus[15 +: 5] == check3) &&
                   (output_bus[30 +: 5] == check6);
endmodule
