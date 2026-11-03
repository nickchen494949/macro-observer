#!/usr/bin/env python3
"""
a4_backtest.py — Claude clean-room backtest of the frozen rule:

  each month-end t: PIT Nasdaq-100 members -> 12-1 momentum -> buy the Top-3 equal weight (1/3 each)
  -> enter at the OPEN of the first trading day after t -> exit/rebalance at the OPEN of the first
  trading day of the following month -> 10 bp per side on traded weight (turnover vs drifted weights).

Outputs
  r_hold_returns_<mode>.parquet   per (t, ticker) holding return + source/flag (ranks <= 10 + all for EW)
  l_SPEC_top3.csv                 main ledger, holding months 2009-01 .. 2026-09
  r_recon_vs_original.csv         month-by-month reconciliation vs the original Gemini/ML3 ledger
"""
import os
import sys

import numpy as np
import pandas as pd

import a2_engine as E

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, '..', 'ml3_feature_discovery_20261102', 'ledgers_qqq_iwm', 'QQQ__T0_Pure_Momentum_12_1__Top3.csv')


def hold_table(P, mode='open', max_rank=15, all_names=False, n_day=1, open_stores=None, tag=None):
    tag = tag or f'{mode}_d{n_day}' + ('' if open_stores is None else '_' + '-'.join(open_stores))
    fn = os.path.join(HERE, f'r_hold_returns_{tag}{"_all" if all_names else ""}.parquet')
    if os.path.exists(fn) and '--rebuild' not in sys.argv:
        return pd.read_parquet(fn)
    sub = P if all_names else P[P['rank'] <= max_rank]
    rows = []
    for t, tk in zip(sub.t, sub.ticker):
        r, st, sym, flag, ed, xd = E.hold_return(tk, t, mode=mode, n_day=n_day, open_stores=open_stores)
        rows.append((t, tk, r, st, sym, flag, ed, xd))
    H = pd.DataFrame(rows, columns=['t', 'ticker', 'ret', 'ret_store', 'ret_sym', 'flag', 'entry', 'exit'])
    H.to_parquet(fn, index=False)
    return H


def run(P, H, k=3, cost_bp=10.0, ranks=None, start='2008-12-31', end='2026-08-31', exclude=None, ret_override=None):
    """Portfolio simulation. ranks: explicit list of rank slots (e.g. [2] = rank-2 only); default 1..k.
    exclude: set of tickers that may never be held (next ranks move up). ret_override: dict (t,ticker)->ret."""
    ranks = ranks or list(range(1, k + 1))
    Hm = H.set_index(['t', 'ticker'])
    prev_w = {}
    out = []
    for t, g in P[(P.t >= start) & (P.t <= end)].groupby('t'):
        g = g.sort_values('rank')
        if exclude:
            g = g[~g.ticker.isin(exclude)].copy()
            g['rank'] = np.arange(1, len(g) + 1)
        # a name that cannot be bought at the entry date (already delisted, e.g. late-entry variants)
        # is skipped and the next rank moves up; counted in 'n_skipped' (must be 0 for SPEC).
        ok = [s for s in g.ticker if (t, s) in Hm.index and np.isfinite(Hm.at[(t, s), 'ret'])]
        skipped = sum(1 for s in g[g['rank'].isin(ranks)].ticker if s not in ok)
        g = g[g.ticker.isin(ok)].copy()
        g['rank'] = np.arange(1, len(g) + 1)
        picks = list(g[g['rank'].isin(ranks)].ticker)
        if not picks:
            continue
        w = {s: 1.0 / len(picks) for s in picks}
        rets = {}
        for s in picks:
            r = ret_override.get((t, s)) if ret_override and (t, s) in ret_override else Hm.at[(t, s), 'ret']
            rets[s] = r
        if any(not np.isfinite(v) for v in rets.values()):
            raise RuntimeError(f'unpriced pick at {t.date()}: {rets}')
        turnover = sum(abs(w.get(s, 0) - prev_w.get(s, 0)) for s in set(w) | set(prev_w))
        gross = sum(w[s] * rets[s] for s in picks)
        cost = turnover * cost_bp / 1e4
        net = gross - cost
        # drifted weights at the exit (= next rebalance) open
        prev_w = {s: w[s] * (1 + rets[s]) / (1 + gross) for s in picks}
        flags = [Hm.at[(t, s), 'flag'] for s in picks]
        out.append({'t': t, 'month': (t + pd.offsets.MonthEnd(1)), 'picks': '|'.join(picks),
                    'rets': '|'.join(f'{rets[s]:.6f}' for s in picks), 'flags': '|'.join(flags),
                    'gross': gross, 'turnover': turnover, 'cost': cost, 'net': net, 'n_skipped': skipped})
    return pd.DataFrame(out)


def cagr(r):
    r = pd.Series(r).dropna()
    return (np.prod(1 + r)) ** (12 / len(r)) - 1 if len(r) else np.nan


def main():
    P = pd.read_parquet(os.path.join(HERE, 's_panel.parquet'))
    H = hold_table(P, 'open')
    L = run(P, H)
    L.to_csv(os.path.join(HERE, 'l_SPEC_top3.csv'), index=False)
    print('flags used by SPEC picks:', pd.Series('|'.join(L['flags']).split('|')).value_counts().to_dict())
    for a, b in [('2009-01-31', '2026-09-30'), ('2015-01-31', '2026-09-30'), ('2015-02-28', '2026-09-30'), ('2019-01-31', '2026-09-30')]:
        s = L[(L.month >= a) & (L.month <= b)].net
        print(f'SPEC Top-3 {a[:7]}..{b[:7]} n={len(s)} CAGR {cagr(s):.2%}')

    # reconciliation vs original ledger (read only here)
    O = pd.read_csv(ORIG, parse_dates=['month'])
    R = O.merge(L, on='month', how='left', suffixes=('_orig', '_claude'))
    R['same_set'] = [set(str(a).split('|')) == set(str(b).split('|')) for a, b in zip(R.picks_orig, R.picks_claude)]
    R['gross_diff_bp'] = (R.gross_claude - R.gross_orig) * 1e4
    R['net_diff_bp'] = (R.net_claude - R.net_orig) * 1e4
    R[['month', 'picks_orig', 'picks_claude', 'same_set', 'gross_orig', 'gross_claude', 'gross_diff_bp', 'turnover_orig',
       'turnover_claude', 'net_orig', 'net_claude', 'net_diff_bp', 'flags']].to_csv(os.path.join(HERE, 'r_recon_vs_original.csv'), index=False)
    print(f'recon: {len(R)} original months; same pick set {R.same_set.sum()}/{len(R)}; '
          f'|gross diff|>1bp among same-set months: {(R[R.same_set].gross_diff_bp.abs() > 1).sum()}')
    print(f'original CAGR {cagr(O.net):.2%} (n={len(O)})  vs claude same window {cagr(R.net_claude):.2%}')
    bad = R[~R.same_set | (R.gross_diff_bp.abs() > 1)]
    pd.set_option('display.width', 250)
    print(bad[['month', 'picks_orig', 'picks_claude', 'gross_orig', 'gross_claude', 'gross_diff_bp', 'flags']].to_string())


if __name__ == '__main__':
    main()
