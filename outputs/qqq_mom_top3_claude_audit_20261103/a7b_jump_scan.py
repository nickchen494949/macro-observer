#!/usr/bin/env python3
"""
a7b_jump_scan.py — corporate-action / bad-adjustment scan for every name that ever ranked Top-6.

For each series actually used for momentum (store, sym from s_panel), list every daily adj-close move
with |r| > 35%, and compare it with every other store holding the same symbol on the same day.
A move that the other vendor does not show (|diff| > 5 pts) is a candidate bad adjustment and must be
explained (spin-off, split, ticker recycling). Moves with no second vendor are listed as unconfirmed.
Output: v_jump_scan.csv
"""
import os

import numpy as np
import pandas as pd

import a2_engine as E

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    P = pd.read_parquet(os.path.join(HERE, 's_panel.parquet'))
    used = P[P['rank'] <= 6][['ticker', 'store', 'sym']].drop_duplicates()
    rows = []
    for tk, st, sym in used.itertuples(index=False):
        df = E.series(st, sym)
        r = df['adjclose'].pct_change(fill_method=None)
        big = r[r.abs() > 0.35]
        for d, v in big.items():
            others = {}
            for st2, sym2 in E.candidates(tk):
                if (st2, sym2) == (st, sym):
                    continue
                o = E.series(st2, sym2)['adjclose']
                if d in o.index:
                    prev = o.loc[:d - pd.Timedelta(days=1)].dropna()
                    if len(prev):
                        others[f'{st2}:{sym2}'] = o.at[d] / prev.iloc[-1] - 1
            conf = [k for k, x in others.items() if abs(x - v) <= 0.05]
            rows.append({'ticker': tk, 'store': st, 'sym': sym, 'date': d.date(), 'ret': v,
                         'other_vendors': '; '.join(f'{k}={x:+.3f}' for k, x in others.items()),
                         'status': 'confirmed' if conf else ('CONFLICT' if others else 'single_vendor')})
    J = pd.DataFrame(rows).sort_values(['status', 'ticker', 'date'])
    J.to_csv(os.path.join(HERE, 'v_jump_scan.csv'), index=False)
    pd.set_option('display.width', 250)
    print(J.status.value_counts().to_dict())
    print(J[J.status != 'confirmed'].to_string())


if __name__ == '__main__':
    main()
