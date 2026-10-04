"""Exact-match authorization with single-use action tokens.

Ports the semantics of AuthraGen ``src/intent.js`` (canonical intent,
shape checks, action-token envelope), ``src/tokens.js`` (delegation
artefacts) and ``src/policy.js`` (glob matching, deny-wins evaluation).

Deviation: AuthraGen seals envelopes with EdDSA (Ed25519). This module
uses HMAC-SHA256 keyed by a local ``secret`` instead, so it runs on the
standard library with no key-management daemon. Envelope layout, field
names and check ordering mirror the JS originals.
"""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import hmac
import json
import math
import re
import time
import unicodedata
from pathlib import Path

INTENT_TTL_MS = 120_000
CLOCK_SKEW_MS = 30_000
APPROVAL_TTL_MS = 15 * 60 * 1000
DEFAULT_AUD = "authragen"

NONCE_RE = re.compile(r"^[A-Za-z0-9:_\-./]+$")
CONTROL_RE = re.compile("[\u0000-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
TRAVERSAL_RE = re.compile(r"(^|/)\.\.(/|$)")

_REQUIRED_TOKEN_FIELDS = ("intent_hash", "action", "resource", "aud")

_APPROVALS: dict[str, dict] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _check_text(value: str, name: str) -> str:
    if CONTROL_RE.search(value):
        raise ValueError(f"{name} contains disallowed control/unicode characters")
    return unicodedata.normalize("NFC", value)


def _normalize(value: object, name: str = "intent") -> object:
    if isinstance(value, str):
        return _check_text(value, name)
    if isinstance(value, dict):
        out: dict[str, object] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise ValueError(f"{name} keys must be strings")
            key = _check_text(raw_key, f"{name} key")
            if key in out:
                raise ValueError(f"{name} keys collide after NFC normalization")
            out[key] = _normalize(item, name=f"{name}.{key}")
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize(item, name=f"{name}[]") for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} contains non-finite number")
    return value


def canonical_intent(d: dict) -> str:
    """Return the stable canonical JSON encoding of intent dict ``d``.

    Applies NFC normalization, rejects control characters and ``..``
    path traversal in ``resource``, then dumps with sorted keys.
    """
    if not isinstance(d, dict):
        raise ValueError("intent must be a dict")
    norm = _normalize(d, name="intent")
    assert isinstance(norm, dict)
    resource = norm.get("resource")
    if isinstance(resource, str) and resource != "":
        if "\\" in resource or TRAVERSAL_RE.search(resource):
            raise ValueError("resource contains illegal path traversal")
        resource = re.sub(r"/{2,}", "/", resource)
        if len(resource) > 1 and resource.endswith("/"):
            resource = resource[:-1]
        norm["resource"] = resource
    return json.dumps(norm, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def intent_hash(d: dict) -> str:
    """Return the SHA-256 hex digest of :func:`canonical_intent`."""
    return hashlib.sha256(canonical_intent(d).encode("utf-8")).hexdigest()


def check_shape(intent: dict) -> None:
    """Validate intent shape; raise ``ValueError`` on any violation.

    Requires integer ``iat``/``exp`` in ms, a 16+ char nonce matching
    ``^[A-Za-z0-9:_\\-./]+$``, ``exp`` in the future, a lifetime of at
    most 120s and ``iat`` skew of at most 30s into the future.
    """
    canonical_intent(intent)  # NFC + control-char + traversal checks
    assert isinstance(intent, dict)
    iat = intent.get("iat")
    exp = intent.get("exp")
    if type(iat) is not int or type(exp) is not int:
        raise ValueError("intent needs numeric integer iat + exp in ms")
    if exp <= iat:
        raise ValueError("intent exp must be after iat")
    nonce = intent.get("nonce")
    if not isinstance(nonce, str) or len(nonce) < 16:
        raise ValueError("intent needs a 16+ char nonce")
    if not NONCE_RE.match(nonce):
        raise ValueError("nonce charset invalid (alphanumeric plus :_-./)")
    now = _now_ms()
    if exp <= now:
        raise ValueError("intent expired")
    if exp - iat > INTENT_TTL_MS:
        raise ValueError("intent lifetime exceeds 120s")
    if iat - now > CLOCK_SKEW_MS:
        raise ValueError("intent iat is in the future (clock skew)")


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(segment: str) -> bytes:
    if not isinstance(segment, str) or not segment:
        raise ValueError("envelope encoding invalid")
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except ValueError as exc:
        raise ValueError("envelope encoding invalid") from exc


def mint_action_token(payload: dict, secret: bytes) -> str:
    """Mint an ``AR1.<b64>.<sig>`` envelope with an HMAC-SHA256 signature.

    ``payload`` must carry ``intent_hash``, ``action``, ``resource``,
    ``aud`` and integer ``iat``/``exp`` ms with ``exp > iat``;
    ``max_uses`` is forced to 1 and ``amount_cents`` defaults to 0.
    """
    if not isinstance(secret, (bytes, bytearray)) or not secret:
        raise ValueError("secret must be non-empty bytes")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    body = dict(payload)
    for field in _REQUIRED_TOKEN_FIELDS:
        if body.get(field) is None or body.get(field) == "":
            raise ValueError(f"payload missing {field}")
    if not isinstance(body["aud"], str) or not body["aud"]:
        raise ValueError("payload aud must be a non-empty string")
    if body.get("max_uses", 1) != 1:
        raise ValueError("payload max_uses must be 1")
    body["max_uses"] = 1
    iat = body.get("iat")
    exp = body.get("exp")
    if type(iat) is not int or type(exp) is not int or exp <= iat:
        raise ValueError("payload needs integer iat/exp ms with exp > iat")
    amount = body.get("amount_cents", 0)
    if type(amount) is not int or amount < 0:
        raise ValueError("payload amount_cents must be a non-negative integer")
    body["amount_cents"] = amount
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    segment = _b64u_encode(raw)
    sig = hmac.new(bytes(secret), segment.encode("ascii"), hashlib.sha256).digest()
    return "AR1." + segment + "." + _b64u_encode(sig)


def verify_action_token(token: str, secret: bytes) -> dict:
    """Verify an ``AR1.<b64>.<sig>`` envelope; return the payload dict.

    Raises ``ValueError`` on malformed envelopes, bad signatures,
    missing fields or expired credentials.
    """
    if not isinstance(secret, (bytes, bytearray)) or not secret:
        raise ValueError("secret must be non-empty bytes")
    parts = token.split(".") if isinstance(token, str) else []
    if len(parts) != 3 or parts[0] != "AR1" or not parts[1] or not parts[2]:
        raise ValueError("not an AR1 action-token envelope")
    _, segment, sig_segment = parts
    try:
        received = _b64u_decode(sig_segment)
    except ValueError as exc:
        raise ValueError("envelope signature encoding invalid") from exc
    expected = hmac.new(bytes(secret), segment.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(received, expected):
        raise ValueError("envelope signature invalid")
    try:
        payload = json.loads(_b64u_decode(segment).decode("utf-8"))
    except ValueError as exc:
        raise ValueError("envelope payload encoding invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("envelope payload must be an object")
    for field in _REQUIRED_TOKEN_FIELDS:
        if payload.get(field) is None or payload.get(field) == "":
            raise ValueError(f"action credential missing {field}")
    if payload.get("max_uses") != 1:
        raise ValueError("action credential max_uses must be 1")
    iat = payload.get("iat")
    exp = payload.get("exp")
    if type(iat) is not int or type(exp) is not int or exp <= iat:
        raise ValueError("iat/exp must be integer ms with exp > iat")
    if exp <= _now_ms():
        raise ValueError("action token expired")
    return payload


class NonceStore:
    """Single-use nonce/jti tracker with an optional JSON file backend.

    The in-memory map is ``{nonce_or_jti: exp_ms}``. ``consume_once``
    returns True on first use and False on replay. Expired entries are
    pruned on every call. When ``path`` is given, the map is loaded at
    construction and persisted after each mutation.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._seen: dict[str, int] = {}
        self._path = Path(path) if path is not None else None
        if self._path is not None and self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
            if isinstance(data, dict):
                for key, exp in data.items():
                    if isinstance(key, str) and type(exp) is int:
                        self._seen[key] = exp
            self.prune()

    def _save(self) -> None:
        if self._path is None:
            return
        parent = self._path.parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._seen, sort_keys=True), encoding="utf-8")

    def prune(self, now_ms: int | None = None) -> int:
        """Drop expired entries; return the number removed."""
        now = _now_ms() if now_ms is None else int(now_ms)
        expired = [key for key, exp in self._seen.items() if exp <= now]
        for key in expired:
            del self._seen[key]
        if expired:
            self._save()
        return len(expired)

    def consume_once(self, nonce: str, exp_ms: int | None = None) -> bool:
        """Record ``nonce``; True on first use, False on replay."""
        if not isinstance(nonce, str) or not nonce:
            raise ValueError("nonce must be a non-empty string")
        self.prune()
        if nonce in self._seen:
            return False
        exp = _now_ms() + INTENT_TTL_MS if exp_ms is None else exp_ms
        if type(exp) is not int:
            raise ValueError("exp_ms must be integer ms")
        self._seen[nonce] = exp
        self._save()
        return True


def _any_match(patterns: object, value: object) -> bool:
    """Fail-closed glob match: empty/missing patterns match nothing."""
    if not patterns:
        return False
    if not isinstance(patterns, (list, tuple)):
        return False
    target = "" if value is None else str(value)
    return any(fnmatch.fnmatchcase(target, str(pat)) for pat in patterns)


def _condition_matches(condition: object, *, spend: int, aud: str, tool: str) -> bool:
    """Subset of policy conditions: spend bounds, audiences, tools."""
    if not condition:
        return True
    if not isinstance(condition, dict):
        return False
    try:
        max_spend = condition.get("max_spend_cents", condition.get("max_spend"))
        if max_spend is not None and spend > int(max_spend):
            return False
        min_spend = condition.get("min_spend_cents", condition.get("min_spend"))
        if min_spend is not None and spend < int(min_spend):
            return False
    except (TypeError, ValueError):
        return False
    audiences = condition.get("audiences")
    if audiences and aud not in audiences:
        return False
    tools = condition.get("tools")
    if tools and not _any_match(tools, tool or ""):
        return False
    return True


def authorize(
    intent: dict,
    token_payload: dict,
    policies: list,
    store: NonceStore,
) -> dict:
    """Authorize an intent against a verified token payload and policies.

    Checks, in order: intent shape, exact ``intent_hash`` / ``action`` /
    ``resource`` / ``amount`` match, ``aud`` binding, token expiry,
    single-use nonce consumption, then policy evaluation (glob via
    fnmatch on actions/resources; deny wins; ``require_approval`` maps
    to ``step_up``; default deny). Returns ``{"decision", "reasons"}``
    where decision is ``allow`` | ``deny`` | ``step_up``.
    """
    try:
        canonical = canonical_intent(intent)
    except ValueError as exc:
        return {"decision": "deny", "reasons": [f"shape: {exc}"]}
    norm = json.loads(canonical)
    try:
        check_shape(intent)
    except ValueError as exc:
        return {"decision": "deny", "reasons": [f"shape: {exc}"]}
    if not isinstance(token_payload, dict):
        return {"decision": "deny", "reasons": ["token: payload must be an object"]}
    if token_payload.get("intent_hash") != intent_hash(intent):
        return {"decision": "deny", "reasons": ["intent_hash_mismatch"]}
    for field in ("action", "resource"):
        if token_payload.get(field) != norm.get(field):
            return {"decision": "deny", "reasons": [f"{field}_mismatch"]}
    if norm.get("amount_cents", 0) != token_payload.get("amount_cents", 0):
        return {"decision": "deny", "reasons": ["amount_mismatch"]}
    want_aud = norm.get("aud") or DEFAULT_AUD
    if token_payload.get("aud") != want_aud:
        return {"decision": "deny", "reasons": ["aud_mismatch"]}
    token_exp = token_payload.get("exp")
    if type(token_exp) is not int or token_exp <= _now_ms():
        return {"decision": "deny", "reasons": ["token_expired"]}
    nonce = norm.get("nonce")
    if not isinstance(nonce, str) or not store.consume_once(nonce, norm.get("exp")):
        return {"decision": "deny", "reasons": ["replay: nonce already used"]}
    req_action = str(norm.get("action", ""))
    req_resource = str(norm.get("resource", ""))
    spend = norm.get("amount_cents", 0)
    spend = spend if type(spend) is int else 0
    tool = norm.get("tool", "") or ""
    matched: list[dict] = []
    for index, policy in enumerate(policies or []):
        if not isinstance(policy, dict):
            continue
        if not _any_match(policy.get("actions"), req_action):
            continue
        if not _any_match(policy.get("resources"), req_resource):
            continue
        cond = policy.get("condition")
        if not _condition_matches(cond, spend=spend, aud=want_aud, tool=tool):
            continue
        if policy.get("id"):
            matched.append(policy)
        else:
            matched.append({**policy, "id": f"policy:{index}"})
    matched.sort(key=lambda p: -(p.get("priority") if type(p.get("priority")) is int else 0))
    deny = next((p for p in matched if p.get("effect") == "deny"), None)
    if deny is not None:
        return {"decision": "deny", "reasons": [f"deny:{deny.get('id')}"]}
    step_up = next((p for p in matched if p.get("effect") == "require_approval"), None)
    if step_up is not None:
        reasons = [f"require_approval:{step_up.get('id')}"]
        cond = step_up.get("condition") or {}
        need = cond.get("min_approvals") if isinstance(cond, dict) else None
        if type(need) is int and need > 1:
            reasons.append(f"quorum:{need}")
        return {"decision": "step_up", "reasons": reasons}
    allow = next((p for p in matched if p.get("effect") == "allow"), None)
    if allow is not None:
        return {"decision": "allow", "reasons": [f"allow:{allow.get('id')}"]}
    return {"decision": "deny", "reasons": ["default_deny:no-matching-allow"]}


def _prune_approvals(now: int) -> None:
    for record_id in [k for k, rec in _APPROVALS.items() if rec["expires_at"] <= now]:
        del _APPROVALS[record_id]


def request_approval(record_id: str, quorum: int, approvers=None) -> dict:
    """Track quorum approvals for ``record_id``; 15-minute expiry.

    ``approvers`` may be a single approver id or a collection of ids;
    each call merges them into the record set. Returns
    ``{"status": "pending" | "approved", "n": <count>, "need": quorum}``.
    """
    if not isinstance(record_id, str) or not record_id:
        raise ValueError("record_id must be a non-empty string")
    if type(quorum) is not int or quorum < 1:
        raise ValueError("quorum must be a positive integer")
    now = _now_ms()
    _prune_approvals(now)
    record = _APPROVALS.get(record_id)
    if record is None or record.get("need") != quorum:
        record = {"need": quorum, "approvers": set(), "expires_at": now + APPROVAL_TTL_MS}
        _APPROVALS[record_id] = record
    if approvers is None:
        pass
    elif isinstance(approvers, str):
        record["approvers"].add(approvers)
    else:
        try:
            members = list(approvers)
        except TypeError:
            members = [approvers]
        for approver in members:
            record["approvers"].add(approver)
    n = len(record["approvers"])
    status = "approved" if n >= record["need"] else "pending"
    return {"status": status, "n": n, "need": record["need"]}
