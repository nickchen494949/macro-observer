"""
fundamentals_pit.py — helpers to use the PIT fundamentals store in backtests.

    from fundamentals_pit import load_eps, asof, eps_on_price_basis

    eps = load_eps()                                  # all sectors (or load_eps('Energy'))
    snap = asof(eps, '2015-06-30')                    # latest fundamentals PUBLIC on that date
    snap = eps_on_price_basis(snap)                   # EPS put on Yahoo split-adjusted price basis
    pe = price_close_on_date / snap.eps_diluted_ttm_adj

Point-in-time rules
  * `available_date` = SEC filing date + 1 day. A row is usable at date t only if available_date <= t.
  * Values are AS FIRST REPORTED (restatements are kept separately in pit_long/<Sector>.parquet
    with is_first_report == False).
  * SEC per-share numbers are on the share basis at FILING time. Yahoo `close` is split-adjusted
    to TODAY's basis → divide EPS by all split ratios that happened after the filing date.
"""
import json, os
from functools import lru_cache

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(HERE, 'data', 'fundamentals')
RAW = os.path.join(HERE, 'data', 'raw')


def load_eps(sector=None):
    p = pd.read_parquet(os.path.join(F, 'eps_quarterly_pit.parquet'))
    return p if sector is None else p[p.sector == sector].copy()


def load_long(sector):
    return pd.read_parquet(os.path.join(F, 'pit_long', sector.replace(' ', '_') + '.parquet'))


def asof(panel, date):
    """Latest row per ticker that was public on `date` (strictly no look-ahead)."""
    d = pd.Timestamp(date)
    x = panel[panel.available_date <= d]
    return x.sort_values(['ticker', 'period_end', 'available_date']).groupby('ticker').tail(1).reset_index(drop=True)


@lru_cache(maxsize=None)
def splits(ticker):
    p = os.path.join(RAW, ticker.replace('.', '-') + '.json')
    if not os.path.exists(p):
        return ()
    d = json.load(open(p))
    return tuple((pd.Timestamp(a), (n or 1) / (dd or 1)) for a, n, dd in d.get('splits', []))


def split_factor_after(ticker, date):
    f = 1.0
    for d, r in splits(ticker):
        if d > pd.Timestamp(date):
            f *= r
    return f


def eps_on_price_basis(df, cols=('eps_diluted', 'eps_basic', 'eps_diluted_ttm', 'eps_basic_ttm')):
    df = df.copy()
    fac = [split_factor_after(t, f) for t, f in zip(df.ticker, df.filed)]
    for c in cols:
        if c in df:
            df[c + '_adj'] = df[c] / pd.Series(fac, index=df.index)
    return df
