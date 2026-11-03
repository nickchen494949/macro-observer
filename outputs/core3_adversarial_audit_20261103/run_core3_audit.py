#!/usr/bin/env python3
"""
Clean-Room Adversarial Falsification Audit of Core3:
  Frozen Rule: 50% QQQ Sharpe-Momentum (12-1 / 12m daily vol) Top-2 + 50% S&P 500 Tech Pure 12-1 Momentum Top-1 (S1)
  Window: 2009-01 .. 2026-09 (213 holding months, unlevered 1.0x, T+1 Open-to-Open, 10 bp/side cost)

Executes all 10 adversarial falsification tests ordered by the user without altering the frozen rule:
  1. Volatility window (3m, 6m, 9m, 12m [frozen], 18m; with/without 1m skip) & Momentum lookback grid
  2. Top-K (Top-1, Top-2 [frozen], Top-3, Top-5, Top-10) & Single-Rank (Rank #1..#5, Ranks 2-3, 3-4) decomposition
  3. Core sleeve weights (0/100, 25/75, 33/67, 50/50 [frozen], 67/33, 75/25, 100/0), Core4, deduplication,
     and Exact Unified Single-Account Drift-Rebalanced Accounting vs Sleeve-Average Accounting
  4. Transaction cost & slippage stress (0, 10 [frozen], 20, 30, 50, 75, 100 bp/side; linear & multiplicative)
  5. Execution timing & lag stress (T+0 close, T+1 open [frozen], T+1 close, T+2 open, T+2 close, T+3 open, T+5 open)
  6. Outlier month removal (drop best 1, 3, 5, 10 months) & Super-winner stock ban (simultaneous across both sleeves)
  7. Second-Vendor (Tiingo-First) end-to-end replication (signals + open-to-open returns) & 639-slot cross-check
  8. Exact Daily Mark-to-Market Equity Curve (4,466 trading days) & True Daily MaxDD vs Monthly MaxDD
  9. Subperiod stability, Calendar years, Paired Newey-West / Block Bootstrap tests, and Multiple-Testing DSR
 10. Strict Rule Freeze verification (plateau vs isolated peak analysis)
"""
import glob
import json
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats as sst

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
EXP_DIR = os.path.join(ROOT, 'outputs', 'alpha_core_regime_experiment_20261103')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)

import a2_engine as QE
import a3_signals as QS
import a4_backtest as QB
import c2_engine as TE
import c4_backtest as TB

WINDOWS = [
    ('FULL 2009-01..2026-09', '2009-01-31', '2026-09-30'),
    ('2009-2014', '2009-01-31', '2014-12-31'),
    ('2015-2019', '2015-01-31', '2019-12-31'),
    ('2020-2022', '2020-01-31', '2022-12-31'),
    ('2023-2026.09', '2023-01-31', '2026-09-30'),
    ('2009-2018 (pre-2019)', '2009-01-31', '2018-12-31'),
    ('2015-2026.09', '2015-01-31', '2026-09-30'),
    ('2019-2026.09', '2019-01-31', '2026-09-30'),
    ('IS 2009-2016', '2009-01-31', '2016-12-31'),
    ('OOS 2017-2026.09', '2017-01-31', '2026-09-30'),
]


# =============================================================================
# 0. Common Helpers & Metrics
# =============================================================================
def load_rf():
    fn = os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')
    d = json.load(open(fn))['values']
    s = pd.Series({pd.Timestamp(dt): float(v) for dt, v in d if v is not None and v != '.'}).sort_index()
    return s.resample('ME').last() / 1200.0


RF_M = load_rf()


def cagr(r):
    r = pd.Series(r).dropna()
    return float((np.prod(1.0 + r)) ** (12.0 / len(r)) - 1.0) if len(r) else np.nan


def maxdd(r):
    r = pd.Series(r).dropna()
    if not len(r):
        return np.nan
    w = np.cumprod(1.0 + r.values)
    w = np.concatenate([[1.0], w])
    return float((w / np.maximum.accumulate(w) - 1.0).min())


def sharpe(r, rf=RF_M):
    r = pd.Series(r).dropna()
    if not len(r) or r.std(ddof=1) == 0:
        return np.nan
    ex = r - rf.reindex(r.index).ffill().fillna(0.0)
    return float(ex.mean() / r.std(ddof=1) * np.sqrt(12.0))


def metrics_dict(r, rf=RF_M):
    r = pd.Series(r).dropna()
    if not len(r):
        return {}
    cg = cagr(r)
    vl = float(r.std(ddof=1) * np.sqrt(12.0))
    sh = sharpe(r, rf)
    dd = maxdd(r)
    cal = cg / abs(dd) if dd < 0 else np.nan
    return {
        'n': len(r),
        'CAGR': cg,
        'Vol': vl,
        'Sharpe': sh,
        'MaxDD_m': dd,
        'Calmar': cal,
        'Best_m': float(r.max()),
        'Worst_m': float(r.min()),
        'Win_pct': float((r > 0).mean()),
    }


def summary_across_windows(name, r_series, extra=None):
    m_full = metrics_dict(r_series.loc['2009-01-31':'2026-09-30'])
    row = {'Variant': name}
    if extra:
        row.update(extra)
    row.update({
        'CAGR_09_26': m_full['CAGR'],
        'Vol_09_26': m_full['Vol'],
        'Sharpe_09_26': m_full['Sharpe'],
        'MaxDD_m_09_26': m_full['MaxDD_m'],
        'Calmar_09_26': m_full['Calmar'],
        'Best_Month': m_full['Best_m'],
        'Worst_Month': m_full['Worst_m'],
        'Win_Pct': m_full['Win_pct'],
    })
    for wname, a, b in WINDOWS[1:]:
        mw = metrics_dict(r_series.loc[a:b])
        col = 'CAGR_' + wname.split(' ')[0].replace('-', '_').replace('.', '_')
        row[col] = mw.get('CAGR', np.nan)
    return row


def nw_t(x, lag):
    x = np.asarray(pd.Series(x).dropna(), float)
    n = len(x)
    e = x - x.mean()
    s = float(e @ e) / n
    for L in range(1, lag + 1):
        s += 2.0 * (1.0 - L / (lag + 1.0)) * float(e[L:] @ e[:-L]) / n
    se = np.sqrt(s / n)
    t_stat = float(x.mean() / se) if se > 0 else np.nan
    p_val = float(2.0 * (1.0 - sst.norm.cdf(abs(t_stat)))) if np.isfinite(t_stat) else np.nan
    return t_stat, p_val


def stationary_boot_diff(a, b, draws=5000, block=6, seed=42):
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    n = len(a)
    d = np.empty(draws)
    p = 1.0 / block
    for j in range(draws):
        idx = np.empty(n, int)
        i = rng.integers(n)
        for k in range(n):
            if k and rng.random() < p:
                i = rng.integers(n)
            idx[k] = i
            i = (i + 1) % n
        d[j] = (np.prod(1.0 + a[idx]) ** (12.0 / n) - 1.0) - (np.prod(1.0 + b[idx]) ** (12.0 / n) - 1.0)
    return np.percentile(d, [5, 50, 95]), float((d <= 0).mean())


# =============================================================================
# 1. Precompute Multi-Window Volatility Panel on QQQ & Tech Universe
# =============================================================================
def build_qqq_vol_panel(P12):
    """
    For every (t, ticker) in QQQ P12 panel, compute annualized daily return volatility over:
      - With 1m skip: W in {3m, 6m, 9m, 12m (frozen), 18m}
      - Without 1m skip: W in {6m, 12m}
    Matches run_experiments.py bit-for-bit on vol_12_1 (intersected with QQQ trading calendar).
    """
    cache_fn = os.path.join(HERE, 'cache_qqq_vol_grid.parquet')
    if os.path.exists(cache_fn) and '--rebuild' not in sys.argv:
        return pd.read_parquet(cache_fn)

    df_q = QE.series('tiingo_api', 'QQQ')
    if df_q is None:
        df_q = QE.series('yahoo', 'QQQ')
    rq_all = df_q['adjclose'].dropna().pct_change()

    # Window specs: (col_name, start_months_back, end_months_back, min_obs)
    w_specs = [
        ('vol_3_1', 4, 1, 35),    # 3 full months [t-4m, t-1m]
        ('vol_6_1', 6, 1, 60),    # [t-6m, t-1m]
        ('vol_9_1', 9, 1, 100),   # [t-9m, t-1m]
        ('vol_12_1', 12, 1, 120), # [t-12m, t-1m] FROZEN SPEC (exact match to run_experiments.py)
        ('vol_18_1', 18, 1, 120), # [t-18m, t-1m] (120 min so newly eligible 12m names are not dropped)
        ('vol_6_0', 6, 0, 70),    # [t-6m, t] no skip
        ('vol_12_0', 12, 0, 120), # [t-12m, t] no skip
    ]

    rows = []
    for t, g in P12.groupby('t'):
        rq_slices = {}
        for col, m_start, m_end, min_n in w_specs:
            ts = t - pd.offsets.MonthEnd(m_start)
            te = t - pd.offsets.MonthEnd(m_end) if m_end > 0 else t
            rq_slices[col] = (ts, te, min_n, rq_all.loc[ts:te].dropna().index)

        for _, r in g.iterrows():
            tk, st, sym, mom = r['ticker'], r['store'], r['sym'], r['mom']
            df = QE.series(st, sym)
            d = {'t': t, 'ticker': tk, 'store': st, 'sym': sym, 'mom_12_1': mom, 'raw_rank': r['rank']}
            for col, m_start, m_end, min_n in w_specs:
                ts, te, _, rq_idx = rq_slices[col]
                c = df['adjclose'].loc[ts:te].dropna()
                ri = c.pct_change().dropna()
                common = ri.index.intersection(rq_idx)
                if len(common) >= min_n:
                    d[col] = float(np.std(ri.loc[common].values, ddof=1) * np.sqrt(252.0))
                else:
                    d[col] = np.nan
            rows.append(d)

    V = pd.DataFrame(rows)
    V.to_parquet(cache_fn, index=False)
    return V


def run_qqq_panel(panel_df, score_col, H, k=2, cost_bp=10.0, ranks=None, exclude=None):
    sub = panel_df.dropna(subset=[score_col]).copy()
    sub['mom'] = sub[score_col]
    sub = sub.sort_values(['t', 'mom', 'ticker'], ascending=[True, False, True])
    sub['rank'] = sub.groupby('t').cumcount() + 1
    L = QB.run(sub, H, k=k, cost_bp=cost_bp, ranks=ranks, exclude=exclude)
    return L.set_index('month')


# =============================================================================
# 2. Tech Sleeve Flexible Engine (Supports Vol-Scaling, N-day Open/Close Lags, Bans)
# =============================================================================
def tech_hold_return_flex(ticker, t, mode='open', n_day=1):
    """
    Synchronized execution window for Tech sleeve:
      mode='close_t0': month-end t close -> month-end t+1m close
      mode='open'    : n_day-th session after t open -> n_day-th session after t+1m open (fallback to same-day close)
      mode='close_t1': n_day-th session after t close -> n_day-th session after t+1m close
    """
    t = pd.Timestamp(t)
    t1 = t + pd.offsets.MonthEnd(1)
    if mode == 'close_t0':
        d0, d1 = QE.last_td_on_or_before(t), QE.last_td_on_or_before(t1)
    else:
        d0, d1 = QE.first_td_after(t, n_day), QE.first_td_after(t1, n_day)

    segs = TE.segments(ticker)
    order = [x for x in segs if d0 in x[0].index and d1 in x[0].index] + \
            [x for x in segs if d0 in x[0].index and d1 not in x[0].index]
    for df, src, sym, note in order:
        flag = []
        if mode == 'open':
            p0 = df.at[d0, 'adj_open'] if 'adj_open' in df.columns else np.nan
            if not np.isfinite(p0):
                p0 = df.at[d0, 'adjclose']
                flag.append('entry_close_fallback')
        else:
            p0 = df.at[d0, 'adjclose']

        if d1 in df.index and np.isfinite(df.at[d1, 'adjclose']):
            if mode == 'open':
                p1 = df.at[d1, 'adj_open'] if 'adj_open' in df.columns else np.nan
                if not np.isfinite(p1):
                    p1 = df.at[d1, 'adjclose']
                    flag.append('exit_close_fallback')
            else:
                p1 = df.at[d1, 'adjclose']
            de = d1
        else:
            s = df['adjclose'].loc[d0:d1].dropna()
            p1, de = float(s.iloc[-1]), s.index[-1]
            flag.append(f'delisted_exit_last_close_{de.date()}')
        return float(p1 / p0 - 1.0), dict(d0=d0, d1=de, p0=float(p0), p1=float(p1), src=src, sym=sym, flag='|'.join(flag) or 'ok')
    return np.nan, dict(d0=d0, d1=d1, flag='no_price_at_entry')


def run_tech_flex(spec='main', rank=1, topn=1, cost_bp=10.0, mode='open', n_day=1,
                  exclude=(), use_sharpe=False, linear_cost=False):
    """Run S&P 500 Tech sleeve with full support for execution lags, stock bans, and Sharpe-mom."""
    rows, prev = [], {}
    c = cost_bp / 1e4
    for t in TE.formations():
        rt = TE.rank_table(t, spec, tuple(exclude))
        rt = rt[rt.mom.notna()].copy()
        if use_sharpe:
            t_s = t - pd.offsets.MonthEnd(1)
            t_l = t - pd.offsets.MonthEnd(12)
            vols = []
            for tk in rt.ticker:
                segs = TE.segments(tk)
                v = np.nan
                for df, _, _, _ in segs:
                    sub = df['adjclose'].loc[t_l:t_s].dropna().pct_change().dropna()
                    if len(sub) >= 120:
                        v = float(sub.std(ddof=1) * np.sqrt(252.0))
                        break
                vols.append(v)
            rt['vol_12_1'] = vols
            rt['score'] = rt['mom'] / rt['vol_12_1']
            rt = rt.dropna(subset=['score']).sort_values(['score', 'ticker'], ascending=[False, True]).reset_index(drop=True)
        else:
            rt = rt.reset_index(drop=True)

        picks = [rt.ticker.iloc[rank - 1]] if topn == 1 else list(rt.ticker.iloc[:topn])
        w = {p: 1.0 / len(picks) for p in picks}
        g, legs = 0.0, []
        for p in picks:
            r, info = tech_hold_return_flex(p, t, mode=mode, n_day=n_day)
            if not np.isfinite(r):
                raise RuntimeError(f'Tech flex {t.date()} {p}: no return ({info})')
            g += w[p] * r
            legs.append((p, r, info))

        sides = 1.0 if not prev else sum(abs(w.get(k, 0.0) - prev.get(k, 0.0)) for k in set(w) | set(prev))
        if linear_cost:
            net = g - sides * c
        else:
            net = (1.0 + g) * ((1.0 - c) ** sides) - 1.0 if sides else g

        tot = sum(w[p] * (1.0 + r) for p, r, _ in legs)
        prev = {p: w[p] * (1.0 + r) / tot for p, r, _ in legs}
        i0 = legs[0][2]
        rows.append(dict(
            month=t + pd.offsets.MonthEnd(1),
            formation=t,
            picks='|'.join(picks),
            rets='|'.join(f'{r:.6f}' for _, r, _ in legs),
            gross=g,
            turnover=sides,
            cost=sides * c,
            net=net,
            d0=str(i0['d0'].date()),
            d1=str(pd.Timestamp(i0['d1']).date()),
            p0=i0.get('p0'),
            p1=i0.get('p1'),
            src=i0.get('src'),
            sym=i0.get('sym'),
            flag='|'.join(l[2]['flag'] for l in legs),
        ))
    return pd.DataFrame(rows).set_index('month')


# =============================================================================
# 3. Unified Single-Account Portfolio Accounting Engine
# =============================================================================
def run_unified_portfolio(L_qqq, L_tech, w_qqq=0.50, w_tech=0.50, cost_bp=10.0, mult_cost=False):
    """
    Simulate Core3 as a single unified account:
      - At each month m, target weights are w_qqq split equally across L_qqq picks + w_tech split across L_tech picks.
      - If a stock appears in both sleeves, its target weight is summed (e.g. 0.25 + 0.50 = 0.75) and trades are netted!
      - At month-end, each stock's weight drifts by (1 + r_s) / (1 + G_m).
      - Next month's turnover is sum_s |w_target(m, s) - w_drifted(m-1, s)|, which captures both stock switches
        AND the monthly rebalancing between the QQQ sleeve and the Tech sleeve!
    """
    c = cost_bp / 1e4
    prev_w = {}
    rows = []
    for m in L_qqq.index:
        q_picks = L_qqq.loc[m, 'picks'].split('|')
        q_rets = [float(x) for x in str(L_qqq.loc[m, 'rets']).split('|')]
        t_picks = L_tech.loc[m, 'picks'].split('|')
        if 'rets' in L_tech.columns:
            t_rets = [float(x) for x in str(L_tech.loc[m, 'rets']).split('|')]
        else:
            t_rets = [float(L_tech.loc[m, 'gross'])]

        w_target = {}
        stock_ret = {}
        for p, r in zip(q_picks, q_rets):
            w_target[p] = w_target.get(p, 0.0) + w_qqq / len(q_picks)
            stock_ret[p] = r
        for p, r in zip(t_picks, t_rets):
            w_target[p] = w_target.get(p, 0.0) + w_tech / len(t_picks)
            # If stock is in both sleeves, use average or QQQ/Tech exact return (identical for Yahoo open-to-open)
            if p not in stock_ret:
                stock_ret[p] = r

        gross = sum(w_target[s] * stock_ret[s] for s in w_target)
        if not prev_w:
            # Initial entry: 100% one-way buy (same convention as Tech S1) or 1.0 turnover
            to = sum(abs(w_target.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(w_target) | set(prev_w))
        else:
            to = sum(abs(w_target.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(w_target) | set(prev_w))

        if mult_cost:
            net = (1.0 + gross) * ((1.0 - c) ** to) - 1.0
        else:
            net = gross - to * c

        prev_w = {s: w_target[s] * (1.0 + stock_ret[s]) / (1.0 + gross) for s in w_target}
        rows.append({
            'month': m,
            'gross': gross,
            'turnover': to,
            'cost': to * c,
            'net': net,
            'weights': '|'.join(f'{s}:{w_target[s]:.3f}' for s in sorted(w_target)),
        })
    return pd.DataFrame(rows).set_index('month')


# =============================================================================
# 4. Main Audit Pipeline (All 10 Checks)
# =============================================================================
def main():
    os.makedirs(HERE, exist_ok=True)
    print('=== STARTING CLEAN-ROOM ADVERSARIAL AUDIT OF CORE3 ===')

    # Load QQQ panels & holding returns
    P12 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel.parquet'))
    P11 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_lb11_sk1.parquet'))
    P9 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_lb9_sk1.parquet'))
    P6 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_lb6_sk1.parquet'))
    P12_0 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_lb12_sk0.parquet'))
    H_all = pd.read_parquet(os.path.join(QQQ_DIR, 'r_hold_returns_open_d1_all.parquet'))

    # Build multi-window volatility panel on QQQ
    V_qqq = build_qqq_vol_panel(P12)
    # Merge momentum lookbacks (6-1, 9-1, 11-1, 12-0) into V_qqq
    for lb_name, P_sub in [('mom_11_1', P11), ('mom_9_1', P9), ('mom_6_1', P6), ('mom_12_0', P12_0)]:
        V_qqq = V_qqq.merge(P_sub[['t', 'ticker', 'mom']].rename(columns={'mom': lb_name}), on=['t', 'ticker'], how='left')
    V_qqq['mom_ens'] = (V_qqq['mom_12_1'] + V_qqq['mom_9_1'] + V_qqq['mom_6_1']) / 3.0

    # Frozen QQQ Sharpe-Momentum score: mom_12_1 / vol_12_1
    V_qqq['sharpe_mom_12_12'] = V_qqq['mom_12_1'] / V_qqq['vol_12_1']

    # Run Frozen Sleeves
    L_qqq_sh_top2 = run_qqq_panel(V_qqq, 'sharpe_mom_12_12', H_all, k=2, cost_bp=10.0)
    L_qqq_raw_top2 = run_qqq_panel(V_qqq, 'mom_12_1', H_all, k=2, cost_bp=10.0)
    L_qqq_raw_top3 = run_qqq_panel(V_qqq, 'mom_12_1', H_all, k=3, cost_bp=10.0)

    L_tech_s1 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'S1_main_top1.csv'), parse_dates=['month', 'formation']).set_index('month')
    L_tech_s1['rets'] = L_tech_s1['gross'].map(lambda v: f'{v:.6f}')
    L_tech_s0 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'S0_wiki_asis_top1.csv'), parse_dates=['month', 'formation']).set_index('month')

    months = L_qqq_sh_top2.index
    x_led = pd.read_csv(os.path.join(QQQ_DIR, 'x_monthly_ledgers.csv'), parse_dates=['month']).set_index('month')
    r_qqq_etf = x_led.loc[months, 'BENCH QQQ ETF']
    r_ndx_ew = x_led.loc[months, 'BENCH NDX equal-weight (PIT, 10bp)']
    L_xlk = TB.bench('XLK').loc[months]
    r_xlk_etf = L_xlk['net']
    L_spy = TB.bench('SPY').loc[months]
    r_spy_etf = L_spy['net']

    # Frozen Core3 (50/50 Sleeve-Average) & Unified Single-Account Core3
    r_core3 = 0.50 * L_qqq_sh_top2.loc[months, 'net'] + 0.50 * L_tech_s1.loc[months, 'net']
    U_core3_lin = run_unified_portfolio(L_qqq_sh_top2, L_tech_s1, 0.50, 0.50, cost_bp=10.0, mult_cost=False)
    U_core3_mult = run_unified_portfolio(L_qqq_sh_top2, L_tech_s1, 0.50, 0.50, cost_bp=10.0, mult_cost=True)
    r_core1 = 0.50 * L_qqq_raw_top2.loc[months, 'net'] + 0.50 * L_tech_s1.loc[months, 'net']
    r_core4 = (1.0 / 3.0) * L_qqq_raw_top2.loc[months, 'net'] + (1.0 / 3.0) * L_qqq_sh_top2.loc[months, 'net'] + (1.0 / 3.0) * L_tech_s1.loc[months, 'net']

    # Save 00_core3_frozen_ledger.csv
    led_rows = []
    for m in months:
        qp = L_qqq_sh_top2.loc[m, 'picks'].split('|')
        qr = [float(x) for x in L_qqq_sh_top2.loc[m, 'rets'].split('|')]
        tp = str(L_tech_s1.loc[m, 'picks']).strip()
        led_rows.append({
            'month': m.strftime('%Y-%m-%d'),
            'formation_t': pd.Timestamp(L_qqq_sh_top2.loc[m, 't']).strftime('%Y-%m-%d'),
            'qqq_pick1': qp[0],
            'qqq_pick2': qp[1],
            'qqq_ret1': qr[0],
            'qqq_ret2': qr[1],
            'qqq_turnover': float(L_qqq_sh_top2.loc[m, 'turnover']),
            'qqq_gross': float(L_qqq_sh_top2.loc[m, 'gross']),
            'qqq_net': float(L_qqq_sh_top2.loc[m, 'net']),
            'tech_pick1': tp,
            'tech_turnover': float(L_tech_s1.loc[m, 'sides']),
            'tech_gross': float(L_tech_s1.loc[m, 'gross']),
            'tech_net': float(L_tech_s1.loc[m, 'net']),
            'overlap_in_qqq_top2': int(tp in qp),
            'overlap_is_qqq_rank1': int(tp == qp[0]),
            'core3_gross': 0.50 * float(L_qqq_sh_top2.loc[m, 'gross']) + 0.50 * float(L_tech_s1.loc[m, 'gross']),
            'core3_net_sleeve5050': float(r_core3.loc[m]),
            'core3_net_unified_linear': float(U_core3_lin.loc[m, 'net']),
            'core3_net_unified_mult': float(U_core3_mult.loc[m, 'net']),
            'core4_net': float(r_core4.loc[m]),
            'core1_net': float(r_core1.loc[m]),
            'qqq_etf_net': float(r_qqq_etf.loc[m]),
            'xlk_etf_net': float(r_xlk_etf.loc[m]),
        })
    df_led0 = pd.DataFrame(led_rows)
    df_led0.to_csv(os.path.join(HERE, '00_core3_frozen_ledger.csv'), index=False)
    print(f'[Check 0] Saved 00_core3_frozen_ledger.csv ({len(df_led0)} months). '
          f'Core3 CAGR={cagr(r_core3):.2%}, Unified Linear={cagr(U_core3_lin["net"]):.2%}, Unified Mult={cagr(U_core3_mult["net"]):.2%}')

    all_audit_series = {
        'Core3 (Frozen 50/50 Sleeve-Avg)': r_core3,
        'Core3 (Unified Account Linear 10bp)': U_core3_lin['net'],
        'Core3 (Unified Account Mult 10bp)': U_core3_mult['net'],
        'Core4 (1/3 Raw + 1/3 Sharpe + 1/3 Tech)': r_core4,
        'Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1)': r_core1,
        'Sleeve1: QQQ Sharpe-Mom Top-2': L_qqq_sh_top2['net'],
        'Sleeve2: Tech Pure 12-1 Top-1 (S1)': L_tech_s1['net'],
    }

    # =========================================================================
    # CHECK 1: Volatility Window & Momentum Lookback Grid
    # =========================================================================
    print('[Check 1] Running Volatility & Momentum Lookback Grid...')
    grid1_rows = []
    # 1a. Varying Volatility Window (3m, 6m, 9m, 12m [frozen], 18m; skip=1 and skip=0) with frozen 12-1 mom numerator
    vol_specs = [
        ('vol_3_1 (3m daily vol, 1m skip)', 'mom_12_1', 'vol_3_1'),
        ('vol_6_1 (6m daily vol, 1m skip)', 'mom_12_1', 'vol_6_1'),
        ('vol_9_1 (9m daily vol, 1m skip)', 'mom_12_1', 'vol_9_1'),
        ('vol_12_1 (12m daily vol, 1m skip) [FROZEN]', 'mom_12_1', 'vol_12_1'),
        ('vol_18_1 (18m daily vol, 1m skip)', 'mom_12_1', 'vol_18_1'),
        ('vol_6_0 (6m daily vol, NO skip)', 'mom_12_1', 'vol_6_0'),
        ('vol_12_0 (12m daily vol, NO skip)', 'mom_12_1', 'vol_12_0'),
        ('No Vol Scaling (Raw 12-1 Momentum = Core1)', 'mom_12_1', None),
        # 1b. Varying Momentum Lookback in numerator with frozen 12m vol denominator
        ('Mom 6-1 / Vol 12m', 'mom_6_1', 'vol_12_1'),
        ('Mom 9-1 / Vol 12m', 'mom_9_1', 'vol_12_1'),
        ('Mom 11-1 / Vol 12m', 'mom_11_1', 'vol_12_1'),
        ('Mom 12-0 (no skip) / Vol 12m', 'mom_12_0', 'vol_12_1'),
        ('Mom Ensemble(6-1,9-1,12-1) / Vol 12m', 'mom_ens', 'vol_12_1'),
        # 1c. Matched Mom & Vol windows
        ('Matched 6-1 Mom / 6m Vol', 'mom_6_1', 'vol_6_1'),
        ('Matched 9-1 Mom / 9m Vol', 'mom_9_1', 'vol_9_1'),
    ]
    for label, mcol, vcol in vol_specs:
        cname = f'score_{label}'
        if vcol is None:
            V_qqq[cname] = V_qqq[mcol]
        else:
            V_qqq[cname] = V_qqq[mcol] / V_qqq[vcol]
        Lq = run_qqq_panel(V_qqq, cname, H_all, k=2, cost_bp=10.0)
        rc = 0.50 * Lq.loc[months, 'net'] + 0.50 * L_tech_s1.loc[months, 'net']
        all_audit_series[f'G1_Core_{label}'] = rc
        grid1_rows.append(summary_across_windows(f'Core (50/50): {label}', rc, {'Scope': '50/50 Core'}))
        grid1_rows.append(summary_across_windows(f'QQQ Sleeve Only: {label}', Lq.loc[months, 'net'], {'Scope': 'QQQ Sleeve Standalone'}))

    # Also test applying Sharpe-Momentum (mom_12_1 / vol_12_1) to the Tech sleeve as well
    L_tech_sh_top1 = run_tech_flex(spec='main', rank=1, topn=1, cost_bp=10.0, mode='open', use_sharpe=True)
    rc_both_sh = 0.50 * L_qqq_sh_top2.loc[months, 'net'] + 0.50 * L_tech_sh_top1.loc[months, 'net']
    all_audit_series['G1_Core_Both_Sharpe'] = rc_both_sh
    grid1_rows.append(summary_across_windows('Core (50/50): Both Sleeves Sharpe-Mom (QQQ Sh-Top2 + Tech Sh-Top1)', rc_both_sh, {'Scope': '50/50 Core'}))
    grid1_rows.append(summary_across_windows('Tech Sleeve Only: Tech Sharpe-Mom Top-1', L_tech_sh_top1.loc[months, 'net'], {'Scope': 'Tech Sleeve Standalone'}))

    df_g1 = pd.DataFrame(grid1_rows)
    df_g1.to_csv(os.path.join(HERE, '01_vol_and_mom_grid.csv'), index=False)

    # =========================================================================
    # CHECK 2: Top-K & Neighboring Rank Decomposition
    # =========================================================================
    print('[Check 2] Running Top-K & Single-Rank Decomposition...')
    grid2_rows = []
    qqq_rank_specs = [
        ('QQQ Sharpe-Mom Top-1', 1, None),
        ('QQQ Sharpe-Mom Top-2 [FROZEN]', 2, None),
        ('QQQ Sharpe-Mom Top-3', 3, None),
        ('QQQ Sharpe-Mom Top-5', 5, None),
        ('QQQ Sharpe-Mom Top-10', 10, None),
        ('QQQ Sharpe-Mom Rank #1 alone', 1, [1]),
        ('QQQ Sharpe-Mom Rank #2 alone', 1, [2]),
        ('QQQ Sharpe-Mom Rank #3 alone', 1, [3]),
        ('QQQ Sharpe-Mom Rank #4 alone', 1, [4]),
        ('QQQ Sharpe-Mom Rank #5 alone', 1, [5]),
        ('QQQ Sharpe-Mom Ranks 2-3 (neighbour pair)', 2, [2, 3]),
        ('QQQ Sharpe-Mom Ranks 3-4 (neighbour pair)', 2, [3, 4]),
        ('QQQ Sharpe-Mom Ranks 4-6', 3, [4, 5, 6]),
    ]
    for label, k_val, r_list in qqq_rank_specs:
        Lq = run_qqq_panel(V_qqq, 'sharpe_mom_12_12', H_all, k=k_val, cost_bp=10.0, ranks=r_list)
        rc = 0.50 * Lq.loc[months, 'net'] + 0.50 * L_tech_s1.loc[months, 'net']
        all_audit_series[f'G2_Core_{label}'] = rc
        grid2_rows.append(summary_across_windows(f'50% ({label}) + 50% Tech Top-1', rc, {'Group': 'Paired with Tech Top-1'}))
        grid2_rows.append(summary_across_windows(f'Standalone: {label}', Lq.loc[months, 'net'], {'Group': 'QQQ Sharpe-Mom Standalone'}))

    # Vary Tech Sleeve Top-K & Ranks while keeping QQQ Sharpe-Mom Top-2 frozen
    L_tech_top2 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'top2_ew.csv'), parse_dates=['month']).set_index('month')
    L_tech_top3 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'top3_ew.csv'), parse_dates=['month']).set_index('month')
    L_tech_top5 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'top5_ew.csv'), parse_dates=['month']).set_index('month')
    L_tech_r2 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'rank2.csv'), parse_dates=['month']).set_index('month')
    L_tech_r3 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'rank3.csv'), parse_dates=['month']).set_index('month')

    for tlabel, Lt in [
        ('Tech Top-1 (S1, no NFLX) [FROZEN]', L_tech_s1),
        ('Tech Top-2 EW (S1)', L_tech_top2),
        ('Tech Top-3 EW (S1)', L_tech_top3),
        ('Tech Top-5 EW (S1)', L_tech_top5),
        ('Tech Rank #2 alone (S1)', L_tech_r2),
        ('Tech Rank #3 alone (S1)', L_tech_r3),
        ('Tech Top-1 (S0 w/ NFLX)', L_tech_s0),
    ]:
        rc = 0.50 * L_qqq_sh_top2.loc[months, 'net'] + 0.50 * Lt.loc[months, 'net']
        all_audit_series[f'G2_TechVar_{tlabel}'] = rc
        grid2_rows.append(summary_across_windows(f'50% QQQ Sharpe-Mom Top-2 + 50% ({tlabel})', rc, {'Group': 'Varying Tech Sleeve'}))

    df_g2 = pd.DataFrame(grid2_rows)
    df_g2.to_csv(os.path.join(HERE, '02_rank_and_topk_grid.csv'), index=False)

    # =========================================================================
    # CHECK 3: Sleeve Weights, Deduplication & Portfolio Accounting
    # =========================================================================
    print('[Check 3] Running Sleeve Weights & Portfolio Accounting Grid...')
    grid3_rows = []
    for wq, wt in [(1.0, 0.0), (0.75, 0.25), (2/3, 1/3), (0.50, 0.50), (1/3, 2/3), (0.25, 0.75), (0.0, 1.0)]:
        tag = f'{int(round(wq*100))}/{int(round(wt*100))}'
        is_froz = ' [FROZEN]' if tag == '50/50' else ''
        r_sa = wq * L_qqq_sh_top2.loc[months, 'net'] + wt * L_tech_s1.loc[months, 'net']
        U_mult = run_unified_portfolio(L_qqq_sh_top2, L_tech_s1, wq, wt, cost_bp=10.0, mult_cost=True)
        all_audit_series[f'G3_Weight_{tag}_SA'] = r_sa
        grid3_rows.append(summary_across_windows(f'Weight {tag} (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg{is_froz}', r_sa, {'Category': 'Weight Grid (Sleeve-Avg)'}))
        grid3_rows.append(summary_across_windows(f'Weight {tag} (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult{is_froz}', U_mult['net'], {'Category': 'Weight Grid (Unified Account)'}))

    # Unrebalanced drift between sleeves (start 50/50 in 2009-01, never rebalance between Sleeve 1 and Sleeve 2)
    w1 = (1.0 + L_qqq_sh_top2.loc[months, 'net']).cumprod()
    w2 = (1.0 + L_tech_s1.loc[months, 'net']).cumprod()
    w_unreb = 0.50 * w1 + 0.50 * w2
    w_unreb_prev = pd.Series([1.0] + list(w_unreb.iloc[:-1].values), index=months)
    r_unreb = w_unreb / w_unreb_prev - 1.0

    # Deduplicated variants when Tech Top-1 is already inside QQQ Sharpe-Mom Top-2:
    # Replace the duplicate in QQQ Sharpe-Mom Top-2 with QQQ Sharpe-Mom Rank #3!
    Hm_qqq = H_all.set_index(['t', 'ticker'])
    V_ranked = V_qqq.dropna(subset=['sharpe_mom_12_12']).sort_values(['t', 'sharpe_mom_12_12', 'ticker'], ascending=[True, False, True]).copy()
    V_ranked['sh_rank'] = V_ranked.groupby('t').cumcount() + 1

    dedup50_rets, dedup33_rets = [], []
    prev_w50, prev_w33 = {}, {}
    for m in months:
        t = m - pd.offsets.MonthEnd(1)
        g = V_ranked[V_ranked['t'] == t]
        q_ok = [s for s in g.ticker if (t, s) in Hm_qqq.index and np.isfinite(Hm_qqq.at[(t, s), 'ret'])]
        q_top3 = q_ok[:3]
        t_pick = str(L_tech_s1.loc[m, 'picks']).strip()
        t_ret = float(L_tech_s1.loc[m, 'gross'])
        s_rets = {s: float(Hm_qqq.at[(t, s), 'ret']) for s in q_top3}
        s_rets[t_pick] = s_rets.get(t_pick, t_ret)

        if t_pick in q_top3[:2]:
            other_q = [s for s in q_top3[:2] if s != t_pick][0]
            w50 = {t_pick: 0.50, other_q: 0.25, q_top3[2]: 0.25}
            w33 = {t_pick: 1.0/3.0, other_q: 1.0/3.0, q_top3[2]: 1.0/3.0}
        else:
            w50 = {t_pick: 0.50, q_top3[0]: 0.25, q_top3[1]: 0.25}
            w33 = {t_pick: 1.0/3.0, q_top3[0]: 1.0/3.0, q_top3[1]: 1.0/3.0}

        for w, pw, lst in [(w50, prev_w50, dedup50_rets), (w33, prev_w33, dedup33_rets)]:
            gross = sum(w[s] * s_rets[s] for s in w)
            to = sum(abs(w.get(s, 0.0) - pw.get(s, 0.0)) for s in set(w) | set(pw))
            net = (1.0 + gross) * ((1.0 - 0.001) ** to) - 1.0
            lst.append((m, net))
            pw.clear()
            for s in w:
                pw[s] = w[s] * (1.0 + s_rets[s]) / (1.0 + gross)

    r_sh_dedup50 = pd.Series(dict(dedup50_rets))
    r_sh_dedup33 = pd.Series(dict(dedup33_rets))

    grid3_rows.extend([
        summary_across_windows('Core3 Accounting: Unified Account Linear 10bp/side', U_core3_lin['net'], {'Category': 'Accounting Comparison'}),
        summary_across_windows('Core3 Accounting: Unified Account Multiplicative 10bp/side', U_core3_mult['net'], {'Category': 'Accounting Comparison'}),
        summary_across_windows('Core3 Accounting: Unrebalanced Drift Between Sleeves', r_unreb, {'Category': 'Accounting Comparison'}),
        summary_across_windows('Core3 Deduplicated: Max 50% Cap (pull in QQQ Sh-Mom #3 on overlap)', r_sh_dedup50, {'Category': 'Deduplication & Multi-Sleeve'}),
        summary_across_windows('Core3 Deduplicated: Equal-Weight 3 Distinct Stocks (1/3 each)', r_sh_dedup33, {'Category': 'Deduplication & Multi-Sleeve'}),
        summary_across_windows('Core4: 1/3 QQQ Raw Top-2 + 1/3 QQQ Sharpe Top-2 + 1/3 Tech Top-1', r_core4, {'Category': 'Deduplication & Multi-Sleeve'}),
        summary_across_windows('Core1: 50% QQQ Raw Top-2 + 50% Tech Top-1', r_core1, {'Category': 'Deduplication & Multi-Sleeve'}),
    ])
    df_g3 = pd.DataFrame(grid3_rows)
    df_g3.to_csv(os.path.join(HERE, '03_weights_and_accounting.csv'), index=False)

    # =========================================================================
    # CHECK 4: Transaction Cost & Slippage Stress (0, 10, 20, 30, 50, 75, 100 bp)
    # =========================================================================
    print('[Check 4] Running Transaction Cost & Slippage Stress...')
    grid4_rows = []
    for c_bp in (0.0, 10.0, 20.0, 30.0, 50.0, 75.0, 100.0):
        Lq_c = run_qqq_panel(V_qqq, 'sharpe_mom_12_12', H_all, k=2, cost_bp=c_bp)
        Lt_c = run_tech_flex(spec='main', rank=1, topn=1, cost_bp=c_bp, mode='open')
        r_sa_c = 0.50 * Lq_c.loc[months, 'net'] + 0.50 * Lt_c.loc[months, 'net']
        U_lin_c = run_unified_portfolio(L_qqq_sh_top2, L_tech_s1, 0.50, 0.50, cost_bp=c_bp, mult_cost=False)
        U_mult_c = run_unified_portfolio(L_qqq_sh_top2, L_tech_s1, 0.50, 0.50, cost_bp=c_bp, mult_cost=True)
        froz_tag = ' [FROZEN]' if c_bp == 10.0 else ''
        grid4_rows.append(summary_across_windows(f'Cost {int(c_bp)} bp/side — Sleeve-Average{froz_tag}', r_sa_c, {'Cost_bp': c_bp, 'Accounting': 'Sleeve-Average'}))
        grid4_rows.append(summary_across_windows(f'Cost {int(c_bp)} bp/side — Unified Multiplicative{froz_tag}', U_mult_c['net'], {'Cost_bp': c_bp, 'Accounting': 'Unified Multiplicative'}))
        grid4_rows.append(summary_across_windows(f'Cost {int(c_bp)} bp/side — Unified Linear{froz_tag}', U_lin_c['net'], {'Cost_bp': c_bp, 'Accounting': 'Unified Linear'}))
    df_g4 = pd.DataFrame(grid4_rows)
    df_g4.to_csv(os.path.join(HERE, '04_cost_stress.csv'), index=False)

    # =========================================================================
    # CHECK 5: Execution Timing & Delay Stress (T+0 Close .. T+5 Open)
    # =========================================================================
    print('[Check 5] Running Synchronized Execution Timing & Delay Stress...')
    grid5_rows = []
    exec_specs = [
        ('T+0 Month-End Close (no lag, optimistic)', 'close_t0', 1),
        ('T+1 Open (1st trading day open) [FROZEN]', 'open', 1),
        ('T+1 Close (1st trading day close)', 'close_t1', 1),
        ('T+2 Open (2nd trading day open)', 'open', 2),
        ('T+2 Close (2nd trading day close)', 'close_t1', 2),
        ('T+3 Open (3rd trading day open)', 'open', 3),
        ('T+5 Open (5th trading day open)', 'open', 5),
    ]
    # Pre-rank V_qqq by sharpe_mom_12_12 and take top 10 per month so QB.hold_table is instantaneous
    V_sh_top10 = V_ranked[V_ranked['sh_rank'] <= 10].copy()
    V_sh_top10['mom'] = V_sh_top10['sharpe_mom_12_12']
    V_sh_top10['rank'] = V_sh_top10['sh_rank']

    for elabel, emode, enday in exec_specs:
        if emode == 'open' and enday == 1:
            Hq_e = H_all
        else:
            # Compute holding returns for top-10 Sharpe-Mom candidates at (emode, enday)
            h_rows = []
            for t_val, tk_val in zip(V_sh_top10.t, V_sh_top10.ticker):
                r_v, st_v, sym_v, fl_v, ed_v, xd_v = QE.hold_return(tk_val, t_val, mode=emode, n_day=enday)
                h_rows.append((t_val, tk_val, r_v, st_v, sym_v, fl_v, ed_v, xd_v))
            Hq_e = pd.DataFrame(h_rows, columns=['t', 'ticker', 'ret', 'ret_store', 'ret_sym', 'flag', 'entry', 'exit'])

        Lq_e = QB.run(V_sh_top10, Hq_e, k=2, cost_bp=10.0).set_index('month')
        Lt_e = run_tech_flex(spec='main', rank=1, topn=1, cost_bp=10.0, mode=emode, n_day=enday)
        rc_e = 0.50 * Lq_e.loc[months, 'net'] + 0.50 * Lt_e.loc[months, 'net']
        all_audit_series[f'G5_Exec_{elabel}'] = rc_e
        grid5_rows.append(summary_across_windows(f'Core3: {elabel}', rc_e, {'Target': 'Core3 (50/50)'}))
        grid5_rows.append(summary_across_windows(f'QQQ Sharpe-Mom Top-2: {elabel}', Lq_e.loc[months, 'net'], {'Target': 'Sleeve 1 (QQQ Sh-Top2)'}))
        grid5_rows.append(summary_across_windows(f'Tech Top-1 (S1): {elabel}', Lt_e.loc[months, 'net'], {'Target': 'Sleeve 2 (Tech Top-1)'}))

    df_g5 = pd.DataFrame(grid5_rows)
    df_g5.to_csv(os.path.join(HERE, '05_execution_timing.csv'), index=False)

    # =========================================================================
    # CHECK 6: Outlier Month Removal & Super-Winner Stock Bans
    # =========================================================================
    print('[Check 6] Running Outlier Month Removal & Stock Contribution / Ban Analysis...')
    # 6a. Exact stock-by-stock log-wealth contribution across Core3
    contrib_rows = []
    tot_log_w = float(np.log1p(r_core3).sum())
    for m in months:
        qp = L_qqq_sh_top2.loc[m, 'picks'].split('|')
        qr = [float(x) for x in L_qqq_sh_top2.loc[m, 'rets'].split('|')]
        tp = str(L_tech_s1.loc[m, 'picks']).strip()
        tr = float(L_tech_s1.loc[m, 'gross'])
        g_m = float(df_led0.loc[df_led0['month'] == m.strftime('%Y-%m-%d'), 'core3_gross'].iloc[0])
        n_m = float(r_core3.loc[m])
        scale = np.log1p(n_m) / g_m if abs(g_m) > 1e-9 else 1.0
        for p, r in zip(qp, qr):
            contrib_rows.append({'month': m, 'ticker': p, 'sleeve': 'QQQ_Sharpe_Top2', 'weight': 0.25, 'ret': r, 'log_w': 0.25 * r * scale})
        contrib_rows.append({'month': m, 'ticker': tp, 'sleeve': 'Tech_Top1', 'weight': 0.50, 'ret': tr, 'log_w': 0.50 * tr * scale})

    df_c = pd.DataFrame(contrib_rows)
    # Aggregate by (month, ticker) first so overlapping months count as 1 held month for that ticker
    df_cm = df_c.groupby(['month', 'ticker']).agg(
        weight=('weight', 'sum'),
        ret=('ret', 'mean'),
        log_w=('log_w', 'sum'),
        sleeves=('sleeve', lambda s: '+'.join(sorted(set(s))))
    ).reset_index()
    stock_agg = df_cm.groupby('ticker').agg(
        months_held=('month', 'size'),
        months_overlap_75pct=('weight', lambda w: int((w > 0.60).sum())),
        mean_weight=('weight', 'mean'),
        log_wealth_sum=('log_w', 'sum'),
        best_month_ret=('ret', 'max'),
        worst_month_ret=('ret', 'min'),
    ).sort_values('log_wealth_sum', ascending=False).reset_index()
    stock_agg['share_of_total_log_wealth'] = stock_agg['log_wealth_sum'] / tot_log_w
    stock_agg.to_csv(os.path.join(HERE, '06b_stock_contributions.csv'), index=False)

    top_contributors = list(stock_agg['ticker'].iloc[:10])
    print('Top 10 stock contributors to Core3 log-wealth:', top_contributors[:6])

    grid6_rows = [summary_across_windows('Baseline Core3 (No months dropped, no stocks banned) [FROZEN]', r_core3, {'Test_Type': 'Baseline'})]
    # Drop best K months of Core3
    for k_drop in (1, 3, 5, 10):
        r_d = r_core3.copy()
        best_idx = r_d.nlargest(k_drop).index
        dropped_str = ', '.join(dt.strftime('%Y-%m') for dt in best_idx)
        r_d.loc[best_idx] = 0.0
        grid6_rows.append(summary_across_windows(f'Drop best {k_drop} months of Core3 -> 0% ({dropped_str[:35]})', r_d, {'Test_Type': 'Drop Best Months'}))

    # Simultaneously ban top contributors from BOTH QQQ Sharpe-Mom Top-2 AND Tech Top-1 (S1)
    ban_sets = [
        ('Ban NVDA (both sleeves)', {'NVDA'}),
        ('Ban SNDK (both sleeves)', {'SNDK'}),
        ('Ban PLTR (both sleeves)', {'PLTR'}),
        ('Ban MU (both sleeves)', {'MU'}),
        ('Ban MRNA (both sleeves)', {'MRNA'}),
        ('Ban TSLA (both sleeves)', {'TSLA'}),
        ('Ban AAPL (both sleeves)', {'AAPL'}),
        ('Ban AVGO (both sleeves)', {'AVGO'}),
        ('Ban AMD (both sleeves)', {'AMD'}),
        ('Ban Netflix NFLX (both sleeves)', {'NFLX'}),
        (f'Ban Top-1 Contributor ({top_contributors[0]})', set(top_contributors[:1])),
        (f'Ban Top-2 Contributors ({",".join(top_contributors[:2])})', set(top_contributors[:2])),
        (f'Ban Top-3 Contributors ({",".join(top_contributors[:3])})', set(top_contributors[:3])),
        (f'Ban Top-5 Contributors ({",".join(top_contributors[:5])})', set(top_contributors[:5])),
    ]
    for blabel, bset in ban_sets:
        Lq_b = run_qqq_panel(V_qqq, 'sharpe_mom_12_12', H_all, k=2, cost_bp=10.0, exclude=bset)
        Lt_b = run_tech_flex(spec='main', rank=1, topn=1, cost_bp=10.0, mode='open', exclude=tuple(bset))
        rc_b = 0.50 * Lq_b.loc[months, 'net'] + 0.50 * Lt_b.loc[months, 'net']
        all_audit_series[f'G6_{blabel}'] = rc_b
        grid6_rows.append(summary_across_windows(blabel, rc_b, {'Test_Type': 'Simultaneous Stock Ban'}))

    df_g6 = pd.DataFrame(grid6_rows)
    df_g6.to_csv(os.path.join(HERE, '06_outlier_and_winner_removal.csv'), index=False)

    # =========================================================================
    # CHECK 7: Second-Vendor (Tiingo-First) End-to-End Replication & Cross-Check
    # =========================================================================
    print('[Check 7] Running Second-Vendor (Tiingo-First) Replication & 639-Slot Cross-Check...')
    # 7a. QQQ Sharpe-Mom Top-2 under Tiingo-First
    P12_tfirst = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_vendor_tiingo_first.parquet'))
    # Compute vol_12_1 on P12_tfirst using each row's (store, sym)
    v_tf_rows = []
    for t_val, g in P12_tfirst.groupby('t'):
        t_s1 = t_val - pd.offsets.MonthEnd(1)
        t_l12 = t_val - pd.offsets.MonthEnd(12)
        for _, r in g.iterrows():
            df_s = QE.series(r['store'], r['sym'])
            sub = df_s['adjclose'].loc[t_l12:t_s1].dropna().pct_change().dropna()
            vol_v = float(sub.std(ddof=1) * np.sqrt(252.0)) if len(sub) >= 120 else np.nan
            v_tf_rows.append({
                't': t_val,
                'ticker': r['ticker'],
                'store': r['store'],
                'sym': r['sym'],
                'mom_12_1': r['mom'],
                'vol_12_1': vol_v,
                'sharpe_mom': r['mom'] / vol_v if (np.isfinite(vol_v) and vol_v > 0) else np.nan,
            })
    V_qqq_tf = pd.DataFrame(v_tf_rows)
    V_qqq_tf_top10 = V_qqq_tf.dropna(subset=['sharpe_mom']).sort_values(['t', 'sharpe_mom', 'ticker'], ascending=[True, False, True]).copy()
    V_qqq_tf_top10['rank'] = V_qqq_tf_top10.groupby('t').cumcount() + 1
    V_qqq_tf_top10['mom'] = V_qqq_tf_top10['sharpe_mom']
    sub_tf = V_qqq_tf_top10[V_qqq_tf_top10['rank'] <= 10]
    h_tf_rows = []
    for t_val, tk_val in zip(sub_tf.t, sub_tf.ticker):
        r_v, st_v, sym_v, fl_v, ed_v, xd_v = QE.hold_return(tk_val, t_val, mode='open', open_stores=['tiingo_api', 'yahoo', 'wikibulk'])
        h_tf_rows.append((t_val, tk_val, r_v, st_v, sym_v, fl_v, ed_v, xd_v))
    H_qqq_tf = pd.DataFrame(h_tf_rows, columns=['t', 'ticker', 'ret', 'ret_store', 'ret_sym', 'flag', 'entry', 'exit'])
    L_qqq_sh_tf = QB.run(V_qqq_tf_top10, H_qqq_tf, k=2, cost_bp=10.0).set_index('month')

    # 7b. Tech Top-1 (S1) under Tiingo-First (using Tiingo EOD when available for both momentum & holding return)
    TIINGO_EXCLUDE = {'LSI', 'ALTR', 'ACS', 'TLAB', 'CPWR'}
    TIINGO_WINDOW = {'SNDK': ('2025-02-13', None), 'CA': (None, '2018-11-05'), 'DELL': ('2016-08-17', None)}
    ALIAS_T = {'FB': 'META', 'JDSU': 'VIAV', 'CSC': 'DXC', 'ERTS': 'EA', 'MOT': 'MSI', 'SAI': 'LDOS', 'YHOO': 'AABA',
               'NLOK': 'GEN', 'SYMC': 'GEN', 'FLT': 'CPAY', 'HRS': 'LHX', 'CDAY': 'DAY', 'FISV': 'FI'}

    def load_tiingo_df(tk):
        if tk in TIINGO_EXCLUDE:
            return None, None
        sym = ALIAS_T.get(tk, tk)
        df = QE.series('tiingo_api', sym)
        if df is not None:
            df = df.rename(columns={'adjopen': 'adj_open'}).copy()
            df['close'] = df['adjclose']
            src_name = f'tiingo_api:{sym}'
        else:
            df_p = QE.series('raw_tiingo', sym)
            if df_p is None:
                df_p = QE.series('raw_ndx', sym)
            if df_p is None:
                return None, None
            df = df_p.rename(columns={'adjopen': 'adj_open'}).copy()
            df['close'] = df['adjclose']
            src_name = f'raw_tiingo:{sym}'
        a, b = TIINGO_WINDOW.get(tk, (None, None))
        if a:
            df = df[df.index >= pd.Timestamp(a)]
        if b:
            df = df[df.index <= pd.Timestamp(b)]
        return (df if len(df) else None), src_name

    tech_tf_rows = []
    prev_tf_pick = None
    for t_val in TE.formations():
        m_val = t_val + pd.offsets.MonthEnd(1)
        univ = TE.it_universe(t_val, 'main')
        cand_list = []
        for tk in univ:
            tdf, tsrc = load_tiingo_df(tk)
            m_tiingo = TE._momentum_from_df(tdf, t_val) if tdf is not None else np.nan
            if np.isfinite(m_tiingo):
                cand_list.append((tk, m_tiingo, tsrc, tdf))
            else:
                m_eng, info_eng = TE.mom_cached(tk, t_val)
                if np.isfinite(m_eng):
                    cand_list.append((tk, m_eng, f"fallback_{info_eng['src']}:{info_eng['sym']}", None))
        cand_df = pd.DataFrame(cand_list, columns=['ticker', 'mom', 'src', 'tdf']).sort_values(['mom', 'ticker'], ascending=[False, True]).reset_index(drop=True)
        top_row = cand_df.iloc[0]
        pick_tk = top_row['ticker']
        tdf_pick = top_row['tdf']
        d0, d1 = QE.first_td_after(t_val, 1), QE.first_td_after(t_val + pd.offsets.MonthEnd(1), 1)
        ret_val, ret_src = np.nan, ''
        if tdf_pick is not None and d0 in tdf_pick.index and d1 in tdf_pick.index:
            if np.isfinite(tdf_pick.at[d0, 'adj_open']) and np.isfinite(tdf_pick.at[d1, 'adj_open']):
                ret_val = float(tdf_pick.at[d1, 'adj_open'] / tdf_pick.at[d0, 'adj_open'] - 1.0)
                ret_src = top_row['src'] + '_open'
        if not np.isfinite(ret_val):
            ret_val, info_r = tech_hold_return_flex(pick_tk, t_val, mode='open', n_day=1)
            ret_src = f"{info_r['src']}:{info_r['sym']}_{info_r['flag']}"
        sides = 1.0 if prev_tf_pick is None else (0.0 if pick_tk == prev_tf_pick else 2.0)
        net_val = (1.0 + ret_val) * ((1.0 - 0.001) ** sides) - 1.0 if sides else ret_val
        prev_tf_pick = pick_tk
        tech_tf_rows.append({'month': m_val, 'formation': t_val, 'picks': pick_tk, 'gross': ret_val, 'net': net_val, 'src': ret_src})
    L_tech_tf = pd.DataFrame(tech_tf_rows).set_index('month')

    r_core3_tf = 0.50 * L_qqq_sh_tf.loc[months, 'net'] + 0.50 * L_tech_tf.loc[months, 'net']

    grid7_rows = [
        summary_across_windows('Core3 Primary (Yahoo-First Open-to-Open) [FROZEN]', r_core3, {'Vendor': 'Primary'}),
        summary_across_windows('Core3 Second-Vendor (Tiingo-First Signals & Open-to-Open)', r_core3_tf, {'Vendor': 'Tiingo-First'}),
        summary_across_windows('QQQ Sharpe-Mom Top-2 Primary', L_qqq_sh_top2.loc[months, 'net'], {'Vendor': 'Primary'}),
        summary_across_windows('QQQ Sharpe-Mom Top-2 Tiingo-First', L_qqq_sh_tf.loc[months, 'net'], {'Vendor': 'Tiingo-First'}),
        summary_across_windows('Tech Top-1 (S1) Primary', L_tech_s1.loc[months, 'net'], {'Vendor': 'Primary'}),
        summary_across_windows('Tech Top-1 (S1) Tiingo-First', L_tech_tf.loc[months, 'net'], {'Vendor': 'Tiingo-First'}),
    ]
    df_g7 = pd.DataFrame(grid7_rows)
    df_g7.to_csv(os.path.join(HERE, '07_vendor_replication.csv'), index=False)

    # 7c. Position-by-position cross-check of all 639 held slot-months (213 months x 3 slots)
    xcheck_rows = []
    for m in months:
        t_val = m - pd.offsets.MonthEnd(1)
        d0, d1 = QE.first_td_after(t_val, 1), QE.first_td_after(m, 1)
        qp = L_qqq_sh_top2.loc[m, 'picks'].split('|')
        qr = [float(x) for x in L_qqq_sh_top2.loc[m, 'rets'].split('|')]
        tp = str(L_tech_s1.loc[m, 'picks']).strip()
        tr = float(L_tech_s1.loc[m, 'gross'])
        slots = [('QQQ_Sh_Slot1', qp[0], qr[0]), ('QQQ_Sh_Slot2', qp[1], qr[1]), ('Tech_Slot1', tp, tr)]
        for sname, tk, r_prim in slots:
            tdf, tsrc = load_tiingo_df(tk)
            r_tiin = np.nan
            if tdf is not None and d0 in tdf.index and d1 in tdf.index:
                if np.isfinite(tdf.at[d0, 'adj_open']) and np.isfinite(tdf.at[d1, 'adj_open']):
                    r_tiin = float(tdf.at[d1, 'adj_open'] / tdf.at[d0, 'adj_open'] - 1.0)
                elif np.isfinite(tdf.at[d0, 'adjclose']) and np.isfinite(tdf.at[d1, 'adjclose']):
                    r_tiin = float(tdf.at[d1, 'adjclose'] / tdf.at[d0, 'adjclose'] - 1.0)
            diff_bp = (r_prim - r_tiin) * 1e4 if np.isfinite(r_tiin) else np.nan
            xcheck_rows.append({
                'month': m.strftime('%Y-%m-%d'),
                'slot': sname,
                'ticker': tk,
                'entry_d': str(d0.date()),
                'exit_d': str(d1.date()),
                'ret_primary': r_prim,
                'ret_tiingo': r_tiin,
                'diff_bp': diff_bp,
                'tiingo_source': tsrc or 'no_tiingo_file',
            })
    df_xc = pd.DataFrame(xcheck_rows)
    df_xc.to_csv(os.path.join(HERE, '07b_position_crosscheck.csv'), index=False)
    valid_xc = df_xc[df_xc['diff_bp'].notna()]
    print(f'[Check 7] Cross-checked {len(valid_xc)}/{len(df_xc)} slot-months with Tiingo. '
          f'Median |diff|={valid_xc["diff_bp"].abs().median():.2f} bp, p95={valid_xc["diff_bp"].abs().quantile(0.95):.2f} bp.')

    # =========================================================================
    # CHECK 8: True Daily Mark-to-Market Equity Curve & Daily MaxDD (4,466 Days)
    # =========================================================================
    print('[Check 8] Building Exact Daily Mark-to-Market Equity Curves (2009-01-02 .. 2026-09-30)...')

    def build_qqq_sleeve_daily(L_sleeve, H_table):
        """Return Series of daily wealth for a QQQ Top-K sleeve (entry open -> daily closes -> exit open)."""
        Hm = H_table.set_index(['t', 'ticker'])
        W = 1.0
        pts = {}
        for m, row in L_sleeve.iterrows():
            t_val = row['t']
            picks = row['picks'].split('|')
            start_w = W * (1.0 + row['net']) / (1.0 + row['gross'])
            legs = []
            e_dates, x_dates = [], []
            for s in picks:
                h = Hm.loc[(t_val, s)]
                df = QE.series(h['ret_store'], h['ret_sym'])
                e, x = pd.Timestamp(h['entry']), pd.Timestamp(h['exit'])
                e_dates.append(e)
                x_dates.append(x)
                if df is None or e not in df.index or not np.isfinite(df.at[e, 'adjopen']):
                    legs.append(None)
                    continue
                p0 = float(df.at[e, 'adjopen'])
                seg = df['adjclose'].loc[e:x].dropna()
                seg = seg[seg.index < x] / p0
                legs.append(seg)
            e0 = min(e_dates)
            x0 = max(x_dates)
            days = sorted(set().union(*[set(c.index) for c in legs if c is not None]))
            for d in days:
                v = 0.0
                for c in legs:
                    if c is None:
                        v += 1.0 / len(picks)
                    else:
                        cc = c.loc[:d]
                        v += (float(cc.iloc[-1]) if len(cc) else 1.0) / len(picks)
                pts[d] = start_w * v
            W = W * (1.0 + float(row['net']))
            pts[x0] = W
        s_out = pd.Series(pts).sort_index()
        return s_out[~s_out.index.duplicated(keep='last')]

    # Load or build S1 daily wealth path
    s1_daily_df = pd.read_csv(os.path.join(TECH_DIR, 'S1_daily_wealth_path.csv'), index_col=0, parse_dates=True)
    w_tech_daily = s1_daily_df.iloc[:, 0].sort_index()
    w_tech_daily = w_tech_daily[~w_tech_daily.index.duplicated(keep='last')]

    w_qqq_sh_daily = build_qqq_sleeve_daily(L_qqq_sh_top2, H_all)
    w_qqq_raw_daily = build_qqq_sleeve_daily(L_qqq_raw_top2, H_all)

    # Align daily calendar across sleeves
    common_days = w_qqq_sh_daily.index.union(w_tech_daily.index).sort_values()
    common_days = common_days[(common_days >= '2009-01-02') & (common_days <= '2026-09-30')]

    r_d_qsh = w_qqq_sh_daily.reindex(common_days).ffill().fillna(1.0).pct_change().fillna(0.0)
    r_d_qraw = w_qqq_raw_daily.reindex(common_days).ffill().fillna(1.0).pct_change().fillna(0.0)
    r_d_tech = w_tech_daily.reindex(common_days).ffill().fillna(1.0).pct_change().fillna(0.0)

    # Exact intra-month drifted daily wealth of Core3, Core1, Core4 (rebalanced at each month's first trading day open)
    def combine_daily_sleeves(L_ref, sleeve_daily_wealths, weights):
        """
        At the start of each holding month m (entry date e_m), reset sleeve weights to `weights`,
        then let each sleeve's daily wealth drift inside month m until next month's entry date e_{m+1},
        scaling so month-end exit matches the exact monthly portfolio net return.
        """
        W_port = 1.0
        pts = {common_days[0]: 1.0}
        entry_dates = [QE.first_td_after(t_val, 1) for t_val in L_ref['t']]
        exit_dates = [QE.first_td_after(t_val + pd.offsets.MonthEnd(1), 1) for t_val in L_ref['t']]
        for idx_m, m in enumerate(L_ref.index):
            e_d, x_d = entry_dates[idx_m], exit_dates[idx_m]
            sub_days = common_days[(common_days >= e_d) & (common_days <= x_d)]
            if not len(sub_days):
                continue
            # Relative wealth of each sleeve from e_d
            rel_s = []
            for sw in sleeve_daily_wealths:
                s_sub = sw.reindex(sub_days).ffill()
                base_v = float(sw.loc[:e_d].iloc[-1]) if len(sw.loc[:e_d]) else 1.0
                rel_s.append(s_sub / base_v)
            comb_rel = sum(w * rs for w, rs in zip(weights, rel_s))
            for d_i, val in comb_rel.items():
                if d_i < x_d:
                    pts[d_i] = W_port * float(val)
            # At x_d, lock to exact monthly compounded wealth
            m_ret = sum(w * float(sw_m.loc[m]) for w, sw_m in zip(weights, [L_qqq_sh_top2['net'], L_tech_s1['net']] if len(weights) == 2 and weights[0] == 0.5 and sleeve_daily_wealths[0] is w_qqq_sh_daily else ([L_qqq_raw_top2['net'], L_tech_s1['net']] if len(weights) == 2 else [L_qqq_raw_top2['net'], L_qqq_sh_top2['net'], L_tech_s1['net']])))
            W_port = W_port * (1.0 + m_ret)
            pts[x_d] = W_port
        return pd.Series(pts).sort_index()

    w_core3_daily = combine_daily_sleeves(L_qqq_sh_top2, [w_qqq_sh_daily, w_tech_daily], [0.50, 0.50])
    w_core1_daily = combine_daily_sleeves(L_qqq_raw_top2, [w_qqq_raw_daily, w_tech_daily], [0.50, 0.50])
    w_core4_daily = combine_daily_sleeves(L_qqq_sh_top2, [w_qqq_raw_daily, w_qqq_sh_daily, w_tech_daily], [1/3, 1/3, 1/3])

    # Daily QQQ ETF and XLK ETF
    df_qqq_raw = QE.series('tiingo_api', 'QQQ')['adjclose'].reindex(common_days).ffill()
    w_qqq_etf_daily = df_qqq_raw / float(df_qqq_raw.iloc[0])
    df_xlk_raw = TE.load_source('yahoo', 'XLK')['adjclose'].reindex(common_days).ffill()
    w_xlk_etf_daily = df_xlk_raw / float(df_xlk_raw.iloc[0])

    daily_wealth_df = pd.DataFrame({
        'Core3_50_QQQ_Sharpe_50_Tech': w_core3_daily.reindex(common_days).ffill(),
        'Core4_3Way': w_core4_daily.reindex(common_days).ffill(),
        'Core1_50_QQQ_Raw_50_Tech': w_core1_daily.reindex(common_days).ffill(),
        'Sleeve1_QQQ_Sharpe_Top2': w_qqq_sh_daily.reindex(common_days).ffill(),
        'Sleeve1b_QQQ_Raw_Top2': w_qqq_raw_daily.reindex(common_days).ffill(),
        'Sleeve2_Tech_Top1_S1': w_tech_daily.reindex(common_days).ffill(),
        'Bench_QQQ_ETF': w_qqq_etf_daily,
        'Bench_XLK_ETF': w_xlk_etf_daily,
    }, index=common_days)
    daily_wealth_df.to_parquet(os.path.join(HERE, '08c_daily_wealth_paths.parquet'))

    def dd_stats(w_daily, r_monthly, label):
        w = w_daily.dropna()
        peak = w.cummax()
        dd_s = w / peak - 1.0
        max_dd_d = float(dd_s.min())
        trough_dt = dd_s.idxmin()
        peak_dt = w.loc[:trough_dt].idxmax()
        after_trough = w.loc[trough_dt:]
        rec_candidates = after_trough[after_trough >= peak.loc[trough_dt]]
        rec_dt = str(rec_candidates.index[0].date()) if len(rec_candidates) else 'Unrecovered'
        # Longest underwater duration in trading days
        is_uw = dd_s < -1e-6
        uw_groups = (~is_uw).cumsum()
        max_uw_days = int(is_uw.groupby(uw_groups).sum().max()) if is_uw.any() else 0
        m_dd = maxdd(r_monthly)
        # Daily volatility & Sharpe
        rd = w.pct_change().dropna()
        vol_d = float(rd.std(ddof=1) * np.sqrt(252.0))
        return {
            'Strategy': label,
            'CAGR_09_26': cagr(r_monthly),
            'Monthly_MaxDD': m_dd,
            'True_Daily_MaxDD': max_dd_d,
            'Daily_minus_Monthly_DD_Gap': max_dd_d - m_dd,
            'Peak_Date': str(peak_dt.date()),
            'Trough_Date': str(trough_dt.date()),
            'Recovery_Date': rec_dt,
            'Max_Underwater_Trading_Days': max_uw_days,
            'Daily_Ann_Vol': vol_d,
            'Calmar_Daily_DD': cagr(r_monthly) / abs(max_dd_d),
        }

    dd_summary_rows = [
        dd_stats(daily_wealth_df['Core3_50_QQQ_Sharpe_50_Tech'], r_core3, 'Core3 (50% QQQ Sharpe Top-2 + 50% Tech Top-1) [FROZEN]'),
        dd_stats(daily_wealth_df['Core4_3Way'], r_core4, 'Core4 (1/3 QQQ Raw + 1/3 QQQ Sharpe + 1/3 Tech)'),
        dd_stats(daily_wealth_df['Core1_50_QQQ_Raw_50_Tech'], r_core1, 'Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1)'),
        dd_stats(daily_wealth_df['Sleeve1_QQQ_Sharpe_Top2'], L_qqq_sh_top2['net'], 'Sleeve 1 Standalone: QQQ Sharpe-Mom Top-2'),
        dd_stats(daily_wealth_df['Sleeve1b_QQQ_Raw_Top2'], L_qqq_raw_top2['net'], 'Sleeve 1b Standalone: QQQ Raw 12-1 Top-2'),
        dd_stats(daily_wealth_df['Sleeve2_Tech_Top1_S1'], L_tech_s1['net'], 'Sleeve 2 Standalone: S&P 500 Tech Top-1 (S1)'),
        dd_stats(daily_wealth_df['Bench_QQQ_ETF'], r_qqq_etf, 'Benchmark: QQQ ETF'),
        dd_stats(daily_wealth_df['Bench_XLK_ETF'], r_xlk_etf, 'Benchmark: XLK ETF'),
    ]
    df_dd_sum = pd.DataFrame(dd_summary_rows)
    df_dd_sum.to_csv(os.path.join(HERE, '08_daily_drawdown_summary.csv'), index=False)

    # Find Top 5 distinct worst daily drawdown episodes for Core3
    w_c3 = daily_wealth_df['Core3_50_QQQ_Sharpe_50_Tech'].dropna()
    pk_c3 = w_c3.cummax()
    dd_c3 = w_c3 / pk_c3 - 1.0
    ep_id = (dd_c3 == 0).cumsum()
    episodes = []
    for eid, grp in dd_c3.groupby(ep_id):
        if grp.min() >= -0.05:
            continue
        tr_d = grp.idxmin()
        pk_d = grp.index[0]
        end_d = grp.index[-1]
        rec_str = str(end_d.date()) if end_d < dd_c3.index[-1] else 'Ongoing'
        episodes.append({
            'Peak_Date': str(pk_d.date()),
            'Trough_Date': str(tr_d.date()),
            'Recovery_Date': rec_str,
            'Daily_MaxDD': float(grp.min()),
            'Peak_to_Trough_Days': int(len(grp.loc[pk_d:tr_d])),
            'Total_Underwater_Days': int(len(grp) - 1),
        })
    df_ep = pd.DataFrame(episodes).sort_values('Daily_MaxDD').head(10).reset_index(drop=True)
    df_ep.to_csv(os.path.join(HERE, '08b_top_drawdown_episodes.csv'), index=False)
    print(f'[Check 8] True Daily MaxDD of Core3 = {df_dd_sum.iloc[0]["True_Daily_MaxDD"]:.2%} '
          f'(vs Monthly MaxDD = {df_dd_sum.iloc[0]["Monthly_MaxDD"]:.2%}).')

    # =========================================================================
    # CHECK 9: Subperiods, Calendar Years, Paired Tests & Multiple-Testing DSR
    # =========================================================================
    print('[Check 9] Running Subperiod Table, Calendar Years, Paired Tests & DSR...')
    # 9a. Calendar years + Subperiods
    key_series = {
        'Core3 (Frozen 50/50)': r_core3,
        'Core3 (Unified Mult)': U_core3_mult['net'],
        'Core4 (3-Way)': r_core4,
        'Core1 (Raw 50/50)': r_core1,
        'QQQ Sharpe Top-2': L_qqq_sh_top2['net'],
        'QQQ Raw Top-2': L_qqq_raw_top2['net'],
        'QQQ Raw Top-3': L_qqq_raw_top3['net'],
        'Tech Top-1 (S1)': L_tech_s1['net'],
        'Bench QQQ ETF': r_qqq_etf,
        'Bench XLK ETF': r_xlk_etf,
        'Bench SPY ETF': r_spy_etf,
    }
    sub_rows = []
    for sname, s_val in key_series.items():
        # Match daily wealth column if available
        w_map = {
            'Core3 (Frozen 50/50)': 'Core3_50_QQQ_Sharpe_50_Tech',
            'Core4 (3-Way)': 'Core4_3Way',
            'Core1 (Raw 50/50)': 'Core1_50_QQQ_Raw_50_Tech',
            'QQQ Sharpe Top-2': 'Sleeve1_QQQ_Sharpe_Top2',
            'QQQ Raw Top-2': 'Sleeve1b_QQQ_Raw_Top2',
            'Tech Top-1 (S1)': 'Sleeve2_Tech_Top1_S1',
            'Bench QQQ ETF': 'Bench_QQQ_ETF',
            'Bench XLK ETF': 'Bench_XLK_ETF',
        }
        for wname, a, b in WINDOWS:
            sub_s = s_val.loc[a:b]
            md = metrics_dict(sub_s)
            d_dd = np.nan
            if sname in w_map:
                dw = daily_wealth_df[w_map[sname]].loc[a[:7] + '-01':b]
                if len(dw):
                    d_dd = float((dw / dw.cummax() - 1.0).min())
            sub_rows.append({
                'Strategy': sname,
                'Window': wname,
                'Months': md['n'],
                'CAGR': md['CAGR'],
                'Vol': md['Vol'],
                'Sharpe': md['Sharpe'],
                'MaxDD_Monthly': md['MaxDD_m'],
                'MaxDD_Daily': d_dd,
                'Calmar_Monthly': md['Calmar'],
                'Win_Months_Pct': md['Win_pct'],
            })
    df_sub = pd.DataFrame(sub_rows)
    df_sub.to_csv(os.path.join(HERE, '09_subperiods_summary.csv'), index=False)

    # Calendar years table (including intra-year daily MaxDD for Core3)
    yr_rows = []
    for yr, grp in pd.DataFrame(key_series).groupby(months.year):
        r_yr = {k: float(np.prod(1.0 + grp[k]) - 1.0) for k in key_series}
        dw_yr = daily_wealth_df['Core3_50_QQQ_Sharpe_50_Tech'].loc[f'{yr}-01-01':f'{yr}-12-31']
        c3_dd_yr = float((dw_yr / dw_yr.cummax() - 1.0).min()) if len(dw_yr) else np.nan
        q_dd_yr = float((daily_wealth_df['Bench_QQQ_ETF'].loc[f'{yr}-01-01':f'{yr}-12-31'] /
                         daily_wealth_df['Bench_QQQ_ETF'].loc[f'{yr}-01-01':f'{yr}-12-31'].cummax() - 1.0).min())
        row_y = {'Year': str(yr) if yr < 2026 else '2026 (Jan-Sep)'}
        row_y.update(r_yr)
        row_y['Core3_IntraYear_Daily_MaxDD'] = c3_dd_yr
        row_y['QQQ_IntraYear_Daily_MaxDD'] = q_dd_yr
        yr_rows.append(row_y)
    df_yr = pd.DataFrame(yr_rows)
    df_yr.to_csv(os.path.join(HERE, '09a_calendar_years.csv'), index=False)

    # 9b. Paired Hypothesis Tests & CAPM Alpha/Beta
    paired_benchmarks = [
        ('Bench QQQ ETF', r_qqq_etf),
        ('Bench XLK ETF', r_xlk_etf),
        ('Bench NDX-EW (PIT 10bp)', r_ndx_ew),
        ('Bench SPY ETF', r_spy_etf),
        ('Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1)', r_core1),
        ('Sleeve 1 Alone: QQQ Sharpe-Mom Top-2', L_qqq_sh_top2['net']),
        ('Sleeve 2 Alone: Tech Top-1 (S1)', L_tech_s1['net']),
        ('QQQ Raw 12-1 Top-3 (Audited)', L_qqq_raw_top3['net']),
    ]
    test_windows = [
        ('FULL 2009-01..2026-09', '2009-01-31', '2026-09-30'),
        ('2009-2018 (pre-2019)', '2009-01-31', '2018-12-31'),
        ('2015-2026.09', '2015-01-31', '2026-09-30'),
        ('2019-2026.09', '2019-01-31', '2026-09-30'),
    ]
    paired_rows = []
    for wname, a, b in test_windows:
        sa = r_core3.loc[a:b]
        rf_sub = RF_M.reindex(sa.index).ffill().fillna(0.0)
        for bname, sb_full in paired_benchmarks:
            sb = sb_full.loc[a:b]
            d = (sa - sb).dropna()
            t3, p3 = nw_t(d, 3)
            t6, p6 = nw_t(d, 6)
            ci, p_le0 = stationary_boot_diff(sa.values, sb.values, draws=5000, block=6, seed=42)
            # CAPM regression of (sa - rf) on (sb - rf)
            y = (sa - rf_sub).values
            x = (sb - rf_sub).values
            Xm = np.column_stack([np.ones(len(x)), x])
            beta_vec = np.linalg.lstsq(Xm, y, rcond=None)[0]
            resid = y - Xm @ beta_vec
            at3, ap3 = nw_t(beta_vec[0] + resid, 3)
            paired_rows.append({
                'Window': wname,
                'Benchmark': bname,
                'Months': len(d),
                'Core3_CAGR': cagr(sa),
                'Bench_CAGR': cagr(sb),
                'CAGR_Diff': cagr(sa) - cagr(sb),
                'Arith_Diff_Ann': float(d.mean() * 12.0),
                'NW_t_lag3': t3,
                'NW_p_lag3': p3,
                'NW_t_lag6': t6,
                'NW_p_lag6': p6,
                'Boot_Diff_p5': ci[0],
                'Boot_Diff_p50': ci[1],
                'Boot_Diff_p95': ci[2],
                'Boot_P_Diff_le_0': p_le0,
                'Monthly_Win_Rate': float((d > 0).mean()),
                'CAPM_Alpha_Ann': float(beta_vec[0] * 12.0),
                'CAPM_Beta': float(beta_vec[1]),
                'Alpha_NW_t_lag3': at3,
                'Alpha_NW_p_lag3': ap3,
            })
    df_paired = pd.DataFrame(paired_rows)
    df_paired.to_csv(os.path.join(HERE, '09b_paired_tests_and_alpha.csv'), index=False)

    # 9c. Multiple Testing & Deflated Sharpe Ratio (DSR) across ALL repo trials + A/B/C experiments + Core3 grid
    repo_trials_df = pd.read_csv(os.path.join(QQQ_DIR, 'm_repo_trials.csv'))
    n_repo = len(repo_trials_df)
    # Add all A/B/C variants from alpha_core_regime_experiment_20261103 (39 variants) + all unique series in this audit
    audit_srs = [s.mean() / s.std(ddof=1) for s in all_audit_series.values() if s.std(ddof=1) > 0]
    combined_srs = np.unique(np.round(np.concatenate([repo_trials_df['sr_monthly'].values, audit_srs]), 6))
    n_total_all = len(combined_srs) + 39  # explicitly include the 39 A/B/C trials
    sr_var_all = float(np.var(combined_srs, ddof=1))

    def compute_dsr(r_arr, n_trials, sr_var):
        r_arr = np.asarray(r_arr, float)
        T_len = len(r_arr)
        sr = float(r_arr.mean() / r_arr.std(ddof=1))
        g3 = float(sst.skew(r_arr))
        g4 = float(sst.kurtosis(r_arr, fisher=False))
        em = 0.5772156649
        if n_trials > 1:
            sr0 = float(np.sqrt(sr_var) * ((1.0 - em) * sst.norm.ppf(1.0 - 1.0 / n_trials) + em * sst.norm.ppf(1.0 - 1.0 / (n_trials * np.e))))
        else:
            sr0 = 0.0
        denom = np.sqrt(max(1e-9, 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * (sr ** 2)))
        z = (sr - sr0) * np.sqrt(T_len - 1.0) / denom
        return float(sst.norm.cdf(z)), sr * np.sqrt(12.0), sr0 * np.sqrt(12.0), g3, g4

    dsr_rows = []
    for wname, a, b in [('FULL 2009-01..2026-09 (213m)', '2009-01-31', '2026-09-30'),
                        ('2015-01..2026-09 (141m)', '2015-01-31', '2026-09-30'),
                        ('2009-2018 Pre-2019 (120m)', '2009-01-31', '2018-12-31')]:
        sa = r_core3.loc[a:b]
        rf_s = RF_M.reindex(sa.index).ffill().fillna(0.0)
        sq = r_qqq_etf.loc[a:b]
        sc1 = r_core1.loc[a:b]

        for s_label, diff_s in [
            ('Core3 Excess Return (over 3M T-bill)', sa - rf_s),
            ('Core3 Active Return (minus QQQ ETF)', sa - sq),
            ('Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom)', sa - sc1),
        ]:
            for N_tr in [1, 10, 39, 100, n_repo, n_repo + 39, n_total_all]:
                p_dsr, sr_ann, sr0_ann, sk, kt = compute_dsr(diff_s.values, N_tr, sr_var_all)
                dsr_rows.append({
                    'Window': wname,
                    'Series': s_label,
                    'N_Trials': N_tr,
                    'Observed_SR_or_IR_Ann': sr_ann,
                    'Expected_Max_Null_SR0_Ann': sr0_ann,
                    'Skewness': sk,
                    'Kurtosis': kt,
                    'DSR_p_value': p_dsr,
                })
    df_dsr = pd.DataFrame(dsr_rows)
    df_dsr.to_csv(os.path.join(HERE, '09c_multiple_testing_dsr.csv'), index=False)
    print(f'[Check 9] Saved DSR table across N up to {n_total_all} total trials.')
    print('=== ALL 10 CORE3 ADVERSARIAL CHECKS COMPLETED SUCCESSFULLY ===')


if __name__ == '__main__':
    main()
