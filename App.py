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

# Load Data
with st.spinner("Loading price data..."):
    df_soxx, df_spy = load_price_data()

# Show raw data
st.subheader("Raw SOXX Data (last 5 rows)")
st.write(df_soxx.tail())

# Price Chart
if 'Close' in df_soxx.columns:
    st.subheader("SOXX Price Chart")
    st.line_chart(df_soxx['Close'])
else:
    st.error("The 'Close' column is missing. Data may have failed to load.")

# Momentum Indicators
st.subheader("Momentum Indicators")

try:
    close = df_soxx['Close'].dropna()
    spy_close = df_spy['Close'].dropna()

    if close.empty or spy_close.empty:
        raise ValueError("Price data is missing or empty.")

    rsi = compute_rsi(close).dropna()
    macd_hist = compute_macd(close).dropna()
    roc_3m = compute_roc(close, 63).dropna()
    relative_strength = compute_relative_strength(close, spy_close).dropna()

    latest_rsi = round(float(rsi.iloc[-1]), 2) if not rsi.empty else "N/A"
    latest_macd = round(float(macd_hist.iloc[-1]), 2) if not macd_hist.empty else "N/A"
    latest_roc = round(float(roc_3m.iloc[-1]), 2) if not roc_3m.empty else "N/A"
    latest_rel = round(float(relative_strength.iloc[-1]), 2) if not relative_strength.empty else "N/A"

    st.metric("RSI (14)", latest_rsi)
    st.metric("MACD Histogram", latest_macd)
    st.metric("3-Month ROC (%)", latest_roc)
    st.metric("SOXX/SPY Relative Strength", latest_rel)

except Exception as e:
    st.error(f"Error computing indicators: {e}")

# ---- Scoring ----
st.subheader("Signal Score")
score = 0

# Technical scoring
if isinstance(latest_rsi, float):
    score += 1 if latest_rsi > 55 else -1 if latest_rsi < 45 else 0

if isinstance(latest_macd, float):
    score += 1 if latest_macd > 0.2 else -1 if latest_macd < -0.2 else 0

if isinstance(latest_roc, float):
    score += 1 if latest_roc > 5 else -1 if latest_roc < -2 else 0

# Relative strength trend
try:
    rel_trend = relative_strength.tail(5).diff().mean()
    if rel_trend > 0.001:
        score += 1
    elif rel_trend < -0.001:
        score -= 1
except:
    pass

# Simulated Semiconductor Sales Growth (placeholder)
semi_sales_yoy_growth = 6.5
if semi_sales_yoy_growth > 0:
    score += 1
elif semi_sales_yoy_growth < 0:
    score -= 1

# PMI scoring (live via FRED)
pmi_value = get_ism_pmi()
if isinstance(pmi_value, float):
    st.metric("ISM PMI (NAPMPI)", pmi_value)
    if pmi_value > 50:
        score += 1
    elif pmi_value < 48:
        score -= 1
else:
    st.warning(pmi_value)

# Macro Simulation Score
st.subheader("Macro Indicator Simulation")
macro_trend = st.radio("Simulate macro conditions:", ["strong", "neutral", "weak"], index=1)
macro_result = get_macro_signal_score(simulate=macro_trend)

st.write("**Macro Indicator Scores:**")
for k, v in macro_result["indicators"].items():
    st.write(f"{k}: {'+1' if v == 1 else '0' if v == 0 else '-1'}")

st.write(f"**Macro Composite Score:** {macro_result['macro_score']}")
score += macro_result["macro_score"]

# Final Signal
if score >= 3:
    signal = "BUY"
elif score <= 0:
    signal = "SELL"
else:
    signal = "HOLD"

st.subheader("Final Signal")
st.write(f"**Total Score:** {score}")
st.success(f"**Signal: {signal}**")