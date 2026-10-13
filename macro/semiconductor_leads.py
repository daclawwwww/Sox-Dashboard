import streamlit as st

def get_macro_signal_score(simulate="neutral"):
    """
    Returns a dictionary with mock scores for semiconductor macro indicators
    and the composite macro signal score.
    
    simulate: 'strong', 'weak', or 'neutral'
    """
    # Define mock indicator values based on selected scenario
    if simulate == "strong":
        indicators = {
            "Global PMI": 1,
            "Tech CapEx": 1,
            "Book-to-Bill": 1,
            "DRAM Prices": 1,
            "Chip Exports (SK/TW)": 1
        }
    elif simulate == "weak":
        indicators = {
            "Global PMI": -1,
            "Tech CapEx": -1,
            "Book-to-Bill": -1,
            "DRAM Prices": -1,
            "Chip Exports (SK/TW)": -1
        }
    else:
        indicators = {
            "Global PMI": 0,
            "Tech CapEx": 0,
            "Book-to-Bill": 0,
            "DRAM Prices": 0,
            "Chip Exports (SK/TW)": 0
        }

    total_score = sum(indicators.values())

    return {
        "indicators": indicators,
        "macro_score": total_score
    }
