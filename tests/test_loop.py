"""The loop's pure logic: description handling, the self-generated avoid list,
and the collapse detector."""
import io

import pytest
from PIL import Image

import avoid
import collapse
import describe
import draw

LOOP = {"avoid_window": 6, "avoid_min_count": 4, "avoid_term_cap": 14}
COL = {"window": 5, "text_similarity": 0.72, "image_distance": 8,
       "patience": 3, "min_frames": 12}


def desc(**kw):
    base = {f: "" for f in describe.FIELDS}
    base.update(kw)
    return base


# --- describe ---------------------------------------------------------------

def test_parse_fills_missing_slots_rather_than_raising():
    # A describer that drops one key must not break a fifty-frame chain.
    out = describe.parse({"subject": "a brass figure"})
    assert set(out) == set(describe.FIELDS)
    assert out["subject"] == "a brass figure" and out["materials"] == ""


def test_parse_rejects_non_objects():
    with pytest.raises(ValueError):
        describe.parse(["a brass figure"])


def test_is_usable_needs_a_subject_and_three_slots():
    assert not describe.is_usable(desc(posture="standing", setting="a room",
                                       light="hard"))
    assert not describe.is_usable(desc(subject="a figure", posture="standing"))
    assert describe.is_usable(desc(subject="a figure", posture="standing",
                                   setting="a room"))


def test_describer_prompt_carries_the_avoid_block():
    assert "brass, tile" in describe.build_prompt("Do not use: brass, tile")
    assert "anomaly" in describe.build_prompt()


# --- avoid ------------------------------------------------------------------

def test_overused_counts_presence_not_frequency():
    # "brass" nine times in ONE description is a tic inside that frame; the run
    # is only circling if it recurs across frames.
    heavy = desc(subject="brass brass brass brass brass brass brass brass brass")
    hits = avoid.overused([heavy] * 1 + [desc(subject="tile")] * 5, 6, 4, 14)
    assert "brass" not in hits
    spread = [desc(subject="a brass figure") for _ in range(4)] + \
             [desc(subject="a tile figure") for _ in range(2)]
    assert "brass" in avoid.overused(spread, 6, 4, 14)


def test_overused_is_quiet_until_there_is_history():
    assert avoid.overused([desc(subject="a brass figure")] * 3, 6, 4, 14) == []


def test_overused_respects_the_cap_and_skips_stopwords():
    frames = [desc(subject="the brass figure stands in the tiled room with light")
              for _ in range(5)]
    hits = avoid.overused(frames, 6, 4, 2)
    assert len(hits) == 2
    assert "the" not in hits and "with" not in hits


def test_block_is_empty_string_when_nothing_is_overused():
    assert avoid.block([desc(subject="a brass figure")], LOOP) == ""


# --- collapse ---------------------------------------------------------------

def _img(seed: int, size: int = 64) -> bytes:
    im = Image.new("L", (size, size))
    im.putdata([(x * seed + y * (seed + 3)) % 256
                for y in range(size) for x in range(size)])
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def test_dhash_is_stable_and_discriminating():
    assert collapse.dhash(_img(7)) == collapse.dhash(_img(7))
    assert collapse.dhash(_img(7)) != collapse.dhash(_img(31))


def test_text_similarity_bounds():
    a = desc(subject="a brass figure in a tiled room")
    assert collapse.text_similarity(a, a) == pytest.approx(1.0)
    assert collapse.text_similarity(a, desc(subject="")) == 0.0


def test_both_signals_must_agree_before_a_run_is_sealed():
    same = desc(subject="a brass figure standing in a tiled room")
    # Identical text, but the pictures are still moving: not stuck.
    moving = [{"description": same, "dhash": str(collapse.dhash(_img(i)))}
              for i in range(1, 6)]
    assert not collapse.assess(moving, COL)["stuck"]
    # Identical pictures, but the description is casting around: not stuck.
    one = str(collapse.dhash(_img(9)))
    talking = [{"description": desc(subject=f"a figure of {w}"), "dhash": one}
               for w in ("brass", "cloth", "stone", "glass", "wax")]
    assert not collapse.assess(talking, COL)["stuck"]
    # Both frozen: stuck.
    frozen = [{"description": same, "dhash": one} for _ in range(5)]
    assert collapse.assess(frozen, COL)["stuck"]


def test_sealing_needs_patience_and_a_minimum_run_length():
    same = desc(subject="a brass figure standing in a tiled room")
    one = str(collapse.dhash(_img(9)))
    frozen = [{"description": same, "dhash": one} for _ in range(20)]
    # Stuck, but not for long enough yet.
    assert collapse.should_seal(frozen, 0, COL)[0] is False
    assert collapse.should_seal(frozen, 1, COL)[0] is False
    assert collapse.should_seal(frozen, 2, COL)[0] is True
    # Stuck for long enough, but the run is too young to seal.
    assert collapse.should_seal(frozen[:6], 2, COL)[0] is False


def test_strikes_reset_the_moment_a_run_moves():
    moving = [{"description": desc(subject=f"a figure of {w}"),
               "dhash": str(collapse.dhash(_img(i)))}
              for i, w in enumerate(("brass", "cloth", "stone", "glass", "wax"), 1)]
    _seal, reading = collapse.should_seal(moving, 2, COL)
    assert reading["strikes"] == 0


# --- draw -------------------------------------------------------------------

def test_image_prompt_skips_empty_slots_without_dangling_punctuation():
    prompt = draw.build_prompt(desc(subject="a brass figure", posture="standing",
                                    setting="a tiled room"))
    assert "a brass figure, standing." in prompt
    assert "Light:" not in prompt and "Materials:" not in prompt
    assert ".." not in prompt and " ." not in prompt


def test_image_prompt_always_bans_text_in_the_picture():
    assert "no watermark" in draw.build_prompt(desc(subject="a brass figure"))


def test_normalise_gives_every_frame_one_width():
    small = Image.new("RGB", (100, 100), "white")
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    out = draw.normalise(buf.getvalue(), 768)
    assert Image.open(io.BytesIO(out)).size == (768, 768)


def test_draw_refuses_a_description_too_sparse_to_be_a_prompt():
    with pytest.raises(ValueError):
        draw.draw(desc(subject="a figure"), {"image": {"store_width": 768}})
