"""
Minimal Streamlit dashboard to display model metrics from the screener API.
Run with: `streamlit run monitoring/dashboard.py`
"""
import streamlit as st
import requests

API_URL = st.secrets.get('PREDICTION_API_URL', 'http://127.0.0.1:8000/api/predict/best')

st.title('Quantify Model Monitoring')

mode = st.selectbox('Mode', ['live', 'previous_close'])
if st.button('Fetch latest metrics'):
    try:
        resp = requests.get(API_URL, params={'mode': mode, 'top_n': 1, 'force': False}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if 'model_metrics' in data and data['model_metrics']:
            st.write('Model metrics:')
            st.json(data['model_metrics'])
        else:
            st.warning('No model_metrics available in API response')
    except Exception as e:
        st.error(f'Failed to query API: {e}')

st.markdown('You can configure `PREDICTION_API_URL` in Streamlit secrets or edit the file.')
