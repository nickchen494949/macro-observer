#!/usr/bin/env python3
"""02_reconcile.py — month-by-month reconciliation: independent ledger vs claimed ledger."""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/Users/happygolucky/Desktop/宏观观察器'
C = pd.read_csv(os.path.join(HERE, 'claimed_G1_SPY_2e_ledger.csv'), index_col=0)
I = pd.read_csv(os.path.join(HERE, 'ind_ledger_G1_SPY_2e.csv'), index_col=0, parse_dates=True)
I.index = (I.index + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
J = C.join(I, rsuffix='_ind')

def same(a, b):
    return set(str(a).split('|')) == set(str(b).split('|'))

J['q_same'] = [same(a, b) for a, b in zip(J['qqq_picks'], J['qqq_picks_ind'])]
J['s_same'] = [same(a, b) for a, b in zip(J['spy_pick'], J['spy_pick_ind'])]
J['diff'] = J['net'] - J['port_net']
print('QQQ leg identical picks:', J['q_same'].sum(), '/', len(J))
print('SPY leg identical picks:', J['s_same'].sum(), '/', len(J))
both = J['q_same'] & J['s_same']
print('Both identical:', both.sum(), '| max |ret diff| when identical:', J.loc[both, 'diff'].abs().max())
print('CAGR claimed', (np.prod(1 + J['port_net'])) ** (12 / len(J)) - 1, ' independent', (np.prod(1 + J['net'])) ** (12 / len(J)) - 1)
cols = ['qqq_picks', 'qqq_picks_ind', 'spy_pick', 'spy_pick_ind', 'port_net', 'net', 'diff']
D = J[~both][cols]
D.to_csv(os.path.join(HERE, '02_pick_disagreements.csv'))
pd.set_option('display.width', 250)
print(D.to_string())
# identical-pick months with return diffs > 5bp
R = J[both & (J['diff'].abs() > 0.0005)][cols]
print('\nIdentical picks but return diff > 5bp:', len(R))
print(R.to_string())
