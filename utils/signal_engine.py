"""Pure observed-data scoring. Hypothetical scenarios are intentionally absent."""
from dataclasses import dataclass
import pandas as pd
import numpy as np
from indicators.rsi import compute_rsi
from indicators.macd import compute_macd
from indicators.roc import compute_roc
from indicators.relative_strength import compute_relative_strength
from utils.observations import Observation, latest_observation


@dataclass(frozen=True)
class Component:
    name: str
    group: str
    observation: Observation
    score: int | None


def vote(value, high, low):
    return 1 if value > high else -1 if value < low else 0


def component(name, group, obs, high=0, low=0):
    return Component(name, group, obs, vote(obs.value, high, low) if obs.eligible else None)


def technical_components(soxx, spy, as_of=None):
    """Keep original indicator functions and thresholds, with explicit freshness gates."""
    specs = [("RSI (14)", 55, 45), ("MACD Histogram", .2, -.2),
             ("3-Month ROC (%)", 5, -2), ("Relative Strength Trend", .001, -.001)]
    price_obs = latest_observation(soxx, 5, as_of, "Yahoo Finance / SOXX")
    spy_obs = latest_observation(spy, 5, as_of, "Yahoo Finance / SPY")
    result = []
    for i, (name, high, low) in enumerate(specs):
        obs = price_obs
        if obs.eligible and (not np.isfinite(soxx).all() or (soxx <= 0).any() or len(soxx) < 64):
            obs = Observation(status="invalid", reason="Need at least 64 valid positive SOXX closes")
        if i == 3 and obs.eligible:
            if not spy_obs.eligible:
                obs = spy_obs
            elif spy_obs.date != price_obs.date:
                obs = Observation(status="invalid", reason="SOXX/SPY latest dates do not match")
        if obs.eligible:
            close = soxx.sort_index()
            if i == 0:
                values = compute_rsi(close)
            elif i == 1:
                values = compute_macd(close)
            elif i == 2:
                values = compute_roc(close, 63)
            else:
                aligned = pd.concat([close.rename("SOXX"), spy.rename("SPY")], axis=1).loc[close.index].tail(5)
                if len(aligned) < 5 or not np.isfinite(aligned).all().all() or (aligned <= 0).any().any():
                    obs = Observation(status="invalid", reason="Need five aligned positive SOXX/SPY closes")
                    result.append(component(name, "technical", obs, high, low))
                    continue
                relative = compute_relative_strength(aligned.SOXX, aligned.SPY)
                values = pd.Series([relative.diff().mean()], index=[relative.index[-1]])
            obs = latest_observation(values.tail(1), 5, as_of, "Yahoo Finance / SOXX and SPY")
        result.append(component(name, "technical", obs, high, low))
    return result


def live_signal(components):
    """Fixed group weights; require 4/4 technical and >=2/3 observed macro votes."""
    allowed = {"RSI (14)", "MACD Histogram", "3-Month ROC (%)", "Relative Strength Trend",
               "Tech Orders (A34SNO)", "CapEx (NEWORDER)", "Semiconductor Sales YoY (%)"}
    if len({c.name for c in components}) != len(components) or any(c.name not in allowed for c in components):
        raise ValueError("Unexpected or duplicate live component")
    macro_names = {"Tech Orders (A34SNO)", "CapEx (NEWORDER)", "Semiconductor Sales YoY (%)"}
    if any(c.group != ("macro" if c.name in macro_names else "technical") for c in components):
        raise ValueError("Incorrect live component group")
    valid = [c for c in components if c.observation.eligible and c.score in (-1, 0, 1)]
    tech = [c.score for c in valid if c.group == "technical"]
    macro = [c.score for c in valid if c.group == "macro"]
    result = {"technical_coverage": f"{len(tech)}/4", "macro_coverage": f"{len(macro)}/3",
              "score": None, "signal": "INSUFFICIENT DATA"}
    if len(tech) == 4 and len(macro) >= 2:
        score = .6 * sum(tech) / 4 + .4 * sum(macro) / len(macro)
        result.update(score=score, signal="BUY" if score >= .25 else "SELL" if score <= -.25 else "HOLD")
    return result
