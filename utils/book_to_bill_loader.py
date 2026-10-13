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

def get_latest_b2b(df):
    if df.empty:
        return None
    return df['BookToBill'].iloc[-1]

def calculate_b2b_score(value, high_threshold=1.05, low_threshold=0.95):
    if value is None:
        return 0
    if value > high_threshold:
        return 1
    elif value < low_threshold:
        return -1
    else:
        return 0
