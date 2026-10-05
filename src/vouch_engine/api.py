# FastAPI service: predict / evaluate / health over the frozen pipeline.

from __future__ import annotations

import concurrent.futures
import csv
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import baseline, evidence, normalise, perspective, validate
from . import evaluate as eval_mod
from .labels import LABEL_NAMES

VERSION = "0.2.1"
DEFAULT_LLM_ENDPOINT = os.getenv("VOUCH_LLM_ENDPOINT", "http://127.0.0.1:8080")
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
try:
    MAX_UPLOAD_BYTES = max(
        1,
        int(os.getenv("VOUCH_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))),
    )
except (TypeError, ValueError):
    MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_BYTES
MAX_WORKERS = 8
DEFAULT_LLM_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "llm"}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_root() -> Path:
    configured = os.getenv("VOUCHPILOT_APP_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _web_root() -> Path:
    configured = os.getenv("VOUCHPILOT_WEB_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return _app_root() / "web" / "dist"

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
    workers: int = Field(default=1, ge=1, le=MAX_WORKERS)
    challenge: bool = False
    fraud: bool = True


class EvalIn(BaseModel):
    gold: list[dict[str, Any]]
    pred: list[dict[str, Any]]


class AuditIn(BaseModel):
    records: list[dict[str, Any]]
    predictions: list[dict[str, Any]]


def _allowed_llm_hosts() -> set[str]:
    configured = os.getenv("VOUCH_LLM_ALLOWED_HOSTS", "")
    hosts = {host.strip().lower() for host in configured.split(",") if host.strip()}
    return DEFAULT_LLM_ALLOWED_HOSTS | hosts


def validate_llm_endpoint(endpoint: str) -> str:
    try:
        parsed = urlsplit(str(endpoint))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid LLM endpoint") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="invalid LLM endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(status_code=422, detail="LLM endpoint must not contain credentials, query, or fragment")
    host = parsed.hostname.lower().rstrip(".")
    if host not in _allowed_llm_hosts():
        raise HTTPException(
            status_code=422,
            detail=f"LLM endpoint host '{host}' is not allowed; use a local host or configure VOUCH_LLM_ALLOWED_HOSTS",
        )
    return endpoint.rstrip("/")


def _clamp_workers(workers: int) -> int:
    try:
        return max(1, min(MAX_WORKERS, int(workers)))
    except (TypeError, ValueError):
        return 1


def _make_scorer(name: str, endpoint: str, fraud: bool = True):
    if name == "server":
        from .scorer import LlamaServerScorer

        return LlamaServerScorer(endpoint=validate_llm_endpoint(endpoint))
    if name == "stub":
        from .scorer import StubScorer

        return StubScorer()
    if name == "vouchpilot":
        from extensions.vouchpilot_scorer import VouchPilotScorer

        return VouchPilotScorer(
            base="keyword",
            endpoint=validate_llm_endpoint(endpoint),
            fraud=fraud,
            firewall=fraud,
        )
    if name != "keyword":
        raise HTTPException(status_code=422, detail="unknown scorer")
    from .__main__ import _KeywordAdapter

    return _KeywordAdapter(baseline)


def _read_csv(path: str | Path) -> dict[str, Any]:
    """Read CSV with delimiter sniffing and decorative-row detection."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\\t|")
        except csv.Error:
            dialect = csv.excel
        grid = list(csv.reader(handle, dialect))

    from .ingest import detect_header_row

    if not grid:
        return {
            "headers": [],
            "rows": [],
            "profile": {"fill_rate": {}, "n_rows": 0, "header_row": 1},
        }

    header_idx = detect_header_row(grid, scan_limit=15)
    raw_headers = grid[header_idx]
    headers = []
    seen = {}
    for index, cell in enumerate(raw_headers):
        name = str(cell).strip() or f"col_{index}"
        count = seen.get(name, 0) + 1
        seen[name] = count
        headers.append(name if count == 1 else f"{name}_{count}")

    rows = []
    for values in grid[header_idx + 1 :]:
        if not any(str(value).strip() for value in values):
            continue
        rows.append({
            header: values[index] if index < len(values) else ""
            for index, header in enumerate(headers)
        })

    n_rows = len(rows)
    fill_rate = {
        header: (
            sum(1 for row in rows if str(row.get(header, "")).strip()) / n_rows
            if n_rows
            else 0.0
        )
        for header in headers
    }
    return {
        "headers": headers,
        "rows": rows,
        "profile": {
            "fill_rate": fill_rate,
            "n_rows": n_rows,
            "header_row": header_idx + 1,
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

    from . import intake as _intake

    converted = path + ".rows.xlsx"
    try:
        _intake.intake_to_xlsx(path, converted)
    except (_intake.IntakeError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"intake failed: {exc}") from exc
    return _read_input(converted, ".xlsx")


def _module_status() -> dict[str, str]:
    statuses: dict[str, str] = {}
    for name in (
        "ingest",
        "normalise",
        "perspective",
        "evidence",
        "baseline",
        "scorer",
        "validate",
        "gold",
        "evaluate",
        "agent",
        "messy",
        "intake",
    ):
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
    if scorer_name not in {"stub", "keyword", "server", "vouchpilot"}:
        raise HTTPException(status_code=422, detail="unknown scorer")
    headers = sorted({k for row in raw_rows for k in row.keys()})
    mapping = normalise.map_columns(headers, raw_rows[:5])
    canonical = normalise.to_canonical(raw_rows, mapping)
    perspective.resolve(canonical)
    scorer_obj = _make_scorer(scorer_name, endpoint, fraud)

    workers = _clamp_workers(workers)

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
    app = FastAPI(title="VouchPilot", version=VERSION)
    app.state.saas_mode = _env_flag("VOUCH_SAAS_MODE")

    cors_origins = [
        origin.strip()
        for origin in os.getenv("VOUCH_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

    @app.get("/health")
    def health() -> dict:
        modules = _module_status()
        failed = [name for name, status in modules.items() if status != "OK"]
        return {
            "status": "degraded" if failed else "ok",
            "version": VERSION,
            "mode": "saas" if app.state.saas_mode else "local",
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
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"uploaded file exceeds the {MAX_UPLOAD_BYTES} bytes server limit",
            )
        if not raw:
            raise HTTPException(status_code=400, detail="uploaded file is empty")

        suffix = _suffix_for_upload(file.filename or "")
        source_paths: list[str] = []
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            source_paths.append(tmp.name)

        try:
            data = _read_input(source_paths[0], suffix)
            input_rows = len(data.get("rows", []))
            preds, invalid = classify_raw_rows(
                list(data.get("rows", [])),
                scorer,
                endpoint,
                workers,
                challenge,
                fraud,
            )
            return {"predictions": preds, "n_rows": input_rows, "invalid": invalid}
        except HTTPException:
            raise
        except Exception as exc:
            from .scorer import ScorerResponseError, ScorerUnavailableError

            if isinstance(exc, ScorerUnavailableError):
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if isinstance(exc, ScorerResponseError):
                raise HTTPException(status_code=502, detail=str(exc)) from exc
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
            from .scorer import ScorerResponseError, ScorerUnavailableError

            if isinstance(exc, ScorerUnavailableError):
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if isinstance(exc, ScorerResponseError):
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            raise HTTPException(status_code=500, detail=f"pipeline failed: {exc}") from exc
        return {"predictions": preds, "n_rows": len(body.rows), "invalid": invalid}

    @app.post("/audit")
    def audit(body: AuditIn) -> dict:
        from . import audit as audit_mod

        return audit_mod.audit_recorded_vs_predicted(
            list(body.records),
            list(body.predictions),
        )

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
            patch = dict(patch or {})
            if app.state.saas_mode:
                merged = dict(_settings.DEFAULTS)
                merged.update(patch)
                return _settings.validate(merged)
            return _settings.save(patch)
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
            weights_dir = _app_root() / "models"
            weights = sorted(path.name for path in weights_dir.glob("*.gguf"))
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

        path = _app_root() / "start-vouchpilot.bat"
        if not path.exists():
            raise HTTPException(status_code=404, detail="launcher not packaged yet")
        return FileResponse(str(path), filename="VouchPilot-Launcher.bat")

    @app.get("/desktop-package")
    def desktop_package():
        import io as _io
        import zipfile as _zf

        root = _app_root()
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

        dist = _web_root()
        if (dist / "index.html").is_file():
            app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    except Exception:
        pass

    return app


__all__ = ["create_app", "classify_raw_rows"]
