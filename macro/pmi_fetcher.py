import os
from fredapi import Fred
import streamlit as st

@st.cache_data(ttl=86400)
def get_ism_pmi():
    try:
        fred_key = os.environ.get("FRED_API_KEY")
        fred = Fred(api_key=fred_key)
        new_orders = fred.get_series('NAPMNOI')
        latest = new_orders.dropna().iloc[-1]
        return float(round(latest, 2))
    except Exception as e:
        return f"Error fetching PMI proxy (New Orders): {e}"