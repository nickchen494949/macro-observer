#!/usr/bin/env python3
"""
improve_v3.py — three robustness / risk upgrades on the asymmetric 6-factor composite (explosive_v2.py):

 (1) market regime filter  : at formation t, if the benchmark (SPY for all-S&P, XLK for tech) closes below its
                             200-day SMA, hold cash (T-bill) next month instead of stocks
 (5) inverse-volatility    : top-5 basket weighted ∝ 1 / 3-month volatility instead of equal weight
 (6) annual re-selection   : every January the factor set is re-chosen with the SAME rule (explosive lift >= 1.2,
                             t >= 2, explosive/bust >= 1.10) using only formations whose 6-month outcome was known by the
                             previous December (formation <= June of the previous year); no fixed hindsight factor list
Costs 10 bp per side (baskets approximated with full turnover 20 bp). Same panel as explosive_v2.py.
"""
import os

import numpy as np
import pandas as pd

import backtest as bt
from explosive_factors import lift_table
from explosive_v2 import FACT
from sma200_overlay import run

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'explosive')
# the factor list chosen by explosive_v2.py with the frozen rule (written to v2_selected_factors.json); originally
# ['log_mcap', 'mom_3_1', 'mom_6_1', 'dist_sma200', 'gm_chg', 'eps_g'] — log_mcap dropped out after the 2026-10-29
# share-split-basis fix if the rule says so
import json as _json
FIXED = _json.load(open(os.path.join(OUT, 'v2_selected_factors.json')))['selected']


def score_with(X, factors):
    cols = []
    for c in factors:
        r = X.groupby('t')[c].rank(pct=True)
        X['r_' + c] = r if FACT[c] > 0 else 1 - r
        cols.append('r_' + c)
    return X[cols].mean(axis=1).where(X[cols].notna().sum(axis=1) >= int(np.ceil(len(cols) * 2 / 3)))


def annual_scores(X, first_year=2015):
    X['score_wf'] = np.nan
    log = {}
    for y in range(first_year, 2027):
        train_m = X.t[(X.t >= '2012-01-31') & (X.t <= pd.Timestamp(f'{y-1}-06-30'))].unique()
        e = lift_table(X, FACT, 'explosive6', train_m).set_index('factor')
        b = lift_table(X, FACT, 'bust6', train_m).set_index('factor')
        sel = [f for f in e.index if e.at[f, 'lift'] >= 1.2 and e.at[f, 't_NW'] >= 2 and e.at[f, 'lift'] / b.at[f, 'lift'] >= 1.10]
        log[y] = sel
        m = X.t.dt.year == y - 1 if False else (X.t + pd.offsets.MonthEnd(1)).dt.year == y      # holding year y
        if sel:
            X.loc[m, 'score_wf'] = score_with(X.loc[m].copy(), sel)
    return log


def basket(D, col, n, rf, weight='ew'):
    rows = []
    for t, g in D.dropna(subset=[col]).groupby('t', sort=True):
        g = g.sort_values([col, 'ticker'], ascending=[False, True]).head(n)
        if weight == 'ivol':
            w = 1 / g.vol_3m.clip(lower=0.05)
            w = w / w.sum()
        else:
            w = pd.Series(1 / len(g), index=g.index)
        r = float((w * g.fwd_ret).sum())
        rows.append({'month': t + pd.offsets.MonthEnd(1), 'net': r - 0.002, 'pick': 'basket', 'gross': r,
                     'picks': '|'.join(g.ticker), 'weights': '|'.join(f'{x:.6f}' for x in w)})
    return pd.DataFrame(rows).set_index('month')


def regime(df, bench_below, rf):
    """Replace months whose formation date had the benchmark below its 200-day SMA by T-bill (switch costs 10 bp)."""
    out = df.copy()
    for m in out.index:
        t = m - pd.offsets.MonthEnd(1)
        if bench_below.get(t, False):
            out.loc[m, 'net'] = float(rf.get(m, 0)) - 0.001
            out.loc[m, 'pick'] = 'CASH(regime)'
    return out


def main():
    X = pd.read_parquet(os.path.join(OUT, 'panel_explosive.parquet'))
    X['bust6'] = (X.groupby('t').fwd6.rank(pct=True) <= 0.05).astype(float).where(X.fwd6.notna())
    X['score_fixed'] = score_with(X, FIXED)
    sel_log = annual_scores(X)
    form = pd.DatetimeIndex(sorted(X.t.unique()))
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    daily, P = bt.load_prices()[:2]
    below = {}
    for k in ['SPY', 'XLK']:
        s = daily[k].dropna()
        sma = s.rolling(200).mean()
        idx = s.index.searchsorted(form, side='right') - 1
        below[k] = dict(zip(form, (s.iloc[idx].values < sma.iloc[idx].values)))
    tech = X[X.sector == 'Information Technology']
    pick = lambda col: (lambda g: None if g.dropna(subset=[col]).empty else
                        g.dropna(subset=[col]).sort_values([col, 'ticker'], ascending=[False, True]).ticker.iloc[0])
    S = {}
    for tag, col in [('fixed', 'score_fixed'), ('annual-reselect', 'score_wf')]:
        S[f'tech top-1 [{tag}]'] = run(tech, pick(col), rf)
        S[f'tech top-5 EW [{tag}]'] = basket(tech, col, 5, rf)
        S[f'tech top-5 inv-vol [{tag}]'] = basket(tech, col, 5, rf, 'ivol')
    for k in list(S):
        S[k + ' + XLK regime'] = regime(S[k], below['XLK'], rf)
    S['pure momentum top-1 (all S&P)'] = pd.read_csv(os.path.join(HERE, 'results', 'ml', 'sma200_pure_momentum_top_1.csv'),
                                                     parse_dates=['month']).set_index('month')
    S['pure momentum top-1 (all) + SPY regime'] = regime(S['pure momentum top-1 (all S&P)'], below['SPY'], rf)
    px = bt.Prices(daily, P, 0)
    for k in ['XLK', 'SPY']:
        S[k] = pd.DataFrame({'net': px.nxt[k].reindex(form).values, 'pick': k}, index=hold)
        S[k + ' + own regime'] = regime(S[k], below[k], rf)
    periods = {'2015-01..2022-12': ('2015-01-31', '2022-12-31'), '2023-01..2026-09': ('2023-01-31', '2026-09-30'),
               '2015-01..2026-09': ('2015-01-31', '2026-09-30'), '2022 only': ('2022-01-31', '2022-12-31')}
    rows = []
    for name, df in S.items():
        for lab, (a, z) in periods.items():
            st = bt.stats(df.net.loc[a:z], rf)
            v = f"{st['CAGR']*100:.1f}% / {st['Sharpe']:.2f} / {st['maxDD_month_end']*100:.0f}%" if lab != '2022 only' \
                else f"{((1 + df.net.loc[a:z]).prod() - 1) * 100:.1f}%"
            rows.append({'strategy': name, 'period': lab, 'v': v})
        df.to_csv(os.path.join(OUT, 'v3_' + ''.join(c if c.isalnum() else '_' for c in name)[:60] + '.csv'))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'v3_summary.csv'), index=False)
    pd.set_option('display.width', 250)
    print(R.pivot(index='strategy', columns='period', values='v')[list(periods)].to_string())
    print('\nannual factor selection (rule re-applied each January, data up to previous June):')
    for y, s_ in sel_log.items():
        print(y, s_)
    print('regime months in cash 2015-2026: SPY', sum(v for t, v in below['SPY'].items() if t >= pd.Timestamp('2014-12-31')),
          '| XLK', sum(v for t, v in below['XLK'].items() if t >= pd.Timestamp('2014-12-31')))


if __name__ == '__main__':
    main()
