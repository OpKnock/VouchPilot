"""VouchIQ Streamlit UI (US3): upload .xlsx, inspect predictions, download results."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import streamlit as st

from vouch_engine import baseline, evidence, ingest, normalise, perspective, scorer, validate
from vouch_engine.labels import LABEL_NAMES

st.set_page_config(page_title="VouchIQ", layout="wide")
st.title("VouchIQ — voucher classification (vertical slice)")

mode = st.sidebar.radio("Mode", ["Classify", "Review approvals"])

if mode == "Review approvals":
    st.header("Human approval gate")
    st.caption("Upload pending.json (from `agent review-template`), decide each queued row, "
               "download decisions.json, then run `agent run --gate file:decisions.json`.")
    pending_file = st.file_uploader("Upload pending.json", type=["json"])
    if pending_file is not None:
        pending = json.load(pending_file)
        queue = pending.get("queue", [])
        st.write(f"{len(queue)} rows need review from {pending.get('source', '?')}")
        decisions = []
        for item in queue:
            rid = item["row_id"]
            with st.expander(f"row {rid} | {item['invoice_number']} | "
                             f"model={item['model_label']} ({item['confidence']:.2f})"):
                st.write(f"reason={item['reason']} evidence={item['evidence'][:8]}")
                st.write(f"top_k={item['top_k'][:3]}")
                if item.get("narration"):
                    st.write(f"narr={item['narration'][:200]}")
                verdict = st.selectbox("verdict", ["approve", "override", "escalate"],
                                       key=f"v{rid}")
                label, note = None, ""
                if verdict == "override":
                    label = st.selectbox("correct label", LABEL_NAMES, key=f"l{rid}")
                    note = st.text_input("note", key=f"n{rid}")
                decisions.append({"row_id": rid, "verdict": verdict,
                                  "label": label, "note": note})
        st.download_button(
            "Download decisions.json",
            data=json.dumps({"decisions": decisions}, indent=1),
            file_name="decisions.json",
        )
    st.stop()

uploaded = st.file_uploader("Upload transactions .xlsx (voucher type missing)", type=["xlsx"])
scorer_choice = st.sidebar.selectbox("Scorer", ["keyword", "stub", "server"])
endpoint = st.sidebar.text_input("llama.cpp endpoint", "http://127.0.0.1:8080")

if uploaded is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name
    data = ingest.read_excel(tmp_path)
    mapping = normalise.map_columns(data["headers"], data["rows"])
    canonical = normalise.to_canonical(data["rows"], mapping)
    perspective.resolve(canonical)
    if scorer_choice == "server":
        scorer_obj = scorer.LlamaServerScorer(endpoint=endpoint)
    elif scorer_choice == "keyword":
        from vouch_engine.__main__ import _KeywordAdapter

        scorer_obj = _KeywordAdapter(baseline)
    else:
        scorer_obj = scorer.StubScorer()
    records = []
    for pos, crow in enumerate(canonical, start=1):
        tags, mask = evidence.extract(crow)
        label, conf, top_k = scorer_obj.predict(crow, tags, mask)
        invoice = (crow.get("doc") or {}).get("invoice_number") or f"ROW-{pos}"
        records.append(
            {
                "row_id": pos,
                "invoice_number": invoice,
                "voucher_type": label,
                "confidence": round(float(conf), 4),
                "needs_review": bool(float(conf) < 0.5),
                "top_k": top_k,
                "evidence": tags,
            }
        )
    preds = [validate.validate_prediction(rec) for rec in records]
    frame = pd.DataFrame([p.model_dump() for p in preds])
    st.dataframe(frame[["row_id", "invoice_number", "voucher_type", "confidence", "needs_review"]])
    st.download_button(
        "Download JSONL",
        data="\n".join(json.dumps(p.model_dump()) for p in preds),
        file_name="predictions.jsonl",
    )
    st.caption(f"n_rows={len(preds)} · scorer={scorer_choice} · offline, open-weight only")
