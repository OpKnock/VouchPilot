"""Evidence-grounded exemplar retrieval over canonical voucher rows.

Chunking uses whitespace-separated words as a documented approximation
of token counting. Ranking uses TF-IDF cosine similarity from
scikit-learn (imported lazily); when sklearn is unavailable the module
falls back to token-Jaccard scoring and notes this on stderr.
"""

from __future__ import annotations

import sys

DEFAULT_CHUNK_SIZE = 512
DEFAULT_OVERLAP_PCT = 20


def chunk_text(text: str, size: int = 512, overlap_pct: int = 20) -> list[str]:
    """Split ``text`` into overlapping word chunks.

    Tokens are whitespace-separated words (``str.split``), an
    approximation of model token counting. Overlap is
    ``size * overlap_pct // 100`` tokens and step is ``size - overlap``
    (minimum 1). Empty or whitespace-only input returns ``[]``.
    """
    if type(size) is not int or size < 1:
        raise ValueError("size must be a positive integer")
    if type(overlap_pct) is not int or not 0 <= overlap_pct <= 100:
        raise ValueError("overlap_pct must be an integer in 0..100")
    tokens = text.split() if isinstance(text, str) else []
    if not tokens:
        return []
    overlap = size * overlap_pct // 100
    step = size - overlap
    if step < 1:
        step = 1
    chunks: list[str] = []
    for start in range(0, len(tokens), step):
        piece = tokens[start:start + size]
        if not piece:
            break
        chunks.append(" ".join(piece))
        if start + size >= len(tokens):
            break
    return chunks


def _iter_scalars(value: object) -> object:
    if value is None:
        return
    if isinstance(value, bool):
        yield str(value)
    elif isinstance(value, (str, int, float)):
        text = str(value).strip()
        if text:
            yield text
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_scalars(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_scalars(item)


def row_text(canonical_row: dict) -> str:
    """Render a canonical voucher row as space-joined evidence text.

    Joins narration, item descriptions, seller/buyer names, document
    numbers (invoice number, date), section values (refs/pay/money) and
    flattened raw values; skips missing or empty fields.
    """
    if not isinstance(canonical_row, dict):
        return ""
    parts: list[str] = []
    narration = canonical_row.get("narration")
    if isinstance(narration, str) and narration.strip():
        parts.append(narration.strip())
    items = canonical_row.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                desc = item.get("desc")
                if isinstance(desc, str) and desc.strip():
                    parts.append(desc.strip())
    for party_key in ("seller", "buyer"):
        party = canonical_row.get(party_key)
        if isinstance(party, dict):
            name = party.get("name")
            if isinstance(name, str) and name.strip():
                parts.append(name.strip())
    doc = canonical_row.get("doc")
    if isinstance(doc, dict):
        for key in ("invoice_number", "date"):
            value = doc.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                text = str(value).strip()
                if text:
                    parts.append(text)
    for section_key in ("refs", "pay", "money"):
        section = canonical_row.get(section_key)
        if isinstance(section, dict):
            parts.extend(_iter_scalars(section))
    raw = canonical_row.get("raw")
    if isinstance(raw, dict):
        parts.extend(_iter_scalars(raw))
    elif isinstance(raw, (str, int, float)) and not isinstance(raw, bool):
        text = str(raw).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def _exemplar_text(exemplar: dict) -> str:
    if not isinstance(exemplar, dict):
        return ""
    parts: list[str] = []
    text = exemplar.get("text")
    if isinstance(text, str) and text.strip():
        parts.append(text.strip())
    tags = exemplar.get("tags")
    if isinstance(tags, (list, tuple)):
        tag_text = " ".join(str(t).strip() for t in tags if str(t).strip())
        if tag_text:
            parts.append(tag_text)
    row = exemplar.get("row")
    if isinstance(row, dict):
        rendered = row_text(row)
        if rendered:
            parts.append(rendered)
    return " ".join(parts)


def _jaccard(a: str, b: str) -> float:
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a and not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _jaccard_scores(chunks: list[str], texts: list[str]) -> list[tuple[float, int]]:
    scored: list[tuple[float, int]] = []
    for index, text in enumerate(texts):
        best = 0.0
        for chunk in chunks:
            score = _jaccard(chunk, text)
            if score > best:
                best = score
        scored.append((best, index))
    return scored


def retrieve_exemplars(
    canonical_row: dict,
    k: int = 5,
    exemplars: list | None = None,
) -> list[dict]:
    """Retrieve the top-``k`` exemplars grounding a canonical row.

    The query text from :func:`row_text` is chunked with
    :func:`chunk_text`; each exemplar (``text`` and/or ``tags`` and/or
    ``row`` plus ``label``) is scored by TF-IDF cosine similarity with
    the maximum taken over query chunks. Returns
    ``[{"label", "score", "text"}]`` sorted by descending score.
    ``exemplars`` of None/empty and empty queries return ``[]``. When
    sklearn cannot be imported, token-Jaccard scoring is used instead
    with a note on stderr.
    """
    if not exemplars:
        return []
    if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        return []
    query = row_text(canonical_row)
    chunks = chunk_text(query)
    if not chunks:
        return []
    texts = [_exemplar_text(ex) for ex in exemplars]
    labels = [ex.get("label", "") if isinstance(ex, dict) else "" for ex in exemplars]
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        print("rag_evidence: sklearn unavailable; using token-Jaccard fallback",
              file=sys.stderr)
        scored = _jaccard_scores(chunks, texts)
    else:
        try:
            vectorizer = TfidfVectorizer()
            matrix = vectorizer.fit_transform(chunks + texts)
            chunk_mat = matrix[:len(chunks)]
            exemplar_mat = matrix[len(chunks):]
            sims = cosine_similarity(chunk_mat, exemplar_mat)
            best = sims.max(axis=0)
            scored = [(float(best[j]), j) for j in range(len(texts))]
        except ValueError:
            print("rag_evidence: empty vocabulary; using token-Jaccard fallback",
                  file=sys.stderr)
            scored = _jaccard_scores(chunks, texts)
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [{"label": labels[i], "score": score, "text": texts[i]}
            for score, i in scored[:k]]
