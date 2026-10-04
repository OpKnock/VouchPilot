# FastAPI service: predict / evaluate / health over the frozen pipeline. New file (004).
# Reuses vouch_engine modules directly; scorer default keyword (no server needed).

from __future__ import annotations

import tempfile
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

from . import baseline, evaluate as eval_mod, evidence, ingest, normalise
from . import perspective, validate
from .labels import LABEL_NAMES

VERSION = '0.1.0'


class RowsIn(BaseModel):
    rows: list[dict[str, Any]]
    scorer: str = 'keyword'
    endpoint: str = 'http://127.0.0.1:8080'
    workers: int = 1
    challenge: bool = False


class EvalIn(BaseModel):
    gold: list[dict[str, Any]]
    pred: list[dict[str, Any]]


def _make_scorer(name: str, endpoint: str):
    if name == 'server':
        from .scorer import LlamaServerScorer
        return LlamaServerScorer(endpoint=endpoint)
    if name == 'stub':
        from .scorer import StubScorer
        return StubScorer()
    if name == 'vouchpilot':
        from extensions.vouchpilot_scorer import VouchPilotScorer
        return VouchPilotScorer(base='keyword', endpoint=endpoint)
    from .__main__ import _KeywordAdapter
    return _KeywordAdapter(baseline)


def classify_raw_rows(raw_rows: list[dict], scorer_name: str,
                      endpoint: str, workers: int,
                      challenge: bool = False) -> tuple[list[dict], int]:
    import concurrent.futures
    headers = sorted({k for row in raw_rows for k in row.keys()})
    mapping = normalise.map_columns(headers, raw_rows[:5])
    canonical = normalise.to_canonical(raw_rows, mapping)
    perspective.resolve(canonical)
    scorer_obj = _make_scorer(scorer_name, endpoint)
    if scorer_name not in ('stub', 'keyword', 'server', 'vouchpilot'):
        raise HTTPException(status_code=422, detail='unknown scorer')
    challenger = None
    if challenge and hasattr(scorer_obj, '_complete'):
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
        out_tags = [str(t) for t in tags]
        if challenger is not None and isinstance(top_k, list) and len(top_k) >= 2:
            try:
                margin = float(top_k[0][1]) - float(top_k[1][1])
            except (TypeError, ValueError, IndexError):
                margin = 1.0
            if margin < 0.15:
                try:
                    desc = 'narration=%s items=%s' % (crow.get('narration', ''),
                                                     crow.get('items', []))
                    winner, cc = challenger(desc, out_tags, top_k[0][0], top_k[1][0],
                                            scorer_obj._complete)
                    label, conf = winner, float(cc)
                    if top_k and top_k[0][0] == winner:
                        top_k[0][1] = float(cc)
                    out_tags = out_tags + ['CHALLENGED']
                except Exception:
                    out_tags = out_tags + ['CHALLENGE-SKIPPED']
        invoice = (crow.get('doc') or {}).get('invoice_number') or 'ROW-%d' % (idx + 1,)
        return {'row_id': crow.get('row_id', idx + 1), 'invoice_number': invoice,
                'voucher_type': label, 'confidence': float(conf),
                'needs_review': bool(float(conf) < 0.5), 'top_k': top_k,
                'evidence': out_tags}
    preds, invalid = [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for rec in pool.map(one, range(len(canonical))):
            try:
                preds.append(validate.validate_prediction(rec).model_dump())
            except Exception:
                invalid += 1
    return preds, invalid


def create_app() -> FastAPI:
    app = FastAPI(title='VouchIQ VouchEngine', version=VERSION)

    @app.get('/health')
    def health() -> dict:
        mods = {}
        for name in ('ingest', 'normalise', 'perspective', 'evidence', 'baseline',
                     'scorer', 'validate', 'gold', 'evaluate', 'agent'):
            try:
                __import__('vouch_engine.' + name)
                mods[name] = 'OK'
            except Exception as exc:
                mods[name] = 'FAIL %s' % (exc,)
        return {'status': 'ok', 'version': VERSION, 'modules': mods}

    @app.post('/predict')
    async def predict(file: UploadFile, scorer: str = 'keyword',
                      endpoint: str = 'http://127.0.0.1:8080',
                      workers: int = 1, challenge: bool = False) -> dict:
        raw = await file.read()
        suffix = '.xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            path = tmp.name
        try:
            data = ingest.read_excel(path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail='unreadable xlsx: %s' % (exc,))
        try:
            preds, invalid = classify_raw_rows(list(data.get('rows', [])), scorer,
                                              endpoint, workers, challenge)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail='pipeline failed: %s' % (exc,))
        return {'predictions': preds, 'n_rows': len(preds), 'invalid': invalid}

    @app.post('/predict-rows')
    def predict_rows(body: RowsIn) -> dict:
        try:
            preds, invalid = classify_raw_rows(list(body.rows), body.scorer,
                                              body.endpoint, body.workers,
                                              body.challenge)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail='pipeline failed: %s' % (exc,))
        return {'predictions': preds, 'n_rows': len(preds), 'invalid': invalid}

    @app.post('/evaluate')
    def evaluate(body: EvalIn) -> dict:
        truth = {g.get('row_id'): g.get('voucher_type', '') for g in body.gold}
        yt = [truth.get(p.get('row_id'), '') for p in body.pred]
        yp = [p.get('voucher_type', '') for p in body.pred]
        return eval_mod.compute_metrics(yt, yp, labels=list(LABEL_NAMES))

    @app.get('/labels')
    def labels() -> dict:
        from .labels import LABELS as _LABELS

        return {'labels': [dict(lb) for lb in _LABELS]}

    @app.get('/settings')
    def get_settings() -> dict:
        from . import settings as _settings

        return _settings.load()

    @app.post('/settings')
    def put_settings(patch: dict) -> dict:
        from . import settings as _settings

        try:
            return _settings.save(dict(patch or {}))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get('/system')
    def system() -> dict:
        import importlib as _il
        import urllib.request as _ur

        modules = {}
        for name in ('ingest', 'normalise', 'perspective', 'evidence', 'baseline',
                     'scorer', 'validate', 'gold', 'evaluate', 'agent'):
            try:
                _il.import_module('vouch_engine.' + name)
                modules[name] = 'OK'
            except Exception as exc:
                modules[name] = 'FAIL %s' % (exc,)
        server: dict[str, object] = {'url': 'http://127.0.0.1:8080', 'up': False}
        try:
            _ur.urlopen('http://127.0.0.1:8080/health', timeout=4)
            server['up'] = True
        except Exception:
            pass
        weights: list[str] = []
        try:
            import pathlib as _pl

            weights = sorted(p.name for p in _pl.Path('models').glob('*.gguf'))
        except Exception:
            pass
        return {'version': VERSION, 'modules': modules, 'server': server,
                'weights': weights}

    @app.get('/launcher')
    def launcher():
        from fastapi.responses import FileResponse

        path = 'start-vouchpilot.bat'
        import os as _os

        if not _os.path.exists(path):
            raise HTTPException(status_code=404, detail='launcher not packaged yet')
        return FileResponse(path, filename='VouchPilot-Launcher.bat')

    @app.get('/desktop-package')
    def desktop_package():
        import io as _io
        import zipfile as _zf

        import os as _os3

        exe = 'VouchPilot.exe'
        if not _os3.path.exists(exe):
            raise HTTPException(
                status_code=404,
                detail='desktop exe not built yet (see desktop/launcher.py)',
            )
        readme = (
            'VouchPilot desktop package (fully offline, no signup, no accounts).\n'
            '\n'
            'Contents: VouchPilot.exe, VouchPilot-Launcher.bat, start-vouchpilot.ps1.\n'
            '\n'
            'Prerequisites on this machine:\n'
            '1. Python 3.11+ installed and on PATH (check: python --version).\n'
            '2. Backend deps installed once: pip install fastapi uvicorn pandas openpyxl\n'
            '   pydantic rapidfuzz scikit-learn streamlit huggingface_hub\n'
            '   (or: pip install -e . from the project folder).\n'
            '3. Model weights in models/ (run scripts/fetch_model.py) for the AI\n'
            '   server scorer. Keyword and fraud-screened scorers need no weights.\n'
            '\n'
            'Run: double-click VouchPilot.exe (or the .bat). Open the printed URL\n'
            'in your browser yourself. Close the console window to stop everything.\n'
        )
        buf = _io.BytesIO()
        with _zf.ZipFile(buf, 'w', _zf.ZIP_DEFLATED) as zf:
            zf.write(exe, arcname='VouchPilot.exe')
            for name, arc in (('start-vouchpilot.bat', 'VouchPilot-Launcher.bat'),
                              ('start-vouchpilot.ps1', 'start-vouchpilot.ps1')):
                if _os3.path.exists(name):
                    zf.write(name, arcname=arc)
            zf.writestr('README.txt', readme)
        from fastapi.responses import Response

        return Response(
            buf.getvalue(),
            media_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename="VouchPilot-Desktop.zip"'},
        )

    try:
        from fastapi.staticfiles import StaticFiles

        import os as _os2

        _here = _os2.path.dirname(_os2.path.abspath(__file__))
        _root = _os2.path.dirname(_os2.path.dirname(_here))
        dist = _os2.path.join(_root, 'web', 'dist')

        if _os2.path.isfile(_os2.path.join(dist, 'index.html')):
            app.mount('/', StaticFiles(directory=dist, html=True), name='web')
    except Exception:
        pass

    return app


__all__ = ['create_app', 'classify_raw_rows']

