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

    if len(close) == 0 or len(spy_close) == 0:
        raise ValueError("Close prices are empty after dropping NaNs")

    rsi = compute_rsi(close)
    macd_hist = compute_macd(close)
    roc_3m = compute_roc(close, 63)
    relative_strength = compute_relative_strength(close, spy_close)

    st.metric("RSI (14)", float(round(rsi.dropna().iloc[-1], 2)))
    st.metric("MACD Histogram", float(round(macd_hist.dropna().iloc[-1], 2)))
    st.metric("3-Month ROC (%)", float(round(roc_3m.dropna().iloc[-1], 2)))
    st.metric("SOXX/SPY Relative Strength", float(round(relative_strength.dropna().iloc[-1], 2)))

except Exception as e:
    st.error(f"Error computing indicators: {e}")