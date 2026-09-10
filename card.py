"""Builds assets/card.jpg, the 1200x630 share card, from the newest frame.

WHY THIS EXISTS. The page carried `og:type`, `og:title` and `og:description` and
no `og:image`, so every share unfurled as a bare link - for a project whose whole
subject is a picture. Found 10/09/2026 in an estate-wide sweep that turned up the
same fault in three other places; the-aftertimes/card.py is the sibling that
solved it first and this follows its two load-bearing decisions.

1. NO TEXT IS DRAWN. Every platform renders `og:title` and `og:description` as
   text beside the image, so painting either again duplicates it - and it removes
   the whole font question, which matters because this site's face is Silkscreen
   and PIL cannot read a woff2. The card is the artwork and nothing else.

2. THE ARTWORK IS COVERED, NOT FITTED. Frames are square (768x768) and a card is
   1200x630, so scaling to fit would either squash the image or letterbox it in
   bars that read as a rendering bug. Cover crops the top and bottom evenly,
   which for these frames loses least.

It runs from render.build(), not from a schedule, so the card is rebuilt whenever
the site is. A card built on its own timer is how you end up advertising
yesterday's frame - and unlike a stale thumbnail, nobody can see it from here.
"""

from __future__ import annotations

import pathlib

from PIL import Image

import chain
from common import rel

WIDTH, HEIGHT = 1200, 630
OUT = "assets/card.jpg"
#: JPEG, not PNG: these are photographic frames, where PNG is roughly ten times
#: the bytes for no visible gain, and several platforms cap the image they will
#: fetch. quality=88 is where the sibling landed.
QUALITY = 88


def cover_box(src_w: int, src_h: int, dst_w: int, dst_h: int) -> tuple[int, int, int, int]:
    """The crop box that fills dst_w x dst_h from the CENTRE of the source."""
    scale = max(dst_w / src_w, dst_h / src_h)
    take_w, take_h = dst_w / scale, dst_h / scale
    left, top = (src_w - take_w) / 2, (src_h - take_h) / 2
    return (round(left), round(top), round(left + take_w), round(top + take_h))


def build() -> str | None:
    """Write the card from the newest frame. Returns the path, or None if the
    chain is empty - a fresh chain has no image to card, and that must not be an
    error that stops the site rendering."""
    frames = chain.load_frames()
    if not frames:
        return None
    newest = frames[-1]
    src = pathlib.Path(rel(newest["image"]))
    if not src.exists():
        return None
    with Image.open(src) as im:
        im = im.convert("RGB")
        box = cover_box(im.width, im.height, WIDTH, HEIGHT)
        card = im.resize((WIDTH, HEIGHT), Image.LANCZOS, box=box)
    out = rel(OUT)
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    card.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}" if path else "No frames yet; no card written")
