"""How far has the chain moved lately?

This module REPORTS and never acts. There is no detector that ends a run, because
there are no runs: the chain is one unbroken sequence and it is never reset.

It still measures, because the alternative is having no idea whether the schema
in describe.py and the ban list in avoid.py are doing anything at all. Two
numbers per frame, both cheap:

- how alike the recent DESCRIPTIONS are (cosine over content-word sets)
- how alike the recent IMAGES are (mean pairwise dHash distance, 0-64)

Both are needed to read the chain honestly, because either alone lies. The words
can repeat while the pictures genuinely change, and two frames can look identical
while the description is visibly casting around for a way out.
"""
from __future__ import annotations

import io
import math
from itertools import combinations

from PIL import Image

import avoid


def text_similarity(a: dict, b: dict) -> float:
    """Cosine over content-word sets. Set-based, not counts: two descriptions
    naming the same six things are the same description for this purpose, however
    many times each word appears."""
    ta, tb = avoid.terms(a), avoid.terms(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / math.sqrt(len(ta) * len(tb))


def dhash(image_bytes: bytes, size: int = 8) -> int:
    """64-bit difference hash. Compares each pixel with its right-hand neighbour,
    so it keys on structure and ignores overall brightness - which matters here,
    because these loops love to drift darker without changing the picture."""
    im = Image.open(io.BytesIO(image_bytes)).convert("L").resize(
        (size + 1, size), Image.LANCZOS)
    # tobytes() rather than getdata(): an "L" image is one byte per pixel in row
    # order, so this is the same values without the deprecation.
    px = im.tobytes()
    bits = 0
    for row in range(size):
        base = row * (size + 1)
        for col in range(size):
            bits = (bits << 1) | int(px[base + col] < px[base + col + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def mean_text_similarity(descs: list[dict]) -> float:
    return _mean([text_similarity(a, b) for a, b in combinations(descs, 2)])


def mean_image_distance(hashes: list[int]) -> float:
    return _mean([float(hamming(a, b)) for a, b in combinations(hashes, 2)])


def assess(frames: list[dict], cfg: dict) -> dict:
    """A reading on the tail of the chain. `frames` carry `description` and
    `dhash`. Nothing consumes this to make a decision - it is recorded on the
    frame and shown on the page."""
    window = frames[-cfg["window"]:]
    if len(window) < 2:
        # None, not 0.0/64.0: there is nothing to compare frame 1 against, and a
        # placeholder here renders on the page as a real measurement of maximum
        # movement, which is the opposite of what it means.
        return {"text": None, "image": None, "n": len(window)}
    return {
        "text": round(mean_text_similarity([f["description"] for f in window]), 4),
        "image": round(mean_image_distance([int(f["dhash"]) for f in window]), 2),
        "n": len(window),
    }
