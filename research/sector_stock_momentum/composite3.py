#!/usr/bin/env python3
"""
composite3.py — user's idea: score = mean of cross-sectional percentile ranks of
  (1) EPS growth (protected: base-period net margin >= 5 %), (2) 12-1 momentum, (3) net-margin improvement (YoY);
buy the single highest-scoring stock each month (all three inputs required). Variants: + SMA200 filter; top-5 / top-20
equal weight as diagnostics. Same audited panel (results/ml/panel.parquet), costs 10 bp per side.
"""
import os

import numpy as np
import pandas as pd

import backtest as bt
from sma200_overlay import run

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'ml')


def main():
    X = pd.read_parquet(os.path.join(OUT, 'panel.parquet'))
    X = X.dropna(subset=['eps_g_m5', 'mom_12_1', 'margin_chg']).copy()
    for c in ['eps_g_m5', 'mom_12_1', 'margin_chg']:
        X['r_' + c] = X.groupby('t')[c].rank(pct=True)
    X['score'] = X[['r_eps_g_m5', 'r_mom_12_1', 'r_margin_chg']].mean(axis=1)
    hold = pd.DatetimeIndex(sorted(X.t.unique())) + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    best = lambda g: None if g.empty else g.sort_values(['score', 'ticker'], ascending=[False, True]).ticker.iloc[0]
    S = {'composite top-1': run(X, best, rf),
         'composite top-1 + SMA200': run(X, lambda g: best(g[g.dist_sma200 > 0]), rf)}
    for n in (5, 20):
        r = X.sort_values(['t', 'score', 'ticker'], ascending=[True, False, True]).groupby('t').head(n)
        S[f'composite top-{n} (equal weight)'] = pd.DataFrame(
            {'net': r.groupby('t').fwd_ret.mean().values - 0.002, 'pick': 'basket'},
            index=pd.DatetimeIndex(sorted(r.t.unique())) + pd.offsets.MonthEnd(1))
    for name, f in [('pure momentum top-1', 'sma200_pure_momentum_top_1.csv'),
                    ('pure momentum top-1 + SMA200', 'sma200_pure_momentum_top_1___SMA200.csv')]:
        S[name] = pd.read_csv(os.path.join(OUT, f), parse_dates=['month']).set_index('month')
    px = bt.Prices(*bt.load_prices()[:2], 0)
    spy = px.nxt['SPY'].reindex(hold - pd.offsets.MonthEnd(1)).set_axis(hold)
    periods = {'2012-01..2021-05': ('2012-01-31', '2021-05-31'), '2021-06..2026-09': ('2021-06-30', '2026-09-30'),
               '2023-01..2026-09': ('2023-01-31', '2026-09-30'), '2012-01..2025-12': ('2012-01-31', '2025-12-31'),
               '2012-01..2026-09': ('2012-01-31', '2026-09-30')}
    rows = []
    for name, df in list(S.items()) + [('SPY', None)]:
        for lab, (a, z) in periods.items():
            r = (spy if df is None else df.net).loc[a:z]
            s = bt.stats(r, rf)
            rows.append({'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'], 'maxDD': s['maxDD_month_end']})
        if df is not None and 'composite' in name:
            df.to_csv(os.path.join(OUT, 'composite3_' + ''.join(c if c.isalnum() else '_' for c in name) + '.csv'))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'composite3_summary.csv'), index=False)
    for lab in periods:
        x = R[R.period == lab].set_index('strategy')
        print(f'\n== {lab}')
        print(x.assign(CAGR=(x.CAGR * 100).round(1), Sharpe=x.Sharpe.round(2), maxDD=(x.maxDD * 100).round(0))[
            ['CAGR', 'Sharpe', 'maxDD']].to_string())
    c = S['composite top-1']
    lr = np.log1p(c.net.loc['2012':])
    print('\ncomposite top-1: top-5 months share', round(lr.sort_values().tail(5).sum() / lr.sum(), 2),
          '| most held', c.pick.value_counts().head(8).to_dict())
    y = (1 + c.net.loc['2012':]).groupby(c.loc['2012':].index.year).prod() - 1
    print((y * 100).round(1).to_dict())


if __name__ == '__main__':
    main()
