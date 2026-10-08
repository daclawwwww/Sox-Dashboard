from utils.observations import frame_observation, weekly_trend
import math
import pandas as pd

def load_dram_prices(csv_path='data/dram_prices.csv'):
    try:
        df = pd.read_csv(csv_path, parse_dates=['Date'])
        df.sort_values('Date', inplace=True)
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        print(f"Error loading DRAM prices: {e}")
        return pd.DataFrame()

def get_latest_dram_price(df, as_of=None):
    obs = frame_observation(df, "DRAM_Price", 14, as_of)
    return obs.value if obs.eligible and obs.value > 0 else None


def calculate_dram_score(latest_price, threshold_high=4.0, threshold_low=3.5):
    if latest_price is None or not math.isfinite(latest_price):
        return None
    if latest_price > threshold_high:
        return 1
    elif latest_price < threshold_low:
        return -1
    else:
        return 0

def calculate_dram_trend_score(df, lookback_weeks=4, as_of=None):
    return weekly_trend(df, "DRAM_Price", 0.01, lookback_weeks, as_of)
