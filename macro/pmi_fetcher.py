from fredapi import Fred
import os
from dotenv import load_dotenv

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

def get_ism_pmi():
    try:
        pmi = fred.get_series('NAPM')  # ISM Manufacturing PMI series code
        latest = pmi.dropna().iloc[-1]
        return float(round(latest, 2))
    except Exception as e:
        return f"Error fetching PMI: {e}"
