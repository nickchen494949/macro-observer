#!/usr/bin/env python3
"""
a7_crosscheck.py — second-vendor verification of every SPEC position + identity checks.

For every (formation t, pick) of the SPEC Top-3 ledger:
  * primary return (as used by the ledger) vs Tiingo adjOpen->adjOpen (independent vendor), same dates
  * primary vs Tiingo adjClose(entry day)->adjClose(exit day) as a secondary check when no adjOpen
  * every |position return| > 30% is listed with both vendors and the raw (unadjusted) price move + splits
Identity: for every held ticker, monthly-return correlation between the series used for momentum and
any other store covering the same months (a wrong company under a recycled ticker shows up as ~0).

Outputs: v_position_crosscheck.csv, v_extreme_positions.csv, v_identity_overlap.csv
"""
import os

import numpy as np
import pandas as pd

import a2_engine as E
import a4_backtest as B

HERE = os.path.dirname(os.path.abspath(__file__))


def tiingo_ret(sym, e, x, col):
    df = E.series('tiingo_api', sym)
    if df is None or e not in df.index or x not in df.index:
        return np.nan
    a, b = df.at[e, col], df.at[x, col]
    return b / a - 1 if np.isfinite(a) and np.isfinite(b) else np.nan


def main():
    P = pd.read_parquet(os.path.join(HERE, 's_panel.parquet'))
    H = B.hold_table(P, 'open')
    L = B.run(P, H)
    Hm = H.set_index(['t', 'ticker'])
    rows = []
    for _, r in L.iterrows():
        for s in r['picks'].split('|'):
            h = Hm.loc[(r['t'], s)]
            sym = h['ret_sym']
            tsym = sym if E.series('tiingo_api', sym) is not None else (E.RENAME.get(s, (s,))[0])
            e, x = pd.Timestamp(h['entry']), pd.Timestamp(h['exit'])
            e1, x1 = E.first_td_after(r['t']), E.first_td_after(r['t'] + pd.offsets.MonthEnd(1))
            to = tiingo_ret(tsym, e1, x1, 'adjopen')
            tc = tiingo_ret(tsym, e1, x1, 'adjclose')
            rows.append({'t': r['t'].date(), 'month': r['month'].date(), 'ticker': s, 'primary_ret': h['ret'],
                         'primary_store': h['ret_store'], 'primary_flag': h['flag'], 'entry': e.date(), 'exit': x.date(),
                         'tiingo_sym': tsym, 'tiingo_open_to_open': to, 'tiingo_close_to_close_t1': tc,
                         'diff_vs_tiingo_open_bp': (h['ret'] - to) * 1e4 if np.isfinite(to) else np.nan,
                         'primary_is_tiingo': h['ret_store'] == 'tiingo_api'})
    V = pd.DataFrame(rows)
    V.to_csv(os.path.join(HERE, 'v_position_crosscheck.csv'), index=False)
    ind = V[~V.primary_is_tiingo & V.tiingo_open_to_open.notna()]
    print(f'{len(V)} positions; Tiingo adjOpen available for {V.tiingo_open_to_open.notna().sum()}; '
          f'primary already Tiingo for {V.primary_is_tiingo.sum()}; independent comparisons {len(ind)}')
    if len(ind):
        d = ind.diff_vs_tiingo_open_bp.abs()
        print(f'  |primary - Tiingo| bp: median {d.median():.2f}, p90 {d.quantile(.9):.2f}, max {d.max():.1f}; >25bp: {(d > 25).sum()}')
        print(ind[d > 25][['month', 'ticker', 'primary_store', 'primary_flag', 'primary_ret', 'tiingo_open_to_open', 'diff_vs_tiingo_open_bp']].to_string())
    noind = V[V.primary_is_tiingo | V.tiingo_open_to_open.isna()]
    print(f'positions without an independent second vendor open: {len(noind)} '
          f'(flags: {noind.primary_flag.value_counts().to_dict()})')

    # extreme positions
    X = V[V.primary_ret.abs() > 0.30].copy()
    X.to_csv(os.path.join(HERE, 'v_extreme_positions.csv'), index=False)
    print(f'extreme |ret|>30% positions: {len(X)}')
    print(X[['month', 'ticker', 'primary_store', 'primary_ret', 'tiingo_open_to_open', 'tiingo_close_to_close_t1']].to_string())

    # identity overlap: monthly returns of momentum series vs other stores
    idr = []
    for tk in sorted(set(P[P['rank'] <= 3].ticker)):
        c = E.candidates(tk)
        if len(c) < 2:
            idr.append({'ticker': tk, 'pair': c[0][0] + ':' + c[0][1] if c else '', 'n_months': 0, 'corr': np.nan})
            continue
        base_st, base_sym = P[(P.ticker == tk) & (P['rank'] <= 3)].iloc[0][['store', 'sym']]
        b = E.series(base_st, base_sym)['adjclose'].resample('ME').last().pct_change()
        for st, sym in c:
            if (st, sym) == (base_st, base_sym):
                continue
            o = E.series(st, sym)['adjclose'].resample('ME').last().pct_change()
            j = pd.concat([b, o], axis=1, join='inner').dropna()
            idr.append({'ticker': tk, 'pair': f'{base_st}:{base_sym} vs {st}:{sym}', 'n_months': len(j),
                        'corr': j.corr().iloc[0, 1] if len(j) > 6 else np.nan,
                        'median_abs_diff_pct': (j.iloc[:, 0] - j.iloc[:, 1]).abs().median() * 100 if len(j) else np.nan})
    I = pd.DataFrame(idr)
    I.to_csv(os.path.join(HERE, 'v_identity_overlap.csv'), index=False)
    weak = I[(I.n_months > 6) & (I['corr'] < 0.98)]
    print(f'identity overlap pairs: {len(I)}; pairs with corr<0.98 over >6 months: {len(weak)}')
    if len(weak):
        print(weak.to_string())


if __name__ == '__main__':
    main()
