"""Run a throwaway chain and report how fast it stops moving.

    python tools/probe.py 18

Answers one question: does this loop flatten out at frame 8, or is it still
moving at frame 20? The published work says these chains converge on a stock
scene; the schema in describe.py and the ban list in avoid.py are a bet against
that, and until a chain has actually been run there is no evidence either way.

It touches NOTHING the site reads. No data/frames, no assets/img, no
manifest.json, no index.html - everything lands in probe-out/, which is
gitignored. The real chain is a separate sequence and stays a separate sequence.

IT IS NOT FREE, THOUGH. One vision call per frame, against a Gemini free tier
that emptied at roughly 25 image calls in a day - measured, on 2026-08-12, at
about 4.5 requests a minute, so it is a daily ceiling and not a rate limit. An
18-frame probe therefore spends most of a day's allowance, and a probe run
before the daily job has filed can cost the chain its frame. Run it AFTER the
day's frame exists, and remember the free day rolls over at midnight Pacific
(07:00 UTC), not at midnight here.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import avoid
import chain
import collapse
import describe
import draw
import safety
from common import load_settings, rel


def _publishable(description, settings, out_dir, i):
    """draw + decency check + bounded redraw - the same loop step.py runs.

    The probe already inherits three of the four safety layers for free:
    describe.py applies describe_clause/strip/deanatomise, and draw.py appends
    the clothing clause and the negative. Only the classifier was missing, so
    a probe was NOT a like-for-like rehearsal of the live chain - it was the
    live chain minus the layer that actually refuses a picture.

    Rejections are written to probe-out/, never to data/rejections.jsonl: that
    file is the real chain's early-warning signal and probe noise would bury it."""
    cfg = settings.get('safety', {})
    attempts = int(cfg.get('max_attempts', 3))
    pause = float(cfg.get('retry_pause_seconds', 15))
    last = 'no attempt made'
    for attempt in range(1, attempts + 1):
        if attempt > 1 and pause:
            time.sleep(pause)
        image, prompt = draw.draw(description, settings)
        safe, reason = safety.check_image(image, settings)
        if safe:
            return image, prompt
        last = reason
        print(f'    !! frame {i} attempt {attempt}/{attempts} rejected: {reason}')
        with open(os.path.join(out_dir, 'rejections.jsonl'), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'frame': i, 'attempt': attempt, 'reason': reason,
                                 'subject': description.get('subject', '')},
                                ensure_ascii=False) + "\n")
    raise RuntimeError(f'no publishable frame at {i} after {attempts} attempts (last: {last})')

OUT = "probe-out"


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 18
    settings = load_settings()
    out_dir = rel(OUT)
    os.makedirs(out_dir, exist_ok=True)

    frames: list[dict] = []
    # 'continue' starts from the live chain's newest description instead of the
    # seed, which answers a different and more useful question: not 'what does a
    # fresh chain do' but 'where is THIS one going next'.
    if len(argv) > 1 and argv[1] == 'continue':
        live = chain.load_frames()
        if not live:
            print('no live frames to continue from'); return 1
        description = dict(live[-1]['description'])
        source = f"live frame {live[-1]['n']}"
        print(f'continuing from {source}: {description["subject"][:60]}')
    else:
        description = dict(settings["seed"])
        source = "seed"

    for i in range(1, n + 1):
        try:
            image, prompt = _publishable(description, settings, out_dir, i)
        except Exception as exc:                       # noqa: BLE001
            print(f"frame {i}: DRAW FAILED ({type(exc).__name__}: {exc})")
            print(f"  description was: {json.dumps(description, ensure_ascii=False)}")
            break
        path = os.path.join(out_dir, f"p{i:03d}.jpg")
        with open(path, "wb") as fh:
            fh.write(image)

        dh = collapse.dhash(image)
        frames.append({"n": i, "description": description, "dhash": str(dh),
                       "prompt": prompt, "from": source})
        reading = collapse.assess(frames, settings["movement"])
        frames[-1]["reading"] = reading

        banned = avoid.overused([f["description"] for f in frames],
                                settings["loop"]["avoid_window"],
                                settings["loop"]["avoid_min_count"],
                                settings["loop"]["avoid_term_cap"])
        frames[-1]["banned"] = banned

        print(f"frame {i:>2} | alike {str(reading['text']):>6} | "
              f"apart {str(reading['image']):>5} | banned {len(banned):>2} | "
              f"{description['subject'][:52]}")
        if banned:
            print(f"         banned: {', '.join(banned)}")

        if i == n:
            break
        try:
            avoid_block = avoid.block([f["description"] for f in frames],
                                      settings["loop"])
            description = describe.describe(image, settings, avoid_block)
            source = f"frame {i}"
        except Exception as exc:                       # noqa: BLE001
            print(f"frame {i + 1}: DESCRIBE FAILED ({type(exc).__name__}: {exc})")
            break
        if not describe.is_usable(description):
            print(f"frame {i + 1}: description too sparse, stopping: {description}")
            break

    with open(os.path.join(out_dir, "probe.json"), "w", encoding="utf-8") as fh:
        json.dump({"frames": frames}, fh, indent=2, ensure_ascii=False)

    # --- the actual question ------------------------------------------------
    readings = [f["reading"] for f in frames if f["reading"].get("text") is not None]
    print(f"\n{'=' * 62}\n{len(frames)} frames drawn\n")
    if len(readings) >= 4:
        half = len(readings) // 2
        early = readings[:half]
        late = readings[half:]
        avg = lambda rs, k: sum(r[k] for r in rs) / len(rs)          # noqa: E731
        print(f"first half  alike {avg(early,'text'):.3f}  apart {avg(early,'image'):.1f}")
        print(f"second half alike {avg(late,'text'):.3f}  apart {avg(late,'image'):.1f}")
        moving = avg(late, "image") > avg(early, "image") * 0.75
        print(f"\npictures still moving at the end: {moving}")
        print("(a big drop in 'apart' between halves is the chain settling)")
    else:
        print("too few frames to compare halves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
