* ngspice placeholder/stub for the analog hard macro interface used by src/project.v.
* Replace the body with the extracted transistor-level SKY130 neuron subckt.
* Pin order mirrors the Verilog blackbox:
*   V U VD VC VGND VDPWR ACK REQ_N

.subckt izh_sky130_macro_vu_vd_vc V U VD VC VGND VDPWR ACK REQ_N
* TODO: replace with SKY130 transistor-level analog Izhikevich circuit.
.ends izh_sky130_macro_vu_vd_vc
