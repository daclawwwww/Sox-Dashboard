"""Historical diagnostics for the SOXX-driven SOXL signal.

Uses prices that the main Streamlit app already loaded from yfinance.
All signals use information known at the close on signal date t.
Entry is the *next session's adjusted close* (t+1), NOT the signal close.
Exits are adjusted closes 21 or 63 sessions after entry.
This is a diagnostic of forward conditional outcomes, not a live-tradable
execution model or an independently verified realized P&L track record.
"""
import pandas as pd

WEIGHTS = {
    "Price > MA200": 2,
    "MA50 > MA200": 1,
    "RSI14 > 55": 1,
    "MACD histogram > 0": 1,
    "ROC63 > 0": 1,
    "SOXX/SPY RS20 > 0": 1,
}

def score_history(df):
    checks = {
        "Price > MA200": df["SOXX"] > df["MA200"],
        "MA50 > MA200": df["MA50"] > df["MA200"],
        "RSI14 > 55": df["RSI14"] > 55,
        "MACD histogram > 0": df["MACD_hist"] > 0,
        "ROC63 > 0": df["ROC63"] > 0,
        "SOXX/SPY RS20 > 0": df["RS20"] > 0,
    }
    scores = sum(passed.astype(int) * WEIGHTS[name] for name, passed in checks.items())
    return scores.rename("Score")

def evaluate(df):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    scored = df.copy()
    scored["Score"] = score_history(scored)
    scored["Regime"] = pd.cut(scored["Score"], bins=[-1, 3, 5, 7],
                              labels=["DEFENSIVE", "NEUTRAL", "BULLISH"])
    scored["Favorable"] = (scored["Regime"] == "BULLISH") & (scored["SOXL"] > scored["SOXL_MA20"])
    # Close-to-close entry after signal is known; forward horizon after entry.
    for horizon in (21, 63):
        scored[f"SOXL_{horizon}d"] = (scored["SOXL"].shift(-(1 + horizon)) /
                                      scored["SOXL"].shift(-1) - 1) * 100
        scored[f"SOXX_{horizon}d"] = (scored["SOXX"].shift(-(1 + horizon)) /
                                      scored["SOXX"].shift(-1) - 1) * 100
    rows = []
    for horizon in (21, 63):
        ret = f"SOXL_{horizon}d"
        for group, frame in [("All sessions", scored), ("Bullish", scored[scored.Regime == "BULLISH"]),
                             ("Neutral", scored[scored.Regime == "NEUTRAL"]),
                             ("Defensive", scored[scored.Regime == "DEFENSIVE"]),
                             ("Favorable SOXL", scored[scored.Favorable])]:
            valid = frame[ret].dropna()
            rows.append({
                "Horizon": f"{horizon} sessions", "Group": group,
                "Observations": len(valid),
                "Mean SOXL %": round(valid.mean(), 2) if len(valid) else None,
                "Median SOXL %": round(valid.median(), 2) if len(valid) else None,
                "Positive %": round(100 * (valid > 0).mean(), 1) if len(valid) else None,
                "Worst %": round(valid.min(), 2) if len(valid) else None,
            })
    return scored, pd.DataFrame(rows)

def event_sample(scored, horizon=21):
    """Conservative, non-overlapping event-date sample to reduce dependence."""
    ret_col = f"SOXL_{horizon}d"
    candidates = scored.index[scored["Favorable"] & scored[ret_col].notna()]
    chosen = []
    last_pos = -10**9
    for dt in candidates:
        pos = scored.index.get_loc(dt)
        if pos > last_pos + horizon + 1:
            chosen.append(dt)
            last_pos = pos
    sample = scored.loc[chosen, ["Score", "SOXL", ret_col]].copy()
    sample.index.name = "Signal date"
    return sample
