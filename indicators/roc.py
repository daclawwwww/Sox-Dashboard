def compute_roc(series, period):
    return ((series - series.shift(period)) / series.shift(period)) * 100
