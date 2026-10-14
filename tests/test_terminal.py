"""Snapshot validation uses real sessions and frozen synthetic downloads only."""
import json
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
import publish_terminal as terminal
from utils.market_sessions import SessionContext, exchange_schedule

CUTOFF = "2026-10-14T11:00:00Z"


@pytest.fixture(autouse=True)
def fixed_time():
    with patch("utils.market_sessions.utc_now", return_value=pd.Timestamp(CUTOFF)):
        yield


def prices(end="2026-10-13"):
    dates = exchange_schedule("2022-01-01", end).index[-800:]
    values = 100 + np.arange(len(dates)) * .1 + np.sin(np.arange(len(dates)))
    return pd.DataFrame({"Close": values}, index=dates)


def output_path(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "ROOT", tmp_path)
    out = tmp_path / "docs/market.json"
    out.parent.mkdir(exist_ok=True)
    return out


def test_snapshot_preserves_schema_and_omits_lagging_watchlist(tmp_path, monkeypatch, capsys):
    out = output_path(tmp_path, monkeypatch)
    def download(symbol, **kwargs):
        df = prices()
        return df.iloc[:-1] if symbol == "AMD" else df
    with patch("yfinance.download", side_effect=download):
        terminal.main()
    snapshot = json.loads(out.read_text())
    assert snapshot["asof"] == "2026-10-13"
    assert snapshot["generated_utc"] == pd.Timestamp(CUTOFF).isoformat()
    assert snapshot["signal"]["score"] in range(8)
    assert len(snapshot["backtest"]) == 12
    assert len(snapshot["chart"]["soxl"]) == 252
    assert any(row["sharpe"] is None for row in snapshot["backtest"])
    assert "AMD" not in [row["ticker"] for row in snapshot["watchlist"]]
    assert snapshot["session"] == SessionContext.create(CUTOFF).metadata("2026-10-13")
    assert snapshot["session"]["status"] == "current"
    amd = snapshot["source_diagnostics"]["AMD"]
    assert amd["latest_seen_session"] == "2026-10-12"
    assert amd["missing_completed_sessions"] == ["2026-10-13"]
    assert amd["omitted_from_watchlist"]
    assert "PRICE_SOURCE_DIAGNOSTICS" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["stale", "future", "infinite", "historical_missing", "too_far_behind", "outage", "non_session", "empty"])
def test_invalid_feed_never_overwrites_snapshot(tmp_path, monkeypatch, failure, capsys):
    out = output_path(tmp_path, monkeypatch)
    out.write_text("previous snapshot")
    def download(symbol, **kwargs):
        df = prices()
        if failure == "outage":
            raise RuntimeError("offline")
        if failure == "empty":
            return pd.DataFrame()
        if failure == "stale":
            df = df.iloc[:-8]
        elif failure == "future":
            df.index += pd.Timedelta(days=10)
        elif failure in ("infinite", "historical_missing"):
            df.iloc[-2, 0] = np.inf if failure == "infinite" else np.nan
        elif failure == "too_far_behind" and symbol == "SPY":
            df = df.iloc[:-2]
        elif failure == "non_session":
            df.loc[pd.Timestamp("2026-10-11"), "Close"] = 123.
        return df
    with patch("yfinance.download", side_effect=download), pytest.raises((ValueError, RuntimeError)):
        terminal.main()
    assert out.read_text() == "previous snapshot"
    log = capsys.readouterr().out
    assert "rejected_reason" in log
    assert '"status": "error"' in log
    assert '"error":' in log
    if failure in ("outage", "empty"):
        assert '"SOXL":' in log
        assert '"latest_seen_session": null' in log


@pytest.mark.parametrize("missing", ["omitted", "nan", "mixed"])
def test_october14_missing_october13_is_visible_fallback(tmp_path, monkeypatch, missing):
    out = output_path(tmp_path, monkeypatch)
    def download(symbol, **kwargs):
        df = prices()
        if missing == "omitted" or (missing == "mixed" and symbol == "SPY"):
            return df.iloc[:-1]
        if missing == "nan":
            df.iloc[-1, 0] = np.nan
        return df
    with patch("yfinance.download", side_effect=download):
        terminal.main()
    snapshot = json.loads(out.read_text())
    assert snapshot["asof"] == "2026-10-12"
    assert snapshot["session"]["expected_latest_completed_session"] == "2026-10-13"
    assert snapshot["session"]["lag_sessions"] == 1
    assert snapshot["session"]["status"] == "fallback"
    assert "2026-10-13" in snapshot["session"]["fallback_reason"]
    assert snapshot["source_diagnostics"]["SPY"]["missing_completed_sessions"] == ["2026-10-13"]
    spy = next(row for row in snapshot["watchlist"] if row["ticker"] == "SPY")
    assert spy["close"] == round(float(prices().iloc[-2, 0]), 2)


@pytest.mark.parametrize("partial", [99999., np.nan])
def test_october13_intraday_snapshot_uses_october12_only(tmp_path, monkeypatch, partial):
    out = output_path(tmp_path, monkeypatch)
    def download(symbol, **kwargs):
        df = prices()
        df.iloc[-1, 0] = partial
        return df
    with patch("yfinance.download", side_effect=download):
        terminal.main(cutoff_utc="2026-10-13T14:00:00Z")
    snapshot = json.loads(out.read_text())
    assert snapshot["asof"] == "2026-10-12"
    assert snapshot["session"]["status"] == "current"
    assert snapshot["session"]["lag_sessions"] == 0
    assert snapshot["session"]["next_session_close_utc"] == "2026-10-13T20:00:00+00:00"
    for row in snapshot["source_diagnostics"].values():
        assert row["latest_seen_session"] == "2026-10-13"
        assert row["latest_completed_valid_session"] == "2026-10-12"
        assert row["excluded_in_progress_sessions"] == ["2026-10-13"]
    assert all(row["close"] != 99999. for row in snapshot["watchlist"])


def test_one_cutoff_captured_before_downloads_even_when_run_crosses_close(tmp_path, monkeypatch):
    out = output_path(tmp_path, monkeypatch)
    clock_calls = []
    def now():
        clock_calls.append(True)
        return pd.Timestamp("2026-10-13T19:59:00Z" if len(clock_calls) == 1 else "2026-10-13T20:01:00Z")
    def download(symbol, **kwargs):
        assert clock_calls  # Context exists before the first request.
        return prices()
    with patch("utils.market_sessions.utc_now", side_effect=now), patch("yfinance.download", side_effect=download):
        terminal.main()
    snapshot = json.loads(out.read_text())
    assert len(clock_calls) == 1
    assert snapshot["asof"] == "2026-10-12"
    assert snapshot["generated_utc"] == snapshot["session"]["cutoff_utc"] == "2026-10-13T19:59:00+00:00"


def prior_snapshot(cutoff="2026-10-13T22:00:00Z"):
    return {"asof": "2026-10-13", "generated_utc": cutoff,
            "session": SessionContext.create(cutoff).metadata("2026-10-13"),
            "watchlist": [{"ticker": "SOXX", "close": 123.}]}


def test_trustworthy_october13_snapshot_cannot_regress_on_october14(tmp_path, monkeypatch, capsys):
    out = output_path(tmp_path, monkeypatch)
    original = json.dumps(prior_snapshot())
    out.write_text(original)
    with patch("yfinance.download", side_effect=lambda *args, **kwargs: prices().iloc[:-1]), \
            pytest.raises(ValueError, match="regression rejected"):
        terminal.main()
    assert out.read_text() == original
    assert not list(out.parent.glob(".market-*"))
    log = capsys.readouterr().out
    assert "existing finalized 2026-10-13" in log
    assert "candidate 2026-10-12" in log
    assert '"latest_seen_session": "2026-10-12"' in log
    assert '"missing_completed_sessions": ["2026-10-13"]' in log


@pytest.mark.parametrize("generated,expected_log", [
    ("2026-10-13T14:00:00.978734+00:00", "Correcting unfinalized prior snapshot"),
    ("2026-10-13T20:00:01Z", "finality is unverifiable"),
])
def test_legacy_snapshot_does_not_pin_bad_session_date(tmp_path, monkeypatch, generated, expected_log, capsys):
    out = output_path(tmp_path, monkeypatch)
    out.write_text(json.dumps({"asof": "2026-10-13", "generated_utc": generated}))
    with patch("yfinance.download", side_effect=lambda *args, **kwargs: prices().iloc[:-1]):
        terminal.main()
    snapshot = json.loads(out.read_text())
    assert snapshot["asof"] == "2026-10-12"
    assert snapshot["session"]["status"] == "fallback"
    assert expected_log in capsys.readouterr().out


@pytest.mark.parametrize("malformation", ["future", "actual_session", "actual_close", "cutoff", "calendar", "not_json"])
def test_unverified_previous_snapshot_can_be_corrected(tmp_path, monkeypatch, malformation, capsys):
    out = output_path(tmp_path, monkeypatch)
    previous = prior_snapshot()
    if malformation == "future":
        previous["generated_utc"] = "2026-10-15T22:00:00Z"
    elif malformation == "actual_session":
        previous["session"]["actual_session"] = "2026-10-12"
    elif malformation == "actual_close":
        previous["session"]["actual_close_utc"] = "2026-10-13T14:00:00Z"
    elif malformation == "cutoff":
        previous["session"]["cutoff_utc"] = "2026-10-13T19:59:59Z"
    elif malformation == "calendar":
        previous["session"]["calendar"] = "FAKE"
    out.write_text("not json" if malformation == "not_json" else json.dumps(previous))
    with patch("yfinance.download", side_effect=lambda *args, **kwargs: prices().iloc[:-1]):
        terminal.main()
    assert json.loads(out.read_text())["asof"] == "2026-10-12"
    assert "finality is unverifiable" in capsys.readouterr().out


def test_serialization_failure_preserves_previous_snapshot(tmp_path):
    out = tmp_path / "market.json"
    out.write_text("previous")
    with pytest.raises(ValueError, match="Out of range float"):
        terminal.write_snapshot(out, {"invalid": float("nan")})
    assert out.read_text() == "previous"
