"""Thin Gemini REST client (free AI Studio tier), text and vision, plus
defensive JSON extraction. Key comes from GEMINI_API_KEY.

Lifted from The Aftertimes and kept deliberately similar - if a quirk of the free
tier bites one project it will bite the other, and a shared shape means the fix
transfers."""
from __future__ import annotations

import json
import os
import re
import sys
import time

import requests


class GeminiError(RuntimeError):
    pass


def extract_json(raw: str):
    """Pull the first JSON object out of a response, through code fences and prose."""
    if raw is None:
        raise GeminiError("empty response")
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = text.find(opener), text.rfind(closer)
        if 0 <= i < j:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise GeminiError(f"no parseable JSON in response: {raw[:200]!r}")


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError("GEMINI_API_KEY not set")
    return key


#: Seconds to wait after each failed attempt. A 503 here is "this model is currently
#: experiencing high demand", and the old 2s/4s waits gave up inside six seconds -
#: twice in a week (02/10 and 05/10/2026) that failed the 18:00 heartbeat frame and
#: left the day to the backup cron. A demand spike lasts minutes, so the waits do.
WAITS = (15, 45, 90)


def _post(payload: dict, settings: dict) -> str:
    """The configured model, then `fallback_model` if the first stays unavailable.
    A different model has its own capacity and its own free-tier quota, so it
    answers through both a demand spike and a spent day. Which one answered is
    printed, because a chain that changes describer changes what it carries."""
    g = settings["gemini"]
    models = [g["model"].strip()] + ([g["fallback_model"].strip()] if g.get("fallback_model") else [])
    last = None
    for i, model in enumerate(models):
        try:
            text = _post_one(payload, g, model)
            if i:
                print(f"gemini: {models[0]} unavailable, answered by {model}", file=sys.stderr)
            return text
        except GeminiError as exc:
            last = exc
            if not _transient(exc):
                raise
    raise last or GeminiError("no response")


def _transient(exc: Exception) -> bool:
    """Worth another model: overloaded, rate-limited or quota-spent. A 400 is our
    request and would fail the same way anywhere."""
    m = re.match(r"HTTP (\d{3})", str(exc))
    return not m or int(m.group(1)) >= 500 or int(m.group(1)) == 429


def _post_one(payload: dict, g: dict, model: str) -> str:
    url = f"{g['endpoint']}/{model}:generateContent"
    last = None
    for attempt in range(g["max_retries"] + 1):
        try:
            resp = requests.post(
                url, params={"key": _api_key()}, json=payload,
                timeout=g["timeout_seconds"],
                headers={"Content-Type": "application/json"})
            if resp.status_code >= 500 or resp.status_code == 429:
                # 800, not 200: a 429 body carries the quotaId and quotaValue,
                # which is the difference between "too fast, wait a minute" and
                # "no more today". Truncating at 200 hid exactly that and cost
                # an afternoon of guessing.
                last = GeminiError(f"HTTP {resp.status_code}: {resp.text[:800]}")
                if attempt < g["max_retries"]:
                    time.sleep(WAITS[min(attempt, len(WAITS) - 1)])
                continue
            if resp.status_code >= 400:
                # Our request, not their capacity: no wait helps and no other
                # model answers it differently, so it is never retried.
                raise GeminiError(f"HTTP {resp.status_code}: {resp.text[:800]}")
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (requests.RequestException, KeyError, IndexError) as exc:
            last = GeminiError(f"{type(exc).__name__}: {exc}")
            if attempt < g["max_retries"]:
                time.sleep(WAITS[min(attempt, len(WAITS) - 1)])
    raise last or GeminiError("no response")


def generate(prompt: str, settings: dict, temperature: float) -> str:
    return _post({"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": temperature}}, settings)


def generate_with_image(prompt: str, image_b64: str, mime: str,
                        settings: dict, temperature: float) -> str:
    """Vision call. The image goes FIRST in the parts list - with the text first
    the model tends to answer the instruction in the abstract and describe a
    photograph in general rather than this one."""
    return _post({
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime, "data": image_b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": temperature},
    }, settings)
