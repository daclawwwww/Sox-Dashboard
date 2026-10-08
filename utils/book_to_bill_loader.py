from utils.observations import frame_observation, weekly_trend
import math
import pandas as pd

def load_book_to_bill(csv_path='data/semi_book_to_bill.csv'):
    try:
        df = pd.read_csv(csv_path, parse_dates=['Date'])
        df.sort_values('Date', inplace=True)
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        print(f"Error loading SEMI book-to-bill data: {e}")
        return pd.DataFrame()

def get_latest_b2b(df, as_of=None):
    obs = frame_observation(df, "BookToBill", 100, as_of)
    return obs.value if obs.eligible and obs.value > 0 else None


def calculate_b2b_score(value, high_threshold=1.05, low_threshold=0.95):
    if value is None or not math.isfinite(value):
        return None
    if value > high_threshold:
        return 1
    elif value < low_threshold:
        return -1
    else:
        return 0
