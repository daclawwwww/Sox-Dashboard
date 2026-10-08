"""Compatibility accessor: A34SNO is tech orders, not ISM PMI."""
from macro.observed import fred_series
from utils.observations import latest_observation


def get_ism_pmi(as_of=None):
    obs = latest_observation(fred_series("A34SNO"), 100, as_of)
    return obs.value if obs.eligible else None
