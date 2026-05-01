`default_nettype none

// Tiny Tapeout analog/custom-GDS wrapper stub for the Izhikevich neuron macro.
// This is NOT the analog circuit itself. The analog circuit must be supplied
// as a custom GDS/LEF hard macro with pins matching izh_sky130_macro below.

module izh_sky130_macro_vu_vd_vc (
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

    // Suggested pin map:
    // ua[0] = V / Isyn injection node
    // ua[1] = U monitor node
    // ua[2] = VC reset bias
    // ua[3] = VD recovery increment bias
    // ua[4] = local VGND/reference bias
    // ua[5] = local VDD/bias supply for neuron macro
    // ui_in[0] = ACK reset/handshake input, active high
    // uo_out[0] = REQ spike/request output, active low

    wire ack = ui_in[0] & ena;
    wire req_n;

    izh_sky130_macro izh0 (
        .V      (ua[0]),
        .U      (ua[1]),
        .VC     (ua[2]),
        .VD     (ua[3]),
        .VGND_B (VGND),
        .VDD_B  (VPWR),
        .ACK    (ack),
        .REQ_N  (req_n)
    );

    assign uo_out = {7'b0, req_n};

    // Not using bidirectional digital GPIOs in this first wrapper.
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    // Prevent unused warnings.
    wire _unused = &{clk, rst_n, ui_in[7:1], uio_in, ua[6], ua[7], 1'b0};

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
