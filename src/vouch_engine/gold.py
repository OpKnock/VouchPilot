"""Synthetic gold-set factory v1 (Team-C, US2).

Generates seeded, deterministic raw voucher rows with known labels covering
all 27 labels in :mod:`vouch_engine.labels`. Raw dicts use *aliased* headers
(Supplier / Bill No / Qty / ...) so the normalise stage gets exercised.

Contracts honoured: ``generate`` uses only ``random.Random(seed)`` (no global
randomness, no clock, no network). Rows are clean (no title-row quirks); the
CLI integration test adds quirks separately.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .labels import LABEL_NAMES

SELF_NAME = "Sharma Traders"
SELF_GSTIN = "27SHARM1234A1Z5"  # clearly synthetic, valid-format GSTIN

STATES = ["27", "29", "07", "33", "19", "24", "09"]
GST_SLABS = [5, 12, 18, 28]

SELLERS = [
    "Patel Enterprises",
    "Gupta Metals",
    "Nair Foods",
    "Khan Suppliers",
    "Reddy Agro Products",
    "Mehta Textiles",
    "Verma Electronics",
    "Das Machinery",
    "Kulkarni Tools",
    "Menon Packaging",
    "Agarwal Chemicals",
    "Bose Plastics",
]
BUYERS = [
    "Sharma Retail Mart",
    "Verma General Store",
    "Iyer Super Bazaar",
    "Qureshi Traders",
    "Pillai Distributors",
    "Jain Marketing",
    "Chopra Sales Corp",
    "Rao Enterprises",
    "Sinha Trading Co",
    "Mishra Stores",
]
FOREIGN_PARTIES = [
    "Gulf Star Trading LLC",
    "Hans Mueller GmbH",
    "Pacific Rim Supplies Pte",
    "Al Noor General Trading",
    "Sakura Sangyo KK",
]
GOODS = [
    "Steel rods 12mm",
    "Cotton fabric grey",
    "LED bulbs 9W",
    "Cement bags 50kg",
    "Copper wire coils",
    "Basmati rice 25kg bags",
    "Detergent cartons",
    "PVC pipes 110mm",
    "Aluminium sheets",
    "Mustard oil tins",
]
SERVICES = [
    "Office stationery supply",
    "Godown rent",
    "Power charges",
    "Internet and telephone",
    "Freight and cartage",
    "Printing and photocopy",
    "Repair and maintenance",
    "Professional fees",
]
EMPLOYEES = [
    "Ramesh Kumar",
    "Priya Nair",
    "Amit Verma",
    "Sunita Rao",
    "Vikram Singh",
    "Kavitha Reddy",
]
PAY_MODES = ["UPI", "NEFT", "RTGS", "Cash", "Cheque"]
FOREIGN_CCY = ["USD", "EUR", "AED"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"]

FULL_HEADER_ORDER = [
    "Supplier",
    "Vendor Name",
    "Supplier GSTIN",
    "Customer",
    "Customer GSTIN",
    "Bill No",
    "Invoice No",
    "Bill Date",
    "Invoice Date",
    "Item Desc",
    "Qty",
    "Quantity",
    "Rate",
    "Amount",
    "Taxable Value",
    "CGST",
    "SGST",
    "IGST",
    "Grand Total",
    "Currency",
    "Payment Mode",
    "UTR / Cheque",
    "Debit Ledger",
    "Credit Ledger",
    "Employee Name",
    "Pay Period",
    "Earnings",
    "Deductions",
    "Order No",
    "Receipt Note No",
    "Delivery Note No",
    "Narration",
]


def _gstin(rng: random.Random) -> str:
    """Valid-format, clearly synthetic GSTIN like 27ABCDE1234F1Z5."""
    letters = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5))
    digits = f"{rng.randint(1000, 9999)}"
    entity = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    branch = rng.choice("123456789ABCDEFGHJKLMNPQRSTUVWXYZ")
    check = rng.choice("123456789ABCDEFGHJKLMNPQRSTUVWXYZ")
    return f"{rng.choice(STATES)}{letters}{digits}{entity}{branch}Z{check}"


def _raw_date(rng: random.Random) -> str:
    from datetime import date

    day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    year = rng.choice([2024, 2025])
    day_s = f"{day:02d}"
    month_s = f"{month:02d}"
    fmt = rng.choice(DATE_FORMATS)
    if fmt == "%d/%m/%Y":
        return f"{day_s}/{month_s}/{year}"
    if fmt == "%Y-%m-%d":
        return f"{year}-{month_s}-{day_s}"
    if fmt == "%d-%m-%Y":
        return f"{day_s}-{month_s}-{year}"
    return date(year, month, day).strftime("%d %b %Y")


def _money_block(rng: random.Random, mode: str) -> dict:
    """Aliased money fields. mode in intra/inter/lump/none."""
    if mode == "none":
        return {}
    taxable = round(rng.uniform(1000, 200000), 2)
    if mode == "lump":
        return {"Taxable Value": taxable, "Grand Total": taxable}
    slab = rng.choice(GST_SLABS)
    tax = round(taxable * slab / 100, 2)
    if mode == "inter":
        return {"Taxable Value": taxable, "IGST": tax, "Grand Total": round(taxable + tax, 2)}
    half = round(tax / 2, 2)
    return {
        "Taxable Value": taxable,
        "CGST": half,
        "SGST": half,
        "IGST": 0.0,
        "Grand Total": round(taxable + half + half, 2),
    }


def _item_block(rng: random.Random, kind: str) -> dict:
    """Aliased item fields. kind in stock/service/qtyonly/none."""
    if kind == "none":
        return {}
    if kind == "service":
        desc = rng.choice(SERVICES)
        return {"Item Desc": desc, "Amount": round(rng.uniform(500, 50000), 2)}
    desc = rng.choice(GOODS)
    qty = rng.randint(1, 500)
    if kind == "qtyonly":
        return {"Item Desc": desc, "Qty": qty}
    rate = round(rng.uniform(10, 5000), 2)
    return {"Item Desc": desc, "Qty": qty, "Rate": rate, "Amount": round(qty * rate, 2)}


def _party_block(rng: random.Random, kind: str, domestic_pool: list) -> tuple:
    """Return (name, gstin-or-None) for a party kind: self/domestic/foreign/none."""
    if kind == "none":
        return None, None
    if kind == "self":
        return SELF_NAME, SELF_GSTIN
    if kind == "foreign":
        return rng.choice(FOREIGN_PARTIES), None
    return rng.choice(domestic_pool), _gstin(rng)


def _ref_no(rng: random.Random, seed: int, prefix: str) -> str:
    return f"{prefix}/{seed:03d}/{rng.randint(1, 9999):04d}"


def _utr(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(12))


def _period(rng: random.Random) -> str:
    return f"{rng.choice(MONTHS)}-{rng.choice([2024, 2025])}"


# Each spec composes party/money/item/pay/people/refs blocks plus narration
# cues. Order matches LABELS so generate() covers every label with n >= 27.
_SPECS = [
    {
        "label": "Purchase", "prefix": "PUR", "seller": "domestic", "buyer": "self",
        "currency": "INR", "money": "intra", "items": "stock", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Purchase of goods vide supplier bill {inv}; input GST claimed.",
            "Domestic purchase from {seller} against bill {inv}; goods inward.",
        ],
    },
    {
        "label": "Sales", "prefix": "SAL", "seller": "self", "buyer": "domestic",
        "currency": "INR", "money": "intra", "items": "stock", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Sales invoice {inv} raised on {buyer}; goods dispatched with e-way bill.",
            "Domestic sale to {buyer} vide bill {inv}; output GST charged.",
        ],
    },
    {
        "label": "Import", "prefix": "IMP", "seller": "foreign", "buyer": "self",
        "currency": "foreign", "money": "inter", "items": "stock", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Import vide bill of entry; CIF value with customs duty paid, IEC on "
            "record; IGST on imports for bill {inv}.",
            "Foreign purchase from {seller}; port clearance, CIF/FOB terms; "
            "customs duty debited for {inv}.",
        ],
    },
    {
        "label": "Export", "prefix": "EXP", "seller": "self", "buyer": "foreign",
        "currency": "foreign", "money": "inter", "items": "stock", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Export vide shipping bill; LUT filed, Incoterms FOB, port Nhava Sheva "
            "for invoice {inv}.",
            "Foreign sale to {buyer} in {currency}; shipping bill and bond "
            "particulars recorded for {inv}.",
        ],
    },
    {
        "label": "Purchase Return / Debit Note", "prefix": "DN", "seller": "domestic",
        "buyer": "self", "currency": "INR", "money": "intra", "items": "stock",
        "pay": False, "people": None, "refs": ["invoice"],
        "narrations": [
            "Debit note {inv} against purchase invoice {invoice}: defective goods "
            "returned to {seller}; purchase return.",
            "Purchase return to {seller}; debit note {inv} referencing invoice "
            "{invoice} for rate difference.",
        ],
    },
    {
        "label": "Sales Return / Credit Note", "prefix": "CN", "seller": "self",
        "buyer": "domestic", "currency": "INR", "money": "intra", "items": "stock",
        "pay": False, "people": None, "refs": ["invoice"],
        "narrations": [
            "Credit note {inv} against sales invoice {invoice}: goods returned by "
            "{buyer}; sales return accepted.",
            "Sales return from {buyer}; credit note {inv} issued referencing "
            "invoice {invoice}.",
        ],
    },
    {
        "label": "Rejection Out", "prefix": "REJO", "seller": "domestic", "buyer": "self",
        "currency": "INR", "money": "none", "items": "qtyonly", "pay": False,
        "people": None, "refs": ["receipt_note"],
        "narrations": [
            "Rejection out {inv} against receipt note {receipt_note}: quantity "
            "rejected at inward inspection, no commercial value.",
            "Goods rejected outward to {seller}; quantity-only memo {inv} "
            "referencing {receipt_note}.",
        ],
    },
    {
        "label": "Rejection In", "prefix": "REJI", "seller": "self", "buyer": "domestic",
        "currency": "INR", "money": "none", "items": "qtyonly", "pay": False,
        "people": None, "refs": ["delivery"],
        "narrations": [
            "Rejection in {inv} against delivery {delivery}: customer {buyer} "
            "returned goods for quality failure.",
            "Inward rejection memo {inv}; goods received back from {buyer} "
            "against delivery {delivery}.",
        ],
    },
    {
        "label": "Payment", "prefix": "PAY", "seller": "domestic", "buyer": "self",
        "currency": "INR", "money": "lump", "items": "none", "pay": True,
        "people": None, "refs": [],
        "narrations": [
            "Payment made to {seller} vide UTR {utr} against outstanding bills.",
            "Supplier payment {inv} via {paymode}; UTR {utr} recorded.",
        ],
    },
    {
        "label": "Receipt", "prefix": "REC", "seller": "self", "buyer": "domestic",
        "currency": "INR", "money": "lump", "items": "none", "pay": True,
        "people": None, "refs": [],
        "narrations": [
            "Receipt from customer {buyer} vide UTR {utr} against sales invoices.",
            "Customer receipt {inv} via {paymode}; UTR {utr} confirmed in bank.",
        ],
    },
    {
        "label": "Contra", "prefix": "CTR", "seller": "none", "buyer": "none",
        "currency": "INR", "money": "lump", "items": "none", "pay": "contra",
        "people": None, "refs": [],
        "narrations": [
            "Contra {inv}: cash deposited into HDFC Bank current account; "
            "cash-to-bank transfer.",
            "Bank-to-bank funds transfer {inv} between HDFC current and SBI "
            "overdraft accounts; contra entry.",
        ],
    },
    {
        "label": "Advance / Prepayment", "prefix": "ADV", "seller": "domestic",
        "buyer": "self", "currency": "INR", "money": "lump", "items": "none",
        "pay": True, "people": None, "refs": ["order"],
        "narrations": [
            "Advance paid to {seller} against purchase order {order}; no invoice "
            "settled yet; prepayment {inv}.",
            "Token advance {inv} to {seller} via {paymode}, UTR {utr}; order "
            "{order} pending execution.",
        ],
    },
    {
        "label": "Journal", "prefix": "JV", "seller": "none", "buyer": "none",
        "currency": "INR", "money": "lump", "items": "none", "pay": "journal",
        "people": None, "refs": [],
        "narrations": [
            "Journal adjustment {inv}: expense booked against payable; "
            "rectification of prior period error.",
            "Provision entry {inv}: audit fee provided; debit expense, credit "
            "provisions; journal voucher.",
        ],
    },
    {
        "label": "Expense", "prefix": "EXP", "seller": "domestic", "buyer": "self",
        "currency": "INR", "money": "intra", "items": "service", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Office expense: {service} for the month; overhead, not a stock "
            "purchase; bill {inv}.",
            "Expense voucher {inv} from {seller} towards {service}; booked to "
            "indirect expenses.",
        ],
    },
    {
        "label": "Other / Miscellaneous", "prefix": "MISC", "seller": "none",
        "buyer": "none", "currency": "INR", "money": "lump", "items": "none",
        "pay": False, "people": None, "refs": [],
        "narrations": [
            "Miscellaneous rounding adjustment {inv} carried for review; "
            "unclassified small entry.",
            "Other entry {inv}: unallocated difference parked pending "
            "clarification.",
        ],
    },
    {
        "label": "Salary / Payroll", "prefix": "PAYR", "seller": "none", "buyer": "none",
        "currency": "INR", "money": "lump", "items": "none", "pay": False,
        "people": "payroll", "refs": [],
        "narrations": [
            "Salary payroll for {employee} for {period}: earnings with PF and ESI "
            "deductions; voucher {inv}.",
            "Payroll run {period}: net salary payable to {employee} after "
            "deductions; voucher {inv}.",
        ],
    },
    {
        "label": "Attendance", "prefix": "ATT", "seller": "none", "buyer": "none",
        "currency": "INR", "money": "none", "items": "none", "pay": False,
        "people": "attendance", "refs": [],
        "narrations": [
            "Attendance of {employee} for {period}: present 26 days, weekly off 4, "
            "leave 1.",
            "Muster entry {inv}: {employee} attendance marked for {period}.",
        ],
    },
    {
        "label": "Purchase Order", "prefix": "PO", "seller": "domestic", "buyer": "self",
        "currency": "INR", "money": "none", "items": "stock", "pay": False,
        "people": None, "refs": ["order"],
        "narrations": [
            "Purchase order {inv} placed on {seller} for supply of goods; "
            "delivery against order {order} pending.",
            "Order confirmation {order}: purchase order {inv} issued to {seller}.",
        ],
    },
    {
        "label": "Sales Order", "prefix": "SO", "seller": "self", "buyer": "domestic",
        "currency": "INR", "money": "none", "items": "stock", "pay": False,
        "people": None, "refs": ["order"],
        "narrations": [
            "Sales order {inv} received from {buyer}; dispatch pending against "
            "order {order}.",
            "Order booking {inv}: sales order from {buyer} confirmed.",
        ],
    },
    {
        "label": "Receipt Note", "prefix": "GRN", "seller": "domestic", "buyer": "self",
        "currency": "INR", "money": "none", "items": "stock", "pay": False,
        "people": None, "refs": ["receipt_note", "order"],
        "narrations": [
            "Goods receipt note {inv}: material received from {seller} against "
            "order {order}; GRN {receipt_note} quality check pending.",
            "Receipt note {inv} recording inward goods; purchase billing to follow.",
        ],
    },
    {
        "label": "Delivery Note", "prefix": "DC", "seller": "self", "buyer": "domestic",
        "currency": "INR", "money": "none", "items": "stock", "pay": False,
        "people": None, "refs": ["delivery"],
        "narrations": [
            "Delivery note cum challan {inv}: goods dispatched to {buyer}; "
            "delivery {delivery} billing later.",
            "Delivery challan {inv} for {buyer}; transporter copy enclosed.",
        ],
    },
    {
        "label": "Material In", "prefix": "MIN", "seller": "domestic", "buyer": "self",
        "currency": "INR", "money": "none", "items": "qtyonly", "pay": False,
        "people": None, "refs": ["receipt_note"],
        "narrations": [
            "Material inward {inv}: goods taken into stores against receipt "
            "{receipt_note}.",
            "Stores receipt {inv} from {seller}; inward quantity recorded.",
        ],
    },
    {
        "label": "Material Out", "prefix": "MOUT", "seller": "self", "buyer": "none",
        "currency": "INR", "money": "none", "items": "qtyonly", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Material outward {inv}: goods issued from stores to production floor.",
            "Stores issue {inv}: quantity drawn for job consumption.",
        ],
    },
    {
        "label": "Job Work In Order", "prefix": "JWIN", "seller": "domestic",
        "buyer": "self", "currency": "INR", "money": "none", "items": "qtyonly",
        "pay": False, "people": None, "refs": ["order"],
        "narrations": [
            "Job work inward order {inv} from {seller}: labour job received for "
            "processing against order {order}.",
            "Inward job challan {inv}: material received for job work.",
        ],
    },
    {
        "label": "Job Work Out Order", "prefix": "JWOUT", "seller": "self",
        "buyer": "domestic", "currency": "INR", "money": "none", "items": "qtyonly",
        "pay": False, "people": None, "refs": ["order"],
        "narrations": [
            "Job work outward order {inv} to {buyer}: material sent out for job "
            "processing against order {order}.",
            "Outward job challan {inv}: goods sent to {buyer} for labour work.",
        ],
    },
    {
        "label": "Stock Journal", "prefix": "SJ", "seller": "none", "buyer": "none",
        "currency": "INR", "money": "none", "items": "qtyonly", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Stock journal {inv}: transfer of goods from godown A to godown B.",
            "Stock transfer voucher {inv}: inter-godown movement recorded.",
        ],
    },
    {
        "label": "Physical Stock", "prefix": "STK", "seller": "none", "buyer": "none",
        "currency": "INR", "money": "none", "items": "qtyonly", "pay": False,
        "people": None, "refs": [],
        "narrations": [
            "Physical stock verification {inv}: counted quantity recorded; "
            "difference adjusted.",
            "Stock count sheet {inv}: physical quantity confirmed for the item.",
        ],
    },
]


def _build_row(rng: random.Random, spec: dict, inv_no: str, seed: int) -> dict:
    raw: dict = {}
    seller_name, seller_gstin = _party_block(rng, spec["seller"], SELLERS)
    buyer_name, buyer_gstin = _party_block(rng, spec["buyer"], BUYERS)
    if seller_name is not None:
        raw["Supplier"] = seller_name
    if seller_gstin is not None:
        raw["Supplier GSTIN"] = seller_gstin
    if buyer_name is not None:
        raw["Customer"] = buyer_name
    if buyer_gstin is not None:
        raw["Customer GSTIN"] = buyer_gstin
    raw["Bill No"] = inv_no
    raw["Bill Date"] = _raw_date(rng)
    raw.update(_item_block(rng, spec["items"]))
    raw.update(_money_block(rng, spec["money"]))
    currency = rng.choice(FOREIGN_CCY) if spec["currency"] == "foreign" else "INR"
    raw["Currency"] = currency
    refs: dict = {}
    for kind in spec["refs"]:
        prefix = {"order": "PO", "receipt_note": "GRN", "delivery": "DC",
                  "invoice": "INV"}[kind]
        refs[kind] = _ref_no(rng, seed, prefix)
        header = {"order": "Order No", "receipt_note": "Receipt Note No",
                  "delivery": "Delivery Note No", "invoice": "Order No"}[kind]
        if kind == "invoice":
            # debit/credit notes reference the original invoice in narration;
            # keep the column holding the original invoice number.
            raw["Order No"] = refs[kind]
        else:
            raw[header] = refs[kind]
    utr = _utr(rng)
    paymode = rng.choice(PAY_MODES)
    if spec["pay"] is True:
        raw["Payment Mode"] = paymode
        raw["UTR / Cheque"] = utr
        raw["Debit Ledger"] = f"Supplier - {seller_name or SELF_NAME}"
        raw["Credit Ledger"] = "HDFC Bank Current Account"
        if spec["label"] == "Receipt":
            raw["Debit Ledger"] = "HDFC Bank Current Account"
            raw["Credit Ledger"] = f"Customer - {buyer_name or SELF_NAME}"
    elif spec["pay"] == "contra":
        raw["Payment Mode"] = rng.choice(["Cash", "NEFT"])
        raw["Debit Ledger"] = "HDFC Bank Current Account"
        raw["Credit Ledger"] = "Cash Account"
    elif spec["pay"] == "journal":
        raw["Debit Ledger"] = rng.choice(["Audit Fee Expense", "Rent Expense"])
        raw["Credit Ledger"] = rng.choice(["Provisions Account", "Sundry Creditors"])
        raw["Amount"] = raw.get("Taxable Value", round(rng.uniform(500, 50000), 2))
    if spec["people"] == "payroll":
        employee = rng.choice(EMPLOYEES)
        period = _period(rng)
        earnings = round(rng.uniform(15000, 120000), 2)
        deductions = round(earnings * rng.uniform(0.05, 0.2), 2)
        raw["Employee Name"] = employee
        raw["Pay Period"] = period
        raw["Earnings"] = earnings
        raw["Deductions"] = deductions
        raw["Grand Total"] = round(earnings - deductions, 2)
        refs.setdefault("employee", employee)
        refs.setdefault("period", period)
    elif spec["people"] == "attendance":
        employee = rng.choice(EMPLOYEES)
        period = _period(rng)
        raw["Employee Name"] = employee
        raw["Pay Period"] = period
        refs.setdefault("employee", employee)
        refs.setdefault("period", period)
    item_desc = raw.get("Item Desc", rng.choice(SERVICES))
    narration = rng.choice(spec["narrations"]).format(
        inv=inv_no,
        seller=seller_name or SELF_NAME,
        buyer=buyer_name or SELF_NAME,
        utr=utr,
        paymode=paymode,
        currency=currency,
        employee=refs.get("employee", rng.choice(EMPLOYEES)),
        period=refs.get("period", _period(rng)),
        service=item_desc,
        **{k: v for k, v in refs.items() if k in ("order", "receipt_note", "delivery",
                                                 "invoice")},
    )
    raw["Narration"] = narration
    # Vary a few header aliases per row so normalise is exercised.
    if "Supplier" in raw and rng.random() < 0.3:
        raw["Vendor Name"] = raw.pop("Supplier")
    if "Bill No" in raw and rng.random() < 0.3:
        raw["Invoice No"] = raw.pop("Bill No")
    if "Bill Date" in raw and rng.random() < 0.3:
        raw["Invoice Date"] = raw.pop("Bill Date")
    if "Qty" in raw and rng.random() < 0.25:
        raw["Quantity"] = raw.pop("Qty")
    return raw


def _invoice_of(raw: dict) -> str:
    for key in ("Bill No", "Invoice No"):
        value = raw.get(key)
        if value:
            return str(value)
    return ""


def generate(n: int, seed: int) -> list:
    """Return ``[(raw_row_dict, label), ...]`` of length ``n``.

    The first 27 rows cover every label once (in LABELS order); remaining rows
    sample labels uniformly via ``random.Random(seed)``. Output order is
    shuffled deterministically so labels are spread through the sheet.
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    rng = random.Random(seed)
    pairs = []
    for i in range(n):
        spec = _SPECS[i] if i < len(_SPECS) else _SPECS[rng.randrange(len(_SPECS))]
        inv_no = f"{spec['prefix']}/{seed:03d}/{i + 1:04d}"
        pairs.append((_build_row(rng, spec, inv_no, seed), spec["label"]))
    rng.shuffle(pairs)
    return pairs


def build_dataset(n: int, seed: int, out_prefix: str) -> dict:
    """Write ``{prefix}.xlsx`` (raw aliased headers) plus labels JSON.

    Labels file holds ``[{row_id, invoice_number, voucher_type}]``.
    """
    pairs = generate(n, seed)
    headers = [h for h in FULL_HEADER_ORDER if any(h in raw for raw, _ in pairs)]
    from openpyxl import Workbook

    out_prefix = str(out_prefix)
    parent = Path(out_prefix).parent
    if str(parent) and str(parent) != ".":
        parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Vouchers"
    sheet.append(headers)
    for raw, _ in pairs:
        sheet.append([raw.get(h, "") if raw.get(h) is not None else "" for h in headers])
    xlsx_path = f"{out_prefix}.xlsx"
    workbook.save(xlsx_path)
    labels = [
        {"row_id": i + 1, "invoice_number": _invoice_of(raw), "voucher_type": label}
        for i, (raw, label) in enumerate(pairs)
    ]
    labels_path = f"{out_prefix}_labels.json"
    Path(labels_path).write_text(json.dumps(labels, indent=2), encoding="utf-8")
    return {"xlsx": xlsx_path, "labels": labels_path, "n_rows": len(pairs)}


assert len(_SPECS) == 27  # keep factory and taxonomy in lockstep
assert [s["label"] for s in _SPECS] == LABEL_NAMES
