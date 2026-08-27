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


#: The garment vocabulary of the 28/08/2026 erosion. REPAIRED, NOT STRIPPED, and
#: the distinction is load-bearing: these words turn up in the SUBJECT slot ("a
#: dummy in a sleeveless orange top"), and strip() takes out whole sentences, so
#: routing them there would blank the subject, fail is_usable and kill the chain.
#: Rewriting puts the sleeves back instead, which also means the repair
#: propagates - tomorrow's describer sees a covered figure and says so.
_RECLOTHE = [
    (re.compile(r"\b(?:sleeveless|strapless|off[- ]the[- ]shoulder)\b", re.I), "long-sleeved"),
    (re.compile(r"\b(?:tank|vest|crop|halter|camisole|singlet)[- ]?tops?\b", re.I),
     "long-sleeved shirt"),
    (re.compile(r"\b(?:camisole|singlet)s?\b", re.I), "long-sleeved shirt"),
    (re.compile(r"\bshirtless|\bbare[- ]chested\b", re.I), "fully clothed"),
    (re.compile(r"\bbare[- ]?(shoulders?|back|arms?|torso|midriff)\b", re.I),
     lambda m: "covered " + m.group(1)),
    (re.compile(r"\b(?:exposed|uncovered)\s+(shoulders?|back|arms?|torso|midriff|chest)\b", re.I),
     lambda m: "covered " + m.group(1)),
]


def reclothe(value: str) -> str:
    """Put the sleeves back on a slot rather than deleting the sentence."""
    if not value:
        return value
    for pattern, replacement in _RECLOTHE:
        value = pattern.sub(replacement, value)
    return value


#: Audit only - what `flagged` reports. Wider than what is stripped, so a garment
#: word shows up in the log even though it is repaired rather than removed.
_GARMENT = re.compile(
    r"\b(shirtless|sleeveless|strapless|halter|camisole|singlet|"
    r"(?:crop|tank|vest)[- ]?tops?|midriff|off[- ]the[- ]shoulder|"
    r"(?:bare|exposed|uncovered)[- ]?(?:shoulders?|back|arms?|torso|chest|midriff))\b",
    re.I)

_SENTENCE = re.compile(r"(?<=[.;])\s+")

#: Appended to every image prompt.
#:
#: THE LINE IS ANATOMY, NOT CLOTHING - and getting that wrong once already cost a
#: CI run. The first version of this said "fully clothed in plain workwear", and
#: the classifier written to match it rejected FRAME 1: a faceless folded-brass
#: figure, the project's own seed and the whole look of the thing. Every figure
#: in this chain is an unclothed mannequin. A rule that bans unclothed mannequins
#: bans the project.
#:
#: What actually went wrong in frames 3-7 was anatomical realism: the figure
#: gained musculature, then buttocks, then a pose that framed them. So the guard
#: pins the figure where frame 1 already was - smooth, featureless, no anatomy -
#: which blocks the drift without dictating a costume the project never had.
#: "wherever it is not covered" rather than "where a person would have features".
#: The old wording described a bare body, which fought NEGATIVE's "no exposed
#: chest" in the same prompt: flux drew the smooth bare torso the first clause
#: asked for and the classifier refused it under the second. That contradiction
#: is what produced the 22/08 probe's rejection loop at steps 6 and 7. The line
#: is still anatomy and not costume - it dictates nothing to wear, it just stops
#: insisting the figure is uncovered.
SMOOTH = ("The figure is a smooth featureless mannequin with no anatomical "
          "detail of any kind: a plain sculptural form, no rendered muscles, no "
          "buttocks, no chest or groin detail, blank and unmodelled wherever it "
          "is not covered.")

#: THE CLOTHING FLOOR, added 28/08/2026, and the reason it exists is worth
#: keeping because I removed the first version of it and this is what happened.
#:
#: On 17/08 the rule was set as "anatomy, not clothing", because a clothing rule
#: had rejected the old brass-figure seed. That reasoning was right about the OLD
#: seed and wrong about this one - the diver is clothed by construction, so a
#: clothing floor costs the project nothing. Removing it cost twelve frames:
#:
#:   2-4  jumpsuit      7-9  shirt, turtleneck     11  sleeve
#:   5-6  top          10  turtleneck, sweater     12  SLEEVELESS
#:
#: Nothing was wrong with any single step. Clothing is incidental detail - it is
#: never the subject and never the anomaly - and a lossy describer drops a little
#: incidental detail every frame. "Figure" is the stable core; the clothes erode
#: off it. So the clothes cannot live in the description. They have to be
#: re-asserted by the DRAWER on every frame, independently of what the describer
#: happened to notice, or they will keep sliding off.
CLOTHED = ("It is dressed in plain workwear that covers it completely: a "
           "long-sleeved top to the wrists and full-length trousers to the "
           "ankles. Shoulders, arms, chest, back and midriff are all covered. "
           "Nothing sleeveless, nothing off-the-shoulder, no bare torso.")

NEGATIVE = ("No nudity, no bare skin, no buttocks, no exposed chest, no "
            "genitals, no underwear, nothing sexual or suggestive, no "
            "anatomically detailed or lifelike body. Not shirtless, not "
            "sleeveless, no vest top, no tank top, no bare shoulders, no bare "
            "back, no bare arms, no exposed midriff.")


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


#: Rewritten, not stripped. The drift was legible in the describer's own words
#: long before anyone looked at the pictures: "mannequin" -> "male body" ->
#: "statue of a male body". But stripping a sentence that says "body" would have
#: blanked the SUBJECT slot, and a description with no subject fails
#: `is_usable` and kills the chain - so the fix has to be a rewrite that keeps
#: the sentence standing while taking the anatomy out of it.
_DEANATOMISE = [
    (re.compile(r"\b(?:male|female|human|man'?s|woman'?s)\s+"
                r"(?:body|bodies|torso|figure|form|nude|anatomy)\b", re.I), "mannequin"),
    (re.compile(r"\b(?:male|female)\s+(?:mannequin|statue|sculpture)\b", re.I), "mannequin"),
    (re.compile(r"\b(?:body|torso|anatomy)\b", re.I), "form"),
    (re.compile(r"\b(?:lifelike|life-?like|realistic|anatomical(?:ly)?)\b", re.I), "plain"),
    (re.compile(r"\b(?:flesh|skin)\b", re.I), "surface"),
]


def deanatomise(value: str) -> str:
    """Take the anatomy out of a slot without destroying it.

    Runs AFTER `strip`: strip removes whole sentences about undress, this
    neutralises the quieter words that were carrying the drift - "a metallic
    yellow statue of a male body" becomes "a metallic yellow statue of a
    mannequin", which is both accurate and no longer an instruction.
    """
    if not value:
        return value
    for pattern, replacement in _DEANATOMISE:
        value = pattern.sub(replacement, value)
    return value


def flagged(text: str) -> list[str]:
    """Which watched terms appear. For logging - a silent guard is unauditable."""
    text = text or ""
    return sorted({m.group(0).lower() for m in _BODY.finditer(text)}
                  | {m.group(0).lower() for m in _GARMENT.finditer(text)})


def describe_clause() -> str:
    return (
        "The figure in this picture is a prop, not a person. Describe what it is "
        "made of, how it is posed and what is around it. Do NOT describe its "
        "body, its anatomy, its state of undress or any part of it that would be "
        "private on a person - not in any slot, and least of all the anomaly. If "
        "the figure appears unclothed, say nothing at all about that; describe "
        "its material and posture and move on. Never use the words nude, naked, "
        "bare, buttocks or any anatomical term.\n\n"
        "The figure is clothed. Describe the clothing as covering it - long "
        "sleeves, full-length trousers - and never as sleeveless, strapless, "
        "off-the-shoulder, a vest or a tank top, and never mention bare "
        "shoulders, a bare back or a bare torso. If the clothing looks skimpy "
        "or partial, describe it as full-length workwear instead."
    )


def draw_clause() -> str:
    """SMOOTH pins the anatomy, CLOTHED pins the coverage. Both, every frame -
    the 28/08 erosion happened in the gap where only the first one existed."""
    return SMOOTH + " " + CLOTHED


#: Written against real verdicts, not from imagination. An earlier version asked
#: "does this read as undressed, even a mannequin?" and it answered false for
#: frame 1 - "unclothed mannequin figure" - which is the seed of the whole
#: project. The question has to be about RENDERED ANATOMY, and it has to say so
#: with an example of each side or it collapses back to "is it wearing clothes".
_CHECK_PROMPT = (
    "You are a content check for a public art website. The site publishes photos "
    "of abstract mannequins and sculptural figures, which are normally not "
    "wearing clothes. That on its own is fine and is the point of the project.\n\n"
    "Answer with a single JSON object:\n"
    '{"safe": true or false, "reason": "one short phrase"}\n\n'
    "Answer FALSE if the image shows any of these:\n"
    "- buttocks, genitals, a nipple or a groin rendered as anatomy\n"
    "- a bare torso, a bare back, bare shoulders or a bare midriff - including on a smooth featureless mannequin. A vest, tank top, singlet, crop top or strapless top leaves the shoulders and back bare and answers false. Judge the TORSO only: bare arms below the shoulder, a bare head, face, hands and feet are all fine, and sleeve length is not the test.\n"
    "- a lifelike naked human body, or a figure with realistic musculature and "
    "body detail that reads as a naked person rather than as a sculpture\n"
    "- a pose or camera angle that frames a backside, crotch or chest as the "
    "subject of the picture\n"
    "- anything sexual, suggestive or fetishistic\n"
    "- a real person, undressed\n\n"
    "Answer TRUE for: a figure whose torso, back, shoulders and midriff are "
    "covered, however abstract or featureless it is and whatever its sleeves "
    "are doing; a machine; an object; an empty room.\n\n"
    "Two tests, and it fails on either. ANATOMY: a gold figure with a rendered "
    "backside, photographed from behind, is not safe. COVERAGE: a grey "
    "mannequin in an orange vest top with its bare back to the camera is not "
    "safe either, even though nothing anatomical is rendered - that one passed "
    "an earlier version of this check and should not pass this one. A faceless "
    "figure in a long-sleeved jumpsuit is safe."
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
