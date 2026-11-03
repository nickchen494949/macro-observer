"""Freeze the CLAIMED G1_SPY_2e ledger from the existing engine (reference only; never used by the independent engine)."""
import os, sys, pandas as pd, numpy as np
ROOT = '/Users/happygolucky/Desktop/宏观观察器'
sys.path.insert(0, os.path.join(ROOT, 'outputs/core3_qqq_spy_g1_audit_20261103'))
import run_qqq_spy_g1_audit as R7
dq = pd.read_parquet(os.path.join(ROOT, 'outputs/core3_stock_selection_audit_20261103/qqq_selection_panel.parquet'))
ds = pd.read_parquet(os.path.join(ROOT, 'outputs/core3_qqq_spy_g1_audit_20261103/spy_selection_panel.parquet'))
q = R7.simulate_single_sleeve(dq, {'type':'score','base_col':'sharpe_mom_12_1','score_col':'sharpe_mom_12_1'}, k=2, k_keep=5, linear_cost=True)
s = R7.simulate_single_sleeve(ds, {'type':'score','base_col':'mom_12_1','score_col':'mom_12_1'}, k=1, k_keep=3, linear_cost=False)
L = R7.combine_sleeves([(q,.5),(s,.5)], ['qqq','spy'])
out = pd.DataFrame({'t': q['t_date'], 'qqq_picks': q['picks'], 'qqq_net': q['net'], 'qqq_to': q['turnover'],
                    'spy_pick': s['picks'], 'spy_net': s['net'], 'spy_to': s['turnover'], 'port_net': L['net']})
out.to_csv('claimed_G1_SPY_2e_ledger.csv')
r = out['port_net']; n = len(r)
print('months', n, 'CAGR', (np.prod(1+r))**(12/n)-1)
# Look-ahead probe: rows with NaN hold_ret are dropped from ranking
for nm, d, col in [('QQQ', dq, 'sharpe_mom_12_1'), ('SPY', ds, 'mom_12_1')]:
    d = d.copy(); d['rk'] = d.groupby('t')[col].rank(ascending=False, method='first')
    na = d[d['hold_ret'].isna()]
    print(nm, 'rows', len(d), 'NaN hold_ret rows', len(na), 'of which rank<=5:', (na['rk']<=5).sum())
    print(na[na['rk']<=6][['t','ticker',col,'rk']].to_string(index=False))
    if 'exit_flag' in d.columns:
        d['top'] = d['rk'] <= 3
        print(d[d['top']]['exit_flag'].value_counts().to_string())
