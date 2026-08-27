"""The decency floor.

Written against the real failure: frames 3-7 of the live chain walked from a
folded-brass figure to a nude male body seen from behind. The descriptions that
produced them are used verbatim below, so a change that would let that run
happen again fails here.
"""
import pytest

import describe
import draw
import safety
import step

#: Verbatim from data/frames/0006.json, the frame before the worst one. Note
#: what is NOT in it: no anatomical word, nothing lewd, nothing a word filter
#: could ever have caught. This is the whole reason the image gate exists.
FRAME_6 = {
    "subject": "a metallic yellow statue of a male body",
    "posture": "standing upright with its back turned directly toward the camera",
    "setting": "a narrow shower cubicle lined with white tile",
    "light": "flat overhead light, soft shadows",
    "materials": "yellow enamel, white ceramic tile, stainless steel",
    "anomaly": "a spoked metal water outlet centered in the shower tray",
}


# --- the word filter --------------------------------------------------------

def test_strips_anatomy_from_a_slot():
    src = ("a polished gold figure. Its bare buttocks face the camera. "
           "It stands on a drain.")
    assert safety.strip(src) == "a polished gold figure. It stands on a drain."


def test_strips_the_plain_nouns_not_just_the_lurid_ones():
    # The describer never wrote "erotic". It wrote "buttocks", because the schema
    # asks for plain nouns and that IS the plain noun. Banning only loaded words
    # would have caught nothing that actually happened.
    for word in ("buttocks", "nude", "naked", "unclothed", "bare skin", "groin"):
        assert safety.flagged(f"the figure shows {word} here") != []


def test_innocent_descriptions_are_untouched():
    for s in (FRAME_6["subject"], FRAME_6["posture"], FRAME_6["anomaly"],
              "one bare bulb overhead, hard shadows",   # "bare" alone is fine
              "a bare tiled wall", ""):
        assert safety.strip(s) == s


def test_parse_applies_the_filter_to_every_slot():
    out = describe.parse({"subject": "a gold mannequin",
                          "anomaly": "a drain. The naked figure faces away."})
    assert out["anomaly"] == "a drain."


# --- the drawn prompt -------------------------------------------------------

def test_prompt_de_anatomises_the_figure_and_says_so_last():
    prompt = draw.build_prompt(FRAME_6)
    assert "no anatomical detail" in prompt
    # Tail position is load-bearing: flux weights the end of a prompt, and the
    # slots in the middle are exactly what kept drawing an undressed figure.
    assert prompt.index("smooth featureless") > prompt.index(FRAME_6["subject"])
    assert prompt.rstrip().endswith(safety.NEGATIVE)


def test_the_rule_is_anatomy_AND_coverage():
    """Both, and the history of this test is the point.

    17/08/2026 it asserted the opposite - "the test is anatomy and framing, NOT
    clothing" - because a clothing rule had rejected the old brass-figure seed.
    That was right about that seed and wrong as a general rule, and it cost
    frames 11-12: a grey mannequin in a vest top with a bare back, which passed
    the anatomy-only check exactly as written.

    The reconciliation is that the two clauses do different jobs. SMOOTH keeps
    the figure unmodelled so no anatomy is ever rendered; CLOTHED keeps it
    covered so there is nothing to render. Neither alone was enough.
    """
    assert "featureless" in safety.SMOOTH          # anatomy floor, unchanged
    assert "no anatomical detail" in safety.SMOOTH
    assert "long-sleeved top to the wrists" in safety.CLOTHED   # coverage floor
    assert "Nothing sleeveless" in safety.CLOTHED
    # Both reach the drawer on every frame, not one or the other.
    clause = safety.draw_clause()
    assert "featureless" in clause and "long-sleeved" in clause


def test_describer_is_told_not_to_record_anatomy():
    assert "Never use the words nude, naked, bare, buttocks" in describe.build_prompt()


# --- the image gate ---------------------------------------------------------

def test_check_fails_closed_when_the_vision_call_dies(monkeypatch):
    # The day the API is down must not be the day anything gets published.
    def boom(*a, **kw):
        raise RuntimeError("quota exhausted")
    monkeypatch.setattr(safety.gemini, "generate_with_image", boom)
    safe, reason = safety.check_image(b"x", {"gemini": {}, "safety": {}})
    assert safe is False and "quota exhausted" in reason


def test_check_fails_closed_on_a_junk_verdict(monkeypatch):
    monkeypatch.setattr(safety.gemini, "generate_with_image",
                        lambda *a, **kw: '{"probably": "fine"}')
    assert safety.check_image(b"x", {"gemini": {}, "safety": {}})[0] is False


def test_unsafe_frames_are_redrawn_then_the_day_is_abandoned(monkeypatch):
    calls = {"draw": 0}

    def fake_draw(desc, settings):
        calls["draw"] += 1
        return b"img", "prompt"

    monkeypatch.setattr(step.draw, "draw", fake_draw)
    monkeypatch.setattr(step.safety, "check_image",
                        lambda *a, **kw: (False, "bare buttocks"))
    with pytest.raises(step.Unpublishable):
        step._draw_something_publishable(
            FRAME_6, {"safety": {"max_attempts": 3, "retry_pause_seconds": 0}})
    assert calls["draw"] == 3


def test_a_frame_that_passes_is_kept(monkeypatch):
    monkeypatch.setattr(step.draw, "draw", lambda d, s: (b"img", "prompt"))
    monkeypatch.setattr(step.safety, "check_image", lambda *a, **kw: (True, "clothed"))
    image, prompt = step._draw_something_publishable(FRAME_6, {"safety": {}})
    assert image == b"img" and prompt == "prompt"


def test_a_redraw_that_comes_back_clean_is_accepted(monkeypatch):
    # The realistic case: flux is stochastic, so the second seed is often fine.
    verdicts = iter([(False, "bare buttocks"), (True, "clothed figure")])
    monkeypatch.setattr(step.draw, "draw", lambda d, s: (b"img", "prompt"))
    monkeypatch.setattr(step.safety, "check_image", lambda *a, **kw: next(verdicts))
    assert step._draw_something_publishable(
        FRAME_6, {"safety": {"retry_pause_seconds": 0}})[0] == b"img"


# --- the describer's own words were the early warning ------------------------

def test_deanatomise_keeps_the_slot_standing():
    # Stripping this sentence would blank the SUBJECT, which fails is_usable and
    # kills the chain. It has to be rewritten, not removed.
    out = describe.parse({"subject": FRAME_6["subject"]})
    assert out["subject"] == "a metallic yellow statue of a mannequin"
    assert describe.is_usable({**FRAME_6, "subject": out["subject"]})


def test_deanatomise_catches_the_actual_drift_words():
    # Verbatim progression from frames 2, 5 and 6 of the live chain.
    seen = [
        "a featureless gold metallic mannequin figure",
        "a polished gold male mannequin",
        "a metallic yellow statue of a male body",
    ]
    cleaned = [safety.deanatomise(s) for s in seen]
    assert "male" not in " ".join(cleaned)
    assert "body" not in " ".join(cleaned)
    # ...and the harmless one is left alone.
    assert cleaned[0] == seen[0]


def test_rejections_are_logged_without_the_image(tmp_path, monkeypatch):
    import json as _json
    monkeypatch.setattr(step, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(step.draw, "draw", lambda d, s: (b"img", "the prompt"))
    monkeypatch.setattr(step.safety, "check_image", lambda *a, **kw: (False, "bare buttocks"))
    settings = {"safety": {"max_attempts": 2, "retry_pause_seconds": 0},
                "timezone": "Australia/Sydney"}
    with pytest.raises(step.Unpublishable):
        step._draw_something_publishable(FRAME_6, settings)
    rows = [_json.loads(l) for l in
            (tmp_path / step.REJECT_LOG).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["reason"] == "bare buttocks" and rows[0]["prompt"] == "the prompt"
    assert "image" not in rows[0]


# --- the covering slot ------------------------------------------------------
# Added 22/08/2026 after a probe watched the chain undress itself in four steps.
# The failure was silent: every existing test still passed with the clothing
# gone, because nothing asserted the schema's shape or where a slot lands in the
# prompt. These are the two checks that would have caught it.

def test_covering_is_a_slot_the_describer_cannot_drop():
    import describe
    assert "covering" in describe.FIELDS
    assert "covering" in describe.build_prompt()
    parsed = describe.parse({"subject": "a mannequin"})
    assert "covering" in parsed


def test_covering_rides_in_the_lead_not_in_the_tail():
    import draw
    prompt = draw.build_prompt({
        "subject": "a mannequin", "covering": "a tan turtleneck and grey trousers",
        "posture": "standing", "setting": "a wheat field", "light": "flat",
        "materials": "plastic, denim", "anomaly": "a yellow helmet"})
    assert "tan turtleneck" in prompt
    # Before the subject's clothes went missing this was implicit. Now it is not:
    # a garment named after the setting is a garment flux mostly ignores.
    assert prompt.index("tan turtleneck") < prompt.index("wheat field")
    assert "wearing a tan turtleneck" in prompt


def test_the_seed_is_covered():
    from common import load_settings
    seed = load_settings()["seed"]
    assert seed.get("covering"), "a bare seed is how the last chain started"


def test_the_smooth_clause_does_not_contradict_the_negative():
    import safety
    # SMOOTH used to say "blank where a person would have features", i.e. bare,
    # while NEGATIVE forbids an exposed chest in the same prompt. flux drew the
    # first and the classifier refused it under the second.
    assert "where a person would have features" not in safety.SMOOTH
    assert "not covered" in safety.SMOOTH


# --- the clothing floor (28/08/2026) -----------------------------------------

#: Verbatim `covering` slots, frames 10-12. The erosion is fully legible here and
#: no rule was reading it: sweater -> short-sleeved shirt -> sleeveless top.
COVERING = {
    10: "an orange hard hat, a tan turtleneck sweater, light blue trousers with a woven belt, and long dark gauntlet gloves",
    11: "an orange short-sleeved shirt, blue denim jeans, a brown leather waist strap, and an orange hardhat",
    12: "an orange sleeveless top, blue jeans, a brown leather waist band, and a black arm sleeve",
}


def test_the_garment_that_ended_the_chain_is_repaired_not_deleted():
    # "sleeveless" sat in frame 12's covering slot in plain sight. Deleting the
    # sentence would empty the slot; the repair keeps it and puts sleeves back.
    fixed = safety.reclothe(COVERING[12])
    assert "sleeveless" not in fixed
    assert "long-sleeved top" in fixed
    assert "blue jeans" in fixed and "brown leather waist band" in fixed


def test_every_near_shirtless_garment_is_repaired():
    for bad, want in (
        ("an orange vest top", "long-sleeved shirt"),
        ("a grey tank top", "long-sleeved shirt"),
        ("a strapless orange top", "long-sleeved"),
        ("a crop top", "long-sleeved shirt"),
        ("bare shoulders", "covered shoulders"),
        ("an exposed midriff", "covered midriff"),
        ("a shirtless dummy", "fully clothed"),
    ):
        assert want in safety.reclothe(bad), bad


def test_clothing_survives_the_repair_untouched():
    for good in (COVERING[10], "a long-sleeved boiler suit and heavy boots",
                 "one bare bulb overhead, hard shadows", "a bare tiled wall", ""):
        assert safety.reclothe(good) == good


def test_the_drawer_asserts_clothing_regardless_of_the_description():
    # The whole lesson of frames 2-12: clothing cannot live in the description,
    # because incidental detail erodes. It has to be re-stated every frame.
    naked_desc = {"subject": "a smooth grey synthetic dummy", "covering": "",
                  "posture": "standing with its back turned", "setting": "a field",
                  "light": "flat overcast", "materials": "grey plastic",
                  "anomaly": "a tractor on the horizon"}
    prompt = draw.build_prompt(naked_desc)
    assert "long-sleeved top to the wrists" in prompt
    assert "full-length trousers" in prompt
    for phrase in ("Not shirtless", "not sleeveless", "no bare shoulders"):
        assert phrase in prompt


def test_the_classifier_is_told_coverage_as_well_as_anatomy():
    check = safety._CHECK_PROMPT
    assert "a bare torso, a bare back, bare shoulders" in check
    # The floor is the TORSO. An earlier draft demanded "sleeves to the wrist"
    # and CI rejected f0010 - the fully clothed turtleneck frame the chain was
    # rolled back to - for having the wrong sleeves. Enforce the line Charlie
    # actually drew (shirtless / near-shirtless), not a stricter one.
    assert "sleeve length is not the test" in check
    # The frame-12 case named explicitly, so a future edit that loosens this
    # has to argue with the example rather than delete an abstraction.
    assert "orange vest top with its bare back" in check
    assert "should not pass this one" in check


def test_the_covering_slot_no_longer_teaches_the_bare_state():
    assert "bare sculptural form" not in describe._GUIDE["covering"]
    assert "sleeves to the wrist" in describe._GUIDE["covering"]
