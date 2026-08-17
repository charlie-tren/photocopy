"""Acceptance test for the decency floor, run against the frames that caused it.

The unit tests in `tests/test_safety.py` prove the wiring - that an unsafe
verdict triggers a redraw, that the filter is surgical, that a dead API fails
closed. They prove nothing about whether the classifier can actually SEE a bare
backside, because they stub it out. This does that, using the five real frames
that were pulled from the live chain on 17/08/2026.

    python tools/checkguard.py

Needs GEMINI_API_KEY. The frames are read out of git history - they were removed
from the working tree, deliberately, and should stay removed.

Expected: frame 1 passes, frames 3-7 fail. Frame 2 is the interesting one - a
front-facing figure with no anatomy rendered, which is where the drift started -
so its verdict is reported but not asserted either way.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import safety                                    # noqa: E402
from common import load_settings                 # noqa: E402

#: The commit before the removal - the last one where all seven frames exist.
BEFORE_REMOVAL = "HEAD"
SHOULD_PASS = [1]
SHOULD_FAIL = [3, 4, 5, 6, 7]
UNASSERTED = [2]


def frame_bytes(n: int, ref: str) -> bytes | None:
    path = f"assets/img/f{n:04d}.jpg"
    for candidate in (ref, f"{ref}~1", f"{ref}~2", f"{ref}~3"):
        try:
            return subprocess.check_output(
                ["git", "show", f"{candidate}:{path}"], stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
    return None


def main() -> int:
    settings = load_settings()
    ref = os.environ.get("GUARD_REF", BEFORE_REMOVAL)
    failures = []

    # gemini-3.6-flash on the free tier allows 5 requests per MINUTE. The first
    # run of this fired seven back to back, and frames 6 and 7 came back as
    # "UNSAFE (check failed: HTTP 429)" - which fail-closed correctly reports as
    # unsafe, and which is therefore indistinguishable from a real verdict unless
    # you read the reason. Pace it.
    spacing = float(os.environ.get("GUARD_SPACING", "14"))
    first = True

    for n in sorted(SHOULD_PASS + SHOULD_FAIL + UNASSERTED):
        data = frame_bytes(n, ref)
        if data is None:
            print(f"frame {n}: NOT FOUND in git at {ref} - skipped")
            continue
        if not first:
            time.sleep(spacing)
        first = False
        safe, reason = safety.check_image(data, settings)
        if "429" in reason or "check failed" in reason:
            print(f"frame {n}: NO VERDICT - {reason[:90]}")
            failures.append(n)
            continue
        verdict = "SAFE  " if safe else "UNSAFE"
        note = ""
        if n in SHOULD_FAIL and safe:
            note = "  <-- WRONG, this is one of the frames that had to go"
            failures.append(n)
        elif n in SHOULD_PASS and not safe:
            note = "  <-- WRONG, this frame is fine"
            failures.append(n)
        elif n in UNASSERTED:
            note = "  (not asserted either way)"
        print(f"frame {n}: {verdict}  {reason}{note}")

    if failures:
        print(f"\nGUARD NOT FIT FOR PURPOSE - wrong on frames {failures}. "
              f"Do not put the site back up on this.")
        return 1
    print("\nGuard agrees with the human call on every asserted frame.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
