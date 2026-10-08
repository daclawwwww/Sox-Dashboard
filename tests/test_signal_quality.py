from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from utils.observations import Observation, latest_observation, weekly_trend
from utils.signal_engine import Component, component, technical_components, live_signal
from utils.dram_loader import load_dram_prices, get_latest_dram_price, calculate_dram_trend_score
from utils.nand_loader import load_nand_prices, get_latest_nand_price, calculate_nand_trend_score
from utils.book_to_bill_loader import load_book_to_bill, get_latest_b2b
from macro.observed import fred_components, sales_component
from macro.semiconductor_leads import get_macro_signal_score
from utils.data_loader import normalize_prices

AS_OF = "2026-10-07"
ROOT = Path(__file__).resolve().parents[1]


def series(values=(1,), dates=(AS_OF,)):
    return pd.Series(values, index=pd.to_datetime(dates))


@pytest.mark.parametrize("values,dates,status", [
    ([], [], "unavailable"), ([1], ["2025-04-14"], "stale"),
    ([1], ["2026-10-08"], "invalid"), ([float("nan")], [AS_OF], "invalid"),
    ([float("inf")], [AS_OF], "invalid"), ([1,2], [AS_OF,AS_OF], "invalid"),
    ([1], ["2026-10-02"], "fresh"), ([1], ["2026-10-01"], "stale"),
])
def test_observation_validation(values, dates, status):
    assert latest_observation(series(values, dates), 5, AS_OF).status == status


def test_invalid_date_and_latest_missing_not_backfilled():
    assert latest_observation(pd.Series([1], index=["bad"]), 5, AS_OF).status == "invalid"
    assert latest_observation(series([1,np.nan], ["2026-10-06",AS_OF]), 5, AS_OF).status == "invalid"


@pytest.mark.parametrize("loader,getter,filename", [
    (load_dram_prices,get_latest_dram_price,"dram_prices.csv"),
    (load_nand_prices,get_latest_nand_price,"nand_flash_prices.csv"),
    (load_book_to_bill,get_latest_b2b,"semi_book_to_bill.csv")])
def test_committed_legacy_data_excluded(loader,getter,filename):
    assert getter(loader(ROOT/"data"/filename), as_of=AS_OF) is None
    assert getter(loader("missing.csv"), as_of=AS_OF) is None


def test_trend_stale_or_irregular_is_not_neutral():
    assert calculate_dram_trend_score(load_dram_prices(), as_of=AS_OF) is None
    assert calculate_nand_trend_score(load_nand_prices(), as_of=AS_OF) is None
    df = pd.DataFrame({"x": [1,2,3,4,5]}, index=pd.date_range(end=AS_OF, periods=5, freq="7D"))
    assert weekly_trend(df,"x",.01,as_of=AS_OF) == 1
    df.index = pd.date_range(end=AS_OF, periods=5, freq="D")
    assert weekly_trend(df,"x",.01,as_of=AS_OF) is None


def components(score=1):
    obs=Observation(1,AS_OF,"fresh","test","fixture")
    names=["RSI (14)","MACD Histogram","3-Month ROC (%)","Relative Strength Trend"]
    return [Component(n,"technical",obs,score) for n in names]+[
        Component(n,"macro",obs,score) for n in ["Tech Orders (A34SNO)","CapEx (NEWORDER)","Semiconductor Sales YoY (%)"]]


@pytest.mark.parametrize("score,signal",[(1,"BUY"),(0,"HOLD"),(-1,"SELL")])
def test_full_coverage(score,signal):
    assert live_signal(components(score))["signal"] == signal


def test_missing_coverage_and_no_weight_shift():
    c=components()
    assert live_signal([])["signal"] == "INSUFFICIENT DATA"
    assert live_signal(c[1:])["score"] is None
    assert live_signal(c[:-2])["score"] is None
    c[-1]=replace(c[-1], observation=Observation(status="stale"), score=1)
    assert live_signal(c)["macro_coverage"] == "2/3"
    assert live_signal(c)["score"] == 1
    c[4]=replace(c[4],score=-1)
    assert live_signal(c)["score"] == .6


def test_scenarios_cannot_enter_live_model():
    baseline=live_signal(components())
    for scenario, expected in [("strong",5),("neutral",0),("weak",-5)]:
        assert get_macro_signal_score(scenario)["macro_score"] == expected
        assert live_signal(components()) == baseline
    with pytest.raises(ValueError):
        live_signal(components()+[Component("Mock PMI","macro",Observation(),1)])


def test_fred_dates_missing_and_nonconsecutive():
    data=series([100,101],["2026-07-01","2026-08-01"])
    assert fred_components(data,data,AS_OF)[1].score == 1
    assert fred_components(data,data,"2027-01-01")[1].score is None
    skipped=series([100,101],["2026-06-01","2026-08-01"])
    assert fred_components(data,skipped,AS_OF)[1].score is None
    assert fred_components(data,series(),AS_OF)[1].score is None


def test_sales_expiration_and_publication(tmp_path):
    assert sales_component(as_of=AS_OF).score == 1
    assert sales_component(as_of="2026-10-04").score is None
    assert sales_component(as_of="2027-01-01").score is None
    assert sales_component(tmp_path/"missing.csv",AS_OF).score is None


def test_technical_preserved_stale_and_misaligned():
    dates=pd.bdate_range(end=AS_OF,periods=100)
    soxx=pd.Series(np.arange(100)+100.,index=dates)
    spy=pd.Series(np.arange(100)+500.,index=dates)
    c=technical_components(soxx,spy,AS_OF)
    assert [x.score for x in c] == [1,0,1,1]
    assert all(x.score is None for x in technical_components(soxx,spy,"2026-11-01"))
    assert technical_components(soxx,spy.iloc[:-1],AS_OF)[-1].score is None
    assert all(x.score is None for x in technical_components(soxx.iloc[-10:],spy,AS_OF))


def test_multiindex_prices():
    df=pd.DataFrame([[123]],columns=pd.MultiIndex.from_tuples([("Close","SOXX")]))
    assert normalize_prices(df,"SOXX")["Close"].iloc[0] == 123


def test_group_spoofing_rejected():
    c=components()
    c[0]=replace(c[0],group="macro")
    with pytest.raises(ValueError):
        live_signal(c)


def test_infinite_history_and_undated_series_excluded():
    dates=pd.bdate_range(end=AS_OF,periods=100)
    prices=pd.Series(np.arange(100)+100.,index=dates)
    prices.iloc[10]=np.inf
    assert all(c.score is None for c in technical_components(prices,prices,AS_OF))
    assert latest_observation(pd.Series([1]),5,AS_OF).status == "invalid"


def test_weighted_thresholds_are_symmetric():
    c=components(0)
    for i in range(2):
        c[i]=replace(c[i],score=1)
    assert live_signal(c)["score"] == .3
    assert live_signal(c)["signal"] == "BUY"
    for i in range(2):
        c[i]=replace(c[i],score=-1)
    assert live_signal(c)["signal"] == "SELL"


def test_unsorted_timezone_dates_and_sales_bad_schema(tmp_path):
    values=pd.Series([2,1],index=pd.to_datetime(["2026-10-07T12:00Z","2026-10-06T12:00Z"]))
    assert latest_observation(values,5,AS_OF).value == 2
    path=tmp_path/"bad.csv"
    path.write_text("Date,wrong\n2026-08-31,1\n")
    assert sales_component(path,AS_OF).score is None
