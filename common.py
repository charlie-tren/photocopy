"""Shared IO, paths and settings. Deliberately tiny: every stage is a pure
function over plain dicts, and this module owns the only filesystem access."""
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))


def rel(path: str) -> str:
    return os.path.join(ROOT, path.replace("/", os.sep))


def load_yaml(rel_path: str) -> dict:
    with open(rel(rel_path), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_settings() -> dict:
    return load_yaml("config/settings.yaml")


def tz_now(settings: dict) -> datetime:
    return datetime.now(ZoneInfo(settings["timezone"]))


def read_json(rel_path: str, default=None):
    try:
        with open(rel(rel_path), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(rel_path: str, obj) -> str:
    path = rel(rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


#: House style, inherited from The Aftertimes: no em/en dashes anywhere, ever.
_DASH_MAP = {cp: "-" for cp in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015,
                                0x2043, 0x2212, 0xFE58, 0xFE63, 0xFF0D)}


def hyphenate(text: str) -> str:
    return (text or "").translate(_DASH_MAP)


#: Cloudflare Web Analytics, same account-wide token as the rest of the estate -
#: the stats dashboard splits one query by requestHost.
BEACON = (
    '<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
    '''data-cf-beacon='{"token": "32b821209b5441a08df42ccf61c9e6c2"}'></script>'''
)
