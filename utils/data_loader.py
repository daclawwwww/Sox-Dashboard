import yfinance as yf
import streamlit as st
import pandas as pd


def normalize_prices(df, ticker):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs(ticker, axis=1, level=-1)
    return df.sort_index()


@st.cache_data(ttl=3600)
def load_price_data():
    # Explicitly retain yfinance's current adjusted-close behavior.
    return tuple(normalize_prices(yf.download(ticker, period="1y", interval="1d", auto_adjust=True), ticker)
                 for ticker in ("SOXX", "SPY"))
