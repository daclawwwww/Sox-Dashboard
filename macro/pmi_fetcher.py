import os
from fredapi import Fred
import streamlit as st

@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_ism_pmi():
    try:
        fred_key = os.environ.get("FRED_API_KEY")
        fred = Fred(api_key=fred_key)
        # Use ISM New Orders Index (a strong PMI proxy)
        new_orders_index = fred.get_series('NAPMNOI')
        latest = new_orders_index.dropna().iloc[-1]
        return float(round(latest, 2))
    except Exception as e:
        return f"Error fetching PMI proxy: {e}"