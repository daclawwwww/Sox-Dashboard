"""Publish dated, adjusted end-of-day market snapshot for the static terminal."""
import json
import os
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from backtest import evaluate, strategy_report
from utils.price_quality import validated_close, aligned_prices
from utils.market_sessions import SessionContext, aware_utc, session_close, session_date

TICKERS = ["SOXL", "SOXX", "SPY", "NVDA", "MU", "AMD", "AVGO", "TSM"]
ROOT = Path(__file__).resolve().parent

def fetch(symbol, sessions, diagnostics):
    diagnostics[symbol] = {
        "status": "loading", "error": None,
        "latest_seen_session": None, "latest_valid_session": None,
        "latest_completed_valid_session": None, "missing_completed_sessions": [],
        "excluded_in_progress_sessions": [], "omitted_from_watchlist": True,
    }
    try:
        data = yf.download(symbol, period="10y", interval="1d", auto_adjust=True,
                           progress=False, threads=False)
        prices = validated_close(data, symbol, sessions=sessions,
                                 allow_missing_latest=True, diagnostics=diagnostics)
    except Exception as exc:
        diagnostics[symbol].update(status="error", error=str(exc))
        raise
    diagnostics[symbol].update(status="ok", error=None)
    return prices


def guard_snapshot_regression(path, candidate_asof, cutoff_utc):
    """Protect finalized newer data; permit repairing a legacy intraday label.

    A newer date by itself is insufficient: older publishers sometimes labeled
    an unfinished daily bar as EOD. Independently compare the prior generated
    time and pre-fetch cutoff with the calendar's actual session close. A legacy
    generated timestamp alone cannot prove when its source data was downloaded.
    """
    if not path.exists():
        return
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        prior_date = session_date(previous["asof"])
        if prior_date <= session_date(candidate_asof):
            return
        prior_close = session_close(prior_date)
        generated = aware_utc(previous["generated_utc"])
        if generated < prior_close:
            print(f"Correcting unfinalized prior snapshot {prior_date.date().isoformat()}: "
                  f"generated {generated.isoformat()} before session close {prior_close.isoformat()}")
            return
        recorded = previous["session"]
        cutoff = aware_utc(recorded["cutoff_utc"])
        if not prior_close <= cutoff <= generated <= aware_utc(cutoff_utc):
            raise ValueError("Previous finality timestamps are inconsistent or in the future")
        expected = SessionContext.create(cutoff).metadata(prior_date)
        for key in ("calendar", "timezone", "actual_session", "expected_latest_completed_session",
                    "lag_sessions", "next_session", "status"):
            if recorded[key] != expected[key]:
                raise ValueError(f"Previous session metadata does not match the calendar: {key}")
        for key in ("actual_close_utc", "expected_latest_completed_close_utc", "next_session_close_utc"):
            if aware_utc(recorded[key]) != aware_utc(expected[key]):
                raise ValueError(f"Previous session timestamp does not match the calendar: {key}")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"Previous snapshot finality is unverifiable; replacing with validated completed closes: {exc}")
        return
    reason = (f"Snapshot regression rejected: existing finalized {prior_date.date().isoformat()} "
              f"(close {prior_close.isoformat()}, cutoff {cutoff.isoformat()}, generated {generated.isoformat()}) "
              f"is newer than candidate {session_date(candidate_asof).date().isoformat()}; "
              "existing snapshot preserved")
    print(reason)
    raise ValueError(reason)


def write_snapshot(path, snapshot):
    """Serialize fully before atomically replacing the previously published file."""
    payload = json.dumps(snapshot, allow_nan=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".market-", suffix=".json", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(payload)
        # Recheck immediately before replacement, after potentially slow scoring.
        guard_snapshot_regression(path, snapshot["asof"], snapshot["session"]["cutoff_utc"])
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

def rsi(series, n=14):
    delta = series.diff()
    up = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = -delta.clip(upper=0).ewm(alpha=1/n, adjust=False).mean()
    ratio = up / down.replace(0, np.nan)
    return (100 - 100/(1+ratio)).where(down!=0,100)

def main(cutoff_utc=None):
    # Capture once, before any download. Crossing a close while fetching must
    # never make different symbols use different completion cutoffs.
    sessions = SessionContext.create(cutoff_utc)
    diagnostics = {}
    try:
        raw = {ticker: fetch(ticker, sessions, diagnostics) for ticker in TICKERS}
        common = aligned_prices({k:raw[k] for k in ("SOXX","SOXL","SPY")},
                                sessions=sessions, allow_fallback=True)
    except Exception as exc:
        print("PRICE_SOURCE_DIAGNOSTICS " + json.dumps({"cutoff_utc": sessions.cutoff_utc.isoformat(),
              "expected_latest_completed_session": sessions.expected_latest_completed_session.date().isoformat(),
              "sources": diagnostics, "rejected_reason": str(exc)}, sort_keys=True))
        raise
    for ticker, prices in raw.items():
        diagnostics[ticker]["omitted_from_watchlist"] = (
            common.index[-1] not in prices.index or len(prices.loc[:common.index[-1]]) < 64)
    print("PRICE_SOURCE_DIAGNOSTICS " + json.dumps({"session": common.attrs["session"],
                                                  "sources": diagnostics}, sort_keys=True))
    # No forward-filling missing observations: an absent bar is not a flat return.
    if len(common)<600:
        raise ValueError("Too little SOXX/SOXL/SPY overlapping history")
    s=common["SOXX"]
    macd=s.ewm(span=12,adjust=False).mean()-s.ewm(span=26,adjust=False).mean()
    rel=common["SOXX"]/common["SPY"]
    df=pd.DataFrame({
        "SOXX":s,"SOXL":common["SOXL"],"SPY":common["SPY"],
        "RSI14":rsi(s),"MACD_hist":macd-macd.ewm(span=9,adjust=False).mean(),
        "ROC63":s.pct_change(63)*100,"MA50":s.rolling(50).mean(),
        "MA200":s.rolling(200).mean(),"RS20":(rel/rel.shift(20)-1)*100,
        "SOXL_MA20":common["SOXL"].rolling(20).mean(),
    }).dropna()
    scored,_=evaluate(df)
    latest=scored.iloc[-1]
    checks=[
        ("SOXX above 200-day MA",latest.SOXX>latest.MA200,2),
        ("50-day MA above 200-day MA",latest.MA50>latest.MA200,1),
        ("RSI above 55",latest.RSI14>55,1),
        ("MACD histogram positive",latest.MACD_hist>0,1),
        ("63-day momentum positive",latest.ROC63>0,1),
        ("20-day relative performance vs SPY positive",latest.RS20>0,1),
    ]
    score=sum(weight for _,passes,weight in checks if passes)
    regime="BULLISH" if score>=6 else "NEUTRAL" if score>=4 else "DEFENSIVE"
    drawdown=latest.SOXX/s.tail(63).max()-1
    dip=latest.SOXX>latest.MA200 and latest.MA50>latest.MA200 and -.15<=drawdown<=-.05 and latest.RSI14<55
    if regime=="BULLISH" and latest.SOXL>latest.SOXL_MA20:
        opportunity="MOMENTUM WATCH"
        comment="SOXX momentum is strong and SOXL is above its 20-day moving average. Evaluate risk before entry."
    elif dip:
        opportunity="PULLBACK WATCH"
        comment="SOXX has corrected 5–15% from its 63-session high while its long-term trend remains constructive. Not an automatic buy."
    else:
        opportunity="WAIT / MONITOR"
        comment="Predeclared momentum and pullback entry conditions are not met."
    watch=[]
    for ticker, prices in raw.items():
        recent=prices.loc[:common.index[-1]].dropna()
        # A watchlist row shares the snapshot's asof date; omit lagging symbols.
        if len(recent)<64 or recent.index[-1] != common.index[-1]:continue
        watch.append(dict(ticker=ticker,close=round(float(recent.iloc[-1]),2),
            day_pct=round(float((recent.iloc[-1]/recent.iloc[-2]-1)*100),2),
            week_pct=round(float((recent.iloc[-1]/recent.iloc[-6]-1)*100),2),
            drawdown_63_pct=round(float((recent.iloc[-1]/recent.tail(63).max()-1)*100),2)))
    _,report=strategy_report(scored)
    backtest=[]
    for row in report.to_dict(orient="records"):
        backtest.append(dict(sample=row["Sample"],strategy=row["Strategy"],
            start_date=row["Start date"],end_date=row["End date"],total_return_pct=row["Total return %"],
            cagr_pct=row["CAGR %"],max_drawdown_pct=row["Max drawdown %"],
            # Pandas coerces None to NaN in mixed numeric columns. A strategy
            # with no return volatility has no defined Sharpe, not a JSON NaN.
            sharpe=(float(row["Sharpe (0% cash rate)"]) if pd.notna(row["Sharpe (0% cash rate)"]) else None),
            exposure_pct=row["Exposure %"]))
    snapshot=dict(asof=common.index[-1].date().isoformat(),
        generated_utc=sessions.cutoff_utc.isoformat(),
        session=common.attrs["session"],source_diagnostics=diagnostics,
        source="yfinance adjusted daily closes",watchlist=watch,
        chart={"soxl":[round(float(x),3) for x in common["SOXL"].tail(252)]},
        signal=dict(score=score,regime=regime,opportunity=opportunity,comment=comment,
                    components=[dict(name=name,pass_=bool(passed),weight=weight) for name,passed,weight in checks]),
        backtest=backtest)
    for c in snapshot["signal"]["components"]:
        c["pass"]=c.pop("pass_")
    out=ROOT/"docs"/"market.json"
    write_snapshot(out, snapshot)
    print(f"Published {out} for {snapshot['asof']} with {len(backtest)} strategy rows.")
    return snapshot

if __name__=="__main__":
    main()
