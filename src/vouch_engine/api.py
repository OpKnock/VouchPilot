# FastAPI service: predict / evaluate / health over the frozen pipeline.

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

from . import baseline, evaluate as eval_mod, evidence, ingest, normalise, perspective, validate
from .labels import LABEL_NAMES

VERSION = "0.2.1"
DEFAULT_LLM_ENDPOINT = os.getenv("VOUCH_LLM_ENDPOINT", "http://127.0.0.1:8080")

_ALLOWED_UPLOADS = {
    ".xlsx",
    ".xlsm",
    ".csv",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
    ".webp",
}


class RowsIn(BaseModel):
    rows: list[dict[str, Any]]
    scorer: str = "keyword"
    endpoint: str = DEFAULT_LLM_ENDPOINT
    workers: int = 1
    challenge: bool = False
    fraud: bool = True


class EvalIn(BaseModel):
    gold: list[dict[str, Any]]
    pred: list[dict[str, Any]]


def _make_scorer(name: str, endpoint: str, fraud: bool = True):
    if name == "server":
        from .scorer import LlamaServerScorer

        return LlamaServerScorer(endpoint=endpoint)
    if name == "stub":
        from .scorer import StubScorer

        return StubScorer()
    if name == "vouchpilot":
        from extensions.vouchpilot_scorer import VouchPilotScorer

        return VouchPilotScorer(
            base="keyword",
            endpoint=endpoint,
            fraud=fraud,
            firewall=fraud,
        )
    if name != "keyword":
        raise HTTPException(status_code=422, detail="unknown scorer")
    from .__main__ import _KeywordAdapter

    return _KeywordAdapter(baseline)


def _read_csv(path: str | Path) -> dict[str, Any]:
    """Read a CSV upload without routing it through the XLSX reader."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]

    rows = [row for row in rows if any(str(value).strip() for value in row.values())]
    headers = list(rows[0].keys()) if rows else []
    return {
        "headers": headers,
        "rows": rows,
        "profile": {
            "fill_rate": {
                header: (
                    sum(1 for row in rows if str(row.get(header, "")).strip()) / len(rows)
                    if rows
                    else 0.0
                )
                for header in headers
            },
            "n_rows": len(rows),
            "header_row": 1,
        },
    }


def _read_input(path: str, suffix: str) -> dict[str, Any]:
    """Route each supported upload type to the correct resilient reader."""
    if suffix == ".csv":
        return _read_csv(path)

    if suffix in {".xlsx", ".xlsm"}:
        from . import messy

        # This is the web/API path that makes the documented messy-workbook
        # behavior real: title rows, merged cells, Hindi headers and the best
        # transaction sheet are handled before canonical normalization.
        return messy.read_messy_xlsx(path, pick_best=True)

    try:
        from . import intake as _intake

        converted = path + ".rows.xlsx"
        _intake.intake_to_xlsx(path, converted)
        return _read_input(converted, ".xlsx")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"intake failed: {exc}") from exc


def _module_status() -> dict[str, str]:
    statuses: dict[str, str] = {}
    for name in ("ingest", "normalise", "perspective", "evidence", "baseline", "scorer", "validate", "gold", "evaluate", "agent", "messy", "intake"):
        try:
            __import__("vouch_engine." + name)
            statuses[name] = "OK"
        except Exception as exc:
            statuses[name] = f"FAIL {exc}"
    return statuses


def classify_raw_rows(
    raw_rows: list[dict],
    scorer_name: str,
    endpoint: str,
    workers: int,
    challenge: bool = False,
    fraud: bool = True,
) -> tuple[list[dict], int]:
    import concurrent.futures

    if scorer_name not in {"stub", "keyword", "server", "vouchpilot"}:
        raise HTTPException(status_code=422, detail="unknown scorer")
    headers = sorted({k for row in raw_rows for k in row.keys()})
    mapping = normalise.map_columns(headers, raw_rows[:5])
    canonical = normalise.to_canonical(raw_rows, mapping)
    perspective.resolve(canonical)
    scorer_obj = _make_scorer(scorer_name, endpoint, fraud)

    challenger = None
    if challenge and hasattr(scorer_obj, "_complete"):
        try:
            from .challenger import recheck as _recheck

            challenger = _recheck
        except Exception:
            challenger = None

    def one(idx: int) -> dict:
        crow = canonical[idx]
        tags, mask = evidence.extract(crow)
        try:
            label, conf, top_k = scorer_obj.predict(crow, tags, mask, None)
        except TypeError:
            label, conf, top_k = scorer_obj.predict(crow, tags, mask)
        out_tags = [str(tag) for tag in tags]

        if challenger is not None and isinstance(top_k, list) and len(top_k) >= 2:
            try:
                margin = float(top_k[0][1]) - float(top_k[1][1])
            except (TypeError, ValueError, IndexError):
                margin = 1.0
            if margin < 0.15:
                try:
                    desc = "narration=%s items=%s" % (
                        crow.get("narration", ""),
                        crow.get("items", []),
                    )
                    winner, cc = challenger(
                        desc,
                        out_tags,
                        top_k[0][0],
                        top_k[1][0],
                        scorer_obj._complete,
                    )
                    label, conf = winner, float(cc)
                    if top_k and top_k[0][0] == winner:
                        top_k[0][1] = float(cc)
                    out_tags.append("CHALLENGED")
                except Exception:
                    out_tags.append("CHALLENGE-SKIPPED")

        invoice = (crow.get("doc") or {}).get("invoice_number") or f"ROW-{idx + 1}"
        return {
            "row_id": crow.get("row_id", idx + 1),
            "invoice_number": invoice,
            "voucher_type": label,
            "confidence": float(conf),
            "needs_review": bool(float(conf) < 0.5),
            "top_k": top_k,
            "evidence": out_tags,
        }

    preds: list[dict] = []
    invalid = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for rec in pool.map(one, range(len(canonical))):
            try:
                preds.append(validate.validate_prediction(rec).model_dump())
            except Exception:
                invalid += 1
    return preds, invalid


def _suffix_for_upload(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_UPLOADS:
        raise HTTPException(
            status_code=415,
            detail=(
                "unsupported file type; use XLSX, XLSM, CSV, PDF or a bill image "
                "(PNG/JPG/TIFF/BMP/WEBP)"
            ),
        )
    return suffix


def _cleanup(paths: list[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="VouchIQ VouchEngine", version=VERSION)

    @app.get("/health")
    def health() -> dict:
        modules = _module_status()
        failed = [name for name, status in modules.items() if status != "OK"]
        return {
            "status": "degraded" if failed else "ok",
            "version": VERSION,
            "modules": modules,
        }

    @app.post("/predict")
    async def predict(
        file: UploadFile,
        scorer: str = "keyword",
        endpoint: str = DEFAULT_LLM_ENDPOINT,
        workers: int = 1,
        challenge: bool = False,
        fraud: bool = True,
    ) -> dict:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="uploaded file is empty")

        suffix = _suffix_for_upload(file.filename or "")
        source_paths: list[str] = []
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            source_paths.append(tmp.name)

        try:
            data = _read_input(source_paths[0], suffix)
            preds, invalid = classify_raw_rows(
                list(data.get("rows", [])),
                scorer,
                endpoint,
                workers,
                challenge,
                fraud,
            )
            return {"predictions": preds, "n_rows": len(preds), "invalid": invalid}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"pipeline failed: {exc}") from exc
        finally:
            # PDF/image intake can create an adjacent .rows.xlsx artifact.
            source_paths.extend(
                [
                    path
                    for path in (
                        source_paths[0] + ".rows.xlsx",
                    )
                    if os.path.exists(path)
                ]
            )
            _cleanup(source_paths)

    @app.post("/predict-rows")
    def predict_rows(body: RowsIn) -> dict:
        try:
            preds, invalid = classify_raw_rows(
                list(body.rows),
                body.scorer,
                body.endpoint,
                body.workers,
                body.challenge,
                body.fraud,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"pipeline failed: {exc}") from exc
        return {"predictions": preds, "n_rows": len(preds), "invalid": invalid}

    @app.post("/evaluate")
    def evaluate(body: EvalIn) -> dict:
        truth = {gold.get("row_id"): gold.get("voucher_type", "") for gold in body.gold}
        yt = [truth.get(pred.get("row_id"), "") for pred in body.pred]
        yp = [pred.get("voucher_type", "") for pred in body.pred]
        return eval_mod.compute_metrics(yt, yp, labels=list(LABEL_NAMES))

    @app.get("/labels")
    def labels() -> dict:
        from .labels import LABELS as _LABELS

        return {"labels": [dict(label) for label in _LABELS]}

    @app.get("/settings")
    def get_settings() -> dict:
        from . import settings as _settings

        return _settings.load()

    @app.post("/settings")
    def put_settings(patch: dict) -> dict:
        from . import settings as _settings

        try:
            return _settings.save(dict(patch or {}))
        except (TypeError, ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/system")
    def system() -> dict:
        import urllib.request as _ur

        modules = _module_status()
        server: dict[str, object] = {"url": DEFAULT_LLM_ENDPOINT, "up": False}
        try:
            _ur.urlopen(f"{DEFAULT_LLM_ENDPOINT.rstrip('/')}/health", timeout=4)
            server["up"] = True
        except Exception:
            pass

        weights: list[str] = []
        try:
            weights = sorted(path.name for path in Path("models").glob("*.gguf"))
        except OSError:
            pass

        return {
            "version": VERSION,
            "modules": modules,
            "server": server,
            "weights": weights,
        }

    @app.get("/launcher")
    def launcher():
        from fastapi.responses import FileResponse

        path = Path(__file__).resolve().parents[2] / "start-vouchpilot.bat"
        if not path.exists():
            raise HTTPException(status_code=404, detail="launcher not packaged yet")
        return FileResponse(str(path), filename="VouchPilot-Launcher.bat")

    @app.get("/desktop-package")
    def desktop_package():
        import io as _io
        import zipfile as _zf

        root = Path(__file__).resolve().parents[2]
        exe = root / "VouchPilot.exe"
        if not exe.exists():
            raise HTTPException(
                status_code=404,
                detail="desktop exe not built yet (see desktop/launcher.py)",
            )
        readme = (
            "VouchPilot desktop package (fully offline, no signup, no accounts).\n\n"
            "Contents: VouchPilot.exe, VouchPilot-Launcher.bat, start-vouchpilot.ps1.\n\n"
            "Prerequisites: Python 3.11+ and project dependencies.\n"
            "Run: double-click VouchPilot.exe, then open the printed local URL.\n"
        )
        buf = _io.BytesIO()
        with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as zf:
            zf.write(exe, arcname="VouchPilot.exe")
            for name, arc in (
                ("start-vouchpilot.bat", "VouchPilot-Launcher.bat"),
                ("start-vouchpilot.ps1", "start-vouchpilot.ps1"),
            ):
                file_path = root / name
                if file_path.exists():
                    zf.write(file_path, arcname=arc)
            zf.writestr("README.txt", readme)

        from fastapi.responses import Response

        return Response(
            buf.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="VouchPilot-Desktop.zip"'
            },
        )

    try:
        from fastapi.staticfiles import StaticFiles

        dist = Path(__file__).resolve().parents[2] / "web" / "dist"
        if (dist / "index.html").is_file():
            app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    except Exception:
        pass

    return app


__all__ = ["create_app", "classify_raw_rows"]
