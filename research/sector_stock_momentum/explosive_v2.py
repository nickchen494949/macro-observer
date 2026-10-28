#!/usr/bin/env python3
"""
explosive_v2.py — composite of ASYMMETRIC factors only.

Rule (stated before computing, but AFTER having seen the dev lift table of explosive_factors.py → only the holdout is
a real test): on development formations 2012-01 … 2022-06, all S&P, a factor is kept if
  explosive lift >= 1.2 and t >= 2   AND   explosive lift / bust lift >= 1.10
(i.e. it picks next-6m top-5 % winners more than it picks next-6m bottom-5 % losers).
Composite = mean percentile rank of the kept factors (at least 2/3 present). Evaluated on holdout formations
2023-01 … 2026-03 (lifts) and as portfolios (top-1 / top-5; all S&P and tech), costs 10 bp per side.
"""
import os

import numpy as np
import pandas as pd

import backtest as bt
from explosive_factors import lift_table, DEV, HOLD
from sma200_overlay import run

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'explosive')
FACT = {'mom_12_1': 1, 'mom_6_1': 1, 'mom_3_1': 1, 'mom_accel': 1, 'dist_52wh': 1, 'smooth': 1, 'dist_sma200': 1,
        'vol_3m': 1, 'maxret_1m': 1, 'eps_g': 1, 'eps_g_m5': 1, 'eps_accel': 1, 'sue': 1, 'deps_p': 1, 'rev_g': 1,
        'rev_g_q': 1, 'rev_accel': 1, 'margin_chg': 1, 'gm_chg': 1, 'rd_int': 1, 'ep': -1, 'log_mcap': -1}


def main():
    X = pd.read_parquet(os.path.join(OUT, 'panel_explosive.parquet'))
    X['bust6'] = (X.groupby('t').fwd6.rank(pct=True) <= 0.05).astype(float).where(X.fwd6.notna())
    form = pd.DatetimeIndex(sorted(X.t.unique()))
    dev_m = form[(form >= DEV[0]) & (form <= DEV[1])]
    hold_m = form[(form >= HOLD[0]) & (form <= HOLD[1])]
    e = lift_table(X, FACT, 'explosive6', dev_m).set_index('factor')
    b = lift_table(X, FACT, 'bust6', dev_m).set_index('factor')
    sel = [f for f in e.index if e.at[f, 'lift'] >= 1.2 and e.at[f, 't_NW'] >= 2 and e.at[f, 'lift'] / b.at[f, 'lift'] >= 1.10]
    print('kept factors:', sel)
    print(pd.DataFrame({'explosive_lift': e.lift, 'bust_lift': b.lift, 'ratio': e.lift / b.lift}).loc[sel].round(2).to_string())
    cols = []
    for c in sel:
        X['r_' + c] = X.groupby('t')[c].rank(pct=True) * FACT[c]
        if FACT[c] < 0:
            X['r_' + c] += 1
        cols.append('r_' + c)
    X['score'] = X[cols].mean(axis=1).where(X[cols].notna().sum(axis=1) >= int(np.ceil(len(cols) * 2 / 3)))
    tech = X[X.sector == 'Information Technology']
    print()
    for uni, D in [('all S&P', X), ('tech', tech)]:
        for lab, months in [('dev', dev_m), ('holdout', hold_m)]:
            out = []
            for tg in ['explosive6', 'bust6']:
                r = lift_table(D, {'score': 1}, tg, months).iloc[0]
                out.append(f'{tg} lift {r.lift:.2f} (t {r.t_NW:.2f}, hit {r["hit_rate_top10%"]:.3f} vs {r.base_rate:.3f})')
            print(f'[{uni}] {lab}: ' + ' | '.join(out))
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    best = lambda g: None if g.dropna(subset=['score']).empty else \
        g.dropna(subset=['score']).sort_values(['score', 'ticker'], ascending=[False, True]).ticker.iloc[0]
    S = {'v2 top-1 (tech)': run(tech, best, rf), 'v2 top-1 (all S&P)': run(X, best, rf)}
    for uni, D in [('tech', tech), ('all S&P', X)]:
        for n in (5, 10):
            r5 = D.dropna(subset=['score']).sort_values(['t', 'score', 'ticker'], ascending=[True, False, True]).groupby('t').head(n)
            S[f'v2 top-{n} ({uni})'] = pd.DataFrame({'net': r5.groupby('t').fwd_ret.mean().values - 0.002, 'pick': 'basket'},
                                                   index=pd.DatetimeIndex(sorted(r5.t.unique())) + pd.offsets.MonthEnd(1))
    prev = pd.read_csv(os.path.join(OUT, 'composite_portfolios.csv'))
    daily, P = bt.load_prices()[:2]
    px = bt.Prices(daily, P, 0)
    for k in ['XLK', 'SPY']:
        S[k] = pd.DataFrame({'net': px.nxt[k].reindex(form).values, 'pick': k}, index=hold)
    rows = []
    periods = {'dev 2012-01..2022-12': ('2012-01-31', '2022-12-31'), 'holdout 2023-01..2026-09': ('2023-01-31', '2026-09-30'),
               'full 2012-01..2026-09': ('2012-01-31', '2026-09-30')}
    for name, df in S.items():
        for lab, (a, z) in periods.items():
            s = bt.stats(df.net.loc[a:z], rf)
            rows.append({'strategy': name, 'period': lab, 'v': f"{s['CAGR']*100:.1f}% / {s['Sharpe']:.2f} / {s['maxDD_month_end']*100:.0f}%"})
        if name.startswith('v2'):
            df.to_csv(os.path.join(OUT, 'v2_' + ''.join(c if c.isalnum() else '_' for c in name) + '.csv'))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'v2_portfolios.csv'), index=False)
    print()
    print(R.pivot(index='strategy', columns='period', values='v')[list(periods)].to_string())
    t1 = S['v2 top-1 (tech)']
    print('\nv2 tech top-1 most held:', t1.pick.loc['2012':].value_counts().head(8).to_dict())
    y = (1 + t1.net.loc['2012':]).groupby(t1.loc['2012':].index.year).prod() - 1
    print('v2 tech top-1 by year:', (y * 100).round(1).to_dict())
    t5 = S['v2 top-5 (tech)']
    y5 = (1 + t5.net.loc['2012':]).groupby(t5.loc['2012':].index.year).prod() - 1
    print('v2 tech top-5 by year:', (y5 * 100).round(1).to_dict())


if __name__ == '__main__':
    main()
