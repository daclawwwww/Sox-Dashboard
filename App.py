import streamlit as st
st.set_page_config(page_title="SOXX Momentum Dashboard", layout="wide")

import yfinance as yf
import pandas as pd
from indicators.rsi import compute_rsi
from indicators.macd import compute_macd
from indicators.roc import compute_roc
from indicators.relative_strength import compute_relative_strength
from utils.data_loader import load_price_data
from utils.dram_loader import (
    load_dram_prices,
    get_latest_dram_price,
    calculate_dram_score,
    calculate_dram_trend_score
)
from utils.book_to_bill_loader import (
    load_book_to_bill,
    get_latest_b2b,
    calculate_b2b_score
)
from macro.semiconductor_leads import get_macro_signal_score
from macro.pmi_fetcher import get_ism_pmi
from macro.capex_proxy import get_capex_proxy
st.title("SOXX Momentum Dashboard")

score = 0
signal = "N/A"

with st.spinner("Loading market data..."):
    df_soxx, df_spy = load_price_data()

try:
    close = df_soxx['Close'].dropna()
    spy_close = df_spy['Close'].dropna()
    rsi = compute_rsi(close).dropna()
    macd_hist = compute_macd(close).dropna()
    roc_3m = compute_roc(close, 63).dropna()
    relative_strength = compute_relative_strength(close, spy_close).dropna()

    latest_rsi = round(float(rsi.iloc[-1]), 2) if not rsi.empty else "N/A"
    latest_macd = round(float(macd_hist.iloc[-1]), 2) if not macd_hist.empty else "N/A"
    latest_roc = round(float(roc_3m.iloc[-1]), 2) if not roc_3m.empty else "N/A"
    latest_rel = round(float(relative_strength.iloc[-1]), 2) if not relative_strength.empty else "N/A"
except Exception as e:
    st.error(f"Error calculating indicators: {e}")

st.subheader("Signal Scorecard")

with st.expander("1. Technical Indicators", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("RSI (14)", latest_rsi)
    col2.metric("MACD Histogram", latest_macd)
    col3.metric("3-Month ROC (%)", latest_roc)
    col4.metric("Rel Strength (SOXX/SPY)", latest_rel)

    if isinstance(latest_rsi, float):
        score += 1 if latest_rsi > 55 else -1 if latest_rsi < 45 else 0
        st.write(f"RSI Score: {'+1' if latest_rsi > 55 else '-1' if latest_rsi < 45 else '0'}")

    if isinstance(latest_macd, float):
        score += 1 if latest_macd > 0.2 else -1 if latest_macd < -0.2 else 0
        st.write(f"MACD Score: {'+1' if latest_macd > 0.2 else '-1' if latest_macd < -0.2 else '0'}")

    if isinstance(latest_roc, float):
        score += 1 if latest_roc > 5 else -1 if latest_roc < -2 else 0
        st.write(f"ROC Score: {'+1' if latest_roc > 5 else '-1' if latest_roc < -2 else '0'}")

    if isinstance(latest_rel, float):
        try:
            rel_trend = relative_strength.tail(5).diff().mean()
            if rel_trend > 0.001:
                score += 1
                st.write("Rel Strength Score: +1")
            elif rel_trend < -0.001:
                score -= 1
                st.write("Rel Strength Score: -1")
            else:
                st.write("Rel Strength Score: 0")
        except:
            st.write("Relative strength trend not available.")

with st.expander("2. Macro Indicators", expanded=True):
    pmi_value = get_ism_pmi()
    semi_sales_yoy_growth = 6.5

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
with st.expander("5. CapEx Proxy Score (FRED: NEWORDER)", expanded=True):
    capex = get_capex_proxy()
    if "error" in capex:
        st.warning(f"CapEx fetch error: {capex['error']}")
    else:
        st.metric("Latest NEWORDER", f"{capex['latest']:,}")
        st.write(f"Previous Value: {capex['prev']:,}")
        st.write(f"CapEx Score: {'+1' if capex['score'] == 1 else '-1' if capex['score'] == -1 else '0'}")
        score += capex["score"]
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

with st.expander("3. DRAM Price Score", expanded=True):
    dram_df = load_dram_prices()
    latest_dram_price = get_latest_dram_price(dram_df)
    dram_score = calculate_dram_score(latest_dram_price)
    dram_trend_score = calculate_dram_trend_score(dram_df)

    if latest_dram_price:
        st.metric("Latest DRAM Price", f"${latest_dram_price:.3f}")
        st.write(f"DRAM Price Score: {'+1' if dram_score == 1 else '-1' if dram_score == -1 else '0'}")
        st.write(f"DRAM Trend Score (4-week): {'+1' if dram_trend_score == 1 else '-1' if dram_trend_score == -1 else '0'}")
    else:
        st.warning("DRAM price data unavailable.")

    score += dram_score + dram_trend_score

with st.expander("4. SEMI Book-to-Bill Score", expanded=True):
    b2b_df = load_book_to_bill()
    latest_b2b = get_latest_b2b(b2b_df)
    b2b_score = calculate_b2b_score(latest_b2b)

    if latest_b2b:
        st.metric("Latest Book-to-Bill Ratio", f"{latest_b2b:.2f}")
        st.write(f"Book-to-Bill Score: {'+1' if b2b_score == 1 else '-1' if b2b_score == -1 else '0'}")
    else:
        st.warning("Book-to-Bill data unavailable.")

    score += b2b_score

st.subheader("Final Signal")
if score >= 3:
    signal = "BUY"
elif score <= 0:
    signal = "SELL"
else:
    signal = "HOLD"

st.metric("Total Score", score)
st.success(f"Trading Signal: {signal}")

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
    - DRAM Price: +1 if > $4.00, -1 if < $3.50
    - DRAM Trend: +1 if rising, -1 if falling
    - SEMI Book-to-Bill: +1 if > 1.05, -1 if < 0.95

    **Signal Rules**:
    - BUY: Total Score â¥ 3
    - HOLD: Score 1â2
    - SELL: Score â¤ 0
    """)