"""Date-aware observations. Missing/invalid data never becomes a neutral vote."""
from dataclasses import dataclass
import math
import pandas as pd


@dataclass(frozen=True)
class Observation:
    value: float | None = None
    date: str | None = None
    status: str = "unavailable"
    reason: str = "No observation"
    source: str = ""

    @property
    def eligible(self):
        return self.status == "fresh"


def today(as_of=None):
    return pd.Timestamp(as_of if as_of is not None else pd.Timestamp.now(tz="UTC")).tz_localize(None).normalize()


def latest_observation(series, max_age_days, as_of=None, source=""):
    if series is None or series.empty:
        return Observation(source=source)
    if not isinstance(series.index, pd.DatetimeIndex) and pd.api.types.is_numeric_dtype(series.index):
        return Observation(status="invalid", reason="Observation dates required", source=source)
    dates = pd.to_datetime(series.index, errors="coerce", utc=True).tz_convert(None).normalize()
    if dates.isna().any() or dates.duplicated().any():
        return Observation(status="invalid", reason="Invalid or duplicate observation dates", source=source)
    values = pd.Series(series.to_numpy(), index=dates).sort_index()
    date = values.index[-1]
    stamp = date.date().isoformat()
    try:
        value = float(values.iloc[-1])
    except (TypeError, ValueError):
        value = float("nan")
    if not math.isfinite(value):
        return Observation(date=stamp, status="invalid", reason="Latest value is not finite", source=source)
    age = (today(as_of) - date).days
    if age < 0:
        return Observation(value, stamp, "invalid", "Future-dated observation", source)
    if age > max_age_days:
        return Observation(value, stamp, "stale", f"{age} days old; limit {max_age_days} days", source)
    return Observation(value, stamp, "fresh", f"{age} days old; limit {max_age_days} days", source)


def frame_observation(df, column, max_age_days, as_of=None):
    return latest_observation(df[column] if column in df else None, max_age_days, as_of)


def weekly_trend(df, column, threshold, weeks=4, as_of=None):
    """Require a contiguous weekly window, not just the last five arbitrary rows."""
    obs = frame_observation(df, column, 14, as_of)
    if not obs.eligible or len(df) < weeks + 1:
        return None
    series = df[column].sort_index().tail(weeks + 1)
    dates = pd.to_datetime(series.index)
    if not ((dates[1:] - dates[:-1]).days == 7).all():
        return None
    values = pd.to_numeric(series, errors="coerce")
    if not values.map(lambda v: math.isfinite(v) and v > 0).all():
        return None
    trend = values.diff().mean()
    return 1 if trend > threshold else -1 if trend < -threshold else 0
