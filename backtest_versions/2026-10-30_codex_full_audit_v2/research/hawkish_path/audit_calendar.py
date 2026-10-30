import pandas as pd

def align_equity_calendar(signal_frame, price_frame):
    """Forward horizons count exchange sessions, never an inner-join calendar."""
    prices = price_frame.sort_values('date')
    signals = signal_frame.sort_values('date')
    if prices['date'].duplicated().any() or signals['date'].duplicated().any():
        raise ValueError('Duplicate dates in signal/price input')
    out = pd.merge_asof(prices, signals, on='date', direction='backward')
    cols = signals.columns.difference(['date'])
    out.loc[out['date'] > signals['date'].max(), cols] = float('nan')
    return out
