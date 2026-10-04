# Quickstart: 001-vertical-slice

**Prereqs**: Python 3.11+, offline except setup downloads.

```powershell
cd C:\Users\wagde\Documents\VouchIQ-dev
pip install -e .[dev]
$env:PYTHONPATH = "src"
python -m pytest tests/ -q          # expect: all green, no weights needed
ruff check src tests scripts
```

## 5-minute demo (stub scorer, no weights)

```powershell
$env:PYTHONPATH = "src"
python -m vouch_engine gold --n 270 --seed 7 --out demo\gold
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred_keyword.jsonl --scorer keyword
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred_stub.jsonl --scorer stub
python -m vouch_engine evaluate --gold demo\gold_labels.json --pred demo\pred_keyword.jsonl --report demo\eval_keyword.json
python -m vouch_engine evaluate --gold demo\gold_labels.json --pred demo\pred_stub.jsonl --report demo\eval_stub.json
```

## Real SLM scoring (one-time setup, needs network)

```powershell
python scripts\fetch_model.py --out models
# start llama-server with the printed command, then:
python -m vouch_engine run --input demo\gold.xlsx --out demo\pred_slm.jsonl --scorer server
python -m vouch_engine doctor            # weights + server health
```

## UI and containers

```powershell
streamlit run app.py
docker compose up --build   # offline app + llm services
```
