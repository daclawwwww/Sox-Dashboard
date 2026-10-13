"""Validate observed daily closes before scoring; never invent missing bars."""
import numpy as np
import pandas as pd


def validated_close(data, symbol, as_of=None):
    if data.empty:
        raise ValueError(f"No prices returned for {symbol}")
    if isinstance(data.columns, pd.MultiIndex):
        matches = [c for c in data.columns if "Close" in c and symbol in c]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous or missing Close column for {symbol}")
        close = data[matches[0]].copy()
    else:
        if "Close" not in data or list(data.columns).count("Close") != 1:
            raise ValueError(f"Ambiguous or missing Close column for {symbol}")
        close = data["Close"].copy()
    if not isinstance(close.index, pd.DatetimeIndex):
        raise ValueError(f"Dated prices required for {symbol}")
    close.index = close.index.tz_localize(None).normalize()
    if close.index.isna().any() or close.index.duplicated().any():
        raise ValueError(f"Invalid or duplicate price dates for {symbol}")
    close = pd.to_numeric(close, errors="coerce").sort_index()
    if close.isna().any() or not np.isfinite(close).all() or (close <= 0).any():
        raise ValueError(f"Non-finite or non-positive prices for {symbol}")
    require_fresh_date(close.index[-1], as_of=as_of)
    return close.rename(symbol)


def require_fresh_date(date, as_of=None):
    today = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now(tz="America/New_York")
    age = (today.tz_localize(None).normalize() - pd.Timestamp(date).tz_localize(None).normalize()).days
    if age < 0:
        raise ValueError("Future-dated price observation")
    if age > 5:
        raise ValueError(f"Stale price observation: {age} calendar days old (limit 5)")
    return age


def aligned_prices(raw, as_of=None):
    """Require a common latest observed date, with no forward-filling."""
    if not raw or any(s.empty for s in raw.values()):
        raise ValueError("Missing price history")
    latest = {s.index[-1] for s in raw.values()}
    if len(latest) != 1:
        raise ValueError("Latest price dates do not match across required symbols")
    common = pd.concat(raw, axis=1).dropna()
    if common.empty:
        raise ValueError("No overlapping price history")
    require_fresh_date(common.index[-1], as_of=as_of)
    return common
