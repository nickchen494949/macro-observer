#!/usr/bin/env python3
"""
sma200_overlay.py — the user's rule "do not buy a stock that is below its 200-day SMA", applied to the existing
strategies (same audited panel: results/ml/panel.parquet; holding months 2010-01 … 2026-09).
  pure momentum top-1            vs  + SMA200 filter
  sector-momentum spec           vs  + SMA200 filter (sector score unchanged; the stock must be above its SMA200)
  protected-EPS (F)              vs  + SMA200 filter
If no stock qualifies the month is held in cash. Costs 10 bp per side (A→B = 20 bp).
"""
import os

import numpy as np
import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'ml')


def run(X, pick_fn, rf, forms=None):
    from legacy_portfolio import run_portfolio
    # Filtering all candidates in one month means CASH, never an omitted month.
    if forms is None:
        forms = pd.DatetimeIndex(rf.index) - pd.offsets.MonthEnd(1)
    def target(g):
        s = pick_fn(g)
        return {} if s is None else {s: 1.0}
    return run_portfolio(X, target, rf, forms=forms)


def best(g, col='mom_12_1'):
    if g.empty:
        return None
    return g.sort_values([col, 'ticker'], ascending=[False, True]).ticker.iloc[0]


def main():
    X = pd.read_parquet(os.path.join(OUT, 'panel.parquet'))
    hold = pd.DatetimeIndex(sorted(X.t.unique())) + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    up = lambda g: g[g.dist_sma200 > 0]

    def spec(g, filt):
        top = g.groupby('sector').mom_12_1.mean().sort_index().sort_values(ascending=False, kind='mergesort').index[0]
        c = g[g.sector == top]
        return best(up(c) if filt else c)

    def epsF(g, filt):
        c = g.dropna(subset=['eps_g_m5']).sort_values(['eps_g_m5', 'ticker'], ascending=[False, True]).head(10)
        c = c[c.mom_12_1 > 0]
        return best(up(c) if filt else c)
    S = {'pure momentum top-1': run(X, lambda g: best(g), rf),
         'pure momentum top-1 + SMA200': run(X, lambda g: best(up(g)), rf),
         'sector spec': run(X, lambda g: spec(g, False), rf),
         'sector spec + SMA200': run(X, lambda g: spec(g, True), rf),
         'EPS protected (F)': run(X, lambda g: epsF(g, False), rf),
         'EPS protected (F) + SMA200': run(X, lambda g: epsF(g, True), rf)}
    px = bt.Prices(*bt.load_prices()[:2], 0)
    spy_r = px.nxt['SPY'].reindex(hold - pd.offsets.MonthEnd(1)).set_axis(hold)
    pd.DataFrame({'net': spy_r, 'gross': spy_r, 'pick': 'SPY', 'cost_per_side': 0.0}).rename_axis('month').to_csv(os.path.join(OUT, 'sma200_SPY.csv'))
    periods = {'IS 2010-01..2021-05': ('2010-01-31', '2021-05-31'), 'OOS 2021-06..2026-09': ('2021-06-30', '2026-09-30'),
               'ML holdout 2023-01..2026-09': ('2023-01-31', '2026-09-30'), 'FULL 2010-01..2026-09': ('2010-01-31', '2026-09-30'),
               'FULL to 2025-12': ('2010-01-31', '2025-12-31')}
    rows = []
    for name, df in list(S.items()) + [('SPY', None)]:
        for lab, (a, z) in periods.items():
            r = (spy_r if df is None else df.net).loc[a:z]
            s = bt.stats(r, rf)
            rows.append({'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'], 'maxDD': s['maxDD_month_end'],
                         'cash_months': 0 if df is None else int((df.pick == 'CASH').loc[a:z].sum())})
        if df is not None:
            df.to_csv(os.path.join(OUT, 'sma200_' + ''.join(c if c.isalnum() else '_' for c in name) + '.csv'))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'sma200_overlay_summary.csv'), index=False)
    for lab in periods:
        x = R[R.period == lab].set_index('strategy')
        print(f'\n== {lab}')
        print(x.assign(CAGR=(x.CAGR * 100).round(1), Sharpe=x.Sharpe.round(2), maxDD=(x.maxDD * 100).round(0))[
            ['CAGR', 'Sharpe', 'maxDD', 'cash_months']].to_string())


if __name__ == '__main__':
    main()
