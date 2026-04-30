/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */


`default_nettype none

module izh_core (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               step_en,
    input  wire signed [15:0] i_q8_8,

    output reg                spike,
    output reg signed [15:0]  v_q8_8,
    output reg signed [15:0]  u_q8_8
);

    // ------------------------------------------------------------
    // Fixed-point convention:
    //   v_q8_8, u_q8_8, i_q8_8 are signed Q8.8.
    //   a and b are signed Q0.16 coefficients.
    //
    // Regular-spiking default:
    //   a = 0.02
    //   b = 0.20
    //   c = -65
    //   d = 8
    // ------------------------------------------------------------

    localparam signed [31:0] A_Q16       = 32'sd1311;    // 0.02 * 65536
    localparam signed [31:0] B_Q16       = 32'sd13107;   // 0.20 * 65536

    localparam signed [31:0] CONST_140_Q = 32'sd35840;   // 140 * 256
    localparam signed [31:0] VTH_Q       = 32'sd7680;    // 30 * 256

    localparam signed [15:0] C_Q8_8      = -16'sd16640;  // -65 * 256
    localparam signed [15:0] D_Q8_8      =  16'sd2048;   // 8 * 256

    localparam signed [15:0] V_INIT_Q    = -16'sd16640;  // -65 * 256
    localparam signed [15:0] U_INIT_Q    = -16'sd3328;   // b*v = 0.2*(-65) = -13

    reg signed [31:0] v_ext;
    reg signed [31:0] u_ext;

    reg signed [31:0] v_sq_32;
    reg signed [47:0] v_sq_ext_48;
    reg signed [47:0] quad_48;

    reg signed [31:0] term004_32;
    reg signed [31:0] term5_32;
    reg signed [31:0] dv_32;
    reg signed [31:0] v_euler_32;

    reg signed [47:0] bv_tmp_48;
    reg signed [31:0] bv_32;
    reg signed [31:0] bu_diff_32;
    reg signed [63:0] du_tmp_64;
    reg signed [31:0] du_32;
    reg signed [31:0] u_euler_32;

    function signed [15:0] sat16_32;
        input signed [31:0] x;
        begin
            if (x > 32'sd32767)
                sat16_32 = 16'sh7FFF;
            else if (x < -32'sd32768)
                sat16_32 = 16'sh8000;
            else
                sat16_32 = x[15:0];
        end
    endfunction

    always @* begin
        v_ext = {{16{v_q8_8[15]}}, v_q8_8};
        u_ext = {{16{u_q8_8[15]}}, u_q8_8};

        // --------------------------------------------------------
        // dv = 0.04*v^2 + 5*v + 140 - u + I
        //
        // 0.04 is approximated as 41/1024 = 0.0400390625.
        // This avoids a general coefficient multiplier for 0.04.
        //
        // v^2:
        //   Q8.8 * Q8.8 = Q16.16
        //
        // (41/1024)*v^2:
        //   shift by 10 for /1024
        //   shift by 8 more to return from Q16.16 to Q8.8
        //   total shift = 18
        // --------------------------------------------------------

        v_sq_32     = v_q8_8 * v_q8_8;
        v_sq_ext_48 = {{16{v_sq_32[31]}}, v_sq_32};

        quad_48     = (v_sq_ext_48 <<< 5)   // *32
                    + (v_sq_ext_48 <<< 3)   // *8
                    +  v_sq_ext_48;         // *1
                                              // total *41

        term004_32  = quad_48 >>> 18;
        term5_32    = (v_ext <<< 2) + v_ext; // 5*v

        dv_32       = term004_32
                    + term5_32
                    + CONST_140_Q
                    - u_ext
                    + {{16{i_q8_8[15]}}, i_q8_8};

        v_euler_32  = v_ext + dv_32;

        // --------------------------------------------------------
        // du = a * (b*v - u)
        //
        // b*v:
        //   Q8.8 * Q0.16 = Q8.24
        //   shift by 16 -> Q8.8
        //
        // a*(b*v-u):
        //   Q8.8 * Q0.16 = Q8.24
        //   shift by 16 -> Q8.8
        // --------------------------------------------------------

        bv_tmp_48   = v_q8_8 * B_Q16;
        bv_32       = bv_tmp_48 >>> 16;

        bu_diff_32  = bv_32 - u_ext;
        du_tmp_64   = bu_diff_32 * A_Q16;
        du_32       = du_tmp_64 >>> 16;

        u_euler_32  = u_ext + du_32;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            v_q8_8 <= V_INIT_Q;
            u_q8_8 <= U_INIT_Q;
            spike  <= 1'b0;
        end else if (step_en) begin
            if (v_euler_32 >= VTH_Q) begin
                v_q8_8 <= C_Q8_8;
                u_q8_8 <= sat16_32(u_ext + {{16{D_Q8_8[15]}}, D_Q8_8});
                spike  <= 1'b1;
            end else begin
                v_q8_8 <= sat16_32(v_euler_32);
                u_q8_8 <= sat16_32(u_euler_32);
                spike  <= 1'b0;
            end
        end else begin
            spike <= 1'b0;
        end
    end

endmodule


module tt_um_abiaselli_UDIZH1 (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // Bidirectional input path
    output wire [7:0] uio_out,  // Bidirectional output path
    output wire [7:0] uio_oe,   // Bidirectional output enable, active high
    input  wire       ena,      // High when selected
    input  wire       clk,
    input  wire       rst_n
);

    // ui_in[0]    = step enable
    // ui_in[7:1]  = input current code
    //
    // I = ui_in[7:1] / 8
    //
    // For approximately I = 10:
    //   ui_in[7:1] = 80
    //   ui_in[0]   = 1
    //   ui_in      = 8'hA1

    wire step_en = ui_in[0] & ena;

    wire signed [15:0] i_q8_8 = ({9'b0, ui_in[7:1]} << 5);

    wire spike;
    wire signed [15:0] v_q8_8;
    wire signed [15:0] u_q8_8;

    izh_core neuron0 (
        .clk     (clk),
        .rst_n   (rst_n),
        .step_en (step_en),
        .i_q8_8  (i_q8_8),
        .spike   (spike),
        .v_q8_8  (v_q8_8),
        .u_q8_8  (u_q8_8)
    );

    // Display-friendly signed integer outputs.
    // v_display = integer part of v plus 128.
    // Example:
    //   v = -65 -> output about 63
    //   v = 0   -> output 128
    //   spike   -> output 255

    wire [7:0] v_display = v_q8_8[15:8] + 8'd128;
    wire [7:0] u_display = u_q8_8[15:8] + 8'd128;

    assign uo_out  = spike ? 8'hFF : v_display;

    // Use bidirectional pins as outputs for recovery-variable debug.
    assign uio_out = u_display;
    assign uio_oe  = 8'hFF;

    // Prevent unused-input warnings.
    wire _unused = &{uio_in, 1'b0};

endmodule
