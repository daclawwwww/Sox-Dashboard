import streamlit as st
import yfinance as yf
import pandas as pd
from indicators.rsi import compute_rsi
from indicators.macd import compute_macd
from indicators.roc import compute_roc
from indicators.relative_strength import compute_relative_strength
from utils.data_loader import load_price_data

st.title("SOXX Momentum Dashboard")

df_soxx, df_spy = load_price_data()

st.subheader("Price Chart")
st.line_chart(df_soxx['Close'])

st.subheader("Momentum Indicators")

rsi = compute_rsi(df_soxx['Close'])
macd_hist = compute_macd(df_soxx['Close'])
roc_3m = compute_roc(df_soxx['Close'], 63)
relative_strength = compute_relative_strength(df_soxx['Close'], df_spy['Close'])

st.metric("RSI (14)", round(rsi.iloc[-1], 2))
st.metric("MACD Histogram", round(macd_hist.iloc[-1], 2))
st.metric("3-Month ROC (%)", round(roc_3m.iloc[-1], 2))
st.metric("SOXX/SPY Relative Strength", round(relative_strength.iloc[-1], 2))
