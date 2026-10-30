#!/usr/bin/env python3
"""
identity_screen_earnings.py — does the price series we hold for (ticker, CIK) belong to THAT SEC filer?

Independent evidence: the filer's own earnings-release dates (SEC 8-K item 2.02, data/earnings_dates.csv).
A real company's stock moves more on its own earnings days than on ordinary days. For each (ticker, CIK) pair used
in the factor panel, over the panel months the pair is used:
   ratio = mean |5-day return − SPY| (close R−3 → close R+1) around the CIK's 8-K 2.02 reaction dates R  /  same statistic
           on all windows that do not touch an event. The window starts 3 sessions early because many companies
           publish the press release 1–2 days BEFORE they file the 8-K (checked on BIG, PLL, CVC: the move is at R−1/R−2)
True pairs: ratio typically 1.8–3. A price series of a DIFFERENT company: ratio ≈ 1.
Flag: ratio < 1.25 with >= 8 events.  Output: results/identity_screen_earnings.csv (+ printed flags for review).
Pairs without earnings dates (no 8-K 2.02 found) are listed as 'no_events' (not tested).
"""
import os

import numpy as np
import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))


def main(panel=os.path.join(HERE, 'results', 'explosive', 'panel_explosive.parquet'), out=os.path.join(HERE, 'results', 'identity_screen_earnings.csv')):
    daily = bt.load_prices()[0]
    X = pd.read_parquet(panel, columns=['t', 'ticker', 'cik'])
    ed = pd.read_csv(os.path.join(HERE, 'data', 'earnings_dates.csv'), parse_dates=['reaction_date'])
    sess = daily['SPY'].dropna().index
    spy = daily['SPY'].reindex(sess)
    rows = []
    for (tk, cik), g in X.dropna(subset=['cik']).groupby(['ticker', 'cik']):
        a, z = g.t.min() - pd.offsets.MonthEnd(12), g.t.max() + pd.offsets.MonthEnd(1)
        s = daily[tk].reindex(sess)
        r3 = (s.shift(-1) / s.shift(3) - 1) - (spy.shift(-1) / spy.shift(3) - 1)       # close k−3 → close k+1
        r3 = r3[(r3.index >= a) & (r3.index <= z)].dropna().abs()
        ev = ed[ed.cik == int(cik)].reaction_date
        k = sess[np.clip(sess.searchsorted(ev.values), 0, len(sess) - 1)]
        k = pd.DatetimeIndex(k).intersection(r3.index)
        if len(k) < 8:
            rows.append({'ticker': tk, 'cik': int(cik), 'events': len(k), 'ratio': np.nan, 'flag': 'no_events'})
            continue
        pos = np.searchsorted(r3.index.values, k.values)
        near = np.zeros(len(r3), bool)
        for o in range(-4, 5):
            q = pos + o
            near[q[(q >= 0) & (q < len(r3))]] = True
        ratio = r3[r3.index.isin(k)].mean() / r3[~near].mean()
        rows.append({'ticker': tk, 'cik': int(cik), 'events': len(k), 'ratio': ratio,
                     'panel_first': g.t.min().date(), 'panel_last': g.t.max().date(), 'source': bt.PRICE_SOURCE.get(tk),
                     'flag': 'SUSPECT' if ratio < 1.25 else 'ok'})
    R = pd.DataFrame(rows).sort_values('ratio')
    R.to_csv(out, index=False)
    print(R.flag.value_counts().to_dict(), '| median ratio', round(R.ratio.median(), 2))
    print(R[R.flag == 'SUSPECT'].to_string(index=False))
    return R


if __name__ == '__main__':
    main()
