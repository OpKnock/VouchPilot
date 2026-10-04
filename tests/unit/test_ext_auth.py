"""Unit tests for extensions.auth_exact. No network."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extensions.auth_exact import (  # noqa: E402
    NonceStore,
    authorize,
    canonical_intent,
    check_shape,
    intent_hash,
    mint_action_token,
    request_approval,
    verify_action_token,
)

SECRET = b"test-secret-32-bytes-long-012345"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _intent(**over: object) -> dict:
    now = _now_ms()
    base: dict = {
        "action": "payments.charge",
        "resource": "/invoices/123",
        "amount_cents": 5000,
        "aud": "vouch-api",
        "tool": "payments-tool",
        "nonce": "nonce-abc123XYZ:4567890",
        "iat": now - 1000,
        "exp": now + 60_000,
    }
    base.update(over)
    return base


def _allow_policies() -> list:
    return [{"id": "p-allow", "actions": ["payments.*"], "resources": ["*"],
             "effect": "allow"}]


def _mint_for(intent: dict, secret: bytes = SECRET, **over: object) -> tuple[str, dict]:
    now = _now_ms()
    payload: dict = {
        "intent_hash": intent_hash(intent),
        "action": intent["action"],
        "resource": intent["resource"],
        "amount_cents": intent.get("amount_cents", 0),
        "aud": intent["aud"],
        "iat": now - 1000,
        "exp": now + 60_000,
    }
    payload.update(over)
    token = mint_action_token(payload, secret)
    return token, verify_action_token(token, secret)


def test_mint_verify_roundtrip() -> None:
    intent = _intent()
    token, payload = _mint_for(intent)
    assert token.startswith("AR1.")
    assert len(token.split(".")) == 3
    assert payload["intent_hash"] == intent_hash(intent)
    assert payload["action"] == intent["action"]
    assert payload["resource"] == intent["resource"]
    assert payload["aud"] == intent["aud"]
    assert payload["max_uses"] == 1


def test_verify_rejects_tampered_and_wrong_secret() -> None:
    intent = _intent()
    token, _ = _mint_for(intent)
    segment, sig = token.split(".")[1], token.split(".")[2]
    tampered = "AR1." + segment[:-2] + ("AA" if not segment.endswith("AA") else "BB")
    tampered += "." + sig
    try:
        verify_action_token(tampered, SECRET)
    except ValueError:
        pass
    else:
        raise AssertionError("tampered payload must not verify")
    try:
        verify_action_token(token, b"wrong-secret-0000000000000000000")
    except ValueError:
        pass
    else:
        raise AssertionError("wrong secret must not verify")
    try:
        verify_action_token("bogus", SECRET)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed token must not verify")


def test_canonical_rejects_traversal_and_controls() -> None:
    assert canonical_intent(_intent()) == canonical_intent(_intent())
    bad_resource = _intent(resource="../etc/passwd")
    try:
        canonical_intent(bad_resource)
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")
    bad_control = _intent(action="payments.charge")
    try:
        canonical_intent(bad_control)
    except ValueError:
        pass
    else:
        raise AssertionError("control chars must be rejected")
    try:
        check_shape(_intent(nonce="short"))
    except ValueError:
        pass
    else:
        raise AssertionError("short nonce must be rejected")


def test_authorize_allow_on_exact_match() -> None:
    intent = _intent()
    _, payload = _mint_for(intent)
    out = authorize(intent, payload, _allow_policies(), NonceStore())
    assert out["decision"] == "allow"
    assert out["reasons"] == ["allow:p-allow"]


def test_replay_rejected_second_time() -> None:
    intent = _intent()
    _, payload = _mint_for(intent)
    store = NonceStore()
    first = authorize(intent, payload, _allow_policies(), store)
    second = authorize(intent, payload, _allow_policies(), store)
    assert first["decision"] == "allow"
    assert second["decision"] == "deny"
    assert any("replay" in reason for reason in second["reasons"])


def test_aud_mismatch_denied() -> None:
    intent = _intent()
    _, payload = _mint_for(intent, aud="other-audience")
    out = authorize(intent, payload, _allow_policies(), NonceStore())
    assert out["decision"] == "deny"
    assert out["reasons"] == ["aud_mismatch"]


def test_tampered_intent_hash_denied() -> None:
    intent = _intent()
    _, payload = _mint_for(intent)
    payload = dict(payload)
    payload["intent_hash"] = "0" * 64
    out = authorize(intent, payload, _allow_policies(), NonceStore())
    assert out["decision"] == "deny"
    assert out["reasons"] == ["intent_hash_mismatch"]


def test_expired_denied() -> None:
    now = _now_ms()
    expired = _intent(iat=now - 200_000, exp=now - 1000)
    payload: dict = {
        "intent_hash": intent_hash(expired),
        "action": expired["action"],
        "resource": expired["resource"],
        "amount_cents": expired["amount_cents"],
        "aud": expired["aud"],
        "iat": now - 1000,
        "exp": now + 60_000,
    }
    token = mint_action_token(payload, SECRET)
    verified = verify_action_token(token, SECRET)
    out = authorize(expired, verified, _allow_policies(), NonceStore())
    assert out["decision"] == "deny"
    assert any("expired" in reason for reason in out["reasons"])
    stale_payload = dict(payload)
    stale_payload["iat"] = now - 5000
    stale_payload["exp"] = now - 1000
    stale_token = mint_action_token(stale_payload, SECRET)
    try:
        verify_action_token(stale_token, SECRET)
    except ValueError as exc:
        assert "expired" in str(exc)
    else:
        raise AssertionError("expired token must not verify")


def test_policy_deny_wins_and_default_deny() -> None:
    intent = _intent()
    _, payload = _mint_for(intent)
    policies = [
        {"id": "p-allow", "actions": ["payments.*"], "resources": ["*"],
         "effect": "allow"},
        {"id": "p-deny", "actions": ["payments.*"], "resources": ["*"],
         "effect": "deny"},
    ]
    out = authorize(intent, payload, policies, NonceStore())
    assert out["decision"] == "deny"
    assert out["reasons"] == ["deny:p-deny"]
    out2 = authorize(_intent(), _mint_for(_intent())[1], [], NonceStore())
    assert out2["decision"] == "deny"
    assert out2["reasons"] == ["default_deny:no-matching-allow"]


def test_require_approval_steps_up() -> None:
    intent = _intent()
    _, payload = _mint_for(intent)
    policies = [{"id": "p-step", "actions": ["payments.*"], "resources": ["*"],
                 "effect": "require_approval"}]
    out = authorize(intent, payload, policies, NonceStore())
    assert out["decision"] == "step_up"
    assert out["reasons"] == ["require_approval:p-step"]


def test_nonce_store_file_backend_persists(tmp_path: Path) -> None:
    backend = tmp_path / "nonces.json"
    store = NonceStore(path=backend)
    assert store.consume_once("file-nonce-0000000001", _now_ms() + 60_000) is True
    reopened = NonceStore(path=backend)
    assert reopened.consume_once("file-nonce-0000000001", _now_ms() + 60_000) is False


def test_quorum_pending_then_approved() -> None:
    record = "rec-quorum-auth-1"
    first = request_approval(record, 2, {"alice"})
    assert first == {"status": "pending", "n": 1, "need": 2}
    second = request_approval(record, 2, {"alice", "bob"})
    assert second == {"status": "approved", "n": 2, "need": 2}
