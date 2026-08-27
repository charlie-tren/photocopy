"""Acceptance test for the decency floor, run against the frames that caused it.

The unit tests in `tests/test_safety.py` prove the wiring - that an unsafe
verdict triggers a redraw, that the filter is surgical, that a dead API fails
closed. They prove nothing about whether the classifier can actually SEE a bare
backside, because they stub it out. This does that, using the five real frames
that were pulled from the live chain on 17/08/2026.

    python tools/checkguard.py

Needs GEMINI_API_KEY, and the fixture frames.

THE FRAMES ARE NO LONGER IN GIT. They were purged from history on 17/08/2026
(`git filter-repo`, force-pushed), because this repo is public and "deleted from
the working tree" is not "deleted from the internet". So the fixtures now live
OUTSIDE the repo, at ~/dev/.photocopy-guard-fixtures, and this test only runs on
a machine that has them. Point GUARD_FIXTURES elsewhere if they move. If they
are lost, the acceptance test is lost with them - there is no way to regenerate
frames that took a live chain five days to drift into.

The cases live in tools/guard_cases.json and come from two places, because the
two failures they encode were cleaned up differently:

- NEW-CHAIN frames (f0001, f0010 clothed; f0011, f0012 near-shirtless) are read
  out of git BY BLOB SHA. They were removed from the working tree on 28/08/2026
  but the objects are still reachable, so CI can check them. Needs fetch-depth 0.
- OLD-CHAIN frames (the 2026-08 nudity drift) were purged from git entirely, so
  they are only available on a machine holding the local fixtures directory.

A case that cannot be loaded is SKIPPED and reported as such; a run where
nothing was checked exits non-zero rather than printing a green line.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import safety                                    # noqa: E402
from common import load_settings                 # noqa: E402

#: Where the fixtures live now that git no longer carries them.
FIXTURES = os.path.expanduser(
    os.environ.get("GUARD_FIXTURES", "~/dev/.photocopy-guard-fixtures"))
CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard_cases.json")


def from_git(sha: str) -> bytes | None:
    """Frames pulled out of git by BLOB SHA, not by ref:path.

    The frames under test were removed from the working tree, so a path lookup
    finds nothing and `HEAD~4:path` rots the moment another commit lands. A blob
    SHA is stable for as long as the object is reachable, which it is - these
    commits are still ancestors. Needs a full clone; a shallow one has no
    objects to find.
    """
    try:
        return subprocess.check_output(["git", "cat-file", "blob", sha],
                                       stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None


def from_file(name: str) -> bytes | None:
    path = os.path.join(FIXTURES, name)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


def main() -> int:
    settings = load_settings()
    spacing = float(os.environ.get("GUARD_SPACING", "14"))
    with open(CASES, encoding="utf-8") as fh:
        cases = json.load(fh)

    todo = [(c["label"], c["expect"], from_git, c["sha"]) for c in cases["git"]]
    todo += [(c["label"], c["expect"], from_file, c["name"]) for c in cases["files"]]

    wrong, checked, first = [], 0, True
    for label, expect, loader, key in todo:
        data = loader(key)
        if data is None:
            print(f"  {label:<40} SKIPPED - not available here")
            continue
        if not first:
            # 5 requests/MINUTE on the free tier. Firing these back to back
            # returns 429s that fail-closed reports as "unsafe", which reads
            # exactly like a pass unless you check the reason.
            time.sleep(spacing)
        first = False
        safe, reason = safety.check_image(data, settings)
        if "429" in reason or "check failed" in reason:
            print(f"  {label:<40} NO VERDICT - {reason[:60]}")
            wrong.append(label)
            continue
        checked += 1
        got = "safe" if safe else "unsafe"
        ok = got == expect
        print(f"  {label:<40} {got:<7} {reason[:52]}{'' if ok else '   <-- WRONG'}")
        if not ok:
            wrong.append(label)

    print()
    if wrong:
        print(f"GUARD NOT FIT FOR PURPOSE - wrong or unverified on {len(wrong)}: "
              f"{', '.join(wrong)}")
        return 1
    if not checked:
        print("Nothing was actually checked. That is a failure, not a pass.")
        return 1
    print(f"Guard agrees with the human call on all {checked} frames checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
