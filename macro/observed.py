"""Fetch raw series with dates; validate outside the cache on every rerun."""
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from fredapi import Fred
from utils.observations import Observation, latest_observation, today
from utils.signal_engine import Component, component

DATA = Path(__file__).resolve().parents[1] / "data"


@st.cache_data(ttl=3600)
def fred_series(series_id):
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return pd.Series(dtype=float)
    try:
        return Fred(api_key=key).get_series(series_id)
    except Exception:
        return pd.Series(dtype=float)


def fred_components(orders, capex, as_of=None):
    source = "https://fred.stlouisfed.org/series/"
    orders_obs = latest_observation(orders, 100, as_of, source + "A34SNO")
    if orders_obs.eligible and orders_obs.value <= 0:
        orders_obs = Observation(orders_obs.value, orders_obs.date, "invalid", "Orders must be positive", orders_obs.source)
    output = [component("Tech Orders (A34SNO)", "macro", orders_obs, 25000, 24000)]
    obs = latest_observation(capex, 100, as_of, source + "NEWORDER")
    score = None
    if obs.eligible:
        previous = latest_observation(capex.sort_index().iloc[:-1], 140, as_of, source + "NEWORDER")
        if obs.value <= 0 or not previous.eligible or previous.value <= 0 or (pd.Period(obs.date, "M") - pd.Period(previous.date, "M")).n != 1:
            obs = Observation(obs.value, obs.date, "invalid", "Need consecutive valid monthly observations", obs.source)
        else:
            score = 1 if obs.value > previous.value else -1 if obs.value < previous.value else 0
    output.append(Component("CapEx (NEWORDER)", "macro", obs, score))
    return output


def sales_component(path=None, as_of=None):
    try:
        df = pd.read_csv(path or DATA / "semiconductor_sales.csv")
        df["Date"] = pd.to_datetime(df.Date, errors="raise")
        df = df.sort_values("Date")
        obs = latest_observation(df.set_index("Date")["YoY_Percent"], 100, as_of)
        row = df.iloc[-1]
        published = pd.Timestamp(row.Published)
        if not str(row.Source).startswith("https://www.semiconductors.org/") or pd.isna(published) or published.normalize() > today(as_of) or published < row.Date:
            obs = Observation(status="invalid", reason="Missing/invalid source or publication date")
        else:
            obs = Observation(obs.value, obs.date, obs.status, obs.reason, row.Source)
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        obs = Observation(reason="Sourced semiconductor sales observation unavailable")
    return component("Semiconductor Sales YoY (%)", "macro", obs)
