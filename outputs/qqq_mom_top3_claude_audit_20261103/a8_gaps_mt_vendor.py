#!/usr/bin/env python3
"""
a8_gaps_mt_vendor.py — (1) data-gap impact, (2) multiple-testing / deflated Sharpe, (3) risk-matched QQQ,
(4) full second-vendor replication (Tiingo-first prices for signals AND returns).

Outputs: g_gap_impact.csv, m_multiple_testing.csv, m_repo_trials.csv, x_risk_matched.csv, x_vendor_swap.csv
"""
import glob
import os

import numpy as np
import pandas as pd
from scipy import stats as sst

import a2_engine as E
import a3_signals as S
import a4_backtest as B
import a5_stats_stress as X

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = E.ROOT


# ------------------------------------------------------------------ (1) gaps
def gap_impact(P):
    G = pd.read_csv(os.path.join(HERE, 's_gaps_member_months.csv'), parse_dates=['t'])
    G = G[~G.reason.str.startswith('history_shorter')]
    thr = P[P['rank'] == 3].set_index('t')['mom']
    # alternative evidence for gap names (Tiingo successor/renamed listings fetched by a0)
    alt = {'FOXA': 'TFCFA', 'FOX': 'TFCF', 'MICC': 'TIGO', 'CA': 'CA', 'BMC': 'BMC', 'LIFE': 'LIFE', 'QRTEA': 'QRTEA',
           'LMCK': 'LMCK', 'PPDI': 'PPDI'}
    rows = []
    for _, g in G.iterrows():
        t, tk = g.t, g.ticker
        m_alt, src = np.nan, ''
        sym = alt.get(tk)
        if sym:
            df = E.series('tiingo_api', sym)
            if df is not None:
                ps, _ = E.px_at(df, 'adjclose', t - pd.offsets.MonthEnd(1))
                pl, _ = E.px_at(df, 'adjclose', t - pd.offsets.MonthEnd(12))
                p0, _ = E.px_at(df, 'adjclose', t)
                if np.isfinite(ps) and np.isfinite(pl) and np.isfinite(p0):
                    m_alt, src = ps / pl - 1, f'tiingo:{sym}'
        rows.append({'t': t.date(), 'ticker': tk, 'reason': g.reason.split(' |')[0], 'top3_threshold_mom': thr.get(t, np.nan),
                     'alt_mom': m_alt, 'alt_source': src,
                     'would_enter_top3': (m_alt > thr.get(t, np.inf)) if np.isfinite(m_alt) else 'unknown'})
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(HERE, 'g_gap_impact.csv'), index=False)
    print(f'non-new-listing gap member-months: {len(R)} over {R.t.nunique()} months; '
          f'priced via alternative: {R.alt_mom.notna().sum()}; would enter Top-3: {(R.would_enter_top3 == True).sum()}; '
          f'unknown: {(R.would_enter_top3 == "unknown").sum()}')
    print(R.groupby('ticker').agg(n=('t', 'size'), first=('t', 'min'), last=('t', 'max'), thr_min=('top3_threshold_mom', 'min'),
                                  alt_max=('alt_mom', 'max'), src=('alt_source', 'first')).to_string())
    return R


# ------------------------------------------------------------------ (2) multiple testing
def repo_trials(a='2015-02-28', b='2026-09-30'):
    rows = []
    for f in glob.glob(os.path.join(ROOT, 'outputs', '**', '*.csv'), recursive=True) + \
            glob.glob(os.path.join(ROOT, 'research', '**', 'results', '**', '*.csv'), recursive=True):
        if 'qqq_mom_top3_claude_audit' in f:
            continue
        try:
            h = pd.read_csv(f, nrows=3)
        except Exception:
            continue
        if 'net' not in h.columns or not ({'month'} & set(h.columns)):
            continue
        try:
            d = pd.read_csv(f, parse_dates=['month'])
            s = d.set_index('month')['net']
            s = pd.to_numeric(s, errors='coerce')
            s = s[~s.index.duplicated()].sort_index().loc[a:b].dropna()
        except Exception:
            continue
        if len(s) < 60 or s.std() == 0:
            continue
        rows.append({'file': os.path.relpath(f, ROOT), 'n': len(s), 'sr_monthly': s.mean() / s.std(ddof=1)})
    T = pd.DataFrame(rows).drop_duplicates('sr_monthly')
    T.to_csv(os.path.join(HERE, 'm_repo_trials.csv'), index=False)
    return T


def dsr(r, n_trials, sr_var):
    r = np.asarray(r, float)
    T = len(r)
    sr = r.mean() / r.std(ddof=1)
    g3, g4 = sst.skew(r), sst.kurtosis(r, fisher=False)
    em = 0.5772156649
    sr0 = np.sqrt(sr_var) * ((1 - em) * sst.norm.ppf(1 - 1 / n_trials) + em * sst.norm.ppf(1 - 1 / (n_trials * np.e))) if n_trials > 1 else 0.0
    z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return float(sst.norm.cdf(z)), sr, sr0


# ------------------------------------------------------------------ (3) risk-matched QQQ
def levered(q, rf, L):
    return L * q - (L - 1) * rf


def main():
    P = pd.read_parquet(os.path.join(HERE, 's_panel.parquet'))
    H = B.hold_table(P, 'open')
    SPEC = B.run(P, H)
    months_t = sorted(SPEC.t)
    Q = X.qqq_ledger(months_t).set_index('month')['net']
    sp = SPEC.set_index('month')['net']
    rf = X.RF.reindex(sp.index).fillna(0)

    gap_impact(P)

    # multiple testing
    T = repo_trials()
    sr_var = T.sr_monthly.var(ddof=1)
    mt = []
    for wn, a, b in [('ORIG 2015-02..2026-09', '2015-02-28', '2026-09-30'), ('FULL 2009-01..2026-09', '2009-01-31', '2026-09-30')]:
        ex = (sp - rf).loc[a:b]
        exq = (Q - rf).loc[a:b]
        for N in (1, 10, 50, 100, len(T)):
            p, sr, sr0 = dsr(ex.values, N, sr_var)
            mt.append({'window': wn, 'series': 'SPEC Top-3 excess of rf', 'n_trials': N, 'sr_ann': sr * np.sqrt(12),
                       'sr0_ann (expected max of N null trials)': sr0 * np.sqrt(12), 'DSR': p})
        # information ratio vs QQQ (active return) deflated the same way
        act = (sp - Q).loc[a:b]
        for N in (1, 10, 50, 100, len(T)):
            p, sr, sr0 = dsr(act.values, N, sr_var)
            mt.append({'window': wn, 'series': 'SPEC minus QQQ (active)', 'n_trials': N, 'sr_ann': sr * np.sqrt(12),
                       'sr0_ann (expected max of N null trials)': sr0 * np.sqrt(12), 'DSR': p})
    M = pd.DataFrame(mt)
    M.to_csv(os.path.join(HERE, 'm_multiple_testing.csv'), index=False)
    print(f'repo strategy ledgers found (2015-02..2026-09, >=60m): {len(T)}; cross-trial SR(monthly) std {np.sqrt(sr_var):.3f}')
    print(M.to_string())

    # risk-matched QQQ
    rows = []
    for wn, a, b in X.WINDOWS:
        s, q, r = sp.loc[a:b], Q.loc[a:b], rf.loc[a:b]
        Lv = s.std() / q.std()
        Xm = np.column_stack([np.ones(len(q)), (q - r).values])
        beta = np.linalg.lstsq(Xm, (s - r).values, rcond=None)[0][1]
        rows.append({'window': wn, 'SPEC_CAGR': X.cagr(s), 'QQQ_CAGR': X.cagr(q), 'vol_ratio': Lv, 'beta': beta,
                     'QQQ_x_volmatched_CAGR': X.cagr(levered(q, r, Lv)), 'QQQ_x_beta_CAGR': X.cagr(levered(q, r, beta)),
                     'QQQ_x_volmatched_MaxDD': X.maxdd(levered(q, r, Lv)), 'SPEC_MaxDD': X.maxdd(s),
                     'SPEC_Sharpe': X.sharpe(s), 'QQQ_Sharpe': X.sharpe(q)})
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(HERE, 'x_risk_matched.csv'), index=False)
    print(R.to_string())

    # (4) second-vendor replication: Tiingo first for momentum and for returns
    E.STORES_CLOSE = ['tiingo_api', 'raw_ndx', 'raw_tiingo', 'yahoo', 'raw_wiki', 'wikibulk', 'raw_archive']
    Pv, _, _ = S.build()
    Pv.to_parquet(os.path.join(HERE, 's_panel_vendor_tiingo_first.parquet'), index=False)
    Hv = B.hold_table(Pv, 'open', open_stores=['tiingo_api', 'yahoo', 'wikibulk'], tag='open_d1_tiingo_first')
    Lv = B.run(Pv, Hv)
    m = SPEC.merge(Lv, on='month', suffixes=('_primary', '_tiingo_first'))
    m['same_picks'] = [set(a.split('|')) == set(b.split('|')) for a, b in zip(m.picks_primary, m.picks_tiingo_first)]
    m[['month', 'picks_primary', 'picks_tiingo_first', 'same_picks', 'net_primary', 'net_tiingo_first']].to_csv(
        os.path.join(HERE, 'x_vendor_swap.csv'), index=False)
    print(f'vendor swap: same Top-3 set {m.same_picks.sum()}/{len(m)} months')
    for wn, a, b in X.WINDOWS:
        x = m.set_index('month').loc[a:b]
        print(f'  {wn}: primary {X.cagr(x.net_primary):.2%}  tiingo-first {X.cagr(x.net_tiingo_first):.2%}')
    print(m[~m.same_picks][['month', 'picks_primary', 'picks_tiingo_first']].to_string())


if __name__ == '__main__':
    main()
