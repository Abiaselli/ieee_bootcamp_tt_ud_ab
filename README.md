![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) 
# Tiny Tapeout Analog Project

- [Read the documentation for project](docs/info.md)

## Includes:
A current tile design for an IZH neuron and a PCB design based on the suggesetion to provide both.

# Izhikevich SKY130 conversion notes

This pack was generated from the uploaded `zvndigital.cir` topology and the 2022 subthreshold CMOS paper component-size table.

# TT analog Izhikevich wrapper: V/U/VD/VC pinout

This package uses four Tiny Tapeout analog pins and two dedicated digital pins.

## Public pinout

| Signal | Pin | Type |
|---|---:|---|
| V / ISYN | ua[0] | analog |
| U / recovery-control node | ua[1] | analog |
| VD | ua[2] | analog |
| VC | ua[3] | analog |
| ACK_IN | ui_in[0] | digital input |
| POLARITY_INV | ui_in[1] | digital input |
| REQ_OUT | uo_out[0] | digital output |
| VDD | VDPWR rail | power |
| GND | VGND rail | power |

Unused `uo_out[7:1]`, `uio_out[7:0]`, and `uio_oe[7:0]` are tied low in `src/project.v`.

