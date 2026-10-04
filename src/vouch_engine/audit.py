# Retro-audit: recorded-vs-predicted disagreement reports plus inter-rater kappa.
# New file (004). Stdlib only.

from __future__ import annotations


def audit_recorded_vs_predicted(records: list[dict], predictions: list[dict]) -> dict:
    pred_by_id = {p.get('row_id'): p for p in predictions}
    per: dict[str, dict] = {}
    disagreements: list[dict] = []
    n = 0
    agree = 0
    for rec in records:
        rid = rec.get('row_id')
        pred = pred_by_id.get(rid)
        if pred is None:
            continue
        recorded = rec.get('voucher_type', '')
        predicted = pred.get('voucher_type', '')
        n += 1
        cell = per.setdefault(recorded, {'label': recorded, 'n': 0, 'agree': 0,
                                         'confusions': {}})
        cell['n'] += 1
        if recorded == predicted:
            agree += 1
            cell['agree'] += 1
        else:
            cell['confusions'][predicted] = cell['confusions'].get(predicted, 0) + 1
            disagreements.append({'row_id': rid, 'invoice_number': rec.get('invoice_number', ''),
                                  'recorded': recorded, 'predicted': predicted,
                                  'confidence': float(pred.get('confidence', 0.0))})
    per_label = []
    for label in sorted(per):
        cell = per[label]
        top = sorted(cell['confusions'].items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        per_label.append({'label': label, 'n': cell['n'], 'agree': cell['agree'],
                          'agree_rate': (cell['agree'] / cell['n']) if cell['n'] else 0.0,
                          'top_confusions': [{'predicted': k, 'n': v} for k, v in top]})
    return {'n_rows': n, 'agreement': (agree / n) if n else 0.0,
            'per_label': per_label, 'disagreements': disagreements}


def cohen_kappa(rater_a: list[str], rater_b: list[str]) -> dict:
    if len(rater_a) != len(rater_b) or not rater_a:
        raise ValueError('raters must be non-empty equal-length lists')
    cats = sorted(set(rater_a) | set(rater_b))
    n = len(rater_a)
    observed = sum(1 for a, b in zip(rater_a, rater_b) if a == b) / n
    expected = 0.0
    for cat in cats:
        pa = sum(1 for a in rater_a if a == cat) / n
        pb = sum(1 for b in rater_b if b == cat) / n
        expected += pa * pb
    kappa = (observed - expected) / (1.0 - expected) if expected < 1.0 else 1.0
    return {'kappa': kappa, 'observed': observed, 'expected': expected,
            'n': n, 'n_categories': len(cats)}


__all__ = ['audit_recorded_vs_predicted', 'cohen_kappa']

