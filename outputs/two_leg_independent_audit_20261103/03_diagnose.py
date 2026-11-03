#!/usr/bin/env python3
"""03_diagnose.py — side-by-side Top-N rankings (claimed panel vs independent panel) at each disagreement formation."""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/Users/happygolucky/Desktop/宏观观察器'
CQ = pd.read_parquet(os.path.join(ROOT, 'outputs/core3_stock_selection_audit_20261103/qqq_selection_panel.parquet'))
CS = pd.read_parquet(os.path.join(ROOT, 'outputs/core3_qqq_spy_g1_audit_20261103/spy_selection_panel.parquet'))
IQ = pd.read_parquet(os.path.join(HERE, 'ind_panel_ndx.parquet'))
IS = pd.read_parquet(os.path.join(HERE, 'ind_panel_spx.parquet'))

def top(df, t, col, n, extra):
    g = df[df['t'] == t].sort_values(col, ascending=False).head(n)
    return g[['ticker', col] + extra].reset_index(drop=True)

qq_months = ['2009-04-30', '2009-07-31', '2018-10-31', '2018-11-30', '2019-01-31', '2019-05-31', '2025-12-31']
ss_months = ['2018-07-31', '2018-10-31', '2019-07-31', '2020-05-31', '2021-06-30']
pd.set_option('display.width', 250)
for t in qq_months:
    t = pd.Timestamp(t)
    a = top(CQ, t, 'sharpe_mom_12_1', 7, ['mom_12_1', 'vol_12_1', 'hold_ret'])
    b = top(IQ, t, 'sharpe', 7, ['mom', 'vol', 'hold_ret', 'src', 'sym'])
    print(f'\n===== QQQ t={t.date()}  CLAIMED | INDEPENDENT =====')
    print(pd.concat([a.add_prefix('C_'), b.add_prefix('I_')], axis=1).to_string())
for t in ss_months:
    t = pd.Timestamp(t)
    a = top(CS, t, 'mom_12_1', 6, ['vol_12_1', 'hold_ret', 'sector', 'store', 'exit_flag'])
    b = top(IS, t, 'mom', 6, ['vol', 'hold_ret', 'src', 'sym'])
    print(f'\n===== SPY t={t.date()}  CLAIMED | INDEPENDENT =====')
    print(pd.concat([a.add_prefix('C_'), b.add_prefix('I_')], axis=1).to_string())
