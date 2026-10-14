"""Offline UI regressions for the current SOXX/SOXL tracker."""
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
import streamlit as st
import pandas_market_calendars as mcal
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fixed_time():
    with patch("utils.market_sessions.utc_now", return_value=pd.Timestamp("2026-10-14T11:00:00Z")):
        yield


def prices():
    dates = mcal.get_calendar("NYSE").schedule("2022-01-01", "2026-10-13").index[-800:]
    return pd.DataFrame({"Close": 100 + np.arange(800) * .1 + np.sin(np.arange(800))}, index=dates)


def run_app(download):
    st.cache_data.clear()
    with patch("yfinance.download", side_effect=download):
        return AppTest.from_file(str(ROOT / "App.py"), default_timeout=20).run()


def test_current_app_preserves_model_and_backtests():
    app = run_app(lambda symbol, **kwargs: prices())
    assert not app.exception
    assert not app.error
    assert any(m.label == "Sector score" for m in app.metric)
    assert any(s.value == "Historical SOXL Signal Backtest" for s in app.subheader)
    assert not app.radio  # No simulated macro scenario influences the current model.


@pytest.mark.parametrize("failure", ["outage", "stale", "future", "infinite", "historical_missing", "too_far_behind"])
def test_bad_feed_withholds_current_app_signal(failure):
    def download(symbol, **kwargs):
        df = prices()
        if failure == "outage":
            raise RuntimeError("offline")
        if failure == "stale":
            df = df.iloc[:-8]
        elif failure == "future":
            df.index += pd.Timedelta(days=10)
        elif failure == "infinite":
            df.iloc[-1, 0] = np.inf
        elif failure == "historical_missing":
            df.iloc[-2, 0] = np.nan
        elif failure == "too_far_behind" and symbol == "SPY":
            df = df.iloc[:-2]
        return df
    app = run_app(download)
    assert not app.exception
    assert app.error
    assert not app.metric


def test_warm_cache_is_revalidated_on_rerun():
    st.cache_data.clear()
    with patch("yfinance.download", side_effect=lambda symbol, **kwargs: prices()):
        app = AppTest.from_file(str(ROOT / "App.py"), default_timeout=20).run()
    assert not app.exception
    assert app.metric
    with patch("utils.price_quality.require_fresh_date", side_effect=ValueError("Stale cached observation")):
        app.run()
    assert not app.exception
    assert app.error
    assert not app.metric


@pytest.mark.parametrize("failure", ["missing_latest", "mismatched_latest"])
def test_one_session_fallback_is_visible(failure):
    def download(symbol, **kwargs):
        df = prices()
        if failure == "missing_latest":
            df.iloc[-1, 0] = np.nan
        elif symbol == "SPY":
            df = df.iloc[:-1]
        return df
    app = run_app(download)
    assert not app.exception
    assert not app.error
    assert app.metric
    assert any("FALLBACK DATA" in w.value and "2026-10-12" in w.value for w in app.warning)


def test_intraday_observation_is_excluded():
    def download(symbol, **kwargs):
        df = prices()
        df.loc[pd.Timestamp("2026-10-14"), "Close"] = 9999
        return df
    app = run_app(download)
    assert not app.exception
    assert not app.error
    assert any("2026-10-13" in m.value for m in app.markdown)
    assert not any("9,999" in m.value for m in app.metric)


def test_cached_snapshot_ages_at_exchange_close_without_download():
    st.cache_data.clear()
    with patch("yfinance.download", side_effect=lambda symbol, **kwargs: prices()):
        app = AppTest.from_file(str(ROOT / "App.py"), default_timeout=20).run()
    assert app.metric
    assert not app.warning
    with patch("utils.market_sessions.utc_now", return_value=pd.Timestamp("2026-10-14T20:01:00Z")), \
         patch("yfinance.download", side_effect=AssertionError("Cache should be used")):
        app.run()
    assert not app.exception
    assert not app.error
    assert any("FALLBACK DATA" in w.value for w in app.warning)
    with patch("utils.market_sessions.utc_now", return_value=pd.Timestamp("2026-10-15T20:01:00Z")), \
         patch("yfinance.download", side_effect=AssertionError("Cache should be used")):
        app.run()
    assert not app.exception
    assert app.error
    assert not app.metric
