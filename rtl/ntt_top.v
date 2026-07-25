// ntt_top.v
//
// The complete iterative 8-point NTT accelerator. This is the "reuse one
// butterfly unit across all stages" design from the task doc: there is
// exactly ONE ntt_butterfly instance here, and the FSM below feeds it a
// different pair of memory values (and a different twiddle) every clock
// cycle, for 12 cycles total (4 butterflies x 3 stages), instead of
// building 12 separate butterfly circuits.
//
// Interface:
//   clk, rst        : standard synchronous, active-high reset
//   start            : pulse high for 1 cycle to load input_bus and begin
//   input_bus[39:0]  : 8 packed 5-bit values, value i at bits [i*5 +: 5]
//   done             : goes high once all 3 stages have completed
//   output_bus[39:0] : same packing as input_bus, valid when done=1

module ntt_top (
    input  wire        clk,
    input  wire        rst,
    input  wire        start,
    input  wire [39:0] input_bus,
    output reg         done,
    output wire [39:0] output_bus
);

    // ---- Register file: the 8 working slots, reused in-place across
    // ---- all 3 stages, exactly like the Python reference model. ----
    reg [4:0] mem [0:7];

    // ---- FSM state ----
    localparam S_IDLE = 2'd0,
               S_RUN  = 2'd1,
               S_DONE = 2'd2;

    reg [1:0] state;
    reg [1:0] stage;    // which of the 3 stages we're on (0,1,2)
    reg [1:0] counter;  // which of the 4 butterflies within this stage (0..3)

    integer i;

    // ---- Address generator: tells us which two memory positions and
    // ---- which twiddle power this cycle's butterfly needs ----
    wire [2:0] idx1_w, idx2_w, twpow_w;
    ntt_addr_gen addr_gen_inst (
        .stage(stage), .counter(counter),
        .idx1(idx1_w), .idx2(idx2_w), .twpow(twpow_w)
    );

    // ---- Twiddle ROM lookup for this cycle ----
    wire [4:0] tw_w;
    ntt_twiddle_rom rom_inst (
        .power(twpow_w), .tw(tw_w)
    );

    // ---- Read the two operands for this cycle's butterfly ----
    wire [4:0] a_w = mem[idx1_w];
    wire [4:0] b_w = mem[idx2_w];

    // ---- The single, reused butterfly unit ----
    wire [4:0] u_w, v_w;
    ntt_butterfly bfly_inst (
        .a(a_w), .b(b_w), .tw(tw_w),
        .u(u_w), .v(v_w)
    );

    // ---- FSM + register file update ----
    always @(posedge clk) begin
        if (rst) begin
            state   <= S_IDLE;
            done    <= 1'b0;
            stage   <= 2'd0;
            counter <= 2'd0;
        end else begin
            case (state)

                S_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        // Parallel-load all 8 input values in one cycle
                        for (i = 0; i < 8; i = i + 1)
                            mem[i] <= input_bus[i*5 +: 5];
                        stage   <= 2'd0;
                        counter <= 2'd0;
                        state   <= S_RUN;
                    end
                end

                S_RUN: begin
                    // Write this cycle's butterfly result back in place -
                    // the same "overwrite the same slots" trick from the
                    // software reference model.
                    mem[idx1_w] <= u_w;
                    mem[idx2_w] <= v_w;

                    if (counter == 2'd3) begin
                        counter <= 2'd0;
                        if (stage == 2'd2) begin
                            // Just finished the last butterfly of stage 3
                            state <= S_DONE;
                            done  <= 1'b1;
                        end else begin
                            stage <= stage + 2'd1;
                        end
                    end else begin
                        counter <= counter + 2'd1;
                    end
                end

                S_DONE: begin
                    done <= 1'b1; // hold done high until next start/reset
                end

                default: state <= S_IDLE;
            endcase
        end
    end

    // ---- Pack the register file back out as the output bus ----
    assign output_bus = {mem[7], mem[6], mem[5], mem[4],
                          mem[3], mem[2], mem[1], mem[0]};

endmodule
