"""Publish dated, adjusted end-of-day market snapshot for the static terminal."""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from backtest import evaluate, strategy_report

TICKERS = ["SOXL", "SOXX", "SPY", "NVDA", "MU", "AMD", "AVGO", "TSM"]
ROOT = Path(__file__).resolve().parent

def fetch(symbol):
    data = yf.download(symbol, period="10y", interval="1d", auto_adjust=True,
                       progress=False, threads=False)
    if data.empty:
        raise ValueError(f"No historical prices available for {symbol}")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    s = pd.to_numeric(data["Close"], errors="coerce").dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None) if s.index.tz is not None else pd.to_datetime(s.index)
    return s[~s.index.duplicated(keep="last")].sort_index()

def rsi(series, n=14):
    delta = series.diff()
    up = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = -delta.clip(upper=0).ewm(alpha=1/n, adjust=False).mean()
    ratio = up / down.replace(0, np.nan)
    return (100 - 100/(1+ratio)).where(down!=0,100)

def main():
    raw = {ticker: fetch(ticker) for ticker in TICKERS}
    common = pd.concat({k:raw[k] for k in ("SOXX","SOXL","SPY")}, axis=1).dropna()
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
        if len(recent)<64:continue
        watch.append(dict(ticker=ticker,close=round(float(recent.iloc[-1]),2),
            day_pct=round(float((recent.iloc[-1]/recent.iloc[-2]-1)*100),2),
            week_pct=round(float((recent.iloc[-1]/recent.iloc[-6]-1)*100),2),
            drawdown_63_pct=round(float((recent.iloc[-1]/recent.tail(63).max()-1)*100),2)))
    _,report=strategy_report(scored)
    backtest=[]
    for row in report.to_dict(orient="records"):
        backtest.append(dict(sample=row["Sample"],strategy=row["Strategy"],\n            start_date=row["Start date"],end_date=row["End date"],total_return_pct=row["Total return %"],
            cagr_pct=row["CAGR %"],max_drawdown_pct=row["Max drawdown %"],
            sharpe=row["Sharpe (0% cash rate)"],exposure_pct=row["Exposure %"]))
    snapshot=dict(asof=common.index[-1].date().isoformat(),
        generated_utc=datetime.now(timezone.utc).isoformat(),
        source="yfinance adjusted daily closes",watchlist=watch,
        chart={"soxl":[round(float(x),3) for x in common["SOXL"].tail(252)]},
        signal=dict(score=score,regime=regime,opportunity=opportunity,comment=comment,
                    components=[dict(name=name,pass_=bool(passed),weight=weight) for name,passed,weight in checks]),
        backtest=backtest)
    for c in snapshot["signal"]["components"]:
        c["pass"]=c.pop("pass_")
    out=ROOT/"docs"/"market.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(snapshot,allow_nan=False,indent=2)+"\n",encoding="utf-8")
    print(f"Published {out} for {snapshot['asof']} with {len(backtest)} strategy rows.")

if __name__=="__main__":
    main()
