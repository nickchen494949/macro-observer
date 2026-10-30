#!/usr/bin/env python3
"""
ndx_fundamentals.py — PIT SEC fundamentals for the Nasdaq-100 names that are not in the S&P store.

Same code path as build_fundamentals.py (build_long → eps_panel → split-basis EPS), only the company list differs:
data/ndx_cik_map.csv (hand-checked CIKs, see its `method` column). CIKs already in the S&P store are skipped.
Foreign private issuers filing 20-F / 40-F (ASML, BIDU, JD, PDD, NTES, TCOM, …) are not in SEC FSDS 10-K/10-Q
extracts → no fundamentals (their fundamental factors stay missing; price factors still exist).
Writes ONLY to data/fundamentals_ndx/ (the S&P store in data/fundamentals/ is not touched):
  pit_long/<Sector>.parquet, eps_quarterly_pit.parquet, dropped_future_dated_values.csv, ambiguous_values_excluded.csv
"""
import json, os

import numpy as np
import pandas as pd

import build_fundamentals as bf
import fundamentals_pit as fp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'fundamentals_ndx')
RAW_NDX = os.path.join(HERE, 'data', 'raw_ndx')


def ndx_splits(ticker):
    p = os.path.join(RAW_NDX, ticker.replace('.', '-') + '.json')
    if not os.path.exists(p):
        return ()
    d = json.load(open(p))
    return tuple((pd.Timestamp(a), (n or 1) / (dd or 1)) for a, n, dd in d.get('splits', []))


def main():
    os.makedirs(os.path.join(OUT, 'pit_long'), exist_ok=True)
    bf.F = OUT                                          # redirect every file build_long / eps_panel writes
    sp_cik = set(pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).cik.dropna().astype(int))
    cm = pd.read_csv(os.path.join(HERE, 'data', 'ndx_cik_map.csv'))
    cm = cm[~cm.cik.isin(sp_cik)]
    sec = pd.read_csv(os.path.join(HERE, 'data', 'ndx_sectors.csv')).set_index('ticker').sector
    cm['sector'] = cm.ticker.map(sec)
    cm['method'] = 'ndx_manual'
    sub = bf.load_raw()
    long = bf.build_long(sub, cm[['ticker', 'cik', 'sector', 'method']])
    for s_, g in long.groupby('sector'):
        g.drop(columns=['fye']).to_parquet(os.path.join(OUT, 'pit_long', s_.replace(' ', '_') + '.parquet'), index=False)
    p = bf.eps_panel(long)
    tk = long.drop_duplicates('cik').set_index('cik')[['ticker', 'all_tickers', 'sector']]
    p = p.join(tk, on='cik')
    fac = [np.prod([r for d, r in ndx_splits(t) if d > pd.Timestamp(f)]) if isinstance(t, str) and pd.notna(f) else np.nan
           for t, f in zip(p.ticker, p.filed_eps_diluted if 'filed_eps_diluted' in p else p.filed)]
    p['_fac'] = fac
    for f in ['eps_diluted_approx', 'eps_basic_approx']:
        if f in p:
            p[f + '_adj'] = p[f] / p['_fac']
            g = p.groupby('cik')
            roll = g[f + '_adj'].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
            span = (p.ddate - g.ddate.shift(3)).dt.days
            p[f + '_ttm_adj'] = roll.where(span.between(250, 290))
    cols = ['ticker', 'all_tickers', 'cik', 'sector', 'ddate', 'fy', 'fp', 'form', 'filed', 'available_date', 'q4_derived',
            'filed_eps_diluted', 'filed_eps_basic', 'filed_net_income', 'filed_revenue', 'filed_diluted_shares',
            'eps_diluted_approx_ttm_available_date', 'eps_basic_approx_ttm_available_date',
            'eps_diluted_approx_adj', 'eps_diluted_approx_ttm_adj', 'eps_basic_approx_ttm_adj',
            'net_income_ttm_available_date', 'revenue_ttm_available_date',
            'eps_diluted', 'eps_basic', 'eps_diluted_approx', 'eps_basic_approx', 'net_income', 'revenue',
            'diluted_shares', 'eps_diluted_approx_ttm', 'eps_basic_approx_ttm', 'net_income_ttm', 'revenue_ttm']
    p = p[[c for c in cols if c in p]].rename(columns={'ddate': 'period_end'})
    p.to_parquet(os.path.join(OUT, 'eps_quarterly_pit.parquet'), index=False)
    have = set(p.cik.unique())
    cov = cm.assign(has_fundamentals=cm.cik.isin(have))
    cov.to_csv(os.path.join(OUT, 'coverage.csv'), index=False)
    print('NDX-only CIKs', cm.cik.nunique(), 'with SEC fundamentals', len(have))
    print('no fundamentals (20-F/40-F or not in FSDS):', sorted(cov.ticker[~cov.has_fundamentals].unique()))


if __name__ == '__main__':
    main()
