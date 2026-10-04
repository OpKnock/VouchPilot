"""Taxonomy invariants: 27 labels, 7 groups A-G, unique member codes."""

from __future__ import annotations

from vouch_engine.labels import BY_NAME, GROUPS, LABELS


def test_27_labels() -> None:
    assert len(LABELS) == 27
    assert len(BY_NAME) == 27


def test_7_groups_a_to_g() -> None:
    assert set(GROUPS.keys()) == {"A", "B", "C", "D", "E", "F", "G"}
    assert len(GROUPS) == 7


def test_member_codes_unique_and_grouped() -> None:
    codes = [label["code"] for label in LABELS]
    assert len(set(codes)) == 27
    for label in LABELS:
        assert label["group"] in GROUPS
        assert label["name"]
        assert label["code"].startswith(label["group"])


def test_expected_group_sizes() -> None:
    from collections import Counter

    counts = Counter(label["group"] for label in LABELS)
    assert counts == {"A": 4, "B": 4, "C": 4, "D": 3, "E": 2, "F": 8, "G": 2}
