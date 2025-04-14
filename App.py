import streamlit as st
st.set_page_config(page_title="SOXX Momentum Dashboard", layout="wide")

import yfinance as yf
import pandas as pd
from indicators.rsi import compute_rsi
from indicators.macd import compute_macd
from indicators.roc import compute_roc
from indicators.relative_strength import compute_relative_strength
from utils.data_loader import load_price_data
from macro.semiconductor_leads import get_macro_signal_score
from macro.pmi_fetcher import get_ism_pmi

st.title("SOXX Momentum Dashboard")

# --- HEADER SIGNAL OUTPUT ---
score = 0
signal = "N/A"

# Load price data
with st.spinner("Loading market data..."):
    df_soxx, df_spy = load_price_data()

# Compute indicators
try:
    close = df_soxx['Close'].dropna()
    spy_close = df_spy['Close'].dropna()
    rsi = compute_rsi(close).dropna()
    macd_hist = compute_macd(close).dropna()
    roc_3m = compute_roc(close, 63).dropna()
    relative_strength = compute_relative_strength(close, spy_close).dropna()

    latest_rsi = round(float(rsi.iloc[-1]), 2)
    latest_macd = round(float(macd_hist.iloc[-1]), 2)
    latest_roc = round(float(roc_3m.iloc[-1]), 2)
    latest_rel = round(float(relative_strength.iloc[-1]), 2)

except Exception as e:
    st.error(f"Error calculating indicators: {e}")

# --- SCORECARD SECTION ---
st.subheader("Signal Scorecard")

with st.expander("1. Technical Indicators", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("RSI (14)", latest_rsi)
    col2.metric("MACD Histogram", latest_macd)
    col3.metric("3-Month ROC (%)", latest_roc)
    col4.metric("Rel Strength (SOXX/SPY)", latest_rel)

    if latest_rsi > 55:
        score += 1
        st.write("RSI Score: +1")
    elif latest_rsi < 45:
        score -= 1
        st.write("RSI Score: -1")

    if latest_macd > 0.2:
        score += 1
        st.write("MACD Score: +1")
    elif latest_macd < -0.2:
        score -= 1
        st.write("MACD Score: -1")

    if latest_roc > 5:
        score += 1
        st.write("ROC Score: +1")
    elif latest_roc < -2:
        score -= 1
        st.write("ROC Score: -1")

    try:
        rel_trend = relative_strength.tail(5).diff().mean()
        if rel_trend > 0.001:
            score += 1
            st.write("Rel Strength Score: +1")
        elif rel_trend < -0.001:
            score -= 1
            st.write("Rel Strength Score: -1")
    except:
        pass

with st.expander("2. Macro Indicators", expanded=True):
    pmi_value = get_ism_pmi()
    semi_sales_yoy_growth = 6.5  # Placeholder

    col1, col2 = st.columns(2)
    col1.metric("Tech Orders (A34SNO)", pmi_value)
    col2.metric("Semi Sales YoY Growth", f"{semi_sales_yoy_growth:.2f}%")

    if isinstance(pmi_value, float):
        if pmi_value > 25000:
            score += 1
            st.write("Tech Orders Score: +1")
        elif pmi_value < 24000:
            score -= 1
            st.write("Tech Orders Score: -1")

    if semi_sales_yoy_growth > 0:
        score += 1
        st.write("Semi Sales Score: +1")
    elif semi_sales_yoy_growth < 0:
        score -= 1
        st.write("Semi Sales Score: -1")

    macro_trend = st.radio("Simulate Macro Conditions:", ["strong", "neutral", "weak"], index=1)
    macro_result = get_macro_signal_score(simulate=macro_trend)
    st.write(f"Simulated Macro Composite Score: {macro_result['macro_score']}")
    score += macro_result["macro_score"]

# --- FINAL SIGNAL DISPLAY ---
st.subheader("Final Signal")
if score >= 3:
    signal = "BUY"
elif score <= 0:
    signal = "SELL"
else:
    signal = "HOLD"

st.metric("Total Score", score)
st.success(f"Trading Signal: {signal}")

# --- METHODOLOGY ---
with st.expander("Methodology", expanded=False):
    st.markdown("""
    **Signal Scorecard Overview**

    Each input is scored based on directional strength:

    - RSI: +1 if > 55, -1 if < 45
    - MACD Histogram: +1 if > 0.2, -1 if < -0.2
    - ROC (3-month): +1 if > 5%, -1 if < -2%
    - Relative Strength: +1 if upward trend, -1 if downward
    - Tech Orders (FRED A34SNO): +1 if > $25B, -1 if < $24B
    - Semi Sales Growth: +1 if positive YoY, -1 if negative
    - Simulated Macro Trend: +1 for strong, 0 neutral, -1 weak

    **Signal Rules**:
    - BUY: Total Score â¥ 3
    - HOLD: Score 1â2
    - SELL: Score â¤ 0
    """)