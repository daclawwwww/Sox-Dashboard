"""Network-free UI regressions: unavailable feeds and scenario isolation."""
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


def test_app_scenarios_do_not_change_live_signal():
    today=pd.Timestamp.now().normalize()
    dates=pd.bdate_range(end=today,periods=100)
    soxx=pd.DataFrame({"Close":np.arange(100)+100.},index=dates)
    spy=pd.DataFrame({"Close":np.arange(100)+500.},index=dates)
    months=pd.date_range(end=today,periods=3,freq="MS")
    observed=pd.Series([26000.,27000.,28000.],index=months)
    with patch("utils.data_loader.load_price_data", return_value=(soxx,spy)), patch("macro.observed.fred_series",return_value=observed):
        app=AppTest.from_file(str(ROOT/"App.py")).run()
        assert not app.exception
        baseline=[m.value for m in app.metric]
        for scenario in ["strong","weak","neutral"]:
            app.radio[0].set_value(scenario).run()
            assert not app.exception
            assert [m.value for m in app.metric] == baseline


def test_app_feed_outage_withholds_signal():
    with patch("utils.data_loader.load_price_data",side_effect=RuntimeError("offline")), patch("macro.observed.fred_series",return_value=pd.Series(dtype=float)):
        app=AppTest.from_file(str(ROOT/"App.py")).run()
        assert not app.exception
        assert app.metric[0].value == "INSUFFICIENT DATA"
