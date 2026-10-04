"""VouchPilot review app: pending.json review with fraud score, pin status, top_k.

Standalone Streamlit app (does not modify app.py). Run:
streamlit run src/vouch_engine/app_review.py
Emits decisions.json in the same {row_id, verdict, label, note} format
consumed by: agent run --gate file:decisions.json
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from vouch_engine.labels import LABEL_NAMES

try:
    from extensions import fraud_firewall as _firewall
except Exception:
    _firewall = None

try:
    from extensions import fraud_quish as _quish
except Exception:
    _quish = None


def _fraud_panel(item: dict) -> None:
    text = str(item.get('narration', '') or '')
    if _firewall is not None:
        try:
            score, action = _firewall.check_narration(text)
            st.write('firewall: score=%d action=%s' % (score, action))
        except Exception as exc:
            st.write('firewall unavailable: %s' % (exc,))
    else:
        st.write('firewall: unavailable')
    if _quish is not None:
        try:
            probe = {'narration': text, 'raw': {}, 'refs': {},
                       'pay': {'utr': ''}}
            score, flags = _quish.score_bill(probe)
            st.write('quish: score=%d flags=%s' % (score, flags[:6]))
        except Exception as exc:
            st.write('quish unavailable: %s' % (exc,))
    else:
        st.write('quish: unavailable')


def main() -> None:
    st.set_page_config(page_title='VouchPilot Review', layout='wide')
    st.title('VouchPilot — human approval gate')
    pending_file = st.file_uploader('Upload pending.json', type=['json'])
    pred_file = st.file_uploader('Upload predictions.jsonl (optional, for pin status)', type=['jsonl'])
    expected_pin = st.text_input('Expected sha256 pin (optional)', '')
    live_pin = ''
    if pred_file is not None:
        live_pin = hashlib.sha256(pred_file.getvalue()).hexdigest()
        st.write('live pin: %s' % (live_pin,))
        if expected_pin.strip():
            match = live_pin == expected_pin.strip().lower()
            st.write('pin status: %s' % ('MATCH' if match else 'DRIFT'))
    if pending_file is None:
        st.stop()
    pending = json.load(pending_file)
    queue = pending.get('queue', [])
    st.write('%d rows need review' % (len(queue),))
    decisions = []
    for item in queue:
        rid = item['row_id']
        with st.expander('row %s | %s | model=%s (%.2f)' % (
                rid, item['invoice_number'], item['model_label'], item['confidence'])):
            st.write('reason=%s' % (item['reason'],))
            st.write('top_k=%s' % (item['top_k'][:3],))
            st.write('evidence=%s' % (item['evidence'][:8],))
            if item.get('narration'):
                st.write('narr=%s' % (item['narration'][:200],))
            _fraud_panel(item)
            verdict = st.selectbox('verdict', ['approve', 'override', 'escalate'], key='v%d' % (rid,))
            label, note = None, ''
            if verdict == 'override':
                label = st.selectbox('correct label', LABEL_NAMES, key='l%d' % (rid,))
                note = st.text_input('note', key='n%d' % (rid,))
            decisions.append({'row_id': rid, 'verdict': verdict, 'label': label, 'note': note})
    st.download_button('Download decisions.json',
                       data=json.dumps({'decisions': decisions}, indent=1),
                       file_name='decisions.json')


if __name__ == '__main__':
    main()

