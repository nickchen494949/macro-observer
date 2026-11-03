#!/usr/bin/env python3
"""
a6_truncation_test.py — physical look-ahead test.

For EVERY formation month-end t (2008-12 .. 2026-08):
  1. membership: rebuild the roster at t from YAML files whose change entries dated > t are DELETED
     (and later-year files removed) -> must equal the roster used by the backtest;
  2. prices: cut every vendor series at t BEFORE any cleaning (a2_engine.CUTOFF = t), recompute 12-1
     momentum for every member -> eligible set, values and full ranking must equal the full-data panel.
Output: t_truncation_test.csv (one row per month) ; exits 1 if any month differs.
"""
import os
import sys

import numpy as np
import pandas as pd

import a1_universe as U
import a2_engine as E

HERE = os.path.dirname(os.path.abspath(__file__))


def roster_truncated(years, t):
    t = pd.Timestamp(t)
    yrs = {y: (set(s), [c for c in ch if c[0] <= t]) for y, (s, ch) in years.items() if y <= t.year}
    return U.members_on(yrs, t)


def main():
    years = U.load_years()
    P = pd.read_parquet(os.path.join(HERE, 's_panel.parquet'))
    members = E.load_members()
    rows = []
    for t in E.month_ends('2008-12-31', '2026-08-31'):
        mem_full = set(members[t])
        mem_trunc = roster_truncated(years, t)
        E.CUTOFF = t
        E._series_cut.cache_clear()
        got = []
        for tk in sorted(mem_trunc):
            m, st, sym = E.momentum(tk, t)
            if np.isfinite(m):
                got.append((tk, m, st, sym))
        G = pd.DataFrame(got, columns=['ticker', 'mom', 'store', 'sym']).sort_values(['mom', 'ticker'], ascending=[False, True])
        G['rank'] = np.arange(1, len(G) + 1)
        F = P[P.t == t].sort_values('rank')
        same_elig = set(G.ticker) == set(F.ticker)
        m = G.merge(F, on='ticker', suffixes=('_trunc', '_full'))
        maxdiff = float((m.mom_trunc - m.mom_full).abs().max()) if len(m) else np.nan
        same_rank = bool((m.rank_trunc == m.rank_full).all()) and same_elig
        rows.append({'t': t.date(), 'roster_equal': mem_full == mem_trunc, 'n_members': len(mem_full),
                     'eligible_equal': same_elig, 'n_eligible_full': len(F), 'n_eligible_trunc': len(G),
                     'max_abs_mom_diff': maxdiff, 'ranking_equal': same_rank,
                     'top3_full': '|'.join(F.ticker[:3]), 'top3_trunc': '|'.join(G.ticker[:3]),
                     'only_full': '|'.join(sorted(set(F.ticker) - set(G.ticker))),
                     'only_trunc': '|'.join(sorted(set(G.ticker) - set(F.ticker)))})
    E.CUTOFF = None
    E._series_cut.cache_clear()
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(HERE, 't_truncation_test.csv'), index=False)
    ok = T.roster_equal & T.eligible_equal & T.ranking_equal & (T.max_abs_mom_diff.fillna(0) == 0)
    print(f'truncation test: {ok.sum()}/{len(T)} months identical (roster, eligible set, momentum values, full ranking)')
    print(f'top-3 identical in {(T.top3_full == T.top3_trunc).sum()}/{len(T)} months')
    if not ok.all():
        print(T[~ok].to_string())
        sys.exit(1)


if __name__ == '__main__':
    main()
