"""Vendor performance summary over sqlite3 (stdlib sqlite3 + pandas only)."""

import re
from datetime import datetime, timezone

import pandas as pd

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INVENTORY_TABLES = ("vendor_invoice", "purchases", "purchase_prices", "sales")

_VENDOR_COLS = ("seller", "vendor", "VendorName", "VendorNumber", "vendor_name")
_AMOUNT_COLS = ("total", "amount", "TotalSalesDollars", "Dollars", "sales")

_VENDOR_SUMMARY_SQL = """WITH FreightSummary AS (
    SELECT VendorNumber, SUM(Freight) AS FreightCost
    FROM vendor_invoice GROUP BY VendorNumber
),
PurchaseSummary AS (
    SELECT p.VendorNumber, p.VendorName, p.Brand, p.Description,
        p.PurchasePrice, pp.Price AS ActualPrice, pp.Volume,
        SUM(p.Quantity) AS TotalPurchaseQuantity,
        SUM(p.Dollars) AS TotalPurchaseDollars
    FROM purchases p
    JOIN purchase_prices pp ON p.Brand = pp.Brand
    WHERE p.PurchasePrice > 0
    GROUP BY p.VendorNumber, p.VendorName, p.Brand, p.Description,
        p.PurchasePrice, pp.Price, pp.Volume
),
SalesSummary AS (
    SELECT VendorNo, Brand,
        SUM(SalesQuantity) AS TotalSalesQuantity,
        SUM(SalesDollars) AS TotalSalesDollars,
        SUM(SalesPrice) AS TotalSalesPrice,
        SUM(ExciseTax) AS TotalExciseTax
    FROM sales GROUP BY VendorNo, Brand
)
SELECT ps.VendorNumber, ps.VendorName, ps.Brand, ps.Description,
    ps.PurchasePrice, ps.ActualPrice, ps.Volume,
    ps.TotalPurchaseQuantity, ps.TotalPurchaseDollars,
    ss.TotalSalesQuantity, ss.TotalSalesDollars, ss.TotalSalesPrice,
    ss.TotalExciseTax, fs.FreightCost
FROM PurchaseSummary ps
LEFT JOIN SalesSummary ss
    ON ps.VendorNumber = ss.VendorNo AND ps.Brand = ss.Brand
LEFT JOIN FreightSummary fs ON ps.VendorNumber = fs.VendorNumber
ORDER BY ps.TotalPurchaseDollars DESC"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _tables(conn) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r[0] for r in rows}


def _columns(conn, table: str) -> list:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({_q(table)})").fetchall()]


def _inventory_vendors(conn) -> list:
    df = pd.read_sql_query(_VENDOR_SUMMARY_SQL, conn).fillna(0)
    for col in (
        "TotalPurchaseQuantity",
        "TotalPurchaseDollars",
        "TotalSalesQuantity",
        "TotalSalesDollars",
        "FreightCost",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    grouped = df.groupby(["VendorNumber", "VendorName"], dropna=False, as_index=False).agg(
        total_purchase_dollars=("TotalPurchaseDollars", "sum"),
        total_sales_dollars=("TotalSalesDollars", "sum"),
        total_purchase_qty=("TotalPurchaseQuantity", "sum"),
        total_sales_qty=("TotalSalesQuantity", "sum"),
        freight_cost=("FreightCost", "sum"),
    )
    vendors = []
    for _, r in grouped.iterrows():
        sales = float(r["total_sales_dollars"])
        purchase = float(r["total_purchase_dollars"])
        bought = float(r["total_purchase_qty"])
        sold = float(r["total_sales_qty"])
        gross = sales - purchase
        vendors.append(
            {
                "vendor": r["VendorNumber"],
                "vendor_name": r["VendorName"],
                "total_purchase_dollars": purchase,
                "total_sales_dollars": sales,
                "freight_cost": float(r["freight_cost"]),
                "gross_profit": gross,
                "profit_margin": (gross / sales * 100.0) if sales else 0.0,
                "stock_turnover": (sold / bought) if bought else 0.0,
            }
        )
    vendors.sort(key=lambda v: v["total_purchase_dollars"], reverse=True)
    return vendors


def _bills_vendors(conn, table: str) -> list | None:
    by_lower = {c.lower(): c for c in _columns(conn, table)}
    vendor_col = next((by_lower[k.lower()] for k in _VENDOR_COLS if k.lower() in by_lower), None)
    if vendor_col is None:
        return None
    amount_col = next((by_lower[k.lower()] for k in _AMOUNT_COLS if k.lower() in by_lower), None)
    if amount_col is None:
        total_expr = "0.0 AS total"
    else:
        total_expr = f"COALESCE(SUM({_q(amount_col)}), 0.0) AS total"
    if "needs_review" in by_lower:
        nr = _q(by_lower["needs_review"])
        review_expr = f"COALESCE(AVG(CAST({nr} AS FLOAT)), 0.0) AS needs_review_rate"
    else:
        review_expr = "0.0 AS needs_review_rate"
    if "fraud_score" in by_lower:
        fs = _q(by_lower["fraud_score"])
        fraud_expr = (
            f"COALESCE(AVG(CASE WHEN CAST({fs} AS FLOAT) > 0.5 "
            "THEN 1.0 ELSE 0.0 END), 0.0) AS fraud_rate"
        )
    else:
        fraud_expr = "0.0 AS fraud_rate"
    sql = (
        f"SELECT {_q(vendor_col)} AS vendor, COUNT(*) AS rows, {total_expr}, "
        f"{review_expr}, {fraud_expr} FROM {_q(table)} "
        f"GROUP BY {_q(vendor_col)} ORDER BY total DESC"
    )
    df = pd.read_sql_query(sql, conn)
    vendors = []
    for _, r in df.iterrows():
        vendors.append(
            {
                "vendor": r["vendor"] if r["vendor"] is not None else "unknown",
                "rows": int(r["rows"]),
                "total": float(r["total"] or 0.0),
                "needs_review_rate": float(r["needs_review_rate"] or 0.0),
                "fraud_rate": float(r["fraud_rate"] or 0.0),
            }
        )
    return vendors


def vendor_summary(conn, table="bills") -> dict:
    """Summarise vendors from an inventory schema or a bills-style table.

    Never raises on missing schema; returns a warning dict when no
    compatible table is found.
    """
    try:
        tables = _tables(conn)
        if all(t in tables for t in _INVENTORY_TABLES):
            vendors = _inventory_vendors(conn)
            return {"generated_at": _now(), "vendors": vendors, "n_vendors": len(vendors)}
        if table and _TABLE_RE.match(str(table)) and table in tables:
            vendors = _bills_vendors(conn, table)
            if vendors is not None:
                return {"generated_at": _now(), "vendors": vendors, "n_vendors": len(vendors)}
        return {
            "generated_at": _now(),
            "vendors": [],
            "n_vendors": 0,
            "warning": "no-compatible-tables",
        }
    except Exception:
        return {
            "generated_at": _now(),
            "vendors": [],
            "n_vendors": 0,
            "warning": "no-compatible-tables",
        }
