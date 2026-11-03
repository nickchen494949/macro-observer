#!/usr/bin/env python3
"""
05_stats_daily_costs.py — on the INDEPENDENT engine:
  (a) single-account ledger (cross-leg rebalancing cost included) vs sleeve-additive accounting
  (b) cost stress 10/20/30/50 bp, execution-lag stress (T+1 open vs T+2 open)
  (c) true daily mark-to-market path (entry at adjusted open, daily closes, exit at next open) -> daily MaxDD
  (d) full statistics: CAGR, excess Sharpe (3M T-bill), monthly MaxDD, sub-periods, calendar years,
      Newey-West t vs QQQ/SPY ETF, stationary bootstrap CI for CAGR.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ind_engine as IE

ROOT = IE.ROOT
Pq = pd.read_parquet(os.path.join(HERE, 'ind_panel_ndx.parquet'))
Ps = pd.read_parquet(os.path.join(HERE, 'ind_panel_spx.parquet'))
pk_q = IE.sleeve_picks(Pq, 'sharpe', k=2, keep=5)
pk_s = IE.sleeve_picks(Ps, 'mom', k=1, keep=3)
months = sorted(set(pk_q) & set(pk_s))

rf = pd.Series({pd.Timestamp(d): float(v) / 100 for d, v in json.load(open(os.path.join(ROOT, 'data/fred/DGS3MO.json')))['values']
                if v not in (None, '.')}).sort_index().resample('ME').last() / 12.0


def ledger(cost=0.0010):
    IE.COST = cost
    L = IE.simulate({'qqq': Pq, 'spy': Ps}, {'qqq': pk_q, 'spy': pk_s}, {'qqq': 0.5, 'spy': 0.5})
    IE.COST = 0.0010
    return L


def sleeve_additive(cost=0.0010):
    out = []
    prev = {'qqq': {}, 'spy': {}}
    look = {('qqq', t, tk): r for t, tk, r in Pq[['t', 'ticker', 'hold_ret']].itertuples(index=False)}
    look.update({('spy', t, tk): r for t, tk, r in Ps[['t', 'ticker', 'hold_ret']].itertuples(index=False)})
    for t in months:
        tot = 0.0
        for leg, pk in (('qqq', pk_q), ('spy', pk_s)):
            w = {x: 1 / len(pk[t]) for x in pk[t]}
            r = {x: look[(leg, t, x)] for x in w}
            to = sum(abs(w.get(x, 0) - prev[leg].get(x, 0)) for x in set(w) | set(prev[leg])) if prev[leg] else 1.0
            g = sum(w[x] * r[x] for x in w)
            den = sum(w[x] * (1 + r[x]) for x in w)
            prev[leg] = {x: w[x] * (1 + r[x]) / den for x in w}
            tot += 0.5 * (g - cost * to)
        out.append(tot)
    return pd.Series(out, index=months)


def stats(r, label):
    r = pd.Series(r.values, index=pd.DatetimeIndex(r.index) + pd.offsets.MonthEnd(1))   # holding-month end
    n = len(r)
    cagr = np.prod(1 + r) ** (12 / n) - 1
    ex = r - rf.reindex(r.index).ffill().fillna(0)
    sh = ex.mean() / r.std(ddof=1) * np.sqrt(12)
    w = np.concatenate([[1], np.cumprod(1 + r.values)])
    mdd = (w / np.maximum.accumulate(w) - 1).min()
    sub = lambda a, b: np.prod(1 + r.loc[a:b]) ** (12 / len(r.loc[a:b])) - 1
    return {'Variant': label, 'Months': n, 'CAGR': cagr, 'Excess_Sharpe': sh, 'Ann_Vol': r.std(ddof=1) * np.sqrt(12),
            'Monthly_MaxDD': mdd, 'CAGR_2009_2018': sub('2009', '2018'), 'CAGR_2019_2026': sub('2019', '2026'),
            'Ret_2022': np.prod(1 + r.loc['2022']) - 1, 'Worst_Month': r.min(), 'Best_Month': r.max()}


rows = []
L = ledger()
rows.append(stats(L['net'], 'INDEPENDENT single-account, 10bp (cross-leg rebalancing cost INCLUDED)'))
rows.append(stats(sleeve_additive(), 'INDEPENDENT sleeve-additive, 10bp (claimed accounting convention)'))
for c in (0.0020, 0.0030, 0.0050):
    rows.append(stats(ledger(c)['net'], f'INDEPENDENT single-account, {int(c*1e4)}bp/side'))
print('avg monthly turnover (single account):', L['turnover'].mean())

# ---------- (c) true daily mark-to-market path
def series_for(P, t, tk):
    row = P[(P.t == t) & (P.ticker == tk)].iloc[0]
    fl = str(row['ret_flag'])
    if fl.startswith('open_open_via_'):
        src, sym = fl.replace('open_open_via_', '').split(':', 1)
    else:
        src, sym = row['src'], row['sym']
    return IE.load_fixed(src, sym)


cal = IE.calendar()
W, path = 1.0, {}
for t in months:
    row = L.loc[t]
    d0, d1 = IE.first_session_after(t), IE.first_session_after(t + pd.offsets.MonthEnd(1))
    days = cal[(cal >= d0) & (cal < d1)]
    legs_of = {tk: ('qqq' if tk in pk_q[t] else 'spy') for tk in row['weights']}
    ser = {tk: series_for(Pq if legs_of[tk] == 'qqq' else Ps, t, tk) for tk in row['weights']}
    cost = row['gross'] - row['net']
    Wd = W * (1 - cost)
    for d in days:
        v = 0.0
        for tk, wt in row['weights'].items():
            df = ser[tk]
            p0 = df.at[d0, 'o'] if (d0 in df.index and np.isfinite(df.at[d0, 'o'])) else df.at[d0, 'c']
            c = df['c'].loc[:d]
            v += wt * (c.iloc[-1] / p0)            # after delisting the last close is carried (cash, 0%)
        path[d] = Wd * v
    W = W * (1 + row['net'])
    path[d1] = W
P_daily = pd.Series(path).sort_index()
dd = P_daily / P_daily.cummax() - 1
trough = dd.idxmin()
peak = P_daily.loc[:trough].idxmax()
print(f'TRUE DAILY MaxDD (independent): {dd.min():.4f}  peak {peak.date()} -> trough {trough.date()}')
P_daily.to_frame('nav').to_csv(os.path.join(HERE, '05_independent_daily_nav.csv'))
for r_ in rows:
    r_['True_Daily_MaxDD'] = dd.min() if r_['Variant'].startswith('INDEPENDENT single-account, 10bp') else np.nan

# ---------- (d) benchmarks + Newey-West + bootstrap
def etf_month(sym):
    df = IE.load('yahoo', sym)
    if df is None:
        df = IE.load('tiingo', sym)
    out = {}
    for t in months:
        d0, d1 = IE.first_session_after(t), IE.first_session_after(t + pd.offsets.MonthEnd(1))
        out[t] = df.at[d1, 'o'] / df.at[d0, 'o'] - 1
    return pd.Series(out)


r = L['net']
for b in ('QQQ', 'SPY'):
    rb = etf_month(b)
    rows.append(stats(rb, f'Benchmark {b} ETF (open-to-open, no cost)'))
    dlt = (r - rb).values
    e = dlt - dlt.mean()
    v = e @ e / len(e)
    for lag in range(1, 7):
        v += 2 * (1 - lag / 7) * (e[lag:] @ e[:-lag]) / len(e)
    print(f'NW(6) t-stat of monthly excess over {b}: {dlt.mean() / np.sqrt(v / len(e)):.2f}')

rng = np.random.default_rng(7)
vals = r.values
bs = []
for _ in range(5000):                       # stationary bootstrap, mean block 6 months
    idx, i = [], rng.integers(len(vals))
    while len(idx) < len(vals):
        idx.append(i)
        i = rng.integers(len(vals)) if rng.random() < 1 / 6 else (i + 1) % len(vals)
    s = vals[idx]
    bs.append(np.prod(1 + s) ** (12 / len(s)) - 1)
print('Stationary-bootstrap CAGR 5/50/95%:', np.percentile(bs, [5, 50, 95]).round(4), ' P(CAGR<20%)=', np.mean(np.array(bs) < 0.20))

S = pd.DataFrame(rows)
S.to_csv(os.path.join(HERE, '05_independent_stats.csv'), index=False)
pd.set_option('display.width', 250)
print(S.to_string(index=False))
yr = pd.Series(r.values, index=pd.DatetimeIndex(r.index) + pd.offsets.MonthEnd(1))
print((yr.groupby(yr.index.year).apply(lambda x: np.prod(1 + x) - 1) * 100).round(2).to_string())
