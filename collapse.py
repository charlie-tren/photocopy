"""Has the run stopped moving?

The published research on image->describe->image loops is unanimous that they
converge: across 700 runs they fell into roughly a dozen stock scenes regardless
of where they started. describe.py's schema and avoid.py's ban list are there to
delay that. This module is the admission that they will not prevent it, and turns
the failure into the measurement: a run's score is how many frames it survived.

BOTH signals must agree before a run is sealed, because either alone lies:

- Text only. A run can hold one subject while genuinely restyling it every day.
  The words repeat; the pictures do not. Sealing there throws away a live run.
- Image only. Two frames can be near-identical while the description is visibly
  casting around for a way out - that run is still trying, and often escapes.

So: descriptions have stopped moving AND pictures have stopped moving, for
`patience` consecutive frames, and never before `min_frames`.
"""
from __future__ import annotations

import io
import math
from itertools import combinations

from PIL import Image

import avoid


def text_similarity(a: dict, b: dict) -> float:
    """Cosine over content-word sets. Set-based, not counts: two descriptions
    that name the same six things are the same description for our purposes,
    however many times each word appears."""
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
    """Report on the tail of a run. `frames` carry `description` and `dhash`."""
    window = frames[-cfg["window"]:]
    if len(window) < 2:
        return {"stuck": False, "text": 0.0, "image": 64.0, "n": len(window)}
    text = mean_text_similarity([f["description"] for f in window])
    image = mean_image_distance([int(f["dhash"]) for f in window])
    return {
        "stuck": text >= cfg["text_similarity"] and image <= cfg["image_distance"],
        "text": round(text, 4),
        "image": round(image, 2),
        "n": len(window),
    }


def should_seal(frames: list[dict], strikes: int, cfg: dict) -> tuple[bool, dict]:
    """(seal?, this frame's reading). `strikes` is the consecutive-stuck count
    BEFORE this frame; the caller carries it on the run record."""
    reading = assess(frames, cfg)
    now = strikes + 1 if reading["stuck"] else 0
    reading["strikes"] = now
    seal = now >= cfg["patience"] and len(frames) >= cfg["min_frames"]
    return seal, reading
