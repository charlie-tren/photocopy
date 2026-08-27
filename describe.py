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

A third constraint, added 17/08/2026 and NOT self-generated: the describer is
told not to record anatomy or undress, and any sentence that does is stripped
before it can reach a prompt. That is an outside rule and it is meant to be -
see safety.py.
"""
from __future__ import annotations

import base64
import re

import gemini
import safety

#: The description IS the data model. Order matters - it is also the order the
#: fields are assembled into the next image prompt.
#: "covering" is a slot rather than an instruction on purpose. On 22/08/2026 a
#: probe watched the chain undress itself in four steps: the subject went from
#: "a plastic mannequin wearing a tan turtleneck sweater and grey cargo
#: trousers" to "A mannequin made of smooth white plastic", and the clothes
#: survived only as "knitted fabric, denim" in materials, which is far too weak
#: to draw from. Two frames later the classifier was rejecting bare torsos.
#: Telling the describer to keep clothing in the subject would have been rule
#: number five in a prompt that already has four; giving it a slot of its own
#: removes the choice instead.
FIELDS = ("subject", "covering", "posture", "setting", "light", "materials",
          "anomaly")

_GUIDE = {
    "subject": "what the figure is made of and what it is, in one clause",
    # The fallback used to read "if it is genuinely covered by nothing, say
    # 'bare sculptural form'" - an escape hatch that told the describer how to
    # write the undressed state, in the one slot built to prevent it. The slot
    # then recorded the erosion faithfully instead of resisting it: sweater ->
    # short-sleeved shirt -> sleeveless top, frames 10 to 12. There is no bare
    # option any more; a figure is covered, and a non-figure has no covering.
    "covering": ("what the figure is wearing or wrapped in, named plainly - the "
                 "garments, suit, casing or shell that cover it. It always has "
                 "sleeves to the wrist and legs to the ankle unless it is a "
                 "sealed suit. If the subject is not a figure at all, say "
                 "'not a figure'."),
    "posture": "how it is standing or sitting, and where it is facing",
    "setting": "the room or place around it",
    "light": "direction, hardness and colour of the light",
    "materials": "the three or four materials actually visible, named plainly",
    "anomaly": ("the single most specific detail in this image - the one thing a "
                "generic version of this picture would NOT have. Name it exactly."),
}

#: Rendered lettering is an artefact of the image generator, not part of the
#: scene, and it is a RUNAWAY if it ever reaches a description. The anomaly slot
#: asks for the most distinctive thing in the frame, and text is always the most
#: distinctive thing in a photograph, so one stray watermark gets promoted into
#: the next prompt as an instruction to draw text - which draws bigger text,
#: which is more distinctive still. Observed live: an 18-frame probe grew
#: "PREKS-OT CONGLIONCE" from a corner mark to a banner in two frames.
_TEXT_ARTEFACT = re.compile(
    r"\b(text|lettering|letters|words?|writing|written|caption|watermark|"
    r"signature|logo|label|signage|inscription|inscribed|typeface|font|"
    r"printed|imprint|numerals?)\b", re.I)

_SENTENCE = re.compile(r"(?<=[.;])\s+")


def strip_text_artefacts(value: str) -> str:
    """Drop any sentence that talks about lettering in the picture.

    Surgical rather than blunt: a slot is usually several clauses and only one
    of them is about the watermark, so the rest of the observation survives.
    """
    if not value or not _TEXT_ARTEFACT.search(value):
        return value
    kept = [s for s in _SENTENCE.split(value) if not _TEXT_ARTEFACT.search(s)]
    return " ".join(k.strip() for k in kept if k.strip()).strip()


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
        "would be' rather than 'an unsettling facial feature'.\n\n"
        "If the image contains any lettering, text, numbers, a watermark or a "
        "signature, IGNORE IT COMPLETELY. It is a flaw in how the picture was "
        "made, not something in the scene, and it must never appear in any "
        "value - least of all the anomaly. Describe what the lettering sits on "
        "instead, or choose a different detail.\n\n"
        f"{safety.describe_clause()}"
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
    # Stripped here, not at draw time, so the stored and displayed description
    # is clean too - otherwise the page would show a watermark being described
    # even though the prompt never saw it. The same applies to anatomy: the
    # caption is published, so a slot that names a body part is a problem on the
    # page as well as in tomorrow's prompt.
    return {f: safety.reclothe(safety.deanatomise(
                safety.strip(strip_text_artefacts(str(raw.get(f, "") or "").strip()))))
            for f in FIELDS}


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
