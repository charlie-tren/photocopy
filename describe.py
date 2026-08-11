"""Stage 1 - look at yesterday's frame and write today's description.

The describer sees ONLY the image. No previous description, no run history, no
memory of what the picture was supposed to be. That is what makes this a genuine
telephone game rather than an edit.

Two things constrain it, and both are generated from the run's own past rather
than supplied from outside:

- THE SCHEMA. Free-text description is what kills these loops. Left to itself a
  vision model slides toward evocative generic prose ("a moody, atmospheric
  scene"), which draws a generic image, which is described even more generically.
  Six fixed slots make that slide impossible to express. The `anomaly` slot is
  the important one: it forces the single most specific thing in the frame to
  survive into the next prompt, where free prose would have smoothed it away.
- THE AVOID LIST. Terms the run has leaned on lately, forbidden (see avoid.py).
"""
from __future__ import annotations

import base64

import gemini

#: The description IS the data model. Order matters - it is also the order the
#: fields are assembled into the next image prompt.
FIELDS = ("subject", "posture", "setting", "light", "materials", "anomaly")

_GUIDE = {
    "subject": "what the figure is made of and what it is, in one clause",
    "posture": "how it is standing or sitting, and where it is facing",
    "setting": "the room or place around it",
    "light": "direction, hardness and colour of the light",
    "materials": "the three or four materials actually visible, named plainly",
    "anomaly": ("the single most specific detail in this image - the one thing a "
                "generic version of this picture would NOT have. Name it exactly."),
}


def build_prompt(avoid_block: str = "") -> str:
    slots = "\n".join(f'  "{f}": "{_GUIDE[f]}"' for f in FIELDS)
    prompt = (
        "You are cataloguing a photograph for an archive. Describe ONLY what is "
        "visible. Do not interpret it, do not say what it evokes, do not use the "
        "words atmospheric, moody, ethereal, haunting, striking or surreal.\n\n"
        "Return a single JSON object with exactly these keys:\n"
        f"{{\n{slots}\n}}\n\n"
        "Each value is one plain sentence or clause. Be concrete and specific. "
        "Name things rather than qualifying them: 'a brass hinge where the mouth "
        "would be' rather than 'an unsettling facial feature'."
    )
    if avoid_block:
        prompt += f"\n\n{avoid_block}"
    return prompt


def parse(raw) -> dict:
    """Coerce a model response into a complete description.

    Missing keys become empty strings rather than raising: a frame with five of
    six slots still draws, and a run that dies because the describer omitted
    `materials` once would be a stupid way to lose fifty frames of chain.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"description must be an object, got {type(raw).__name__}")
    return {f: str(raw.get(f, "") or "").strip() for f in FIELDS}


def is_usable(desc: dict) -> bool:
    """A description has to carry a subject and at least three filled slots to be
    worth drawing - below that the next frame is generated from almost nothing and
    the chain has effectively been reset by accident."""
    if not desc.get("subject"):
        return False
    return sum(1 for f in FIELDS if desc.get(f)) >= 3


def describe(image_bytes: bytes, settings: dict, avoid_block: str = "",
             mime: str = "image/jpeg") -> dict:
    """Look at one frame, return the next description."""
    payload = base64.b64encode(image_bytes).decode("ascii")
    raw = gemini.generate_with_image(
        build_prompt(avoid_block), payload, mime, settings,
        settings["gemini"]["temperature"])
    return parse(gemini.extract_json(raw))
