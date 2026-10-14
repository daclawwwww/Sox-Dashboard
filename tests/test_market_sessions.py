"""Calendar regressions use real schedules and frozen UTC cutoffs, never today."""
import pandas as pd
import pytest

from utils.market_sessions import SessionContext, session_close


@pytest.mark.parametrize("cutoff,expected,next_session,next_close", [
    ("2026-10-13T14:00:00Z", "2026-10-12", "2026-10-13", "2026-10-13T20:00:00Z"),
    ("2026-10-13T19:59:59Z", "2026-10-12", "2026-10-13", "2026-10-13T20:00:00Z"),
    ("2026-10-13T20:00:00Z", "2026-10-13", "2026-10-14", "2026-10-14T20:00:00Z"),
    ("2026-10-14T11:00:00Z", "2026-10-13", "2026-10-14", "2026-10-14T20:00:00Z"),
    # A weekend spanning the spring DST transition changes the UTC close.
    ("2026-03-08T23:00:00Z", "2026-03-06", "2026-03-09", "2026-03-09T20:00:00Z"),
    ("2026-11-01T23:00:00Z", "2026-10-30", "2026-11-02", "2026-11-02T21:00:00Z"),
    # Thanksgiving and its early-close Friday are not generic weekdays.
    ("2026-11-26T22:00:00Z", "2026-11-25", "2026-11-27", "2026-11-27T18:00:00Z"),
    ("2026-11-27T17:59:59Z", "2026-11-25", "2026-11-27", "2026-11-27T18:00:00Z"),
    ("2026-11-27T18:00:00Z", "2026-11-27", "2026-11-30", "2026-11-30T21:00:00Z"),
    ("2026-12-27T12:00:00Z", "2026-12-24", "2026-12-28", "2026-12-28T21:00:00Z"),
    ("2026-07-03T23:00:00Z", "2026-07-02", "2026-07-06", "2026-07-06T20:00:00Z"),
])
def test_latest_completed_session(cutoff, expected, next_session, next_close):
    ctx = SessionContext.create(cutoff)
    assert ctx.expected_latest_completed_session == pd.Timestamp(expected)
    assert ctx.next_session == pd.Timestamp(next_session)
    assert ctx.next_session_close_utc == pd.Timestamp(next_close)
    assert ctx.expected_latest_completed_close_utc <= ctx.cutoff_utc < ctx.next_session_close_utc


def test_dst_and_early_close_timestamps():
    assert session_close("2026-03-06") == pd.Timestamp("2026-03-06T21:00:00Z")
    assert session_close("2026-03-09") == pd.Timestamp("2026-03-09T20:00:00Z")
    assert session_close("2026-12-24") == pd.Timestamp("2026-12-24T18:00:00Z")


def test_lag_counts_sessions_not_calendar_days():
    ctx = SessionContext.create("2026-11-30T12:00:00Z")
    assert ctx.lag_sessions("2026-11-27") == 0
    assert ctx.lag_sessions("2026-11-25") == 1
    assert ctx.metadata("2026-11-25")["status"] == "fallback"
    with pytest.raises(ValueError, match="Not an exchange session"):
        ctx.lag_sessions("2026-11-26")
    with pytest.raises(ValueError, match="Unfinished or future"):
        ctx.lag_sessions("2026-11-30")


@pytest.mark.parametrize("cutoff", ["2026-10-13", "2026-10-13T14:00:00", pd.NaT])
def test_cutoff_requires_timezone(cutoff):
    with pytest.raises(ValueError, match="aware"):
        SessionContext.create(cutoff)


def test_aware_cutoff_is_converted_to_utc():
    ctx = SessionContext.create("2026-10-13T10:00:00-04:00")
    assert ctx.cutoff_utc == pd.Timestamp("2026-10-13T14:00:00Z")
