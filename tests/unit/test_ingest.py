"""Unit tests for ingest.read_excel header detection and profiling."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from vouch_engine.ingest import detect_header_row, read_excel


def _make_sheet(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["SHARMA TRADERS - SALES REGISTER"])  # title row (1 non-empty cell)
    ws.append([])  # blank line
    ws.append(["Seller", "Buyer", "Invoice No", "Date", "Amount"])  # header row
    ws.append(["Sharma Traders", "Nagpur Agro", "SI/001", "31/03/2026", 50000])
    ws.append(["Sharma Traders", "Pune Foods", "SI/002", "01/04/2026", 25000])
    wb.save(str(path))


def test_header_detection_with_title_and_blank(tmp_path: Path) -> None:
    xlsx = tmp_path / "sample.xlsx"
    _make_sheet(xlsx)
    result = read_excel(xlsx)
    assert result["headers"] == ["Seller", "Buyer", "Invoice No", "Date", "Amount"]
    assert result["profile"]["header_row"] == 3  # 1-based Excel row
    assert result["profile"]["n_rows"] == 2
    assert len(result["rows"]) == 2
    assert result["rows"][0]["Seller"] == "Sharma Traders"


def test_profile_fill_rate(tmp_path: Path) -> None:
    xlsx = tmp_path / "sample.xlsx"
    _make_sheet(xlsx)
    result = read_excel(xlsx)
    fill = result["profile"]["fill_rate"]
    assert fill["Seller"] == 1.0
    assert fill["Amount"] == 1.0
    assert set(fill.keys()) == set(result["headers"])


def test_detect_header_row_rule() -> None:
    rows = [
        ["TITLE ONLY", None, None],
        [None, None, None],
        ["Seller", "Buyer", "Invoice No", "Date"],
        ["a", "b", "c", 1],
    ]
    assert detect_header_row(rows) == 2


def test_detect_header_row_fallback() -> None:
    rows = [[None, None], ["a", "b"]]
    assert detect_header_row(rows) == 1
