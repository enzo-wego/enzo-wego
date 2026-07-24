#!/usr/bin/env python3
"""Generate a neofetch-style profile card SVG (dark + light) from avatar.png.
Left column: colored ASCII art of the avatar. Right column: info panel.
Edit the DATA block below, then run:  python3 generate.py
"""
import json
import os
import urllib.request
from PIL import Image
from html import escape

GH_USER = "enzo-wego"
COLS = 76          # ascii art width in chars (higher = finer portrait)
RAMP = " .':-~=+*a#%@$B8&W"   # density ramp: sparse -> dense
BG_CUT = 0.78      # pixels brighter than this are treated as background (blanked)
CROP = (0.03, 0.0, 0.80, 1.0)  # (l,t,r,b) fractions: trim the gold pillar on the right


def gh_stats(user):
    """Live repos/followers/stars from the GitHub API. Falls back to '—' offline."""
    hdr = {"User-Agent": user, "Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        hdr["Authorization"] = f"Bearer {tok}"

    def get(url):
        return json.load(urllib.request.urlopen(
            urllib.request.Request(url, headers=hdr), timeout=15))

    try:
        u = get(f"https://api.github.com/users/{user}")
        return [("Repos", str(u["public_repos"]))]
    except Exception as e:  # network/rate-limit: keep the card renderable
        print(f"gh_stats failed ({e}); using placeholder")
        return [("Repos", "—")]

DATA = {
    "user": "enzo@wego",
    "sections": [
        ("", [  # first block has no header, sits under the user@host rule
            ("OS", "macOS"),
            ("Host", "Wego"),
            ("Role", "Software Engineer, Payments"),
        ]),
        ("Languages", [
            ("Programming", "Go, Python, JavaScript"),
            ("Query", "SQL"),
            ("Real", "English"),
        ]),
        ("Contact", [
            ("Email.Work", "enzo@wego.com"),
            ("GitHub", "enzo-wego"),
        ]),
        ("Certifications", [
            ("Claude Code in Action", "Anthropic (2026)"),
        ]),
        ("GitHub Stats", gh_stats(GH_USER)),
    ],
}

THEMES = {
    "dark":  {"bg": "#1a1b26", "fg": "#c0caf5", "label": "#f7768e",
              "accent": "#7aa2f7", "rule": "#565f89", "value": "#c0caf5"},
    "light": {"bg": "#ffffff", "fg": "#343b58", "label": "#8c4351",
              "accent": "#34548a", "rule": "#a1a6c5", "value": "#343b58"},
}

CW, LH = 8.0, 17.0            # panel char cell / line height
PANEL_FS = 13
ART_CW, ART_LH, ART_FS = 6.0, 10.5, 10   # finer cell for the portrait


def _lerp(c1, c2, f):
    a = (int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16))
    b = (int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16))
    r, g, bl = (round(a[i] + (b[i] - a[i]) * f) for i in range(3))
    return f"#{r:02x}{g:02x}{bl:02x}"


def _shade(r, g, b, theme):
    """Recolor a pixel so the subject reads well on the card background.
    Boosts saturation, then lifts shadows (dark theme) or deepens (light)."""
    m = (r + g + b) / 3
    sat = 1.35                                    # push away from grey
    r, g, b = (max(0, min(255, m + (c - m) * sat)) for c in (r, g, b))
    if theme == "dark":
        r, g, b = (c * 0.62 + 74 for c in (r, g, b))   # 0->74, 255->232
    else:
        r, g, b = (c * 0.80 for c in (r, g, b))        # deepen for white bg
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def ascii_art(path, theme):
    """Return list of rows; each row is list of (char, '#rrggbb').
    Real photo colors mapped to a density ramp; bright background blanked."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    l, tp, r, bt = CROP
    img = img.crop((int(l * w), int(tp * h), int(r * w), int(bt * h)))
    w, h = img.size
    rows = max(1, round(COLS * (h / w) * (ART_CW / ART_LH)))  # keep image aspect
    img = img.resize((COLS, rows))
    px = img.load()
    t = THEMES[theme]
    out = []
    for y in range(rows):
        row = []
        for x in range(COLS):
            r, g, b = px[x, y]
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
            if lum >= BG_CUT:
                row.append((" ", t["bg"])); continue
            density = 1 - (lum / BG_CUT)          # dark pixel -> dense char
            ch = RAMP[min(len(RAMP) - 1, int(density * len(RAMP)))]
            row.append((ch, _shade(r, g, b, theme)))
        out.append(row)
    return out


def _tl(nchars):
    # force glyphs to occupy exactly nchars*CW px -> font-metric independent
    return f'textLength="{nchars * CW:.1f}" lengthAdjust="spacingAndGlyphs"'


def art_svg(rows, x0, y0):
    lines = [f'<g font-size="{ART_FS}">']
    for i, row in enumerate(rows):
        y = y0 + i * ART_LH
        spans, run, color = [], "", None
        for ch, col in row:
            if col != color and run:
                spans.append((run, color)); run = ""
            color, run = col, run + ch
        if run:
            spans.append((run, color))
        tspans = "".join(
            f'<tspan fill="{c}">{escape(t).replace(" ", "&#160;")}</tspan>'
            for t, c in spans)
        lines.append(f'<text x="{x0}" y="{y:.1f}" '
                     f'textLength="{COLS*ART_CW:.1f}" lengthAdjust="spacingAndGlyphs" '
                     f'xml:space="preserve">{tspans}</text>')
    lines.append("</g>")
    return "\n".join(lines)


def panel_svg(data, t, x0, y0, maxc):
    lines, y = [], y0
    panel_w = maxc * CW
    for header, pairs in data["sections"]:
        if header == "" and y == y0:
            # user@host title line + rule
            u = escape(data["user"])
            lines.append(f'<text x="{x0}" y="{y:.0f}" {_tl(len(data["user"]))} '
                         f'fill="{t["accent"]}" font-weight="bold">{u}</text>')
            rule_x = x0 + (len(data["user"]) + 1) * CW
            lines.append(f'<line x1="{rule_x:.0f}" y1="{y-5:.0f}" '
                         f'x2="{x0+panel_w:.0f}" y2="{y-5:.0f}" '
                         f'stroke="{t["rule"]}" stroke-width="1.5"/>')
            y += LH
        elif header:
            y += LH * 0.4
            lines.append(f'<text x="{x0}" y="{y:.0f}" {_tl(len(header)+3)} '
                         f'xml:space="preserve" fill="{t["fg"]}">— '
                         f'<tspan fill="{t["accent"]}" font-weight="bold">{escape(header)}</tspan> </text>')
            rule_x = x0 + (len(header) + 4) * CW
            lines.append(f'<line x1="{rule_x:.0f}" y1="{y-5:.0f}" '
                         f'x2="{x0+panel_w:.0f}" y2="{y-5:.0f}" '
                         f'stroke="{t["rule"]}" stroke-width="1.5"/>')
            y += LH
        for k, v in pairs:
            key, val = escape(k), escape(v)
            # dot leader fills the gap; value is right-aligned with a 1-char gap
            left_n = maxc - len(v) - 1          # chars in "key: ....." segment
            dots = "." * max(1, left_n - len(k) - 2)
            lines.append(
                f'<text x="{x0}" y="{y:.0f}" {_tl(len(k) + 2 + len(dots))} '
                f'xml:space="preserve">'
                f'<tspan fill="{t["label"]}" font-weight="bold">{key}</tspan>'
                f'<tspan fill="{t["rule"]}">: {dots}</tspan></text>')
            vx = x0 + panel_w - len(v) * CW     # right-align via explicit x (end+textLength is buggy)
            lines.append(
                f'<text x="{vx:.1f}" y="{y:.0f}" {_tl(len(v))} '
                f'fill="{t["value"]}">{val}</text>')
            y += LH
    return "\n".join(lines), y


def build(theme):
    t = THEMES[theme]
    rows = ascii_art("avatar.png", theme)
    pad = 28
    art_w = COLS * ART_CW
    art_h = len(rows) * ART_LH
    maxc = 52                       # panel width in characters
    panel_w = maxc * CW
    # measure panel height with a throwaway pass, then center both columns
    _, panel_end = panel_svg(DATA, t, 0, 0, maxc)
    panel_h = panel_end
    body_h = max(art_h, panel_h)
    H = body_h + pad * 2
    px0 = pad + art_w + 40
    art_y = pad + (body_h - art_h) / 2 + ART_LH
    py0 = pad + (body_h - panel_h) / 2 + LH
    panel, _ = panel_svg(DATA, t, px0, py0, maxc)
    W = px0 + panel_w + pad
    art = art_svg(rows, pad, art_y)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" font-family="'JetBrains Mono','Fira Mono','DejaVu Sans Mono',Consolas,monospace" font-size="{PANEL_FS}">
<rect width="{W:.0f}" height="{H:.0f}" rx="14" fill="{t["bg"]}"/>
{art}
{panel}
</svg>
'''


for theme in ("dark", "light"):
    open(f"{theme}_mode.svg", "w").write(build(theme))
    print(f"wrote {theme}_mode.svg")
