#!/usr/bin/env python3
"""Generate a neofetch-style profile card SVG (dark + light) from avatar.png.
Left: the avatar image (inverted on the dark theme). Right: info panel.
Edit the DATA block below, then run:  python3 generate.py
"""
import base64
import io
import json
import os
import urllib.request
from PIL import Image
from html import escape

GH_USER = "enzo-wego"
CROP = (0.0, 0.0, 1.0, 1.0)       # avatar.png is already framed by engrave.py
ART_H = 340                       # displayed avatar height in px


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


def art_image(theme):
    """Return (disp_w, disp_h, data_uri) for the theme's pre-rendered engraving."""
    path = "avatar_dark.png" if theme == "dark" else "avatar.png"
    img = Image.open(path).convert("RGB")
    w, h = img.size
    l, tp, r, bt = CROP
    img = img.crop((int(l * w), int(tp * h), int(r * w), int(bt * h)))
    w, h = img.size
    disp_w = ART_H * w / h
    img = img.resize((round(disp_w * 2), ART_H * 2))   # 2x for retina
    if theme == "light":
        img = img.convert("L")                         # grayscale -> smaller PNG
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return disp_w, ART_H, uri


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
    art_w, art_h, uri = art_image(theme)
    pad = 28
    maxc = 52                       # panel width in characters
    panel_w = maxc * CW
    _, panel_end = panel_svg(DATA, t, 0, 0, maxc)   # measure panel height
    panel_h = panel_end
    body_h = max(art_h, panel_h)
    H = body_h + pad * 2
    px0 = pad + art_w + 44
    art_y = pad + (body_h - art_h) / 2
    py0 = pad + (body_h - panel_h) / 2 + LH
    panel, _ = panel_svg(DATA, t, px0, py0, maxc)
    W = px0 + panel_w + pad
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" font-family="'JetBrains Mono','Fira Mono','DejaVu Sans Mono',Consolas,monospace" font-size="{PANEL_FS}">
<defs><clipPath id="r"><rect x="{pad}" y="{art_y:.0f}" width="{art_w:.0f}" height="{art_h:.0f}" rx="10"/></clipPath></defs>
<rect width="{W:.0f}" height="{H:.0f}" rx="14" fill="{t["bg"]}"/>
<image x="{pad}" y="{art_y:.0f}" width="{art_w:.0f}" height="{art_h:.0f}" clip-path="url(#r)" preserveAspectRatio="xMidYMid slice" href="{uri}"/>
{panel}
</svg>
'''


for theme in ("dark", "light"):
    open(f"{theme}_mode.svg", "w").write(build(theme))
    print(f"wrote {theme}_mode.svg")
