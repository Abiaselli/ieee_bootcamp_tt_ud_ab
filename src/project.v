/*
 * Copyright (c) 2024 Austin Biaselli
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Tiny Tapeout SKY130 analog/custom-GDS wrapper stub for the Izhikevich neuron.
//
// Four analog-pin version:
//   ua[0] = V / ISYN  membrane capacitor node and external input-current node
//   ua[1] = VDD_B     externally adjustable neuron analog supply/bias
//   ua[2] = VD        recovery increment/reset bias
//   ua[3] = VC        membrane reset bias
//
// Digital pins:
//   ui_in[0]  = ACK, active high
//   uo_out[0] = REQ_N, active low
//
// Notes:
//   * The actual transistor-level neuron must be implemented in the custom GDS/LEF.
//   * REQ_N must be a valid VDPWR-domain digital signal before it is driven onto uo_out[0].
//     If the analog AER circuit only swings to a low analog rail such as 0.18 V, add a
//     comparator/level shifter in the custom layout, or export REQ_N on an analog pin instead.
//   * VD and VC are kept as external analog pins in this version. If you need fewer analog pins,
//     tie VD to VDD_B and VC to VGND inside the custom layout and set analog_pins to 2.

module tt_um_abiaselli_UDIZH1 (
    input  wire       VGND,
    input  wire       VDPWR,   // 1.8 V digital core rail, useful for REQ_N output buffering/level shifting
    // input  wire    VAPWR,   // 3.3 V analog rail; only add this if uses_3v3: true and using the 3v3 DEF
    input  wire [7:0] ui_in,   // Dedicated digital inputs
    output wire [7:0] uo_out,  // Dedicated digital outputs
    input  wire [7:0] uio_in,  // Bidirectional GPIO input path
    output wire [7:0] uio_out, // Bidirectional GPIO output path
    output wire [7:0] uio_oe,  // Bidirectional GPIO output enable, active high
    inout  wire [7:0] ua,      // Analog pins; only ua[0]..ua[3] are used by this project
    input  wire       ena,     // High when selected
    input  wire       clk,
    input  wire       rst_n
);

    wire ack_to_macro = ui_in[0] & ena;
    wire req_n_from_macro;

    // This submodule name is a placeholder for the custom analog/layout cell.
    // In the final GDS/LEF flow, make sure the physical top-level pins match
    // tt_um_abiaselli_UDIZH1 and the functional connectivity below.
    izh_sky130_macro_4pin izh0 (
        .V      (ua[0]),
        .VDD_B  (ua[1]),
        .VD     (ua[2]),
        .VC     (ua[3]),
        .VGND   (VGND),
        .VDPWR  (VDPWR),
        .ACK    (ack_to_macro),
        .REQ_N  (req_n_from_macro)
    );

    // Active-low request/spike output. When the project is not selected, hold inactive high.
    assign uo_out[0] = ena ? req_n_from_macro : 1'b1;
    assign uo_out[7:1] = 7'b0;

    // No bidirectional digital GPIOs used.
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    // Consume otherwise-unused template inputs/pins for lint cleanliness.
    wire _unused = &{clk, rst_n, uio_in, ui_in[7:1], ua[7:4], 1'b0};

endmodule

(* blackbox *)
module izh_sky130_macro_4pin (
    inout  wire V,
    inout  wire VDD_B,
    inout  wire VD,
    inout  wire VC,
    input  wire VGND,
    input  wire VDPWR,
    input  wire ACK,
    output wire REQ_N
);
endmodule

`default_nettype wire
