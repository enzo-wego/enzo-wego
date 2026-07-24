#!/usr/bin/env python3
"""Turn photo.png into line-engraving avatars for the profile card.

Writes two files so each theme reads correctly (a plain negative would look
like an X-ray, so the dark one re-encodes tone as white ink on dark "paper"):
  avatar.png       black ink on white  -> light theme
  avatar_dark.png  white ink on #1a1b26 -> dark theme

Run locally (needs numpy):  python3 engrave.py   then   python3 generate.py
"""
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance

CROP = (0.12, 0.02, 0.88, 1.0)   # (l,t,r,b) fractions -> portrait bust
OUT_W = 720                       # output width px
SS = 2                            # supersample for anti-aliased lines
PERIOD = 7.0                      # hatch spacing (px, at supersample res)
EDGE_T = 0.30                     # edge strength -> ink threshold
DARK_BG, DARK_INK = (26, 27, 38), (206, 212, 235)   # #1a1b26 paper, light ink


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


def _ink(tg, edge, H, W, polarity):
    """Boolean ink mask. light: dense in shadows; dark: dense in highlights."""
    y = np.arange(H)[:, None].astype(np.float32)
    x = np.arange(W)[None, :].astype(np.float32)
    p = PERIOD * SS
    drive = (1 - tg) if polarity == "light" else tg   # how much ink here
    ink = (0.5 - 0.5 * np.cos(2 * np.pi * y / p)) < np.clip(drive * 1.15, 0, 0.86)
    ink |= (0.5 - 0.5 * np.cos(2 * np.pi * (x + y) / p)) < np.clip((drive - 0.58) / 0.42, 0, 0.8)
    ink |= edge > EDGE_T
    return ink


def engrave():
    tg, edge, H, W = _tone_and_edge()

    light = np.where(_ink(tg, edge, H, W, "light"), 30, 255).astype(np.uint8)
    Image.fromarray(light, "L").resize((OUT_W, H // SS), Image.LANCZOS).save("avatar.png")

    ink = _ink(tg, edge, H, W, "dark")[..., None]
    dark = np.where(ink, DARK_INK, DARK_BG).astype(np.uint8)
    Image.fromarray(dark, "RGB").resize((OUT_W, H // SS), Image.LANCZOS).save("avatar_dark.png")
    print(f"wrote avatar.png / avatar_dark.png ({OUT_W}x{H // SS})")


if __name__ == "__main__":
    engrave()
