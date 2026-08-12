"""The loop's pure logic: description handling, the self-generated avoid list,
and the movement reading."""
import io

import pytest
from PIL import Image

import avoid
import collapse
import describe
import draw

LOOP = {"avoid_window": 6, "avoid_min_count": 4, "avoid_term_cap": 14}
COL = {"window": 5}


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
    # "brass" nine times in ONE description is a tic inside that frame; the
    # chain is only circling if it recurs across frames.
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


# --- movement ---------------------------------------------------------------

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


def test_assess_separates_the_two_kinds_of_stillness():
    same = desc(subject="a brass figure standing in a tiled room")
    one = str(collapse.dhash(_img(9)))
    # Words frozen, pictures still moving.
    words_stuck = collapse.assess(
        [{"description": same, "dhash": str(collapse.dhash(_img(i)))}
         for i in range(1, 6)], COL)
    assert words_stuck["text"] == pytest.approx(1.0)
    assert words_stuck["image"] > 0
    # Pictures frozen, words still casting around.
    pics_stuck = collapse.assess(
        [{"description": desc(subject=f"a figure of {w}"), "dhash": one}
         for w in ("brass", "cloth", "stone", "glass", "wax")], COL)
    assert pics_stuck["image"] == 0.0
    assert pics_stuck["text"] < 1.0


def test_assess_reports_and_never_decides():
    # Nothing in this module may tell the chain to stop: there are no runs and it
    # is never reset. A verdict key creeping back in is the regression to catch.
    frozen = [{"description": desc(subject="a brass figure"),
               "dhash": str(collapse.dhash(_img(9)))} for _ in range(8)]
    reading = collapse.assess(frozen, COL)
    assert set(reading) == {"text", "image", "n"}
    assert not hasattr(collapse, "should_seal")


def test_assess_is_honest_about_a_chain_too_short_to_read():
    # Frame 1 has nothing to be compared with. A zero here would render on the
    # page as "0% alike, 64/64 apart", i.e. maximum movement, which is a lie.
    assert collapse.assess([], COL)["n"] == 0
    one = collapse.assess([{"description": desc(subject="a figure"),
                            "dhash": "1"}], COL)
    assert one["n"] == 1
    assert one["text"] is None and one["image"] is None


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
