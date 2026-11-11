"""
Builds RobotRover_System_Guide.pdf from the repository's own files.

    pip install reportlab
    python docs/build_pdf.py                 # writes RobotRover_System_Guide.pdf in the repo root
    python docs/build_pdf.py other.pdf       # or to another path
    python docs/build_pdf.py --pinout-svg    # writes images/board_pinout.svg (source of the README's PNG)

Inputs: images/app_mockup.png and images/wiring.png (rendered from images/wiring.svg).
Every other figure (architecture, command sequence, board pinout, LED matrix frames) is
drawn here in code.

Uses only reportlab's built-in fonts (Helvetica / Courier), so every character
must be in Windows-1252. check_text() enforces that so nothing renders as a box.
"""

import sys
from datetime import date

from reportlab.graphics.shapes import Circle, Drawing, Group, Line, Polygon, Rect, String
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    CondPageBreak, Flowable, Image, KeepTogether, PageBreak, Paragraph, Preformatted,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root
PINOUT_SVG = "--pinout-svg" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = _args[0] if _args else os.path.join(ROOT, "RobotRover_System_Guide.pdf")
APP_IMG = os.path.join(ROOT, "images", "app_mockup.png")   # 808 x 2206 px render of the app
WIRING_IMG = os.path.join(ROOT, "images", "wiring.png")    # 2299 x 1690 px, rendered from wiring.svg

# ---------------------------------------------------------------- palette
INK = colors.HexColor("#1F2430")
MUTED = colors.HexColor("#5B6472")
ACCENT = colors.HexColor("#E8892E")
ACCENT_LIGHT = colors.HexColor("#FDF0E3")
SLATE = colors.HexColor("#2E3541")
NAVY = colors.HexColor("#12151A")
RULE = colors.HexColor("#D9DDE3")
CODE_BG = colors.HexColor("#F3F4F6")
TEAL = colors.HexColor("#0F766E")
TEAL_LIGHT = colors.HexColor("#E3F4F1")
BLUE = colors.HexColor("#2563EB")
BLUE_LIGHT = colors.HexColor("#E6EEFC")
PURPLE = colors.HexColor("#6D28D9")
PURPLE_LIGHT = colors.HexColor("#EFE9FC")
GRAY_LIGHT = colors.HexColor("#F1F3F5")
POWER_RED = colors.HexColor("#DC2626")

# ---------------------------------------------------------------- text safety
def check_text(s):
    try:
        s.encode("cp1252")
    except UnicodeEncodeError as e:
        raise SystemExit(f"Character not supported by built-in fonts: {s[e.start:e.end]!r} in: {s[:80]!r}")
    return s

# ---------------------------------------------------------------- styles
BASE = dict(fontName="Helvetica", textColor=INK)
S = {
    "body": ParagraphStyle("body", fontSize=9.6, leading=13.6, spaceAfter=6, **BASE),
    "small": ParagraphStyle("small", fontSize=8.4, leading=11.4, textColor=MUTED, fontName="Helvetica"),
    "cell": ParagraphStyle("cell", fontSize=8.4, leading=11, **BASE),
    "cellb": ParagraphStyle("cellb", fontSize=8.4, leading=11, fontName="Helvetica-Bold", textColor=INK),
    "cellh": ParagraphStyle("cellh", fontSize=8.4, leading=11, fontName="Helvetica-Bold", textColor=colors.white),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=NAVY, spaceBefore=4, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13.5, leading=17, textColor=NAVY, spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.8, leading=14, textColor=SLATE, spaceBefore=8, spaceAfter=3),
    "lead": ParagraphStyle("lead", fontSize=11, leading=15.5, textColor=MUTED, spaceAfter=10, fontName="Helvetica"),
    "bullet": ParagraphStyle("bullet", fontSize=9.6, leading=13.4, leftIndent=14, bulletIndent=3, spaceAfter=2.5, **BASE),
    "num": ParagraphStyle("num", fontSize=9.6, leading=13.4, leftIndent=16, bulletIndent=0, spaceAfter=2.5, **BASE),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=7.9, leading=10.2, textColor=INK,
                           backColor=CODE_BG, borderPadding=(5, 6, 5, 6), leftIndent=6, rightIndent=6,
                           spaceBefore=4, spaceAfter=9),
    "callout": ParagraphStyle("callout", fontSize=9.2, leading=13, **BASE),
    "caption": ParagraphStyle("caption", fontSize=8.2, leading=11, textColor=MUTED, fontName="Helvetica-Oblique",
                              spaceBefore=3, spaceAfter=10),
}

story = []

def P(text, style="body"):
    story.append(Paragraph(check_text(text), S[style]))

def H1(text, kicker=None):
    story.append(PageBreak())
    if kicker:
        story.append(Paragraph(check_text(kicker.upper()), ParagraphStyle(
            "kick", fontName="Helvetica-Bold", fontSize=8.5, textColor=ACCENT, leading=11, spaceAfter=2)))
    story.append(Paragraph(check_text(text), S["h1"]))
    story.append(HRule(RULE, 1.2, 2, 8))

def H2(text):
    story.append(CondPageBreak(1.3 * inch))
    story.append(Paragraph(check_text(text), S["h2"]))

def H3(text):
    story.append(CondPageBreak(0.9 * inch))
    story.append(Paragraph(check_text(text), S["h3"]))

def BUL(items, style="bullet"):
    for it in items:
        story.append(Paragraph(check_text(it), S[style], bulletText="\x95"))

def NUM(items, start=1):
    for i, it in enumerate(items, start):
        story.append(Paragraph(check_text(it), S["num"], bulletText=f"{i}."))

def CODE(text):
    for line in text.splitlines():
        check_text(line)
        if len(line) > 98:
            raise SystemExit(f"Code line too long ({len(line)}): {line}")
    story.append(KeepTogether([Preformatted(text, S["code"])]))

def SP(h=6):
    story.append(Spacer(1, h))

def CAPTION(text):
    story.append(Paragraph(check_text(text), S["caption"]))

class HRule(Flowable):
    def __init__(self, color, width, before, after):
        super().__init__()
        self.color, self.w, self.before, self.after = color, width, before, after
    def wrap(self, aw, ah):
        self.aw = aw
        return aw, self.before + self.after + self.w
    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.w)
        self.canv.line(0, self.after, self.aw, self.after)

def TABLE(rows, widths, header=True, zebra=True, head_color=SLATE, font_rows=None, add=True):
    data = []
    for r_i, row in enumerate(rows):
        out = []
        for c_i, cell in enumerate(row):
            if isinstance(cell, Flowable):
                out.append(cell)
                continue
            style = "cellh" if (header and r_i == 0) else ("cellb" if (font_rows and c_i == 0) else "cell")
            out.append(Paragraph(check_text(str(cell)), S[style]))
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    st = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), head_color)]
    if zebra:
        for i in range(1 if header else 0, len(data)):
            if (i % 2 == 0) == header:
                st.append(("BACKGROUND", (0, i), (-1, i), GRAY_LIGHT))
    t.setStyle(TableStyle(st))
    if not add:
        return t
    story.append(t)
    SP(8)

def CALLOUT(title, text, fill=ACCENT_LIGHT, edge=ACCENT):
    p = Paragraph(check_text(f"<b>{title}</b>&nbsp;&nbsp;{text}"), S["callout"])
    t = Table([[p]], colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    SP(9)

# ---------------------------------------------------------------- diagram helpers
def arrow(d, x1, y1, x2, y2, color=SLATE, width=1.2, both=False):
    import math
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width))
    def head(xa, ya, xb, yb):
        ang = math.atan2(yb - ya, xb - xa)
        L, W = 6.5, 3.2
        bx, by = xb - L * math.cos(ang), yb - L * math.sin(ang)
        px, py = -math.sin(ang) * W, math.cos(ang) * W
        d.add(Polygon([xb, yb, bx + px, by + py, bx - px, by - py], fillColor=color, strokeColor=color, strokeWidth=0.5))
    head(x1, y1, x2, y2)
    if both:
        head(x2, y2, x1, y1)

def box(d, x, y, w, h, title, sub, fill, edge, sub2=None):
    d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=edge, strokeWidth=1))
    d.add(String(x + w / 2, y + h - 15, check_text(title), fontName="Helvetica-Bold", fontSize=8.6,
                 fillColor=INK, textAnchor="middle"))
    if sub:
        d.add(String(x + w / 2, y + h - 27, check_text(sub), fontName="Helvetica", fontSize=7.2,
                     fillColor=MUTED, textAnchor="middle"))
    if sub2:
        d.add(String(x + w / 2, y + h - 37, check_text(sub2), fontName="Helvetica", fontSize=7.2,
                     fillColor=MUTED, textAnchor="middle"))

def badge(d, x, y, label, color=ACCENT):
    d.add(Rect(x - 11, y - 6.5, 22, 13, rx=6.5, ry=6.5, fillColor=color, strokeColor=color))
    d.add(String(x, y - 3, label, fontName="Helvetica-Bold", fontSize=7.4, fillColor=colors.white, textAnchor="middle"))

def label(d, x, y, text, size=7, color=MUTED, anchor="middle", bold=False):
    d.add(String(x, y, check_text(text), fontName="Helvetica-Bold" if bold else "Helvetica",
                 fontSize=size, fillColor=color, textAnchor=anchor))

def architecture_diagram():
    W, H = 468, 330
    d = Drawing(W, H)
    # zones
    d.add(Rect(0, 172, 150, 154, rx=8, ry=8, fillColor=colors.white, strokeColor=RULE, strokeDashArray=[3, 2]))
    label(d, 8, 316, "CONTROLLERS", 6.8, MUTED, "start", True)
    d.add(Rect(170, 4, 298, 322, rx=8, ry=8, fillColor=colors.white, strokeColor=RULE, strokeDashArray=[3, 2]))
    label(d, 178, 316, "ARDUINO UNO Q", 6.8, MUTED, "start", True)
    d.add(Rect(180, 172, 278, 136, rx=6, ry=6, fillColor=GRAY_LIGHT, strokeColor=GRAY_LIGHT))
    label(d, 188, 298, "Linux side - Qualcomm QRB2210, Debian 13", 6.8, SLATE, "start", True)
    d.add(Rect(180, 14, 278, 148, rx=6, ry=6, fillColor=GRAY_LIGHT, strokeColor=GRAY_LIGHT))
    label(d, 188, 152, "Microcontroller - STM32U585, Zephyr", 6.8, SLATE, "start", True)

    box(d, 10, 270, 130, 36, "Android app", "android/ - Kotlin", BLUE_LIGHT, BLUE)
    box(d, 10, 228, 130, 36, "Desktop controller", "desktop/ - Chrome or Edge", BLUE_LIGHT, BLUE)
    box(d, 10, 182, 130, 36, "8BitDo SF30 Pro", "gamepad - Bluetooth Classic", PURPLE_LIGHT, PURPLE)
    box(d, 192, 226, 118, 60, "Bluetooth relay", "robot_ble_bridge.py", TEAL_LIGHT, TEAL, "+ robot_gamepad.py")
    box(d, 330, 226, 118, 60, "arduino-router", "Arduino's broker (Go)", colors.white, MUTED, "systemd service")
    box(d, 192, 186, 118, 30, "BlueZ + radio", None, colors.white, RULE)
    box(d, 192, 84, 160, 56, "RobotRover.ino", "commands, drive, arm", ACCENT_LIGHT, ACCENT, "Bridge 'robot' method")
    box(d, 362, 84, 86, 56, "RobotMatrix.h", "face + icons", ACCENT_LIGHT, ACCENT)
    box(d, 192, 24, 76, 46, "Motor driver", "D2,D4-D8", colors.white, MUTED)
    box(d, 278, 24, 84, 46, "PCA9685", "I2C 0x40", colors.white, MUTED)
    box(d, 372, 24, 76, 46, "LED matrix", "13 x 8", colors.white, MUTED)

    # seams
    arrow(d, 140, 288, 200, 216, BLUE, both=True)      # app -> radio
    arrow(d, 140, 246, 192, 201, BLUE, both=True)      # desktop -> radio
    arrow(d, 140, 200, 192, 196, PURPLE)              # gamepad -> radio
    badge(d, 168, 262, "S2", BLUE)
    badge(d, 160, 213, "S3", BLUE)
    badge(d, 166, 188, "S10", PURPLE)
    arrow(d, 251, 216, 251, 226, TEAL, both=True)
    arrow(d, 310, 256, 330, 256, SLATE, both=True)
    badge(d, 320, 270, "S4")
    arrow(d, 340, 226, 340, 140, SLATE, both=True)     # router <-> sketch
    badge(d, 340, 196, "S5")
    label(d, 356, 178, "UART /dev/ttyHS1", 6.4, MUTED, "start")
    arrow(d, 352, 112, 362, 112, ACCENT, both=False)
    badge(d, 357, 126, "S7")
    arrow(d, 230, 84, 230, 70, SLATE)
    arrow(d, 320, 84, 320, 70, SLATE)
    badge(d, 214, 77, "S6")
    arrow(d, 405, 84, 405, 70, ACCENT)
    return d

def sequence_diagram():
    W, H = 468, 250
    d = Drawing(W, H)
    lanes = [("Phone app", 40, BLUE), ("Relay", 140, TEAL), ("arduino-router", 240, SLATE),
             ("Sketch", 340, ACCENT), ("Servo / matrix", 430, MUTED)]
    for name, x, c in lanes:
        d.add(Rect(x - 38, H - 24, 76, 18, rx=4, ry=4, fillColor=colors.white, strokeColor=c))
        label(d, x, H - 18, name, 7.2, INK, bold=True)
        d.add(Line(x, H - 26, x, 6, strokeColor=RULE, strokeWidth=1, strokeDashArray=[2, 2]))
    steps = [
        (40, 140, 205, "write \"base 45\\n\" (NUS RX, with response)", BLUE),
        (140, 140, 186, "allowlist check", TEAL),
        (140, 240, 167, "[0, id, \"robot\", [\"base 45\"]]", TEAL),
        (240, 340, 148, "forward over UART (Bridge)", SLATE),
        (340, 340, 129, "handleCommand(): target = 45", ACCENT),
        (340, 240, 110, "[1, id, null, \"base -> 45\"]", ACCENT),
        (240, 140, 91, "response to relay", SLATE),
        (140, 40, 72, "notify \"base -> 45\" (NUS TX)", TEAL),
        (340, 430, 53, "servo steps 1 deg / 15 ms; dial follows", ACCENT),
        (340, 430, 34, "matrix: dial icon 1.2 s, then face 2.5 s", ACCENT),
    ]
    for x1, x2, y, text, c in steps:
        if x1 == x2:
            d.add(Rect(x1 - 3, y - 6, 6, 12, fillColor=c, strokeColor=c))
            label(d, x1 + 8, y - 3, text, 6.8, INK, "start")
        else:
            arrow(d, x1, y, x2, y, c)
            mid = (x1 + x2) / 2
            label(d, mid, y + 4, text, 6.6, INK)
    return d

FRAMES = {
    "Idle face": ".............\n..222...222..\n..2#2...2#2..\n..2#2...2#2..\n..222...222..\n.............\n.....444.....\n.............",
    "Forward (moving)": "....#...#....\n...#.....#...\n.............\n......#......\n.....#.#.....\n....#...#....\n...#.....#...\n.............",
    "Base dial at 30 deg": ".............\n##...........\n#.#..........\n##.....222...\n#.#..22...22.\n##...2.....#.\n....2....##.2\n....2...#...2",
    "Gripper closed": "....##.##....\n....#...#....\n....#...#....\n....#...#....\n....#####....\n......#......\n......#......\n......#......",
    "Home": "......#......\n.....###.....\n....#####....\n...#######...\n..#########..\n...#.....#...\n...#..##.#...\n...#######...",
    "Happy (after home)": ".............\n.............\n...#.....#...\n..#.#...#.#..\n.............\n....#...#....\n.....###.....\n.............",
}

def vtext(d, x, y, text, size, color, bold=False):
    """Text rotated 90 degrees (reads bottom to top), starting at (x, y), centered on column x."""
    font = "Helvetica-Bold" if bold else "Helvetica"
    g = Group(String(0, 0, check_text(text), fontName=font, fontSize=size, fillColor=color))
    g.transform = (0, 1, -1, 0, x + 0.36 * size, y)
    d.add(g)
    return stringWidth(text, font, size)

IDLE_FACE = FRAMES_IDLE = (".............", "..222...222..", "..2#2...2#2..", "..2#2...2#2..",
                           "..222...222..", ".............", ".....444.....", ".............")

PINK = colors.HexColor("#DB2777")

def board_pinout():
    """Annotated UNO Q, drawn to scale from Arduino's published top view (68.6 x 53.3 mm).
    Positions below are in mm from the board's top-left corner."""
    K = 4.8                                   # points per mm
    BW, BH = 68.6, 53.3
    W, H = 468, 484
    bx, by = 69, 130                          # board's bottom-left corner in the drawing
    d = Drawing(W, H)

    def P(mx, my):                            # mm (top-left origin) -> drawing point
        return bx + mx * K, by + (BH - my) * K

    def mrect(x0, y0, x1, y1, fill, stroke=None, r=0.4, sw=0.6):
        X0, Y1 = P(x0, y1)
        d.add(Rect(X0, Y1, (x1 - x0) * K, (y1 - y0) * K, rx=r * K, ry=r * K,
                   fillColor=fill, strokeColor=stroke, strokeWidth=sw))

    def mtext(mx, my, text, size, color, anchor="middle", bold=False):
        X, Y = P(mx, my)
        label(d, X, Y, text, size, color, anchor, bold)

    PCB = colors.HexColor("#057582")
    PCB_EDGE = colors.HexColor("#03535C")
    SILVER = colors.HexColor("#A3ADAE")
    SILVER_DARK = colors.HexColor("#7F8C8D")
    CHIP = colors.HexColor("#111417")
    PIN_OFF = colors.HexColor("#3B4650")
    ON_BOARD = colors.HexColor("#D7ECEE")
    GND = colors.HexColor("#4B5563")

    # ---- board outline (UNO shape with the stepped right edge)
    outline = [(0, 0), (66.3, 0), (66.3, 12.4), (68.6, 14.9), (68.6, 47.7), (66.3, 50.2), (66.3, BH), (0, BH)]
    pts = []
    for mx, my in outline:
        pts += list(P(mx, my))
    d.add(Polygon(pts, fillColor=PCB, strokeColor=PCB_EDGE, strokeWidth=1.2, strokeLineJoin=1))

    # ---- mounting holes
    for mx, my in ((14.9, 2.5), (65.9, 17.7), (65.9, 45.7), (13.9, 50.7)):
        X, Y = P(mx, my)
        d.add(Circle(X, Y, 1.9 * K, fillColor=colors.HexColor("#C8B89E"), strokeColor=None))
        d.add(Circle(X, Y, 1.5 * K, fillColor=colors.white, strokeColor=None))

    # ---- parts, placed as on the real board
    mrect(3.0, 1.0, 11.0, 7.0, SILVER)                                  # button
    X, Y = P(7.0, 4.0); d.add(Circle(X, Y, 1.9 * K, fillColor=colors.HexColor("#C9D1D3"), strokeColor=SILVER_DARK, strokeWidth=0.5))
    mrect(12.4, 6.5, 24.9, 11.4, CHIP, r=0.6)                           # 2x5 header
    for i in range(5):
        for j in range(2):
            X, Y = P(13.65 + i * 2.54, 7.7 + j * 2.54)
            d.add(Circle(X, Y, 0.45 * K, fillColor=SILVER, strokeColor=None))
    mrect(27.0, 6.5, 41.6, 16.4, CHIP)                                  # memory
    mrect(28.3, 17.4, 40.5, 29.6, CHIP)                                 # Linux SoC
    mrect(49.2, 11.4, 55.7, 19.6, CHIP)                                 # microcontroller
    mrect(14.0, 15.4, 18.2, 19.4, CHIP, r=0.2)                          # small IC
    mrect(23.7, 36.0, 29.6, 42.0, SILVER, r=0.2)                        # shielded part
    mrect(62.6, 21.7, 67.1, 28.8, CHIP, r=0.6)                          # 2x3 header
    for i in range(2):
        for j in range(3):
            X, Y = P(63.7 + i * 2.3, 23.0 + j * 2.4)
            d.add(Circle(X, Y, 0.45 * K, fillColor=SILVER, strokeColor=None))
    for j in range(4):                                                  # status LEDs
        mrect(64.4, 4.9 + j * 2.0, 65.6, 6.1 + j * 2.0, colors.HexColor("#6459A3"), r=0.2)
    # Wi-Fi / Bluetooth module and its antenna
    mrect(5.5, 31.3, 17.4, 47.7, colors.HexColor("#6D982E"), r=0.3)
    mrect(6.1, 31.9, 16.8, 47.1, colors.HexColor("#B7BFBF"), r=0.3)
    ant = [(0.9, 52.4), (0.9, 35.0), (3.4, 35.0), (3.4, 38.0), (1.9, 38.0), (1.9, 41.0), (3.4, 41.0), (3.4, 44.5)]
    for (x1, y1), (x2, y2) in zip(ant, ant[1:]):
        X1, Y1 = P(x1, y1); X2, Y2 = P(x2, y2)
        d.add(Line(X1, Y1, X2, Y2, strokeColor=colors.HexColor("#00A6AD"), strokeWidth=1.6))
    # USB-C (left edge) and Qwiic (right edge)
    mrect(-1.4, 10.9, 7.5, 19.9, SILVER, SILVER_DARK, r=0.8, sw=0.6)
    for i in range(6):
        X0, Y0 = P(0.0, 12.0 + i * 1.3); X1, _ = P(6.2, 0)
        d.add(Line(X0, Y0, X1, Y0, strokeColor=SILVER_DARK, strokeWidth=0.5))
    mrect(63.9, 35.8, 68.9, 42.0, SILVER, SILVER_DARK, r=0.3)
    for i in range(4):
        X0, Y0 = P(64.6, 36.9 + i * 1.3); X1, _ = P(68.3, 0)
        d.add(Line(X0, Y0, X1, Y0, strokeColor=SILVER_DARK, strokeWidth=0.5))

    # ---- LED matrix: 13 x 8 LEDs
    x0, x1, y0, y1 = 32.3, 57.7, 33.3, 47.7
    fx0, fy1 = P(x0 - 1.3, y1 + 1.3)
    d.add(Rect(fx0, fy1, (x1 - x0 + 2.6) * K, (y1 - y0 + 2.6) * K, rx=4, ry=4,
               fillColor=None, strokeColor=ACCENT, strokeWidth=1.4))
    for r in range(8):
        for c in range(13):
            X, Y = P(x0 + c * (x1 - x0) / 12, y0 + r * (y1 - y0) / 7)
            s = 0.62 * K
            d.add(Polygon([X, Y + s, X + s, Y, X, Y - s, X - s, Y], fillColor=colors.HexColor("#EBAA01"), strokeColor=None))

    # ---- on-board labels
    mtext(19.4, 26.6, "ARDUINO UNO Q", 7.4, colors.white, "middle", True)
    mtext(11.45, 38.6, "Wi-Fi /", 6.2, INK, "middle", True)
    mtext(11.45, 41.0, "Bluetooth", 6.2, INK, "middle", True)
    mtext(34.4, 22.6, "QRB2210", 6.8, colors.white, "middle", True)
    mtext(34.4, 25.0, "Linux SoC", 5.8, ON_BOARD)
    mtext(34.3, 11.9, "memory", 5.8, ON_BOARD)
    mtext(52.45, 15.4, "STM32", 5.8, colors.white, "middle", True)
    mtext(52.45, 17.6, "MCU", 5.6, ON_BOARD)
    mtext(50.6, 31.1, "LED matrix 13 x 8", 6.6, colors.HexColor("#FFD08A"), "middle", True)
    mtext(62.9, 39.6, "Qwiic", 5.8, ON_BOARD, "end")
    # USB-C callout, outside the left edge
    X, Y = P(-2.6, 14.4)
    label(d, X, Y + 1, "USB-C", 7.2, INK, "end", True)
    label(d, X, Y - 8, "PC link, uploads", 6.2, MUTED, "end")

    # ---- pin headers and labels
    def header(pins, x_start_mm, y_mm, labels_above):
        xs = [x_start_mm + i * 2.54 for i in range(len(pins))]
        X0, Yc = P(xs[0], y_mm)
        X1, _ = P(xs[-1], y_mm)
        d.add(Rect(X0 - 1.3 * K, Yc - 1.3 * K, X1 - X0 + 2.6 * K, 2.6 * K, rx=1.2, ry=1.2,
                   fillColor=CHIP, strokeColor=None))
        edge_top = by + BH * K
        for mx, (name, func, col) in zip(xs, pins):
            X, Y = P(mx, y_mm)
            used = col is not None
            d.add(Rect(X - 3.6, Y - 3.6, 7.2, 7.2, rx=1, ry=1, fillColor=col if used else PIN_OFF,
                       strokeColor=colors.white if used else None, strokeWidth=0.8))
            text = f"{name}  {func}" if func else name
            color = col if used else MUTED
            size = 6.3
            if labels_above:
                d.add(Line(X, Y + 5, X, edge_top + 3, strokeColor=col if used else RULE, strokeWidth=0.6))
                vtext(d, X, edge_top + 6, text, size, color, used)
            else:
                w = stringWidth(text, "Helvetica-Bold" if used else "Helvetica", size)
                d.add(Line(X, Y - 5, X, by - 3, strokeColor=col if used else RULE, strokeWidth=0.6))
                vtext(d, X, by - 6 - w, text, size, color, used)

    # Top header (USB on the left): SCL ... D8 | D7 ... D0
    top_left = [("SCL", "PCA9685 servo board", PURPLE), ("SDA", "PCA9685 servo board", PURPLE),
                ("AREF", "", None), ("GND", "common ground", GND), ("D13", "", None), ("D12", "", None),
                ("D11", "", None), ("D10", "", None), ("D9", "", None), ("D8", "left dir (AIN2)", BLUE)]
    top_right = [("D7", "left dir (AIN1)", BLUE), ("D6", "right speed (PWMB)", PINK),
                 ("D5", "left speed (PWMA)", BLUE), ("D4", "right dir (BIN1)", PINK),
                 ("D3", "", None), ("D2", "right dir (BIN2)", PINK), ("D1", "free (serial)", None),
                 ("D0", "free (serial)", None)]
    header(top_left, 18.7, 2.5, True)
    header(top_right, 45.8, 2.5, True)
    # Bottom header: power | analog
    power = [("NC", "", None), ("IOREF", "", None), ("RESET", "", None),
             ("3.3V", "logic power (VCC)", GND), ("5V", "power in", POWER_RED),
             ("GND", "common ground", GND), ("GND", "", None), ("VIN", "not used", None)]
    analog = [("A0", "battery sense", TEAL)] + [(f"A{i}", "", None) for i in range(1, 6)]
    header(power, 28.0, 50.8, False)
    header(analog, 50.9, 50.8, False)

    # ---- legend, two rows
    rows = [[(BLUE, "Left wheel: motor driver channel A"), (PINK, "Right wheel: channel B"),
             (PURPLE, "Servo board (I2C)")],
            [(POWER_RED, "5 V in from the board regulator"), (GND, "Logic power / ground"),
             (TEAL, "Battery sense"), (ACCENT, "On-board LED matrix")]]
    for r, items in enumerate(rows):
        y = 16 - r * 14
        widths = [13 + stringWidth(t, "Helvetica", 6.6) for _, t in items]
        gap = (W - sum(widths)) / (len(items) - 1)
        x = 0
        for (col, text), w in zip(items, widths):
            d.add(Rect(x, y, 9, 9, rx=2, ry=2, fillColor=col, strokeColor=None))
            label(d, x + 13, y + 2, text, 6.6, INK, "start")
            x += w + gap
    return d

# Frames verified against RobotMatrix.h (C++ compiled on the PC) and the JavaScript port
def _rows(frame):
    return frame.split(chr(10)) if isinstance(frame, str) else list(frame)

GRID_FRAMES = [
    ("Idle face", "Nothing happening; blinks every 4 s", _rows(FRAMES["Idle face"])),
    ("Forward", "w held; the arrows stream upward", _rows(FRAMES["Forward (moving)"])),
    ("Spin right", "d held; the arrows stream right", [
        ".#....#....#.", "..#....#....#", "...#....#....", "....#....#...",
        "....#....#...", "...#....#....", "..#....#....#", ".#....#....#."]),
    ("Stop", "x; the sign pulses for 0.7 s", [
        ".....###.....", "....#####....", "...#######...", "...#######...",
        "...#######...", "...#######...", "....#####....", ".....###....."]),
    ("Base dial at 30 deg", "The needle follows the real servo", _rows(FRAMES["Base dial at 30 deg"])),
    ("Gripper closed", "The claw follows the real servo", _rows(FRAMES["Gripper closed"])),
    ("Speed 255", "Bar length is the speed; dots stream", [
        ".............", ".5....5..5...", ".............", "#############",
        "#############", ".............", ".5....5..5...", "............."]),
    ("Home", "home; shown for 1.2 s", _rows(FRAMES["Home"])),
    ("Happy face", "For 2.5 s after home", _rows(FRAMES["Happy (after home)"])),
    ("Battery low", "1 s of every 8 s; the bar is the charge", [
        ".............", "###########..", "#.........#..", "#.##......##.",
        "#.##......##.", "#.........#..", "###########..", "............."]),
    ("Powering off", "Pulses while Linux shuts down", [
        "......#......", "...#..#..#...", "..#...#...#..", "..#.......#..",
        "..#.......#..", "...#.....#...", "....#####....", "............."]),
    ("Safe to switch off", "15 s after Power off", [
        "........####.", "..........#..", ".........#...", "........####.",
        ".............", "..444...444..", ".............", ".....333....."]),
]

def matrix_grid():
    """Grid of large LED matrix frames, three per row, each with a name and when it appears."""
    W = 480
    cols, gap_x, gap_y, label_h = 3, 18, 14, 30
    pw = (W - gap_x * (cols - 1)) / cols          # panel width
    cell = (pw - 12) / 13
    ph = 8 * cell + 12                             # panel height
    rows = (len(GRID_FRAMES) + cols - 1) // cols
    H = rows * (ph + label_h) + (rows - 1) * gap_y
    d = Drawing(W, H)
    for i, (name, when, frame) in enumerate(GRID_FRAMES):
        c, r = i % cols, i // cols
        x0 = c * (pw + gap_x)
        y_top = H - r * (ph + label_h + gap_y)
        y0 = y_top - ph
        d.add(Rect(x0, y0, pw, ph, rx=6, ry=6, fillColor=NAVY, strokeColor=NAVY))
        for y, row in enumerate(frame):
            for x, ch in enumerate(row):
                v = 0 if ch == "." else 7 if ch == "#" else int(ch)
                cx = x0 + 6 + x * cell + cell / 2
                cy = y0 + 6 + (7 - y) * cell + cell / 2
                if v:
                    a = 0.25 + 0.75 * v / 7
                    col = colors.Color(0.30 * a + 0.11 * (1 - a), 0.64 * a + 0.13 * (1 - a), 1.0 * a + 0.20 * (1 - a))
                else:
                    col = colors.HexColor("#1B2233")
                d.add(Circle(cx, cy, cell * 0.38, fillColor=col, strokeColor=None))
        label(d, x0, y0 - 12, name, 8.4, INK, "start", True)
        label(d, x0, y0 - 23, when, 7.4, MUTED, "start")
    return d

# ---------------------------------------------------------------- page furniture
TODAY = date(2026, 11, 11).strftime("%B %d, %Y").replace(" 0", " ")
VERSION = "1.2"

def cover(c, doc):
    w, h = letter
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, h - 4.3 * inch, w, 4.3 * inch, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(0, h - 4.3 * inch, w, 0.09 * inch, stroke=0, fill=1)
    # little robot mark
    x, y = 0.9 * inch, h - 1.45 * inch
    c.setStrokeColor(ACCENT); c.setLineWidth(2.2)
    c.roundRect(x, y, 0.62 * inch, 0.48 * inch, 6, stroke=1, fill=0)
    c.line(x + 0.31 * inch, y + 0.48 * inch, x + 0.31 * inch, y + 0.6 * inch)
    c.circle(x + 0.31 * inch, y + 0.65 * inch, 3, stroke=1, fill=0)
    c.setFillColor(ACCENT)
    c.circle(x + 0.19 * inch, y + 0.29 * inch, 2.6, stroke=0, fill=1)
    c.circle(x + 0.43 * inch, y + 0.29 * inch, 2.6, stroke=0, fill=1)
    c.line(x + 0.22 * inch, y + 0.13 * inch, x + 0.4 * inch, y + 0.13 * inch)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(0.9 * inch, h - 2.35 * inch, "RobotRover")
    c.setFont("Helvetica", 15)
    c.setFillColor(colors.HexColor("#C9CED6"))
    c.drawString(0.9 * inch, h - 2.75 * inch, "System design, build notes and installation guide")
    c.setFont("Helvetica", 10.5)
    c.drawString(0.9 * inch, h - 3.2 * inch, "Arduino UNO Q  -  Bluetooth LE  -  Android  -  Web Bluetooth  -  LED matrix")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.9 * inch, h - 5.0 * inch, "What this document covers")
    c.setFont("Helvetica", 9.6)
    lines = [
        "1. What the system is and the parts it is made of",
        "2. How a command travels from a tap on the phone to a servo and the LED matrix",
        "3. The seams: every place two components meet, what crosses, and how it fails",
        "4. How the system was built, including the problems found along the way",
        "5. How to install each part from scratch, and how to check it works",
        "6. What has been tested and what has not, security, troubleshooting, and a code map",
    ]
    for i, t in enumerate(lines):
        c.drawString(1.05 * inch, h - (5.3 + i * 0.27) * inch, t)
    c.setStrokeColor(RULE); c.setLineWidth(0.8)
    c.line(0.9 * inch, 1.35 * inch, w - 0.9 * inch, 1.35 * inch)
    c.setFillColor(MUTED); c.setFont("Helvetica", 8.6)
    c.drawString(0.9 * inch, 1.1 * inch, f"Version {VERSION}  -  {TODAY}")
    c.drawString(0.9 * inch, 0.9 * inch, "Everything described here is open source and needs no accounts.")
    c.restoreState()

def later(c, doc):
    w, h = letter
    c.saveState()
    c.setStrokeColor(RULE); c.setLineWidth(0.6)
    c.line(0.9 * inch, h - 0.62 * inch, w - 0.9 * inch, h - 0.62 * inch)
    c.setFont("Helvetica-Bold", 7.6); c.setFillColor(ACCENT)
    c.drawString(0.9 * inch, h - 0.55 * inch, "ROBOTROVER")
    c.setFont("Helvetica", 7.6); c.setFillColor(MUTED)
    c.drawString(0.9 * inch + c.stringWidth("ROBOTROVER", "Helvetica-Bold", 7.6) + 8, h - 0.55 * inch,
                 "System design, build notes and installation guide")
    c.drawRightString(w - 0.9 * inch, 0.55 * inch, f"Page {doc.page}")
    c.drawString(0.9 * inch, 0.55 * inch, f"Version {VERSION}  -  {TODAY}")
    c.restoreState()

if PINOUT_SVG:
    # Export only the board pinout, for the README (render it to PNG at 3x, e.g. with a browser)
    from reportlab.graphics import renderSVG
    _svg = os.path.join(ROOT, "images", "board_pinout.svg")
    renderSVG.drawToFile(board_pinout(), _svg)
    # Browsers don't know "Helvetica-Bold" and fall back to a serif font
    with open(_svg, encoding="utf-8") as f:
        _text = f.read()
    _text = (_text.replace("font-family: Helvetica-Bold;", "font-family: Helvetica, Arial, sans-serif; font-weight: bold;")
                  .replace("font-family: Helvetica;", "font-family: Helvetica, Arial, sans-serif;"))
    with open(_svg, "w", encoding="utf-8") as f:
        f.write(_text)
    print("wrote", _svg)
    sys.exit(0)

# =================================================================
#  CONTENT
# =================================================================
story.append(Spacer(1, 1))   # cover page is drawn by cover()

# ---------------------------------------------------------------- 1 at a glance
H1("At a glance", "Section 1")
P("RobotRover is a small two-wheeled robot with a four-joint arm, driven from an Android phone, "
  "a desktop browser or a paired 8BitDo gamepad over Bluetooth. The brain is an <b>Arduino UNO Q</b>, a board with two "
  "processors: a Qualcomm chip running Debian Linux, and an STM32 microcontroller running the "
  "Arduino sketch. The board's 13 x 8 LED matrix shows what the robot is doing: an icon for each "
  "command, then a little face that reacts.", "lead")
P("The design goal was a system that is <b>fully open source, needs no accounts, and works without "
  "an internet connection</b> once installed. Every tool used is either open source or downloaded "
  "directly from its publisher with checksum verification, and no component phones home.")
story.append(architecture_diagram())
CAPTION("Figure 1. The components and the seams between them (S1, the command language, is shared by "
        "every seam and is not drawn). S8 and S9 are build-time seams and are covered in Section 4. S10 is "
        "the optional gamepad, paired straight to the board.")
H2("Why there are so many pieces")
P("The UNO Q's Bluetooth radio is wired to the Linux processor, not to the microcontroller that "
  "drives the motors. So a phone command has to land on the Linux side first and then be handed "
  "across to the microcontroller. Arduino provides that hand-off: a broker called "
  "<font face='Courier'>arduino-router</font> on Linux and a library called <b>Bridge</b> in the "
  "sketch, connected by an internal serial link. RobotRover adds a small Python program, the "
  "<b>relay</b>, that speaks Bluetooth to the phone on one side and the router's protocol on the other. "
  "An 8BitDo SF30 Pro gamepad can also be paired straight to the board's radio; the relay turns its sticks "
  "and buttons into the same commands, so the phone isn't needed to drive.")
TABLE([
    ["Component", "Runs on", "Language", "Job"],
    ["Android app", "Phone (Android 8+)", "Kotlin, no libraries", "Drive pad, arm sliders, shows replies"],
    ["Desktop controller", "PC browser (Chrome/Edge)", "HTML + JavaScript", "Same controls, keyboard, console, demo mode, matrix preview"],
    ["Gamepad (optional)", "8BitDo SF30 Pro, paired to the board", "-", "Drives on the left stick, arm on the D-pad and triggers"],
    ["Bluetooth relay", "UNO Q, Linux side", "Python 3.13", "Bluetooth LE server; reads the gamepad; checks commands; forwards to the sketch; shuts the board down on request"],
    ["arduino-router", "UNO Q, Linux side", "Go (Arduino's)", "Message broker between Linux programs and the microcontroller"],
    ["RobotRover sketch", "UNO Q, microcontroller", "C++ (Arduino, Zephyr)", "Runs commands: wheels, servos, safety timeouts, battery gauge"],
    ["RobotMatrix", "UNO Q, microcontroller", "C++ header", "Draws icons and the face on the LED matrix"],
], [1.25 * inch, 1.35 * inch, 1.25 * inch, 2.65 * inch])

H2("The phone app")
_img_h = 5.55 * inch
_img = Image(APP_IMG, width=_img_h * 808 / 2206, height=_img_h)
_bul = ParagraphStyle("appbul", parent=S["bullet"], spaceAfter=5)
_txt = [Paragraph(check_text(t), S["body"]) for t in [
    "Figure 2 shows the Android app connected to the robot while the Forward arrow is held. "
    "From top to bottom:"]]
_txt += [Paragraph(check_text(t), _bul, bulletText="") for t in [
    "<b>Status pill:</b> grey when offline, yellow while searching or connecting, green when connected.",
    "<b>Connect / Disconnect</b> button, with a status line under it that explains problems "
    "(for example \"Robot not found\").",
    "<b>Drive card:</b> hold an arrow to drive; the held arrow lights orange. The red Stop sits in the "
    "middle. The pill and slider set the wheel speed.",
    "<b>Arm card:</b> one slider per joint with its angle in a pill. Home is in the corner. The "
    "Open / Close toggle follows the gripper slider.",
    "<b>Robot says:</b> the last six replies from the sketch, the newest one highlighted.",
    "<b>Power off robot</b> (below Robot says, added after the mockup was drawn): asks for confirmation, "
    "then shuts the board down so the battery can be switched off safely.",
    "Controls are dimmed and disabled until the app is connected.",
]]
_txt.append(Spacer(1, 4))
_txt.append(Paragraph(check_text("The desktop controller (desktop/index.html) has the same controls in a wider "
                                 "layout, plus keyboard driving, a command console, a demo mode and a live "
                                 "preview of the LED matrix."), S["body"]))
_t = Table([[_img, _txt]], colWidths=[2.35 * inch, 4.15 * inch], hAlign="LEFT")
_t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0),
                        ("LEFTPADDING", (1, 0), (1, 0), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
story.append(_t)
CAPTION("Figure 2. The Android app, connected, with Forward held. Mockup drawn from the app's own layout, "
        "colors and icons; on a phone the screen scrolls.")

# ---------------------------------------------------------------- 2 hardware
H1("The hardware", "Section 2")
H2("Arduino UNO Q")
BUL([
    "<b>Linux side:</b> Qualcomm QRB2210, Debian GNU/Linux 13 (trixie), Python 3.13.5, hostname "
    "<font face='Courier'>uno-q</font>, default user <font face='Courier'>arduino</font>. Owns the Wi-Fi and "
    "Bluetooth 5.1 radio and the USB-C port.",
    "<b>Microcontroller:</b> STM32U585 (Cortex-M33), running Arduino's Zephyr-based core "
    "(board package <i>Arduino Q Boards</i> 1.0.0, FQBN <font face='Courier'>arduino:zephyr:unoq</font>). "
    "Owns the UNO-style header pins and the LED matrix.",
    "<b>Link between them:</b> an internal UART, opened on Linux as <font face='Courier'>/dev/ttyHS1</font> "
    "by arduino-router.",
    "<b>I/O voltage:</b> the header pins are 3.3 V. The TB6612 / L298N motor drivers and the PCA9685 "
    "servo board accept 3.3 V logic.",
])
H2("Robot parts")
TABLE([
    ["Part", "Connection", "Notes"],
    ["Left wheel motor", "PWM D5, direction D7 / D8", "Through a dual H-bridge (TB6612FNG recommended, L298N works)"],
    ["Right wheel motor", "PWM D6, direction D4 / D2", "Flip LEFT_REVERSED / RIGHT_REVERSED in the sketch if a wheel runs backwards"],
    ["Front ball caster", "-", "Passive; follows the wheels"],
    ["Servo board (PCA9685)", "I2C SDA / SCL, address 0x40", "16-channel, 50 Hz. Gives the servos their own power"],
    ["Base servo", "PCA9685 channel 0", "0 - 180 deg, home 90"],
    ["Shoulder servo", "PCA9685 channel 1", "15 - 165 deg, home 90"],
    ["Elbow servo", "PCA9685 channel 2", "15 - 165 deg, home 90"],
    ["Gripper servo", "PCA9685 channel 3", "30 (open) - 120 (closed) deg, home 30. Goes limp after 3 s idle while open"],
    ["LED matrix", "Built into the UNO Q", "13 x 8, 3-bit brightness (0 - 7)"],
    ["Battery", "2S Li-ion pack with BMS, through a main switch", "7.4 V nominal, 8.4 V full; its protection cuts off at about 6.0 V"],
    ["Servo regulator", "Pack -> 5 V -> PCA9685 V+", "Switching (buck or UBEC), 5 A or more (3 A for micro servos); must regulate down to 6 V in"],
    ["Board regulator", "Pack -> 5 V -> UNO Q 5V pin", "Buck-boost, 3 A. Arduino's datasheet (rev 15 and later) allows powering the board here"],
    ["Battery divider", "20k from the pack to A0, 10k from A0 to GND", "8.4 V reads 2.8 V at A0. Set BATTERY_SENSE in the sketch once wired"],
], [1.5 * inch, 1.85 * inch, 3.15 * inch])
CALLOUT("Power.", "One 2S Li-ion pack powers everything through a main switch: the motors straight from the "
        "pack, the servos and the board through their own 5 V regulators. Never power motors or servos from "
        "the UNO Q itself. All grounds connect together. The switch also cuts the board's Linux side, so use "
        "Power off in the app first.")
story.append(KeepTogether([
    Paragraph("Where everything connects", S["h2"]),
    Paragraph(check_text("The pins RobotRover uses, colored by what they drive. The board is drawn to scale "
                         "(68.6 x 53.3 mm) from Arduino's published top view of the UNO Q, with the "
                         "header pins in their real positions."), S["body"]),
    board_pinout(),
    Paragraph(check_text("Figure 3. Arduino UNO Q pins used by RobotRover. Outline, headers, holes and major parts "
                         "follow Arduino's top view; small parts are omitted and chip labels are approximate. "
                         "Pins without a description are free. D5 and D6 must be PWM-capable pins."),
              S["caption"]),
]))

_ww = 6.6 * inch
story.append(KeepTogether([
    Paragraph("Wiring", S["h2"]),
    Paragraph(check_text("How the UNO Q, the TB6612FNG motor driver, the PCA9685 servo board, the motors, servos, "
                         "regulators and battery connect. Wire colors match Figure 3: blue left wheel, pink right "
                         "wheel, purple I2C and servo cables, orange 3.3 V logic, red power, teal battery sense, "
                         "black ground."), S["body"]),
    Image(WIRING_IMG, width=_ww, height=_ww * 1690 / 2299),
    Paragraph(check_text("Figure 4. Wiring for RobotRover (schematic, not to scale). Pins match RobotRover.ino."),
              S["caption"]),
]))
H3("Rules that matter")
BUL([
    "<b>One battery, three branches.</b> After the main switch the pack feeds the TB6612's VM directly "
    "(6 - 8.4 V; TB6612 maximum 13.5 V), the servo regulator (5 V into the PCA9685's V+) and the board "
    "regulator (5 V into the UNO Q's 5V pin).",
    "<b>Never power motors or servos from the UNO Q.</b> Its 5V pin is an input here, fed only by its own regulator.",
    "<b>Check polarity on the 5V pin.</b> Arduino's datasheet lists no reverse-polarity or over-voltage "
    "protection on it; keep it at 4.5 - 5.5 V. USB-C can stay plugged in for uploads: the board joins its "
    "inputs through diodes.",
    "<b>Don't feed the pack into VIN.</b> VIN needs 7 - 24 V, and a 2S pack spends its last stretch below 7 V.",
    "<b>The board regulator must be buck-boost</b> (step-up/step-down), so it keeps giving 5 V when motor surges "
    "sag the pack. The servo regulator must keep regulating down to a 6 V input.",
    "<b>Shut down before switching off.</b> The main switch also cuts the board's Linux side. Use Power off in "
    "the app and wait for the sleeping face on the matrix.",
    "<b>All grounds connect together:</b> UNO Q GND, both TB6612 GND pins, PCA9685 GND, both regulators' GND, "
    "the pack's (-) and the bottom of the battery divider.",
    "<b>Battery gauge:</b> 20k from the pack's + (after the switch, so it doesn't drain a parked robot) to A0, "
    "10k from A0 to GND. Then set BATTERY_SENSE to true in the sketch and adjust BATT_CAL until "
    "<font face='Courier'>batt</font> matches a multimeter.",
    "<b>STBY must be tied high</b> (to 3.3 V), or the TB6612 ignores every command.",
    "<b>Logic is 3.3 V.</b> TB6612 VCC and PCA9685 VCC take 3.3 V from the board; the high-current power goes "
    "only to VM and V+.",
    "<b>Add a 470 - 1000 µF capacitor</b> across the servo board's V+ and GND to ride out current spikes.",
    "<b>Servo plugs:</b> signal (yellow or orange) toward the PCA9685's PWM row, brown or black toward GND.",
    "<b>Using an L298N instead?</b> ENA = D5, IN1 = D7, IN2 = D8, ENB = D6, IN3 = D4, IN4 = D2. Remove the "
    "ENA / ENB jumpers; motors go on OUT1 / OUT2 and OUT3 / OUT4.",
    "<b>First power-up:</b> wheels off the ground, then try <font face='Courier'>w 500</font> and <font face='Courier'>base 90</font> from the Serial Monitor or "
    "the desktop console.",
])

# ---------------------------------------------------------------- 3 command life
H1("How a command travels", "Section 3")
P("Following one command end to end is the quickest way to see how the parts fit. Here the user "
  "drags the Base slider on the phone to 45 degrees.", "lead")
story.append(sequence_diagram())
CAPTION("Figure 5. The life of \"base 45\". Each arrow crosses one seam from Section 4.")
NUM([
    "<b>Phone:</b> the slider sends <font face='Courier'>base 45</font> (at most every 100 ms while dragging, plus "
    "once on release). The app queues it, merging it with any older unsent <font face='Courier'>base</font> "
    "command, and writes it to the robot's Bluetooth characteristic.",
    "<b>Relay:</b> receives the text, lower-cases it, checks it against an allowlist of robot commands, "
    "and calls the sketch's <font face='Courier'>robot</font> method through arduino-router's Unix socket.",
    "<b>Router:</b> forwards the call over the internal UART to the microcontroller.",
    "<b>Sketch:</b> Bridge runs the <font face='Courier'>robot</font> handler on its own thread, under a lock "
    "that keeps it from overlapping <font face='Courier'>loop()</font>. It parses the command, clamps 45 to the "
    "base's limits, sets the target angle, tells the LED matrix, and returns the reply "
    "<font face='Courier'>base -&gt; 45</font>.",
    "<b>Back out:</b> the reply returns through the router and relay and arrives at the phone as a "
    "Bluetooth notification, shown under \"Robot says\".",
    "<b>Physically:</b> the servo moves toward 45 degrees one degree every 15 ms. The LED matrix shows "
    "a \"B\" dial whose needle follows the servo's actual position, then the face glances toward the "
    "side the base turned.",
])
story.append(KeepTogether([
    Paragraph("LED matrix frames", S["h2"]),
    matrix_grid(),
    Paragraph("Figure 6. Real frames from RobotMatrix.h, drawn from the same pixel data the board shows. "
              "Each command shows its icon first; the face reacts afterwards. An empty battery shows the "
              "battery outline with no bar, blinking, in place of the faces.",
              S["caption"]),
]))
H2("Driving is a stream of short pulses")
P("Holding a drive arrow does not send \"drive forever\". The app sends "
  "<font face='Courier'>w 400</font> (forward for 400 ms) every 150 ms. Each pulse restarts the "
  "sketch's 400 ms timer. Releasing the button sends <font face='Courier'>x</font> (stop). If anything "
  "between the phone and the motors fails (Bluetooth drops, the app is backgrounded, the relay "
  "restarts), the pulses stop arriving and the wheels stop on their own within 400 ms. The same rule "
  "is used by the desktop controller.")
P("The sketch ramps each wheel up to speed over about 150 ms instead of jumping to full power, which "
  "cuts the current surge at every start. Slowing down, stopping and reversing are instant, so "
  "<font face='Courier'>x</font> still stops the robot at once. Repeated pulses set the same target, so "
  "holding a button doesn't restart the ramp.")

# ---------------------------------------------------------------- 4 seams
H1("The seams", "Section 4")
P("A seam is a place where two independently written components meet. Most bugs in a system like "
  "this live at the seams, so each one is described the same way: what crosses it, its exact "
  "format, which code owns each side, how it fails, and how to test it in isolation.", "lead")
TABLE([
    ["Seam", "Between", "Medium", "Format"],
    ["S1", "Everything", "-", "The text command language"],
    ["S2", "Android app - relay", "Bluetooth LE", "Nordic UART Service, newline-terminated text"],
    ["S3", "Desktop controller - relay", "Bluetooth LE (Web Bluetooth)", "Same as S2"],
    ["S4", "Relay - arduino-router", "Unix socket", "MessagePack-RPC"],
    ["S5", "arduino-router - sketch", "Internal UART", "MessagePack-RPC via Bridge"],
    ["S6", "Sketch - motors and servos", "GPIO / PWM / I2C", "Pin levels, PCA9685 registers"],
    ["S7", "Sketch - LED matrix", "Function calls", "13 x 8 brightness frame"],
    ["S8", "C++ - JavaScript mirrors", "Source code", "Ported logic that must stay identical"],
    ["S9", "PC - devices (build and deploy)", "USB", "APK sideload, firmware upload, adb push"],
    ["S10", "Gamepad - relay", "Bluetooth Classic (HID)", "Linux input events, turned into S1 commands"],
], [0.55 * inch, 2.0 * inch, 1.6 * inch, 2.35 * inch], font_rows=True)

def seam(title, rows):
    """Heading + seam card kept on one page."""
    t = TABLE(rows, [1.15 * inch, 5.35 * inch], header=False, zebra=True, font_rows=True, add=False)
    story.append(KeepTogether([Paragraph(check_text(title), S["h2"]), t, Spacer(1, 8)]))

H2("S1  The command language")
P("Every controller, the relay and the sketch share one tiny text protocol. It is the contract that "
  "lets each side be written, tested and replaced independently: a command typed into the Serial "
  "Monitor, the desktop console, the relay's <font face='Courier'>--send</font> option, or sent from the "
  "phone all behave the same.")
TABLE([
    ["Command", "Effect", "Reply (examples)"],
    ["w | s | a | d  [ms]", "Forward / back / spin left / spin right. Default 1000 ms; 0 = until stopped", "forward, backward, spin left, spin right"],
    ["m L R  [ms]", "Tank drive: left and right wheel -255 to 255 (the gamepad's sticks). Default 1000 ms", "wheels 180 -120"],
    ["x  or  stop", "Stop the wheels", "stopped"],
    ["speed N", "Wheel speed 0 - 255 (default 180)", "speed 200"],
    ["base | shoulder | elbow | grip N", "Move a joint to N degrees, clamped to its limits", "base -> 45,  base -> 180 (limit 0-180)"],
    ["open | close | home", "Gripper open / closed, whole arm to home", "gripper opening, arm going home"],
    ["pos", "Report targets and speed", "base 90 shoulder 90 elbow 90 gripper 30 speed 180"],
    ["batt", "Report the battery voltage and state", "battery 7.62 V ok, battery not connected"],
    ["poweroff", "Shut the board down (the relay does this; the sketch stops and locks out moves)",
     "powering off: switch off when the face sleeps"],
    ["help  (Serial Monitor only)", "Print the command list to the Serial Monitor", "help printed to Serial Monitor"],
], [1.75 * inch, 2.75 * inch, 2.0 * inch])
story.append(CondPageBreak(1.7 * inch))
P("<b>Rules:</b> one command per line, lower case, single spaces, whole-number values. Replies are "
  "short single lines (they must fit in one Bluetooth packet; the relay truncates at 180 bytes). "
  "The relay only forwards commands matching this allowlist (from "
  "<font face='Courier'>board/robot_ble_bridge.py</font>); everything else is answered with "
  "<font face='Courier'>rejected: ...</font> and never reaches the sketch. When the battery is empty, or "
  "while powering off, every command that moves something is refused (\"battery empty 6.5 V, charge me\" "
  "or \"powering off\"):")
CODE("^(?:(?:w|a|s|d) \\d{1,5}|w|a|s|d|x|stop|open|close|home|pos|batt|poweroff\n"
     "  |(?:speed|base|shoulder|elbow|grip) \\d{1,3}|m -?\\d{1,3} -?\\d{1,3}(?: \\d{1,5})?)$")

seam("S2  Android app - relay  (Bluetooth LE)", [
    ["Crosses", "Command text from the phone; reply text back."],
    ["Format", "Nordic UART Service (NUS). Service 6e400001-b5a3-f393-e0a9-e50e24dcca9e. "
               "The phone writes to RX ...0002 (write with response), the relay notifies on TX ...0003. "
               "Each write is one command plus \"\\n\"; the relay also splits a write on newlines."],
    ["Phone side", "RobotBle.kt: scans for the service UUID or the name \"RobotRover\" (10 s timeout), "
                   "connects with TRANSPORT_LE, requests a 185-byte MTU, discovers services, enables "
                   "notifications by writing the 0x2902 descriptor, then sends through a one-at-a-time "
                   "queue (max 20) that merges commands of the same kind (all drive commands are one kind)."],
    ["Board side", "robot_ble_bridge.py, built on bless 0.3.0 over BlueZ D-Bus. Advertises as \"RobotRover\". "
                   "Commands go into an asyncio queue (max 50, oldest dropped) and are handled one at a time."],
    ["Permissions", "Android 12+: BLUETOOTH_SCAN (neverForLocation) and BLUETOOTH_CONNECT. Android 8 - 11: "
                    "location permission, and Location must be on. The app has no internet permission."],
    ["Fails how", "\"Robot not found\": relay not running or Bluetooth off on the board. Connect then drop: "
                  "radio range or the relay restarted. No replies but commands work: notifications not enabled."],
    ["Test it", "Board: bluetoothctl show should list \"Nordic UART Service\" and ActiveInstances 1. "
                "Phone: the status pill turns green and \"pos\" (desktop console) gets a reply."],
])

seam("S3  Desktop controller - relay  (Web Bluetooth)", [
    ["Crosses", "Exactly what S2 carries; the board cannot tell the PC and the phone apart."],
    ["Format", "Same NUS service and characteristics. Uses navigator.bluetooth.requestDevice with a filter on "
               "the service UUID or name, writeValueWithResponse, and startNotifications."],
    ["PC side", "desktop/index.html, served by desktop/serve.py on http://localhost:8765 bound to 127.0.0.1 "
                "(Web Bluetooth needs a secure origin; localhost counts). Chrome or Edge only."],
    ["Extras", "Keyboard driving, a console for raw commands, demo mode (no hardware), and an LED matrix "
               "preview. When connected, the preview mirrors only commands sent from this page."],
    ["Fails how", "\"This browser can't use Bluetooth\": wrong browser or the file was opened directly "
                  "instead of through serve.py. Device list empty: PC Bluetooth off or relay not advertising."],
    ["Test it", "Try demo mode first (exercises everything except Bluetooth), then Connect."],
])

seam("S4  Relay - arduino-router  (MessagePack-RPC over a Unix socket)", [
    ["Crosses", "One RPC call per command: method \"robot\", one string parameter; the reply string back."],
    ["Format", "MessagePack arrays on /var/run/arduino-router.sock (mode 666, so no root needed). "
               "Request [0, msgid, \"robot\", [\"base 45\"]]; response [1, msgid, error, result]."],
    ["Relay side", "RouterClient in robot_ble_bridge.py: a minimal client (about 60 lines) instead of "
                   "Arduino's App Lab Python package, so the relay runs outside App Lab. 3 s timeout, one "
                   "reconnect attempt on a dropped socket, ignores unrelated messages. The relay answers "
                   "poweroff itself: it sends poweroff to the sketch, then runs systemctl halt (directly as "
                   "root, or with sudo -n as the arduino user, which needs a sudoers rule). If that is refused it "
                   "tells the phone why and sends poweroff 0 so the sketch carries on."],
    ["Router side", "arduino-router (GPL-3.0) brokers calls in a star topology. Methods are registered by "
                    "whoever provides them; here the sketch registers \"robot\"."],
    ["Fails how", "[2, 'method robot not available']: the sketch is not running, is an old version without "
                  "Bridge.provide_safe(\"robot\"), or is registered with an older router process (after a "
                  "Linux-only reboot the microcontroller keeps running). The relay handles the last case: at "
                  "startup, and whenever a command comes back \"not available\", it resets the microcontroller with "
                  "Arduino's /opt/openocd/bin/arduino-reset.sh (GPIO, no sudo), at most once every 30 s. "
                  "Timeout: the sketch is stuck or rebooting. Connection refused: arduino-router is not running."],
    ["Test it", "./run.sh --send pos on the board (no Bluetooth involved). Expected: "
                "base 90 shoulder 90 elbow 90 gripper 30 speed 180."],
])

seam("S5  arduino-router - sketch  (Bridge over the internal UART)", [
    ["Crosses", "The forwarded RPC request and the sketch's reply."],
    ["Format", "MessagePack-RPC over UART /dev/ttyHS1. Handled entirely by Arduino's Bridge library "
               "(Arduino_RouterBridge) in the sketch; RobotRover never touches the bytes."],
    ["Sketch side", "setup() calls Bridge.begin(), Monitor.begin(), then "
                    "Bridge.provide_safe(\"robot\", bridgeCommand). \"Safe\" handlers are meant to run between "
                    "loop() passes, but with Arduino_RPClite 0.3.x the Bridge's own thread runs them (measured "
                    "on the board: a different thread from loop()). So runCommand() and loop() take turns "
                    "through a Zephyr mutex, and command handlers only set targets; every pin and I2C write "
                    "happens in loop(). loop() must stay fast and non-blocking."],
    ["Fails how", "A burst of \"invalid packet, expected array\" in the router log right after the "
                  "microcontroller resets is normal (Bridge flushes old data at startup). If the sketch "
                  "blocks in loop(), every command times out at S4."],
    ["Test it", "journalctl -u arduino-router shows the connection; S4's --send test proves S5 too."],
])

seam("S6  Sketch - motors and servos", [
    ["Crosses", "Electrical signals."],
    ["Wheels", "Each motor: one PWM pin (analogWrite 0 - 255, 500 Hz) and two direction pins. IN1 high = "
               "forward, IN2 high = reverse, both low = coast. Commands set targets; updateDrive() ramps the "
               "output 17 steps every 10 ms (0 - 255 in about 150 ms) and drops instantly when slowing, "
               "stopping or reversing. A timed drive stops itself when driveStopAt passes."],
    ["Servos", "Adafruit PCA9685 library over I2C (address 0x40), 50 Hz, angle mapped to 500 - 2500 us. "
               "updateArm() moves each servo 1 degree every 15 ms toward its target, so motion is smooth "
               "and the power draw is spread out. At power-on the servos go to home one at a time, 250 ms "
               "apart. The open gripper goes limp after 3 s still (PCA9685 full-off) and wakes on its next "
               "command; the other joints always hold."],
    ["Battery", "A0 through a 20k / 10k divider, 12-bit, sampled every 200 ms and smoothed over about 2 s. "
                "States: not connected (under 3 V), ok, low (under 7.0 V), empty (under 6.6 V for 3 s), with "
                "0.2 V of hysteresis. Empty stops the wheels and refuses moves. Off until BATTERY_SENSE is true."],
    ["Fails how", "\"PCA9685 servo board not found\" on the Serial Monitor at startup: wiring or power. "
                  "Servos jitter or the board resets: regulator too small, or grounds not shared. batt says "
                  "\"not connected\": pack switched off or divider not wired. Random battery readings: "
                  "BATTERY_SENSE is true but nothing is on A0."],
    ["Test it", "Serial Monitor commands (base 45, w 500, batt) with the robot on a stand."],
])

seam("S7  Sketch - LED matrix", [
    ["Crosses", "RobotMatrix::onCommand(cmd, hasValue, value) from handleCommand, "
                "RobotMatrix::update(angles, speed) from every loop(), setBattery(state, fill) after each "
                "battery reading, and setPoweringOff(on) for power-off."],
    ["Format", "A 104-byte frame (13 columns x 8 rows, row-major), values 0 - 7, passed to "
               "Arduino_LED_Matrix::draw() after setGrayscaleBits(3). At most one frame every 40 ms."],
    ["Behavior", "An icon for 0.6 - 1.5 s (refreshed while a command repeats), then a face reaction for "
                 "2.5 s, then the idle face (blinks every 4 s, glances every 9 s). The joint dial and claw "
                 "draw the servos' current angles, not the targets. Battery low: a battery icon for 1 s of "
                 "every 8 s. Empty: a blinking empty battery instead of the faces. Power off: a pulsing power "
                 "symbol, then after 15 s a sleeping face, over everything else. A pos or help doesn't cut "
                 "short an icon or reaction that is still showing."],
    ["Fails how", "Matrix blank: sketch not running. All LEDs the same brightness or very dim: the "
                  "grayscale setting; online reports about the UNO Q's brightness range conflict, so check "
                  "this on the real board first."],
    ["Test it", "Power the bare board: the idle face should appear within a second."],
])

H2("S8  Mirrors: C++ logic ported to JavaScript")
P("The desktop controller's demo mode and its matrix preview contain line-for-line ports of sketch "
  "code. This is a source-code seam: nothing checks it automatically, so any change on one side must be "
  "copied to the other.")
TABLE([
    ["C++ original", "JavaScript copy (desktop/index.html)", "How it was verified"],
    ["handleCommand() in RobotRover.ino", "demoSketch(), battText()", "Same replies for the full command table, "
                                          "including clamping, empty-battery and powering-off refusals"],
    ["Relay allowlist (Python regex)", "ALLOWED", "Same pattern; demo rejects \"help\" exactly like the real relay"],
    ["Relay's poweroff reply", "demoReceive(), POWEROFF_REPLY", "Same text; the demo adds \"(demo)\""],
    ["tankIcon() and the m command", "tankIcon(), demoSketch()", "Same arrow icons, clamping and replies"],
    ["updateArm(): 1 degree / 15 ms", "armClock interval", "Dial and claw animate at the same speed"],
    ["RobotMatrix.h (all drawing)", "LM module", "C++ compiled on the PC with g++ and stub libraries; its frames "
                                                 "matched the JavaScript frames pixel for pixel for 38 frames, "
                                                 "including the battery and power-off icons"],
], [1.9 * inch, 1.9 * inch, 2.7 * inch])

H2("S9  Build and deploy seams")
TABLE([
    ["Path", "Tool", "What crosses", "Notes"],
    ["PC -> phone", "MTP file transfer", "RobotRover.apk", "Sideloaded from the Download folder. Debug-signed; Play Protect may warn."],
    ["PC -> microcontroller", "arduino-cli (inside Arduino IDE 2) on COM13", "Compiled sketch",
     "Upload goes through the board's Linux side, which flashes the STM32 over SWD with OpenOCD."],
    ["PC -> board Linux", "adb (platform-tools 37.0.1) over USB", "Relay files and libraries",
     "The board exposes an ADB interface on USB; no password needed for the arduino user."],
    ["Board boot", "cron @reboot -> keepalive.sh", "Starts the relay",
     "Restarts it 3 s after any exit. cron skips the job while the arduino user's password is marked "
     "expired, as it is on a fresh board: set one with arduino-passwd. 20 s after starting, the relay "
     "restarts the sketch if it isn't registered with the new router."],
], [1.2 * inch, 1.6 * inch, 1.35 * inch, 2.35 * inch])

seam("S10  Gamepad - relay  (Bluetooth Classic HID)", [
    ["Crosses", "Button and stick input from an 8BitDo SF30 Pro paired to the board. Nothing goes back to it."],
    ["Format", "BlueZ's HID support turns the controller into a Linux input device (/dev/input/eventN). "
               "robot_gamepad.py reads its events with plain Python (no extra packages; the arduino user is "
               "in the input group). The button and stick codes are a table at the top of that file."],
    ["Board side", "GamepadReader looks every 2 s for an input device named 8BitDo or SF30 with gamepad buttons. "
                   "PadLogic turns its state into ordinary commands on the relay's queue, marked as coming from "
                   "the pad; their replies aren't sent to the phone."],
    ["Driving", "One stick: the relay mixes the left stick (up/down speed, left/right steering) into wheel "
                "speeds and sends m L R 400 every 150 ms while it is outside the 15% dead zone (sooner if a "
                "wheel's speed changes by more than 20). DRIVE_STYLE = \"tank\" drives each wheel from one "
                "stick instead. Releasing the stick, or losing the controller, sends "
                "x. While the pad drives, the phone's drive commands are ignored until 0.5 s after the pad's last "
                "one; stop from either always works."],
    ["Fails how", "Not found: not paired, switched off, or not in D-input (Android) mode; Switch mode needs a "
                  "driver this board doesn't have. \"Has no sticks\" in relay.log: wrong mode. A button does the "
                  "wrong thing: this controller's codes differ from the table."],
    ["Test it", "./run.sh --gamepad-test prints each button and stick as it changes."],
])
TABLE([
    ["Gamepad control", "Does"],
    ["Left stick", "Drive: up / down is speed, left / right steers (spins in place), diagonals curve"],
    ["Right stick", "Not used"],
    ["D-pad left / right", "Base, 50 degrees a second while held"],
    ["D-pad up / down", "Shoulder up / down"],
    ["L2 / R2", "Elbow down / up"],
    ["A / B", "Gripper open / close"],
    ["L / R", "Top speed down / up by 25 (also sets the phone's speed)"],
    ["X", "Battery icon on the matrix"],
    ["Select", "Stop"],
    ["Start", "Arm home"],
    ["Hold Start + Select for 3 s", "Power off"],
], [2.1 * inch, 4.4 * inch])

H2("Values that must match across seams")
P("If you change any of these, change every place listed.")
TABLE([
    ["Value", "Where it lives"],
    ["Service UUID 6e400001-..., RX ...0002, TX ...0003", "robot_ble_bridge.py, RobotBle.kt, desktop/index.html"],
    ["Device name \"RobotRover\"", "robot_ble_bridge.py, RobotBle.kt, desktop/index.html"],
    ["Bridge method name \"robot\"", "RobotRover.ino (provide_safe), robot_ble_bridge.py (BRIDGE_METHOD)"],
    ["Command allowlist", "robot_ble_bridge.py (ALLOWED), desktop/index.html (ALLOWED)"],
    ["Joint limits and home angles", "RobotRover.ino (joints), activity_main.xml (slider min/max), "
                                     "MainActivity.kt (HOME_*), desktop/index.html (sliders, demo, HOME)"],
    ["Gripper open 30 / closed 120", "RobotRover.ino, RobotMatrix.h (claw), MainActivity.kt, desktop/index.html"],
    ["Drive pulse 400 ms every 150 ms", "MainActivity.kt, desktop/index.html, robot_gamepad.py (PULSE_MS, REPEAT_S)"],
    ["Gamepad button and stick codes", "robot_gamepad.py (BUTTONS, LEFT_Y, RIGHT_Y); check with --gamepad-test"],
    ["Reply length under 180 bytes", "robot_ble_bridge.py (MAX_REPLY_BYTES), app MTU request (185)"],
    ["Matrix shapes and timings", "RobotMatrix.h and the LM module in desktop/index.html"],
    ["Battery divider ratio (20k / 10k = 3.0)", "The resistors and RobotRover.ino (BATT_DIVIDER)"],
    ["Battery levels: empty 6.6 V, full 8.2 V", "RobotRover.ino (BATT_*), desktop/index.html (BATT_EMPTY_V, BATT_FULL_V)"],
    ["Power-off reply and the 15 s sleeping-face delay", "robot_ble_bridge.py, RobotMatrix.h (SAFE_AFTER_MS), "
                                                        "desktop/index.html (POWEROFF_REPLY, SAFE_AFTER_MS)"],
    ["Power-off command /usr/bin/systemctl halt", "robot_ble_bridge.py (POWEROFF_CMD) and the sudoers rule on the board"],
], [2.6 * inch, 3.9 * inch])

# ---------------------------------------------------------------- 5 how it was built
H1("How it was built", "Section 5")
P("The project was built in one long session, in this order. The decisions and the problems found "
  "along the way are recorded here because they explain why things are the way they are.", "lead")
H2("Decisions")
TABLE([
    ["Decision", "Why"],
    ["Arduino IDE 2 / arduino-cli instead of App Lab", "Open source, works offline once the board package is installed, no account."],
    ["Relay on the Linux side", "The Bluetooth radio is only reachable from Linux; Arduino's Bridge is the supported way across."],
    ["Bluetooth LE with the Nordic UART Service", "Widely supported text-over-BLE convention; easy to test with generic tools."],
    ["Own MessagePack-RPC client in the relay", "Avoids depending on App Lab's Python package; about 60 lines."],
    ["Command allowlist in the relay", "BLE here has no pairing, so the relay limits what a stranger could send."],
    ["Drive pulses instead of start/stop", "Fails safe: losing the link stops the wheels within 400 ms."],
    ["PCA9685 for servos", "Arduino's Servo library support on the UNO Q's Zephyr core could not be confirmed; the "
                           "arm also needs separate servo power anyway."],
    ["Kotlin app with zero libraries", "Small (838 KB), nothing to audit beyond the code, no internet permission."],
    ["Dark theme, round drive pad", "Chosen from an interactive mockup before implementation."],
    ["Desktop controller via Web Bluetooth", "Tests the same seam as the phone from a PC; demo mode needs no hardware."],
    ["\"Face + icons\" LED matrix design", "Chosen from four animated concepts: clear about what is running, with personality."],
    ["SDK parts downloaded directly, not via Google's 'android' tool", "The new tool collects usage data by default; direct "
                                                                       "downloads with checksums send nothing."],
    ["Relay installed offline as the normal user", "The board had no internet and sudo needs a password; BlueZ's D-Bus "
                                                   "policy and the router socket both allow a normal user."],
    ["One 2S battery for everything", "One pack to charge. Motors run straight from it; the servos and the board get "
                                      "their own 5 V regulators, the board's a buck-boost so motor surges can't brown it out."],
    ["Commands set targets; loop() does the hardware", "The Bridge runs commands on its own thread. A mutex plus this rule "
                                                       "keeps pin and I2C writes from ever overlapping."],
    ["Battery cut-off at 6.6 V", "Above the pack's own 6.0 V protection, so the robot stops cleanly before the pack "
                                 "cuts all power."],
    ["Power off through the relay", "The main switch also cuts Linux. A button in the app shuts it down first, with "
                                    "no shell access needed; the sudoers rule allows only that one command."],
    ["Halt, not poweroff", "On USB power this board starts again within seconds of a poweroff, but stays down "
                           "about 45 s after a halt, with the microcontroller still showing the matrix."],
    ["Ramp the wheels, stagger the servos, relax the open gripper", "Fewer current spikes on the shared pack. The base "
                                                                     "stays powered because the arm can be knocked while driving."],
    ["Gamepad paired to the board, read by the relay", "Drives without a phone, and the phone still works. Going through "
                                                        "the relay's queue reuses its allowlist, power-off and restart handling."],
    ["Wheel-speed command m L R", "Lets the relay mix one stick into smooth curves (or drive tank style); the existing "
                                  "ramp works per wheel."],
    ["Gamepad owns the wheels while driving", "Phone and pad pulses would otherwise fight every 150 ms. Stop always works."],
], [2.3 * inch, 4.2 * inch])
H2("Problems found and fixed")
TABLE([
    ["Problem", "Cause", "Fix"],
    ["Phone could not connect", "Relay never installed; board had no internet for setup.sh",
     "Packages bundled on the PC, pushed with adb, run as user 'arduino', started by cron"],
    ["Relay got \"method robot not available\"", "Board still had the first sketch version, from before the "
     "Bluetooth work", "Compiled and uploaded the current sketch with arduino-cli"],
    ["pip downloaded the wrong packages", "Dependency markers were evaluated for Windows, not the board",
     "Downloaded exactly five pinned packages with --no-deps"],
    ["sdkmanager no longer manages licenses", "Google replaced it with the 'android' CLI, which collects usage data",
     "Read the license, user accepted it, downloaded packages directly"],
    ["Keyboard driving did not start in a test", "Handler assumed every key event came from an element",
     "Guarded the check; real keypresses and synthetic ones now both work"],
    ["Matrix preview stayed blank in the in-app browser", "requestAnimationFrame does not fire there",
     "Switched to a 20 ms timer (also keeps running when the window is covered)"],
    ["Relay start command killed itself", "pkill -f matched its own command line", "Used the pattern [r]obot_ble_bridge.py"],
    ["Commands could run at the same time as loop()", "Bridge (Arduino_RPClite 0.3.x) runs \"safe\" handlers on its own "
     "thread, not between loop() passes", "A Zephyr mutex around commands and loop(); confirmed with a thread-ID test build"],
    ["Relay never started after a reboot", "The arduino user's password is marked expired, so cron refuses its @reboot job",
     "Set a password with Arduino's arduino-passwd tool (Section 6, B4)"],
    ["Sketch unreachable after a reboot", "A Linux-only reboot doesn't reset the microcontroller; it stays registered "
     "with the old router", "The relay resets the microcontroller through arduino-reset.sh when the sketch doesn't answer"],
], [1.9 * inch, 2.3 * inch, 2.3 * inch])
H2("Tool and package versions")
TABLE([
    ["Area", "Versions"],
    ["Microcontroller", "Arduino Q Boards (arduino:zephyr) 1.0.0, arduino-cli 1.5.1, Arduino_RouterBridge, "
                        "Adafruit PWM Servo Driver Library, Arduino_LED_Matrix (bundled)"],
    ["Board Linux", "Debian 13, Python 3.13.5, BlueZ; relay packages bless 0.3.0, bleak 3.0.2, "
                    "dbus-fast 5.2.0, dbus-next 0.2.3, msgpack 1.2.3"],
    ["Android", "Gradle 8.9, Android Gradle Plugin 8.7.3, Kotlin 2.0.21, compileSdk / targetSdk 35, minSdk 26, "
                "build-tools 34.0.0, JDK 21"],
    ["Tools on the PC", "Android SDK in D:\\Android\\Sdk (platform 35 r02, build-tools 34.0.0, "
                        "platform-tools 37.0.1), Python 3.12 for the desktop server"],
], [1.4 * inch, 5.1 * inch])

# ---------------------------------------------------------------- 6 install
H1("Installation", "Section 6")
P("Install in this order: the sketch, then the relay, then a controller. Each step ends with a "
  "check that proves its seam works before moving on.", "lead")
H2("Prerequisites")
TABLE([
    ["Needed for", "What"],
    ["Sketch", "Arduino IDE 2 (or arduino-cli) with the Arduino Q Boards package and the two libraries"],
    ["Relay", "USB cable and adb (Android platform-tools), or SSH and internet on the board"],
    ["Android app", "JDK 17 or newer, the Android SDK parts below (or Android Studio), a USB cable"],
    ["Desktop controller", "Python 3 and Chrome or Edge, on a PC with Bluetooth"],
], [1.5 * inch, 5.0 * inch])

H2("A. The sketch (microcontroller)")
NUM([
    "In Arduino IDE 2: <b>Boards Manager</b> - install <b>Arduino Q Boards</b>. <b>Library Manager</b> - install "
    "<b>Arduino_RouterBridge</b> and <b>Adafruit PWM Servo Driver Library</b>.",
    "Open RobotRover.ino (RobotMatrix.h must sit in the same folder), select <b>Arduino UNO Q</b>, and upload. "
    "Or from a terminal in the project folder:",
])
CODE("arduino-cli compile -b arduino:zephyr:unoq .\n"
     "arduino-cli upload  -b arduino:zephyr:unoq -p COM13 .     # use your board's port")
P("<b>Check:</b> the LED matrix shows the idle face. In the Serial Monitor (line ending \"New Line\"), "
  "<font face='Courier'>pos</font> answers with the joint angles.")
P("<b>Battery gauge:</b> once the 20k / 10k divider is wired to A0, set "
  "<font face='Courier'>BATTERY_SENSE = true</font> in RobotRover.ino and upload again. Compare "
  "<font face='Courier'>batt</font> with a multimeter on the pack and adjust "
  "<font face='Courier'>BATT_CAL</font> until they agree.")

H2("B. The Bluetooth relay (board Linux side)")
H3("Option 1: offline over USB (how the current board is set up)")
NUM([
    "Install Android platform-tools to get adb, and check the board is listed with "
    "<font face='Courier'>adb devices</font>.",
    "On the PC, download the five packages built for the board (aarch64, Python 3.13) and unpack them "
    "into a <font face='Courier'>lib</font> folder next to the relay files:",
])
CODE("python -m pip download --no-deps --only-binary=:all: --dest wheels \\\n"
     "    --platform manylinux2014_aarch64 --platform manylinux_2_28_aarch64 \\\n"
     "    --python-version 3.13 --implementation cp --abi cp313 --abi none \\\n"
     "    bless==0.3.0 bleak==3.0.2 dbus-fast==5.2.0 dbus-next==0.2.3 msgpack==1.2.3\n"
     "# unzip every .whl in wheels/ into robot-ble/lib/  (a wheel is a zip file)")
NUM(start=3, items=[
    "Copy the libraries and the three relay files to <font face='Courier'>/home/arduino/robot-ble/</font> "
    "(from the project folder), then make the scripts executable and start the relay at boot:",
])
CODE("adb shell \"mkdir -p ~/robot-ble\"\n"
     "adb push robot-ble/lib /home/arduino/robot-ble/\n"
     "adb push board/robot_ble_bridge.py board/robot_gamepad.py /home/arduino/robot-ble/\n"
     "adb push board/run.sh board/keepalive.sh board/pair-gamepad.sh /home/arduino/robot-ble/\n"
     "adb shell \"chmod +x ~/robot-ble/*.sh\"\n"
     "# note: the next line replaces the arduino user's crontab (it is empty on a fresh board)\n"
     "adb shell \"echo '@reboot /home/arduino/robot-ble/keepalive.sh' | crontab -\"\n"
     "adb shell \"cd ~/robot-ble && setsid nohup ./keepalive.sh >/dev/null 2>&1 </dev/null &\"")
NUM(start=4, items=[
    "<b>Set a password for the arduino user.</b> A fresh board's password is marked expired, and cron skips "
    "the @reboot job until it is changed. In <font face='Courier'>adb shell</font> on the board, run Arduino's "
    "own tool <font face='Courier'>sudo /usr/local/bin/arduino-passwd</font>, type the new password and press "
    "Enter. It doesn't ask for the old password or a sudo password. <font face='Courier'>chage -l arduino</font> "
    "should then say the password never expires.",
    "<b>Allow Power off</b> (optional, needed for the app's Power off button). In "
    "<font face='Courier'>adb shell</font> on the board, add a sudoers rule that allows only that one command:",
])
CODE("echo 'arduino ALL=(root) NOPASSWD: /usr/bin/systemctl halt' \\\n"
     "    | sudo tee /etc/sudoers.d/robot-poweroff\n"
     "sudo chmod 440 /etc/sudoers.d/robot-poweroff && sudo visudo -c")
P("<b>Check S4/S5:</b> <font face='Courier'>adb shell \"cd ~/robot-ble &amp;&amp; ./run.sh --send pos\"</font> "
  "prints the joint angles. <b>Check S2:</b> <font face='Courier'>adb shell \"bluetoothctl show\"</font> lists the "
  "Nordic UART Service, and <font face='Courier'>~/robot-ble/relay.log</font> says \"Advertising as 'RobotRover'\".")
H3("Option 2: standard install (board has internet)")
P("Copy the <font face='Courier'>board</font> folder to the board (scp or adb push) and run "
  "<font face='Courier'>bash setup.sh</font>. It installs packages with apt and pip, puts the relay in "
  "<font face='Courier'>/opt/robot-ble</font> and runs it as a root systemd service "
  "(<font face='Courier'>robot-ble-bridge</font>). It asks for the sudo password. Running as root, the relay "
  "can power the board off without the sudoers rule.")

H2("C. The Android app")
NUM([
    "Get the SDK parts: either install Android Studio, or download <b>platform 35</b> and <b>build-tools "
    "34.0.0</b> from Google's repository (the Android SDK License Agreement applies) into a folder such as "
    "D:\\Android\\Sdk, and point <font face='Courier'>android/local.properties</font> at it "
    "(<font face='Courier'>sdk.dir=D\\:\\\\Android\\\\Sdk</font>).",
    "Build with a JDK 17+ as JAVA_HOME:",
])
CODE("cd android\n"
     "gradlew.bat assembleDebug          # output: app/build/outputs/apk/debug/RobotRover.apk")
NUM(start=3, items=[
    "Plug the phone in with <b>File transfer</b> on and copy the APK to its <b>Download</b> folder.",
    "On the phone: <b>Files - Downloads</b>, tap the APK, allow <b>Install unknown apps</b> for Files, tap "
    "<b>Install</b>, and choose <b>Install anyway</b> if Play Protect warns.",
])
P("<b>Check:</b> open RobotRover, tap <b>Connect to robot</b>, allow the Bluetooth permission. The pill turns "
  "green; Home or Open/Close produce replies and matrix icons.")

H2("D. The desktop controller")
CODE("python desktop/serve.py            # opens http://localhost:8765 in your browser")
P("Use Chrome or Edge. <b>Try demo</b> works without hardware; <b>Connect to robot</b> opens the browser's "
  "Bluetooth device picker. Keyboard: W/A/S/D or arrows to drive, Space stop, O/C/H gripper and home.")

H2("E. The gamepad (optional)")
NUM([
    "Put the 8BitDo SF30 Pro in <b>D-input (Android) mode</b>: hold <b>Start + B</b> to switch it on. Then "
    "hold <b>Pair</b> for 3 s until the lights blink quickly.",
    "On the board, run the pairing script. It looks for the controller for up to 2 minutes, then pairs, "
    "trusts and connects it:",
])
CODE("adb shell \"cd ~/robot-ble && ./pair-gamepad.sh\"")
NUM(start=3, items=[
    "Check the map: <font face='Courier'>adb shell \"cd ~/robot-ble &amp;&amp; ./run.sh --gamepad-test\"</font> "
    "prints each button and stick as you press it. If a label is wrong, edit BUTTONS at the top of "
    "robot_gamepad.py and push it again.",
])
P("<b>Check:</b> relay.log says \"gamepad connected\", and pushing both sticks forward shows the forward "
  "arrows on the matrix. Afterwards, switching the controller on in D-input mode connects it again by itself.")

H2("Verification checklist")
TABLE([
    ["#", "Check", "Proves"],
    ["1", "Matrix shows the idle face after power-on", "Sketch running (S7)"],
    ["2", "Serial Monitor: pos answers", "Sketch command handling (S1)"],
    ["3", "./run.sh --send pos answers on the board", "Relay - router - sketch (S4, S5)"],
    ["4", "bluetoothctl show lists the Nordic UART Service", "Relay advertising (S2)"],
    ["5", "Phone connects and Home gets \"arm going home\"", "Whole chain (S2 to S7)"],
    ["6", "Hold an arrow, then turn the phone's Bluetooth off: wheels stop within 0.4 s", "Drive safety"],
    ["7", "Reboot the board; phone reconnects after about a minute (needs the password set, step B4)", "Boot autostart (S9)"],
    ["8", "batt answers (\"battery sensing off\" until the divider is wired)", "Battery gauge (S6)"],
    ["9", "Power off in the app: power symbol, then the sleeping face; Linux shuts down", "Safe shutdown (S4, S7)"],
    ["10", "Gamepad: both sticks forward drives; letting go stops; switching it off mid-drive stops", "Gamepad (S10)"],
], [0.3 * inch, 3.9 * inch, 2.3 * inch])

# ---------------------------------------------------------------- 7 testing
H1("What has been tested", "Section 7")
TABLE([
    ["Verified", "How"],
    ["Phone app connects to the board over Bluetooth", "On the real phone (moto g stylus 5G 2023) and board"],
    ["Relay - router - sketch round trip", "./run.sh --send pos and home on the board"],
    ["Relay advertising and autostart setup", "bluetoothctl show; keep-alive running; crontab entry present"],
    ["Sketch compiles for the UNO Q and uploads", "arduino-cli 1.5.1, and 0.32.2 (bundled with Arduino IDE 2); "
                                                  "Arduino Q Boards 1.0.0"],
    ["Android app builds cleanly", "Gradle 8.9 / AGP 8.7.3, no compiler warnings; APK permissions inspected with aapt2"],
    ["RobotMatrix.h drawing logic", "Compiled on the PC with g++ -Wall and stubs; 38 frames checked"],
    ["C++ and JavaScript matrix match", "Pixel-identical frames for the same inputs, including battery and power-off icons"],
    ["Desktop demo mode, keyboard and console", "Automated checks in a browser"],
    ["Desktop demo: batt, Power off, refused moves", "Script-driven checks in Node with a stub page"],
    ["Relay protocol code and allowlist", "Unit test against a fake router, including the error path"],
    ["Commands run on a different thread from loop()", "Thread-ID test build on the board"],
    ["The command lock under load", "300 commands in 2.7 s through the router on the board, no lost replies"],
    ["batt, poweroff, poweroff 0 and the move lockout", "On the board through arduino-router"],
    ["Power off refused without the sudoers rule", "On the board: the phone is told why, the robot carries on"],
    ["Power off all the way down", "On the board (USB power): Linux shut down cleanly; after a halt the "
                                   "matrix showed the sleeping face and the board stayed down about 45 s"],
    ["Wheel ramp, gripper relax and battery states", "Unit tests on the PC with g++"],
    ["Tank drive command m", "On the board: m 200 200 300, m -120 150, clamping, a malformed m rejected"],
    ["Gamepad logic", "Unit tests on the PC: one-stick and tank drive, dead zone, pulses, arm steps, clamped replies, buttons, "
                      "power-off hold, disconnect"],
    ["Gamepad end to end", "On the board with a virtual SF30 Pro (Linux uinput): the relay found it, drove, moved "
                           "the base, opened and closed, changed speed, went home, and stopped when it vanished"],
    ["Relay autostart and sketch restart after a reboot", "sudo reboot on the board: relay started from cron, reset the "
                                                         "microcontroller, sketch answered 46 s after boot"],
], [3.0 * inch, 3.5 * inch])
TABLE([
    ["Not yet verified", "Notes"],
    ["Motors, servos and the PCA9685 in the robot", "Not wired yet; test on a stand first"],
    ["Battery gauge on a real pack", "Divider not wired yet; calibrate against a multimeter"],
    ["Power off on battery power", "On USB power the board starts again about 45 s after Power off; on battery it may stay off"],
    ["Gripper relaxing saves current", "Some digital servos keep holding with no pulses"],
    ["LED matrix brightness levels on the real board", "Conflicting reports online about the grayscale range"],
    ["Desktop controller over real Bluetooth", "Demo mode only so far"],
    ["Wheels stop when the link drops", "Logic is in place; check with item 6 of the checklist"],
    ["Driving with the real SF30 Pro", "Paired; it reconnects by itself and its axes and buttons match the map. "
                                   "Driving with the left stick still to be tried"],
    ["Phone and gamepad at the same time", "The drive hand-over is in place but untested with a real phone"],
    ["Cold start from the battery switch", "Both processors start together; the relay's 20 s wait should cover the "
                                           "sketch's start-up, and it resets the microcontroller if not"],
], [3.0 * inch, 3.5 * inch], head_color=ACCENT)

# ---------------------------------------------------------------- 8 security
H1("Security and privacy", "Section 8")
BUL([
    "<b>No accounts anywhere.</b> No Arduino Cloud, no Google sign-in, no App Lab account.",
    "<b>Nothing phones home.</b> The Android app has no internet permission. The desktop page loads nothing "
    "from the internet and its server only listens on 127.0.0.1. Google's new 'android' SDK tool (which "
    "collects usage data by default) was not used for installs; its two help commands were run once "
    "before that was known.",
    "<b>Bluetooth is open.</b> There is no pairing or PIN, so anyone nearby with a Bluetooth app could "
    "connect while the relay runs. The relay's allowlist means they can only send robot commands, never "
    "anything to the Linux system. Stop the relay when not in use, or add a PIN in the relay as a future step.",
    "<b>Power off is open too.</b> Anyone who can connect can shut the board down, the same exposure as "
    "driving it.",
    "<b>Least privilege.</b> The relay runs as the normal 'arduino' user, not root. Its one extra right is the "
    "sudoers rule for <font face='Courier'>systemctl halt</font>, which allows that command and nothing else.",
    "<b>Downloads were verified.</b> Every SDK and Gradle download was checked against the publisher's SHA-1 "
    "or SHA-256; Python packages came from pypi.org over HTTPS with pip's hash checks.",
    "<b>License.</b> Building the Android app uses Google's Android SDK, under the Android SDK License "
    "Agreement (accepted for this project). The RobotRover code itself does not depend on it at runtime.",
])

# ---------------------------------------------------------------- 9 troubleshooting
H1("Troubleshooting by seam", "Section 9")
TABLE([
    ["Symptom", "Seam", "Check"],
    ["App: \"Robot not found\"", "S2", "Relay running? tail ~/robot-ble/relay.log; bluetoothctl show (Powered: yes). "
                                       "Android 11 or older: Location on."],
    ["Replies say \"robot restarting, try again in a few seconds\"", "S4/S5",
     "The relay found the sketch unregistered (usually after a reboot) and is restarting it. If it keeps "
     "happening, re-upload RobotRover.ino."],
    ["run.sh --send says 'robot' failed ... not available", "S4/S5",
     "Same cause: ./run.sh --reset-mcu restarts the sketch. If that doesn't help, re-upload RobotRover.ino."],
    ["Replies say error: no answer from 'robot'", "S5", "Sketch stuck or rebooting; check the Serial Monitor."],
    ["Replies say rejected: ...", "S1", "The command is not in the allowlist (expected for help or typos)."],
    ["Matrix blank", "S7", "Sketch not running; re-upload."],
    ["\"PCA9685 servo board not found\"", "S6", "SDA/SCL wiring, servo board power, shared ground."],
    ["A wheel runs backwards", "S6", "Flip LEFT_REVERSED or RIGHT_REVERSED."],
    ["Desktop: \"This browser can't use Bluetooth\"", "S3", "Use Chrome or Edge, opened through serve.py."],
    ["Relay not running after reboot", "S9", "crontab -l shows the @reboot line; relay.log shows \"relay starting\". "
                                             "journalctl -u cron saying \"expired password\": set one with arduino-passwd."],
    ["Replies say battery empty ... charge me", "S6", "Charge the pack. Moves unlock once it reads 6.8 V or more."],
    ["batt says battery not connected", "S6", "Pack switched off, or the divider isn't wired to A0."],
    ["Power off says not allowed", "S4", "Add the sudoers rule (Section 6, B5)."],
    ["Gamepad does nothing", "S10", "relay.log should say \"gamepad connected\". If not: switch it on in D-input "
                                     "mode (Start + B), or pair it again with pair-gamepad.sh."],
    ["Gamepad buttons do the wrong thing", "S10", "Run ./run.sh --gamepad-test and fix BUTTONS in robot_gamepad.py."],
    ["Phone's drive buttons don't work", "S10", "The gamepad is driving; the phone gets the wheels 0.5 s after its sticks are released."],
    ["Board resets when the motors or servos start", "S6", "Board regulator not buck-boost or too small, servo "
                                                           "regulator too small, or grounds not shared."],
], [2.2 * inch, 0.6 * inch, 3.7 * inch])

# ---------------------------------------------------------------- 10 code map + files
# Line counts are a rounded snapshot of release 1.2 (git-tracked text files; images excluded).
CODE_LOGIC = colors.HexColor("#2563EB")
CODE_MARKUP = colors.HexColor("#93C5FD")
CODE_CONFIG = colors.HexColor("#A8A49A")
CODE_GENERATED = colors.HexColor("#D8D5CD")

CODE_MAP = [
    # name, path, rounded label, [(exact lines, kind), ...] (exact values only set the bar proportions)
    ("Android app", "android/", "~2,090", [(641, CODE_LOGIC), (982, CODE_MARKUP), (123, CODE_CONFIG), (346, CODE_GENERATED)]),
    ("Sketch", "RobotRover.ino, RobotMatrix.h", "~990", [(993, CODE_LOGIC)]),
    ("Relay and gamepad", "board/", "~840", [(737, CODE_LOGIC), (100, CODE_CONFIG)]),
    ("Desktop controller", "desktop/", "~830", [(652, CODE_LOGIC), (127, CODE_MARKUP), (46, CODE_CONFIG)]),
    ("Docs and repo config", "README.md, .git*", "~450", [(445, CODE_CONFIG)]),
]

def code_map_chart():
    """Horizontal stacked bars: lines per folder, split by kind of code."""
    W = 480
    name_w, count_w, row_h, bar_h = 168, 52, 32, 15
    bar_x0, bar_w = name_w, W - name_w - count_w
    longest = max(sum(n for n, _ in segs) for _, _, _, segs in CODE_MAP)
    legend_h = 24
    H = len(CODE_MAP) * row_h + legend_h
    d = Drawing(W, H)
    for i, (name, path, rounded, segs) in enumerate(CODE_MAP):
        y_mid = H - (i + 0.5) * row_h
        label(d, 0, y_mid + 2, name, 8.8, INK, "start", True)
        d.add(String(0, y_mid - 9, check_text(path), fontName="Courier", fontSize=7.2, fillColor=MUTED))
        x = bar_x0
        for n, col in segs:
            w = bar_w * n / longest
            d.add(Rect(x, y_mid - bar_h / 2, w, bar_h, fillColor=col, strokeColor=colors.white, strokeWidth=0.6))
            x += w
        label(d, W, y_mid - 3, rounded, 8.8, INK, "end", True)
    items = [(CODE_LOGIC, "Logic you'd edit"), (CODE_MARKUP, "UI markup and styles"),
             (CODE_CONFIG, "Build config, scripts, docs"), (CODE_GENERATED, "Generated by Gradle")]
    x = 0
    for col, text in items:
        d.add(Rect(x, 3, 9, 9, rx=2, ry=2, fillColor=col, strokeColor=None))
        label(d, x + 13, 5, text, 7.4, MUTED, "start")
        x += 13 + stringWidth(text, "Helvetica", 7.4) + 18
    return d

H1("Code map and file map", "Section 10")
P("Where the code lives, what each part is written in, and what it builds. Line counts are rounded and "
  "were taken at release 1.2, so they drift as the code changes.", "lead")
story.append(KeepTogether([
    Paragraph("Lines per folder", S["h2"]),
    code_map_chart(),
    Paragraph(check_text("Figure 7. About 5,200 lines of text files in git at release 1.2 (about 4,000 at the "
                         "first release). Images, including the SVG sources, and the PDF are not counted, and "
                         "neither is docs/build_pdf.py."),
              S["caption"]),
]))
P("<b>The Android folder is almost half the line count, but mostly screens and icons.</b> The sketch now has "
  "the most logic: about 990 lines of C++, then 740 of Python in the relay and gamepad support, 650 of "
  "JavaScript in the desktop page, and 640 of Kotlin in the app.")

H2("What each part builds")
TABLE([
    ["Part", "Logic", "Builds with", "Produces", "Runs on"],
    ["Sketch", "~990 lines C++", "arduino-cli 1.5.1 or Arduino IDE 2, board arduino:zephyr:unoq",
     "Firmware, about 125 KB (15% of flash)", "UNO Q's STM32U585"],
    ["Android app", "~640 lines Kotlin", "Gradle 8.9, Android Gradle Plugin 8.7.3, Kotlin 2.0.21",
     "RobotRover.apk, about 860 KB", "Android 8 or newer"],
    ["Desktop controller", "~650 lines JavaScript", "No build step; desktop/serve.py serves it",
     "A page at localhost:8765", "Chrome or Edge on a PC"],
    ["Bluetooth relay", "~740 lines Python", "No build step; copied to the board with adb",
     "A Bluetooth service named RobotRover", "UNO Q's Linux side"],
    ["This document", "~1,480 lines Python", "python docs/build_pdf.py (needs reportlab)",
     "This PDF", "Any PC with Python 3"],
], [1.05 * inch, 1.05 * inch, 1.8 * inch, 1.4 * inch, 1.2 * inch], font_rows=True)
P("Only the sketch and the Android app have a real build step. The relay and the desktop page run as plain "
  "source files.")

H2("File map")
TABLE([
    ["Path", "What it is", "Size"],
    ["RobotRover.ino", "The sketch: commands, wheels, servos, battery gauge, tank drive, Bridge registration", "~590 lines"],
    ["RobotMatrix.h", "LED matrix icons and face (part of the sketch)", "~400 lines"],
    ["board/robot_ble_bridge.py", "The Bluetooth relay: MessagePack-RPC client, allowlist, power-off, sketch restart", "~370 lines"],
    ["board/robot_gamepad.py", "Gamepad support: finds and reads the 8BitDo, turns it into commands, --gamepad-test", "~370 lines"],
    ["board/pair-gamepad.sh", "Pairs, trusts and connects the gamepad with bluetoothctl", "~35 lines"],
    ["board/run.sh, board/keepalive.sh", "Run the relay with bundled libraries; keep it running (offline install)", "~15 lines"],
    ["board/setup.sh, board/robot-ble-bridge.service", "Standard install with apt/pip and a systemd service", "~50 lines"],
    ["android/", "Android app (Kotlin). Gradle wrapper included; local.properties is per-PC and not in git", "~2,090 lines"],
    ["android/app/src/main/java/.../RobotBle.kt", "Bluetooth LE client: scan, connect, queue, notifications", "~310 lines"],
    ["android/app/src/main/java/.../MainActivity.kt", "Screen logic: drive pulses, sliders, status, log, power off", "~330 lines"],
    ["android/app/src/main/res/", "Layout, theme, colors, icons, launcher icon (XML)", "~980 lines"],
    ["desktop/index.html", "Desktop controller, demo model and matrix preview (ports of sketch code)", "~780 lines"],
    ["desktop/serve.py", "Local web server on 127.0.0.1:8765", "~50 lines"],
    ["docs/build_pdf.py", "Generates this document; draws every figure except the app and wiring images", "~1,480 lines"],
    ["README.md", "Quick start and reference", "-"],
    ["RobotRover_System_Guide.pdf", "This document", "-"],
    ["images/", "App mockup, board pinout and wiring images (used in the README and this document), with "
                "the SVG sources of the pinout and the wiring diagram", "-"],
], [2.45 * inch, 3.2 * inch, 0.85 * inch])
CALLOUT("Not in the repository.",
        "Build outputs (the APK and the firmware); the five Python packages bundled for the relay on the board "
        "(Section 6 has the download command); Arduino's arduino-router, which comes with the board; "
        "android/local.properties, which is specific to each PC; and the HTML page used to render "
        "images/app_mockup.png.")

# ---------------------------------------------------------------- build
doc = SimpleDocTemplate(
    OUT, pagesize=letter,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch, topMargin=0.85 * inch, bottomMargin=0.8 * inch,
    title="RobotRover - System Guide", author="RobotRover project",
    subject="System design, build notes and installation guide", creator="reportlab",
)
doc.build(story, onFirstPage=cover, onLaterPages=later)
print("wrote", OUT)
