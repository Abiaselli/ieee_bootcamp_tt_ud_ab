![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) 
# Tiny Tapeout Analog Project

- [Read the documentation for project](docs/info.md)

## Includes:
A current tile design for an IZH neuron and a PCB design based on the suggesetion to provide both.

# Izhikevich SKY130 conversion notes

This pack was generated from the uploaded `zvndigital.cir` topology and the 2022 subthreshold CMOS paper component-size table.

## Pin map

| Tiny Tapeout pin | Proposed function | Notes |
|---|---|---|
| ua[0] | V / Isyn | Membrane node and external current/voltage injection node |
| ua[1] | U | Recovery-variable monitor node |
| ua[2] | VC | V reset bias |
| ua[3] | VD | U increment/reset bias |
| ua[4] | VGND_B | Local ground/reference bias |
| ua[5] | VDD_B | Local neuron supply/bias |
| ui_in[0] | ACK | Active-high acknowledge/reset input |
| uo_out[0] | REQ_N | Active-low request/spike output |

## Ratio-scaled SKY130 sizes

These use rough minimums W>=0.42um and L>=0.15um while preserving each paper W/L ratio exactly. Check your specific PDK/CDF constraints in Virtuoso.

| Device | Type | Paper W/L | Ratio-scaled W/L |
|---|---|---:|---:|
| M1 | NMOS | 300n/125n | 420n/175n |
| M2 | PMOS | 300n/125n | 420n/175n |
| M3 | PMOS | 300n/125n | 420n/175n |
| M4 | PMOS | 650n/90n | 1.08333u/150n |
| M5 | NMOS | 400n/600n | 420n/630n |
| M6 | NMOS | 700n/150n | 700n/150n |
| M7 | NMOS | 175n/350n | 420n/840n |
| M8 | PMOS | 1.3u/125n | 1.56u/150n |
| M9 | NMOS | 100n/100n | 420n/420n |
| M10 | PMOS | 1u/100n | 1.5u/150n |
| M11 | NMOS | 1u/100n | 1.5u/150n |
| M12 | PMOS | 100n/100n | 420n/420n |
| M13 | NMOS | 200n/100n | 420n/210n |
| M14 | NMOS | 100n/100n | 420n/420n |
| M15 | NMOS | 100n/250n | 420n/1.05u |
| M16 | NMOS | 100n/100n | 420n/420n |
| M17 | PMOS | 100n/100n | 420n/420n |
| M18 | PMOS | 200n/100n | 420n/210n |
