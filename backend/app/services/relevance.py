"""
Lightweight query–title relevance for merged retailer results.
"""
from __future__ import annotations
import re
from typing import Optional

_GPUISH = re.compile(
    r"\b(rtx|gtx|rx\s*\d|\d{3,4}\s*(ti|super)?|geforce|radeon|gpu|graphics|"
    r"video\s*card|vga)\b",
    re.I,
)
_PERIPHERAL = re.compile(
    r"\b(mouse|mice|keyboard|keypad|headset|headphone|earphone|webcam|mic|"
    r"speaker|gamepad|controller|mouse\s*pad|mousepad|cable\s*only|adapter\s*hub|"
    r"usb\s*hub|charger(?!.*gpu)|stand|mount)\b",
    re.I,
)


def _normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())


def _tokens(s: str) -> list[str]:
    return [t for t in _normalize_text(s).split() if len(t) > 1]


def _numeric_tokens(s: str) -> set[str]:
    return set(re.findall(r"\d{3,5}", s))


def _spec_tokens(s: str) -> set[str]:
    # Spec-aware features: capacities/speeds/generation hints.
    caps = re.findall(r"\b\d+\s?(gb|tb|mhz|w)\b", s.lower())
    gens = re.findall(r"\b(ddr\d|gen\s?\d|pcie\s?\d)\b", s.lower())
    return set(caps + gens)


def relevance_score(query: str, title: str, description: Optional[str] = None) -> float:
    """Higher = better match. Safe to call per product (e.g. streaming chunks)."""
    q_raw = query.strip()
    if not q_raw:
        return 0.0

    title_n = _normalize_text(title)
    desc_n = _normalize_text(description or "")
    blob = f"{title_n} {desc_n}"

    score = 0.0
    q_lower = q_raw.lower()

    if q_lower in title_n:
        score += 80.0
    elif q_lower in blob:
        score += 35.0
    else:
        q_compact = re.sub(r"\W+", "", q_lower)
        t_compact = re.sub(r"\W+", "", title_n)
        if len(q_compact) >= 3 and q_compact in t_compact:
            score += 70.0

    q_toks = _tokens(q_raw)
    if q_toks:
        title_toks = set(_tokens(title))
        desc_toks = set(_tokens(description or ""))
        for tok in q_toks:
            if tok in title_toks:
                score += 12.0
            elif tok in desc_toks:
                score += 4.0

    for num in _numeric_tokens(q_raw):
        if re.search(rf"(^|\D){re.escape(num)}(\D|$)", title_n):
            score += 25.0
        elif num in desc_n:
            score += 8.0

    q_specs = _spec_tokens(q_raw)
    if q_specs:
        t_specs = _spec_tokens(title_n)
        d_specs = _spec_tokens(desc_n)
        for sp in q_specs:
            if sp in t_specs:
                score += 8.0
            elif sp in d_specs:
                score += 3.0

    if _GPUISH.search(q_raw) and _PERIPHERAL.search(title) and not _GPUISH.search(title):
        score -= 45.0

    return max(score, 0.0)
