import os
from fredapi import Fred
import streamlit as st

@st.cache_data(ttl=86400)
def get_capex_proxy():
    try:
        fred_key = os.environ.get("FRED_API_KEY")
        fred = Fred(api_key=fred_key)
        series = fred.get_series('NEWORDER')  # Nondefense CapEx ex-aircraft
        series = series.dropna()
        latest = float(series.iloc[-1])
        prev = float(series.iloc[-2])
        score = 1 if latest > prev else -1 if latest < prev else 0
        return {"latest": round(latest, 2), "prev": round(prev, 2), "score": score}
    except Exception as e:
        return {"error": str(e)}