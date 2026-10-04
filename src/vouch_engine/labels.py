"""27-label voucher taxonomy, hierarchy, and precedence policy v1 (README 4.3/4.4)."""

GROUPS = {
    "A": "Trade invoices",
    "B": "Returns and rejections",
    "C": "Money movement",
    "D": "Non-cash ledger and miscellaneous",
    "E": "People",
    "F": "Orders and movement documents",
    "G": "Stock accounting",
}

LABELS = [
    {"code": "A1", "group": "A", "name": "Purchase"},
    {"code": "A2", "group": "A", "name": "Sales"},
    {"code": "A3", "group": "A", "name": "Import"},
    {"code": "A4", "group": "A", "name": "Export"},
    {"code": "B1", "group": "B", "name": "Purchase Return / Debit Note"},
    {"code": "B2", "group": "B", "name": "Sales Return / Credit Note"},
    {"code": "B3", "group": "B", "name": "Rejection Out"},
    {"code": "B4", "group": "B", "name": "Rejection In"},
    {"code": "C1", "group": "C", "name": "Payment"},
    {"code": "C2", "group": "C", "name": "Receipt"},
    {"code": "C3", "group": "C", "name": "Contra"},
    {"code": "C4", "group": "C", "name": "Advance / Prepayment"},
    {"code": "D1", "group": "D", "name": "Journal"},
    {"code": "D2", "group": "D", "name": "Expense"},
    {"code": "D3", "group": "D", "name": "Other / Miscellaneous"},
    {"code": "E1", "group": "E", "name": "Salary / Payroll"},
    {"code": "E2", "group": "E", "name": "Attendance"},
    {"code": "F1", "group": "F", "name": "Purchase Order"},
    {"code": "F2", "group": "F", "name": "Sales Order"},
    {"code": "F3", "group": "F", "name": "Receipt Note"},
    {"code": "F4", "group": "F", "name": "Delivery Note"},
    {"code": "F5", "group": "F", "name": "Material In"},
    {"code": "F6", "group": "F", "name": "Material Out"},
    {"code": "F7", "group": "F", "name": "Job Work In Order"},
    {"code": "F8", "group": "F", "name": "Job Work Out Order"},
    {"code": "G1", "group": "G", "name": "Stock Journal"},
    {"code": "G2", "group": "G", "name": "Physical Stock"},
]

LABEL_NAMES = [label["name"] for label in LABELS]
BY_NAME = {label["name"]: label for label in LABELS}
BY_CODE = {label["code"]: label for label in LABELS}

PRECEDENCE_V1 = {
    "Import_over_Purchase": "specific wins on foreign supplier/currency, bill of entry, port, customs duty, IEC, CIF/FOB",
    "Export_over_Sales": "specific wins on foreign customer/currency, shipping bill, LUT/bond, port, Incoterms",
    "Expense_over_Purchase": "overhead/service wins when no stock items exist",
    "Advance_over_Payment_Receipt": "advance wins when money moves without a settling invoice",
    "DebitNote_over_RejectionOut": "debit note is value-bearing with invoice ref; rejection out is quantity-only with receipt-note ref",
    "Other_last_resort": "only when genuinely the top label; low confidence raises needs_review instead",
}
