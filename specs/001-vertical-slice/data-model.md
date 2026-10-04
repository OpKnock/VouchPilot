# Data Model: 001-vertical-slice

**Date**: 2026-10-03 | **Spec**: `spec.md`

`CanonicalRow` and `EvidenceTags` are plain dicts/lists (flexible for unknown schema); only `Prediction` is Pydantic-validated (output contract).

## CanonicalRow (dict)

| Key | Type | Notes |
|---|---|---|
| `row_id` | int | 1-based source row |
| `seller` | {name, gstin} | None values where absent |
| `buyer` | {name, gstin} | None values where absent |
| `doc` | {invoice_number, date} | date ISO or None |
| `items` | list[{desc, qty, rate, amount}] | empty where absent |
| `money` | {taxable, cgst, sgst, igst, total, currency} | numbers or None; currency default INR |
| `pay` | {mode, utr, debit, credit} | ledger names for Contra detection |
| `people` | {employee, period, earnings, deductions} | payroll/attendance fields |
| `refs` | {invoice, order, receipt_note, delivery} | cross-document references |
| `narration` | str | free text, all languages kept as-is |
| `raw` | dict | unmapped columns, shown to model |
| `presence` | dict[str, bool] | which families are present |
| `perspective` | seller \| buyer \| neither \| unknown | set by perspective resolver |
| `self_entity` | str \| None | file-level reporting entity |

## EvidenceTags

`tags: list[str]` from families PERSPECTIVE, DOC_SIGN, HAS_ITEMS, QTY_ONLY, NO_INVOICE_NO, TAX, TAX_ARITHMETIC, PAY_MODE, LEDGER_PAIR, HAS_UTR_OR_CHEQUE, CURRENCY, HAS_CUSTOMS_FIELDS, HAS_SHIPPING_BILL, EMPLOYEE_FIELDS, PAY_PERIOD, DEDUCTIONS, ATTENDANCE_FIELDS, REFS_*, CUE, NO_PARTY, NO_ITEMS. `mask: dict[label, float]` penalties in (0, 1], 1.0 = fully feasible.

## Prediction (Pydantic, see contracts/prediction.schema.json)

`row_id, invoice_number, voucher_type` (must be one of the 27 LABELS), `confidence` in [0,1], `needs_review` bool, `top_k` list[[label, prob]] (sums ≈ 1), `evidence` list[str].

## EvalReport (dict, JSON-serialisable)

`accuracy, macro_f1, micro_f1, weighted_f1, per_class[{label, precision, recall, f1, support}], confusion_matrix{labels, matrix}, baseline_delta{A0, A1}, latency{mean_s, p95_s}, n_rows, seed`.
