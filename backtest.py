"""Daily close-to-close backtest of three SOXL strategies.

Signals are computed after each close. Positions begin at the *next* close-to-close
return (shift(1)); they cannot benefit from the return that formed the signal.
Transaction costs are an illustrative 10 bps for each full notional entry/exit,
not an estimate of actual realized costs. Taxes, spreads, intraday execution,
borrow, interest on cash, and market impact are excluded.

Do not optimize thresholds against holdout; these are predeclared rule comparisons.
"""
import numpy as np
import pandas as pd

def score_history(df):
    return (
        (df["SOXX"] > df["MA200"]).astype(int) * 2
        + (df["MA50"] > df["MA200"]).astype(int)
        + (df["RSI14"] > 55).astype(int)
        + (df["MACD_hist"] > 0).astype(int)
        + (df["ROC63"] > 0).astype(int)
        + (df["RS20"] > 0).astype(int)
    ).rename("Score")

def evaluate(df):
    scored = df.copy()
    scored["Score"] = score_history(scored)
    scored["Regime"] = pd.cut(scored["Score"], bins=[-1, 3, 5, 7], labels=["DEFENSIVE", "NEUTRAL", "BULLISH"])
    scored["Favorable"] = (scored["Regime"] == "BULLISH") & (scored["SOXL"] > scored["SOXL_MA20"])
    for horizon in (21, 63):
        scored[f"SOXL_{horizon}d"] = (scored["SOXL"].shift(-(1 + horizon)) /
                                      scored["SOXL"].shift(-1) - 1) * 100
    rows = []
    for horizon in (21, 63):
        ret = f"SOXL_{horizon}d"
        for group, frame in [
            ("All sessions", scored), ("Bullish", scored[scored.Regime == "BULLISH"]),
            ("Neutral", scored[scored.Regime == "NEUTRAL"]),
            ("Defensive", scored[scored.Regime == "DEFENSIVE"]),
            ("Favorable SOXL", scored[scored.Favorable]),
        ]:
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

def strategy_report(scored, side_bps=10):
    """Daily mark-to-market strategy comparison with chronological 70/30 split.

    Cost charged per unit of position turnover, including last holding liquidated.
    A rolling drawdown on trailing SOXX prices is known as of signal close.
    """
    if len(scored) < 500:
        raise ValueError("At least 500 scored sessions required for a useful comparison.")

    close = scored["SOXL"]
    ret = close.pct_change().fillna(0.0)
    longtrend = (scored["SOXX"] > scored["MA200"]) & (scored["MA50"] > scored["MA200"])
    correction = scored["SOXX"] / scored["SOXX"].rolling(63, min_periods=63).max() - 1
    pos = {
        "SOXL Buy & hold": pd.Series(1.0, index=scored.index),
        "Momentum": (scored["Score"] >= 6).astype(float),
        "Dip + trend": (longtrend & correction.between(-0.15, -0.05) & (scored["RSI14"] < 55)).astype(float),
        "Momentum + dip": ((scored["Score"] >= 6) | (longtrend & correction.between(-0.15, -0.05) & (scored["RSI14"] < 55))).astype(float),
    }
    returns = {}
    exposure = {}
    for name, desired in pos.items():
        # The day's SOXL return ends at the closing price; today's signal
        # influences tomorrow's return, never today's.
        held = desired.shift(1).fillna(0)
        turnover = held.diff().abs().fillna(held.abs())
        pnl = held * ret - turnover * side_bps / 10000.0
        returns[name] = pnl
        exposure[name] = held

    daily = pd.DataFrame(returns, index=scored.index)
    positions = pd.DataFrame(exposure, index=scored.index)
    split = int(len(daily) * .7)
    rows = []
    for sample, subset in [("Full period", daily), ("First 70%", daily.iloc[:split]), ("Last 30% (holdout)", daily.iloc[split:])]:
        for name in daily.columns:
            r = subset[name]
            equity = (1 + r).cumprod()
            if len(equity) == 0:
                continue
            years = len(r) / 252
            total = equity.iloc[-1] - 1
            cagr = equity.iloc[-1] ** (1 / years) - 1 if equity.iloc[-1] > 0 else -1
            vol = r.std(ddof=0) * np.sqrt(252)
            sharpe = (r.mean() * 252) / vol if vol > 0 else np.nan
            maxdd = (equity / pd.concat([pd.Series([1.0]), equity.reset_index(drop=True)]).cummax().iloc[1:].to_numpy() - 1).min()
            rows.append({
                "Sample": sample, "Strategy": name,\n                "Start date": str(subset.index[0].date()), "End date": str(subset.index[-1].date()),
                "Total return %": round(total * 100, 1),
                "CAGR %": round(cagr * 100, 1),
                "Max drawdown %": round(maxdd * 100, 1),
                "Sharpe (0% cash rate)": round(sharpe, 2) if np.isfinite(sharpe) else None,
                "Exposure %": round(positions.loc[subset.index, name].mean() * 100, 1),
                "Sessions": len(r),
            })
    return daily, pd.DataFrame(rows)

def event_sample(scored, horizon=21):
    ret_col = f"SOXL_{horizon}d"
    candidates = scored.index[scored["Favorable"] & scored[ret_col].notna()]
    chosen, last_pos = [], -10**9
    for dt in candidates:
        pos = scored.index.get_loc(dt)
        if pos > last_pos + horizon + 1:
            chosen.append(dt)
            last_pos = pos
    sample = scored.loc[chosen, ["Score", "SOXL", ret_col]].copy()
    sample.index.name = "Signal date"
    return sample
