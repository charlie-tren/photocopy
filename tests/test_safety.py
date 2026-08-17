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


def test_the_rule_is_anatomy_not_clothing():
    # The first version demanded "fully clothed in plain workwear" and the
    # matching classifier then rejected FRAME 1 - a faceless brass figure, the
    # project's own seed. Every figure in this chain is an unclothed mannequin,
    # so a clothing rule bans the project. Guard the distinction explicitly.
    assert "clothed" not in safety.SMOOTH
    assert "featureless" in safety.SMOOTH
    check = safety._CHECK_PROMPT
    assert "The test is anatomy and framing, not clothing." in check
    assert "normally not wearing clothes" in check


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
