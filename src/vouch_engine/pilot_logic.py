"""Pure helpers for the unified VouchPilot web app (import-safe, UI-free).

Mirrors agent gate semantics: approve/override clear needs_review, escalate keeps it.
"""

from __future__ import annotations

from collections import Counter

from .labels import LABEL_NAMES


def apply_decisions(predictions: list[dict], decisions: list[dict]) -> tuple[list[dict], list[dict]]:
    by_id = {d['row_id']: d for d in decisions}
    final_rows: list[dict] = []
    approvals: list[dict] = []
    for pred in predictions:
        rid = pred.get('row_id')
        row = dict(pred)
        tags = list(row.get('evidence', []))
        dec = by_id.get(rid)
        if dec is None:
            tags = tags + ['HUMAN:approved']
            row['evidence'] = tags
            row['needs_review'] = False
            approvals.append({'row_id': rid, 'model_label': pred.get('voucher_type'),
                              'final_label': row['voucher_type'], 'verdict': 'approve',
                              'note': '', 'by': 'web-review'})
            final_rows.append(row)
            continue
        verdict = dec.get('verdict', 'approve')
        model_label = pred.get('voucher_type')
        if verdict == 'override' and dec.get('label') in LABEL_NAMES:
            row['voucher_type'] = dec['label']
            tags = tags + ['HUMAN:override->%s' % (dec['label'],)]
            row['needs_review'] = False
        elif verdict == 'escalate':
            tags = tags + ['HUMAN:escalated']
            row['needs_review'] = True
        else:
            tags = tags + ['HUMAN:approved']
            row['needs_review'] = False
        row['evidence'] = tags
        approvals.append({'row_id': rid, 'model_label': model_label,
                          'final_label': row['voucher_type'], 'verdict': verdict,
                          'note': dec.get('note', ''), 'by': 'web-review'})
        final_rows.append(row)
    return final_rows, approvals


def review_queue(predictions: list[dict]) -> list[dict]:
    return [p for p in predictions if p.get('needs_review')]


def label_distribution(predictions: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = Counter()
    for pred in predictions:
        counts[str(pred.get('voucher_type', '?'))] += 1
    return dict(counts)


def review_stats(predictions: list[dict], approvals: list[dict]) -> dict:
    by_verdict: dict[str, int] = Counter()
    for item in approvals:
        by_verdict[str(item.get('verdict', '?'))] += 1
    return {
        'n_rows': len(predictions),
        'needs_review': sum(1 for p in predictions if p.get('needs_review')),
        'mean_confidence': (sum(float(p.get('confidence', 0.0)) for p in predictions)
                            / len(predictions)) if predictions else 0.0,
        'by_verdict': dict(by_verdict),
    }


__all__ = ['apply_decisions', 'review_queue', 'label_distribution', 'review_stats']

