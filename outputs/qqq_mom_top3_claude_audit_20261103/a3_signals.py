#!/usr/bin/env python3
"""
a3_signals.py — PIT 12-1 momentum for every Nasdaq-100 member at every formation month-end
2008-12-31 .. 2026-08-31 (last formation whose next-month holding period is complete in the data).

Outputs
  s_panel.parquet / s_panel.csv  t, ticker, mom, store, sym, rank (1 = highest momentum; ties by ticker)
  s_coverage_by_month.csv        members, priced, eligible per month
  s_gaps_member_months.csv       every member-month without a momentum value + reason
"""
import os

import numpy as np
import pandas as pd

import a2_engine as E

HERE = os.path.dirname(os.path.abspath(__file__))


def reason(tk, t):
    c = E.candidates(tk)
    if not c:
        return 'no_price_series_in_any_store'
    t = pd.Timestamp(t)
    best = []
    for st, sym in c:
        df = E.series(st, sym)
        best.append(f'{st}:{sym}:{df.index.min().date()}..{df.index.max().date()}')
    first = min(E.series(st, sym).index.min() for st, sym in c)
    last = max(E.series(st, sym).index.max() for st, sym in c)
    if first > t - pd.offsets.MonthEnd(12) + pd.Timedelta(days=7):
        return 'history_shorter_than_12m | ' + ' ; '.join(best)
    if last < t - pd.Timedelta(days=7):
        return 'series_ends_before_t | ' + ' ; '.join(best)
    return 'stale_or_gap>30d | ' + ' ; '.join(best)


def build(lb=12, skip=1, start='2008-12-31', end='2026-08-31', members=None):
    members = members or E.load_members()
    rows, gaps, cov = [], [], []
    for t in E.month_ends(start, end):
        mem = members.get(t, [])
        n_ok = 0
        for tk in mem:
            m, st, sym = E.momentum(tk, t, lb=lb, skip=skip)
            if np.isfinite(m):
                rows.append((t, tk, m, st, sym))
                n_ok += 1
            elif lb == 12 and skip == 1:
                gaps.append((t.date(), tk, reason(tk, t)))
        cov.append((t.date(), len(mem), n_ok))
    P = pd.DataFrame(rows, columns=['t', 'ticker', 'mom', 'store', 'sym'])
    P = P.sort_values(['t', 'mom', 'ticker'], ascending=[True, False, True])
    P['rank'] = P.groupby('t').cumcount() + 1
    return P.reset_index(drop=True), pd.DataFrame(gaps, columns=['t', 'ticker', 'reason']), \
        pd.DataFrame(cov, columns=['t', 'members', 'eligible'])


def main():
    P, G, C = build()
    P.to_parquet(os.path.join(HERE, 's_panel.parquet'), index=False)
    P.to_csv(os.path.join(HERE, 's_panel.csv'), index=False)
    G.to_csv(os.path.join(HERE, 's_gaps_member_months.csv'), index=False)
    C.to_csv(os.path.join(HERE, 's_coverage_by_month.csv'), index=False)
    C['pct'] = C.eligible / C.members
    print(f'{len(C)} formation months, {len(P)} eligible stock-months, mean eligible/members {C.pct.mean():.3%}')
    print('store usage:', P.groupby('store').size().to_dict())
    print('gap reasons:', G.reason.str.split(' |', regex=False).str[0].value_counts().to_dict())
    g2 = G[~G.reason.str.startswith('history_shorter')]
    print('non-new-listing gaps by ticker:')
    print(g2.groupby('ticker').agg(n=('t', 'size'), first=('t', 'min'), last=('t', 'max'), why=('reason', 'first')).to_string())


if __name__ == '__main__':
    main()
