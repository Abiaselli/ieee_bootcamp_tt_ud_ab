#!/usr/bin/env python3
"""
generate_izh_from_netlist_gdsfactory.py

Netlist-aware GDSFactory starter generator for the Tiny Tapeout SKY130
analog Izhikevich neuron project.

This is a starting-point custom layout generator, not a signoff-quality analog
router. It parses the LTspice structural netlist (zvndigital.cir), maps the
ZVN3310A/ZVP3310A transistor instances onto one-finger SKY130-ish NFET/PFET
geometry, omits the capacitors so V and U can use external capacitance, routes
same-named nets with visible metal straps, and emits a TT pin-aligned GDS/LEF.

Default public pinout:
  ua[0]    = V / ISYN membrane node, external Cv access
  ua[1]    = U recovery node, external Cu/control access
  ua[2]    = VD recovery increment/reset bias
  ua[3]    = VC membrane reset bias
  ui_in[0] = ACK input to the analog reset/AER circuit
  uo_out[0]= REQ_N output from the analog reset/AER circuit
  VDPWR    = Tiny Tapeout 1.8 V rail used as the macro high rail
  VGND     = Tiny Tapeout ground rail used as the macro low rail

Typical run from a Tiny Tapeout analog repo:

  mkdir -p gds lef reports
  python3 scripts/generate_izh_from_netlist_gdsfactory.py \
    --def def/tt_analog_1x2.def \
    --netlist spice/zvndigital.cir \
    --top tt_um_abiaselli_UDIZH1 \
    --out-gds gds/tt_um_abiaselli_UDIZH1.gds \
    --out-lef lef/tt_um_abiaselli_UDIZH1.lef \
    --report reports/izh_layout_report.txt \
    --out-spice spice/izh_sky130_layout_start.spice

The default --size-mode ratio_scaled uses the 2022 paper's W/L values but scales
small dimensions up enough to satisfy the rough SKY130 1.8 V minimums used here
(W >= 0.42um, L >= 0.15um), preserving W/L ratios. Pass --size-mode paper for
literal paper dimensions, or --size-mode sky130_min to clamp W/L independently.

You still need to run Magic/KLayout DRC, LVS, and extraction, then iterate.
"""
from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# GDS layer/datatype pairs commonly used by SKY130. If your PDK tech file uses
# different aliases, keep the GDS numbers and fix display names in KLayout/Magic.
LAYER = {
    "pr_boundary": (235, 4),
    "nwell": (64, 20),
    "diff": (65, 20),
    "tap": (65, 44),
    "poly": (66, 20),
    "licon": (66, 44),
    "li1": (67, 20),
    "mcon": (67, 44),
    "met1": (68, 20),
    "met1_pin": (68, 16),
    "met1_label": (68, 5),
    "via": (68, 44),
    "met2": (69, 20),
    "met2_pin": (69, 16),
    "via2": (69, 44),
    "met3": (70, 20),
    "met3_pin": (70, 16),
    "via3": (70, 44),
    "met4": (71, 20),
    "met4_pin": (71, 16),
    "met4_label": (71, 5),
    "nsdm": (93, 44),
    "psdm": (94, 20),
    "npc": (95, 20),
}

TOP_DEFAULT = "tt_um_abiaselli_UDIZH1"
MACRO_NAME = "izh_sky130_macro_vu_vd_vc"

# Literal dimensions from the newest paper's Fig. 1 component-size table as
# previously mapped to the uploaded zvndigital.cir topology. Units are microns.
# The LTspice instance number does not exactly equal the paper M-number because
# the uploaded netlist orders the devices differently.
PAPER_SIZE_UM: Dict[str, Tuple[float, float]] = {
    "U1": (0.300, 0.125),  # NFET: N001 V VGND
    "U2": (0.300, 0.125),  # PFET: N001 N001 VDD
    "U3": (0.300, 0.125),  # PFET: V N001 VDD
    "U4": (0.400, 0.600),  # NFET: V U VGND
    "U5": (0.175, 0.350),  # NFET: V ACK VC
    "U6": (0.700, 0.150),  # NFET: U U VGND
    "U7": (0.650, 0.090),  # PFET: U N001 VDD
    "U8": (1.300, 0.125),  # PFET: U N002 VD
    "U9": (0.100, 0.100),  # PFET: N003 N005 N004
    "U10": (1.000, 0.100), # PFET: N005 V VDD
    "U11": (0.100, 0.250), # NFET: REQ N003 VGND
    "U12": (0.100, 0.100), # NFET: N005 V VGND
    "U13": (0.200, 0.100), # NFET: VGND N003 N006
    "U14": (0.100, 0.100), # NFET: N003 N005 VGND
    "U16": (0.100, 0.100), # NFET: N002 ACK N006
    "U17": (0.100, 0.100), # PFET: N004 ACK VDD
    "U18": (0.200, 0.100), # PFET: N002 ACK VDD (extra ACK PMOS in uploaded netlist)
    "U19": (0.200, 0.100), # PFET: REQ N003 VDD
}

# Reasonable starter minimum dimensions for the basic 1.8V SKY130 primitive FETs.
MIN_W_UM = 0.42
MIN_L_UM = 0.15

NET_ALIASES = {
    "Vdd": "VDPWR",
    "VDD": "VDPWR",
    "vdd": "VDPWR",
    "VPWR": "VDPWR",
    "Vgnd": "VGND",
    "VGnd": "VGND",
    "VGND": "VGND",
    "gnd": "VGND",
    "0": "VGND",
    "REQ": "REQ_N",
    "Req": "REQ_N",
    "Vd": "VD",
    "VD": "VD",
    "Vc": "VC",
    "VC": "VC",
}

PUBLIC_PIN_NETS = {
    "ua[0]": "V",
    "ua[1]": "U",
    "ua[2]": "VD",
    "ua[3]": "VC",
    "ui_in[0]": "ACK",
    "uo_out[0]": "REQ_N",
}

UNUSED_DIGITAL_OUTPUT_PREFIXES = ("uo_out[", "uio_out[", "uio_oe[")
USED_DIGITAL_OUTPUTS = {"uo_out[0]"}

@dataclass
class Pin:
    name: str
    direction: str
    cx: float
    cy: float
    llx: float
    lly: float
    urx: float
    ury: float
    layer_name: str = "met4"

    @property
    def bbox(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        return ((self.cx + self.llx, self.cy + self.lly), (self.cx + self.urx, self.cy + self.ury))

    @property
    def center(self) -> Tuple[float, float]:
        return (self.cx, self.cy)

@dataclass
class DefTemplate:
    die: Tuple[float, float, float, float]
    pins: Dict[str, Pin]

@dataclass
class Device:
    inst: str
    mos_name: str
    kind: str      # nfet or pfet
    d: str
    g: str
    s: str
    b: str
    paper_w: float
    paper_l: float
    w: float
    l: float
    nf: int = 1

@dataclass
class CapIgnored:
    name: str
    n1: str
    n2: str
    value: str


def canonical_net(name: str) -> str:
    return NET_ALIASES.get(name, name)


def parse_def(path: Path) -> DefTemplate:
    text = path.read_text()
    units_m = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", text)
    dbu = float(units_m.group(1)) if units_m else 1000.0
    die_m = re.search(
        r"DIEAREA\s*\(\s*([-0-9]+)\s+([-0-9]+)\s*\)\s*\(\s*([-0-9]+)\s+([-0-9]+)\s*\)",
        text,
    )
    if not die_m:
        raise ValueError(f"Could not find DIEAREA in {path}")
    die = tuple(float(v) / dbu for v in die_m.groups())  # type: ignore[assignment]

    pins: Dict[str, Pin] = {}
    pins_block = re.search(r"PINS\s+\d+\s*;(.*?)END\s+PINS", text, flags=re.S)
    if not pins_block:
        raise ValueError(f"Could not find PINS block in {path}")
    chunks = re.split(r"\n\s*-\s+", pins_block.group(1))
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("-"):
            chunk = chunk[1:].strip()
        name_m = re.match(r"([^\s]+)", chunk)
        if not name_m:
            continue
        name = name_m.group(1)
        direction_m = re.search(r"\+\s+DIRECTION\s+(\w+)", chunk)
        layer_m = re.search(
            r"\+\s+LAYER\s+(\w+)\s+\(\s*([-0-9]+)\s+([-0-9]+)\s*\)\s+\(\s*([-0-9]+)\s+([-0-9]+)\s*\)",
            chunk,
        )
        placed_m = re.search(r"\+\s+PLACED\s+\(\s*([-0-9]+)\s+([-0-9]+)\s*\)", chunk)
        if not (direction_m and layer_m and placed_m):
            continue
        layer_name = layer_m.group(1)
        llx, lly, urx, ury = [float(x) / dbu for x in layer_m.groups()[1:]]
        cx, cy = [float(x) / dbu for x in placed_m.groups()]
        pins[name] = Pin(
            name=name,
            direction=direction_m.group(1),
            cx=cx,
            cy=cy,
            llx=llx,
            lly=lly,
            urx=urx,
            ury=ury,
            layer_name=layer_name,
        )
    return DefTemplate(die=die, pins=pins)


def choose_size(inst_key: str, mode: str) -> Tuple[float, float, float, float]:
    paper_w, paper_l = PAPER_SIZE_UM.get(inst_key, (MIN_W_UM, MIN_L_UM))
    if mode == "paper":
        return paper_w, paper_l, paper_w, paper_l
    if mode == "sky130_min":
        return paper_w, paper_l, max(paper_w, MIN_W_UM), max(paper_l, MIN_L_UM)
    if mode == "ratio_scaled":
        scale = max(1.0, MIN_W_UM / paper_w, MIN_L_UM / paper_l)
        return paper_w, paper_l, paper_w * scale, paper_l * scale
    raise ValueError(f"Unsupported --size-mode {mode!r}")


def parse_ltspice_netlist(path: Path, size_mode: str) -> Tuple[List[Device], List[CapIgnored]]:
    devices: List[Device] = []
    caps: List[CapIgnored] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("*") or line.startswith("."):
            continue
        # Strip LTspice semicolon comments.
        line = line.split(";", 1)[0].strip()
        toks = line.split()
        if not toks:
            continue
        head = toks[0]
        if head[0].upper() == "C" and len(toks) >= 4:
            caps.append(CapIgnored(head, canonical_net(toks[1]), canonical_net(toks[2]), toks[3]))
            continue
        if head[0].upper() != "X" or len(toks) < 5:
            continue
        # LTspice discrete-MOS subckt instance: X§U1 D G S ZVN3310A ZVN3310A
        model = toks[4]
        if not ("ZVN" in model.upper() or "ZVP" in model.upper()):
            continue
        d, g, s = [canonical_net(t) for t in toks[1:4]]
        b = s
        inst_m = re.search(r"U(\d+)", head, re.I)
        inst_key = f"U{inst_m.group(1)}" if inst_m else head.lstrip("X")
        kind = "nfet" if "ZVN" in model.upper() else "pfet"
        paper_w, paper_l, w, l = choose_size(inst_key, size_mode)
        devices.append(
            Device(
                inst=head,
                mos_name="M" + inst_key,
                kind=kind,
                d=d,
                g=g,
                s=s,
                b=b,
                paper_w=paper_w,
                paper_l=paper_l,
                w=w,
                l=l,
                nf=1,
            )
        )
    if not devices:
        raise ValueError(f"No ZVN/ZVP transistor instances found in {path}")
    return devices, caps


def import_gdsfactory():
    try:
        import gdsfactory as gf  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "Could not import gdsfactory. In the Tiny Tapeout/SKY130 VM try:\n"
            "  python3 -m pip install --user gdsfactory\n"
            "or, if uv is available:\n"
            "  uv pip install gdsfactory\n\n"
            f"Original import error: {exc}"
        )
    return gf


def rect(c, x0: float, y0: float, x1: float, y1: float, layer: Tuple[int, int], label: Optional[str] = None):
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    c.add_polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer=layer)
    if label:
        c.add_label(label, position=((x0 + x1) / 2, (y0 + y1) / 2), layer=LAYER["met1_label"])


def metal_rect(c, p0: Tuple[float, float], p1: Tuple[float, float], width: float, layer: Tuple[int, int]):
    x0, y0 = p0
    x1, y1 = p1
    if abs(x1 - x0) >= abs(y1 - y0):
        rect(c, min(x0, x1), y0 - width / 2, max(x0, x1), y0 + width / 2, layer)
    else:
        rect(c, x0 - width / 2, min(y0, y1), x0 + width / 2, max(y0, y1), layer)


def label(c, text: str, pos: Tuple[float, float], layer: Tuple[int, int] = LAYER["met4_label"]):
    c.add_label(text, position=pos, layer=layer)


def draw_via_stack(c, x: float, y: float, size: float = 0.28):
    # Simplified via stack marker. Verify/replace with PDK via arrays before tapeout.
    rect(c, x - size / 2, y - size / 2, x + size / 2, y + size / 2, LAYER["via"])
    rect(c, x - size / 2, y - size / 2, x + size / 2, y + size / 2, LAYER["via2"])
    rect(c, x - size / 2, y - size / 2, x + size / 2, y + size / 2, LAYER["via3"])


def draw_mos(c, dev: Device, x: float, y: float) -> Dict[str, Tuple[float, float]]:
    """Draw a one-finger schematic-sized MOS placeholder and return terminal coords.

    This is intentionally simple: active + poly + implant + met1 landing pads.
    It should be used as an editable starting geometry, not final signoff layout.
    """
    # Enlarge landing structure enough for labels/routing even for tiny paper devices.
    contact = 0.22
    sd = 0.55
    gate_ext = 0.42
    w = max(dev.w, 0.42)
    l = max(dev.l, 0.15)
    active_len = 2 * sd + l
    ax0, ax1 = x - active_len / 2, x + active_len / 2
    ay0, ay1 = y - w / 2, y + w / 2

    # Well/implant regions.
    if dev.kind == "pfet":
        rect(c, ax0 - 0.7, ay0 - 0.7, ax1 + 0.7, ay1 + 0.7, LAYER["nwell"])
        rect(c, ax0 - 0.25, ay0 - 0.25, ax1 + 0.25, ay1 + 0.25, LAYER["psdm"])
    else:
        rect(c, ax0 - 0.25, ay0 - 0.25, ax1 + 0.25, ay1 + 0.25, LAYER["nsdm"])

    # Diffusion and gate.
    rect(c, ax0, ay0, ax1, ay1, LAYER["diff"])
    rect(c, x - l / 2, ay0 - gate_ext, x + l / 2, ay1 + gate_ext, LAYER["poly"])

    # Source/drain contacts and M1 landing pads.
    dpos = (ax0 + sd * 0.42, y)
    spos = (ax1 - sd * 0.42, y)
    gpos = (x, ay1 + 0.95)
    bpos = (spos[0], ay0 - 0.95)

    for px, py, net, term in [
        (dpos[0], dpos[1], dev.d, "D"),
        (spos[0], spos[1], dev.s, "S"),
    ]:
        rect(c, px - 0.20, py - 0.20, px + 0.20, py + 0.20, LAYER["licon"])
        rect(c, px - 0.25, py - 0.25, px + 0.25, py + 0.25, LAYER["li1"])
        rect(c, px - 0.28, py - 0.28, px + 0.28, py + 0.28, LAYER["mcon"])
        rect(c, px - 0.42, py - 0.28, px + 0.42, py + 0.28, LAYER["met1"], f"{dev.mos_name}.{term}:{net}")
        label(c, net, (px, py), LAYER["met1_label"])

    # Gate landing. This is not a precise poly-contact implementation; it marks
    # and routes the gate terminal. Replace with a DRC-clean poly-contact stack.
    rect(c, gpos[0] - 0.20, gpos[1] - 0.20, gpos[0] + 0.20, gpos[1] + 0.20, LAYER["li1"])
    rect(c, gpos[0] - 0.28, gpos[1] - 0.28, gpos[0] + 0.28, gpos[1] + 0.28, LAYER["mcon"])
    rect(c, gpos[0] - 0.42, gpos[1] - 0.28, gpos[0] + 0.42, gpos[1] + 0.28, LAYER["met1"], f"{dev.mos_name}.G:{dev.g}")
    label(c, dev.g, gpos, LAYER["met1_label"])

    # Body marker. For one-finger starter cells, tie body to source net by label.
    if dev.kind == "pfet":
        rect(c, bpos[0] - 0.35, bpos[1] - 0.20, bpos[0] + 0.35, bpos[1] + 0.20, LAYER["tap"])
        rect(c, bpos[0] - 0.42, bpos[1] - 0.26, bpos[0] + 0.42, bpos[1] + 0.26, LAYER["met1"], f"{dev.mos_name}.B:{dev.b}")
    else:
        rect(c, bpos[0] - 0.35, bpos[1] - 0.20, bpos[0] + 0.35, bpos[1] + 0.20, LAYER["tap"])
        rect(c, bpos[0] - 0.42, bpos[1] - 0.26, bpos[0] + 0.42, bpos[1] + 0.26, LAYER["met1"], f"{dev.mos_name}.B:{dev.b}")
    label(c, f"{dev.mos_name} {dev.kind}\nW={dev.w:.3g} L={dev.l:.3g} nf=1", (x, ay0 - 1.8), LAYER["met1_label"])

    return {"D": dpos, "G": gpos, "S": spos, "B": bpos}


def device_positions(devices: List[Device], die: Tuple[float, float, float, float]) -> Dict[str, Tuple[float, float]]:
    """Functional-block placement: membrane/recovery below, AER/reset above."""
    x0, y0, x1, y1 = die
    usable_w = x1 - x0
    # Keep away from bottom analog pins and top digital pins.
    left = x0 + 14
    top_y = y1 - 52
    mid_y = y0 + 98
    low_y = y0 + 53
    dx = 18

    order_rows = {
        "low": ["U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8"],
        "mid": ["U9", "U10", "U11", "U12", "U13", "U14"],
        "top": ["U16", "U17", "U18", "U19"],
    }
    pos: Dict[str, Tuple[float, float]] = {}
    for row_name, keys in order_rows.items():
        y = {"low": low_y, "mid": mid_y, "top": top_y}[row_name]
        for i, key in enumerate(keys):
            pos[key] = (left + i * dx, y)
    # If anything unexpected appears, place it on a spare diagonal.
    for i, d in enumerate(devices):
        key = re.search(r"U(\d+)", d.inst, re.I)
        k = f"U{key.group(1)}" if key else d.inst
        if k not in pos:
            pos[k] = (left + (i % 6) * dx, y0 + 135 + (i // 6) * 18)
    return pos


def collect_nets(devices: List[Device]) -> List[str]:
    nets = set()
    for d in devices:
        nets.update([d.d, d.g, d.s, d.b])
    # Deterministic order: public/important nets first.
    preferred = ["VGND", "VDPWR", "V", "U", "VD", "VC", "ACK", "REQ_N", "N001", "N002", "N003", "N004", "N005", "N006"]
    return [n for n in preferred if n in nets] + sorted(nets.difference(preferred))


def make_tracks(nets: List[str], die: Tuple[float, float, float, float]) -> Dict[str, float]:
    _x0, y0, _x1, y1 = die
    # Horizontal routing tracks in the open core. Keep away from pins and devices.
    base = y0 + 20
    pitch = 5.0
    tracks: Dict[str, float] = {}
    for i, net in enumerate(nets):
        tracks[net] = base + i * pitch
    return tracks


def route_to_track(c, start: Tuple[float, float], track_y: float, net: str, x_escape: Optional[float] = None):
    x, y = start
    if x_escape is None:
        x_escape = x
    # vertical to track on met2, with a small M1/M2 via marker at start.
    draw_via_stack(c, x, y)
    metal_rect(c, (x, y), (x_escape, y), 0.34, LAYER["met2"])
    metal_rect(c, (x_escape, y), (x_escape, track_y), 0.34, LAYER["met2"])
    label(c, net, (x_escape + 0.35, track_y + 0.35), LAYER["met4_label"])


def add_tt_pins_and_boundary(c, template: DefTemplate, top_name: str):
    x0, y0, x1, y1 = template.die
    rect(c, x0, y0, x1, y1, LAYER["pr_boundary"], None)
    label(c, top_name, ((x0 + x1) / 2, y1 - 8), LAYER["met4_label"])
    for p in template.pins.values():
        layer = LAYER["met4_pin"] if p.layer_name == "met4" else LAYER.get(p.layer_name, LAYER["met4_pin"])
        (a, b) = p.bbox
        rect(c, a[0], a[1], b[0], b[1], layer, None)
        label(c, p.name, p.center, LAYER["met4_label"])


def add_top_rails(c, die: Tuple[float, float, float, float], tracks: Dict[str, float]):
    x0, y0, x1, y1 = die
    # Wide-ish internal rails. TT top-level power grid is not implemented here;
    # these are macro internal straps tied by label/geometry to VGND/VDPWR.
    if "VGND" in tracks:
        yg = tracks["VGND"]
        rect(c, x0 + 5, yg - 0.55, x1 - 5, yg + 0.55, LAYER["met4"], "VGND")
        label(c, "VGND", (x0 + 8, yg + 1.2), LAYER["met4_label"])
    if "VDPWR" in tracks:
        yp = tracks["VDPWR"]
        rect(c, x0 + 5, yp - 0.55, x1 - 5, yp + 0.55, LAYER["met4"], "VDPWR/VPWR")
        label(c, "VDPWR", (x0 + 8, yp + 1.2), LAYER["met4_label"])


def route_public_pins(c, template: DefTemplate, tracks: Dict[str, float], die: Tuple[float, float, float, float]):
    # Route ua[0:3], ui_in[0], uo_out[0] to their net tracks.
    for pin_name, net in PUBLIC_PIN_NETS.items():
        if pin_name not in template.pins or net not in tracks:
            continue
        p = template.pins[pin_name]
        x, y = p.center
        ty = tracks[net]
        metal_rect(c, (x, y), (x, ty), 0.60, LAYER["met4"])
        draw_via_stack(c, x, ty)
        label(c, f"{pin_name}:{net}", (x + 1.0, (y + ty) / 2), LAYER["met4_label"])

    # Tie unused digital outputs / output enables to VGND track.
    if "VGND" not in tracks:
        return
    for p in template.pins.values():
        is_unused_out = False
        if p.name.startswith("uo_out[") and p.name not in USED_DIGITAL_OUTPUTS:
            is_unused_out = True
        elif p.name.startswith("uio_out[") or p.name.startswith("uio_oe["):
            is_unused_out = True
        if is_unused_out:
            x, y = p.center
            ty = tracks["VGND"]
            metal_rect(c, (x, y), (x, ty), 0.32, LAYER["met4"])
            draw_via_stack(c, x, ty)


def draw_routing(c, devices: List[Device], term_pos: Dict[str, Dict[str, Tuple[float, float]]], tracks: Dict[str, float], die: Tuple[float, float, float, float]):
    x0, _y0, x1, _y1 = die
    # Horizontal tracks.
    for net, y in tracks.items():
        layer = LAYER["met4"] if net in {"VGND", "VDPWR"} else LAYER["met2"]
        width = 0.50 if net in {"VGND", "VDPWR", "V", "U"} else 0.32
        metal_rect(c, (x0 + 6, y), (x1 - 6, y), width, layer)
        label(c, net, (x1 - 12, y + 0.7), LAYER["met4_label"])

    for dev in devices:
        dpos = term_pos[dev.mos_name]
        for term, net in [("D", dev.d), ("G", dev.g), ("S", dev.s), ("B", dev.b)]:
            if net not in tracks:
                continue
            route_to_track(c, dpos[term], tracks[net], net)


def write_lef(path: Path, top: str, template: DefTemplate):
    """
    Write an abstract LEF, not a physical layout.

    This intentionally keeps the TT template pin rectangles, because the top-level
    shuttle integration wants the macro pins at the template locations.  The
    internal MOS/diff/poly geometries live only in the GDS.  LEF only needs:
      * the macro size,
      * the public port rectangles,
      * routing obstructions so the top-level router does not run through the
        analog layout.

    If the LEF looks similar to the DEF template, that is expected.  What should
    differ from a DEF is the file structure: LEF has MACRO/PIN/OBS sections, not
    ROW/TRACKS/NETS/COMPONENTS sections.
    """
    x0, y0, x1, y1 = template.die
    w = x1 - x0
    h = y1 - y0

    # Keep OBS away from the top/bottom template pin rows so pins remain visible
    # and accessible.  Units are microns, matching the DEF parser conversion.
    obs_margin_x = 3.0
    obs_margin_bottom = 4.0
    obs_margin_top = 4.0
    ox0, oy0 = obs_margin_x, obs_margin_bottom
    ox1, oy1 = max(obs_margin_x, w - obs_margin_x), max(obs_margin_bottom, h - obs_margin_top)

    lines: List[str] = []
    lines.append("VERSION 5.8 ;")
    lines.append("BUSBITCHARS \"[]\" ;")
    lines.append("DIVIDERCHAR \"/\" ;")
    lines.append("UNITS")
    lines.append("  DATABASE MICRONS 1000 ;")
    lines.append("END UNITS")
    lines.append(f"MACRO {top}")
    lines.append("  CLASS BLOCK ;")
    lines.append("  FOREIGN {top} 0.000 0.000 ;".format(top=top))
    lines.append("  ORIGIN 0.000 0.000 ;")
    lines.append(f"  SIZE {w:.3f} BY {h:.3f} ;")
    lines.append("  SYMMETRY X Y R90 ;")

    # Include all TT pins, not just the user-visible pins.  The Verilog wrapper
    # still has the full TT analog-template port list, so the abstract should
    # preserve the top-level pin contract.
    for p in template.pins.values():
        direction = p.direction.upper()
        use = "SIGNAL"
        if p.name in {"VGND", "VNB"}:
            use = "GROUND"
        elif p.name in {"VPWR", "VDPWR", "VAPWR", "VPB"}:
            use = "POWER"
        lines.append(f"  PIN {p.name}")
        lines.append(f"    DIRECTION {direction} ;")
        lines.append(f"    USE {use} ;")
        lines.append("    PORT")
        (a, b) = p.bbox
        # The TT templates place the boundary pins on met4.
        lines.append("      LAYER met4 ;")
        lines.append(f"        RECT {a[0]:.3f} {a[1]:.3f} {b[0]:.3f} {b[1]:.3f} ;")
        lines.append("    END")
        lines.append(f"  END {p.name}")

    # Obstructions: block the interior on the routing layers used by this
    # starter layout.  Do not include met5; TT reserves met5 for the top-level
    # power grid.  Do not include diffusion/poly in LEF because LEF abstracts
    # routing blockages, not device-level mask detail.
    lines.append("  OBS")
    for layer in ["li1", "met1", "met2", "met3", "met4"]:
        lines.append(f"    LAYER {layer} ;")
        lines.append(f"      RECT {ox0:.3f} {oy0:.3f} {ox1:.3f} {oy1:.3f} ;")
    lines.append("  END")
    lines.append(f"END {top}")
    lines.append("END LIBRARY")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def write_spice(path: Path, devices: List[Device]):
    lines = [
        "* SKY130 starter MOS netlist generated from zvndigital.cir",
        "* Capacitors omitted intentionally: use external Cv on V and Cu on U.",
        ".subckt izh_sky130_macro_vu_vd_vc V U VD VC ACK REQ_N VDPWR VGND",
    ]
    for d in devices:
        model = "sky130_fd_pr__nfet_01v8" if d.kind == "nfet" else "sky130_fd_pr__pfet_01v8"
        lines.append(
            f"{d.mos_name} {d.d} {d.g} {d.s} {d.b} {model} w={d.w:.6g}u l={d.l:.6g}u nf=1"
        )
    lines.append(".ends izh_sky130_macro_vu_vd_vc")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def write_report(path: Path, devices: List[Device], caps: List[CapIgnored], tracks: Dict[str, float], size_mode: str, template: DefTemplate):
    lines: List[str] = []
    lines.append("Izhikevich SKY130 netlist-aware starter layout report")
    lines.append("=====================================================")
    lines.append(f"size_mode: {size_mode}")
    lines.append(f"die: {template.die}")
    lines.append("")
    lines.append("Devices drawn as one-finger starter MOS geometries:")
    lines.append("inst,mos,type,D,G,S,B,paper_W_um,paper_L_um,draw_W_um,draw_L_um,nf")
    for d in devices:
        lines.append(f"{d.inst},{d.mos_name},{d.kind},{d.d},{d.g},{d.s},{d.b},{d.paper_w},{d.paper_l},{d.w},{d.l},{d.nf}")
    lines.append("")
    lines.append("Capacitors intentionally omitted / externalized:")
    for cap in caps:
        lines.append(f"{cap.name}: {cap.n1} to {cap.n2}, original LTspice value {cap.value}")
    lines.append("")
    lines.append("Net tracks:")
    for n, y in tracks.items():
        lines.append(f"{n}: y={y:.3f}um")
    lines.append("")
    lines.append("Next checks:")
    lines.append("1. Open GDS in KLayout/Magic and visually inspect every same-name net.")
    lines.append("2. Replace simplified via markers and poly contacts with DRC-clean SKY130 structures.")
    lines.append("3. Add proper nwell/pwell/substrate ties and guard rings around the analog block.")
    lines.append("4. Run DRC, extract, and LVS against the generated starter SPICE.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def build_layout(args):
    gf = import_gdsfactory()
    template = parse_def(Path(args.def_file))
    devices, caps = parse_ltspice_netlist(Path(args.netlist), args.size_mode)
    nets = collect_nets(devices)
    tracks = make_tracks(nets, template.die)

    c = gf.Component(args.top)
    add_tt_pins_and_boundary(c, template, args.top)
    add_top_rails(c, template.die, tracks)

    pos = device_positions(devices, template.die)
    term_pos: Dict[str, Dict[str, Tuple[float, float]]] = {}
    for d in devices:
        key_m = re.search(r"U(\d+)", d.inst, re.I)
        key = f"U{key_m.group(1)}" if key_m else d.inst
        x, y = pos[key]
        term_pos[d.mos_name] = draw_mos(c, d, x, y)

    draw_routing(c, devices, term_pos, tracks, template.die)
    route_public_pins(c, template, tracks, template.die)

    # Add warning labels for external capacitors.
    label(c, "EXTERNAL CAPS: connect Cv from V=ua[0] to VGND; Cu from U=ua[1] to VGND", (template.die[0] + 12, template.die[3] - 15), LAYER["met4_label"])
    label(c, "STARTER GEOMETRY: run DRC/LVS and replace simplified contacts/vias before tapeout", (template.die[0] + 12, template.die[3] - 20), LAYER["met4_label"])

    out_gds = Path(args.out_gds)
    out_gds.parent.mkdir(parents=True, exist_ok=True)
    c.write_gds(out_gds)
    write_lef(Path(args.out_lef), args.top, template)
    if args.out_spice:
        write_spice(Path(args.out_spice), devices)
    if args.report:
        write_report(Path(args.report), devices, caps, tracks, args.size_mode, template)


def main():
    parser = argparse.ArgumentParser(description="Generate a netlist-aware SKY130/Tiny Tapeout starter GDS from zvndigital.cir")
    parser.add_argument("--def", dest="def_file", required=True, help="Tiny Tapeout DEF template, e.g. def/tt_analog_1x2.def")
    parser.add_argument("--netlist", required=True, help="Structural LTspice netlist, e.g. spice/zvndigital.cir")
    parser.add_argument("--top", default=TOP_DEFAULT, help="Top GDS/LEF cell name; should match info.yaml top_module")
    parser.add_argument("--out-gds", required=True, help="Output GDS path")
    parser.add_argument("--out-lef", required=True, help="Output LEF path")
    parser.add_argument("--out-spice", default="", help="Optional generated SKY130 starter SPICE/CDL path")
    parser.add_argument("--report", default="", help="Optional connectivity/sizing report path")
    parser.add_argument(
        "--size-mode",
        choices=["ratio_scaled", "sky130_min", "paper"],
        default="ratio_scaled",
        help=(
            "ratio_scaled: preserve paper W/L while meeting rough SKY130 minima; "
            "sky130_min: clamp W and L independently; paper: literal paper sizes"
        ),
    )
    args = parser.parse_args()
    build_layout(args)


if __name__ == "__main__":
    main()
