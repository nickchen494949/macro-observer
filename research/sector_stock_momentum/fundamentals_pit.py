"""
fundamentals_pit.py — helpers to use the PIT fundamentals store in backtests.

    from fundamentals_pit import load_eps, asof, eps_on_price_basis

    eps = load_eps()                                  # all sectors (or load_eps('Energy'))
    snap = asof(eps, '2015-06-30', ttm_field='eps_diluted_approx')   # latest TTM EPS PUBLIC on that date
    # TTM EPS on a common share basis is precomputed (eps_diluted_approx_ttm_adj); eps_on_price_basis() is only
    # needed for single-quarter fields
    pe = yahoo_close_on_date / snap.eps_diluted_approx_ttm_adj   # both on today's split-adjusted basis

Point-in-time rules
  * `available_date` = SEC filing date of that quarter's EPS + 1 day; each TTM field has its own
    `<field>_ttm_available_date` (all 4 quarters public + 1 day). Use the one that matches what you read.
  * eps_diluted / eps_basic are REPORTED quarterly values only. Q4 (= FY − 9M) and every TTM EPS
    live in *_approx columns because EPS is not additive across periods.
  * Values are AS FIRST REPORTED (restatements are kept separately in pit_long/<Sector>.parquet
    with is_first_report == False).
  * SEC per-share numbers are on the share basis at FILING time. Yahoo `close` is split-adjusted
    to TODAY's basis → divide EPS by all split ratios that happened after the filing date.
"""
import json, os
from functools import lru_cache

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(HERE, 'data', 'fundamentals')
RAW = os.path.join(HERE, 'data', 'raw')


def load_eps(sector=None):
    p = pd.read_parquet(os.path.join(F, 'eps_quarterly_pit.parquet'))
    return p if sector is None else p[p.sector == sector].copy()


def load_long(sector):
    return pd.read_parquet(os.path.join(F, 'pit_long', sector.replace(' ', '_') + '.parquet'))


def asof(panel, date, max_age_days=200, ttm_field=None):
    """Latest row per ticker that was public on `date` (strictly no look-ahead).

    ttm_field: e.g. 'eps_diluted_approx' / 'net_income' / 'revenue' → use that field's TTM availability
               date (all 4 quarters public) instead of the quarter's own availability date.
    max_age_days drops stale rows whose fiscal quarter ended long before `date`
    (e.g. 2008–09 quarters that only appeared in XBRL a year later as comparatives)."""
    d = pd.Timestamp(date)
    col = f'{ttm_field}_ttm_available_date' if ttm_field else 'available_date'
    x = panel[panel[col] <= d]
    x = x.sort_values(['ticker', 'period_end', 'available_date']).groupby('ticker').tail(1).copy()
    if max_age_days is not None:
        x = x[(d - x.period_end).dt.days <= max_age_days]
    # every field is returned only if IT was public on `date` (fields of one quarter are filed at different times)
    gates = {'eps_diluted': 'filed_eps_diluted', 'eps_diluted_approx': 'filed_eps_diluted',
             'eps_diluted_approx_adj': 'filed_eps_diluted', 'eps_basic': 'filed_eps_basic',
             'eps_basic_approx': 'filed_eps_basic', 'net_income': 'filed_net_income', 'revenue': 'filed_revenue',
             'diluted_shares': 'filed_diluted_shares'}
    for f, g in gates.items():
        if f in x and g in x:
            x.loc[~(x[g] + pd.Timedelta(days=1) <= d), f] = np.nan
    for f in ['eps_diluted_approx', 'eps_basic_approx', 'net_income', 'revenue']:
        a = f'{f}_ttm_available_date'
        for c in [f'{f}_ttm', f'{f}_ttm_adj']:
            if c in x and a in x:
                x.loc[~(x[a] <= d), c] = np.nan
    return x.reset_index(drop=True)


@lru_cache(maxsize=None)
def splits(ticker):
    p = os.path.join(RAW, ticker.replace('.', '-') + '.json')
    pt = os.path.join(HERE, 'data', 'raw_tiingo', ticker.replace('.', '-') + '.json')
    if os.path.exists(pt) and json.load(open(pt)).get('covers_membership'):
        p = pt                        # same source as the price series used for that security
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


def eps_on_price_basis(df, cols=('eps_diluted', 'eps_basic', 'eps_basic_approx')):
    """Put as-first-reported EPS on the share basis of Yahoo's split-adjusted prices (today's basis).

    A first-reported value is on the share basis at its FILING date, so it is divided by every split
    that happened after that filing date — exactly once (later restated comparatives are not used here,
    so a split is never applied twice). Price and EPS then share one basis and P/E is basis-free."""
    df = df.copy()
    fac = [split_factor_after(t, f) for t, f in zip(df.ticker, df.get('filed_eps_diluted', df.filed))]
    for c in cols:
        if c in df:
            df[c + '_adj'] = df[c] / pd.Series(fac, index=df.index)
    return df
