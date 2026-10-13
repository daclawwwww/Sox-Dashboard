"""Snapshot validation runs against synthetic downloads, never production files."""
import json
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
import publish_terminal as terminal


def prices():
    dates = pd.bdate_range(end=pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize(), periods=800)
    return pd.DataFrame({"Close": 100 + np.arange(800) * .1 + np.sin(np.arange(800))}, index=dates)


def test_snapshot_preserves_schema_and_omits_lagging_watchlist(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "ROOT", tmp_path)
    def download(symbol, **kwargs):
        df = prices()
        return df.iloc[:-1] if symbol == "AMD" else df
    with patch("yfinance.download", side_effect=download):
        terminal.main()
    snapshot = json.loads((tmp_path / "docs/market.json").read_text())
    assert snapshot["asof"] == prices().index[-1].date().isoformat()
    assert snapshot["signal"]["score"] in range(8)
    assert len(snapshot["backtest"]) == 12
    assert len(snapshot["chart"]["soxl"]) == 252
    assert any(row["sharpe"] is None for row in snapshot["backtest"])
    assert "AMD" not in [row["ticker"] for row in snapshot["watchlist"]]


@pytest.mark.parametrize("failure", ["stale", "future", "infinite", "missing", "mismatch", "outage"])
def test_invalid_feed_never_overwrites_snapshot(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(terminal, "ROOT", tmp_path)
    out = tmp_path / "docs/market.json"
    out.parent.mkdir()
    out.write_text("previous snapshot")
    def download(symbol, **kwargs):
        df = prices()
        if failure == "outage":
            raise RuntimeError("offline")
        if failure == "stale":
            df.index -= pd.Timedelta(days=10)
        elif failure == "future":
            df.index += pd.Timedelta(days=10)
        elif failure in ("infinite", "missing"):
            df.iloc[-1, 0] = np.inf if failure == "infinite" else np.nan
        elif failure == "mismatch" and symbol == "SPY":
            df = df.iloc[:-1]
        return df
    with patch("yfinance.download", side_effect=download), pytest.raises((ValueError, RuntimeError)):
        terminal.main()
    assert out.read_text() == "previous snapshot"
