import yfinance as yf
import streamlit as st

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_price_data():
    soxx = yf.download("SOXX", period="1y", interval="1d")
    spy = yf.download("SPY", period="1y", interval="1d")
    return soxx, spy
