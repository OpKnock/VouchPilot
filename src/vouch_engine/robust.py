# Perturbation robustness for O4 (missing fields) and O5 (header renames). New file (004).
# Raw-level perturbations with seeded RNG; keyword/stub scorers for sweep speed.
# Every rate point is deterministic given the seed.

from __future__ import annotations

import random

from . import baseline, evidence, ingest, normalise, perspective, validate
from . import evaluate as eval_mod

ESSENTIAL_CANON = {'doc.invoice_number', 'doc.date', 'seller.name', 'buyer.name',
                   'money.total', 'money.taxable', 'money.currency', 'narration',
                   'items.desc', 'pay.mode', 'pay.utr', 'people.employee',
                   'refs.invoice', 'refs.order', 'refs.receipt_note', 'refs.delivery'}


def _reverse_aliases() -> dict:
    rev: dict[str, list[str]] = {}
    for canon, aliases in normalise.ALIASES.items():
        if isinstance(aliases, list):
            rev[str(canon)] = [str(a) for a in aliases]
    return rev


def perturb_mapped(raw_rows: list[dict], mapping: dict, drop_rate: float,
                  rename_rate: float, seed: int) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    rev = _reverse_aliases()
    droppable = [raw for raw, canon in mapping.items() if canon not in ESSENTIAL_CANON]
    dropped = {raw for raw in droppable if rng.random() < drop_rate}
    renames: dict[str, str] = {}
    for raw, canon in mapping.items():
        if raw in dropped or rng.random() >= rename_rate:
            continue
        pool = [a for a in rev.get(canon, []) if a != raw]
        if pool:
            renames[raw] = rng.choice(pool)
    new_rows: list[dict] = []
    for row in raw_rows:
        new_row: dict = {}
        for key, value in row.items():
            canon = mapping.get(key)
            if canon in dropped or key in dropped:
                continue
            new_row[renames.get(key, key)] = value
        new_rows.append(new_row)
    return new_rows, {'dropped': sorted(dropped), 'renamed': renames}


def _score_rows(raw_rows: list[dict], scorer_name: str) -> list[dict]:
    headers = sorted({k for row in raw_rows for k in row.keys()})
    mapping = normalise.map_columns(headers, raw_rows[:5])
    canonical = normalise.to_canonical(raw_rows, mapping)
    perspective.resolve(canonical)
    preds = []
    for pos, crow in enumerate(canonical, start=1):
        tags, mask = evidence.extract(crow)
        if scorer_name == 'stub':
            from .scorer import StubScorer
            label, conf, top_k = StubScorer().predict(crow, tags, mask)
        else:
            label, conf = baseline.keyword_predict(crow, tags)
            top_k = [[label, 1.0]]
        invoice = (crow.get('doc') or {}).get('invoice_number') or 'ROW-%d' % (pos,)
        preds.append(validate.validate_prediction({
            'row_id': pos, 'invoice_number': invoice, 'voucher_type': label,
            'confidence': float(conf), 'needs_review': bool(float(conf) < 0.5),
            'top_k': top_k, 'evidence': list(tags)}))
    return preds


def sweep(gold_xlsx: str, labels: list[dict], rates: list[float],
           rename_rates: list[float], scorer_name: str = 'keyword',
           seed: int = 7) -> dict:
    data = ingest.read_excel(gold_xlsx)
    raw_rows = list(data.get('rows', []))
    mapping = normalise.map_columns(list(data.get('headers', [])), raw_rows)
    truth = {item['row_id']: item['voucher_type'] for item in labels}
    drop_curve, rename_curve = [], []
    base_f1 = None
    for rate in rates:
        perturbed, _ = perturb_mapped(raw_rows, mapping, rate, 0.0, seed)
        preds = _score_rows(perturbed, scorer_name)
        yt = [truth.get(p.row_id, '') for p in preds]
        yp = [p.voucher_type for p in preds]
        rep = eval_mod.compute_metrics(yt, yp)
        drop_curve.append({'rate': rate, 'macro_f1': rep['macro_f1'],
                           'accuracy': rep['accuracy']})
        if base_f1 is None:
            base_f1 = rep['macro_f1']
    for rate in rename_rates:
        perturbed, _ = perturb_mapped(raw_rows, mapping, 0.0, rate, seed)
        preds = _score_rows(perturbed, scorer_name)
        yt = [truth.get(p.row_id, '') for p in preds]
        yp = [p.voucher_type for p in preds]
        rep = eval_mod.compute_metrics(yt, yp)
        rename_curve.append({'rate': rate, 'macro_f1': rep['macro_f1'],
                             'accuracy': rep['accuracy']})
    f30 = next((p['macro_f1'] for p in drop_curve if abs(p['rate'] - 0.3) < 1e-9), None)
    verdict_o4 = (base_f1 - f30 <= 0.10) if (base_f1 is not None and f30 is not None) else None
    rmax = rename_curve[-1]['macro_f1'] if rename_curve else None
    verdict_o5 = (base_f1 - rmax <= 0.05) if (base_f1 is not None and rmax is not None) else None
    return {'base_macro_f1': base_f1, 'drop_curve': drop_curve, 'rename_curve': rename_curve,
            'verdict_o4_drop_within_10pts': verdict_o4,
            'verdict_o5_rename_within_5pts': verdict_o5, 'seed': seed, 'scorer': scorer_name}


__all__ = ['ESSENTIAL_CANON', 'perturb_mapped', 'sweep']

