"""The decency floor. The one thing in this project that IS an outside constraint.

`docs/collapse.md` argues that nothing may enter the chain from outside, because
movement that came from Charlie is not evidence of anything. That argument is
about AESTHETICS. It does not extend to what the page is allowed to publish, and
this module is a deliberate, documented exception to it - see the "Where this
does not apply" section of that document.

WHAT WENT WRONG (frames 3-7, 12-16/08/2026). The chain walked from a folded-brass
figure to a nude male body seen from behind, and by frame 7 to a crouched figure
whose buttocks filled the frame. **No description ever said anything lewd.** The
words stayed flat and clinical the whole way down - "a polished gold male
mannequin", "standing upright facing the back wall". The nudity was supplied
entirely by the image model reading an unclothed mannequin in a tiled wet room,
and then by the describer faithfully recording what it had drawn ("mannequin" ->
"male body" -> "glossy life-sized mannequin"), which drew it harder next time.

That is why the guard is in three places and not one:

1. `describe_clause()` - the describer is told not to record nudity or anatomy.
2. `strip(...)` - and if it does anyway, those sentences never reach the prompt.
3. `draw_clause()` / `NEGATIVE` - the drawer is told to clothe the figure.
4. `check_image(...)` - and then the drawn frame is LOOKED AT before it is kept.

Layers 1-3 are prompt text, which flux and Gemini are both free to ignore; only
layer 4 actually knows what was drawn. A frame that fails it is never written, so
the chain cannot continue from it. Do not remove layer 4 and keep the wording -
that would look like a guard while being one.
"""
from __future__ import annotations

import base64
import re

import gemini

#: Sentences mentioning any of these never reach an image prompt. Deliberately
#: about BODIES rather than about tone: "sensual" is a word the describer would
#: never use, "buttocks" is one it used happily because it is a plain anatomical
#: noun and the schema asks for plain nouns.
_BODY = re.compile(
    r"\b(nude|nudes|nudity|naked|nakedness|unclothed|undressed|bare[- ]?"
    r"(?:skin|body|bodies|chest|breast|breasts|buttock|buttocks|bottom)|"
    r"buttock|buttocks|butt|butts|backside|rear[- ]end|glutes|gluteal|"
    r"genital|genitals|genitalia|groin|crotch|penis|phallus|phallic|scrotum|"
    r"testicle|testicles|vulva|vagina|breast|breasts|nipple|nipples|"
    r"pubic|loins|erotic|sensual|seductive|provocative|suggestive|"
    r"topless|bottomless|lingerie|underwear)\b", re.I)

_SENTENCE = re.compile(r"(?<=[.;])\s+")

#: Appended to every image prompt. Positive instruction as well as negative:
#: "no nudity" alone leaves the model free to draw a smooth featureless nude,
#: which is exactly what frames 2-6 were, so the figure must be affirmatively
#: dressed in something.
CLOTHED = ("The figure is fully clothed in plain workwear - long sleeves and "
           "long trousers, or a boiler suit - covering it from neck to ankle.")

NEGATIVE = ("No nudity, no bare skin, no buttocks, no exposed chest, no "
            "underwear, nothing sexual or suggestive. Nobody is undressed.")


def strip(value: str) -> str:
    """Drop any sentence describing a body or its state of dress.

    Sentence-surgical, matching `describe.strip_text_artefacts`: a slot is
    usually several clauses and only one of them is the problem, so the rest of
    the observation survives and the chain keeps its continuity.
    """
    if not value or not _BODY.search(value):
        return value
    kept = [s for s in _SENTENCE.split(value) if not _BODY.search(s)]
    return " ".join(k.strip() for k in kept if k.strip()).strip()


def flagged(text: str) -> list[str]:
    """Which banned terms appear. For logging - a silent guard is unauditable."""
    return sorted({m.group(0).lower() for m in _BODY.finditer(text or "")})


def describe_clause() -> str:
    return (
        "The figure in this picture is a prop, not a person. Describe what it is "
        "made of, how it is posed and what is around it. Do NOT describe its "
        "body, its anatomy, its state of undress or any part of it that would be "
        "private on a person - not in any slot, and least of all the anomaly. If "
        "the figure appears unclothed, say nothing at all about that; describe "
        "its material and posture and move on. Never use the words nude, naked, "
        "bare, buttocks or any anatomical term."
    )


def draw_clause() -> str:
    return CLOTHED


_CHECK_PROMPT = (
    "You are a content check for a public website. Look at this image and answer "
    "with a single JSON object:\n"
    '{"safe": true or false, "reason": "one short phrase"}\n\n'
    "Answer false if the image shows: nudity or partial nudity, bare buttocks, "
    "an exposed chest or genitals, visible underwear, a figure that reads as "
    "undressed even if it is a mannequin or statue, anything sexual or "
    "suggestive, or any sexualised framing of a body.\n\n"
    "A clothed figure is safe. A machine, an object or an empty room is safe. "
    "Classical or artistic framing does NOT make an unclothed body safe here - "
    "this is a plain decency floor, not an art judgement. If you are unsure, "
    "answer false."
)


def check_image(image_bytes: bytes, settings: dict,
                mime: str = "image/jpeg") -> tuple[bool, str]:
    """Look at a drawn frame before it is kept. (safe, reason).

    FAILS CLOSED. Every error path - a malformed answer, a quota refusal, a
    network drop - returns unsafe. The alternative is that the day the vision
    API is down is the day anything at all gets published, which is precisely
    backwards: a missing frame is a gap in a chain, a bad frame is on the
    internet under Charlie's own name.
    """
    payload = base64.b64encode(image_bytes).decode("ascii")
    try:
        raw = gemini.generate_with_image(
            _CHECK_PROMPT, payload, mime, settings,
            settings.get("safety", {}).get("temperature", 0.0))
        verdict = gemini.extract_json(raw)
    except Exception as exc:                      # noqa: BLE001 - see docstring
        return False, f"check failed ({type(exc).__name__}: {exc})"
    if not isinstance(verdict, dict) or "safe" not in verdict:
        return False, f"check returned no verdict: {str(verdict)[:120]}"
    reason = str(verdict.get("reason", "") or "").strip()[:160]
    return bool(verdict["safe"]) is True, reason or "no reason given"
