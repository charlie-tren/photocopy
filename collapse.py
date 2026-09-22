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
from collections import Counter
from itertools import combinations

from PIL import Image

import avoid


def text_similarity(a: dict, b: dict) -> float:
    """Cosine over content-word sets. Set-based, not counts: two descriptions
    naming the same six things are the same description for this purpose, however
    many times each word appears.

    Over ALL content words, including the ones the avoid list may not ban - that
    exemption exists to stop a ban being written and has no business in a
    read-only number. It is worth 0.01 to 0.03 here and nothing else.

    WHAT THIS NUMBER CANNOT DO, measured 22/09/2026. Over the nine days the chain
    spent drawing one mannequin, hand to temple, in one furrowed field, it read
    0.31 FALLING to 0.28 - apparent divergence - because the describer kept
    finding new words for the same picture: copper for amber, jacket for shirt,
    temple for forehead. A set-overlap score over free prose measures the
    describer's vocabulary, not the picture, and it points the wrong way exactly
    when the picture stops moving. The image distance caught this one (29 to
    17.4) and `subject` below says it in one number.
    """
    ta = avoid.terms(a, exempt_protected=False)
    tb = avoid.terms(b, exempt_protected=False)
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


def subject_lock(descs: list[dict]) -> tuple[str | None, float]:
    """The stickiest word in the recent SUBJECT slots, and the share of frames
    carrying it.

    The third number, added 22/09/2026, because the first two both missed a lock
    that was obvious on sight: four consecutive frames of a mannequin with a hand
    at its temple in a furrowed field. The image distance fell (it noticed) and
    the word similarity fell too (it did not). Neither says WHAT is stuck, and
    the thing that was stuck is the subject - one slot, out of seven, that
    decides what the picture is of.

    Presence per frame, not frequency, exactly as avoid.overused counts: a word
    in every subject line is a locked subject however often each line says it.
    1.0 means every recent frame is of the same thing by name. Over frames 28-36
    it reads 1.0 on "mannequin" without a break.
    """
    seen = Counter()
    for desc in descs:
        text = str(desc.get("subject", "")).lower()
        seen.update({w for w in avoid._WORD.findall(text) if w not in avoid._STOP})
    if not seen:
        return None, 0.0
    # Deterministic on a tie, the way avoid.overused sorts: every subject line
    # naming "a white plastic mannequin" puts three words on the same count, and
    # Counter.most_common then returns whichever insertion order happens to hand
    # it. Frame 30 reported "white" and frames 29 and 31 reported "mannequin"
    # off identical data, which reads as movement and is not.
    top = max(seen.values())
    word = min(t for t, n in seen.items() if n == top)
    return word, round(top / len(descs), 2)


def assess(frames: list[dict], cfg: dict) -> dict:
    """A reading on the tail of the chain. `frames` carry `description` and
    `dhash`. Nothing consumes this to make a decision - it is recorded on the
    frame and shown on the page."""
    window = frames[-cfg["window"]:]
    if len(window) < 2:
        # None, not 0.0/64.0: there is nothing to compare frame 1 against, and a
        # placeholder here renders on the page as a real measurement of maximum
        # movement, which is the opposite of what it means.
        return {"text": None, "image": None, "subject": None,
                "subject_word": None, "n": len(window)}
    descs = [f["description"] for f in window]
    word, share = subject_lock(descs)
    return {
        "text": round(mean_text_similarity(descs), 4),
        "image": round(mean_image_distance([int(f["dhash"]) for f in window]), 2),
        "subject": share,
        "subject_word": word,
        "n": len(window),
    }
