"""Bounded agentic loop: inspect -> reason/classify -> challenge -> approve -> export.

Roles run in fixed order with typed I/O and budgets. Every tool call is local
and recorded in trace.jsonl. No free-roaming behaviour by construction.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
import os
import sys
from typing import Any

from . import __main__ as cli
from .labels import LABEL_NAMES

STEP_BUDGET_PER_ROW = 12

REVIEW_CONF_THRESHOLD = 0.5
REVIEW_CHALLENGED_CONF = 0.7

GATE_MODES = ('auto', 'cli', 'file')


class AgentState:
    def __init__(self, run_dir: str):
        self.run_dir = run_dir
        self.seq = 0
        self.trace: list[dict] = []
        self.tool_calls = 0

    def log(self, phase: str, tool: str, row_id: Any, detail: str) -> None:
        self.seq += 1
        self.tool_calls += 1
        self.trace.append(
            {'seq': self.seq, 'phase': phase, 'tool': tool,
             'row_id': row_id, 'detail': detail}
        )

    def write_trace(self, path: str) -> None:
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            for entry in self.trace:
                handle.write(json.dumps(entry) + chr(10))


def inspect_sheet(mods: dict, input_path: str, state: AgentState) -> dict:
    data = mods['ingest'].read_excel(input_path)
    state.log('inspect', 'inspect_sheet', None, 'read excel')
    headers, raw_rows = list(data.get('headers', [])), list(data.get('rows', []))
    mapping = mods['normalise'].map_columns(headers, raw_rows)
    state.log('inspect', 'map_schema', None, 'mapped columns')
    canonical = mods['normalise'].to_canonical(raw_rows, mapping)
    self_entity, perspectives = mods['perspective'].resolve(canonical)
    state.log('inspect', 'resolve_perspective', None, 'self=%s' % (self_entity,))
    profile = data.get('profile', {}) or {}
    mapped = sum(1 for v in mapping.values() if v)
    total = len(mapping) or 1
    counts: dict[str, int] = {}
    for p in perspectives:
        counts[p] = counts.get(p, 0) + 1
    n = len(canonical)
    flags: list[str] = []
    if mapped / total < 0.6:
        flags.append('low-schema-coverage')
    if n and counts.get('unknown', 0) / n > 0.3:
        flags.append('perspective-uncertain')
    if not any((r.get('doc') or {}).get('invoice_number') for r in canonical):
        flags.append('no-invoice-numbers')
    report = {
        'n_rows': n, 'header_row': profile.get('header_row'),
        'mapped_columns': mapped, 'total_columns': len(mapping),
        'unmapped_columns': sorted([k for k, v in mapping.items() if not v]),
        'self_entity': self_entity, 'perspectives': counts, 'red_flags': flags,
    }
    return {'report': report, 'headers': headers, 'raw_rows': raw_rows,
            'mapping': mapping, 'canonical': canonical}


def classify_all(ctx: dict, indices: list[int], workers: int,
                state: AgentState) -> list[dict]:
    states: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for pos, st in enumerate(pool.map(lambda i: cli._first_pass_state(ctx, i), indices), start=1):
            states.append(st)
            state.log('classify', 'score_row', st.get('row_id'), 'ok=%s' % (st.get('ok'),))
            if pos % 10 == 0 or pos == len(indices):
                print('progress %d/%d' % (pos, len(indices)), file=sys.stderr)
    return states


def challenge_budgeted(ctx: dict, states: list[dict], margin_thr: float,
                     max_rate: float, state: AgentState) -> tuple[int, int]:
    budget = math.ceil(max_rate * len(states)) if max_rate > 0 else 0
    ranked = sorted(
        ((cli._margin_of(s['top_k']), n) for n, s in enumerate(states)
         if s['ok'] and isinstance(s.get('top_k'), list) and len(s['top_k']) >= 2
         and cli._margin_of(s['top_k']) < margin_thr),
        key=lambda t: (t[0], t[1]),
    )
    chosen = {n for _, n in ranked[:budget]}
    ctx['states'] = states
    challenged = skipped = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=ctx.get('workers', 1)) as pool:
        results = list(pool.map(lambda i: cli._challenge_state(ctx, i), sorted(chosen)))
    for n, result, err in results:
        s = states[n]
        if err is not None:
            skipped += 1
            s['force_review'] = True
            state.log('challenge', 'challenge_row', s.get('row_id'), 'skipped=%s' % (err,))
            continue
        winner, chal_conf = result
        s['label'], s['conf'] = winner, float(chal_conf)
        if s['top_k'] and s['top_k'][0][0] == winner:
            s['top_k'][0][1] = float(chal_conf)
        s['tags'] = s['tags'] + ['CHALLENGED']
        challenged += 1
        state.log('challenge', 'challenge_row', s.get('row_id'), 'winner=%s' % (winner,))
    return challenged, skipped


def build_review_queue(states: list[dict]) -> list[dict]:
    queue = []
    for s in states:
        if not s.get('ok'):
            continue
        conf = float(s.get('conf', 0.0))
        tags = s.get('top_k', [])
        challenged = any('CHALLENGED' in t for t in s.get('tags', []))
        if conf < REVIEW_CONF_THRESHOLD:
            reason = 'low-confidence'
        elif challenged and conf < REVIEW_CHALLENGED_CONF:
            reason = 'challenged-uncertain'
        else:
            continue
        crow = s.get('crow', {}) or {}
        queue.append({
            'row_id': s.get('row_id'), 'invoice_number': s.get('invoice'),
            'model_label': s.get('label'), 'confidence': conf,
            'top_k': tags, 'evidence': list(s.get('tags', [])),
            'narration': (crow.get('narration', '') or '')[:280],
            'reason': reason,
        })
    return queue


def gate_cli(queue: list[dict]) -> list[dict]:
    decisions = []
    print('%d rows need human approval.' % (len(queue),))
    print('Commands per row: [a]pprove  [o]verride LABEL  [e]scalate  [A]pprove-all-remaining  [q]uit')
    approve_rest = False
    for item in queue:
        rid = item['row_id']
        if approve_rest:
            decisions.append({'row_id': rid, 'verdict': 'approve', 'note': 'batch'})
            continue
        print('-' * 60)
        print('row %s | %s | model=%s (%.3f) | %s' % (
            rid, item['invoice_number'], item['model_label'],
            item['confidence'], item['reason']))
        print('top_k=%s' % (item['top_k'][:3],))
        print('evidence=%s' % (item['evidence'][:8],))
        if item['narration']:
            print('narr=%s' % (item['narration'][:200],))
        while True:
            try:
                raw = input('[a/o LABEL/e/A/q] ').strip()
            except EOFError:
                raw = 'q'
            if raw.lower() == 'a':
                decisions.append({'row_id': rid, 'verdict': 'approve'})
                break
            if raw.lower() == 'a-all' or raw == 'A':
                approve_rest = True
                decisions.append({'row_id': rid, 'verdict': 'approve', 'note': 'batch'})
                break
            if raw.lower() == 'e':
                decisions.append({'row_id': rid, 'verdict': 'escalate'})
                break
            if raw.lower() == 'q':
                for rest in queue[queue.index(item) + 1:]:
                    decisions.append({'row_id': rest['row_id'], 'verdict': 'escalate', 'note': 'quit'})
                decisions.append({'row_id': rid, 'verdict': 'escalate', 'note': 'quit'})
                return decisions
            if raw.lower().startswith('o '):
                label = raw[2:].strip()
                if label not in LABEL_NAMES:
                    print('unknown label; valid: %s' % (', '.join(LABEL_NAMES),))
                    continue
                note = input('note (optional): ').strip()
                decisions.append({'row_id': rid, 'verdict': 'override',
                                  'label': label, 'note': note})
                break
            print('unknown command')
    return decisions


def gate_file(path: str) -> list[dict]:
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    items = data.get('decisions', data if isinstance(data, list) else [])
    out = []
    for item in items:
        verdict = str(item.get('verdict', 'approve')).lower()
        if verdict not in ('approve', 'override', 'escalate'):
            raise ValueError('bad verdict for row %s' % (item.get('row_id'),))
        if verdict == 'override' and item.get('label') not in LABEL_NAMES:
            raise ValueError('bad override label for row %s' % (item.get('row_id'),))
        out.append({'row_id': item['row_id'], 'verdict': verdict,
                    'label': item.get('label'), 'note': item.get('note', '')})
    return out


def apply_gate(states: list[dict], decisions: list[dict], gate: str,
               state: AgentState) -> list[dict]:
    by_id = {d['row_id']: d for d in decisions}
    approvals = []
    for s in states:
        if not s.get('ok'):
            continue
        rid = s.get('row_id')
        model_label = s['label']
        dec = by_id.get(rid, {'verdict': 'approve'})
        verdict = dec['verdict']
        final = model_label
        if verdict == 'override':
            final = dec['label']
            s['tags'] = s['tags'] + ['HUMAN:override->%s' % (final,)]
            s['label'] = final
            s['conf'] = max(float(s.get('conf', 0.0)), 0.51)
            s['cleared'] = True
        elif verdict == 'escalate':
            s['force_review'] = True
            s['tags'] = s['tags'] + ['HUMAN:escalated']
        else:
            s['tags'] = s['tags'] + ['HUMAN:approved']
            s['cleared'] = True
        state.log('gate', 'human_verdict', rid, '%s final=%s' % (verdict, final))
        approvals.append({'row_id': rid, 'model_label': model_label,
                          'final_label': final, 'verdict': verdict,
                          'note': dec.get('note', ''), 'by': gate})
    return approvals


__all__ = ['AgentState', 'inspect_sheet', 'classify_all', 'challenge_budgeted',
           'build_review_queue', 'gate_cli', 'gate_file', 'apply_gate']

