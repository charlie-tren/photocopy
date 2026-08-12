"""Run a throwaway chain and report how fast it stops moving.

    python tools/probe.py 18

Answers one question: does this loop flatten out at frame 8, or is it still
moving at frame 20? The published work says these chains converge on a stock
scene; the schema in describe.py and the ban list in avoid.py are a bet against
that, and until a chain has actually been run there is no evidence either way.

It touches NOTHING the site reads. No data/frames, no assets/img, no
manifest.json, no index.html - everything lands in probe-out/, which is
gitignored. The real chain is a separate sequence and stays a separate sequence.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import avoid
import collapse
import describe
import draw
from common import load_settings, rel

OUT = "probe-out"


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 18
    settings = load_settings()
    out_dir = rel(OUT)
    os.makedirs(out_dir, exist_ok=True)

    frames: list[dict] = []
    description = dict(settings["seed"])
    source = "seed"

    for i in range(1, n + 1):
        try:
            image, prompt = draw.draw(description, settings)
        except Exception as exc:                       # noqa: BLE001
            print(f"frame {i}: DRAW FAILED ({type(exc).__name__}: {exc})")
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
