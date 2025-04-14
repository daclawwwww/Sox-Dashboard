import yfinance as yf

def load_price_data():
    soxx = yf.download("SOXX", period="1y")
    spy = yf.download("SPY", period="1y")
    return soxx, spy
