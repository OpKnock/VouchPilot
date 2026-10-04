# Feature Specification: Real-World Intake (005)

Sources: web research 2026-10-05 (Tesseract hin 99.18pct char-level, Apache-2.0; xldetect/messy-xlsx tactics ported natively to avoid new heavy deps; PyMuPDF/pypdfium2/Pillow already on machine).

## Stories
- US1 P1: messy .xlsx (merged cells, title rows, multi-sheet, Hindi headers) classifies end-to-end via messy pre-pass plus existing pipeline; no frozen module behavior changes.
- US2 P1: text PDF converts to rows without OCR (PyMuPDF/pypdf installed); scanned PDF/image OCRs via tesseract hin+eng when present, else fails LOUD with install instructions (never silent garbage).
- US3 P1: Hindi/Marathi headers map (messy-layer translation), Devanagari digits folded; Hindi narrations ride the multilingual SLM, keyword gaps surface as needs_review honestly.
- US4 P2: web Classify plus API /predict accept pdf/png/jpg; intake CLI converts documents to xlsx.

## Requirements
- intake.py: detect_type, pdf_to_text (PyMuPDF), pdf_page_to_image (pypdfium2), ocr_image (tesseract hin+eng+mar if binary else raise IntakError with setup steps), parse_invoice_fields(text)->raw row dict (invoice no, dates, GSTIN, amounts, tax lines, parties), intake_to_xlsx(in_path, out_path).
- messy.py: read_messy_xlsx(path, sheet=None|all)->{headers,rows,profile,report} with merged-fill (MergedCell parent rule), header-row search by alias-hit score (English+Hindi), decorative skip, empty drop, sheet picker (best header score) or concat with sheet tag.
- i18n.py: HI_ALIASES (Hindi/Marathi headers to English alias forms), fold_digits (Devanagari+Arabic-Indic to ASCII), HINDI_CUES (small narration keyword sets for evidence display only, not scoring).
- pyproject adds pymupdf, pypdfium2, Pillow, pytesseract (all already on machine; tesseract BINARY external, documented).
- CLI intake command (new module intake_cli wired additively), API /predict accepts pdf/png/jpg, pilot.py upload types extended.
- Tests: messy fixtures (merged/title/multi-sheet/Hindi) built with openpyxl in tmp; text-PDF generated with PyMuPDF; OCR tests run only when binary present else assert loud-error contract.

## Success Criteria
- SC-001: merged+title+multi-sheet fixture classifies with zero dropped rows.
- SC-002: Hindi-header fixture maps to same canonical keys as English twin.
- SC-003: text PDF converts to a valid Prediction row.
- SC-004: full suite green; frozen files behavior-identical (existing tests untouched and passing).

