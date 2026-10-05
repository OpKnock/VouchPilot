"""Real-world document intake: detect, extract, OCR-fallback, parse, export to XLSX.

Offline-only module: no network calls. Embedded PDF text is extracted first
(PyMuPDF); Tesseract OCR (hin+eng) runs only as a per-page fallback for pages
with no extractable text. Nothing is ever dropped silently: every input yields
at least one row (narration/text) in the output workbook.
"""

from __future__ import annotations

import csv
import os
import re
import shutil
from pathlib import Path

from PIL import Image

__all__ = [
    "IntakeError",
    "TESSDATA_DIR",
    "detect_type",
    "intake_to_xlsx",
    "ocr_image",
    "parse_invoice_fields",
    "pdf_page_to_image",
    "pdf_to_text",
    "tesseract_available",
]


class IntakeError(Exception):
    """Raised when intake cannot proceed (unsupported type, missing OCR binary, ...)."""


TESSDATA_DIR = Path(__file__).resolve().parents[2] / "tessdata"
if (TESSDATA_DIR / "hin.traineddata").exists() and "TESSDATA_PREFIX" not in os.environ:
    os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)

_TESSERACT_HINT = (
    "tesseract binary not found. Install: winget install UB-Mannheim.TesseractOCR, "
    "then download hin/mar/guj traineddata into tessdata/ "
    "(see specs/005-real-world-intake/spec.md)"
)

_DEFAULT_LANGS = ("hin", "eng", "mar", "guj")
MAX_IMAGE_PIXELS = 25_000_000
MAX_PDF_PAGES = 100
MAX_PDF_PAGE_PIXELS = 25_000_000

_XLSX_EXTS = frozenset({".xlsx", ".xlsm", ".xls"})
_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"})

_INVOICE_RE = re.compile(
    r"(?:INV|INVOICE|SI|PI|BE|SB|Bill|No)[\s:./-]*([A-Z0-9/\-]{3,})", re.IGNORECASE
)
_GSTIN_RE = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})")
_AMOUNT_RE = re.compile(r"\b(?:Rs|INR|Total|Amount)\b[^\d]{0,10}([\d,]*\d\.?\d*)", re.IGNORECASE)
_TAX_RE = re.compile(r"\b(CGST|SGST|IGST)\b[^\d]{0,6}([\d,]*\d\.?\d*)", re.IGNORECASE)
_SELLER_RE = re.compile(
    r"^\s*(Seller|विक्रेता|Supplier)\s*[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE
)
_BUYER_RE = re.compile(r"^\s*(Buyer|खरीदार|Customer)\s*[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def detect_type(path: str) -> str:
    """Map a file path to one of 'xlsx' | 'csv' | 'pdf' | 'image' by extension."""
    ext = Path(path).suffix.lower()
    if ext in _XLSX_EXTS:
        return "xlsx"
    if ext == ".csv":
        return "csv"
    if ext == ".pdf":
        return "pdf"
    if ext in _IMAGE_EXTS:
        return "image"
    raise IntakeError(f"unsupported file type: {path!r}")


def pdf_to_text(path: str) -> str:
    """Extract embedded text from a PDF with PyMuPDF; '' when nothing extractable."""
    import fitz

    doc = fitz.open(path)
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()


def pdf_page_to_image(path: str, page: int = 0, dpi: int = 200) -> Image.Image:
    """Render one PDF page to a PIL image via pypdfium2 (scale = dpi / 72)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(path)
    try:
        return doc[page].render(scale=dpi / 72).to_pil()
    finally:
        doc.close()


def tesseract_available() -> bool:
    """True when the external `tesseract` binary is on PATH."""
    return shutil.which("tesseract") is not None


def ocr_image(image: Image.Image, langs: tuple = ("hin", "eng"), psm: int = 6) -> str:
    """OCR a PIL image with Tesseract; narrow images (<800px wide) are upscaled 2x first."""
    if not tesseract_available():
        raise IntakeError(_TESSERACT_HINT)
    import pytesseract

    if image.width < 800:
        image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
    return pytesseract.image_to_string(image, lang="+".join(langs), config=f"--oem 1 --psm {psm}")


def _clean_amount(raw: str) -> str:
    return raw.strip().rstrip(".")


def parse_invoice_fields(text: str) -> dict:
    """Parse raw invoice text into a raw row dict; missing fields stay absent.

    Always includes ``currency`` (default ``'INR'``) plus ``narration`` (first
    3 non-empty lines) and ``items_desc`` (remaining lines) when text exists.
    """
    row: dict = {}
    invoice_hits = _INVOICE_RE.findall(text)
    if invoice_hits:
        digit_hits = [hit for hit in invoice_hits if any(ch.isdigit() for ch in hit)]
        row["invoice_number"] = (digit_hits[0] if digit_hits else invoice_hits[0]).strip()
    gstin = _GSTIN_RE.search(text)
    if gstin:
        row["gstin"] = gstin.group(0).strip()
    date = _DATE_RE.search(text)
    if date:
        row["date"] = date.group(1).strip()
    amounts = [_clean_amount(m) for m in _AMOUNT_RE.findall(text)]
    amounts = [m for m in amounts if m]
    if amounts:
        row["total"] = amounts[-1]
        if len(amounts) > 1:
            row["taxable"] = amounts[0]
    for kind, value in _TAX_RE.findall(text):
        row[kind.lower()] = _clean_amount(value)
    seller = _SELLER_RE.search(text)
    if seller:
        row["seller"] = seller.group(2).strip()
    buyer = _BUYER_RE.search(text)
    if buyer:
        row["buyer"] = buyer.group(2).strip()
    row["currency"] = "INR"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        row["narration"] = "\n".join(lines[:3])
        if len(lines) > 3:
            row["items_desc"] = "\n".join(lines[3:])
    return row


def _ensure_narration(row: dict, text: str) -> dict:
    """Guarantee the row carries narration/text so no input is dropped silently."""
    if not row.get("narration") and text.strip():
        row["narration"] = text.strip()[:2000]
    if "narration" not in row:
        row["narration"] = ""
    return row


def _write_rows(rows: list[dict], out_path: str) -> None:
    """Write rows to XLSX with headers = sorted union of parsed keys."""
    import openpyxl

    headers = sorted({key for row in rows for key in row}) or ["narration"]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "intake"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    wb.save(out_path)


def intake_to_xlsx(in_path: str, out_path: str,
                   langs: tuple = _DEFAULT_LANGS) -> dict:
    """Convert a document to XLSX; report ``{kind, pages, ocr_used, langs, rows}``.

    PDFs are read text-first with per-page OCR fallback (one row per page);
    images yield a single OCR row; xlsx/csv inputs are normalised through.
    """
    kind = detect_type(in_path)
    if Path(in_path).suffix.lower() == ".xls":
        raise IntakeError(
            "legacy .xls is recognized as Excel input but cannot be parsed by openpyxl; "
            "save it as .xlsx before intake"
        )
    langs_str = "+".join(langs)
    rows: list[dict] = []
    pages = 1
    ocr_used = False
    if kind == "pdf":
        import fitz

        doc = fitz.open(in_path)
        try:
            page_texts = [page.get_text() for page in doc]
        finally:
            doc.close()
        pages = len(page_texts)
        for index, text in enumerate(page_texts):
            if text.strip():
                rows.append(_ensure_narration(parse_invoice_fields(text), text))
            else:
                ocr_text = ocr_image(pdf_page_to_image(in_path, page=index), langs)
                ocr_used = True
                rows.append(_ensure_narration(parse_invoice_fields(ocr_text), ocr_text))
        if not rows:
            rows.append({"currency": "INR", "narration": ""})
    elif kind == "image":
        with Image.open(in_path) as img:
            img.load()
            ocr_text = ocr_image(img, langs)
        ocr_used = True
        rows.append(_ensure_narration(parse_invoice_fields(ocr_text), ocr_text))
    elif kind == "csv":
        with open(in_path, newline="", encoding="utf-8-sig") as handle:
            rows = [dict(r) for r in csv.DictReader(handle)]
        rows = [r for r in rows if any(str(v).strip() for v in r.values())]
        if not rows:
            rows = [{"currency": "INR", "narration": ""}]
    elif kind == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(in_path, read_only=True, data_only=True)
        grid = list(wb.active.values)
        wb.close()
        if grid and any(c is not None and str(c).strip() for c in grid[0]):
            headers_in = [str(c).strip() if c is not None else "" for c in grid[0]]
            rows = [{h: ("" if v is None else v) for h, v in zip(headers_in, r)} for r in grid[1:]]
            rows = [r for r in rows if any(str(v).strip() for v in r.values())]
        if not rows:
            rows = [{"currency": "INR", "narration": ""}]
    _write_rows(rows, out_path)
    return {"kind": kind, "pages": pages, "ocr_used": ocr_used, "langs": langs_str, "rows": len(rows)}
