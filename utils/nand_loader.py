from utils.observations import frame_observation, weekly_trend
import math
import pandas as pd

def load_nand_prices(csv_path='data/nand_flash_prices.csv'):
    try:
        df = pd.read_csv(csv_path, parse_dates=['Date'])
        df.sort_values('Date', inplace=True)
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        print(f"Error loading NAND prices: {e}")
        return pd.DataFrame()

def get_latest_nand_price(df, as_of=None):
    obs = frame_observation(df, "NAND_Price", 14, as_of)
    return obs.value if obs.eligible and obs.value > 0 else None


def calculate_nand_score(latest_price, threshold_high=4.75, threshold_low=4.60):
    if latest_price is None or not math.isfinite(latest_price):
        return None
    if latest_price > threshold_high:
        return 1
    elif latest_price < threshold_low:
        return -1
    else:
        return 0

def calculate_nand_trend_score(df, lookback_weeks=4, as_of=None):
    return weekly_trend(df, "NAND_Price", 0.005, lookback_weeks, as_of)
