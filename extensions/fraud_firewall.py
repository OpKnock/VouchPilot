"""Prompt-injection firewall for voucher narration text.

Ports the stdlib-only logic of an LLM prompt-injection firewall: the 64
pattern rules (descriptions kept as rule ids), homoglyph/leet heuristics
(entropy, base64 runs, payload checks) and NFKC-plus-fold normalization.
Adds narration scoring with block / sanitize / warn / ok actions.
"""

from __future__ import annotations

import base64
import math
import re
import unicodedata

HOMOGLYPHS = {
    "\u0430": "a", "\u0410": "A", "\u0435": "e", "\u0415": "E",
    "\u0456": "i", "\u0406": "I", "\u043e": "o", "\u041e": "O",
    "\u0440": "p", "\u0420": "P", "\u0441": "c", "\u0421": "C",
    "\u0443": "y", "\u0423": "Y", "\u0445": "x", "\u0425": "X",
    "\u043d": "h", "\u041d": "H", "\u043c": "m", "\u041c": "M",
    "\u0442": "t", "\u0422": "T", "\u043a": "k", "\u041a": "K",
    "\u03bf": "o", "\u039f": "O", "\u03c1": "p", "\u03a1": "P",
    "\u03c4": "t", "\u03a4": "T", "\u03b9": "i", "\u0399": "I",
    "\u03b5": "e", "\u0395": "E", "\u03b1": "a", "\u0391": "A",
    "\u03c5": "y", "\u03a5": "Y",
}

LEET_MAP = {
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s", "!": "i", "8": "b",
}

LEET_MAP_L = dict(LEET_MAP)
LEET_MAP_L["1"] = "l"

BASE64_CHARS = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")
HEX_CHARS = re.compile(r"^[0-9a-f]+$", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=]+")


def fold_homoglyphs(text: str) -> str:
    """Replace confusable non-ASCII characters with ASCII lookalikes."""
    return "".join(HOMOGLYPHS.get(ch, ch) for ch in text)


def deleet(text: str, mapping: dict[str, str] = LEET_MAP) -> str:
    """Decode leet-speak digits back to letters."""
    return "".join(mapping.get(ch, ch) for ch in text)


def normalize_for_rules(text: str) -> str:
    """Normalize input before rule matching: homoglyph fold + leet decode."""
    return deleet(fold_homoglyphs(text))


def normalize_unicode(text: str) -> str:
    """NFKC normalization plus homoglyph folding to defeat lookalikes."""
    folded = "".join(HOMOGLYPHS.get(ch, ch) for ch in text)
    return unicodedata.normalize("NFKC", folded)


def sanitize(text: str) -> str:
    """NFKC + homoglyph fold, then strip control characters."""
    if not isinstance(text, str):
        return ""
    out = normalize_unicode(text)
    return "".join(ch for ch in out if unicodedata.category(ch) != "Cc")


def shannon_entropy(data: bytes) -> float:
    """Shannon entropy in bits per byte for the given bytes."""
    if not data:
        return 0.0
    counts: dict[int, int] = {}
    for b in data:
        counts[b] = counts.get(b, 0) + 1
    length = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def entropy_bits(text: str) -> float:
    """Entropy of the text as bytes."""
    return shannon_entropy(text.encode("utf-8", errors="replace"))


def longest_base64_run(text: str) -> int:
    """Length of the longest contiguous base64-alphabet run in the text."""
    longest = 0
    current = 0
    alphabet = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    for ch in text:
        if ch in alphabet:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest


def is_base64_payload(chunk: str) -> bool:
    """True if chunk is a plausible base64-encoded payload."""
    if len(chunk) < 16:
        return False
    if not BASE64_CHARS.match(chunk):
        return False
    if len(chunk) % 4 == 0:
        try:
            base64.b64decode(chunk, validate=True)
            return True
        except Exception:
            return False
    return True


def is_hex_payload(chunk: str) -> bool:
    """True if chunk looks like a hex-encoded payload."""
    if len(chunk) < 16 or len(chunk) % 2 != 0:
        return False
    return bool(HEX_CHARS.match(chunk))


class Rule:
    __slots__ = ("category", "pattern", "weight", "description")

    def __init__(self, category: str, pattern: str, weight: int, description: str):
        self.category = category
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.weight = weight
        self.description = description

    def find(self, text: str) -> list[str]:
        return self.pattern.findall(text)


DIRECT = 65
JAILBREAK = 60
EXTRACTION = 60
ENCODING = 45
DELIMITER = 45
INDIRECT = 45
ROLE_SWITCH = 45

RULES = [
    Rule("direct", r"ignore\s+(all\s+|any\s+|the\s+|your\s+|my\s+)?(previous|earlier|prior|above|past|system|former)\s+(instructions|messages|message|prompts|orders|rules|text|content)", DIRECT, "ignore previous instructions"),
    Rule("direct", r"ignore\s+(everything|all)\s+(that\s+)?(i\s*'?ve?\s*|you\s+were\s+told\s+)?(said|say|wrote|typed|sent|text|above)", DIRECT, "ignore everything said before"),
    Rule("direct", r"ignore\s+(the\s+|all\s+|any\s+)?(content|text|message|messages)\s+above", DIRECT, "ignore content above"),
    Rule("direct", r"ignore\s+(the\s+)?above", DIRECT, "ignore the above"),
    Rule("direct", r"ignore\s+your\s+(programming|training|instructions)", DIRECT, "ignore your programming"),
    Rule("direct", r"disregard\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier)\s+(instructions|messages|prompts|orders|rules)", DIRECT, "disregard previous instructions"),
    Rule("direct", r"disregard\s+(the\s+|your\s+|these\s+|all\s+following\s+)?(instructions|content|text|rules)", DIRECT, "disregard instructions"),
    Rule("direct", r"forget\s+(all\s+|everything\s+|the\s+|your\s+)?(previous|prior|above|earlier|system)?\s*(instructions|prompts|messages|orders|rules|system\s+prompt)", DIRECT, "forget instructions"),
    Rule("direct", r"forget\s+(everything|all)\s+you\s+were\s+(told|taught|given)", DIRECT, "forget everything you were told"),
    Rule("direct", r"you\s+(are|will|must)\s+(now\s+)?(ignore|disregard|forget)\s+(everything|all|the\s+instructions)", DIRECT, "you will ignore everything"),
    Rule("direct", r"(don'?t|do\s+not)\s+(follow|obey|listen\s+to|respect)\s+(the\s+|your\s+)?(instructions|system\s+prompt|rules)", DIRECT, "do not follow instructions"),
    Rule("direct", r"override\s+(the\s+|your\s+)?(system\s+)?(prompt|instructions|directives)", DIRECT, "override system prompt"),
    Rule("direct", r"you\s+are\s+no\s+longer\s+(bound\s+by|required\s+to\s+follow)", DIRECT, "no longer bound by instructions"),
    Rule("direct", r"(new|changed)\s+instructions\s*[:\.]", DIRECT, "new/changed instructions prefix"),
    Rule("direct", r"from\s+now\s+on\s+you\s+will", DIRECT, "from now on you will"),
    Rule("direct", r"(i\s+have|here\s+are|these\s+are)\s+new\s+(orders|instructions|rules)", DIRECT, "new orders declared"),
    Rule("jailbreak", r"dan\s+mode", JAILBREAK, "DAN mode"),
    Rule("jailbreak", r"you\s+are\s+now\s+dan\b", JAILBREAK, "you are now DAN"),
    Rule("jailbreak", r"(play|pretend|become)\s+dan\b", JAILBREAK, "play DAN"),
    Rule("jailbreak", r"jail\s*break(\s+(mode|activated|enabled))?", JAILBREAK, "jailbreak"),
    Rule("jailbreak", r"developer\s+mode", JAILBREAK, "developer mode"),
    Rule("jailbreak", r"sudo\s+mode", JAILBREAK, "sudo mode"),
    Rule("jailbreak", r"unrestricted\s+mode", JAILBREAK, "unrestricted mode"),
    Rule("jailbreak", r"do\s+anything\s+now", JAILBREAK, "do anything now"),
    Rule("jailbreak", r"(no|without|don'?t\s+apply)\s+(filters|restrictions|content\s+policies)", JAILBREAK, "no filters"),
    Rule("jailbreak", r"pretend\s+(you\s+are|to\s+be)\s+(dan|an\s+ai\s+(without|with\s+no))", JAILBREAK, "pretend to be DAN"),
    Rule("jailbreak", r"act\s+(as|like)\s+(dan|an\s+ai\s+(with\s+no|without)|if\s+you\s+have\s+no)", JAILBREAK, "act as unrestricted AI"),
    Rule("jailbreak", r"unbanned\s+(version|mode)", JAILBREAK, "unbanned version"),
    Rule("jailbreak", r"bypass\s+(the\s+)?(filter|safety|content\s+policy)", JAILBREAK, "filter bypass"),
    Rule("jailbreak", r"answer\s+without\s+(any|the)\s+(restrictions|limitations|rules)", JAILBREAK, "answer without restrictions"),
    Rule("extraction", r"reveal\s+(your|the|its)\s+(system\s+)?prompt", EXTRACTION, "reveal system prompt"),
    Rule("extraction", r"show\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions)", EXTRACTION, "show system prompt"),
    Rule("extraction", r"(output|print|display)\s+(your|the)\s+(system\s+)?(prompt|instructions)", EXTRACTION, "print system prompt"),
    Rule("extraction", r"what\s+are\s+(your|the)\s+(instructions|directives|system\s+prompt)", EXTRACTION, "ask for instructions"),
    Rule("extraction", r"tell\s+(me\s+)?(your|the|what)\s+(instructions|directives|system\s+prompt)", EXTRACTION, "tell me instructions"),
    Rule("extraction", r"repeat\s+((the|your|the\s+system)\s+)?(prompt|instructions)\s*(above|verbatim|exactly|word\s+for\s+word)?", EXTRACTION, "repeat prompt"),
    Rule("extraction", r"leak\s+(your|the|its)\s+(system\s+)?(prompt|instructions)", EXTRACTION, "leak prompt"),
    Rule("extraction", r"summarize\s+(the|your|it)?\s*(system\s+)?prompt", EXTRACTION, "summarize prompt"),
    Rule("extraction", r"what\s+did\s+the\s+(system|assistant)\s+tell\s+you", EXTRACTION, "what did system say"),
    Rule("extraction", r"(initial|original)\s+(instructions|prompt|directives)\s*(you\s+were\s+given|given\s+to\s+you)?", EXTRACTION, "initial instructions"),
    Rule("delimiter", r"<\s*\\?system[^>]*>", DELIMITER, "system tag"),
    Rule("delimiter", r"<\s*\\?instructions[^>]*>", DELIMITER, "instructions tag"),
    Rule("delimiter", r"<\|im_start\|>", DELIMITER, "ChatML token"),
    Rule("delimiter", r"<\s*\\?prompt[^>]*>", DELIMITER, "prompt tag"),
    Rule("delimiter", r"\[\s*system\s*\]", DELIMITER, "bracketed system"),
    Rule("delimiter", r"^system\s*:", DELIMITER, "system colon prefix"),
    Rule("encoding", r"\bbase64\b", ENCODING, "base64 mention"),
    Rule("encoding", r"\brot13\b|\bcaesar\s+(cipher|shift)\b", ENCODING, "rot13/caesar mention"),
    Rule("encoding", r"\bhex\s*(decode|encoded|string)\b", ENCODING, "hex encoding mention"),
    Rule("encoding", r"\bhex\s*[:=]", ENCODING, "hex payload prefix"),
    Rule("encoding", r"\\u[0-9a-f]{4}", ENCODING, "unicode escape sequences"),
    Rule("encoding", r"read\s+(the\s+)?text\s+backwards|reverse\s+(this\s+)?(string|text)", ENCODING, "reverse text"),
    Rule("encoding", r"(decoded|decode|decrypt)\s*(the\s*)?(payload|message|text|string)", ENCODING, "decode payload"),
    Rule("encoding", r"decode\s+(this|the)\s+(base64|text|string|message|payload)", ENCODING, "decode this base64"),
    Rule("indirect", r"important\s*:\s*ignore", INDIRECT, "important ignore"),
    Rule("indirect", r"please\s+forget\s+(everything|all)", INDIRECT, "please forget"),
    Rule("indirect", r"note\s*:\s*(the\s+)?(above|previous|document|text|email)", INDIRECT, "note about above"),
    Rule("indirect", r"(document|text|email|website|webpage|article)\s+(above\s+|below\s+)?contains\s+(instructions|commands)", INDIRECT, "retrieved content contains instructions"),
    Rule("indirect", r"(follow|obey|carry\s+out)\s+(the\s+)?(instructions|commands)\s+in\s+(this|the)\s+(document|text|email|website)", INDIRECT, "follow instructions in content"),
    Rule("indirect", r"(continue|proceed)\s+(with|as\s+per)\s+(the\s+)?(instructions|commands)", INDIRECT, "proceed as per instructions"),
    Rule("role_switch", r"you\s+are\s+(now\s+)?(a\s+|an\s+)?([a-z]+\s+){0,3}(assistant|ai|bot|model)\s+that\s+(can\s+)?do\s+anything", ROLE_SWITCH, "assistant that can do anything"),
    Rule("role_switch", r"(act|pretend)\s+(as|to\s+be)\s+(my\s+)?\w+[\w\s]{0,20}\b(with\s+unlimited|no\s+(rules|limits|restrictions))", ROLE_SWITCH, "pretend with no limits"),
    Rule("role_switch", r"(your\s+)?(only|sole)\s+instruction", ROLE_SWITCH, "sole instruction"),
    Rule("role_switch", r"(mentor|assistant)\s+with\s+unlimited\b", ROLE_SWITCH, "mentor with unlimited power"),
]


def all_rules() -> list[Rule]:
    return list(RULES)


def rules_for_category(category: str) -> list[Rule]:
    return [r for r in RULES if r.category == category]


def find_matches(text: str) -> list[tuple[Rule, str]]:
    """Match every rule against raw, folded and leet-decoded variants."""
    folded = fold_homoglyphs(text)
    variants = [text, folded, deleet(folded), deleet(folded, LEET_MAP_L)]
    hits: list[tuple[Rule, str]] = []
    matched: set[int] = set()
    for variant in variants:
        for rule in RULES:
            if id(rule) in matched:
                continue
            matches = rule.find(variant)
            if matches:
                matched.add(id(rule))
                first = matches[0]
                hits.append((rule, first if isinstance(first, str) else first[0]))
    return hits


def check_narration(text: str) -> tuple[int, str]:
    """Score narration text 0-100 and return (score, action)."""
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    total = 0
    for rule, _ in find_matches(fold_homoglyphs(text)):
        total += rule.weight
    total = min(80, total)
    entropy = entropy_bits(text)
    if entropy >= 4.6 and len(text) >= 24:
        total += min(12, int((entropy - 4.5) * 10))
    if longest_base64_run(text) >= 32:
        total += 12
    if any(is_hex_payload(w) for w in _TOKEN_RE.findall(text)):
        total += 8
    score = min(100, total)
    if score >= 65:
        action = "block"
    elif score >= 40:
        action = "sanitize"
    elif score >= 15:
        action = "warn"
    else:
        action = "ok"
    return score, action
