"""Offline UI regressions for the current SOXX/SOXL tracker."""
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def prices():
    dates = pd.bdate_range(end=pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize(), periods=800)
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


@pytest.mark.parametrize("failure", ["outage", "stale", "future", "infinite", "missing", "mismatch"])
def test_bad_feed_withholds_current_app_signal(failure):
    def download(symbol, **kwargs):
        df = prices()
        if failure == "outage":
            raise RuntimeError("offline")
        if failure == "stale":
            df.index -= pd.Timedelta(days=10)
        elif failure == "future":
            df.index += pd.Timedelta(days=10)
        elif failure == "infinite":
            df.iloc[-1, 0] = np.inf
        elif failure == "missing":
            df.iloc[-1, 0] = np.nan
        elif failure == "mismatch" and symbol == "SPY":
            df = df.iloc[:-1]
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
