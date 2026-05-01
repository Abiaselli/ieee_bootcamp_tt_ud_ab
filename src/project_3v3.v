/*
 * Copyright (c) 2026 Austin Biaselli
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Same as project.v, but with the optional Tiny Tapeout 3.3 V VAPWR rail
// exposed for layouts based on tt_analog_1x2_3v3.def and uses_3v3: true.
// Use this only if the custom GDS really connects to VAPWR.

module tt_um_abiaselli_UDIZH1 (
    input  wire       VGND,
    input  wire       VDPWR,  // 1.8 V power supply
    input  wire       VAPWR,  // 3.3 V analog supply, only for _3v3.def flow
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    inout  wire [7:0] ua,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    wire polarity_inv;
    wire ack_to_macro;
    wire req_n_from_macro;
    wire req_to_pad;

    assign polarity_inv = ui_in[1] & ena;
    assign ack_to_macro = (ui_in[0] ^ polarity_inv) & ena;
    assign req_to_pad   = req_n_from_macro ^ polarity_inv;

    izh_sky130_macro_vu_vd_vc_3v3 izh0 (
        .V      (ua[0]),
        .U      (ua[1]),
        .VD     (ua[2]),
        .VC     (ua[3]),
        .VGND   (VGND),
        .VDPWR  (VDPWR),
        .VAPWR  (VAPWR),
        .ACK    (ack_to_macro),
        .REQ_N  (req_n_from_macro)
    );

    assign uo_out  = {7'b0000000, req_to_pad};
    assign uio_out = 8'b00000000;
    assign uio_oe  = 8'b00000000;

    wire _unused = &{
        ui_in[7:2],
        uio_in,
        ua[7:4],
        clk,
        rst_n,
        VGND,
        VDPWR,
        VAPWR,
        1'b0
    };

endmodule

(* blackbox *)
module izh_sky130_macro_vu_vd_vc_3v3 (
    inout  wire V,
    inout  wire U,
    inout  wire VD,
    inout  wire VC,
    input  wire VGND,
    input  wire VDPWR,
    input  wire VAPWR,
    input  wire ACK,
    output wire REQ_N
);
endmodule

`default_nettype wire
