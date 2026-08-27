"""The run's self-generated avoid list.

Collapse is a vocabulary problem before it is a picture problem: the same nouns
recur, then the same image recurs. So each frame forbids the terms the run has
been leaning on lately. The input is the run's OWN recent descriptions and
nothing else, which is the point - the chain is never nudged from outside, it is
only stopped from repeating itself.

Directly modelled on The Aftertimes' trends.py/avoid.py pair, which has kept that
project off its own hobby-horses for months.
"""
from __future__ import annotations

import re
from collections import Counter

import describe
import safety

#: Words that carry no subject matter, so banning them would only make the
#: describer write worse English without moving the picture.
_STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "by", "with",
    "from", "into", "over", "under", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "there", "here", "one", "two",
    "three", "four", "some", "no", "not", "as", "but", "for", "up", "down",
    "left", "right", "front", "back", "side", "where", "would", "has", "have",
    "toward", "towards", "against", "across", "around", "very", "more", "most",
    "than", "then", "so", "if", "which", "who", "whose", "out", "off", "about",
}

_WORD = re.compile(r"[a-z]{4,}")


def terms(desc: dict) -> set[str]:
    """Content words in one description, deduplicated.

    `safety.PROTECTED` is excluded here rather than filtered later, so a
    protected word can never reach the counter at all. See that constant: a
    figure that stays dressed the same way for a week was getting its own
    clothes banned, which is an instruction to undress it.
    """
    text = " ".join(str(desc.get(f, "")) for f in describe.FIELDS).lower()
    return {w for w in _WORD.findall(text)
            if w not in _STOP and w not in safety.PROTECTED}


def overused(history: list[dict], window: int, min_count: int,
             cap: int) -> list[str]:
    """Terms present in at least `min_count` of the last `window` descriptions.

    Presence, not frequency: a word used nine times in one description is a
    stylistic tic within that frame, whereas a word present in four frames out of
    six is the run circling. Only the second is collapse.
    """
    recent = history[-window:] if window > 0 else []
    if len(recent) < min_count:
        return []
    counts = Counter()
    for desc in recent:
        counts.update(terms(desc))
    hits = [(n, t) for t, n in counts.items() if n >= min_count]
    hits.sort(key=lambda pair: (-pair[0], pair[1]))
    return [t for _n, t in hits[:cap]]


def render(overused_terms: list[str]) -> str:
    if not overused_terms:
        return ""
    listed = ", ".join(overused_terms)
    return ("This archive has used these words heavily in recent entries. Do not "
            "use any of them. Find different words for what you can actually see, "
            "or describe a different part of the image:\n"
            f"{listed}")


def block(history: list[dict], cfg: dict) -> str:
    return render(overused(history, cfg["avoid_window"], cfg["avoid_min_count"],
                           cfg["avoid_term_cap"]))
