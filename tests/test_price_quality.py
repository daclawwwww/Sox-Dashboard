import numpy as np
import pandas as pd
import pytest
from utils.price_quality import validated_close, aligned_prices, require_fresh_date
from utils.market_sessions import SessionContext

AS_OF = "2026-10-13"


def frame(values=(100., 101.), dates=("2026-10-12", "2026-10-13")):
    return pd.DataFrame({"Close": values}, index=pd.to_datetime(dates))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, 0, -1, "bad"])
@pytest.mark.parametrize("position", [0, 1])
def test_invalid_prices_are_never_backfilled(bad, position):
    values = [100, 101]
    values[position] = bad
    with pytest.raises(ValueError, match="Non-finite or non-positive"):
        validated_close(frame(values), "SOXX", AS_OF)


@pytest.mark.parametrize("date,message", [("2026-10-14", "Future"), ("2026-10-07", "Stale")])
def test_date_gates(date, message):
    with pytest.raises(ValueError, match=message):
        validated_close(frame([100], [date]), "SOXX", AS_OF)


def test_five_calendar_days_accepted():
    assert require_fresh_date("2026-10-08", AS_OF) == 5


def test_nullable_missing_value_rejected():
    df = frame().astype("Float64")
    df.iloc[-1, 0] = pd.NA
    with pytest.raises(ValueError, match="Non-finite"):
        validated_close(df, "SOXX", AS_OF)


@pytest.mark.parametrize("index", [[0, 1], ["bad", "date"], pd.to_datetime([None, "2026-10-13"]), pd.to_datetime([AS_OF, AS_OF])])
def test_invalid_dates(index):
    df = frame()
    df.index = index
    with pytest.raises(ValueError):
        validated_close(df, "SOXX", AS_OF)


@pytest.mark.parametrize("reverse", [False, True])
def test_multiindex_selects_requested_symbol(reverse):
    df = frame()
    df.columns = pd.MultiIndex.from_tuples([("SOXX", "Close") if reverse else ("Close", "SOXX")])
    assert validated_close(df, "SOXX", AS_OF).tolist() == [100, 101]
    with pytest.raises(ValueError):
        validated_close(df, "SPY", AS_OF)


def test_unsorted_timezone_closes_keep_exchange_dates():
    df = frame([101, 100], ["2026-10-13", "2026-10-12"])
    df.index = df.index.tz_localize("America/New_York")
    assert validated_close(df, "SOXX", AS_OF).tolist() == [100, 101]


def test_missing_close_empty_and_duplicate_columns():
    for df in [pd.DataFrame(), frame().rename(columns={"Close": "Open"}), pd.concat([frame(), frame()], axis=1)]:
        with pytest.raises(ValueError):
            validated_close(df, "SOXX", AS_OF)


def test_alignment_never_forward_fills():
    a = pd.Series([1., 2., 3.], index=pd.to_datetime(["2026-10-09", "2026-10-12", AS_OF]))
    b = a.drop(pd.Timestamp("2026-10-12"))
    out = aligned_prices({"SOXX": a, "SPY": b}, AS_OF)
    assert out.index.tolist() == b.index.tolist()
    with pytest.raises(ValueError, match="do not match"):
        aligned_prices({"SOXX": a, "SPY": b.iloc[:-1]}, AS_OF)


def test_cached_data_rechecked_and_missing_alignment():
    a = pd.Series([1.], index=pd.to_datetime([AS_OF]))
    with pytest.raises(ValueError, match="Stale"):
        aligned_prices({"SOXX": a}, "2026-10-19")
    for raw in [{}, {"SOXX": pd.Series(dtype=float)}]:
        with pytest.raises(ValueError):
            aligned_prices(raw, AS_OF)


@pytest.mark.parametrize("partial_price", [101., np.nan, np.inf, -1, "bad"])
def test_intraday_bars_excluded_before_price_validation(partial_price):
    ctx = SessionContext.create("2026-10-13T14:00:00Z")
    diagnostics = {}
    out = validated_close(frame([100., partial_price]), "SOXX", sessions=ctx,
                          allow_missing_latest=True, diagnostics=diagnostics)
    assert out.index.tolist() == [pd.Timestamp("2026-10-12")]
    assert out.tolist() == [100.]
    assert diagnostics["SOXX"]["latest_seen_session"] == "2026-10-13"
    assert diagnostics["SOXX"]["latest_completed_valid_session"] == "2026-10-12"
    assert diagnostics["SOXX"]["excluded_in_progress_sessions"] == ["2026-10-13"]
    assert diagnostics["SOXX"]["missing_completed_sessions"] == []


@pytest.mark.parametrize("nullable", [False, True])
def test_missing_expected_latest_close_requires_explicit_fallback(nullable):
    ctx = SessionContext.create("2026-10-14T11:00:00Z")
    df = frame([100., np.nan])
    if nullable:
        df = df.astype("Float64")
    with pytest.raises(ValueError, match="Non-finite"):
        validated_close(df, "SOXX", sessions=ctx)
    diagnostics = {}
    out = validated_close(df, "SOXX", sessions=ctx, allow_missing_latest=True, diagnostics=diagnostics)
    assert out.tolist() == [100.]
    assert diagnostics["SOXX"]["missing_completed_sessions"] == ["2026-10-13"]
    assert diagnostics["SOXX"]["latest_valid_session"] == "2026-10-12"


@pytest.mark.parametrize("bad", [np.nan, np.inf, 0, -1, "bad"])
def test_completed_historical_invalid_prices_still_reject(bad):
    ctx = SessionContext.create("2026-10-14T11:00:00Z")
    with pytest.raises(ValueError, match="Non-finite"):
        validated_close(frame([bad, 101.]), "SOXX", sessions=ctx, allow_missing_latest=True)


@pytest.mark.parametrize("bad", [np.inf, -np.inf, 0, -1, "bad"])
def test_bad_latest_close_is_not_a_missing_value_fallback(bad):
    ctx = SessionContext.create("2026-10-14T11:00:00Z")
    with pytest.raises(ValueError, match="Non-finite"):
        validated_close(frame([100., bad]), "SOXX", sessions=ctx, allow_missing_latest=True)


@pytest.mark.parametrize("date,message", [("2026-10-15", "Future"), ("2026-10-11", "Non-session"), ("2026-07-03", "Non-session")])
def test_session_invalid_dates_are_not_silently_filtered(date, message):
    ctx = SessionContext.create("2026-10-14T11:00:00Z")
    with pytest.raises(ValueError, match=message):
        validated_close(frame([100.], [date]), "SOXX", sessions=ctx, allow_missing_latest=True)


def test_alignment_fallback_is_explicit_and_bounded():
    ctx = SessionContext.create("2026-10-14T11:00:00Z")
    a = pd.Series([99., 100., 101.], index=pd.to_datetime(["2026-10-09", "2026-10-12", "2026-10-13"]))
    with pytest.raises(ValueError, match="do not match"):
        aligned_prices({"SOXX": a, "SPY": a.iloc[:-1]}, sessions=ctx)
    common = aligned_prices({"SOXX": a, "SPY": a.iloc[:-1]}, sessions=ctx, allow_fallback=True)
    assert common.index[-1] == pd.Timestamp("2026-10-12")
    assert common.attrs["session"]["lag_sessions"] == 1
    assert common.attrs["session"]["status"] == "fallback"
    assert common.attrs["session"]["fallback_reason"]
    with pytest.raises(ValueError, match="2 completed sessions"):
        aligned_prices({"SOXX": a, "SPY": a.iloc[:-2]}, sessions=ctx, allow_fallback=True)


def test_cached_session_freshness_rechecked_after_close():
    assert require_fresh_date("2026-10-12", sessions=SessionContext.create("2026-10-13T14:00:00Z")) == 0
    with pytest.raises(ValueError, match="Stale"):
        require_fresh_date("2026-10-12", sessions=SessionContext.create("2026-10-13T20:00:00Z"))
