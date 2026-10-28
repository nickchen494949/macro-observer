#!/usr/bin/env python3
"""
earnings_factor.py — earnings-announcement return (EAR) as an "explosive stock" factor.

Pre-declared design (written before looking at any result, 2026-10-28 23:45; same protocol as explosive_factors.py):
  Event       every SEC 8-K with item 2.02 (earnings release), data/earnings_dates.csv (fetch_earnings_dates.py).
              Reaction session R = first trading session >= reaction_date (releases accepted after 16:00 NY → next day).
  ear         stock return from the close of the session BEFORE R to the close of the session AFTER R (3 sessions),
              minus SPY's return over the same window. Public at the close of R+1; used at formation t only if
              R+1 <= t and the event is <= 100 calendar days old (else missing).
  ear_sum4    sum of the last 4 ears (each <= 400 days old, at least 3 present).
  Test        explosive6 / bust6 lift (top decile vs base rate, Newey-West t, lag 6) on dev 2012-01..2022-06 and
              holdout 2023-01..2026-03, all S&P and tech; useful = explosive lift >= 1.2, t >= 2, explosive/bust >= 1.10.
  Portfolio   only if useful on dev: add to the fixed 6-factor composite, tech top-5 inverse-vol 2015-01..2026-09
              (same code as improve_v3.py), compared with the composite without it.
Output: results/explosive/ear_*.csv
"""
import os

import numpy as np
import pandas as pd

import backtest as bt
from explosive_factors import lift_table, DEV, HOLD

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'explosive')


def ear_events(daily, X):
    ed = pd.read_csv(os.path.join(HERE, 'data', 'earnings_dates.csv'), parse_dates=['reaction_date'])
    sess = daily['SPY'].dropna().index
    spy = daily['SPY'].reindex(sess)
    pairs = X[['ticker', 'cik']].dropna().drop_duplicates()
    rows = []
    for tk, cik in pairs.itertuples(index=False):
        if tk not in daily.columns:
            continue
        s = daily[tk].reindex(sess)
        seg = bt.SEG_D[tk].reindex(sess) if tk in bt.SEG_D.columns else None
        ev = ed[ed.cik == int(cik)].reaction_date.values
        if not len(ev):
            continue
        i = sess.searchsorted(ev, side='left')               # R = first session >= reaction date
        ok = (i >= 1) & (i + 1 < len(sess))
        for k in i[ok]:
            a, b = k - 1, k + 1
            pa, pb = s.iloc[a], s.iloc[b]
            if not (np.isfinite(pa) and np.isfinite(pb)) or (seg is not None and seg.iloc[a] != seg.iloc[b]):
                continue
            rows.append((tk, sess[k], sess[b], pb / pa - 1 - (spy.iloc[b] / spy.iloc[a] - 1)))
    E = pd.DataFrame(rows, columns=['ticker', 'R', 'public', 'ear']).drop_duplicates(['ticker', 'R'])
    return E.sort_values(['ticker', 'R'])


def attach(X, E):
    E = E.sort_values(['ticker', 'public']).copy()
    g = E.groupby('ticker')
    E['n4'] = g.ear.transform(lambda s: s.rolling(4, min_periods=3).count())
    E['ear_sum4'] = g.ear.transform(lambda s: s.rolling(4, min_periods=3).sum())
    E['oldest4'] = g.R.shift(3)
    X = X.sort_values('t')
    m = pd.merge_asof(X[['t', 'ticker']].reset_index(), E.sort_values('public'), left_on='t', right_on='public',
                      by='ticker', direction='backward').set_index('index')
    age = (m.t - m.R).dt.days
    X['ear'] = m.ear.where(age <= 100)
    X['ear_sum4'] = m.ear_sum4.where((age <= 100) & ((m.t - m.oldest4).dt.days.fillna(0) <= 400))
    return X.sort_index()


def main():
    X = pd.read_parquet(os.path.join(OUT, 'panel_explosive.parquet'))
    X['bust6'] = (X.groupby('t').fwd6.rank(pct=True) <= 0.05).astype(float).where(X.fwd6.notna())
    daily = bt.load_prices()[0]
    E = ear_events(daily, X)
    E.to_csv(os.path.join(OUT, 'ear_events.csv'), index=False)
    X = attach(X, E)
    print('events', len(E), 'tickers', E.ticker.nunique(), '| panel coverage ear', round(X.ear.notna().mean(), 3),
          'ear_sum4', round(X.ear_sum4.notna().mean(), 3))
    form = pd.DatetimeIndex(sorted(X.t.unique()))
    dev_m = form[(form >= DEV[0]) & (form <= DEV[1])]
    hold_m = form[(form >= HOLD[0]) & (form <= HOLD[1])]
    F = {'ear': 1, 'ear_sum4': 1, 'sue': 1}
    rows = []
    for uni, D in [('all', X), ('tech', X[X.sector == 'Information Technology'])]:
        for lab, months in [('dev', dev_m), ('holdout', hold_m)]:
            e = lift_table(D, F, 'explosive6', months).set_index('factor')
            b = lift_table(D, F, 'bust6', months).set_index('factor')
            for f in e.index:
                rows.append({'universe': uni, 'period': lab, 'factor': f, 'explosive_lift': e.at[f, 'lift'],
                             't_NW': e.at[f, 't_NW'], 'bust_lift': b.at[f, 'lift'],
                             'ratio': e.at[f, 'lift'] / b.at[f, 'lift'], 'months': e.at[f, 'months']})
    L = pd.DataFrame(rows)
    L.to_csv(os.path.join(OUT, 'ear_lift.csv'), index=False)
    print(L.round(2).to_string(index=False))
    dev_all = L[(L.universe == 'all') & (L.period == 'dev')].set_index('factor')
    useful = [f for f in ['ear', 'ear_sum4'] if dev_all.at[f, 'explosive_lift'] >= 1.2 and dev_all.at[f, 't_NW'] >= 2
              and dev_all.at[f, 'ratio'] >= 1.10]
    print('useful on dev (pre-declared rule):', useful or 'none')
    X.to_parquet(os.path.join(OUT, 'panel_explosive_ear.parquet'), index=False)
    # portfolio check (reported whether or not the factor passed, labelled accordingly)
    import improve_v3 as v3
    from explosive_v2 import FACT
    FACT.update({'ear': 1, 'ear_sum4': 1})
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    S = {}
    for tag, fs in [('composite (baseline)', v3.FIXED), ('composite + ear', v3.FIXED + ['ear']),
                    ('composite + ear_sum4', v3.FIXED + ['ear_sum4'])]:
        X['sc'] = v3.score_with(X, fs)                 # ranks across all S&P members (as improve_v3.py), then tech
        S[tag] = v3.basket(X[X.sector == 'Information Technology'], 'sc', 5, rf, 'ivol')
    out = []
    for name, df in S.items():
        for lab, (a, z) in {'2015-01..2022-12': ('2015-01-31', '2022-12-31'), '2023-01..2026-09': ('2023-01-31', '2026-09-30'),
                            '2015-01..2026-09': ('2015-01-31', '2026-09-30')}.items():
            s = bt.stats(df.net.loc[a:z], rf)
            out.append({'strategy': f'tech top-5 inv-vol, {name}', 'period': lab,
                        'v': f"{s['CAGR']*100:.1f}% / {s['Sharpe']:.2f} / {s['maxDD_month_end']*100:.0f}%"})
    R = pd.DataFrame(out)
    R.to_csv(os.path.join(OUT, 'ear_portfolios.csv'), index=False)
    print(R.pivot(index='strategy', columns='period', values='v').to_string())


if __name__ == '__main__':
    main()
