#!/usr/bin/env python3
"""
pit_fundamentals_truncation_test.py — "pretend today is C" test for the FUNDAMENTAL feature paths (external audit
2026-10-29: the price truncation test did not cover them; AMD 2017-06-30 used a margin first public on 2018-02-28).

For each cutoff C: every fundamental value that was NOT public on C is removed from the inputs
  - eps_quarterly_pit: each value column is blanked where its own first-public date (filed_<field> + 1 day, or the
    *_ttm_available_date for TTM columns, or available_date for row-level columns) is after C
  - pit_long (gross profit, R&D, balance-sheet, cash-flow items): rows filed after C are dropped
then the production feature builders run on the truncated inputs. Every feature at every formation month t <= C must
equal the value built from the full data. Builders tested: ml_features.fundamental_panel,
explosive_factors.quarterly_factors, factor_screen.build_new.
Output: PASS / FAIL with the first differing rows; exit code 1 on FAIL.
"""
import glob, os, shutil, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CUTOFFS = ['2013-06-30', '2017-06-30', '2021-12-31']


def truncated_root(C):
    C = pd.Timestamp(C)
    root = os.path.join(HERE, 'data', f'_pit_trunc_{C.date()}')
    shutil.rmtree(root, ignore_errors=True)
    fd = os.path.join(root, 'data', 'fundamentals')
    os.makedirs(os.path.join(fd, 'pit_long'))
    p = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'))
    one = pd.Timedelta(days=1)
    gate = {
        'eps_diluted': 'filed_eps_diluted', 'eps_diluted_approx': 'filed_eps_diluted', 'eps_diluted_approx_adj': 'filed_eps_diluted',
        'eps_basic': 'filed_eps_basic', 'eps_basic_approx': 'filed_eps_basic', 'net_income': 'filed_net_income',
        'revenue': 'filed_revenue', 'diluted_shares': 'filed_diluted_shares',
    }
    for col, fcol in gate.items():
        if col in p and fcol in p:
            p.loc[~(p[fcol] + one <= C), col] = np.nan
    ttm = {'eps_diluted_approx_ttm': 'eps_diluted_approx_ttm_available_date', 'eps_diluted_approx_ttm_adj': 'eps_diluted_approx_ttm_available_date',
           'eps_basic_approx_ttm': 'eps_basic_approx_ttm_available_date', 'eps_basic_approx_ttm_adj': 'eps_basic_approx_ttm_available_date',
           'net_income_ttm': 'net_income_ttm_available_date', 'revenue_ttm': 'revenue_ttm_available_date'}
    for col, acol in ttm.items():
        if col in p and acol in p:
            p.loc[~(p[acol] <= C), col] = np.nan
    # the dates themselves are only known once public
    for c in [c for c in p.columns if c.startswith('filed_')]:
        p.loc[~(p[c] + one <= C), c] = pd.NaT
    for c in [c for c in p.columns if c.endswith('_available_date')] + ['available_date']:
        p.loc[~(p[c] <= C), c] = pd.NaT
    p.to_parquet(os.path.join(fd, 'eps_quarterly_pit.parquet'), index=False)
    for f in glob.glob(os.path.join(HERE, 'data', 'fundamentals', 'pit_long', '*.parquet')):
        L = pd.read_parquet(f)
        L = L[pd.to_datetime(L.filed) + one <= C]
        # first-report flags must be recomputed on what was known at C (a restatement after C is unknown)
        L.to_parquet(os.path.join(fd, 'pit_long', os.path.basename(f)), index=False)
    return root


def compare(a, b, keys, label):
    a = a.set_index(keys).sort_index()
    b = b.set_index(keys).reindex(a.index)
    bad = []
    for c in a.columns:
        if c not in b.columns:
            continue
        x, y = a[c], b[c]
        if np.issubdtype(x.dtype, np.datetime64) or np.issubdtype(y.dtype, np.datetime64):
            diff = ~((x == y) | (x.isna() & y.isna()))
        else:
            x, y = pd.to_numeric(x, errors='coerce'), pd.to_numeric(y, errors='coerce')
            diff = ~(np.isclose(x, y, rtol=1e-9, atol=1e-12, equal_nan=True))
        if diff.any():
            bad.append((c, int(diff.sum()), a.index[diff][:3].tolist()))
    print(f'  {label}: {len(a)} rows, {len(bad)} columns differ', flush=True)
    for c, n, ex in bad:
        print(f'     {c}: {n} rows differ, e.g. {ex}', flush=True)
    return not bad


def main():
    import ml_features as mlf
    import explosive_factors as ef
    import factor_screen as fs
    ok = True
    X = pd.read_parquet(os.path.join(HERE, 'results', 'ml', 'panel.parquet'), columns=['t', 'ticker'])
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    X['cik'] = X.ticker.map({t.replace('.', '-'): int(c) for t, c in zip(cm.ticker, cm.cik)})
    for C in CUTOFFS:
        form = pd.date_range('2010-01-31', C, freq='ME')
        print('cutoff', C, flush=True)
        full_F = mlf.fundamental_panel(form)
        full_Q = ef.quarterly_factors(form)
        g = X[X.t.isin(form)].dropna(subset=['cik'])
        full_N = fs.build_new(g)
        root = truncated_root(C)
        keep = (mlf.HERE, ef.HERE, fs.HERE)
        try:
            mlf.HERE = ef.HERE = fs.HERE = root
            tr_F = mlf.fundamental_panel(form)
            tr_Q = ef.quarterly_factors(form)
            tr_N = fs.build_new(g)
        finally:
            mlf.HERE, ef.HERE, fs.HERE = keep
            shutil.rmtree(root, ignore_errors=True)
        ok &= compare(tr_F, full_F, ['t', 'cik'], 'ml_features.fundamental_panel')
        ok &= compare(tr_Q, full_Q, ['t', 'cik'], 'explosive_factors.quarterly_factors')
        ok &= compare(tr_N, full_N, ['t', 'cik'], 'factor_screen.build_new')
    print('RESULT:', 'PASS' if ok else 'FAIL', flush=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
