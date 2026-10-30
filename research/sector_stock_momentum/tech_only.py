#!/usr/bin/env python3
"""
tech_only.py — the same picking rules restricted to the Information Technology sector (GICS as of each month-end:
before 2018-09 IT also held GOOGL/META/EBAY/EA, after the 2018 reshuffle those are Communication Services).
Rules: pure momentum top-1, + SMA200, momentum top-5 equal weight, three-factor score top-1
(EPS growth protected + momentum + margin improvement). Benchmarks: XLK (tech ETF), SPY.
WARNING: choosing "tech" after seeing that tech led 2009-2026 is hindsight; read results as descriptive.
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
    T = X[X.sector == 'Information Technology'].copy()
    form = pd.DatetimeIndex(sorted(X.t.unique()))
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    best = lambda g, col='mom_12_1': None if g.empty else g.sort_values([col, 'ticker'], ascending=[False, True]).ticker.iloc[0]
    F = T.dropna(subset=['eps_g_m5', 'margin_chg']).copy()
    for c in ['eps_g_m5', 'mom_12_1', 'margin_chg']:
        F['r_' + c] = F.groupby('t')[c].rank(pct=True)
    F['score'] = F[['r_eps_g_m5', 'r_mom_12_1', 'r_margin_chg']].mean(axis=1)
    S = {'tech: momentum top-1': run(T, best, rf),
         'tech: momentum top-1 + SMA200': run(T, lambda g: best(g[g.dist_sma200 > 0]), rf),
         'tech: three-factor score top-1': run(F, lambda g: best(g, 'score'), rf)}
    r5 = T.sort_values(['t', 'mom_12_1', 'ticker'], ascending=[True, False, True]).groupby('t').head(5)
    S['tech: momentum top-5 (equal weight)'] = pd.DataFrame({'net': r5.groupby('t').fwd_ret.mean().values - 0.002,
                                                            'pick': 'basket'}, index=pd.DatetimeIndex(sorted(r5.t.unique())) + pd.offsets.MonthEnd(1))
    S['all S&P: momentum top-1'] = pd.read_csv(os.path.join(OUT, 'sma200_pure_momentum_top_1.csv'), parse_dates=['month']).set_index('month')
    px = bt.Prices(*bt.load_prices()[:2], 0)
    bench = {k: px.nxt[k].reindex(form).set_axis(hold) for k in ['XLK', 'SPY']}
    periods = {'2010-01..2021-05': ('2010-01-31', '2021-05-31'), '2021-06..2026-09': ('2021-06-30', '2026-09-30'),
               '2010-01..2025-12': ('2010-01-31', '2025-12-31'), '2010-01..2026-09': ('2010-01-31', '2026-09-30')}
    rows = []
    for name, r_ in list(S.items()) + [(k, v) for k, v in bench.items()]:
        ser = r_ if isinstance(r_, pd.Series) else r_.net
        for lab, (a, z) in periods.items():
            s = bt.stats(ser.loc[a:z], rf)
            rows.append({'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'], 'maxDD': s['maxDD_month_end']})
        if not isinstance(r_, pd.Series) and name.startswith('tech'):
            r_.to_csv(os.path.join(OUT, 'tech_' + ''.join(c if c.isalnum() else '_' for c in name)[:45] + '.csv'))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'tech_only_summary.csv'), index=False)
    for lab in periods:
        x = R[R.period == lab].set_index('strategy')
        print(f'\n== {lab}')
        print(x.assign(CAGR=(x.CAGR * 100).round(1), Sharpe=x.Sharpe.round(2), maxDD=(x.maxDD * 100).round(0))[['CAGR', 'Sharpe', 'maxDD']].to_string())
    m = S['tech: momentum top-1']
    lr = np.log1p(m.net)
    print('\ntech momentum top-1: top-5 months share', round(lr.sort_values().tail(5).sum() / lr.sum(), 2),
          '| most held', m.pick.value_counts().head(8).to_dict(), '| tech names per month', round(T.groupby('t').size().mean(), 1))
    y = (1 + m.net).groupby(m.index.year).prod() - 1
    print((y * 100).round(1).to_dict())


if __name__ == '__main__':
    main()
