"""One day of the loop.

    python step.py            # advance the chain by one frame
    python step.py --render   # rebuild the site from what already exists

The order matters. The image is written to disk BEFORE the run file is saved, so
a crash between the two leaves an orphan jpg (harmless, overwritten next run)
rather than a run record pointing at a frame that does not exist (fatal - the
next describe step has nothing to look at and the chain is broken).
"""
from __future__ import annotations

import os
import sys

import avoid
import chain
import collapse
import describe
import draw
import render
from common import load_settings, read_json, rel, tz_now, write_json


def _load_dotenv() -> None:
    """Best-effort .env for local runs; CI supplies the same names as secrets."""
    path = rel(".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))


def _write_image(rel_path: str, data: bytes) -> None:
    path = rel(rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _read_image(rel_path: str) -> bytes:
    with open(rel(rel_path), "rb") as fh:
        return fh.read()


def advance(settings: dict) -> dict:
    """Add one frame to the live run, starting or sealing runs as needed."""
    runs = chain.load_runs()
    today = tz_now(settings).date().isoformat()
    run = chain.live_run(runs)

    if run is None:
        seeds = settings["seeds"]
        idx = chain.next_seed_index(runs, len(seeds))
        run = chain.new_run(len(runs) + 1, idx, seeds[idx], today)
        runs.append(run)
        print(f">>> RUN {run['n']} opened from seed {idx}")

    if not run["frames"]:
        # Frame 1 is drawn straight from the seed: there is no previous image to
        # look at, and inventing one would put a frame in the chain that nothing
        # in the chain produced.
        description, source = dict(run["seed"]), "seed"
        avoid_block = ""
    else:
        last = run["frames"][-1]
        history = [f["description"] for f in run["frames"]]
        avoid_block = avoid.block(history, settings["loop"])
        if avoid_block:
            print(f"    avoiding {avoid_block.count(',') + 1} term(s)")
        description = describe.describe(
            _read_image(last["image"]), settings, avoid_block)
        source = f"frame {last['n']}"

    if not describe.is_usable(description):
        raise RuntimeError(f"description from {source} is too sparse to draw: "
                           f"{description}")
    print(f">>> DESCRIBE (from {source}): {description['subject'][:70]}")

    image, prompt = draw.draw(description, settings)
    frame_n = len(run["frames"]) + 1
    image_rel = chain.image_path(run["n"], frame_n)
    _write_image(image_rel, image)
    print(f">>> DREW {image_rel} ({len(image) // 1024}kB)")

    dh = collapse.dhash(image)
    provisional = run["frames"] + [{"description": description, "dhash": str(dh)}]
    seal, reading = collapse.should_seal(provisional, run.get("strikes", 0),
                                         settings["collapse"])
    run["strikes"] = reading["strikes"]
    frame = chain.add_frame(run, today, description, prompt, image_rel, dh, reading)
    print(f"    text {reading['text']} / image {reading['image']} / "
          f"strikes {reading['strikes']}")

    if seal:
        run["sealed"] = today
        print(f">>> RUN {run['n']} SEALED after {len(run['frames'])} frames")

    chain.save_run(run)
    render.build()
    print(f"    frame {frame['n']} of run {run['n']}; site rebuilt")
    return frame


def main(argv: list[str]) -> int:
    settings = load_settings()
    if "--render" in argv:
        render.build()
        print("rebuilt site")
        return 0
    _load_dotenv()
    advance(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
