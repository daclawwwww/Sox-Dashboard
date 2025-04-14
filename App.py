from macro.semiconductor_leads import get_macro_signal_score
import streamlit as st
import yfinance as yf
import pandas as pd
from indicators.rsi import compute_rsi
from indicators.macd import compute_macd
from indicators.roc import compute_roc
from indicators.relative_strength import compute_relative_strength
from utils.data_loader import load_price_data

st.title("SOXX Momentum Dashboard")

# Load Data
df_soxx, df_spy = load_price_data()

# Show raw data to confirm loading
st.subheader("Raw SOXX Data (last 5 rows)")
st.write(df_soxx.tail())

# Check if 'Close' column exists
if 'Close' in df_soxx.columns:
    st.subheader("SOXX Price Chart")
    st.line_chart(df_soxx['Close'])
else:
    st.error("The 'Close' column is missing. Data may have failed to load.")

# Indicators Section
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

    # Use safe fallback if series is still empty
    latest_rsi = float(round(rsi.iloc[-1], 2)) if not rsi.empty else "N/A"
    latest_macd = float(round(macd_hist.iloc[-1], 2)) if not macd_hist.empty else "N/A"
    latest_roc = float(round(roc_3m.iloc[-1], 2)) if not roc_3m.empty else "N/A"
    latest_rel = float(round(relative_strength.iloc[-1], 2)) if not relative_strength.empty else "N/A"

    st.metric("RSI (14)", latest_rsi)
    st.metric("MACD Histogram", latest_macd)
    st.metric("3-Month ROC (%)", latest_roc)
    st.metric("SOXX/SPY Relative Strength", latest_rel)

except Exception as e:
    st.error(f"Error computing indicators: {e}")
    st.subheader("Signal Score")

# Simulated Semiconductor Sales Growth (can be replaced with CSV/API later)
semi_sales_yoy_growth = 6.5  # Example: +6.5% YoY

# ---- Scoring ----
score = 0

# RSI scoring
if isinstance(latest_rsi, float):
    score += 1 if latest_rsi > 55 else -1 if latest_rsi < 45 else 0

# MACD scoring
if isinstance(latest_macd, float):
    score += 1 if latest_macd > 0.2 else -1 if latest_macd < -0.2 else 0

# ROC scoring
if isinstance(latest_roc, float):
    score += 1 if latest_roc > 5 else -1 if latest_roc < -2 else 0

# Relative Strength scoring (use trend of last 5 days)
try:
    rel_trend = relative_strength.tail(5).diff().mean()
    if rel_trend > 0.001:
        score += 1
    elif rel_trend < -0.001:
        score -= 1
except:
    pass  # Keep score unchanged if data is bad

# Semi Sales scoring
if semi_sales_yoy_growth > 0:
    score += 1
elif semi_sales_yoy_growth < 0:
    score -= 1
st.subheader("Macro Indicator Simulation")

macro_trend = st.radio("Simulate macro conditions:", ["strong", "neutral", "weak"], index=1)
macro_result = get_macro_signal_score(simulate=macro_trend)

st.write("**Macro Indicator Scores:**")
for k, v in macro_result["indicators"].items():
    st.write(f"{k}: {'+1' if v == 1 else '0' if v == 0 else '-1'}")

st.write(f"**Macro Composite Score:** {macro_result['macro_score']}")

# Add to total signal score
score += macro_result["macro_score"]

# ---- Final Signal ----
if score >= 3:
    signal = "BUY"
elif score <= 0:
    signal = "SELL"
else:
    signal = "HOLD"

st.write(f"**Total Score:** {score}")
st.success(f"**Signal: {signal}**")
    