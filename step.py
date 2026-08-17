"""One day of the loop.

    python step.py            # advance the chain by one frame
    python step.py --force    # ...even if today already has one
    python step.py --render   # rebuild the site from what already exists

The order matters. The image is written to disk BEFORE the frame record is saved,
so a crash between the two leaves an orphan jpg (harmless, overwritten next run)
rather than a record pointing at a frame that does not exist (fatal - tomorrow's
describe step would have nothing to look at and the chain would be broken).
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
import safety
from common import load_settings, rel, tz_now


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


class Unpublishable(RuntimeError):
    """Every attempt at today's frame failed the decency check."""


def _draw_something_publishable(description: dict, settings: dict) -> tuple[bytes, str]:
    """Draw, look at what came back, and only then accept it.

    Retries because flux is stochastic: the same prompt that drew a bare figure
    often draws a clothed one on the next seed, so a redraw is a real fix and not
    a dice-roll dressed up as one. It is bounded because if several attempts in a
    row come back unsafe, the DESCRIPTION is steering there and no number of
    redraws will help - that wants a human, not another API call.

    Raising is the right failure. A gap in the chain is visible, explicable and
    fixable tomorrow; publishing the frame anyway is not.
    """
    attempts = int(settings.get("safety", {}).get("max_attempts", 3))
    last = "no attempt made"
    for attempt in range(1, attempts + 1):
        image, prompt = draw.draw(description, settings)
        safe, reason = safety.check_image(image, settings)
        if safe:
            if attempt > 1:
                print(f"    decency check passed on attempt {attempt}")
            return image, prompt
        last = reason
        print(f"    !! attempt {attempt}/{attempts} rejected: {reason}")
    raise Unpublishable(
        f"no publishable frame after {attempts} attempts (last: {last}). "
        f"The description is steering it: {description}")


def advance(settings: dict, force: bool = False) -> dict | None:
    """Add one frame to the chain, unless today already has one."""
    frames = chain.load_frames()
    today = tz_now(settings).date().isoformat()

    if not force and chain.filed_on(frames, today):
        # Not an error: the backup cron exists precisely so a dropped primary
        # still files, which means most days it runs and finds the work done.
        print(f"already filed for {today}; nothing to do")
        return None

    if not frames:
        # Frame 1 is drawn straight from the written seed: there is no previous
        # image to look at, and inventing one would put a frame in the chain that
        # nothing in the chain produced.
        description, source = dict(settings["seed"]), "the seed"
        avoid_block = ""
    else:
        last = frames[-1]
        avoid_block = avoid.block([f["description"] for f in frames],
                                  settings["loop"])
        if avoid_block:
            print(f"    avoiding {avoid_block.count(',') + 1} term(s)")
        description = describe.describe(
            _read_image(last["image"]), settings, avoid_block)
        source = f"frame {last['n']}"

    if not describe.is_usable(description):
        raise RuntimeError(f"description from {source} is too sparse to draw: "
                           f"{description}")
    print(f">>> DESCRIBE (from {source}): {description['subject'][:70]}")

    image, prompt = _draw_something_publishable(description, settings)
    n = len(frames) + 1
    image_rel = chain.image_path(n)
    _write_image(image_rel, image)
    print(f">>> DREW {image_rel} ({len(image) // 1024}kB)")

    dh = collapse.dhash(image)
    reading = collapse.assess(
        frames + [{"description": description, "dhash": str(dh)}],
        settings["movement"])
    print(f"    movement: text {reading['text']} / image {reading['image']}")

    frame = chain.make_frame(n, today, description, prompt, image_rel, dh, reading)
    chain.save_frame(frame)
    render.build()
    print(f"    frame {n} saved; site rebuilt")
    return frame


def main(argv: list[str]) -> int:
    settings = load_settings()
    if "--render" in argv:
        render.build()
        print("rebuilt site")
        return 0
    _load_dotenv()
    advance(settings, force="--force" in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
