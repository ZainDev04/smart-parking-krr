"""Report figures drawn at their printed size.

Mermaid lays these diagrams out far wider than an A4 text column, so once
Word shrinks them to 16 cm the text drops to 3-4 pt. These figures are drawn
directly with Pillow on a fixed layout instead: every box, arrow and label is
placed in centimetres on a canvas at most 16 cm wide, and the PNG carries a
300 dpi tag so the report inserts it at 1:1 scale. Body text in every figure
is 8 pt.

Node and slot content still comes from the code (frames, semantic network,
script), so renaming a slot or a class changes the figure on the next build.
Only the positions are fixed here, and every builder checks that it placed
every node the code produced.

The Mermaid sources in docs/diagrams stay as they are for viewing on GitHub.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from krr.frames.ontology import build_frames  # noqa: E402
from krr.frames.scripts import PARKING_SESSION  # noqa: E402
from krr.semantic_net.network import (build_class_network,  # noqa: E402
                                      build_instance_network)

OUT = ROOT / "docs" / "figures"
DPI = 300
SS = 2                      # draw at 2x and downsample for smooth lines
PX = DPI * SS / 2.54        # canvas pixels per cm

INK = "#0f172a"
LINE = "#334155"
MUTED = "#475569"
FAIL = "#b91c1c"
PALETTE = {
    "plain": ("#ffffff", "#475569"),
    "panel": ("#f1f5f9", "#94a3b8"),
    "class": ("#dbeafe", "#1e40af"),
    "value": ("#fef3c7", "#b45309"),
    "instance": ("#dcfce7", "#15803d"),
    "store": ("#ede9fe", "#6d28d9"),
    "out": ("#fee2e2", "#b91c1c"),
}

FONT_FILES = {
    "regular": ["arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
    "bold": ["arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "mono": ["consola.ttf", "LiberationMono-Regular.ttf", "DejaVuSansMono.ttf"],
}
FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/liberation"),
             Path("/usr/share/fonts/truetype/dejavu"), Path("/Library/Fonts"),
             Path("/System/Library/Fonts/Supplemental")]
_font_cache: dict[tuple[str, float], ImageFont.FreeTypeFont] = {}


def font(face: str, pt: float) -> ImageFont.FreeTypeFont:
    key = (face, pt)
    if key not in _font_cache:
        for name in FONT_FILES[face]:
            for folder in FONT_DIRS:
                if (folder / name).exists():
                    _font_cache[key] = ImageFont.truetype(str(folder / name),
                                                          round(pt / 72 * DPI * SS))
                    break
            if key in _font_cache:
                break
        else:
            raise FileNotFoundError(f"no font found for {face}: install Arial or Liberation")
    return _font_cache[key]


# text styles: face, size in pt, colour
STYLE = {
    "title": ("bold", 8.5, INK),
    "body": ("regular", 8, INK),
    "note": ("regular", 7.5, MUTED),
    "mono": ("mono", 7.5, INK),
    "label": ("regular", 7.5, LINE),
    "head": ("bold", 8.5, INK),
}


def line_height(style: str) -> float:
    return STYLE[style][1] * 1.28 / 72 * 2.54


def text_width(text: str, style: str) -> float:
    face, pt, _ = STYLE[style]
    return font(face, pt).getlength(text) / PX


def wrap(text: str, style: str, width: float) -> list[str]:
    if text_width(text, style) <= width or " " not in text:
        return [text]
    out, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}".strip()
        if cur and text_width(trial, style) > width:
            out.append(cur)
            cur = word
        else:
            cur = trial
    out.append(cur)
    return out


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float
    shape: str = "rect"

    @property
    def r(self) -> float:
        return self.x + self.w

    @property
    def b(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def border_toward(self, px: float, py: float) -> tuple[float, float]:
        """Point where the ray from the centre toward (px, py) leaves the box."""
        dx, dy = px - self.cx, py - self.cy
        if dx == 0 and dy == 0:
            return self.cx, self.cy
        if self.shape == "diamond":
            t = 1 / (abs(dx) / (self.w / 2) + abs(dy) / (self.h / 2))
        else:
            tx = (self.w / 2) / abs(dx) if dx else math.inf
            ty = (self.h / 2) / abs(dy) if dy else math.inf
            t = min(tx, ty)
        return self.cx + dx * t, self.cy + dy * t


class Figure:
    def __init__(self, width: float, height: float) -> None:
        self.width, self.height = width, height
        self.img = Image.new("RGB", (round(width * PX), round(height * PX)), "white")
        self.draw = ImageDraw.Draw(self.img)
        self.boxes: dict[str, Box] = {}

    # ----- primitives ----------------------------------------------------
    def p(self, x: float, y: float) -> tuple[float, float]:
        return x * PX, y * PX

    def text(self, x: float, y: float, text: str, style: str = "body",
             anchor: str = "la", color: str | None = None) -> None:
        face, pt, col = STYLE[style]
        self.draw.text(self.p(x, y), text, font=font(face, pt), fill=color or col,
                       anchor=anchor)

    def label(self, x: float, y: float, text: str, style: str = "label",
              anchor: str = "mm", bg: bool = True, color: str | None = None) -> None:
        """A short label centred (by default) on (x, y), on a white patch."""
        lines = text.split("\n")
        lh = line_height(style)
        w = max(text_width(t, style) for t in lines)
        h = lh * len(lines)
        hx = {"l": 0, "m": 0.5, "r": 1}[anchor[0]]
        vy = {"t": 0, "m": 0.5, "b": 1}[anchor[1]]
        left, top = x - w * hx, y - h * vy
        if bg:
            pad = 0.04
            self.draw.rectangle([*self.p(left - pad, top - pad / 2),
                                 *self.p(left + w + pad, top + h + pad / 2)], fill="white")
        for i, t in enumerate(lines):
            self.text(left + w / 2, top + lh * (i + 0.5), t, style, "mm", color)

    def shape(self, b: Box, fill: str, stroke: str, width: float = 0.022,
              dashed: bool = False) -> None:
        d, lw = self.draw, max(1, round(width * PX))
        x0, y0, x1, y1 = *self.p(b.x, b.y), *self.p(b.r, b.b)
        if b.shape == "diamond":
            pts = [self.p(b.cx, b.y), self.p(b.r, b.cy), self.p(b.cx, b.b), self.p(b.x, b.cy)]
            d.polygon(pts, fill=fill, outline=stroke, width=lw)
        elif b.shape == "pill":
            d.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) / 2, fill=fill,
                                outline=stroke, width=lw)
        elif b.shape == "round":
            d.rounded_rectangle([x0, y0, x1, y1], radius=0.14 * PX, fill=fill,
                                outline=stroke, width=lw)
        elif b.shape == "cyl":
            e = 0.12 * PX
            d.rectangle([x0, y0 + e, x1, y1 - e], fill=fill)
            d.ellipse([x0, y1 - 2 * e, x1, y1], fill=fill, outline=stroke, width=lw)
            d.rectangle([x0 + lw, y0 + e, x1 - lw, y1 - e], fill=fill)
            d.line([x0, y0 + e, x0, y1 - e], fill=stroke, width=lw)
            d.line([x1, y0 + e, x1, y1 - e], fill=stroke, width=lw)
            d.ellipse([x0, y0, x1, y0 + 2 * e], fill=fill, outline=stroke, width=lw)
        else:
            d.rectangle([x0, y0, x1, y1], fill=fill, outline=stroke, width=lw)

    def node(self, key: str, x: float, y: float, lines: list[tuple[str, str]], *,
             w: float | None = None, kind: str = "plain", shape: str = "rect",
             pad: float = 0.1, center: bool = True, h: float | None = None,
             header: bool = False) -> Box:
        """Box at top-left (x, y). lines = [(text, style)]. If w is None the box
        fits its text. header=True draws the first line as a frame title band."""
        padx = 0.14 if shape != "pill" else 0.22
        if w is None:
            w = max(text_width(t, s) for t, s in lines) + 2 * padx
        rows: list[tuple[str, str]] = []
        for t, s in lines:
            rows += [(part, s) for part in wrap(t, s, w - 2 * padx)]
        inner = sum(line_height(s) for _, s in rows)
        extra = 0.08 if header and len(rows) > 1 else 0
        need = inner + 2 * pad + extra + (0.2 if shape == "cyl" else 0)
        h = need if h is None else max(h, need)
        b = Box(x, y, w, h, shape)
        fill, stroke = PALETTE[kind]
        self.shape(b, fill, stroke)
        top = y + (h - inner - extra) / 2 + (0.06 if shape == "cyl" else 0)
        for i, (t, s) in enumerate(rows):
            lh = line_height(s)
            if center or (header and i == 0):
                self.text(x + w / 2, top + lh / 2, t, s, "mm")
            else:
                self.text(x + padx, top + lh / 2, t, s, "lm")
            top += lh
            if header and i == 0 and len(rows) > 1:
                self.draw.line([self.p(x, top + 0.04), self.p(b.r, top + 0.04)],
                               fill=stroke, width=max(1, round(0.018 * PX)))
                top += extra
        self.boxes[key] = b
        return b

    def polyline(self, pts: list[tuple[float, float]], color: str = LINE,
                 width: float = 0.02, dashed: bool = False) -> None:
        lw = max(1, round(width * PX))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if not dashed:
                self.draw.line([self.p(x0, y0), self.p(x1, y1)], fill=color, width=lw)
                continue
            length = math.hypot(x1 - x0, y1 - y0)
            dash, gap = 0.12, 0.08
            t = 0.0
            while t < length:
                t2 = min(t + dash, length)
                a = (x0 + (x1 - x0) * t / length, y0 + (y1 - y0) * t / length)
                c = (x0 + (x1 - x0) * t2 / length, y0 + (y1 - y0) * t2 / length)
                self.draw.line([self.p(*a), self.p(*c)], fill=color, width=lw)
                t = t2 + gap
        # round joints
        r = lw / 2
        for x, y in pts[1:-1]:
            cx, cy = self.p(x, y)
            self.draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    def head(self, tip: tuple[float, float], frm: tuple[float, float], kind: str,
             color: str = LINE) -> tuple[float, float]:
        """Draw an arrow head at tip; return the point where the shaft should end."""
        ang = math.atan2(tip[1] - frm[1], tip[0] - frm[0])
        if kind == "triangle":
            ln, half = 0.26, 0.15
        else:
            ln, half = 0.2, 0.085
        bx, by = tip[0] - ln * math.cos(ang), tip[1] - ln * math.sin(ang)
        nx, ny = -math.sin(ang) * half, math.cos(ang) * half
        pts = [self.p(*tip), self.p(bx + nx, by + ny), self.p(bx - nx, by - ny)]
        if kind == "triangle":
            self.draw.polygon(pts, fill="white", outline=color,
                              width=max(1, round(0.02 * PX)))
        else:
            self.draw.polygon(pts, fill=color)
        return bx, by

    def arrow(self, pts: list[tuple[float, float]], head: str = "arrow",
              color: str = LINE, dashed: bool = False, both: bool = False,
              label: str | None = None, at: tuple[float, float] | None = None,
              anchor: str = "mm", style: str = "label") -> None:
        pts = list(pts)
        if head != "none":
            pts[-1] = self.head(pts[-1], pts[-2], head, color)
        if both:
            pts[0] = self.head(pts[0], pts[1], "arrow", color)
        self.polyline(pts, color, dashed=dashed)
        if label:
            if at is None:
                segs = list(zip(pts, pts[1:]))
                (x0, y0), (x1, y1) = max(segs, key=lambda s: math.dist(*s))
                at = ((x0 + x1) / 2, (y0 + y1) / 2)
            self.label(*at, label, style, anchor)

    def link(self, a: str, b: str, label: str | None = None, *, head: str = "arrow",
             dashed: bool = False, color: str = LINE, at: float = 0.5,
             offset: tuple[float, float] = (0, 0)) -> None:
        """Straight arrow between two boxes, border to border."""
        A, B = self.boxes[a], self.boxes[b]
        p0 = A.border_toward(B.cx, B.cy)
        p1 = B.border_toward(A.cx, A.cy)
        pos, anchor = None, "mm"
        if label:
            pos = (p0[0] + (p1[0] - p0[0]) * at + offset[0],
                   p0[1] + (p1[1] - p0[1]) * at + offset[1])
            dx, dy = abs(p1[0] - p0[0]), abs(p1[1] - p0[1])
            # keep short straight shafts visible: label beside a vertical edge,
            # above a horizontal one, on the line only for diagonals
            if dx < 0.25 * dy:
                pos, anchor = (pos[0] + 0.09, pos[1]), "lm"
            elif dy < 0.25 * dx:
                pos, anchor = (pos[0], pos[1] - 0.05), "mb"
        self.arrow([p0, p1], head, color, dashed, label=label, at=pos, anchor=anchor)

    def save(self, name: str) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        img = self.img.resize((round(self.width * DPI / 2.54), round(self.height * DPI / 2.54)),
                              Image.LANCZOS)
        path = OUT / f"{name}.png"
        img.save(path, dpi=(DPI, DPI), optimize=True)
        return path


def legend_item(fig: Figure, x: float, y: float, sample: str, text: str) -> None:
    """One legend row: a short line sample at (x, y) then its meaning."""
    if sample == "isa":
        fig.arrow([(x, y), (x + 0.8, y)], "triangle")
    elif sample == "slot":
        fig.arrow([(x, y), (x + 0.8, y)])
    elif sample == "dashed":
        fig.arrow([(x, y), (x + 0.8, y)], dashed=True, color="#15803d")
    fig.text(x + 0.95, y, text, "note", "lm")


# --------------------------------------------------------------------------------
# Figure: system architecture
# --------------------------------------------------------------------------------

def architecture() -> Path:
    cols = {
        "L1": ("1. Presentation", [("main.py", "command line"), ("app.py", "Streamlit UI")]),
        "L2": ("2. Inference engines", [("Forward chainer", "data-driven"),
                                        ("Backward chainer", "goal-driven"),
                                        ("Why-not explainer", None), ("DL reasoner", None),
                                        ("FOL model checker", None)]),
        "L3": ("3. Knowledge base", [("Facts", "frames + policy + context"),
                                     ("Horn rules R01-R28", "constraints IC1-IC7")]),
        "L5": ("5. Generated artefacts", [("Prolog program", None), ("OWL ontology", None),
                                          ("Trace sheets", None), ("Word report", None)]),
        "L4": ("4. Knowledge representation", [("Frames, facets, defaults", None),
                                               ("ParkingSession script", None),
                                               ("Semantic network", None), ("DL TBox", None),
                                               ("FOL statements", None)]),
    }
    colw, gap, padx, node_gap = 2.95, 1.33, 0.18, 0.14
    xs = [0.02, 0.02 + colw + gap, 0.02 + 2 * (colw + gap), 0.02 + 3 * (colw + gap)]
    fig = Figure(xs[3] + colw + 0.04, 12.0)

    def panel(key: str, x: float, y: float) -> Box:
        title, items = cols[key]
        # measure first, then draw panel behind the nodes
        heights = []
        for main, sub in items:
            lines = [(main, "title")] + ([(sub, "note")] if sub else [])
            h = sum(line_height(s) * len(wrap(t, s, colw - 2 * padx - 0.28)) for t, s in lines)
            heights.append(h + 0.16)
        head = line_height("head") * len(wrap(title, "head", colw - 0.2)) + 0.16
        total = head + sum(heights) + node_gap * (len(items) - 1) + 0.18
        box = Box(x, y, colw, total, "round")
        fig.shape(box, *PALETTE["panel"])
        ty = y + 0.1
        for t in wrap(title, "head", colw - 0.2):
            fig.text(x + colw / 2, ty + line_height("head") / 2, t, "head", "mm")
            ty += line_height("head")
        ny = y + head
        for i, (main, sub) in enumerate(items):
            lines = [(main, "title")] + ([(sub, "note")] if sub else [])
            fig.node(f"{key}.{i}", x + padx, ny, lines, w=colw - 2 * padx, h=heights[i],
                     shape="round")
            ny += heights[i] + node_gap
        fig.boxes[key] = box
        return box

    l2 = panel("L2", xs[1], 0.02)
    l4 = panel("L4", xs[3], 0.02)
    l3 = panel("L3", xs[2], 0.02)
    l5 = panel("L5", xs[2], l3.b + 1.0)
    l1 = panel("L1", xs[0], 0.02)
    ya = l3.cy
    yq = min(ya, l1.b - 0.3)
    fig.arrow([(l1.r, yq), (l2.x, yq)], label="queries",
              at=((l1.r + l2.x) / 2, yq - 0.07), anchor="mb")
    fig.arrow([(l2.r, ya), (l3.x, ya)], label="reads", at=((l2.r + l3.x) / 2, ya - 0.07),
              anchor="mb")
    fig.arrow([(l4.x, ya), (l3.r, ya)], label="frames\nbecome\nfacts",
              at=((l4.x + l3.r) / 2, ya - 0.07), anchor="mb")
    fig.arrow([(l3.cx, l3.b), (l5.cx, l5.y)], label="exported to",
              at=(l3.cx + 0.12, (l3.b + l5.y) / 2), anchor="lm")
    bottom = max(l2.b, l4.b, l5.b) + 0.03
    fig.height = bottom
    fig.img = fig.img.crop((0, 0, fig.img.width, round(bottom * PX)))
    return fig.save("architecture")


# --------------------------------------------------------------------------------
# Figure: frame hierarchy
# --------------------------------------------------------------------------------

def frame_hierarchy() -> Path:
    fs = build_frames()
    classes = {f.name: f for f in fs.classes()}
    own, rel = {}, []
    for name, frame in classes.items():
        rows = []
        for slot in frame.slots.values():
            spec = fs.slot_specs(name)[slot.name]
            if spec.type.startswith("frame:"):
                many = " [many]" if spec.cardinality == "multiple" else ""
                rel.append((name, slot.name + many, spec.type.split(":", 1)[1]))
                continue
            text = slot.name
            if slot.default is not None:
                text += f" = {slot.default}"
            if spec.if_needed is not None:
                text += " (if-needed)"
            rows.append(text)
        own[name] = rows
    children = {n: [c for c, f in classes.items() if f.isa == n] for n in classes}
    targets = {n: [t for s, _, t in rel if s == n] for n in classes}

    col_b = ["Person", "Reservation", "ParkingSpace"]
    groups = [(r, children[r], [t for t in targets[r] if t not in col_b]) for r in
              ("Person", "ParkingSpace")]
    col_c = [n for _, kids, rels in groups for n in kids + rels]
    col_d = {n: children[n] + targets[n] for n in col_c if children[n] or targets[n]}
    placed = set(col_b) | set(col_c) | {x for v in col_d.values() for x in v}
    missing = set(classes) - placed
    assert not missing, f"frame_hierarchy layout does not place {missing}"

    def lines(n):
        return [(n, "title")] + [(r, "body") for r in own[n]]

    def width(n):
        return max(text_width(t, s) for t, s in lines(n)) + 0.3

    wb = max(width(n) for n in ("Person", "ParkingSpace"))
    wc = max(width(n) for n in col_c)
    wd = max(width(x) for v in col_d.values() for x in v)
    wd = min(wd, 3.75)
    rel_labels = [lab for s, lab, t in rel if s in ("Person", "ParkingSpace")]
    gap_bc = max(text_width(t, "label") for t in rel_labels) + 0.55
    gap_cd = 1.05
    xb, xc = 0.02, 0.02 + wb + gap_bc
    xd = xc + wc + gap_cd
    fig = Figure(xd + wd + 0.03, 20)

    # column C: stack, larger gap between the people group and the space group
    y = 0.02
    for gi, (root, kids, rels) in enumerate(groups):
        if gi:
            y += 0.35
        for n in kids + rels:
            b = fig.node(n, xc, y, lines(n), w=wc, center=False, header=True)
            y += b.h + 0.22
    height = y - 0.22 + 0.03

    # column D: centred on the anchor in column C
    for anchor, items in col_d.items():
        a = fig.boxes[anchor]
        hs = []
        for n in items:
            rows = []
            for t, s in lines(n):
                rows += wrap(t, s, wd - 0.28)
            hs.append(sum(line_height("body") for _ in rows) + 0.28)
        total = sum(hs) + 0.22 * (len(items) - 1)
        y = a.cy - total / 2
        for n in items:
            b = fig.node(n, xd, y, lines(n), w=wd, center=False, header=True)
            y += b.h + 0.22

    # column B
    for root, kids, _ in groups:
        span = [fig.boxes[k] for k in kids]
        mid = (span[0].y + span[-1].b) / 2
        h = (line_height("title") + line_height("body") * len(own[root]) + 0.28)
        fig.node(root, xb, mid - h / 2, lines(root), w=wb, center=False, header=True)
    p, s = fig.boxes["Person"], fig.boxes["ParkingSpace"]
    wr = width("Reservation")
    hr = line_height("title") + line_height("body") * len(own["Reservation"]) + 0.28
    fig.node("Reservation", xb, (p.b + s.y) / 2 - hr / 2, lines("Reservation"), w=wr,
             center=False, header=True)
    r = fig.boxes["Reservation"]

    # ISA buses
    def isa(parent: str, kids: list[str], bus_x: float) -> None:
        P = fig.boxes[parent]
        ys = [fig.boxes[k].cy for k in kids] + [P.cy]
        fig.polyline([(bus_x, min(ys)), (bus_x, max(ys))])
        for k in kids:
            K = fig.boxes[k]
            fig.polyline([(K.x, K.cy), (bus_x, K.cy)])
        fig.arrow([(bus_x, P.cy), (P.r, P.cy)], "triangle")

    for root, kids, _ in groups:
        isa(root, kids, xb + wb + gap_bc - 0.42)
    for anchor, items in col_d.items():
        kids = [k for k in items if classes[k].isa == anchor]
        if kids:
            isa(anchor, kids, xc + wc + gap_cd / 2)

    # relation slots
    for src, lab, dst in rel:
        S, D = fig.boxes[src], fig.boxes[dst]
        if src in ("Person", "ParkingSpace"):
            i = [t for s2, _, t in rel if s2 == src].index(dst)
            x0 = S.r - 0.25 - 0.3 * i
            fig.arrow([(x0, S.b), (x0, D.cy), (D.x, D.cy)], label=lab,
                      at=((S.r + D.x) / 2 + 0.05, D.cy - 0.2))
        elif src == "Reservation":
            if D.b <= S.y:
                fig.arrow([(S.cx, S.y), (S.cx, D.b)], label=lab,
                          at=(S.cx + 0.1, (S.y + D.b) / 2), anchor="lm")
            else:
                fig.arrow([(S.cx, S.b), (S.cx, D.y)], label=lab,
                          at=(S.cx + 0.1, (S.b + D.y) / 2), anchor="lm")
        else:
            fig.arrow([(S.r, D.cy), (D.x, D.cy)], label=lab,
                      at=((S.r + D.x) / 2, D.cy - 0.2))

    # legend in the empty middle of column D
    ys = sorted((fig.boxes[n].y, fig.boxes[n].b) for v in col_d.values() for n in v)
    gaps = [(b0, a1) for (_, b0), (a1, _) in zip(ys, ys[1:])]
    g0, g1 = max(gaps, key=lambda g: g[1] - g[0])
    ly = (g0 + g1) / 2 - 0.55
    fig.text(xd, ly, "Legend", "title", "lm")
    legend_item(fig, xd, ly + 0.45, "isa", "ISA (subclass of)")
    legend_item(fig, xd, ly + 0.85, "slot", "frame-valued slot")
    fig.text(xd, ly + 1.25, "slot = v: default value v", "note", "lm")
    fig.text(xd, ly + 1.6, "(if-needed): computed on read", "note", "lm")

    fig.height = height
    fig.img = fig.img.crop((0, 0, fig.img.width, round(height * PX)))
    return fig.save("frame_hierarchy")


# --------------------------------------------------------------------------------
# Figure: semantic networks
# --------------------------------------------------------------------------------

def _net_figure(net, pos: dict[str, tuple[float, float]], width: float, height: float,
                name: str, label_at: dict | None = None, quiet: tuple[str, ...] = (),
                legend: tuple[float, float, bool] | None = None) -> Path:
    """Straight-line semantic network. Edges whose label is in `quiet` are drawn
    without a label and explained in the legend instead."""
    missing = set(net.nodes) - set(pos)
    assert not missing, f"{name} layout does not place {missing}"
    label_at = label_at or {}
    fig = Figure(width, height)
    shape = {"class": "rect", "value": "pill", "instance": "round"}
    for n, kind in net.nodes.items():
        w = text_width(n, "body") + (0.44 if kind == "value" else 0.28)
        h = line_height("body") + 0.2
        cx, cy = pos[n]
        assert 0 <= cx - w / 2 and cx + w / 2 <= width, f"{n} is outside the figure"
        fig.boxes[n] = Box(cx - w / 2, cy - h / 2, w, h, shape[kind])
    for e in net.edges:
        dashed = e.label == "instance-of"
        color = "#15803d" if dashed else ("#1e40af" if e.label == "is-a" else LINE)
        at, off = label_at.get((e.source, e.label, e.target), (0.5, (0, 0)))
        text = None if e.label in quiet else e.label
        fig.link(e.source, e.target, text, dashed=dashed, color=color, at=at, offset=off)
    for n, kind in net.nodes.items():
        b = fig.boxes[n]
        fig.shape(b, *PALETTE[kind])
        fig.text(b.cx, b.cy, n, "body", "mm")
    if legend:
        x, y, horizontal = legend
        rows = [("class", "rect", "class"), ("value", "pill", "value"),
                ("instance", "round", "individual")]
        for kind, shp, text in rows:
            if kind not in net.nodes.values():
                continue
            b = Box(x, y - 0.14, 0.55, 0.28, shp)
            fig.shape(b, *PALETTE[kind])
            fig.text(x + 0.7, y, text, "note", "lm")
            if horizontal:
                x += 0.7 + text_width(text, "note") + 0.45
            else:
                y += 0.42
        if "instance-of" in quiet:
            legend_item(fig, x, y, "dashed", "instance-of")
    return fig.save(name)


def semantic_network() -> Path:
    net = build_class_network()
    r = [0.35, 1.65, 2.95, 4.25, 5.55, 6.85]
    pos = {
        "Faculty": (0.85, r[0]), "Staff": (3.0, r[0]),
        "Employee": (1.9, r[1]), "Student": (4.6, r[1]), "Visitor": (6.7, r[1]),
        "Person": (4.6, r[2]), "ParkingPermit": (9.4, r[1]), "PermitClass": (14.7, r[1]),
        "Vehicle": (9.4, r[2]), "VehicleType": (12.45, r[2]), "SpaceType": (12.45, r[3]),
        "Reservation": (1.4, r[3]),
        "ParkingSpace": (4.6, r[4]), "ParkingZone": (9.4, r[4]), "ZoneType": (14.7, r[4]),
        "AccessibleSpace": (1.3, r[5]), "EVChargingSpace": (4.6, r[5]),
        "MotorbikeSpace": (7.75, r[5]), "ParkingFacility": (11.0, r[5]),
    }
    labels = {("ParkingSpace", "has-type", "SpaceType"): (0.62, (0, 0)),
              ("Person", "has-a", "ParkingPermit"): (0.62, (0, 0))}
    return _net_figure(net, pos, 15.8, 7.2, "semantic_network", labels,
                       legend=(8.6, 0.35, True))


def semantic_network_example() -> Path:
    net = build_instance_network(["ali", "r1"])
    # Zara's own car and permit add nothing to the paths in section 5.3; leave them out.
    drop = {"car_zara", "p_zara"}
    for n in drop:
        net.nodes.pop(n, None)
    net.edges = [e for e in net.edges if e.source not in drop and e.target not in drop]
    r = [0.35, 1.7, 3.05, 4.4, 5.75, 7.1]
    pos = {
        "Person": (3.5, r[0]), "Student": (3.5, r[1]), "ParkingPermit": (1.2, r[1]),
        "Reservation": (7.4, r[1]),
        "ali": (2.3, r[2]), "zara": (4.7, r[2]), "r1": (7.4, r[2]),
        "ParkingSpace": (10.2, r[2]), "ParkingZone": (13.1, r[2]),
        "p_ali": (1.2, r[3]), "car_ali": (3.5, r[3]), "Vehicle": (5.9, r[3]),
        "s_a5": (7.4, r[3]), "zone_a": (10.4, r[3]), "ned_lot": (13.4, r[3]),
        "car": (3.5, r[4]), "standard": (7.4, r[4]), "ParkingFacility": (13.4, r[4]),
        "student_permit": (1.7, r[5]), "student_zone": (10.4, r[5]),
    }
    return _net_figure(net, pos, 15.6, 7.45, "semantic_network_example",
                       quiet=("instance-of",), legend=(12.9, 0.35, False))


# --------------------------------------------------------------------------------
# Figure: ParkingSession script
# --------------------------------------------------------------------------------

def parking_script() -> Path:
    goals = {7: "space_status(S, occupied)"}
    scenes = []
    for sc in PARKING_SESSION.scenes:
        goal = sc.goal or goals.get(sc.number, "")
        goal = goal.replace("{driver}", "D").replace("{space}", "S").replace("{zone}", "Z")
        scenes.append((sc.number, sc.name, goal))
    fig = Figure(15.6, 7.0)
    x_sc, w_sc = 4.1, 6.6
    h_sc, gap = 0.62, 0.3
    y = 0.03
    for num, name, goal in scenes:
        b = Box(x_sc, y, w_sc, h_sc, "round")
        fig.shape(b, *PALETTE["class"])
        fig.text(b.x + 0.18, b.cy, f"{num}", "title", "lm")
        fig.text(b.x + 0.5, b.cy, name, "title", "lm")
        fig.text(b.r - 0.18, b.cy, goal, "mono", "rm")
        fig.boxes[f"s{num}"] = b
        if num > 1:
            prev = fig.boxes[f"s{num - 1}"]
            fig.arrow([(b.cx, prev.b), (b.cx, b.y)])
        y += h_sc + gap
    height = y - gap + 0.03
    s1, s7 = fig.boxes["s1"], fig.boxes[f"s{len(scenes)}"]
    entry_lines = [("Entry conditions", "title"), ("driver owns a vehicle and", "note"),
                   ("has requested a space", "note")]
    eh = line_height("title") + 2 * line_height("note") + 0.2
    e = fig.node("entry", 0.02, max(0.03, s1.cy - eh / 2), entry_lines, w=3.5, shape="round",
                 kind="instance")
    fig.arrow([(e.r, s1.cy), (s1.x, s1.cy)])
    res_lines = [("Results", "title"), ("bay occupied,", "note"), ("driver parked", "note")]
    rh = line_height("title") + 2 * line_height("note") + 0.2
    rs = fig.node("results", 0.02, min(height - rh - 0.03, s7.cy - rh / 2), res_lines,
                  w=3.5, shape="round", kind="instance")
    fig.arrow([(s7.x, s7.cy), (rs.r, s7.cy)])
    checks = [fig.boxes[f"s{n}"] for n, _, _ in scenes if 2 <= n <= 6]
    ta = Box(12.2, checks[0].y, 3.35, checks[-1].b - checks[0].y, "round")
    fig.shape(ta, *PALETTE["out"])
    fig.label(ta.cx, ta.cy - 0.42, "Turned away", "title", bg=False)
    fig.label(ta.cx, ta.cy + 0.05, "with the reason from", "note", bg=False)
    fig.label(ta.cx, ta.cy + 0.4, "the why-not explainer", "note", bg=False)
    for b in checks:
        fig.arrow([(b.r, b.cy), (ta.x, b.cy)], color=FAIL, dashed=True, label="fails",
                  at=((b.r + ta.x) / 2, b.cy - 0.17))
    fig.height = height
    fig.img = fig.img.crop((0, 0, fig.img.width, round(height * PX)))
    return fig.save("parking_script")


# --------------------------------------------------------------------------------
# Figure: inference engine architecture
# --------------------------------------------------------------------------------

def reasoning_engine() -> Path:
    fig = Figure(15.9, 8.0)
    lane = [0.05, 1.6, 3.15, 4.6]           # top y of each lane
    lh = 1.05
    x = {"req": 0.02, "mode": 2.62, "eng": 4.05, "c3": 8.2, "c4": 10.65, "c5": 13.52}
    w = {"req": 2.35, "eng": 3.25, "c3": 2.1, "c4": 2.5, "c5": 2.35}

    req = fig.node("req", x["req"], lane[1], [("Request", "title"), ("allocate(D, S)", "mono")],
                   w=w["req"], h=lh, shape="round")
    mode = fig.node("mode", x["mode"], lane[1] + 0.05, [("Mode", "title")], w=1.1, h=0.95,
                    shape="diamond")
    fc = fig.node("fc", x["eng"], lane[0], [("Forward chaining", "title"),
                                            ("match, fire, add facts", "note")],
                  w=w["eng"], h=lh, kind="class", shape="round")
    bc = fig.node("bc", x["eng"], lane[2], [("Backward chaining", "title"),
                                            ("unify, prove subgoals", "note")],
                  w=w["eng"], h=lh, kind="class", shape="round")
    cw = (w["eng"] - 0.12) / 2
    wm = fig.node("wm", x["eng"], lane[1] - 0.05, [("Working", "body"), ("memory", "body")],
                  w=cw, h=lh + 0.1, kind="store", shape="cyl")
    rb = fig.node("rb", x["eng"] + w["eng"] - cw, lane[1] - 0.05,
                  [("Rule base", "body"), ("R01-R28", "note")], w=cw, h=lh + 0.1,
                  kind="store", shape="cyl")
    s2 = fig.node("s2", x["c3"], lane[0], [("Stratum 2", "title"), ("R28 with not", "note")],
                  w=w["c3"], h=lh, shape="round")
    ic = fig.node("ic", x["c4"], lane[0], [("Integrity check", "title"), ("IC1-IC7", "note")],
                  w=w["c4"], h=lh, shape="round")
    dec = fig.node("dec", x["c5"], lane[0], [("Decisions", "title"),
                                             ("allocate/2 facts", "note")], w=w["c5"], h=lh,
                   kind="instance", shape="round")
    bad = fig.node("bad", x["c5"], lane[1], [("Report", "title"), ("inconsistency", "title")],
                   w=w["c5"], h=lh, kind="out", shape="round")
    pt = fig.node("pt", x["c3"], lane[2], [("Proof tree", "title")], w=w["c3"], h=lh,
                  kind="instance", shape="round")
    wn = fig.node("wn", x["c3"], lane[3], [("Why-not explanation", "title"),
                                           ("first blocked literal", "note")],
                  w=3.3, h=lh, kind="out", shape="round")

    fig.arrow([(req.r, req.cy), (mode.x, mode.cy)])
    fig.arrow([(mode.cx, mode.y), (mode.cx, fc.cy), (fc.x, fc.cy)], label="data-driven",
              at=(mode.cx - 0.1, (mode.y + fc.cy) / 2), anchor="rm")
    fig.arrow([(mode.cx, mode.b), (mode.cx, bc.cy), (bc.x, bc.cy)], label="goal-driven",
              at=(mode.cx - 0.1, (mode.b + bc.cy) / 2), anchor="rm")
    fig.arrow([(wm.cx, wm.y + 0.05), (wm.cx, fc.b)], both=True)
    fig.arrow([(wm.cx, wm.b), (wm.cx, bc.y)])
    fig.arrow([(rb.cx, rb.y + 0.05), (rb.cx, fc.b)])
    fig.arrow([(rb.cx, rb.b), (rb.cx, bc.y)])
    fig.arrow([(fc.r, fc.cy), (s2.x, s2.cy)])
    fig.arrow([(s2.r, s2.cy), (ic.x, ic.cy)])
    fig.arrow([(ic.r, ic.cy), (dec.x, dec.cy)], label="ok",
              at=((ic.r + dec.x) / 2, ic.cy - 0.06), anchor="mb")
    fig.arrow([(ic.cx, ic.b), (ic.cx, bad.cy), (bad.x, bad.cy)], label="violated",
              at=(ic.cx + 0.1, (ic.b + bad.cy) / 2), anchor="lm")
    fig.arrow([(bc.r, pt.cy), (pt.x, pt.cy)], label="proved",
              at=((bc.r + pt.x) / 2, pt.cy - 0.06), anchor="mb")
    xm = bc.r + 0.4
    fig.arrow([(bc.r, bc.b - 0.2), (xm, bc.b - 0.2), (xm, wn.cy), (wn.x, wn.cy)],
              label="failed", at=(xm - 0.1, (bc.b + wn.cy) / 2), anchor="rm")
    height = wn.b + 0.03
    fig.height = height
    fig.img = fig.img.crop((0, 0, fig.img.width, round(height * PX)))
    return fig.save("reasoning_engine")


FIGURES = {
    "architecture": architecture,
    "frame_hierarchy": frame_hierarchy,
    "parking_script": parking_script,
    "semantic_network": semantic_network,
    "semantic_network_example": semantic_network_example,
    "reasoning_engine": reasoning_engine,
}


def build_figures(names: list[str] | None = None) -> list[Path]:
    return [FIGURES[n]() for n in (names or FIGURES)]


if __name__ == "__main__":
    for path in build_figures(sys.argv[1:] or None):
        with Image.open(path) as im:
            w, h = im.size
        print(f"{path.name:32s} {w / DPI * 2.54:5.2f} x {h / DPI * 2.54:5.2f} cm")
