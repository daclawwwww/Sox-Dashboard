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

def get_latest_nand_price(df):
    if df.empty:
        return None
    return df['NAND_Price'].iloc[-1]

def calculate_nand_score(latest_price, threshold_high=4.75, threshold_low=4.60):
    if latest_price is None:
        return 0
    if latest_price > threshold_high:
        return 1
    elif latest_price < threshold_low:
        return -1
    else:
        return 0

def calculate_nand_trend_score(df, lookback_weeks=4):
    if df.empty or len(df) < lookback_weeks + 1:
        return 0
    trend = df['NAND_Price'].tail(lookback_weeks + 1).diff().mean()
    if trend > 0.005:
        return 1
    elif trend < -0.005:
        return -1
    else:
        return 0