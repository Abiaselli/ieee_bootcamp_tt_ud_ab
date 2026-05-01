/*
 * Copyright (c) 2026 Austin Biaselli
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Tiny Tapeout SKY130 analog/custom-GDS wrapper for the analog Izhikevich
// neuron macro.
//
// Public interface:
//   ua[0]     = V / ISYN membrane node
//   ua[1]     = U recovery-variable node / external recovery control
//   ua[2]     = VD recovery increment/reset bias
//   ua[3]     = VC membrane reset bias
//   ui_in[0]  = ACK_IN, digital acknowledge input
//   ui_in[1]  = POLARITY_INV, digital handshake polarity invert control
//   uo_out[0] = REQ_OUT, digital request/spike output
//
// Power/reference:
//   VDPWR = 1.8 V Tiny Tapeout digital/core power rail
//   VGND  = Tiny Tapeout ground rail
//
// Notes:
// - VDD/VGND are rails, not ordinary GPIO bits. Do not power the analog macro
//   from ui_in/uo_out pins.
// - REQ_N_FROM_MACRO must already be a valid VDPWR-domain digital signal.
//   If the analog AER circuit only swings to a low analog rail, put a
//   comparator/level-shifter in the custom macro before this wrapper.
// - Unused digital outputs are tied low as required by the TT analog flow.

module tt_um_abiaselli_UDIZH1 (
    input  wire       VGND,
    input  wire       VDPWR,  // 1.8 V power supply
    // input wire     VAPWR,  // Uncomment only for the 3.3 V template and uses_3v3=true
    input  wire [7:0] ui_in,  // Dedicated inputs
    output wire [7:0] uo_out, // Dedicated outputs
    input  wire [7:0] uio_in, // IOs: input path
    output wire [7:0] uio_out,// IOs: output path
    output wire [7:0] uio_oe, // IOs: enable path, active high
    inout  wire [7:0] ua,     // Analog pins; only purchased ua[5:0] can be used
    input  wire       ena,    // High when project is enabled/powered
    input  wire       clk,
    input  wire       rst_n
);

    wire polarity_inv;
    wire ack_to_macro;
    wire req_n_from_macro;
    wire req_to_pad;

    assign polarity_inv = ui_in[1] & ena;

    // ui_in[0] is the external ACK convention. ui_in[1] lets us flip the
    // handshake convention at the wrapper boundary without changing the analog
    // macro. This is handshake inversion only; it is not physical rail swapping.
    assign ack_to_macro = (ui_in[0] ^ polarity_inv) & ena;
    assign req_to_pad   = req_n_from_macro ^ polarity_inv;

    // Analog hard macro. The final GDS/LEF macro should expose exactly these
    // named pins, plus any required physical VPWR/VGND straps in layout.
    izh_sky130_macro_vu_vd_vc izh0 (
        .V      (ua[0]),
        .U      (ua[1]),
        .VD     (ua[2]),
        .VC     (ua[3]),
        .VGND   (VGND),
        .VDPWR  (VDPWR),
        .ACK    (ack_to_macro),
        .REQ_N  (req_n_from_macro)
    );

    // Dedicated digital outputs:
    //   uo_out[0] = REQ output after optional polarity inversion.
    //   uo_out[7:1] = unused, tied to GND.
    assign uo_out = {7'b0000000, req_to_pad};

    // Bidirectional digital GPIOs are unused. Keep their output data at 0 and
    // disable all output drivers.
    assign uio_out = 8'b00000000;
    assign uio_oe  = 8'b00000000;

    // Avoid unused-signal lint warnings. These are referenced but not driven.
    wire _unused = &{
        ui_in[7:2],
        uio_in,
        ua[7:4],
        clk,
        rst_n,
        VGND,
        VDPWR,
        1'b0
    };

endmodule

// Blackbox placeholder for the custom analog GDS/LEF macro.
// The physical macro cell should be named izh_sky130_macro_vu_vd_vc and should
// have pins matching this declaration.
(* blackbox *)
module izh_sky130_macro_vu_vd_vc (
    inout  wire V,
    inout  wire U,
    inout  wire VD,
    inout  wire VC,
    input  wire VGND,
    input  wire VDPWR,
    input  wire ACK,
    output wire REQ_N
);
endmodule

`default_nettype wire
