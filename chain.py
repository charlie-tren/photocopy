"""The chain: runs, and the frames inside them.

One file per run (data/runs/001.json) rather than one big file. A run that has
been sealed never changes again, so its file never appears in another diff - which
keeps a repo that gains a frame every day for years readable in git log.
"""
from __future__ import annotations

import glob
import os

from common import read_json, rel, write_json

RUN_DIR = "data/runs"


def run_path(n: int) -> str:
    return f"{RUN_DIR}/{n:03d}.json"


def image_path(run_n: int, frame_n: int) -> str:
    return f"assets/img/r{run_n:03d}-f{frame_n:04d}.jpg"


def load_runs() -> list[dict]:
    runs = []
    for path in sorted(glob.glob(rel(f"{RUN_DIR}/*.json"))):
        run = read_json(f"{RUN_DIR}/{os.path.basename(path)}")
        if run:
            runs.append(run)
    return sorted(runs, key=lambda r: r["n"])


def save_run(run: dict) -> str:
    return write_json(run_path(run["n"]), run)


def new_run(n: int, seed_index: int, seed: dict, started: str) -> dict:
    return {
        "n": n,
        "seed_index": seed_index,
        "seed": dict(seed),
        "started": started,
        "sealed": None,
        "strikes": 0,
        "frames": [],
    }


def add_frame(run: dict, date: str, description: dict, prompt: str,
              image: str, dhash: int, reading: dict) -> dict:
    frame = {
        "n": len(run["frames"]) + 1,
        "date": date,
        "description": description,
        "prompt": prompt,
        "image": image,
        # Stored as a string: JSON numbers are doubles in a lot of readers and a
        # 64-bit hash silently loses its low bits on the way through.
        "dhash": str(dhash),
        "reading": reading,
    }
    run["frames"].append(frame)
    return frame


def live_run(runs: list[dict]) -> dict | None:
    for run in reversed(runs):
        if not run.get("sealed"):
            return run
    return None


def next_seed_index(runs: list[dict], n_seeds: int) -> int:
    """Cycle the seed list. Reusing a seed on a later run is a feature: two runs
    from the same start are the only way to see whether the anti-collapse rules
    are doing anything or the chain was always going to go where it went."""
    return len(runs) % max(1, n_seeds)


def frames_total(runs: list[dict]) -> int:
    return sum(len(r["frames"]) for r in runs)
