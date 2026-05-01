* Izhikevich mixed-signal neuron, ngspice-style SKY130 subckt netlist
* Device sizes: SKY130 ratio-scaled to preserve W/L while meeting rough W>=0.42u L>=0.15u
* Include path may need to be edited:
*.lib "$PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice" tt
.subckt izh_sky130_zvndigital V U VC VD ACK REQ VDD VGND
Cv V VGND 20f
Cu U VGND 300f
Creq REQ VGND 25f
XM1 N001 V VGND VGND sky130_fd_pr__nfet_01v8 w=420n l=175n
XM2 N001 N001 VDD VDD sky130_fd_pr__pfet_01v8 w=420n l=175n
XM3 V N001 VDD VDD sky130_fd_pr__pfet_01v8 w=420n l=175n
XM4 U N001 VDD VDD sky130_fd_pr__pfet_01v8 w=1.08333u l=150n
XM5 V U VGND VGND sky130_fd_pr__nfet_01v8 w=420n l=630n
XM6 U U VGND VGND sky130_fd_pr__nfet_01v8 w=700n l=150n
XM7 V ACK VC VC sky130_fd_pr__nfet_01v8 w=420n l=840n
XM8 U N002 VD VD sky130_fd_pr__pfet_01v8 w=1.56u l=150n
XM9 N005 V VGND VGND sky130_fd_pr__nfet_01v8 w=420n l=420n
XM10 N005 V VDD VDD sky130_fd_pr__pfet_01v8 w=1.5u l=150n
XM11 N003 N005 VGND VGND sky130_fd_pr__nfet_01v8 w=1.5u l=150n
XM12 N003 N005 N004 N004 sky130_fd_pr__pfet_01v8 w=420n l=420n
XM13 VGND N003 N006 N006 sky130_fd_pr__nfet_01v8 w=420n l=210n
XM14 N003 N005 VGND VGND sky130_fd_pr__nfet_01v8 w=420n l=420n
XM15 REQ N003 VGND VGND sky130_fd_pr__nfet_01v8 w=420n l=1.05u
XM16 N002 ACK N006 N006 sky130_fd_pr__nfet_01v8 w=420n l=420n
XM17 N004 ACK VDD VDD sky130_fd_pr__pfet_01v8 w=420n l=420n
XM18 REQ N003 VDD VDD sky130_fd_pr__pfet_01v8 w=420n l=210n
XMX_ACK_P N002 ACK VDD VDD sky130_fd_pr__pfet_01v8 w=420n l=210n
.ends izh_sky130_zvndigital

* Example bench:
*.lib /path/to/sky130A/libs.tech/ngspice/sky130.lib.spice tt
*XN v u vc vd ack req vdd vgnd izh_sky130_zvndigital
*Vvdd vdd 0 0.18
*Vgnd vgnd 0 0
*Vvc vc 0 0.14
*Vvd vd 0 0.14
*Iin v vgnd DC 2p
*Vack ack 0 PULSE(0 0.18 1u 1n 1n 1u 20u)
*.tran 100n 10m
*.control
*run
*plot v(v) v(u) v(req) v(ack)
*.endc
*.end
