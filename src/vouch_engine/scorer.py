"""Hierarchical SLM scorer: group-then-member single-token reads + stub fallback.

Contracts:
- predict(row, tags, mask) -> (label in LABEL_NAMES, confidence, top_k top3).
- Stdlib only (urllib, json).
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from .labels import GROUPS, LABELS, PRECEDENCE_V1

GROUP_CODES: list[str] = list(GROUPS.keys())


class ScorerError(RuntimeError):
    """Base error for failures that make a model prediction untrustworthy."""


class ScorerUnavailableError(ScorerError):
    """The local model server could not be reached or did not answer."""


class ScorerResponseError(ScorerError):
    """The model server responded, but not with a usable completion payload."""

# Qwen3.5 is a thinking model: the chat template opens a <think> block that
# must be closed for direct single-token answers (verified against
# llama-server /apply-template + /completion probes).
THINK_CLOSE_SUFFIX = "\n</think>\n\n"


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(_format_value(v) for v in value if v is not None)
    if isinstance(value, dict):
        inner = ", ".join(f"{k}={_format_value(v)}" for k, v in value.items())
        return "{" + inner + "}"
    return str(value)


def _format_row(row: dict[str, Any]) -> str:
    """Render canonical row as compact `key: value` lines."""
    lines: list[str] = []
    for key in sorted(row.keys()):
        value = row[key]
        if isinstance(value, dict):
            for sub in sorted(value.keys()):
                lines.append(f"{key}.{sub}: {_format_value(value[sub])}")
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                for i, item in enumerate(value):
                    lines.append(f"items[{i}]: {_format_value(item)}")
            else:
                lines.append(f"{key}: {_format_value(value)}")
        else:
            lines.append(f"{key}: {_format_value(value)}")
    return "\n".join(lines)


def _format_exemplars(exemplars: list[Any]) -> str:
    if not exemplars:
        return "Exemplars: none"
    lines = ["Exemplars:"]
    for i, ex in enumerate(exemplars):
        if isinstance(ex, dict):
            label = ex.get("label", ex.get("voucher_type", ""))
            text = ex.get("text", ex.get("row", ""))
            lines.append(f"- exemplar {i + 1} [{label}]: {_format_value(text)}")
        else:
            lines.append(f"- exemplar {i + 1}: {_format_value(ex)}")
    return "\n".join(lines)


def _precedence_lines() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in PRECEDENCE_V1.items())


def _group_table() -> str:
    return "\n".join(f"{code} = {name}" for code, name in GROUPS.items())


def _member_table(group_code: str) -> str:
    rows = [lb for lb in LABELS if lb["group"] == group_code]
    return "\n".join(f"{lb['code']} = {lb['name']}" for lb in rows)


def build_group_prompt(
    row: dict[str, Any],
    tags: list[str],
    exemplars: list[Any] | None = None,
) -> str:
    """Build the group-step prompt (answer is one of A-G)."""
    ex = exemplars or []
    return (
        "You are an Indian accounting voucher classifier. "
        "Choose the voucher group for the row. Rules: use only the codes below; "
        "specific labels win over generic ones per the precedence policy; "
        "missing fields are signals, not gaps.\n"
        "Group codes:\n"
        f"{_group_table()}\n"
        "Precedence policy (v1):\n"
        f"{_precedence_lines()}\n"
        f"{_format_exemplars(ex)}\n"
        "Target row (key: value):\n"
        f"{_format_row(row if isinstance(row, dict) else {})}\n"
        f"Evidence tags: {', '.join(tags) if tags else 'none'}\n"
        "Answer with a single code token (one of A, B, C, D, E, F, G). Group:"
    )


def build_member_prompt(
    row: dict[str, Any],
    tags: list[str],
    group_code: str,
    exemplars: list[Any] | None = None,
) -> str:
    """Build the member-step prompt for one group (answer is a member code)."""
    ex = exemplars or []
    return (
        "You are an Indian accounting voucher classifier. "
        f"Choose the voucher within group {group_code}. Rules: use only the "
        "member codes below; specific labels win per the precedence policy.\n"
        f"Member codes for group {group_code}:\n"
        f"{_member_table(group_code)}\n"
        "Precedence policy (v1):\n"
        f"{_precedence_lines()}\n"
        f"{_format_exemplars(ex)}\n"
        "Target row (key: value):\n"
        f"{_format_row(row if isinstance(row, dict) else {})}\n"
        f"Evidence tags: {', '.join(tags) if tags else 'none'}\n"
        "Answer with a single code token (member code only). Member:"
    )


def _normalise(dist: dict[str, float], valid_codes: list[str]) -> dict[str, float]:
    total = sum(dist.get(c, 0.0) for c in valid_codes)
    if total <= 0:
        uniform = 1.0 / len(valid_codes) if valid_codes else 0.0
        return {c: uniform for c in valid_codes}
    return {c: dist.get(c, 0.0) / total for c in valid_codes}


class LlamaServerScorer:
    """Thin stdlib client over a llama.cpp server `/completion` endpoint."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8080",
        timeout: int = 120,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def _format_prompt(self, prompt: str) -> str:
        """Apply the server-side chat template; close the think block.

        Falls back to the raw prompt if /apply-template is unavailable.
        """
        body = json.dumps(
            {
                "messages": [{"role": "user", "content": prompt}],
                "add_generation_prompt": True,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint + "/apply-template",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_err: str | None = None
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                time.sleep(1.0 * attempt)
        else:
            data = {}
        if not data:
            print(f"WARN: /apply-template failed ({last_err}); raw prompt", file=sys.stderr)
            return prompt
        try:
            formatted = str(data.get("prompt", prompt))
            # Close the think block only for thinking models whose template
            # opens one (e.g. Qwen3.5); non-thinking models (e.g. Gemma 4)
            # must not receive stray think tokens.
            if "<think>" in formatted and "</think>" not in formatted:
                formatted += THINK_CLOSE_SUFFIX
            return formatted
        except (ValueError, TypeError, AttributeError) as exc:
            print(f"WARN: /apply-template parse failed ({exc}); raw prompt", file=sys.stderr)
            return prompt

    @staticmethod
    def _entry_prob(entry: dict[str, Any]) -> tuple[str, float]:
        """Normalise both llama-server shapes: probs/tok_str/prob and
        top_logprobs/token/logprob (prob = exp(logprob))."""
        tok = str(entry.get("tok_str", entry.get("token", "")))
        if "prob" in entry:
            try:
                return tok, float(entry.get("prob", 0.0))
            except (TypeError, ValueError):
                return tok, 0.0
        if "logprob" in entry:
            try:
                return tok, math.exp(float(entry.get("logprob", float("-inf"))))
            except (TypeError, ValueError, OverflowError):
                return tok, 0.0
        return tok, 0.0

    def _complete(self, prompt: str, valid_codes: list[str]) -> dict[str, float]:
        """Single-token read: POST completion, map token probs to valid codes."""
        raw: dict[str, float] = {c: 0.0 for c in valid_codes}
        valid_set = set(valid_codes)
        payload = {
            "prompt": self._format_prompt(prompt),
            "n_predict": 1,
            "n_probs": 50,
            "temperature": 0,
            # cache_prompt intentionally off: b11374 server returns HTTP 500
            # on concurrent cached-prompt restores (q8 KV + parallel slots).
            "cache_prompt": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint + "/completion",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_err: str | None = None
        data: dict = {}
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                time.sleep(1.0 * attempt)
        if not data:
            raise ScorerUnavailableError(
                f"local model server unavailable at {self.endpoint}: {last_err or 'no response'}"
            )
        try:
            first = data["completion_probabilities"][0]
            probs = first.get("probs") or first.get("top_logprobs") or []
        except (KeyError, IndexError, TypeError, AttributeError):
            probs = []
        matched_any = False
        for entry in probs:
            if not isinstance(entry, dict):
                continue
            tok, p = self._entry_prob(entry)
            t = tok.strip()
            if t in valid_set:
                raw[t] += p
                matched_any = True
                continue
            cleaned = t.strip(" \t\n\r\"'`,.:;()[]{}")
            if cleaned in valid_set:
                raw[cleaned] += p
                matched_any = True
                continue
            # Fallback: substring match; longest code wins for this token.
            cands = [c for c in valid_codes if c and c in t]
            if cands:
                cands.sort(key=lambda c: (-len(c), valid_codes.index(c)))
                raw[cands[0]] += p
                matched_any = True
        if not matched_any:
            raise ScorerResponseError(
                f"local model server at {self.endpoint} returned no usable token probabilities"
            )
        return _normalise(raw, valid_codes)

    def predict(
        self,
        row: dict[str, Any],
        tags: list[str],
        mask: dict[str, float],
        exemplars: list[Any] | None = None,
    ) -> tuple[str, float, list[list[Any]]]:
        """Group step over A-G, member step for top-2 groups, mask, renormalise."""
        tags = tags or []
        mask = mask or {}
        group_probs = self._complete(build_group_prompt(row, tags, exemplars), GROUP_CODES)
        ranked_groups = sorted(GROUP_CODES, key=lambda g: (-group_probs.get(g, 0.0), g))
        top_groups = ranked_groups[:2]
        combined: dict[str, float] = {}
        for g in top_groups:
            members = [lb for lb in LABELS if lb["group"] == g]
            codes = [lb["code"] for lb in members]
            if not codes:
                continue
            member_probs = self._complete(build_member_prompt(row, tags, g, exemplars), codes)
            gp = group_probs.get(g, 0.0)
            for lb in members:
                combined[lb["name"]] = gp * member_probs.get(lb["code"], 0.0)
        # Multiply feasibility mask (default 1.0 when a label is absent).
        for name in list(combined.keys()):
            combined[name] *= float(mask.get(name, 1.0))
        total = sum(combined.values())
        if total <= 0:
            names = list(combined.keys()) or [lb["name"] for lb in LABELS]
            uniform = 1.0 / len(names)
            combined = {n: uniform for n in names}
        else:
            combined = {n: v / total for n, v in combined.items()}
        order = {lb["name"]: i for i, lb in enumerate(LABELS)}
        ranked = sorted(combined.items(), key=lambda kv: (-kv[1], order.get(kv[0], 999)))
        label = ranked[0][0]
        confidence = float(ranked[0][1])
        top_k: list[list[Any]] = [[name, float(prob)] for name, prob in ranked[:3]]
        return label, confidence, top_k


class StubScorer:
    """Deterministic weightless scorer: mask order decides the label."""

    def predict(
        self,
        row: dict[str, Any],
        tags: list[str],
        mask: dict[str, float],
        exemplars: list[Any] | None = None,
    ) -> tuple[str, float, list[list[Any]]]:
        _ = row
        _ = tags
        _ = exemplars
        order = {lb["name"]: i for i, lb in enumerate(LABELS)}
        if not mask:
            weights = {lb["name"]: 1.0 for lb in LABELS}
        else:
            weights = {lb["name"]: float(mask.get(lb["name"], 0.0)) for lb in LABELS}
        ranked = sorted(weights.items(), key=lambda kv: (-kv[1], order.get(kv[0], 999)))
        label = ranked[0][0]
        top3 = ranked[:3]
        total = sum(v for _, v in top3)
        if total <= 0:
            top_k: list[list[Any]] = [[n, 1.0 / len(top3)] for n, _ in top3]
        else:
            top_k = [[n, float(v) / total] for n, v in top3]
        return label, 0.5, top_k


__all__ = [
    "GROUP_CODES",
    "ScorerError",
    "ScorerUnavailableError",
    "ScorerResponseError",
    "LlamaServerScorer",
    "StubScorer",
    "build_group_prompt",
    "build_member_prompt",
]
