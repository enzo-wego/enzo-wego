#!/usr/bin/env python3
"""Turn photo.png into a hybrid engraving avatar for the profile card.

Face/skin -> fine engraving hatch lines. Dark regions (hair, clothes) -> ASCII
characters. Split on tone: cells darker than DARK_T become ASCII, the rest hatch.

Writes two theme variants (a plain negative would look like an X-ray, so the
dark one re-encodes tone as light ink on dark "paper"):
  avatar.png       dark ink on white   -> light theme
  avatar_dark.png  light ink on #1a1b26 -> dark theme

Run locally (needs numpy):  python3 engrave.py   then   python3 generate.py
"""
import numpy as np
from PIL import (Image, ImageOps, ImageFilter, ImageEnhance,
                 ImageDraw, ImageFont)

CROP = (0.12, 0.02, 0.88, 1.0)   # (l,t,r,b) fractions -> portrait bust
OUT_W = 720                       # output width px
SS = 2                            # supersample for anti-aliased lines
PERIOD = 7.0                      # hatch spacing (px, at supersample res)
EDGE_T = 0.30                     # edge strength -> ink threshold
CELL = 12                         # ASCII cell size px (output res)
DARK_T = 0.42                     # tone below this -> ASCII (hair, clothes)
ASCII_RAMP = "@%#*o+=~-:. "       # dense (dark) -> sparse (light)
DARK_BG, DARK_INK = (26, 27, 38), (206, 212, 235)  # #1a1b26 paper, light ink
FONTS = ["/System/Library/Fonts/Menlo.ttc",
         "/System/Library/Fonts/Monaco.ttf",
         "/Library/Fonts/Courier New.ttf"]


def _font(size):
    for p in FONTS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _tone_and_edge():
    im = Image.open("photo.png").convert("RGB")
    w, h = im.size
    l, tp, r, bt = CROP
    im = im.crop((int(l * w), int(tp * h), int(r * w), int(bt * h)))
    g = ImageOps.grayscale(im)
    g = ImageOps.autocontrast(g, cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(1.2)
    W = OUT_W * SS
    H = round(W * g.height / g.width)
    g = g.resize((W, H), Image.LANCZOS)
    edge = np.asarray(g.filter(ImageFilter.FIND_EDGES)).astype(np.float32) / 255
    g = g.filter(ImageFilter.GaussianBlur(SS * 0.6))
    t = np.asarray(g).astype(np.float32) / 255
    t = np.clip((t - 0.04) / (0.86 - 0.04), 0, 1)     # levels: clean bg, deep blacks
    return t ** 0.85, edge, H, W


def _hatch(tg, edge, H, W, polarity):
    """Boolean ink mask. light: dense in shadows; dark: dense in highlights."""
    y = np.arange(H)[:, None].astype(np.float32)
    x = np.arange(W)[None, :].astype(np.float32)
    p = PERIOD * SS
    drive = (1 - tg) if polarity == "light" else tg   # how much ink here
    ink = (0.5 - 0.5 * np.cos(2 * np.pi * y / p)) < np.clip(drive * 1.15, 0, 0.86)
    ink |= (0.5 - 0.5 * np.cos(2 * np.pi * (x + y) / p)) < np.clip((drive - 0.58) / 0.42, 0, 0.8)
    ink |= edge > EDGE_T
    return ink


def render(tg, edge, H, W, polarity, paper, ink):
    Wo = (OUT_W // CELL) * CELL
    Ho = ((H // SS) // CELL) * CELL
    cols, rows = Wo // CELL, Ho // CELL

    # hatch layer, anti-aliased, as RGB on paper
    cover = np.asarray(Image.fromarray(
        np.where(_hatch(tg, edge, H, W, polarity), 0, 255).astype(np.uint8), "L")
        .resize((Wo, Ho), Image.LANCZOS)).astype(np.float32) / 255   # 1 paper .. 0 ink
    paper_a, ink_a = np.array(paper, np.float32), np.array(ink, np.float32)
    hatch_rgb = (paper_a * cover[..., None] + ink_a * (1 - cover[..., None])).astype(np.uint8)

    # per-cell mean tone -> which cells are hair/clothes (ASCII)
    grid = np.asarray(Image.fromarray((np.clip(tg, 0, 1) * 255).astype(np.uint8), "L")
                      .resize((cols, rows), Image.BOX)).astype(np.float32) / 255
    ascii_cell = grid < DARK_T
    cell_px = np.repeat(np.repeat(ascii_cell, CELL, 0), CELL, 1)

    base = np.where(cell_px[..., None], paper_a.astype(np.uint8), hatch_rgb)
    canvas = Image.fromarray(base, "RGB")
    draw = ImageDraw.Draw(canvas)
    font = _font(CELL + 1)
    for r in range(rows):
        for c in range(cols):
            if not ascii_cell[r, c]:
                continue
            idx = int((grid[r, c] / DARK_T) * (len(ASCII_RAMP) - 1))
            ch = ASCII_RAMP[min(idx, len(ASCII_RAMP) - 1)]
            if ch != " ":
                draw.text((c * CELL, r * CELL - 1), ch, font=font, fill=ink)
    return canvas


def engrave():
    tg, edge, H, W = _tone_and_edge()
    render(tg, edge, H, W, "light", (255, 255, 255), (28, 28, 32)).save("avatar.png")
    render(tg, edge, H, W, "dark", DARK_BG, DARK_INK).save("avatar_dark.png")
    print("wrote avatar.png / avatar_dark.png")


if __name__ == "__main__":
    engrave()
