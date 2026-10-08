"""Compatibility accessor; dates and freshness retained."""
import pandas as pd
from macro.observed import fred_series, fred_components


def get_capex_proxy(as_of=None):
    series = fred_series("NEWORDER")
    c = fred_components(pd.Series(dtype=float), series, as_of)[1]
    if c.score is None:
        return {"error": c.observation.reason, "status": c.observation.status, "date": c.observation.date}
    return {"latest": c.observation.value, "prev": float(series.sort_index().iloc[-2]),
            "score": c.score, "date": c.observation.date, "status": c.observation.status}
