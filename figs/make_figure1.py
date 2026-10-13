"""Figure 1 (cover): one step of the agent, achromatic, 16:9.

Writes figure1_agent_loop.svg (text set in Inter, formula as outlines) and
figure1_agent_loop.png (rendered by Chromium at 2x, 3200 x 1800).
usage: python figs/make_figure1.py (the PNG needs playwright and Chromium)
"""
from pathlib import Path

import matplotlib
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MPath
from matplotlib.textpath import TextPath

OUT = Path(__file__).resolve().parent
W, H = 1600, 900

INK = "#1a1a1a"      # primary text
INK2 = "#5c5c5c"     # secondary text
LINE = "#3d3d3d"     # strokes and arrows
DARK = "#222222"     # the probe box
PANEL = "#f3f3f3"    # light fills
MUTED = "#8a8a8a"
FONT = "Inter, 'Helvetica Neue', Arial, sans-serif"

matplotlib.rcParams["mathtext.fontset"] = "stixsans"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size, weight=400, fill=INK, anchor="start", spacing=0.0, italic=False):
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    style = ' font-style="italic"' if italic else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}{style}>{esc(s)}</text>')


def lines_centered(cx, cy, lines):
    """lines: (text, size, weight, fill, italic). Centres the block on (cx, cy)."""
    heights = [ln[1] * 1.32 for ln in lines]
    total = sum(heights) - lines[-1][1] * 0.32
    y = cy - total / 2
    out = []
    for (s, size, weight, fill, italic), h in zip(lines, heights):
        y_base = y + size * 0.76
        out.append(text(cx, y_base, s, size, weight, fill, "middle", italic=italic))
        y += h
    return "".join(out)


def box(x, y, w, h, fill="white", stroke=LINE, dash=None, rx=12, sw=1.6):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}{d}/>'


def diamond(cx, cy, hw, hh):
    pts = f"{cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh} {cx - hw},{cy}"
    return f'<polygon points="{pts}" fill="white" stroke="{LINE}" stroke-width="1.6" stroke-linejoin="round"/>'


def arrow(points, head=True, dash=None, sw=1.75):
    d = " ".join(("M" if i == 0 else "L") + f"{x:.1f} {y:.1f}" for i, (x, y) in enumerate(points))
    m = ' marker-end="url(#ah)"' if head else ""
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="{sw}" stroke-linejoin="round" '
            f'stroke-linecap="round"{m}{ds}/>')


def math_path(tex, size):
    """Outline of a mathtext string; returns (path data with baseline at y=0, x-extent, y-top, y-bottom)."""
    tp = TextPath((0, 0), tex, size=size, prop=FontProperties(family="Inter"))
    bb = tp.get_extents()
    parts = []
    for verts, code in tp.iter_segments(curves=True, simplify=False):
        pts = [(verts[i] - bb.x0, -verts[i + 1]) for i in range(0, len(verts), 2)]
        if code == MPath.MOVETO:
            parts.append("M%.2f %.2f" % pts[0])
        elif code == MPath.LINETO:
            parts.append("L%.2f %.2f" % pts[0])
        elif code == MPath.CURVE3:
            parts.append("Q%.2f %.2f %.2f %.2f" % (*pts[0], *pts[1]))
        elif code == MPath.CURVE4:
            parts.append("C%.2f %.2f %.2f %.2f %.2f %.2f" % (*pts[0], *pts[1], *pts[2]))
        elif code == MPath.CLOSEPOLY:
            parts.append("Z")
    return " ".join(parts), bb.width, -bb.y1, -bb.y0


def build():
    el = []
    el.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    el.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.4" '
              f'markerHeight="6.4" orient="auto-start-reverse"><path d="M0 0.6 L10 5 L0 9.4 z" fill="{LINE}"/>'
              '</marker></defs>')

    # header
    el.append(text(80, 112, "Pay for Information Early", 60, 700, INK, spacing=-0.6))
    el.append(text(82, 158, "A probe rule derived from the ARC-AGI-3 score, and a test of when it pays",
                   24, 400, INK2))

    # results panel (top right)
    px0, py0, pw, ph = 1004, 40, 516, 188
    el.append(box(px0, py0, pw, ph, fill=PANEL, stroke=None, rx=14))
    el.append(text(px0 + 26, py0 + 36, "SECOND PRE-REGISTERED ROUND", 12.5, 600, INK2, spacing=1.4))

    def result(y, name, qual, finding):
        el.append(f'<text x="{px0 + 26}" y="{y}" font-family="{FONT}" font-size="19" fill="{INK}">'
                  f'<tspan font-weight="600">{esc(name)}</tspan>'
                  f'<tspan font-weight="400" fill="{INK2}">, {esc(qual)}</tspan></text>')
        el.append(text(px0 + 26, y + 27, finding, 16.5, 400, INK2))

    result(py0 + 78, "Open rooms", "rarely stuck", "the rule beat no rule in 12 of 16 games (p = 0.038)")
    result(py0 + 140, "Mazes", "often stuck", "no gain, as predicted")

    # flow
    y1, y2, y3 = 380, 570, 736
    # observe
    ox, ow, oh = 80, 206, 96
    el.append(box(ox, y1 - oh / 2, ow, oh))
    el.append(lines_centered(ox + ow / 2, y1, [("Observe", 22, 600, INK, False),
                                               ("the settled frame", 16.5, 400, INK2, False)]))
    # update (the graph is rebuilt every level; only the table carries over)
    ux, uw, uh = 336, 276, 118
    el.append(box(ux, y1 - uh / 2, uw, uh))
    el.append(lines_centered(ux + uw / 2, y1, [("Update", 22, 600, INK, False),
                                               ("state graph of the level", 16.5, 400, INK2, False),
                                               ("and action-effect table", 16.5, 400, INK2, False),
                                               ("table kept across levels", 14, 400, MUTED, True)]))
    el.append(arrow([(ox + ow, y1), (ux - 3, y1)]))
    # decision 1: the rule only admits unknown actions; it probes one untried here
    dcx, hw, hh = 806, 128, 78
    el.append(diamond(dcx, y1, hw, hh))
    el.append(lines_centered(dcx, y1, [("Rule holds and", 16.5, 600, INK, False),
                                       ("an unknown action", 16.5, 600, INK, False),
                                       ("is untried here?", 16.5, 600, INK, False)]))
    el.append(arrow([(ux + uw, y1), (dcx - hw - 3, y1)]))
    # decision 2
    el.append(diamond(dcx, y2, hw, hh))
    el.append(lines_centered(dcx, y2, [("Untried action", 16.5, 600, INK, False),
                                       ("known to work?", 16.5, 600, INK, False)]))
    el.append(arrow([(dcx, y1 + hh), (dcx, y2 - hh - 3)]))
    el.append(text(dcx + 12, (y1 + hh + y2 - hh) / 2 + 5, "no", 15, 500, INK2))

    # actions
    ax, aw, ah = 1024, 356, 96
    # probe (dark)
    el.append(text(ax, y1 - ah / 2 - 12, "ONLY WITH THE RULE", 12.5, 600, INK2, spacing=1.4))
    el.append(box(ax, y1 - ah / 2, aw, ah, fill=DARK, stroke=None))
    el.append(lines_centered(ax + aw / 2, y1, [("Probe", 22, 600, "white", False),
                                               ("pay one action to try it", 16.5, 400, "#d6d6d6", False)]))
    el.append(arrow([(dcx + hw, y1), (ax - 3, y1)]))
    el.append(text((dcx + hw + ax) / 2, y1 - 10, "yes", 15, 500, INK2, "middle"))
    # exploit
    el.append(box(ax, y2 - ah / 2, aw, ah, fill=PANEL, stroke=LINE))
    el.append(lines_centered(ax + aw / 2, y2, [("Exploit", 22, 600, INK, False),
                                               ("walk to it and try it", 16.5, 400, INK2, False)]))
    el.append(arrow([(dcx + hw, y2), (ax - 3, y2)]))
    el.append(text((dcx + hw + ax) / 2, y2 - 10, "yes", 15, 500, INK2, "middle"))
    # stuck (dashed)
    sh = 104
    el.append(box(ax, y3 - sh / 2, aw, sh, dash="7 6"))
    el.append(lines_centered(ax + aw / 2, y3, [("Stuck", 22, 600, INK, False),
                                               ("try any untried action", 16.5, 400, INK2, False),
                                               ("information comes free", 14, 400, MUTED, True)]))
    el.append(arrow([(dcx, y2 + hh), (dcx, y3), (ax - 3, y3)]))
    el.append(text(dcx + 12, (y2 + hh + y3) / 2 + 4, "no", 15, 500, INK2))

    # loop back to observe
    bus, ybot = 1452, 840
    for yy in (y1, y2, y3):
        el.append(arrow([(ax + aw, yy), (bus, yy)], head=False))
    el.append(arrow([(bus, y1), (bus, ybot), (ox + ow / 2, ybot), (ox + ow / 2, y1 + oh / 2 + 3)]))
    el.append(text(ox + ow / 2 + 14, ybot - 12, "act, then observe the next frame", 15, 400, INK2))

    # probe-rule formula, attached to the first decision
    lhs, lw, lt, lb = math_path(r"$\rho\sum_{i>j}\frac{i\,q^{\,i-j}}{r_*^{\,2}}$", 34)
    rel, gw, gt, gb = math_path(r"$>$", 34)
    rhs, rw, rt, rb = math_path(r"$\frac{j}{\hat{a}_j\,\hat{r}_j^{\,2}}$", 34)
    gap = 34
    total = lw + gap + gw + gap + rw
    # symbols of the rule, defined under it so the figure stands alone
    legend = [(r"$\rho$", "share of a later level's actions one learned effect saves"),
              (r"$q$", "chance of completing each further level"),
              (r"$\hat{a}_j$", "actions spent so far in level j"),
              (r"$\hat{r}_j$", "estimated agent / human action ratio of the previous level"),
              (r"$r_*$", "action ratio assumed for later levels (2)")]
    row = 21
    fx0, fy0, fw = 204, 494, 452
    cap_y = fy0 + 150
    rule_y = cap_y + 16
    fh = rule_y - fy0 + 14 + row * len(legend) + 6
    el.append(box(fx0, fy0, fw, fh, fill=PANEL, stroke=None, rx=14))
    el.append(text(fx0 + 22, fy0 + 32, "THE PROBE RULE, FROM THE SCORE", 12.5, 600, INK2, spacing=1.4))
    x = fx0 + (fw - total) / 2
    base = fy0 + 98
    el.append(f'<path transform="translate({x:.1f},{base:.1f})" d="{lhs}" fill="{INK}"/>')
    lhs_c = x + lw / 2
    x += lw + gap
    el.append(f'<path transform="translate({x:.1f},{base:.1f})" d="{rel}" fill="{INK}"/>')
    x += gw + gap
    el.append(f'<path transform="translate({x:.1f},{base:.1f})" d="{rhs}" fill="{INK}"/>')
    rhs_c = x + rw / 2
    el.append(text(lhs_c, cap_y, "expected saving later", 14, 400, INK2, "middle"))
    el.append(text(rhs_c, cap_y, "cost of an action now", 14, 400, INK2, "middle"))
    el.append(f'<path d="M{fx0 + 22} {rule_y} L{fx0 + fw - 22} {rule_y}" stroke="#dcdcdc" stroke-width="1"/>')
    for k, (sym, desc) in enumerate(legend):
        yb = rule_y + 14 + row * (k + 1) - 6
        path, sw_, st, sb = math_path(sym, 17.5)
        el.append(f'<path transform="translate({fx0 + 22:.1f},{yb:.1f})" d="{path}" fill="{INK}"/>')
        el.append(text(fx0 + 74, yb, desc, 13, 400, INK2))
    # dashed leader to the diamond's lower-left edge
    ex, ey = dcx - hw / 2, y1 + hh / 2
    el.append(f'<path d="M{fx0 + fw - 30:.1f} {fy0:.1f} L{ex - 4:.1f} {ey + 3:.1f}" stroke="{MUTED}" '
              f'stroke-width="1.3" stroke-dasharray="4 4" fill="none"/>')
    el.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.2" fill="{MUTED}"/>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           + "".join(el) + "</svg>")
    return svg


def render(svg_path, png_path, scale=2):
    from playwright.sync_api import sync_playwright
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;'
            f'background:#fff}}</style></head><body>{svg_path.read_text()}</body></html>')
    tmp = svg_path.with_suffix(".render.html")
    tmp.write_text(html)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=scale)
        pg.goto(tmp.resolve().as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(200)
        pg.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()
    tmp.unlink()


if __name__ == "__main__":
    svg_file = OUT / "figure1_agent_loop.svg"
    svg_file.write_text(build())
    print("wrote", svg_file)
    try:
        render(svg_file, OUT / "figure1_agent_loop.png")
        print("wrote", OUT / "figure1_agent_loop.png")
    except ImportError:
        print("playwright is not installed; the PNG was not rendered (pip install playwright)")
