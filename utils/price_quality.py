"""Validate observed daily closes before scoring; never invent missing bars."""
import numpy as np
import pandas as pd
from utils.market_sessions import MAX_FALLBACK_SESSIONS, exchange_schedule


def validated_close(data, symbol, as_of=None, *, sessions=None,
                    allow_missing_latest=False, diagnostics=None):
    """Validate raw observations, with optional completed-session enforcement.

    Missing values are never filled. The sole opt-in exception to rejecting a
    missing close is an absent value at the expected latest completed session;
    that row is excluded and an explicitly stale fallback may be used instead.
    Invalid historical prices, infinities, zero and negative values still fail.
    """
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
    close = close.sort_index()
    if sessions is not None:
        close = _completed_closes(close, symbol, sessions, allow_missing_latest, diagnostics)
    close = pd.to_numeric(close, errors="coerce")
    if close.isna().any() or not np.isfinite(close).all() or (close <= 0).any():
        raise ValueError(f"Non-finite or non-positive prices for {symbol}")
    require_fresh_date(close.index[-1], as_of=as_of, sessions=sessions,
                       allow_fallback=allow_missing_latest)
    return close.rename(symbol)


def _completed_closes(close, symbol, sessions, allow_missing_latest, diagnostics):
    numeric = pd.to_numeric(close, errors="coerce")
    valid = numeric.notna() & np.isfinite(numeric) & (numeric > 0)
    seen = close.index[-1].date().isoformat()
    info = {
        "latest_seen_session": seen,
        "latest_valid_session": numeric[valid].index[-1].date().isoformat() if valid.any() else None,
        "latest_completed_valid_session": None,
        "missing_completed_sessions": [],
        "excluded_in_progress_sessions": [],
        "omitted_from_watchlist": False,
    }
    if diagnostics is not None:
        diagnostics[symbol] = info
    if close.index[-1] > sessions.exchange_date:
        raise ValueError(f"Future-dated price observation for {symbol}: {seen}")
    schedule = exchange_schedule(close.index[0], sessions.exchange_date)
    invalid_dates = close.index.difference(schedule.index)
    if len(invalid_dates):
        raise ValueError(f"Non-session price observation for {symbol}: {invalid_dates[0].date().isoformat()}")
    completed_dates = schedule.index[schedule.market_close <= sessions.cutoff_utc]
    in_progress = close.index.difference(completed_dates)
    info["excluded_in_progress_sessions"] = [d.date().isoformat() for d in in_progress]
    completed_valid = numeric[valid & numeric.index.isin(completed_dates)]
    if not completed_valid.empty:
        info["latest_completed_valid_session"] = completed_valid.index[-1].date().isoformat()
    info["missing_completed_sessions"] = [d.date().isoformat() for d in completed_dates.difference(completed_valid.index)]
    # Drop unfinished bars before inspecting their price: NaN/partial prints on
    # today's still-open session are not part of an end-of-day calculation.
    close = close.loc[close.index.isin(completed_dates)]
    if allow_missing_latest:
        missing_latest = close.isna() & (close.index == sessions.expected_latest_completed_session)
        close = close.loc[~missing_latest]
    if close.empty:
        raise ValueError(f"No completed prices returned for {symbol}")
    return close


def require_fresh_date(date, as_of=None, *, sessions=None, allow_fallback=False):
    if sessions is not None:
        lag = sessions.lag_sessions(date)
        limit = MAX_FALLBACK_SESSIONS if allow_fallback else 0
        if lag > limit:
            raise ValueError(f"Stale price observation: {lag} completed sessions behind (limit {limit})")
        return lag
    today = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now(tz="America/New_York")
    age = (today.tz_localize(None).normalize() - pd.Timestamp(date).tz_localize(None).normalize()).days
    if age < 0:
        raise ValueError("Future-dated price observation")
    if age > 5:
        raise ValueError(f"Stale price observation: {age} calendar days old (limit 5)")
    return age


def aligned_prices(raw, as_of=None, *, sessions=None, allow_fallback=False):
    """Require an observed common close, with explicit bounded fallback only."""
    if not raw or any(s.empty for s in raw.values()):
        raise ValueError("Missing price history")
    latest = {s.index[-1] for s in raw.values()}
    if len(latest) != 1 and not (sessions is not None and allow_fallback):
        raise ValueError("Latest price dates do not match across required symbols")
    common = pd.concat(raw, axis=1).dropna()
    if common.empty:
        raise ValueError("No overlapping price history")
    require_fresh_date(common.index[-1], as_of=as_of, sessions=sessions, allow_fallback=allow_fallback)
    if sessions is not None:
        common.attrs["session"] = sessions.metadata(common.index[-1])
    return common
