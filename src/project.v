/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */


`default_nettype none

// Tiny Tapeout analog/custom-GDS wrapper stub for the Izhikevich neuron macro.
// This is NOT the analog circuit itself. The analog circuit must be supplied
// as a custom GDS/LEF hard macro with pins matching izh_sky130_macro below.
//
// Digital helper behavior:
//   ui_in[0] = external ACK, active high
//   ui_in[1] = auto-ACK enable
//   ui_in[3:2] = auto-ACK delay code
//   ui_in[5:4] = auto-ACK pulse width code
//   uo_out[0] = REQ_N from analog macro
//   uo_out[1] = ACK actually sent to analog macro
//
// Important: REQ_N must be a valid VDPWR-domain digital signal before it
// enters this Verilog logic. If the analog REQ_N only swings to a low-voltage
// analog rail such as 0.18 V, add a comparator/level-shifter in the analog macro
// or export REQ_N on an analog pin instead.

module  tt_um_abiaselli_UDIZH1 (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n,
    inout  wire [7:0] ua
);

    // Suggested analog pin map:
    // ua[0] = V / Isyn injection node
    // ua[1] = U monitor node
    // ua[2] = VC reset bias
    // ua[3] = VD recovery increment bias
    // ua[4] = local VGND/reference bias
    // ua[5] = local VDD/bias supply for neuron macro
    // ua[6] and ua[7] are intentionally unused; TT analog shuttles only expose
    // the first six analog pins when purchased/connected.

    wire req_n;
    wire ack_ext = ui_in[0] & ena;
    wire auto_ack_en = ui_in[1] & ena;

    wire ack_auto;
    aer_auto_ack #(
        .CTR_WIDTH(8)
    ) ack_ctrl (
        .clk        (clk),
        .rst_n      (rst_n),
        .enable     (auto_ack_en),
        .req_n      (req_n),
        .delay_sel  (ui_in[3:2]),
        .width_sel  (ui_in[5:4]),
        .ack        (ack_auto)
    );

    wire ack_to_macro = ack_ext | ack_auto;

    izh_sky130_macro izh0 (
        .V      (ua[0]),
        .U      (ua[1]),
        .VC     (ua[2]),
        .VD     (ua[3]),
        .VGND_B (ua[4]),
        .VDD_B  (ua[5]),
        .ACK    (ack_to_macro),
        .REQ_N  (req_n)
    );

    assign uo_out = {6'b0, ack_to_macro, req_n};

    // Not using bidirectional digital GPIOs in this first wrapper.
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    // Prevent unused warnings.
    wire _unused = &{uio_in, ui_in[7:6], ua[6], ua[7], 1'b0};

endmodule

module aer_auto_ack #(
    parameter CTR_WIDTH = 8
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 enable,
    input  wire                 req_n,
    input  wire [1:0]           delay_sel,
    input  wire [1:0]           width_sel,
    output reg                  ack
);

    localparam S_IDLE  = 2'd0;
    localparam S_DELAY = 2'd1;
    localparam S_ACK   = 2'd2;

    reg [1:0] state;
    reg [CTR_WIDTH-1:0] count;

    reg req_n_d;
    wire req_fall = req_n_d & ~req_n;

    function [CTR_WIDTH-1:0] delay_count;
        input [1:0] sel;
        begin
            case (sel)
                2'b00: delay_count = 8'd1;
                2'b01: delay_count = 8'd4;
                2'b10: delay_count = 8'd16;
                default: delay_count = 8'd64;
            endcase
        end
    endfunction

    function [CTR_WIDTH-1:0] width_count;
        input [1:0] sel;
        begin
            case (sel)
                2'b00: width_count = 8'd1;
                2'b01: width_count = 8'd4;
                2'b10: width_count = 8'd16;
                default: width_count = 8'd64;
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            req_n_d <= 1'b1;
            state   <= S_IDLE;
            count   <= {CTR_WIDTH{1'b0}};
            ack     <= 1'b0;
        end else begin
            req_n_d <= req_n;
            ack <= 1'b0;

            if (!enable) begin
                state <= S_IDLE;
                count <= {CTR_WIDTH{1'b0}};
            end else begin
                case (state)
                    S_IDLE: begin
                        if (req_fall) begin
                            state <= S_DELAY;
                            count <= delay_count(delay_sel);
                        end
                    end
                    S_DELAY: begin
                        if (count == 0) begin
                            state <= S_ACK;
                            count <= width_count(width_sel);
                        end else begin
                            count <= count - 1'b1;
                        end
                    end
                    S_ACK: begin
                        ack <= 1'b1;
                        if (count == 0) begin
                            state <= S_IDLE;
                        end else begin
                            count <= count - 1'b1;
                        end
                    end
                    default: begin
                        state <= S_IDLE;
                    end
                endcase
            end
        end
    end

endmodule

(* blackbox *)
module izh_sky130_macro (
    inout  wire V,
    inout  wire U,
    inout  wire VC,
    inout  wire VD,
    inout  wire VGND_B,
    inout  wire VDD_B,
    input  wire ACK,
    output wire REQ_N
);
endmodule

`default_nettype wire
