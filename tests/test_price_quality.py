import numpy as np
import pandas as pd
import pytest
from utils.price_quality import validated_close, aligned_prices, require_fresh_date

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
