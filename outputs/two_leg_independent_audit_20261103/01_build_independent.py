#!/usr/bin/env python3
"""01_build_independent.py — build independent membership + feature panels, picks, ledger; save to disk."""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ind_engine as IE

t0 = time.time()
M_ndx = IE.ndx_members()
M_spx = IE.spx_members()
print(f'membership: NDX avg {np.mean([len(v) for v in M_ndx.values()]):.1f}, SPX avg {np.mean([len(v) for v in M_spx.values()]):.1f}')

Pq = IE.build_panel(M_ndx)
Pq.to_parquet(os.path.join(HERE, 'ind_panel_ndx.parquet'), index=False)
print(f'NDX panel {len(Pq)} rows, valid {Pq["mom"].notna().sum()}  ({time.time()-t0:.0f}s)')
Ps = IE.build_panel(M_spx)
Ps.to_parquet(os.path.join(HERE, 'ind_panel_spx.parquet'), index=False)
print(f'SPX panel {len(Ps)} rows, valid {Ps["mom"].notna().sum()}  ({time.time()-t0:.0f}s)')

pk_q = IE.sleeve_picks(Pq, 'sharpe', k=2, keep=5)
pk_s = IE.sleeve_picks(Ps, 'mom', k=1, keep=3)
L = IE.simulate({'qqq': Pq, 'spy': Ps}, {'qqq': pk_q, 'spy': pk_s}, {'qqq': 0.5, 'spy': 0.5})
L['qqq_picks'] = [ '|'.join(pk_q[t]) for t in L.index]
L['spy_pick'] = [ '|'.join(pk_s[t]) for t in L.index]
L[['qqq_picks', 'spy_pick', 'gross', 'turnover', 'net']].to_csv(os.path.join(HERE, 'ind_ledger_G1_SPY_2e.csv'))
r = L['net']
print('months', len(r), 'NaN months', r.isna().sum(), 'CAGR', (np.prod(1 + r.fillna(0))) ** (12 / len(r)) - 1)
