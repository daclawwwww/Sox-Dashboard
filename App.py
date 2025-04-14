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