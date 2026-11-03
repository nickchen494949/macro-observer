#!/usr/bin/env python3
"""
a8b_membership_doubt.py — every SPEC Top-3 pick checked against the independent Wikipedia snapshot,
and a falsification variant that removes every pick whose membership is not confirmed.

A pick (t, ticker) is 'confirmed' if the ticker (or its rename alias / predecessor) is listed in the
Wikipedia "Nasdaq-100" revision live at month-end t, or in the revision live at the next month-end
(Wikipedia edits often lag Nasdaq's effective dates by days). Unparseable snapshots count as 'no_snapshot'.
Outputs: u_pick_membership_check.csv, x_membership_doubt_variant.csv
"""
import os

import numpy as np
import pandas as pd

import a1c_compare_wiki as C
import a2_engine as E
import a4_backtest as B
import a5_stats_stress as X

HERE = os.path.dirname(os.path.abspath(__file__))
ALIAS = {k: v[0] for k, v in E.RENAME.items()}
ALIAS.update({'TCOM': 'CTRP', 'META': 'FB', 'BKNG': 'PCLN', 'MNST': 'HANS', 'MDLZ': 'KFT', 'WFM': 'WFMI'})


def snapshot(me):
    import json
    fn = os.path.join(HERE, 'wiki_ndx', f'{pd.Timestamp(me).date()}.json')
    if not os.path.exists(fn):
        return None
    w = json.load(open(fn))['wikitext']
    sec = C.components_section(w)
    tk = C.tickers(sec, w)
    return tk if len(tk) >= 90 else None


def main():
    P = pd.read_parquet(os.path.join(HERE, 's_panel.parquet'))
    H = B.hold_table(P, 'open')
    L = B.run(P, H)
    rows = []
    cache = {}
    for _, r in L.iterrows():
        t = r['t']
        for me in (t, t + pd.offsets.MonthEnd(1)):
            if me not in cache:
                cache[me] = snapshot(me)
        for s in r['picks'].split('|'):
            names = {s, ALIAS.get(s, s)} | {k for k, v in ALIAS.items() if v == s}
            a, b = cache[t], cache[t + pd.offsets.MonthEnd(1)]
            if a is None and b is None:
                st = 'no_snapshot'
            elif (a and names & a) or (b and names & b):
                st = 'confirmed'
            else:
                st = 'NOT_in_wikipedia'
            rows.append({'t': t.date(), 'month': r['month'].date(), 'ticker': s, 'status': st})
    U = pd.DataFrame(rows)
    U.to_csv(os.path.join(HERE, 'u_pick_membership_check.csv'), index=False)
    print(U.status.value_counts().to_dict())
    print(U[U.status != 'confirmed'].to_string())
    bad = {(pd.Timestamp(t), s) for t, s, st in zip(U.t, U.ticker, U.status) if st == 'NOT_in_wikipedia'}
    if bad:
        # remove doubtful names month by month (next rank moves up)
        P2 = P[~P.apply(lambda r: (r.t, r.ticker) in bad, axis=1)].copy()
        P2['rank'] = P2.groupby('t')['mom'].rank(ascending=False, method='first').astype(int)
        L2 = B.run(P2, H)
    else:
        L2 = L
    rows = []
    for wn, a, b in X.WINDOWS:
        rows.append({'window': wn, 'SPEC': X.cagr(L.set_index('month').loc[a:b, 'net']),
                     'excluding_unconfirmed_picks': X.cagr(L2.set_index('month').loc[a:b, 'net'])})
    D = pd.DataFrame(rows)
    D.to_csv(os.path.join(HERE, 'x_membership_doubt_variant.csv'), index=False)
    print(D.to_string())


if __name__ == '__main__':
    main()
