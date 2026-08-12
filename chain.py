"""The chain. One unbroken sequence of frames, no runs, no resets.

One file per frame rather than one growing file: a frame never changes once
written, so it never appears in another diff, and a repo that gains a frame every
day for years stays readable in git log.
"""
from __future__ import annotations

import glob
import os

from common import read_json, rel, write_json

FRAME_DIR = "data/frames"


def frame_path(n: int) -> str:
    return f"{FRAME_DIR}/{n:04d}.json"


def image_path(n: int) -> str:
    return f"assets/img/f{n:04d}.jpg"


def load_frames() -> list[dict]:
    frames = []
    for path in sorted(glob.glob(rel(f"{FRAME_DIR}/*.json"))):
        frame = read_json(f"{FRAME_DIR}/{os.path.basename(path)}")
        if frame:
            frames.append(frame)
    return sorted(frames, key=lambda f: f["n"])


def save_frame(frame: dict) -> str:
    return write_json(frame_path(frame["n"]), frame)


def make_frame(n: int, date: str, description: dict, prompt: str,
               image: str, dhash: int, reading: dict) -> dict:
    return {
        "n": n,
        "date": date,
        "description": description,
        "prompt": prompt,
        "image": image,
        # Stored as a string: JSON numbers are doubles in plenty of readers and a
        # 64-bit hash silently loses its low bits on the way through.
        "dhash": str(dhash),
        "reading": reading,
    }
