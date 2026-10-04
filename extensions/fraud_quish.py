"""Quishing (QR/URL phishing) screening for voucher text fields.

Ports the stdlib-only detection logic of a phishing-domain generator and
quishing scanner: homoglyph table, SequenceMatcher similarity, lookalike
check, URL flag analysis and a 0-100 URL score. Adds bill-level scoring
over narration / raw values / refs / UTR text.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

HOMOGLYPHS: dict[str, str] = {
    "a": "\u0430", "c": "\u0441", "e": "\u0435", "i": "\u0456",
    "o": "\u043e", "p": "\u0440", "s": "\u0455", "x": "\u0445",
    "y": "\u0443", "b": "\u044c", "h": "\u04bb", "k": "\u043a",
    "m": "\u043c", "n": "\u043f", "t": "\u0442", "u": "\u0456",
}

DANGER_KEYWORDS = [
    "login", "verify", "account", "update", "confirm",
    "secure", "alert", "suspension", "billing", "reward",
]
SUSPICIOUS_SCHEMES = {"http", "ftp"}
SUSPICIOUS_TLDS = {"xyz", "top", "site", "online", "shop", "cc", "vip", "info", "biz"}

LEGIT = [
    "hdfcbank.com",
    "icicibank.com",
    "statebankofindia.com",
    "axisbank.com",
    "kotak.com",
    "upi.org.in",
    "gst.gov.in",
    "tallysolutions.com",
]

_URL_RE = re.compile(r"https?://\S+")
_WWW_RE = re.compile(r"www\.\S+")
_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_TRAILING_PUNCT = ".,;:!?'\")]}>"


def similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def is_lookalike(domain: str, legit: str, threshold: float = 0.85) -> bool:
    """True if domain visually or nearly matches a legit domain."""
    if domain == legit:
        return False
    a = domain.lower()
    b = legit.lower()
    if similarity(a, b) >= threshold:
        return True
    for ch, fake in HOMOGLYPHS.items():
        if ch in a and fake in b:
            return True
        if fake in a and ch in b:
            return True
    return False


def analyze_url(url: str) -> list[str]:
    """Flag analysis for a URL string (ported QR-scan flag logic)."""
    parsed = urlparse(url if "://" in url else "http://" + url)
    scheme = parsed.scheme.lower() or None
    flags: list[str] = []
    if scheme in SUSPICIOUS_SCHEMES:
        flags.append("non-https-scheme")
    if scheme is None:
        flags.append("no-scheme")
    host = (parsed.hostname or "").lower()
    if host and "." not in host:
        flags.append("short-host")
    if host and any(k in host for k in DANGER_KEYWORDS):
        flags.append("keyword-verification")
    tld = host.rpartition(".")[2] if host else ""
    if tld in SUSPICIOUS_TLDS:
        flags.append("unusual-tld")
    if parsed.username or parsed.password:
        flags.append("userinfo")
    if host and _IP_RE.match(host):
        flags.append("ip-address")
    if len(url) > 500:
        flags.append("very-long-url")
    return flags


def score_url(url: str) -> int:
    """Heuristic 0-100 phishing score for a single URL."""
    parsed = urlparse(url if "://" in url else "http://" + url)
    scheme = (parsed.scheme or "").lower()
    flags = analyze_url(url)
    score = 0
    if scheme == "https":
        score += 20
    elif scheme in SUSPICIOUS_SCHEMES:
        score += 5
    score += len(flags) * 10
    return min(100, score)


def _core_label(label: str) -> str:
    """Reduce a host label to its typosquat core for legit-name comparison."""
    core = label.lower().replace("xn--", "")
    for kw in DANGER_KEYWORDS:
        core = core.replace(kw, "")
    return _NON_ALNUM_RE.sub("", core)


def typosquat_legit(host: str) -> str | None:
    """Return the LEGIT domain the host typosquats, or None."""
    host = (host or "").lower().strip(".")
    if not host:
        return None
    for legit in LEGIT:
        if host == legit or host.endswith("." + legit):
            return None
    candidates = {host}
    for label in host.split("."):
        if not label:
            continue
        candidates.add(label)
        core = _core_label(label)
        if core:
            candidates.add(core)
    for legit in LEGIT:
        if host == legit:
            continue
        legit_name = legit.split(".")[0]
        for cand in candidates:
            if not cand:
                continue
            if cand == legit_name:
                return legit
            if is_lookalike(cand, legit) or is_lookalike(cand, legit_name):
                return legit
    return None


def _clean_token(tok: str) -> str:
    return tok.rstrip(_TRAILING_PUNCT).strip("'\"()[]{}<>").strip()


def extract_urls(text: str) -> list[str]:
    """Extract URL-like tokens (http(s)://... and www....)."""
    text = text or ""
    spans: list[tuple[int, int]] = [m.span() for m in _URL_RE.finditer(text)]
    found: list[str] = []
    seen: set[str] = set()

    def overlaps(span: tuple[int, int]) -> bool:
        return any(span[0] < end and span[1] > start for start, end in spans)

    for match in list(_URL_RE.finditer(text)) + list(_WWW_RE.finditer(text)):
        if match.re is _WWW_RE and overlaps(match.span()):
            continue
        tok = _clean_token(match.group(0))
        if tok and tok not in seen:
            seen.add(tok)
            found.append(tok)
    return found


def _collect_texts(row: dict) -> str:
    """Gather narration, raw values, refs and UTR text from a row."""
    if not isinstance(row, dict):
        return ""
    parts: list[str] = []
    for key in ("narration", "remarks"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    stack: list = [row.get("raw")]
    refs = row.get("refs")
    stack.append(refs)
    ref = row.get("ref")
    if isinstance(ref, str):
        parts.append(ref)
    pay = row.get("pay")
    if isinstance(pay, dict):
        utr = pay.get("utr")
        if isinstance(utr, str) and utr.strip():
            parts.append(utr)
    utr_top = row.get("utr")
    if isinstance(utr_top, str) and utr_top.strip():
        parts.append(utr_top)
    while stack:
        val = stack.pop()
        if isinstance(val, str):
            if val.strip():
                parts.append(val)
        elif isinstance(val, dict):
            stack.extend(val.values())
        elif isinstance(val, (list, tuple)):
            stack.extend(val)
    return " ".join(parts)


def _score_one(url: str) -> tuple[int, list[str]]:
    flags = analyze_url(url)
    parsed = urlparse(url if "://" in url else "http://" + url)
    host = (parsed.hostname or "").lower()
    extras: list[str] = []
    lookalike: str | None = typosquat_legit(host) if host else None
    if lookalike is not None:
        extras.append("lookalike:" + lookalike)
    puny = bool(host and "xn--" in host)
    if puny:
        extras.append("punycode")
    score = len(flags) * 10 + (25 if lookalike is not None else 0)
    if puny:
        score += 15
    all_flags = sorted("quish:" + f for f in flags + extras)
    return min(100, score), all_flags


def score_bill(canonical_row: dict) -> tuple[int, list[str]]:
    """Score a voucher row for quishing risk.

    Returns (best score 0-100 across extracted URLs, sorted quish: flags).
    Rows without URL-like tokens score 0 with no flags.
    """
    text = _collect_texts(canonical_row)
    urls = extract_urls(text)
    if not urls:
        return 0, []
    best_score = 0
    best_flags: list[str] = []
    for url in urls:
        score, flags = _score_one(url)
        if score > best_score:
            best_score = score
            best_flags = flags
    return best_score, best_flags
