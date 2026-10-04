"""VouchPilotScorer: optional fraud-aware wrapper around any base scorer.

Default off. Wraps keyword/stub/server base, applies fraud_quish and
firewall penalties, then optional temperature rescaling. Same
predict(row, tags, mask, exemplars) contract. Any extension failure is
reported on stderr and the unpenalized base verdict is kept (never drops rows).
"""

from __future__ import annotations

import sys
from typing import Any

try:
    from vouch_engine import baseline as _baseline
    from vouch_engine import scorer as _scorer_mod
    from vouch_engine.labels import LABEL_NAMES
except Exception:
    _baseline = None  # type: ignore[assignment]
    _scorer_mod = None  # type: ignore[assignment]
    LABEL_NAMES = []

try:
    from extensions import fraud_firewall as _firewall
except Exception as exc:
    _firewall = None  # type: ignore[assignment]
    print('WARN: fraud_firewall unavailable (%s); disabled' % (exc,), file=sys.stderr)

try:
    from extensions import fraud_quish as _quish
except Exception as exc:
    _quish = None  # type: ignore[assignment]
    print('WARN: fraud_quish unavailable (%s); disabled' % (exc,), file=sys.stderr)

try:
    from vouch_engine.calibrate import apply_conf as _apply_conf
except Exception:
    _apply_conf = None  # type: ignore[assignment]


class VouchPilotScorer:
    def __init__(self, base: str = 'keyword', endpoint: str = 'http://127.0.0.1:8080',
                 fraud: bool = True, firewall: bool = True, temperature: float | None = None):
        self.base_name = base
        self.temperature = temperature
        self.use_fraud = bool(fraud) and _quish is not None
        self.use_firewall = bool(firewall) and _firewall is not None
        self.last: dict[str, Any] = {}
        if base == 'server' and _scorer_mod is not None:
            self._base = _scorer_mod.LlamaServerScorer(endpoint=endpoint)
        elif base == 'stub' and _scorer_mod is not None:
            self._base = _scorer_mod.StubScorer()
        else:
            from vouch_engine.__main__ import _KeywordAdapter
            self._base = _KeywordAdapter(_baseline)

    def _audit_text(self, row: dict) -> str:
        parts = [str(row.get('narration', '') or '')]
        for value in (row.get('raw') or {}).values():
            parts.append(str(value))
        return ' '.join(parts)

    def predict(self, row: dict, tags: list, mask: dict,
               exemplars: Any = None) -> tuple[str, float, list]:
        try:
            label, conf, top_k = self._base.predict(row, tags, mask, exemplars)
        except TypeError:
            label, conf, top_k = self._base.predict(row, tags, mask)
        conf = float(conf)
        audit: dict[str, Any] = {'base': self.base_name}
        if self.use_fraud:
            try:
                fscore, fflags = _quish.score_bill(row)
                audit['fraud_score'] = int(fscore)
                audit['fraud_flags'] = list(fflags)
                conf *= max(0.4, 1.0 - float(fscore) / 250.0)
            except Exception as exc:
                audit['fraud_error'] = str(exc)
                print('WARN: fraud check failed (%s); unpenalized' % (exc,), file=sys.stderr)
        if self.use_firewall:
            try:
                wscore, action = _firewall.check_narration(self._audit_text(row))
                audit['firewall_score'] = int(wscore)
                audit['firewall_action'] = str(action)
                if action == 'block':
                    conf *= 0.1
                elif action == 'sanitize':
                    conf *= 0.7
                elif action == 'warn':
                    conf *= 0.9
            except Exception as exc:
                audit['firewall_error'] = str(exc)
                print('WARN: firewall check failed (%s); unpenalized' % (exc,), file=sys.stderr)
        if self.temperature is not None and _apply_conf is not None:
            try:
                conf = float(_apply_conf(conf, float(self.temperature)))
            except Exception as exc:
                audit['calibrate_error'] = str(exc)
        old_top = float(top_k[0][1]) if top_k else 0.0
        factor = (conf / old_top) if old_top > 0 else 1.0
        top_k = [
            [name, max(0.0, min(1.0, float(prob) * factor))]
            for name, prob in (top_k or [[label, conf]])
        ]
        self.last = audit
        return label, max(0.0, min(1.0, conf)), top_k


__all__ = ['VouchPilotScorer']

