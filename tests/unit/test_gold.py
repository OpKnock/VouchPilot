"""Unit tests for the synthetic gold-set factory (Team-C, US2)."""

import json
import re

from vouch_engine import gold
from vouch_engine.labels import LABEL_NAMES

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def test_covers_all_27_labels():
    pairs = gold.generate(270, 7)
    assert len(pairs) == 270
    got = {label for _, label in pairs}
    assert got == set(LABEL_NAMES)


def test_seed_reproducibility():
    first = gold.generate(100, 42)
    second = gold.generate(100, 42)
    assert len(first) == len(second) == 100
    for (raw_a, label_a), (raw_b, label_b) in zip(first, second):
        assert label_a == label_b
        assert raw_a == raw_b


def test_different_seeds_differ():
    first = gold.generate(60, 1)
    second = gold.generate(60, 2)
    assert [(r, lab) for r, lab in first] != [(r, lab) for r, lab in second]


def test_rows_look_real_and_varied():
    pairs = gold.generate(60, 3)
    invoices = set()
    gstins_seen = 0
    for raw, label in pairs:
        assert label in LABEL_NAMES
        inv = raw.get("Bill No", raw.get("Invoice No", ""))
        assert inv, "every row needs a voucher number"
        invoices.add(inv)
        for key in ("Supplier GSTIN", "Customer GSTIN"):
            if raw.get(key):
                assert GSTIN_RE.match(str(raw[key])), raw[key]
                gstins_seen += 1
        assert raw.get("Narration"), "every row needs a narration cue"
    assert len(invoices) == 60
    assert gstins_seen > 0
    bill_keys = {k for raw, _ in pairs for k in raw if k in ("Bill No", "Invoice No")}
    assert bill_keys == {"Bill No", "Invoice No"}, "header aliases must vary"


def test_build_dataset_writes_files(tmp_path):
    prefix = str(tmp_path / "gold")
    result = gold.build_dataset(30, 9, prefix)
    assert result["n_rows"] == 30
    labels = json.loads(open(result["labels"], encoding="utf-8").read())
    assert len(labels) == 30
    assert all(set(e) == {"row_id", "invoice_number", "voucher_type"} for e in labels)
    assert {e["voucher_type"] for e in labels} == set(LABEL_NAMES)
    assert all(e["invoice_number"] for e in labels)
