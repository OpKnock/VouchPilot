# VouchPilot dashboard: the whole product on one screen. Run: streamlit run pilot.py
# Or one command for everything: powershell -ExecutionPolicy Bypass -File start-vouchpilot.ps1
import concurrent.futures
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import streamlit as st

from vouch_engine import baseline, evidence, ingest, normalise, perspective, scorer, validate
from vouch_engine import evaluate as eval_mod
from vouch_engine import pilot_logic
from vouch_engine.labels import LABEL_NAMES

try:
    from extensions import fraud_firewall as _firewall
except Exception:
    _firewall = None

try:
    from extensions.vouchpilot_scorer import VouchPilotScorer
except Exception:
    VouchPilotScorer = None

try:
    from vouch_engine.challenger import recheck as _recheck
except Exception:
    _recheck = None

st.set_page_config(page_title="VouchPilot", layout="wide", page_icon="🧾")
st.markdown(
    "<style>"
    ".stApp { background: #f1f5f9; }"
    "section[data-testid='stSidebar'] { background: #0f172a; }"
    "section[data-testid='stSidebar'] * { color: #e2e8f0 !important; }"
    ".kpi { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;"
    " padding: 14px 16px; }"
    ".kpi .v { font-size: 26px; font-weight: 700; color: #0f172a; }"
    ".kpi .l { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }"
    ".kpi.good .v { color: #059669; } .kpi.warn .v { color: #d97706; } .kpi.bad .v { color: #dc2626; }"
    ".card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 14px; }"
    ".stButton>button[kind='primary'] { background: #10b981; border-color: #10b981; }"
    ".pill { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }"
    ".pill-auto { background: #d1fae5; color: #065f46; }"
    ".pill-need { background: #fef3c7; color: #92400e; }"
    "h1, h2, h3 { color: #0f172a; }"
    "</style>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## 🧾 VouchPilot")
    st.caption("Offline voucher classification")
    tab = st.radio("Go to", ["Classify", "Review", "Dashboard", "System"])
    st.divider()
    scorer_name = st.selectbox("Scorer", ["keyword", "vouchpilot", "stub", "server"])
    endpoint = st.text_input("llama.cpp endpoint", "http://127.0.0.1:8080")
    workers = st.number_input("Workers", min_value=1, max_value=8, value=1, step=1)
    use_challenger = st.checkbox("Challenge uncertain rows", value=True)
    try:
        import urllib.request as _ur
        _ur.urlopen("http://127.0.0.1:8080/health", timeout=3)
        st.success("● server online")
    except Exception:
        st.caption("○ server offline (keyword/stub need none)")


def _make_scorer():
    if scorer_name == "server":
        return scorer.LlamaServerScorer(endpoint=endpoint)
    if scorer_name == "keyword":
        from vouch_engine.__main__ import _KeywordAdapter
        return _KeywordAdapter(baseline)
    if scorer_name == "vouchpilot" and VouchPilotScorer is not None:
        return VouchPilotScorer(base="keyword")
    return scorer.StubScorer()


def _run_pipeline(xlsx_bytes, progress_cb=None, filename="upload.xlsx"):
    lower = filename.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(xlsx_bytes)
        path = tmp.name
    if lower.endswith((".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")):
        from vouch_engine import intake as intake_mod

        stamped = path + ("_src.pdf" if lower.endswith(".pdf") else "_src.png")
        os.rename(path, stamped)
        converted = stamped + ".rows.xlsx"
        rep = intake_mod.intake_to_xlsx(stamped, converted)
        if rep.get("ocr_used"):
            st.warning("Scanned document: text came from OCR — verify amounts before filing.")
        path = converted
    data = ingest.read_excel(path)
    mapping = normalise.map_columns(data["headers"], data["rows"])
    canonical = normalise.to_canonical(data["rows"], mapping)
    perspective.resolve(canonical)
    scorer_obj = _make_scorer()
    def one(i):
        crow = canonical[i]
        tags, mask = evidence.extract(crow)
        label, conf, top_k = scorer_obj.predict(crow, tags, mask)
        audit = dict(getattr(scorer_obj, "last", {}) or {})
        invoice = (crow.get("doc") or {}).get("invoice_number") or "ROW-%d" % (i + 1,)
        return {"crow": crow, "tags": tags, "label": label, "conf": float(conf),
                "top_k": top_k, "invoice": invoice, "audit": audit}
    states = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(workers)) as pool:
        for pos, st_ in enumerate(pool.map(one, range(len(canonical))), start=1):
            states.append(st_)
            if progress_cb is not None and (pos % 10 == 0 or pos == len(canonical)):
                progress_cb(pos / len(canonical))
    if use_challenger and hasattr(scorer_obj, "_complete") and _recheck is not None:
        for st_ in states:
            tk = st_["top_k"]
            if isinstance(tk, list) and len(tk) >= 2:
                margin = float(tk[0][1]) - float(tk[1][1])
                if margin < 0.15:
                    try:
                        winner, cc = _recheck(st_["invoice"], st_["tags"],
                                             tk[0][0], tk[1][0], scorer_obj._complete)
                        st_["label"], st_["conf"] = winner, float(cc)
                        if tk and tk[0][0] == winner:
                            tk[0][1] = float(cc)
                        st_["tags"] = st_["tags"] + ["CHALLENGED"]
                    except Exception:
                        st_["tags"] = st_["tags"] + ["CHALLENGE-SKIPPED"]
    records = []
    for pos, st_ in enumerate(states, start=1):
        records.append({"row_id": pos, "invoice_number": st_["invoice"],
                        "voucher_type": st_["label"], "confidence": round(st_["conf"], 4),
                        "needs_review": bool(st_["conf"] < 0.5), "top_k": st_["top_k"],
                        "evidence": st_["tags"], "_audit": st_["audit"]})
    preds = [validate.validate_prediction(
        {k: v for k, v in rec.items() if not k.startswith("_")}) for rec in records]
    return [p.model_dump() for p in preds], [r["_audit"] for r in records]


def kpi_cards(preds):
    n = len(preds)
    nr = sum(1 for p in preds if p["needs_review"])
    cols = st.columns(4)
    cards = [("Rows", str(n), ""), ("Needs review", str(nr), "warn" if nr else "good"),
             ("Auto-classified", str(n - nr), "good"),
             ("Mean confidence", "%.3f" % (sum(p["confidence"] for p in preds) / n,) if n else "-", "")]
    for col, (label, val, tone) in zip(cols, cards):
        col.markdown('<div class="kpi %s"><div class="l">%s</div><div class="v">%s</div></div>'
                     % (tone, label, val), unsafe_allow_html=True)


if tab == "Classify":
    c1, c2 = st.columns([3, 1])
    c1.header("Classify")
    up = st.file_uploader("Drop an .xlsx, .pdf or photo of a bill (voucher type missing)",
                          type=["xlsx", "pdf", "png", "jpg", "jpeg"])
    run = c2.button("▶ Run classification", type="primary", use_container_width=True)
    if up is not None and run:
        bar = st.progress(0.0, "Scoring rows…")
        try:
            preds, audits = _run_pipeline(up.read(), bar.progress, up.name)
        except Exception as exc:
            st.error("Classification failed: %s" % (exc,))
            st.stop()
        st.session_state["preds"] = preds
        st.session_state["audits"] = audits
        bar.progress(1.0)
    preds = st.session_state.get("preds", [])
    if preds:
        kpi_cards(preds)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Predictions")
        frame = pd.DataFrame(preds)
        frame["status"] = frame["needs_review"].map(lambda v: "Needs review" if v else "Auto")
        st.dataframe(frame[["row_id", "invoice_number", "voucher_type", "confidence", "status"]],
                     column_config={"confidence": st.column_config.ProgressColumn(
                         "confidence", min_value=0.0, max_value=1.0)},
                     use_container_width=True, hide_index=True)
        st.download_button("⬇ Export predictions.jsonl",
                           data="\n".join(json.dumps(p) for p in preds),
                           file_name="predictions.jsonl")
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("Row detail: evidence, top-k, fraud audit"):
            rid = st.number_input("row_id", min_value=1, max_value=len(preds), value=1, step=1)
            row = preds[rid - 1]
            st.json({"voucher_type": row["voucher_type"], "confidence": row["confidence"],
                     "top_k": row["top_k"][:3], "evidence": row["evidence"]})
            audits = st.session_state.get("audits", [])
            if audits and rid - 1 < len(audits):
                st.json(audits[rid - 1])


if tab == "Review":
    st.header("Review — human approval gate")
    preds = st.session_state.get("preds", [])
    up_pred = st.file_uploader("…or upload predictions.jsonl", type=["jsonl"])
    if up_pred is not None:
        preds = [json.loads(line) for line in up_pred.read().decode("utf-8").splitlines() if line.strip()]
        st.session_state["preds"] = preds
    if not preds:
        st.info("Classify a sheet first, or upload predictions.")
        st.stop()
    queue = pilot_logic.review_queue(preds)
    st.write("%d of %d rows need review" % (len(queue), len(preds)))
    decided = st.session_state.setdefault("decisions", {})
    for item in queue:
        rid = item["row_id"]
        with st.expander("row %s · %s · model=%s (%.2f)" % (
                rid, item["invoice_number"], item["voucher_type"], item["confidence"])):
            st.write("top_k=%s" % (item["top_k"][:3],))
            st.write("evidence=%s" % (item["evidence"][:8],))
            if _firewall is not None:
                try:
                    _fs, _fa = _firewall.check_narration(str(item.get("narration", "") or ""))
                    st.write("fraud firewall: score=%d action=%s" % (_fs, _fa))
                except Exception:
                    pass
            b1, b2, b3 = st.columns(3)
            if b1.button("✓ Approve", key="a%d" % rid):
                decided[rid] = {"row_id": rid, "verdict": "approve", "label": None, "note": ""}
            if b2.button("✎ Override", key="o%d" % rid):
                decided[rid] = {"row_id": rid, "verdict": "OVERRIDING", "label": None, "note": ""}
            if b3.button("⚑ Escalate", key="e%d" % rid):
                decided[rid] = {"row_id": rid, "verdict": "escalate", "label": None, "note": ""}
            cur = decided.get(rid)
            if cur and cur["verdict"] == "OVERRIDING":
                label = st.selectbox("correct label", LABEL_NAMES, key="l%d" % rid)
                note = st.text_input("note", key="n%d" % rid)
                if st.button("Save override", key="s%d" % rid):
                    decided[rid] = {"row_id": rid, "verdict": "override", "label": label, "note": note}
            if cur and cur["verdict"] not in ("OVERRIDING",):
                st.caption("decision saved: %s" % cur["verdict"])
    if st.button("Apply decisions and export final", type="primary"):
        decs = [d for d in decided.values() if d["verdict"] in ("approve", "override", "escalate")]
        final_rows, approvals = pilot_logic.apply_decisions(preds, decs)
        st.session_state["final_rows"] = final_rows
        st.session_state["approvals"] = approvals
    final_rows = st.session_state.get("final_rows", [])
    if final_rows:
        st.success("final needs_review=%d" % sum(1 for r in final_rows if r["needs_review"]))
        st.download_button("⬇ final.jsonl",
                           data="\n".join(json.dumps(p) for p in final_rows), file_name="final.jsonl")
        acted = [d for d in decided.values()
                 if d["verdict"] in ("approve", "override", "escalate")]
        st.download_button("⬇ decisions.json",
                           data=json.dumps({"decisions": acted}, indent=1),
                           file_name="decisions.json")


if tab == "Dashboard":
    st.header("Dashboard")
    preds = st.session_state.get("preds", [])
    up_pred = st.file_uploader("predictions.jsonl (uses Classify results if empty)", type=["jsonl"])
    if up_pred is not None:
        preds = [json.loads(line) for line in up_pred.read().decode("utf-8").splitlines() if line.strip()]
    up_gold = st.file_uploader("gold labels json (optional)", type=["json"])
    if not preds:
        st.info("Nothing to show yet.")
        st.stop()
    kpi_cards(preds)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Label distribution")
        st.bar_chart(pd.Series(pilot_logic.label_distribution(preds)))
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Margin histogram (top1 − top2)")
        margins = []
        for p in preds:
            tk = p.get("top_k", [])
            margins.append(round(float(tk[0][1]) - float(tk[1][1]), 3) if len(tk) >= 2 else 1.0)
        st.bar_chart(pd.Series(margins).value_counts().sort_index())
        st.markdown("</div>", unsafe_allow_html=True)
    if up_gold is not None:
        gold = json.load(up_gold)
        truth = {g["row_id"]: g["voucher_type"] for g in gold}
        yt = [truth.get(p["row_id"], "") for p in preds]
        yp = [p["voucher_type"] for p in preds]
        rep = eval_mod.compute_metrics(yt, yp)
        st.subheader("Metrics vs gold: accuracy=%.3f macro_f1=%.3f (n=%d)"
                     % (rep["accuracy"], rep["macro_f1"], rep["n_rows"]))
        st.dataframe(pd.DataFrame(rep["per_class"])[["label", "precision", "recall", "f1", "support"]],
                     use_container_width=True, hide_index=True)


if tab == "System":
    st.header("System")
    import importlib as _il
    rows = []
    for mod in ["ingest", "normalise", "perspective", "evidence", "baseline", "scorer",
                "validate", "gold", "evaluate", "retriever", "calibrate", "challenger", "agent"]:
        try:
            _il.import_module("vouch_engine." + mod)
            rows.append((mod, "OK"))
        except Exception as exc:
            rows.append((mod, "FAIL %s" % (exc,)))
    st.dataframe(pd.DataFrame(rows, columns=["module", "status"]), use_container_width=True, hide_index=True)
    import urllib.request as _ur
    try:
        _ur.urlopen("http://127.0.0.1:8080/health", timeout=5)
        st.success("llama server :8080 reachable")
    except Exception:
        st.warning("llama server :8080 not reachable — keyword/stub/vouchpilot need no server")
    models = sorted(p.name for p in Path("models").glob("*.gguf")) if Path("models").exists() else []
    st.write("weights: %s" % (models if models else "none — run scripts/fetch_model.py"))
