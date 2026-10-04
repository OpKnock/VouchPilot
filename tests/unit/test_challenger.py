"""Unit tests for the pairwise challenger (002/US3). No network."""

from vouch_engine.challenger import PAIRS, pairwise_f1, recheck


def test_pairs_count_and_canonical_names():
    assert len(PAIRS) == 11
    flat = {name for pair in PAIRS for name in pair}
    assert "Purchase" in flat and "Sales" in flat
    assert "Purchase Return / Debit Note" in flat
    assert "Sales Return / Credit Note" in flat
    assert "Advance / Prepayment" in flat
    assert "Salary / Payroll" in flat


def _mock_complete_favouring(first_label_calls):
    """Return complete_fn favouring label_a consistently across orderings."""
    calls = []

    def fn(prompt, codes):
        calls.append((prompt, list(codes)))
        # First call: A=label_a. Second call: A=label_b.
        # Favour label_a: P(A)=0.8 in call 1, P(B)=0.7 in call 2.
        if len(calls) == 1:
            return {"A": 0.8, "B": 0.2}
        return {"A": 0.3, "B": 0.7}

    first_label_calls.append(calls)
    return fn


def test_order_swap_averaging_picks_label_a():
    bucket: list = []
    fn = _mock_complete_favouring(bucket)
    winner, conf = recheck("row desc", ["T1"], "Purchase", "Sales", fn)
    assert winner == "Purchase"
    # avg P(Purchase) = (0.8 + 0.7) / 2 = 0.75
    assert abs(conf - 0.75) < 1e-9
    assert len(bucket[0]) == 2
    # Codes are A/B and order is swapped: second prompt flips A/B labels.
    assert "A = Purchase" in bucket[0][0][0]
    assert "A = Sales" in bucket[0][1][0]


def test_order_swap_averaging_math_flips():
    def fn(prompt, codes):
        if "A = Purchase" in prompt:
            return {"A": 0.1, "B": 0.9}
        return {"A": 0.9, "B": 0.1}

    winner, conf = recheck("desc", [], "Purchase", "Sales", fn)
    # P(Purchase) = (0.1 + 0.1) / 2 = 0.1 -> Sales wins with 0.9.
    assert winner == "Sales"
    assert abs(conf - 0.9) < 1e-9


def test_pairwise_f1_perfect_and_worst():
    pairs = [("Purchase", "Sales")]
    perfect = pairwise_f1(["Purchase", "Sales"], ["Purchase", "Sales"], pairs)
    assert abs(perfect[("Purchase", "Sales")] - 1.0) < 1e-9
    swapped = pairwise_f1(["Purchase", "Sales"], ["Sales", "Purchase"], pairs)
    assert swapped[("Purchase", "Sales")] == 0.0
