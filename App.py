from pathlib import Path
import pandas as pd
import streamlit as st
from utils.data_loader import load_price_data
from utils.observations import frame_observation, latest_observation
from utils.signal_engine import technical_components, live_signal
from macro.observed import fred_series, fred_components, sales_component
from macro.semiconductor_leads import get_macro_signal_score

st.set_page_config(page_title="SOXX Momentum Dashboard", layout="wide")
st.title("SOXX Momentum Dashboard")
st.caption("Observed-data signal • Dates and coverage checked on each rerun")
ROOT = Path(__file__).resolve().parent

with st.spinner("Loading observed market data..."):
    try:
        soxx, spy = load_price_data()
        technical = technical_components(soxx["Close"], spy["Close"])
    except Exception:
        st.warning("Market prices unavailable. Live recommendation withheld.")
        technical = technical_components(pd.Series(dtype=float), pd.Series(dtype=float))
    macro = fred_components(fred_series("A34SNO"), fred_series("NEWORDER"))
    macro.append(sales_component())
components = technical + macro
result = live_signal(components)
st.subheader("Live recommendation")
st.metric("Trading Signal", result["signal"])
st.metric("Weighted Score (-1 to +1)", "N/A" if result["score"] is None else f'{result["score"]:+.3f}')
st.caption(f'Technical coverage: {result["technical_coverage"]} • Macro coverage: {result["macro_coverage"]}')
if result["score"] is None:
    st.warning("Requires all four fresh technical indicators and at least two of three fresh macro indicators. Missing data is not a SELL or a neutral vote.")
if any(c.score is None for c in components):
    st.warning("Some observations are excluded. Review dates, status, and reasons below. Configure FRED_API_KEY for observed macro orders.")

for group, title in [(technical, "Technical indicators"), (macro, "Observed macro indicators")]:
    with st.expander(title, expanded=True):
        st.dataframe(pd.DataFrame([{
            "Indicator": c.name, "Value": c.observation.value,
            "Observation date": c.observation.date, "Status": c.observation.status,
            "Live vote": c.score, "Reason": c.observation.reason,
            "Source": c.observation.source,
        } for c in group]), hide_index=True, use_container_width=True)
st.caption("A34SNO is computer/electronic-product orders in $ millions, not ISM PMI or semiconductor orders. NEWORDER is nondefense capital goods excluding aircraft. Sales is SIA/WSTS global three-month-average sales YoY, stored as a dated manual observation.")

with st.expander("Semiconductor input audit — excluded legacy data", expanded=True):
    for filename, column, age in [("dram_prices.csv", "DRAM_Price", 14), ("nand_flash_prices.csv", "NAND_Price", 14), ("semi_book_to_bill.csv", "BookToBill", 100)]:
        try:
            df = pd.read_csv(ROOT / "data" / filename, index_col="Date")
        except (OSError, ValueError):
            df = pd.DataFrame()
        obs = frame_observation(df, column, age)
        st.write(f"**{column}**: {obs.value} | observation {obs.date or 'unavailable'} | {obs.status}: {obs.reason}. **Excluded from live scoring.**")
    st.warning("Legacy memory CSVs lack product/source provenance. Their absolute-price thresholds and trends cannot be verified. The North American SEMI book-to-bill series ended in 2017; the repository's 2025 rows are unverified.")
    st.markdown("[SEMI publication status](https://www.semi.org/zh/products-services/market-data/equipment/billings-report)")
    st.write("Refreshed, named memory quotes — context only; not joined to legacy history:")
    try:
        context = pd.read_csv(ROOT / "data" / "memory_spot_context.csv")
        context["Status"] = [latest_observation(pd.Series([row.USD_Per_Chip], index=[row.Date]), 14).status for row in context.itertuples()]
        st.dataframe(context, hide_index=True)
    except (OSError, ValueError, KeyError):
        st.warning("Memory context unavailable; no impact on live score.")

with st.expander("Hypothetical macro sandbox — never used in live recommendation"):
    scenario = st.radio("Hypothetical conditions", ["strong", "neutral", "weak"], index=1)
    simulated = get_macro_signal_score(simulate=scenario)
    st.write(f'Hypothetical composite: {simulated["macro_score"]:+d}')
    st.json(simulated["indicators"])
    st.caption("Five mock votes only. This sandbox does not change live scores, weights, coverage, or recommendation.")

with st.expander("Methodology and limitations"):
    st.markdown((ROOT / "METHODOLOGY.md").read_text())
