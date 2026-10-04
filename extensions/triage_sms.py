"""Stdlib-only text normalizer for SMS / narration triage.

No external NLP: NFKC normalization, lowercasing, regex tokenization,
long-digit dropping, inline English stopwords and single Bengali suffix
stripping per token. Deterministic and idempotent.
"""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset({
    "i", "we", "you", "he", "she", "it", "they", "the", "a", "an",
    "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "been", "has", "have", "had", "do", "does",
    "did", "not", "no", "yes", "please", "kindly", "dear", "sir",
    "madam", "rs", "rupees", "only",
})

SUFFIXES = (
    "\u0997\u09c1\u09b2\u09cb",
    "\u0997\u09c1\u09b2\u09bf",
    "\u09a6\u09c7\u09b0",
    "\u09a4\u09c7",
    "\u0995\u09c7",
    "\u09b0\u09be",
    "\u099f\u09bf",
    "\u09c7",
)

_TOKEN_RE = re.compile(r"[a-z0-9\u0980-\u09ff]+")


def _strip_suffix(token: str) -> str:
    """Strip at most one Bengali suffix (longest match first)."""
    for suffix in SUFFIXES:
        if len(token) > len(suffix) and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def normalize_text(s: str) -> str:
    """Normalize free text to a collapsed single-space token string."""
    if not isinstance(s, str):
        return ""
    lowered = unicodedata.normalize("NFKC", s).lower()
    out: list[str] = []
    for token in _TOKEN_RE.findall(lowered):
        if token.isdigit() and len(token) > 6:
            continue
        if token in STOPWORDS:
            continue
        out.append(_strip_suffix(token))
    return " ".join(out)
