#!/usr/bin/env python3
"""
a5_stats_stress.py — performance, benchmarks, adversarial stress and statistics for the Claude
clean-room QQQ 12-1 Top-3 ledger. Everything is recomputed from a2/a3/a4 outputs (no project code).

Outputs
  x_perf_windows.csv          SPEC + benchmarks over all windows (CAGR, vol, Sharpe, MaxDD monthly/daily)
  x_calendar_years.csv        calendar-year net returns
  x_stress.csv                every stress / falsification variant x window
  x_paired_tests.csv          NW-t, stationary block bootstrap, alpha/beta vs QQQ, vs NDX-EW, vs Top-1
  x_contribution.csv          log-wealth contribution by ticker
  x_monthly_ledgers.csv       monthly net returns of every variant (for audit)
"""
import glob
import os

import numpy as np
import pandas as pd
from scipy import stats as sst

import a2_engine as E
import a3_signals as S
import a4_backtest as B

HERE = os.path.dirname(os.path.abspath(__file__))
RF = pd.read_csv(os.path.join(E.D, 'rf_monthly.csv'), index_col=0, parse_dates=True)['rf_monthly']
WINDOWS = [('FULL 2009-01..2026-09', '2009-01-31', '2026-09-30'),
           ('2009-2014', '2009-01-31', '2014-12-31'),
           ('2015-2019', '2015-01-31', '2019-12-31'),
           ('2020-2022', '2020-01-31', '2022-12-31'),
           ('2023-2026.09', '2023-01-31', '2026-09-30'),
           ('ORIG 2015-02..2026-09', '2015-02-28', '2026-09-30'),
           ('ORIG 2019-01..2026-09', '2019-01-31', '2026-09-30'),
           ('2009-2018 (pre-2019)', '2009-01-31', '2018-12-31')]


# ------------------------------------------------------------------ metrics
def cagr(r):
    r = pd.Series(r).dropna()
    return np.prod(1 + r) ** (12 / len(r)) - 1 if len(r) else np.nan


def maxdd(r):
    w = np.cumprod(1 + pd.Series(r).dropna().values)
    w = np.concatenate([[1.0], w])
    return float((w / np.maximum.accumulate(w) - 1).min())


def sharpe(r):
    r = pd.Series(r).dropna()
    ex = r - RF.reindex(r.index).fillna(0).values
    return ex.mean() / ex.std(ddof=1) * np.sqrt(12) if ex.std() > 0 else np.nan


def nw_t(x, lag):
    x = np.asarray(pd.Series(x).dropna(), float)
    n = len(x)
    e = x - x.mean()
    s = e @ e / n
    for L in range(1, lag + 1):
        s += 2 * (1 - L / (lag + 1)) * (e[L:] @ e[:-L]) / n
    se = np.sqrt(s / n)
    t = x.mean() / se
    return t, 2 * (1 - sst.norm.cdf(abs(t)))


def stationary_boot_idx(n, mean_block, rng):
    idx = np.empty(n, int)
    i = rng.integers(n)
    p = 1.0 / mean_block
    for k in range(n):
        idx[k] = i
        i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return idx


def boot_diff(a, b, draws=5000, block=6, seed=11):
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    n = len(a)
    d = np.empty(draws)
    for j in range(draws):
        ix = stationary_boot_idx(n, block, rng)
        d[j] = cagr(a[ix]) - cagr(b[ix])
    return np.percentile(d, [5, 50, 95]), float((d <= 0).mean())


# ------------------------------------------------------------------ daily path (for daily MaxDD)
def daily_maxdd(L, H):
    Hm = H.set_index(['t', 'ticker'])
    W = 1.0
    vals = []
    for _, row in L.iterrows():
        picks = row['picks'].split('|')
        start = W * (1 - row['cost'])
        comp = []
        for s in picks:
            h = Hm.loc[(row['t'], s)]
            df = E.series(h['ret_store'], h['ret_sym'])
            e, x = pd.Timestamp(h['entry']), pd.Timestamp(h['exit'])
            if 'close' in h['flag'] or df is None or e not in df.index or not np.isfinite(df.at[e, 'adjopen']):
                comp.append(None)
                continue
            p0 = df.at[e, 'adjopen']
            seg = df['adjclose'].loc[e:x].dropna()
            seg = seg[seg.index < x] / p0
            comp.append(seg)
        days = sorted(set().union(*[set(c.index) for c in comp if c is not None])) if any(c is not None for c in comp) else []
        for d in days:
            v = 0.0
            for s, c in zip(picks, comp):
                if c is None:
                    v += 1.0 / len(picks)   # no daily path available -> flat until month end (understates DD)
                else:
                    cc = c.loc[:d]
                    v += (cc.iloc[-1] if len(cc) else 1.0) / len(picks)
            vals.append(start * v)
        W = W * (1 + row['net'])
        vals.append(W)
    v = np.array([1.0] + vals)
    return float((v / np.maximum.accumulate(v) - 1).min())


def perf_row(name, L, a, b, H=None):
    s = L[(L.month >= a) & (L.month <= b)].set_index('month')['net']
    r = {'variant': name, 'window_start': a[:7], 'window_end': b[:7], 'n_months': len(s), 'CAGR': cagr(s),
         'vol': s.std(ddof=1) * np.sqrt(12), 'Sharpe': sharpe(s), 'MaxDD_monthly': maxdd(s),
         'best_month': s.max(), 'worst_month': s.min(), 'pct_pos_months': (s > 0).mean()}
    if H is not None:
        r['MaxDD_daily'] = daily_maxdd(L[(L.month >= a) & (L.month <= b)], H)
    return r


# ------------------------------------------------------------------ benchmarks
def qqq_ledger(months_t):
    """QQQ ETF, Tiingo adjOpen first trading day -> next month first trading day (same timing as SPEC)."""
    df = E.series('tiingo_api', 'QQQ')
    out = []
    for t in months_t:
        e, x = E.first_td_after(t), E.first_td_after(t + pd.offsets.MonthEnd(1))
        out.append({'t': t, 'month': t + pd.offsets.MonthEnd(1), 'net': df.at[x, 'adjopen'] / df.at[e, 'adjopen'] - 1,
                    'picks': 'QQQ', 'cost': 0.0, 'gross': np.nan, 'turnover': 0.0})
    return pd.DataFrame(out)


def ew_ledger(P, Hall, cost_bp=10.0):
    """Equal weight all eligible PIT NDX members, monthly rebalanced, open-to-open, 10bp on turnover."""
    Hm = Hall.set_index(['t', 'ticker'])['ret']
    prev = {}
    out = []
    for t, g in P.groupby('t'):
        names = [s for s in g.ticker if np.isfinite(Hm.get((t, s), np.nan))]
        w = {s: 1 / len(names) for s in names}
        rets = {s: Hm[(t, s)] for s in names}
        to = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in set(w) | set(prev))
        gross = sum(w[s] * rets[s] for s in names)
        prev = {s: w[s] * (1 + rets[s]) / (1 + gross) for s in names}
        out.append({'t': t, 'month': t + pd.offsets.MonthEnd(1), 'net': gross - to * cost_bp / 1e4, 'gross': gross,
                    'turnover': to, 'cost': to * cost_bp / 1e4, 'picks': f'EW{len(names)}'})
    return pd.DataFrame(out)


def contribution(L, H, a, b):
    Hm = H.set_index(['t', 'ticker'])['ret']
    rows = []
    for _, r in L[(L.month >= a) & (L.month <= b)].iterrows():
        picks = r['picks'].split('|')
        for s in picks:
            ret = Hm[(r['t'], s)]
            rows.append((s, r['month'], ret, (ret / len(picks)) / (1 + r['gross']) * np.log1p(r['net']) if r['gross'] != -1 else 0))
    C = pd.DataFrame(rows, columns=['ticker', 'month', 'ret', 'log_contrib'])
    tot = np.log1p(L[(L.month >= a) & (L.month <= b)].net).sum()
    G = C.groupby('ticker').agg(months=('month', 'size'), log_contrib=('log_contrib', 'sum'), best=('ret', 'max'),
                                worst=('ret', 'min')).sort_values('log_contrib', ascending=False)
    G['share_of_total_log_wealth'] = G.log_contrib / tot
    G['window'] = f'{a[:7]}..{b[:7]}'
    return G.reset_index()


def drop_best_months(L, n):
    L2 = L.copy()
    idx = L2.net.nlargest(n).index
    L2.loc[idx, 'net'] = 0.0
    return L2


def main():
    P = pd.read_parquet(os.path.join(HERE, 's_panel.parquet'))
    H = B.hold_table(P, 'open')
    Hall = B.hold_table(P, 'open', all_names=True)
    SPEC = B.run(P, H)
    months_t = sorted(SPEC.t)
    LED = {'SPEC Top-3 (10bp)': SPEC}

    # ---------------- benchmarks / neighbours
    LED['BENCH QQQ ETF'] = qqq_ledger(months_t)
    LED['BENCH NDX equal-weight (PIT, 10bp)'] = ew_ledger(P, Hall)
    LED['Top-1'] = B.run(P, H, k=1)
    LED['Top-2'] = B.run(P, H, k=2)
    LED['Top-5'] = B.run(P, H, k=5)
    LED['Top-10'] = B.run(P, H, k=10)
    for r in range(1, 7):
        LED[f'Rank #{r} alone'] = B.run(P, H, ranks=[r])
    LED['Ranks 4-6 (neighbour Top-3)'] = B.run(P, H, ranks=[4, 5, 6])
    LED['Ranks 2-4'] = B.run(P, H, ranks=[2, 3, 4])

    # ---------------- cost / execution stress
    for c in (20, 30, 50, 100):
        LED[f'Cost {c}bp/side'] = B.run(P, H, cost_bp=c)
    Hc1 = B.hold_table(P, 'close_t1')
    LED['Exec T+1 close (first trading day close)'] = B.run(P, Hc1)
    Hc0 = B.hold_table(P, 'close_t0')
    LED['Exec month-end close (no lag, optimistic)'] = B.run(P, Hc0)
    for nd in (2, 3, 5, 10):
        Hn = B.hold_table(P, 'open', n_day=nd)
        LED[f'Exec open of trading day {nd} (timing luck)'] = B.run(P, Hn)

    # ---------------- signal robustness (NOT optimisation: rule is frozen at 12-1)
    for lb, sk in [(11, 1), (12, 2), (9, 1), (6, 1), (12, 0)]:
        fn = os.path.join(HERE, f's_panel_lb{lb}_sk{sk}.parquet')
        if os.path.exists(fn):
            Pv = pd.read_parquet(fn)
        else:
            Pv, _, _ = S.build(lb=lb, skip=sk)
            Pv.to_parquet(fn, index=False)
        Hv = B.hold_table(Pv, 'open', tag=f'open_d1_lb{lb}_sk{sk}')
        LED[f'Signal {lb}-{sk} momentum'] = B.run(Pv, Hv)

    # ---------------- concentration / falsification
    for n in (1, 3, 5, 10):
        LED[f'Drop best {n} months (set to 0%)'] = drop_best_months(SPEC, n)
    con = contribution(SPEC, H, '2009-01-31', '2026-09-30')
    top_names = list(con.ticker[:6])
    for k in (1, 3, 6):
        LED[f'Ban top-{k} contributors ({",".join(top_names[:k])})'] = B.run(P, H, exclude=set(top_names[:k]))
    LED['Ban SNDK'] = B.run(P, H, exclude={'SNDK'})
    LED['Ban NVDA'] = B.run(P, H, exclude={'NVDA'})
    LED['Ban TSLA'] = B.run(P, H, exclude={'TSLA'})

    # ---------------- worst-case data treatment: every fallback-priced position at its worse alternative
    Hm = H.set_index(['t', 'ticker'])
    Hc1m = Hc1.set_index(['t', 'ticker'])
    ov = {}
    for (t, s), h in Hm.iterrows():
        if h['flag'] != 'open_to_open':
            alt = Hc1m['ret'].get((t, s), np.nan)
            ov[(t, s)] = min(h['ret'], alt) - 0.02 if np.isfinite(alt) else h['ret'] - 0.02
    LED['Worst-case: fallback-priced positions = min(open,close proxy) - 2%'] = B.run(P, H, ret_override=ov)
    LED['Worst-case combo: 30bp/side + T+1 close + fallback worst'] = B.run(P, Hc1, cost_bp=30, ret_override=ov)

    # ---------------- tables
    perf = []
    for name, L in LED.items():
        for wn, a, b in WINDOWS:
            r = perf_row(name, L, a, b, H=H if name == 'SPEC Top-3 (10bp)' else None)
            r['window'] = wn
            perf.append(r)
    X = pd.DataFrame(perf)
    X.to_csv(os.path.join(HERE, 'x_stress.csv'), index=False)
    X[X.variant.isin(['SPEC Top-3 (10bp)', 'BENCH QQQ ETF', 'BENCH NDX equal-weight (PIT, 10bp)', 'Top-1', 'Top-5'])].to_csv(
        os.path.join(HERE, 'x_perf_windows.csv'), index=False)

    M = pd.DataFrame({k: v.set_index('month')['net'] for k, v in LED.items()})
    M.to_csv(os.path.join(HERE, 'x_monthly_ledgers.csv'))
    cy = M[['SPEC Top-3 (10bp)', 'Top-1', 'BENCH QQQ ETF', 'BENCH NDX equal-weight (PIT, 10bp)']].groupby(M.index.year).apply(lambda d: (1 + d).prod() - 1)
    cy.to_csv(os.path.join(HERE, 'x_calendar_years.csv'))

    con2 = pd.concat([con, contribution(SPEC, H, '2019-01-31', '2026-09-30'), contribution(SPEC, H, '2009-01-31', '2018-12-31')])
    con2.to_csv(os.path.join(HERE, 'x_contribution.csv'), index=False)

    # ---------------- paired tests
    tests = []
    for wn, a, b in WINDOWS:
        if wn.startswith('2009-2014') or wn.startswith('2015-2019') or wn.startswith('2020') or wn.startswith('2023'):
            pass
        sa = M.loc[a:b, 'SPEC Top-3 (10bp)']
        for bn in ['BENCH QQQ ETF', 'BENCH NDX equal-weight (PIT, 10bp)', 'Top-1', 'Ranks 4-6 (neighbour Top-3)']:
            sb = M.loc[a:b, bn]
            d = (sa - sb).dropna()
            t3, p3 = nw_t(d, 3)
            t6, p6 = nw_t(d, 6)
            ci, pneg = boot_diff(sa.values, sb.values)
            row = {'window': wn, 'A': 'SPEC Top-3', 'B': bn, 'n': len(d), 'CAGR_A': cagr(sa), 'CAGR_B': cagr(sb),
                   'CAGR_diff': cagr(sa) - cagr(sb), 'mean_diff_ann': d.mean() * 12, 'NW_t_lag3': t3, 'NW_p_lag3': p3,
                   'NW_t_lag6': t6, 'NW_p_lag6': p6, 'boot_CAGRdiff_p5': ci[0], 'boot_CAGRdiff_p50': ci[1],
                   'boot_CAGRdiff_p95': ci[2], 'boot_P(diff<=0)': pneg, 'monthly_win_rate': (d > 0).mean()}
            if bn == 'BENCH QQQ ETF':
                rf = RF.reindex(sa.index).fillna(0)
                y, x = (sa - rf).values, (sb - rf).values
                Xm = np.column_stack([np.ones(len(x)), x])
                beta = np.linalg.lstsq(Xm, y, rcond=None)[0]
                resid = y - Xm @ beta
                at, ap = nw_t(beta[0] + resid, 3)   # NW t of alpha (mean of alpha+resid series = alpha)
                row.update({'alpha_ann': beta[0] * 12, 'beta': beta[1], 'alpha_NW_t': at, 'alpha_NW_p': ap})
            tests.append(row)
    T = pd.DataFrame(tests)
    T.to_csv(os.path.join(HERE, 'x_paired_tests.csv'), index=False)

    pd.set_option('display.width', 250)
    pd.set_option('display.max_rows', 500)
    show = X[X.window.isin(['FULL 2009-01..2026-09', 'ORIG 2015-02..2026-09', 'ORIG 2019-01..2026-09'])]
    print(show.pivot_table(index='variant', columns='window', values='CAGR', sort=False).map(lambda v: f'{v:.2%}').to_string())
    print(X[X.variant == 'SPEC Top-3 (10bp)'][['window', 'n_months', 'CAGR', 'vol', 'Sharpe', 'MaxDD_monthly', 'MaxDD_daily']].to_string())
    print(T[['window', 'B', 'CAGR_A', 'CAGR_B', 'NW_t_lag3', 'NW_p_lag3', 'boot_P(diff<=0)', 'alpha_ann', 'beta', 'alpha_NW_t']].to_string())
    print(con.head(12).to_string())


if __name__ == '__main__':
    main()
