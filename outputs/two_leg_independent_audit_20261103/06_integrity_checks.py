#!/usr/bin/env python3
"""
06_integrity_checks.py
  (1) Physical truncation (look-ahead) test of the INDEPENDENT engine: physically cut every raw price file at a cutoff,
      rebuild features for all formations <= cutoff, and require identical picks/scores.
  (2) Return-source flags of every actual pick (open-to-open vs close proxy vs delisting exit).
  (3) Second-vendor check of every pick-month: Yahoo vs Tiingo vs WIKI open-to-open where >=2 vendors exist.
  (4) Every pick-month with |return| > 30%: show both vendors.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ind_engine as IE

Pq = pd.read_parquet(os.path.join(HERE, 'ind_panel_ndx.parquet'))
Ps = pd.read_parquet(os.path.join(HERE, 'ind_panel_spx.parquet'))
pk_q = IE.sleeve_picks(Pq, 'sharpe', k=2, keep=5)
pk_s = IE.sleeve_picks(Ps, 'mom', k=1, keep=3)

# ---------------- (1) truncation
orig_load = IE.load.__wrapped__
res = []
for cut in ([] if '--skip-trunc' in sys.argv else ['2012-12-31', '2018-06-30', '2022-12-31']):
    cut = pd.Timestamp(cut)
    IE.calendar.cache_clear()

    @IE.functools.lru_cache(maxsize=None)
    def cut_load(source, sym, _c=cut):
        df = orig_load(source, sym)
        if df is None:
            return None
        df = df.loc[:_c]
        return df if len(df) else None
    IE.load = cut_load
    Mq = {t: m for t, m in IE.ndx_members().items() if t <= cut}
    Ms = {t: m for t, m in IE.spx_members().items() if t <= cut}
    Tq, Ts = IE.build_panel(Mq), IE.build_panel(Ms)
    tq = IE.sleeve_picks(Tq, 'sharpe', k=2, keep=5)
    ts = IE.sleeve_picks(Ts, 'mom', k=1, keep=3)
    same_q = all(set(tq[t]) == set(pk_q[t]) for t in tq)
    same_s = all(set(ts[t]) == set(pk_s[t]) for t in ts)
    a = Pq[Pq.t <= cut].set_index(['t', 'ticker'])['sharpe']
    b = Tq.set_index(['t', 'ticker'])['sharpe']
    j = pd.concat([a, b], axis=1, keys=['full', 'cut']).dropna()
    a2 = Ps[Ps.t <= cut].set_index(['t', 'ticker'])['mom']
    b2 = Ts.set_index(['t', 'ticker'])['mom']
    j2 = pd.concat([a2, b2], axis=1, keys=['full', 'cut']).dropna()
    res.append({'cutoff': cut.date(), 'months': len(tq), 'NDX_picks_identical': same_q, 'SPX_picks_identical': same_s,
                'NDX_max_abs_score_diff': float((j['full'] - j['cut']).abs().max()),
                'SPX_max_abs_score_diff': float((j2['full'] - j2['cut']).abs().max()),
                'NDX_rows_valid_full_vs_cut': f"{int(a.notna().sum())}/{int(b.notna().sum())}",
                'SPX_rows_valid_full_vs_cut': f"{int(a2.notna().sum())}/{int(b2.notna().sum())}"})
    print(res[-1])
IE.load = IE.functools.lru_cache(maxsize=None)(orig_load)
IE.calendar.cache_clear()   # calendar must be rebuilt from the FULL SPY file after the truncation runs
if res:
    pd.DataFrame(res).to_csv(os.path.join(HERE, '06a_truncation_test_independent.csv'), index=False)

# ---------------- (2)(3)(4)
rows = []
for t in sorted(pk_q):
    for leg, pk, P in (('qqq', pk_q, Pq), ('spy', pk_s, Ps)):
        for tk in pk[t]:
            r = P[(P.t == t) & (P.ticker == tk)].iloc[0]
            d0, d1 = IE.first_session_after(t), IE.first_session_after(t + pd.offsets.MonthEnd(1))
            alt = {}
            for src, sym in IE.candidate_series(tk):
                df = IE.load_fixed(src, sym)
                if df is None or d0 not in df.index or d1 not in df.index:
                    continue
                if np.isfinite(df.at[d0, 'o']) and np.isfinite(df.at[d1, 'o']):
                    alt.setdefault(src, df.at[d1, 'o'] / df.at[d0, 'o'] - 1)
            rows.append({'t': t.date(), 'leg': leg, 'ticker': tk, 'ret_used': r['hold_ret'], 'flag': r['ret_flag'],
                         'yahoo_oo': alt.get('yahoo'), 'tiingo_oo': alt.get('tiingo'), 'wiki_oo': alt.get('wiki'),
                         'n_vendors': len(alt)})
X = pd.DataFrame(rows)
for c in ('yahoo_oo', 'tiingo_oo', 'wiki_oo'):
    X[c] = pd.to_numeric(X[c])
v = X[['yahoo_oo', 'tiingo_oo', 'wiki_oo']]
X['vendor_spread'] = v.max(axis=1) - v.min(axis=1)
X.to_csv(os.path.join(HERE, '06b_pick_vendor_crosscheck.csv'), index=False)
print('\nReturn flags of all pick-months:\n', X['flag'].str.replace(r'_via_.*', '_via_alias', regex=True).value_counts().to_string())
multi = X[X['n_vendors'] >= 2]
print(f'\nPick-months with >=2 vendors: {len(multi)} / {len(X)}; max vendor spread {multi["vendor_spread"].max():.5f}; '
      f'spread > 50bp: {(multi["vendor_spread"] > 0.005).sum()}')
print(multi[multi['vendor_spread'] > 0.005].to_string(index=False))
big = X[X['ret_used'].abs() > 0.30]
print(f'\nPick-months with |ret| > 30%: {len(big)}')
pd.set_option('display.width', 250)
print(big.to_string(index=False))
