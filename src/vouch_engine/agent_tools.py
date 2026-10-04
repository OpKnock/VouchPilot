"""ToolRegistry for the VouchPilot agent loop: named tools with per-call cost,
a shared step budget (default 12, mirrors Agent STEP_BUDGET_PER_ROW), and every
call recorded through AgentState.log. Lazy extension imports with stderr
fallback notes; tools never drop rows (neutral result on failure).
"""

from __future__ import annotations

import sys
from typing import Any, Callable

BUDGET_DEFAULT = 12


class BudgetExceeded(RuntimeError):
    pass


class Tool:
    def __init__(self, name: str, cost: int, fn: Callable, description: str = ''):
        self.name = name
        self.cost = int(cost)
        self.fn = fn
        self.description = description


class ToolRegistry:
    def __init__(self, state, budget: int = BUDGET_DEFAULT):
        self.state = state
        self.budget = int(budget)
        self.spent = 0
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def call(self, name: str, row_id: Any, *args: Any, **kwargs: Any) -> Any:
        tool = self.tools.get(name)
        if tool is None:
            raise KeyError('unknown tool: %s' % (name,))
        if self.spent + tool.cost > self.budget:
            raise BudgetExceeded('step budget %d exceeded' % (self.budget,))
        self.spent += tool.cost
        try:
            result = tool.fn(*args, **kwargs)
        except Exception as exc:
            self.state.log('agent-tool', name, row_id, 'error=%s' % (exc,))
            raise
        self.state.log('agent-tool', name, row_id, 'cost=%d spent=%d' % (tool.cost, self.spent))
        return result

    def remaining(self) -> int:
        return self.budget - self.spent


def _optional(modname: str, attr: str | None = None):
    try:
        mod = __import__(modname, fromlist=['x'])
        return getattr(mod, attr) if attr else mod
    except Exception as exc:
        print('WARN: %s unavailable (%s)' % (modname, exc), file=sys.stderr)
        return None


def default_registry(state, scorer=None) -> ToolRegistry:
    reg = ToolRegistry(state)
    ingest = _optional('vouch_engine.ingest')
    if ingest is not None:
        reg.register(Tool('inspect_sheet', 1, ingest.read_excel, 'read plus profile a sheet'))
    if scorer is not None:
        reg.register(Tool('score_row', 3, scorer.predict, 'classify one row'))
    quish = _optional('extensions.fraud_quish')
    firewall = _optional('extensions.fraud_firewall')
    if quish is not None or firewall is not None:
        def _fraud_check(row: dict) -> dict:
            out: dict[str, Any] = {}
            if quish is not None:
                try:
                    score, flags = quish.score_bill(row)
                    out['quish'] = {'score': score, 'flags': flags}
                except Exception as exc:
                    out['quish'] = {'score': 0, 'flags': [], 'error': str(exc)}
            if firewall is not None:
                try:
                    text = str(row.get('narration', '') or '')
                    fscore, action = firewall.check_narration(text)
                    out['firewall'] = {'score': fscore, 'action': action}
                except Exception as exc:
                    out['firewall'] = {'score': 0, 'action': 'ok', 'error': str(exc)}
            return out
        reg.register(Tool('fraud_check', 2, _fraud_check, 'quish plus firewall screen'))
    trust = _optional('extensions.trust_pin')
    if trust is not None:
        def _pin_check(payload: bytes, pinned_hex: str) -> dict:
            try:
                return trust.verify_live_vs_pinned(payload, pinned_hex)
            except Exception as exc:
                return {'match': False, 'error': str(exc)}
        reg.register(Tool('pin_check', 1, _pin_check, 'tamper-evidence drift check'))
    reconcile = _optional('extensions.reconcile_zenml.pipeline')
    if reconcile is not None:
        def _reconcile_check(config: dict, steps: list) -> dict:
            try:
                return reconcile.run_pipeline(config, steps)
            except Exception as exc:
                return {'error': str(exc)}
        reg.register(Tool('reconcile_check', 4, _reconcile_check, 'bill retrain pipeline'))
    return reg


__all__ = ['BUDGET_DEFAULT', 'BudgetExceeded', 'Tool', 'ToolRegistry', 'default_registry']

