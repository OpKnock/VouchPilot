"""Pairwise challenger for look-alike labels (002/US3). Stdlib + sklearn only."""

from __future__ import annotations

from typing import Callable

PAIRS: list[tuple[str, str]] = [
    ("Purchase", "Sales"),
    ("Purchase", "Import"),
    ("Sales", "Export"),
    ("Purchase", "Purchase Return / Debit Note"),
    ("Sales", "Sales Return / Credit Note"),
    ("Payment", "Contra"),
    ("Payment", "Advance / Prepayment"),
    ("Journal", "Expense"),
    ("Receipt Note", "Material In"),
    ("Delivery Note", "Sales"),
    ("Salary / Payroll", "Payment"),
]


def _build_pairwise_prompt(
    row_desc: str, tags: list[str], first_label: str, second_label: str
) -> str:
    tag_str = ", ".join(tags) if tags else "none"
    return (
        "You are an Indian accounting voucher classifier. "
        "Choose between two voucher types. Answer with a single code token, "
        "either A or B.\n"
        f"A = {first_label}\n"
        f"B = {second_label}\n"
        f"Row: {row_desc}\n"
        f"Evidence tags: {tag_str}\n"
        "Answer with a single code token (A or B). Choice:"
    )


def _prob_of(dist: dict, code: str) -> float:
    if not isinstance(dist, dict):
        return 0.5
    try:
        a = float(dist.get("A", 0.0))
    except (TypeError, ValueError):
        a = 0.0
    try:
        b = float(dist.get("B", 0.0))
    except (TypeError, ValueError):
        b = 0.0
    total = a + b
    if total <= 0:
        return 0.5
    if code == "A":
        return a / total
    return b / total


def recheck(
    row_desc: str,
    tags: list[str],
    label_a: str,
    label_b: str,
    complete_fn: Callable[[str, list[str]], dict],
) -> tuple[str, float]:
    """Pairwise re-check with A/B order swap and averaged preference.

    Call 1 presents label_a as A and label_b as B; call 2 swaps them
    (label_b as A, label_a as B; codes always mean 'A = first-mentioned').
    P(label_a) is dist1['A'] in call 1 and dist2['B'] in call 2; the two
    are averaged. Winner is label_a iff avg >= 0.5; challenged confidence
    is the averaged probability of the winner.
    """
    tags = list(tags or [])
    prompt1 = _build_pairwise_prompt(row_desc, tags, label_a, label_b)
    dist1 = complete_fn(prompt1, ["A", "B"])
    p_a_1 = _prob_of(dist1, "A")
    prompt2 = _build_pairwise_prompt(row_desc, tags, label_b, label_a)
    dist2 = complete_fn(prompt2, ["A", "B"])
    p_a_2 = _prob_of(dist2, "B")
    avg = (float(p_a_1) + float(p_a_2)) / 2.0
    if avg >= 0.5:
        return label_a, float(avg)
    return label_b, float(1.0 - avg)


def pairwise_f1(y_true: list, y_pred: list, pairs: list) -> dict:
    """Macro-F1 per confusable pair on rows whose truth lies in the pair.

    For each pair (a, b), filter to indices with y_true in (a, b) and
    compute sklearn macro-F1 over labels [a, b] (zero_division=0). Empty
    slices score 1.0 when no prediction falls in the pair else 0.0.
    Keys are the input pair tuples.
    """
    from sklearn.metrics import f1_score

    y_true = list(y_true or [])
    y_pred = list(y_pred or [])
    out: dict = {}
    for pair in pairs or []:
        a, b = pair[0], pair[1]
        idx = [i for i, t in enumerate(y_true) if t == a or t == b]
        if not idx:
            preds_in = any(p == a or p == b for p in y_pred)
            out[(a, b)] = 0.0 if preds_in else 1.0
            continue
        sub_true = [y_true[i] for i in idx]
        sub_pred = [y_pred[i] if i < len(y_pred) else None for i in idx]
        out[(a, b)] = float(
            f1_score(sub_true, sub_pred, labels=[a, b], average="macro", zero_division=0)
        )
    return out


__all__ = ["PAIRS", "pairwise_f1", "recheck"]
