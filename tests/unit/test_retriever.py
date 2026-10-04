"""Unit tests for evidence-tag retrieval grounding (002/US1). No network."""

from vouch_engine.retriever import build_index, retrieve


def _ex(tags, label, row_id):
    return {"tags": tags, "label": label, "row_id": row_id}


def test_ranking_by_jaccard():
    idx = build_index(
        [
            _ex(["A", "B", "C"], "Purchase", 1),
            _ex(["X", "Y"], "Sales", 2),
            _ex(["A", "B"], "Purchase", 3),
        ]
    )
    out = retrieve(idx, ["A", "B", "C", "D"], k=5, per_class_cap=5)
    # Jaccard: ex1 = 3/4=0.75, ex3 = 2/4=0.5, ex2 = 0
    assert [e["row_id"] for e in out] == [1, 3, 2]


def test_per_class_cap_enforced():
    idx = build_index(
        [
            _ex(["A"], "Purchase", 1),
            _ex(["A"], "Purchase", 2),
            _ex(["A"], "Purchase", 3),
            _ex(["A"], "Sales", 4),
        ]
    )
    out = retrieve(idx, ["A"], k=5, per_class_cap=2)
    counts = {}
    for e in out:
        counts[e["label"]] = counts.get(e["label"], 0) + 1
    assert counts["Purchase"] == 2
    assert counts["Sales"] == 1
    assert len(out) == 3


def test_determinism_tiebreak_label_then_row():
    idx = build_index(
        [
            _ex(["A"], "Sales", 9),
            _ex(["A"], "Purchase", 7),
            _ex(["A"], "Purchase", 5),
        ]
    )
    first = retrieve(idx, ["A"], k=5, per_class_cap=5)
    second = retrieve(idx, ["A"], k=5, per_class_cap=5)
    assert first == second
    # Purchase (LABELS order earlier) before Sales; row_id asc within label.
    assert [(e["label"], e["row_id"]) for e in first] == [
        ("Purchase", 5),
        ("Purchase", 7),
        ("Sales", 9),
    ]


def test_leave_one_out_excludes_self():
    idx = build_index(
        [
            _ex(["A", "B"], "Purchase", 1),
            _ex(["A"], "Purchase", 2),
            _ex(["B"], "Sales", 3),
        ]
    )
    out = retrieve(idx, ["A", "B"], k=5, per_class_cap=5, exclude_row_id=1)
    assert all(e["row_id"] != 1 for e in out)
    assert len(out) == 2
    # Without exclusion the identical row ranks first.
    full = retrieve(idx, ["A", "B"], k=5, per_class_cap=5)
    assert full[0]["row_id"] == 1
