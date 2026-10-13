import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Semiconductor & SOXL Signal Tracker", layout="wide")
st.title("Semiconductor & SOXL Signal Tracker")
st.caption("SOXX drives the sector signal; SOXL is a 3x daily leveraged tactical instrument. Research tool, not an execution system.")

@st.cache_data(ttl=3600)
def get_prices():
    result = {}
    for symbol in ("SOXX", "SOXL", "SPY"):
        df = yf.download(symbol, period="10y", interval="1d", auto_adjust=True, progress=False, threads=False)
        if df.empty:
            raise ValueError(f"No prices returned for {symbol}.")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if "Close" not in df:
            raise ValueError(f"Close column not found for {symbol}.")
        close = pd.to_numeric(df["Close"], errors="coerce").dropna()
        close.index = pd.to_datetime(close.index).tz_localize(None) if close.index.tz is not None else pd.to_datetime(close.index)
        result[symbol] = close
    return pd.DataFrame(result).ffill().dropna()

def calc_rsi(s, n=14):
    change = s.diff()
    up = change.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = (-change.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / down.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.where(down != 0, 100)
    return rsi

def calc_indicators(p):
    s = p["SOXX"]
    macd = s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    rel = (p["SOXX"] / p["SPY"])
    return pd.DataFrame({
        "SOXX": s, "SOXL": p["SOXL"], "SPY": p["SPY"],
        "RSI14": calc_rsi(s),
        "MACD_hist": hist,
        "ROC63": s.pct_change(63) * 100,
        "MA50": s.rolling(50).mean(),
        "MA200": s.rolling(200).mean(),
        "RS20": (rel / rel.shift(20) - 1) * 100,
        "SOXL_MA20": p["SOXL"].rolling(20).mean()
    }).dropna()

try:
    prices = get_prices()
    data = calc_indicators(prices)
    if data.empty:
        raise ValueError("Not enough complete price history to calculate indicators.")
except Exception as exc:
    st.error(f"Market data unavailable: {exc}. No signal generated.")
    st.stop()

last = data.iloc[-1]
asof = data.index[-1].date()
today = pd.Timestamp.now(tz="America/New_York").date()
age = (today - asof).days
st.write(f"**Latest trading observation:** {asof.isoformat()} (end-of-day; prices may be delayed)")
if age > 5:
    st.error(f"PRICE DATA STALE: latest observation is {age} calendar days old. Signal disabled.")
    st.stop()
if age > 3:
    st.warning(f"Latest observation is {age} calendar days old; confirm market holiday/weekend and data availability.")

checks = [
    ("SOXX above 200-day average", last.SOXX > last.MA200, 2),
    ("50-day above 200-day average", last.MA50 > last.MA200, 1),
    ("RSI above 55", last.RSI14 > 55, 1),
    ("MACD histogram positive", last.MACD_hist > 0, 1),
    ("3-month momentum positive", last.ROC63 > 0, 1),
    ("20-day relative performance vs SPY positive", last.RS20 > 0, 1),
]
score = sum(weight for _, passed, weight in checks if passed)
max_score = sum(weight for _, _, weight in checks)
regime = "BULLISH" if score >= 6 else "NEUTRAL" if score >= 4 else "DEFENSIVE"
tactical = "FAVORABLE SETUP" if regime == "BULLISH" and last.SOXL > last.SOXL_MA20 else "WAIT / MONITOR" if regime != "DEFENSIVE" else "HIGH RISK / DEFENSIVE"

a, b, c, d = st.columns(4)
a.metric("SOXX close", f"${last.SOXX:,.2f}")
b.metric("SOXL close", f"${last.SOXL:,.2f}")
c.metric("Sector score", f"{score}/{max_score}")
d.metric("Sector regime", regime)
st.subheader("SOXL Tactical Assessment")
st.write(f"**{tactical}** — SOXL is daily leveraged, so multi-day performance will differ from 3× SOXX due to compounding and volatility drag. This is not a trade instruction.")
st.metric("SOXL 20-day average", f"${last.SOXL_MA20:,.2f}")

st.subheader("Signal Components")
table = pd.DataFrame([
    {"Indicator": name, "Points": weight if passed else 0, "Possible": weight, "Pass": "Yes" if passed else "No"}
    for name, passed, weight in checks
])
st.dataframe(table, use_container_width=True, hide_index=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("SOXX RSI (14)", f"{last.RSI14:.1f}")
c2.metric("MACD histogram", f"{last.MACD_hist:.2f}")
c3.metric("SOXX 63-session return", f"{last.ROC63:+.1f}%")
c4.metric("20-session relative return", f"{last.RS20:+.1f}%")


st.subheader("Strategy Comparison: 10-Year History")
st.caption("Predeclared rules: momentum, correction within an uptrend, combined, and buy-and-hold. Signals at today's close, exposure from the following daily return. Assumed 10 bps per side of turnover. Zero cash yield; taxes and execution costs not captured. Last 30% is a chronological holdout, not a randomized sample.")
try:
    daily_pnl, comparison = strategy_report(evaluate(data)[0])
    st.dataframe(comparison, use_container_width=True, hide_index=True)
    st.line_chart((1 + daily_pnl).cumprod())
except Exception as exc:
    st.warning(f"Strategy backtest unavailable: {exc}")
st.subheader("Historical SOXL Signal Backtest")
from backtest import evaluate, event_sample, strategy_report
historical, stats = evaluate(data)
st.caption("Overlapping forward-return study (not individual trades). Yahoo Finance adjusted daily closes via yfinance. Signals are computed at close t; simulated entry at adjusted close t+1. Exits 21 or 63 sessions later. Returns are percentage changes, not annualized.")
st.dataframe(stats, use_container_width=True, hide_index=True)
events21 = event_sample(historical, 21)
events63 = event_sample(historical, 63)
c1, c2 = st.columns(2)
c1.metric("Non-overlapping 21-session favorable entries", len(events21))
c2.metric("Non-overlapping 63-session favorable entries", len(events63))
if len(events21):
    st.write("**Non-overlapping favorable-entry outcomes (21 sessions)**")
    st.dataframe(events21.tail(20), use_container_width=True)
else:
    st.warning("Not enough favorable-entry observations with complete forward returns.")
with st.expander("How to interpret the backtest"):
    st.markdown("""
    - The table tests conditional forward returns after **every eligible daily signal**; neighboring observations overlap substantially and are **not independent trades**. Do not treat the hit rate as statistically validated.
    - 'All sessions' is the unconditional SOXL comparison using the **same date sample**. This is not a buy-and-hold trading simulation.
    - The non-overlapping favorable-entry sample skips later signals while a prior signal's horizon is open. This reduces overlap, but is sensitive to the initial date and may produce very few observations.
    - Entry is modeled at **the next daily close**, not the next open; real fills, intraday path, costs, spreads, taxes and slippage are not modeled. No short selling is assumed.
    - Indicator parameters and cutoffs were chosen heuristically, without train/test splitting. Results are **in-sample** and may be overfit even when they appear profitable.
    - Ten years of requested data (including indicator warm-up) remains **a limited and regime-dependent sample**. Evaluate longer periods and bear markets before using these results for allocations.
    - Adjusted prices reflect vendor corporate-action adjustments and do not guarantee executable historical fills. Independently verify anomalous bars and split/dividend dates before trading.
    """)

st.subheader("Price History")
st.line_chart(data[["SOXX", "MA50", "MA200"]].tail(252))
st.subheader("SOXL Price History")
st.line_chart(data[["SOXL", "SOXL_MA20"]].tail(126))

st.subheader("Important Data Quality Notes")
st.info("Legacy macro simulation, hardcoded semiconductor sales growth, and historical DRAM/NAND/book-to-bill series have been removed from the actionable score because they were simulated, fixed, or lacked freshness verification. Reintroduce macro inputs only with verifiable dated observations and explicit stale-data rules.")
with st.expander("Methodology and risk"):
    st.markdown("""
    - **Sector score:** 0–7, based only on observed SOXX/SPY price series; above-200-day moving average earns 2 points and each other passing condition earns 1.
    - **Regimes:** 6–7 bullish, 4–5 neutral, 0–3 defensive. Heuristic thresholds are not statistically validated or backtested.
    - **SOXL tactical assessment:** favorable only when sector regime is bullish and SOXL is above its own 20-session average.
    - **Updates:** data are cached for 1 hour and may be delayed; refresh the page to fetch new observations after cache expiry.
    - **Limitations:** no transaction costs, slippage, funding costs, position sizing, or realistic entry/exit modeling. Leveraged ETF path dependence and sharp drawdowns are significant.
    - **Research plan:** add a walk-forward backtest, forward 1/3-month hit rates, volatility filter, and dated live macro series before trading from this score.
    """)
