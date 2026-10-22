"""
Builds RobotRover_System_Guide.pdf from the repository's own files.

    pip install reportlab
    python docs/build_pdf.py                 # writes RobotRover_System_Guide.pdf in the repo root
    python docs/build_pdf.py other.pdf       # or to another path

Inputs: images/app_mockup.png and images/wiring.png. Every other figure (architecture,
command sequence, board pinout, LED matrix frames) is drawn here in code.

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
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "RobotRover_System_Guide.pdf")
APP_IMG = os.path.join(ROOT, "images", "app_mockup.png")   # 808 x 2206 px render of the app
WIRING_IMG = os.path.join(ROOT, "images", "wiring.png")    # 2299 x 1364 px

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
    d.add(Rect(0, 222, 150, 104, rx=8, ry=8, fillColor=colors.white, strokeColor=RULE, strokeDashArray=[3, 2]))
    label(d, 8, 316, "CONTROLLERS", 6.8, MUTED, "start", True)
    d.add(Rect(170, 4, 298, 322, rx=8, ry=8, fillColor=colors.white, strokeColor=RULE, strokeDashArray=[3, 2]))
    label(d, 178, 316, "ARDUINO UNO Q", 6.8, MUTED, "start", True)
    d.add(Rect(180, 172, 278, 136, rx=6, ry=6, fillColor=GRAY_LIGHT, strokeColor=GRAY_LIGHT))
    label(d, 188, 298, "Linux side - Qualcomm QRB2210, Debian 13", 6.8, SLATE, "start", True)
    d.add(Rect(180, 14, 278, 148, rx=6, ry=6, fillColor=GRAY_LIGHT, strokeColor=GRAY_LIGHT))
    label(d, 188, 152, "Microcontroller - STM32U585, Zephyr", 6.8, SLATE, "start", True)

    box(d, 10, 270, 130, 36, "Android app", "android/ - Kotlin", BLUE_LIGHT, BLUE)
    box(d, 10, 228, 130, 36, "Desktop controller", "desktop/ - Chrome or Edge", BLUE_LIGHT, BLUE)
    box(d, 192, 226, 118, 60, "Bluetooth relay", "robot_ble_bridge.py", TEAL_LIGHT, TEAL, "Python, user 'arduino'")
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
    badge(d, 168, 262, "S2", BLUE)
    badge(d, 160, 213, "S3", BLUE)
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
    W, H = 468, 470
    bx, by = 69, 116                          # board's bottom-left corner in the drawing
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
    label(d, X, Y - 8, "PC link, power", 6.2, MUTED, "end")

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
             ("3.3V", "logic power (VCC)", GND), ("5V", "not for motors/servos", None),
             ("GND", "common ground", GND), ("GND", "", None), ("VIN", "not for motors/servos", None)]
    analog = [(f"A{i}", "", None) for i in range(6)]
    header(power, 28.0, 50.8, False)
    header(analog, 50.9, 50.8, False)

    # ---- legend
    items = [(BLUE, "Left wheel: motor driver channel A"), (PINK, "Right wheel: channel B"),
             (PURPLE, "Servo board (I2C)"), (GND, "Power / ground"), (ACCENT, "On-board LED matrix")]
    widths = [13 + stringWidth(t, "Helvetica", 6.6) for _, t in items]
    gap = (W - sum(widths)) / (len(items) - 1)
    x = 0
    for (col, text), w in zip(items, widths):
        d.add(Rect(x, 2, 9, 9, rx=2, ry=2, fillColor=col, strokeColor=None))
        label(d, x + 13, 4, text, 6.6, INK, "start")
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
]

def matrix_grid():
    """3 x 3 grid of large LED matrix frames, each with a name and when it appears."""
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
TODAY = date(2026, 10, 22).strftime("%B %d, %Y").replace(" 0", " ")

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
    c.drawString(0.9 * inch, 1.1 * inch, f"Version 1.1  -  {TODAY}")
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
    c.drawString(0.9 * inch, 0.55 * inch, f"Version 1.1  -  {TODAY}")
    c.restoreState()

# =================================================================
#  CONTENT
# =================================================================
story.append(Spacer(1, 1))   # cover page is drawn by cover()

# ---------------------------------------------------------------- 1 at a glance
H1("At a glance", "Section 1")
P("RobotRover is a small two-wheeled robot with a four-joint arm, driven from an Android phone "
  "or a desktop browser over Bluetooth. The brain is an <b>Arduino UNO Q</b>, a board with two "
  "processors: a Qualcomm chip running Debian Linux, and an STM32 microcontroller running the "
  "Arduino sketch. The board's 13 x 8 LED matrix shows what the robot is doing: an icon for each "
  "command, then a little face that reacts.", "lead")
P("The design goal was a system that is <b>fully open source, needs no accounts, and works without "
  "an internet connection</b> once installed. Every tool used is either open source or downloaded "
  "directly from its publisher with checksum verification, and no component phones home.")
story.append(architecture_diagram())
CAPTION("Figure 1. The components and the seams between them (S1, the command language, is shared by "
        "every seam and is not drawn). S8 and S9 are build-time seams and are covered in Section 4.")
H2("Why there are so many pieces")
P("The UNO Q's Bluetooth radio is wired to the Linux processor, not to the microcontroller that "
  "drives the motors. So a phone command has to land on the Linux side first and then be handed "
  "across to the microcontroller. Arduino provides that hand-off: a broker called "
  "<font face='Courier'>arduino-router</font> on Linux and a library called <b>Bridge</b> in the "
  "sketch, connected by an internal serial link. RobotRover adds a small Python program, the "
  "<b>relay</b>, that speaks Bluetooth to the phone on one side and the router's protocol on the other.")
TABLE([
    ["Component", "Runs on", "Language", "Job"],
    ["Android app", "Phone (Android 8+)", "Kotlin, no libraries", "Drive pad, arm sliders, shows replies"],
    ["Desktop controller", "PC browser (Chrome/Edge)", "HTML + JavaScript", "Same controls, keyboard, console, demo mode, matrix preview"],
    ["Bluetooth relay", "UNO Q, Linux side", "Python 3.13", "Bluetooth LE server; checks commands; forwards to the sketch"],
    ["arduino-router", "UNO Q, Linux side", "Go (Arduino's)", "Message broker between Linux programs and the microcontroller"],
    ["RobotRover sketch", "UNO Q, microcontroller", "C++ (Arduino, Zephyr)", "Runs commands: wheels, servos, safety timeouts"],
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
    ["Gripper servo", "PCA9685 channel 3", "30 (open) - 120 (closed) deg, home 30"],
    ["LED matrix", "Built into the UNO Q", "13 x 8, 3-bit brightness (0 - 7)"],
], [1.5 * inch, 1.85 * inch, 3.15 * inch])
CALLOUT("Power.", "Motors and servos run from their own batteries, never from the UNO Q's 5 V pin. "
        "All grounds (board, motor driver, servo board, batteries) must be connected together.")
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
    Paragraph(check_text("How the UNO Q, the TB6612FNG motor driver, the PCA9685 servo board, the motors, servos "
                         "and batteries connect. Wire colors match Figure 3: blue left wheel, pink right wheel, "
                         "purple I2C and servo cables, orange 3.3 V logic, red power, black ground."), S["body"]),
    Image(WIRING_IMG, width=_ww, height=_ww * 1364 / 2299),
    Paragraph(check_text("Figure 4. Wiring for RobotRover (schematic, not to scale). Pins match RobotRover.ino."),
              S["caption"]),
]))
H3("Rules that matter")
BUL([
    "<b>Never power motors or servos from the UNO Q.</b> The board runs from a USB-C supply (Arduino specifies "
    "5 V, 3 A); the motors and servos each get their own battery.",
    "<b>All grounds connect together:</b> UNO Q GND, both TB6612 GND pins, PCA9685 GND and both batteries' (-).",
    "<b>STBY must be tied high</b> (to 3.3 V), or the TB6612 ignores every command.",
    "<b>Logic is 3.3 V.</b> TB6612 VCC and PCA9685 VCC take 3.3 V from the board; the high-current power goes "
    "only to VM (motors, 6 - 9 V, TB6612 maximum 13.5 V) and V+ (servos, 5 - 6 V, 3 A or more).",
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
    "<b>Sketch:</b> Bridge runs the <font face='Courier'>robot</font> handler between two passes of "
    "<font face='Courier'>loop()</font>. It parses the command, clamps 45 to the base's limits, sets the "
    "target angle, tells the LED matrix, and returns the reply <font face='Courier'>base -&gt; 45</font>.",
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
              "Each command shows its icon first; the face reacts afterwards.",
              S["caption"]),
]))
H2("Driving is a stream of short pulses")
P("Holding a drive arrow does not send \"drive forever\". The app sends "
  "<font face='Courier'>w 400</font> (forward for 400 ms) every 150 ms. Each pulse restarts the "
  "sketch's 400 ms timer. Releasing the button sends <font face='Courier'>x</font> (stop). If anything "
  "between the phone and the motors fails (Bluetooth drops, the app is backgrounded, the relay "
  "restarts), the pulses stop arriving and the wheels stop on their own within 400 ms. The same rule "
  "is used by the desktop controller.")

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
    ["x  or  stop", "Stop the wheels", "stopped"],
    ["speed N", "Wheel speed 0 - 255 (default 180)", "speed 200"],
    ["base | shoulder | elbow | grip N", "Move a joint to N degrees, clamped to its limits", "base -> 45,  base -> 180 (limit 0-180)"],
    ["open | close | home", "Gripper open / closed, whole arm to home", "gripper opening, arm going home"],
    ["pos", "Report targets and speed", "base 90 shoulder 90 elbow 90 gripper 30 speed 180"],
    ["help  (Serial Monitor only)", "Print the command list to the Serial Monitor", "help printed to Serial Monitor"],
], [1.75 * inch, 2.75 * inch, 2.0 * inch])
story.append(CondPageBreak(1.7 * inch))
P("<b>Rules:</b> one command per line, lower case, single spaces, whole-number values. Replies are "
  "short single lines (they must fit in one Bluetooth packet; the relay truncates at 180 bytes). "
  "The relay only forwards commands matching this allowlist (from "
  "<font face='Courier'>board/robot_ble_bridge.py</font>); everything else is answered with "
  "<font face='Courier'>rejected: ...</font> and never reaches the sketch:")
CODE("^(?:(?:w|a|s|d) \\d{1,5}|w|a|s|d|x|stop|open|close|home|pos\n"
     "  |(?:speed|base|shoulder|elbow|grip) \\d{1,3})$")

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
                   "reconnect attempt on a dropped socket, ignores unrelated messages."],
    ["Router side", "arduino-router (GPL-3.0) brokers calls in a star topology. Methods are registered by "
                    "whoever provides them; here the sketch registers \"robot\"."],
    ["Fails how", "[2, 'method robot not available']: the sketch is not running or is an old version "
                  "without Bridge.provide_safe(\"robot\"). Timeout: the sketch is stuck or rebooting. "
                  "Connection refused: arduino-router is not running."],
    ["Test it", "./run.sh --send pos on the board (no Bluetooth involved). Expected: "
                "base 90 shoulder 90 elbow 90 gripper 30 speed 180."],
])

seam("S5  arduino-router - sketch  (Bridge over the internal UART)", [
    ["Crosses", "The forwarded RPC request and the sketch's reply."],
    ["Format", "MessagePack-RPC over UART /dev/ttyHS1. Handled entirely by Arduino's Bridge library "
               "(Arduino_RouterBridge) in the sketch; RobotRover never touches the bytes."],
    ["Sketch side", "setup() calls Bridge.begin(), Monitor.begin(), then "
                    "Bridge.provide_safe(\"robot\", bridgeCommand). \"Safe\" handlers run in the main thread "
                    "between loop() passes (the core calls __loopHook after each loop), so they never race "
                    "with the motor and servo code. loop() must therefore stay fast and non-blocking."],
    ["Fails how", "A burst of \"invalid packet, expected array\" in the router log right after the "
                  "microcontroller resets is normal (Bridge flushes old data at startup). If the sketch "
                  "blocks in loop(), every command times out at S4."],
    ["Test it", "journalctl -u arduino-router shows the connection; S4's --send test proves S5 too."],
])

seam("S6  Sketch - motors and servos", [
    ["Crosses", "Electrical signals."],
    ["Wheels", "Each motor: one PWM pin (analogWrite 0 - 255) and two direction pins. IN1 high = forward, "
               "IN2 high = reverse, both low = coast. A timed drive stops itself when driveStopAt passes."],
    ["Servos", "Adafruit PCA9685 library over I2C (address 0x40), 50 Hz, angle mapped to 500 - 2500 us. "
               "updateArm() moves each servo 1 degree every 15 ms toward its target, so motion is smooth "
               "and the power draw is spread out."],
    ["Fails how", "\"PCA9685 servo board not found\" on the Serial Monitor at startup: wiring or power. "
                  "Servos jitter or the board resets: servos are powered from the board, or grounds are "
                  "not shared. Note: servos jump to home at power-on because they cannot report position."],
    ["Test it", "Serial Monitor commands (base 45, w 500) with the robot on a stand."],
])

seam("S7  Sketch - LED matrix", [
    ["Crosses", "Two calls: RobotMatrix::onCommand(cmd, hasValue, value) from handleCommand, and "
                "RobotMatrix::update(angles, speed) from every loop()."],
    ["Format", "A 104-byte frame (13 columns x 8 rows, row-major), values 0 - 7, passed to "
               "Arduino_LED_Matrix::draw() after setGrayscaleBits(3). At most one frame every 40 ms."],
    ["Behavior", "An icon for 0.6 - 1.5 s (refreshed while a command repeats), then a face reaction for "
                 "2.5 s, then the idle face (blinks every 4 s, glances every 9 s). The joint dial and claw "
                 "draw the servos' current angles, not the targets."],
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
    ["handleCommand() in RobotRover.ino", "demoSketch()", "Same replies for the full command table, including clamping messages"],
    ["Relay allowlist (Python regex)", "ALLOWED", "Same pattern; demo rejects \"help\" exactly like the real relay"],
    ["updateArm(): 1 degree / 15 ms", "armClock interval", "Dial and claw animate at the same speed"],
    ["RobotMatrix.h (all drawing)", "LM module", "C++ compiled on the PC with g++ and stub libraries; its frames "
                                                 "matched the JavaScript frames pixel for pixel for 10 test cases"],
], [1.9 * inch, 1.9 * inch, 2.7 * inch])

H2("S9  Build and deploy seams")
TABLE([
    ["Path", "Tool", "What crosses", "Notes"],
    ["PC -> phone", "MTP file transfer", "RobotRover.apk", "Sideloaded from the Download folder. Debug-signed; Play Protect may warn."],
    ["PC -> microcontroller", "arduino-cli (inside Arduino IDE 2) on COM13", "Compiled sketch",
     "Upload goes through the board's Linux side, which flashes the STM32 over SWD with OpenOCD."],
    ["PC -> board Linux", "adb (platform-tools 37.0.1) over USB", "Relay files and libraries",
     "The board exposes an ADB interface on USB; no password needed for the arduino user."],
    ["Board boot", "cron @reboot -> keepalive.sh", "Starts the relay", "Restarts it 3 s after any exit."],
], [1.2 * inch, 1.6 * inch, 1.35 * inch, 2.35 * inch])

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
    ["Drive pulse 400 ms every 150 ms", "MainActivity.kt, desktop/index.html"],
    ["Reply length under 180 bytes", "robot_ble_bridge.py (MAX_REPLY_BYTES), app MTU request (185)"],
    ["Matrix shapes and timings", "RobotMatrix.h and the LM module in desktop/index.html"],
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

H2("B. The Bluetooth relay (board Linux side)")
H3("Option 1: offline over USB, no password (how the current board is set up)")
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
     "adb push board/robot_ble_bridge.py board/run.sh board/keepalive.sh /home/arduino/robot-ble/\n"
     "adb shell \"chmod +x ~/robot-ble/*.sh\"\n"
     "# note: the next line replaces the arduino user's crontab (it is empty on a fresh board)\n"
     "adb shell \"echo '@reboot /home/arduino/robot-ble/keepalive.sh' | crontab -\"\n"
     "adb shell \"cd ~/robot-ble && setsid nohup ./keepalive.sh >/dev/null 2>&1 </dev/null &\"")
P("<b>Check S4/S5:</b> <font face='Courier'>adb shell \"cd ~/robot-ble &amp;&amp; ./run.sh --send pos\"</font> "
  "prints the joint angles. <b>Check S2:</b> <font face='Courier'>adb shell \"bluetoothctl show\"</font> lists the "
  "Nordic UART Service, and <font face='Courier'>~/robot-ble/relay.log</font> says \"Advertising as 'RobotRover'\".")
H3("Option 2: standard install (board has internet)")
P("Copy the <font face='Courier'>board</font> folder to the board (scp or adb push) and run "
  "<font face='Courier'>bash setup.sh</font>. It installs packages with apt and pip, puts the relay in "
  "<font face='Courier'>/opt/robot-ble</font> and runs it as a root systemd service "
  "(<font face='Courier'>robot-ble-bridge</font>). It asks for the sudo password.")

H2("C. The Android app")
NUM([
    "Get the SDK parts: either install Android Studio, or download <b>platform 35</b> and <b>build-tools "
    "34.0.0</b> from Google's repository (the Android SDK License Agreement applies) into a folder such as "
    "D:\\Android\\Sdk, and point <font face='Courier'>android/local.properties</font> at it "
    "(<font face='Courier'>sdk.dir=D\\:\\\\Android\\\\Sdk</font>).",
    "Build with a JDK 17+ as JAVA_HOME:",
])
CODE("cd android\n"
     "gradlew.bat assembleDebug          # output: app/build/outputs/apk/debug/app-debug.apk")
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

H2("Verification checklist")
TABLE([
    ["#", "Check", "Proves"],
    ["1", "Matrix shows the idle face after power-on", "Sketch running (S7)"],
    ["2", "Serial Monitor: pos answers", "Sketch command handling (S1)"],
    ["3", "./run.sh --send pos answers on the board", "Relay - router - sketch (S4, S5)"],
    ["4", "bluetoothctl show lists the Nordic UART Service", "Relay advertising (S2)"],
    ["5", "Phone connects and Home gets \"arm going home\"", "Whole chain (S2 to S7)"],
    ["6", "Hold an arrow, then turn the phone's Bluetooth off: wheels stop within 0.4 s", "Drive safety"],
    ["7", "Reboot the board; phone reconnects after about a minute", "Boot autostart (S9)"],
], [0.3 * inch, 3.9 * inch, 2.3 * inch])

# ---------------------------------------------------------------- 7 testing
H1("What has been tested", "Section 7")
TABLE([
    ["Verified", "How"],
    ["Phone app connects to the board over Bluetooth", "On the real phone (moto g stylus 5G 2023) and board"],
    ["Relay - router - sketch round trip", "./run.sh --send pos and home on the board"],
    ["Relay advertising and autostart setup", "bluetoothctl show; keep-alive running; crontab entry present"],
    ["Sketch compiles for the UNO Q and uploads", "arduino-cli 1.5.1, Arduino Q Boards 1.0.0"],
    ["Android app builds cleanly", "Gradle 8.9 / AGP 8.7.3, no compiler warnings; APK permissions inspected with aapt2"],
    ["RobotMatrix.h drawing logic", "Compiled on the PC with g++ -Wall -Wextra and stubs; 10 frames checked"],
    ["C++ and JavaScript matrix match", "Pixel-identical frames for the same inputs"],
    ["Desktop demo mode, keyboard and console", "Automated checks in a browser"],
    ["Relay protocol code and allowlist", "Unit test against a fake router, including the error path"],
], [3.0 * inch, 3.5 * inch])
TABLE([
    ["Not yet verified", "Notes"],
    ["Motors, servos and the PCA9685 in the robot", "Not wired yet; test on a stand first"],
    ["LED matrix brightness levels on the real board", "Conflicting reports online about the grayscale range"],
    ["Desktop controller over real Bluetooth", "Demo mode only so far"],
    ["Wheels stop when the link drops", "Logic is in place; check with item 6 of the checklist"],
    ["Relay restart after a reboot", "Set up but not yet rebooted; checklist item 7"],
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
    "<b>Least privilege.</b> The relay runs as the normal 'arduino' user, not root.",
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
    ["Connects, but replies say error: 'robot' failed ... not available", "S4/S5",
     "The sketch on the board is old or not running. Re-upload RobotRover.ino."],
    ["Replies say error: no answer from 'robot'", "S5", "Sketch stuck or rebooting; check the Serial Monitor."],
    ["Replies say rejected: ...", "S1", "The command is not in the allowlist (expected for help or typos)."],
    ["Matrix blank", "S7", "Sketch not running; re-upload."],
    ["\"PCA9685 servo board not found\"", "S6", "SDA/SCL wiring, servo board power, shared ground."],
    ["A wheel runs backwards", "S6", "Flip LEFT_REVERSED or RIGHT_REVERSED."],
    ["Desktop: \"This browser can't use Bluetooth\"", "S3", "Use Chrome or Edge, opened through serve.py."],
    ["Relay not running after reboot", "S9", "crontab -l shows the @reboot line; relay.log shows \"relay starting\"."],
], [2.2 * inch, 0.6 * inch, 3.7 * inch])

# ---------------------------------------------------------------- 10 code map + files
# Line counts are a rounded snapshot of the first release (commit e986fe6).
CODE_LOGIC = colors.HexColor("#2563EB")
CODE_MARKUP = colors.HexColor("#93C5FD")
CODE_CONFIG = colors.HexColor("#A8A49A")
CODE_GENERATED = colors.HexColor("#D8D5CD")

CODE_MAP = [
    # name, path, rounded label, [(exact lines, kind), ...] (exact values only set the bar proportions)
    ("Android app", "android/", "~2,050", [(627, CODE_LOGIC), (968, CODE_MARKUP), (114, CODE_CONFIG), (346, CODE_GENERATED)]),
    ("Desktop controller", "desktop/", "~710", [(543, CODE_LOGIC), (116, CODE_MARKUP), (55, CODE_CONFIG)]),
    ("Sketch", "RobotRover.ino, RobotMatrix.h", "~660", [(657, CODE_LOGIC)]),
    ("Bluetooth relay", "board/", "~290", [(221, CODE_LOGIC), (66, CODE_CONFIG)]),
    ("Docs and repo config", "README.md, .git*", "~290", [(286, CODE_CONFIG)]),
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
  "were taken at the first release (commit e986fe6), so they drift as the code changes.", "lead")
story.append(KeepTogether([
    Paragraph("Lines per folder", S["h2"]),
    code_map_chart(),
    Paragraph(check_text("Figure 7. About 4,000 lines of text files in git at the first release. The PDF and "
                         "images are binary and not counted; docs/build_pdf.py was added later and is not included."),
              S["caption"]),
]))
P("<b>The Android folder is half the line count, but mostly screens and icons.</b> The logic is split fairly "
  "evenly: about 660 lines of C++ in the sketch, 630 of Kotlin in the app, 540 of JavaScript in the desktop "
  "page, and 220 of Python in the relay.")

H2("What each part builds")
TABLE([
    ["Part", "Logic", "Builds with", "Produces", "Runs on"],
    ["Sketch", "~660 lines C++", "arduino-cli 1.5.1 or Arduino IDE 2, board arduino:zephyr:unoq",
     "Firmware, about 120 KB (15% of flash)", "UNO Q's STM32U585"],
    ["Android app", "~630 lines Kotlin", "Gradle 8.9, Android Gradle Plugin 8.7.3, Kotlin 2.0.21",
     "app-debug.apk, about 840 KB", "Android 8 or newer"],
    ["Desktop controller", "~540 lines JavaScript", "No build step; desktop/serve.py serves it",
     "A page at localhost:8765", "Chrome or Edge on a PC"],
    ["Bluetooth relay", "~220 lines Python", "No build step; copied to the board with adb",
     "A Bluetooth service named RobotRover", "UNO Q's Linux side"],
    ["This document", "~1,250 lines Python", "python docs/build_pdf.py (needs reportlab)",
     "This PDF", "Any PC with Python 3"],
], [1.05 * inch, 1.05 * inch, 1.8 * inch, 1.4 * inch, 1.2 * inch], font_rows=True)
P("Only the sketch and the Android app have a real build step. The relay and the desktop page run as plain "
  "source files.")

H2("File map")
TABLE([
    ["Path", "What it is", "Size"],
    ["RobotRover.ino", "The sketch: commands, wheels, servos, Bridge registration", "~340 lines"],
    ["RobotMatrix.h", "LED matrix icons and face (part of the sketch)", "~320 lines"],
    ["board/robot_ble_bridge.py", "The Bluetooth relay, with its MessagePack-RPC client and allowlist", "~220 lines"],
    ["board/run.sh, board/keepalive.sh", "Run the relay with bundled libraries; keep it running (offline install)", "~15 lines"],
    ["board/setup.sh, board/robot-ble-bridge.service", "Standard install with apt/pip and a systemd service", "~50 lines"],
    ["android/", "Android app (Kotlin). Gradle wrapper included; local.properties is per-PC and not in git", "~2,050 lines"],
    ["android/app/src/main/java/.../RobotBle.kt", "Bluetooth LE client: scan, connect, queue, notifications", "~310 lines"],
    ["android/app/src/main/java/.../MainActivity.kt", "Screen logic: drive pulses, sliders, status, log", "~320 lines"],
    ["android/app/src/main/res/", "Layout, theme, colors, icons, launcher icon (XML)", "~970 lines"],
    ["desktop/index.html", "Desktop controller, demo model and matrix preview (ports of sketch code)", "~670 lines"],
    ["desktop/serve.py", "Local web server on 127.0.0.1:8765", "~50 lines"],
    ["docs/build_pdf.py", "Generates this document; draws every figure except the app and wiring images", "~1,250 lines"],
    ["README.md", "Quick start and reference", "-"],
    ["RobotRover_System_Guide.pdf", "This document", "-"],
    ["images/", "App mockup, board pinout and wiring images (used in the README and this document)", "-"],
], [2.45 * inch, 3.2 * inch, 0.85 * inch])
CALLOUT("Not in the repository.",
        "Build outputs (the APK and the firmware); the five Python packages bundled for the relay on the board "
        "(Section 6 has the download command); Arduino's arduino-router, which comes with the board; "
        "android/local.properties, which is specific to each PC; and the HTML pages used to render "
        "images/app_mockup.png and images/wiring.png.")

# ---------------------------------------------------------------- build
doc = SimpleDocTemplate(
    OUT, pagesize=letter,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch, topMargin=0.85 * inch, bottomMargin=0.8 * inch,
    title="RobotRover - System Guide", author="RobotRover project",
    subject="System design, build notes and installation guide", creator="reportlab",
)
doc.build(story, onFirstPage=cover, onLaterPages=later)
print("wrote", OUT)
