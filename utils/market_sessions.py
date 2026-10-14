"""US regular-equity sessions, evaluated against one timezone-aware run cutoff.

The terminal's NYSE/Arca and Nasdaq listings share this regular-session calendar.
Calendar schedules include exchange holidays, special closes and DST; a weekday
or a date label alone is never evidence that a daily bar has finished.
"""
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
import pandas_market_calendars as mcal

CALENDAR = "NYSE"
TIMEZONE = "America/New_York"
MAX_FALLBACK_SESSIONS = 1


def utc_now():
    return pd.Timestamp.now(tz="UTC")


def aware_utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("An aware timestamp is required for the run cutoff")
    return stamp.tz_convert("UTC")


def session_date(value):
    """Normalize a daily session label without changing its calendar date."""
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("Invalid session date")
    return stamp.tz_localize(None).normalize()


@lru_cache(maxsize=128)
def _schedule(start, end):
    # Official API: schedule's timestamps are UTC; special closes are enabled.
    return mcal.get_calendar(CALENDAR).schedule(start_date=start, end_date=end)


def exchange_schedule(start, end):
    return _schedule(session_date(start).date().isoformat(),
                     session_date(end).date().isoformat()).copy()


def session_close(date):
    date = session_date(date)
    schedule = exchange_schedule(date, date)
    if date not in schedule.index:
        raise ValueError(f"Not an exchange session: {date.date().isoformat()}")
    return schedule.loc[date, "market_close"]


@dataclass(frozen=True)
class SessionContext:
    cutoff_utc: pd.Timestamp
    expected_latest_completed_session: pd.Timestamp
    expected_latest_completed_close_utc: pd.Timestamp
    next_session: pd.Timestamp
    next_session_close_utc: pd.Timestamp

    @classmethod
    def create(cls, cutoff_utc=None):
        cutoff = aware_utc(utc_now() if cutoff_utc is None else cutoff_utc)
        date = cutoff.tz_convert(TIMEZONE).tz_localize(None).normalize()
        schedule = exchange_schedule(date - pd.Timedelta(days=40), date + pd.Timedelta(days=40))
        completed = schedule[schedule.market_close <= cutoff]
        upcoming = schedule[schedule.market_close > cutoff]
        if completed.empty or upcoming.empty:
            raise ValueError("Unable to determine completed and next exchange sessions")
        return cls(cutoff, completed.index[-1], completed.market_close.iloc[-1],
                   upcoming.index[0], upcoming.market_close.iloc[0])

    @property
    def exchange_date(self):
        return self.cutoff_utc.tz_convert(TIMEZONE).tz_localize(None).normalize()

    def lag_sessions(self, actual):
        actual = session_date(actual)
        if session_close(actual) > self.cutoff_utc:
            raise ValueError(f"Unfinished or future session: {actual.date().isoformat()}")
        schedule = exchange_schedule(actual, self.expected_latest_completed_session)
        return len(schedule.index[schedule.index > actual])

    def metadata(self, actual):
        actual = session_date(actual)
        lag = self.lag_sessions(actual)
        return {
            "calendar": CALENDAR,
            "timezone": TIMEZONE,
            "cutoff_utc": self.cutoff_utc.isoformat(),
            "expected_latest_completed_session": self.expected_latest_completed_session.date().isoformat(),
            "expected_latest_completed_close_utc": self.expected_latest_completed_close_utc.isoformat(),
            "actual_session": actual.date().isoformat(),
            "actual_close_utc": session_close(actual).isoformat(),
            "lag_sessions": lag,
            "next_session": self.next_session.date().isoformat(),
            "next_session_close_utc": self.next_session_close_utc.isoformat(),
            "status": "fallback" if lag else "current",
            "fallback_reason": (f"Latest completed session {self.expected_latest_completed_session.date().isoformat()} "
                                "is missing from one or more required symbol histories; "
                                f"using the last common completed session {actual.date().isoformat()}.") if lag else None,
        }
