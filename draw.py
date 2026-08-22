"""Stage 2 - draw the description. Cloudflare Workers AI (free tier), flux-schnell.

The style clause is FIXED and deliberately plain. Every word of house style in
this prompt is a word the loop cannot drift in, and a project about drift should
put as little of itself in the way as possible: the register stays "a photograph"
forever, so anything that changes between frames changed because the loop changed
it, not because the prompt let it.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request

from PIL import Image

import describe
import safety
from common import rel

_STYLE = ("A photograph. Sharp focus, natural depth of field, no visible camera "
          "effects, no border, no frame.")
_NEGATIVE = ("Absolutely no text, no letters, no words, no captions, no numbers, "
             "no signature and no watermark anywhere in the image.")


def build_prompt(desc: dict) -> str:
    """Assemble the image prompt from the six slots, in schema order.

    Empty slots are skipped rather than emitted blank - flux reads a dangling
    "Light: ." as an instruction about punctuation and it shows.
    """
    subject = (desc.get("subject") or "").strip()
    covering = (desc.get("covering") or "").strip()
    posture = (desc.get("posture") or "").strip()
    # Covering rides in the LEAD, immediately after the subject. It was the
    # subject slot quietly losing the clothes that undressed the chain on
    # 22/08/2026, and a garment named only under "materials" does not survive
    # the trip - "knitted fabric, denim" drew a bare torso in jeans.
    if covering and not covering.lower().startswith(
            ("wearing", "clad", "dressed", "wrapped", "in ", "a sealed")):
        covering = f"wearing {covering}"
    lead = ", ".join(p for p in (subject, covering, posture) if p) or "a figure"
    parts = [_STYLE, lead + "."]
    for field, prefix in (("setting", ""), ("light", "Light: "),
                          ("materials", "Materials: "), ("anomaly", "")):
        value = (desc.get(field) or "").strip()
        if value:
            parts.append(f"{prefix}{value}".rstrip(".") + ".")
    # Clothing goes AFTER the slots and the negative goes last. flux weights the
    # tail of a prompt more heavily, and the slots are exactly what kept drawing
    # an undressed figure, so a clause in front of them loses the argument.
    parts.append(safety.draw_clause())
    parts.append(_NEGATIVE)
    parts.append(safety.NEGATIVE)
    return " ".join(parts)


def _cf_image(prompt: str, settings: dict) -> bytes:
    acct = os.environ.get("CF_ACCOUNT_ID", "").strip()
    tok = os.environ.get("CF_API_TOKEN", "").strip()
    if not acct or not tok:
        raise RuntimeError("CF_ACCOUNT_ID / CF_API_TOKEN not set")
    cfg = settings["image"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{cfg['model']}"
    body = json.dumps({"prompt": prompt, "steps": cfg["steps"]}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("timeout", 120)) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        # urllib raises before anyone reads the body, and Cloudflare puts the
        # actual reason there. Without this a 400 is indistinguishable from a
        # 400, which is how an entire probe run was wasted.
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(
            f"Cloudflare HTTP {exc.code}: {detail} | prompt was: "
            f"{prompt[:300]!r}") from exc
    if not data.get("success") or "result" not in data:
        raise RuntimeError(f"Cloudflare returned no image: {str(data.get('errors'))[:200]}")
    return base64.b64decode(data["result"]["image"])


def normalise(raw: bytes, width: int) -> bytes:
    """One canonical size and format for every frame.

    Not cosmetic: collapse.dhash compares frames against each other, and a run
    whose images changed size mid-chain would show a distance step that the loop
    did not actually produce.
    """
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def draw(desc: dict, settings: dict) -> tuple[bytes, str]:
    """(image bytes, the prompt used). Raises on failure - step.py decides what a
    failed frame means for the run, because silently skipping a day would leave a
    gap in a chain whose whole claim is that each frame came from the last."""
    if not describe.is_usable(desc):
        raise ValueError("description too sparse to draw")
    prompt = build_prompt(desc)
    raw = _cf_image(prompt, settings)
    return normalise(raw, settings["image"]["store_width"]), prompt
