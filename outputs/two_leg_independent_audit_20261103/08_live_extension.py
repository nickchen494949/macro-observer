#!/usr/bin/env python3
"""08_live_extension.py — extend the INDEPENDENT engine past the backtest window (formation 2026-09-30, holding October
2026) and mark the live drawdown to the latest available close. Prior holdings come from the audited ledger."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ind_engine as IE

L = pd.read_csv(os.path.join(HERE, 'ind_ledger_G1_SPY_2e.csv'), index_col=0, parse_dates=True)
nav_hist = pd.read_csv(os.path.join(HERE, '05_independent_daily_nav.csv'), index_col=0, parse_dates=True)['nav']
last_t = L.index[-1]
held_q, held_s = L.iloc[-1]['qqq_picks'].split('|'), [L.iloc[-1]['spy_pick']]

for t in [pd.Timestamp('2026-09-30'), pd.Timestamp('2026-10-31')]:
    IE.FORM_START = IE.FORM_END = t
    Mq, Ms = IE.ndx_members(), IE.spx_members()
    Pq, Ps = IE.build_panel(Mq), IE.build_panel(Ms)
    rq = Pq.dropna(subset=['sharpe']).sort_values(['sharpe', 'ticker'], ascending=[False, True]).reset_index(drop=True)
    rs = Ps.dropna(subset=['mom']).sort_values(['mom', 'ticker'], ascending=[False, True]).reset_index(drop=True)
    rank_q = {x: i + 1 for i, x in enumerate(rq.ticker)}
    rank_s = {x: i + 1 for i, x in enumerate(rs.ticker)}
    kq = sorted([x for x in held_q if rank_q.get(x, 999) <= 5], key=lambda x: rank_q[x])[:2]
    for x in rq.ticker:
        if len(kq) >= 2:
            break
        if x not in kq:
            kq.append(x)
    ks = [x for x in held_s if rank_s.get(x, 999) <= 3][:1] or [rs.ticker.iloc[0]]
    print(f'\n=== formation {t.date()} (holding {(t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")}) ===')
    print('QQQ leg top-6:', [(x, round(s, 3), rank_q[x]) for x, s in zip(rq.ticker[:6], rq.sharpe[:6])])
    print('SPY leg top-4:', [(x, round(m, 3)) for x, m in zip(rs.ticker[:4], rs.mom[:4])])
    print('previous holdings  QQQ', held_q, 'SPY', held_s, '-> ranks', {x: rank_q.get(x) for x in held_q}, {x: rank_s.get(x) for x in held_s})
    print('NEW HOLDINGS       QQQ', kq, ' SPY', ks)
    if t == pd.Timestamp('2026-09-30'):
        # mark October to market with the latest data (Yahoo to 10-29, Tiingo to 11-02)
        w = {}
        for x in kq:
            w[x] = w.get(x, 0) + 0.25
        for x in ks:
            w[x] = w.get(x, 0) + 0.50
        d0 = IE.first_session_after(t)
        W0 = nav_hist.iloc[-1]
        prev_w = {}
        lastrow = L.iloc[-1]
        # turnover vs drifted September weights
        sep_w = {}
        for x in lastrow['qqq_picks'].split('|'):
            sep_w[x] = sep_w.get(x, 0) + 0.25
        sep_w[lastrow['spy_pick']] = sep_w.get(lastrow['spy_pick'], 0) + 0.5
        to = sum(abs(w.get(x, 0) - sep_w.get(x, 0)) for x in set(w) | set(sep_w))   # approx (ignores Sept drift)
        series = {}
        for x in w:
            for src, sym in IE.candidate_series(x):
                df = IE.load_fixed(src, sym)
                if df is not None and d0 in df.index:
                    series[x] = df
                    break
        days = sorted(set.intersection(*[set(s.loc[d0:].index) for s in series.values()]))
        live = {}
        for d in days:
            live[d] = W0 * (1 - IE.COST * to) * sum(w[x] * series[x].at[d, 'c'] / series[x].at[d0, 'o'] for x in w)
        live = pd.Series(live)
        full = pd.concat([nav_hist, live]).sort_index()
        full = full[~full.index.duplicated(keep='last')]
        dd = full / full.cummax() - 1
        print('October weights', w, ' est. turnover', round(to, 3))
        print('Oct MTM path (last 5):', live.tail(5).round(4).to_dict())
        print(f'October return to {live.index[-1].date()}: {live.iloc[-1] / W0 - 1:.4f}')
        print(f'Peak NAV date {full.loc[:dd.idxmin()].idxmax().date()} | LIVE drawdown at {full.index[-1].date()}: {dd.iloc[-1]:.4f} '
              f'| max daily DD incl. live: {dd.min():.4f} on {dd.idxmin().date()}')
        full.to_frame('nav').to_csv(os.path.join(HERE, '08_daily_nav_with_live_oct2026.csv'))
    held_q, held_s = kq, ks
