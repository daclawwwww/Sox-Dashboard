import pandas as pd
from pathlib import Path

def load_dram_prices(csv_path='data/dram_prices.csv'):
    try:
        df = pd.read_csv(csv_path, parse_dates=['Date'])
        df.sort_values('Date', inplace=True)
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        print(f"Error loading DRAM prices: {e}")
        return pd.DataFrame()

def get_latest_dram_price(df):
    if df.empty:
        return None
    return df['DRAM_Price'].iloc[-1]

def calculate_dram_score(latest_price, threshold_high=4.0, threshold_low=3.5):
    if latest_price is None:
        return 0
    if latest_price > threshold_high:
        return 1
    elif latest_price < threshold_low:
        return -1
    else:
        return 0
