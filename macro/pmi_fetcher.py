import os
from fredapi import Fred
import streamlit as st

@st.cache_data(ttl=86400)
def get_ism_pmi():
    try:
        fred_key = os.environ.get("FRED_API_KEY")
        fred = Fred(api_key=fred_key)
        # Proxy for PMI: new orders in tech equipment
        orders_series = fred.get_series('A34SNO')
        latest = orders_series.dropna().iloc[-1]
        return round(float(latest), 2)
    except Exception as e:
        return f"Error fetching Tech Orders (A34SNO): {e}"