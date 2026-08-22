#!/usr/bin/env python3
"""
Feature Stability and Significance Trial
1. Permutation Significance: Are the ICs statistically different from random noise?
2. Time Stability: H1 (2019-2022) vs H2 (2023-2026) split.
3. Lag Robustness: Do they hold up at T+1, T+2, and T+3?
"""

import os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, load_pe, build_features, SECTORS

daily = load_prices()
pe, pe_cov = load_pe()

def run_ic_eval(df, f):
    ics = []
    t1_exc = []
    for dt in df['date'].unique():
        m = df[df['date'] == dt].dropna(subset=[f, 'exec_ret'])
        if len(m) < 4: continue
        ic, _ = spearmanr(m[f], m['exec_ret'])
        ics.append(ic)
        m_s = m.sort_values(f, ascending=False)
        t1 = m_s.head(1)['exec_ret'].mean()
        ew = m['exec_ret'].mean()
        t1_exc.append(t1 - ew)
    return np.nanmean(ics) if len(ics) else np.nan, np.nanmean(t1_exc) if len(t1_exc) else np.nan

dfs = {}
for lag in [1, 2, 3]:
    df_l, fx, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=lag, strict_universe_n=len(SECTORS)-1)
    dmin = df_l[df_l['universe_valid']]['date'].min()
    dfs[lag] = df_l[df_l['date'] >= dmin].copy()

df_main = dfs[2]
h1_mask = df_main['date'] <= '2022-12-31'
h2_mask = df_main['date'] >= '2023-01-01'

N_PERM = 500
results = []

print("Running stability trials on 9 features (500 permutations each)...", flush=True)

for f in fx:
    ic_h1, t1_h1 = run_ic_eval(df_main[h1_mask], f)
    ic_h2, t1_h2 = run_ic_eval(df_main[h2_mask], f)
    ic_full, t1_full = run_ic_eval(df_main, f)
    
    ic_t1, _ = run_ic_eval(dfs[1], f)
    ic_t3, _ = run_ic_eval(dfs[3], f)
    
    perm_ics = []
    dates = df_main['date'].unique()
    for seed in range(N_PERM):
        rng = np.random.RandomState(seed)
        shuf_ics = []
        for dt in dates:
            m = df_main[df_main['date'] == dt].dropna(subset=[f, 'exec_ret']).copy()
            if len(m) < 4: continue
            m[f] = rng.permutation(m[f].values)
            ic, _ = spearmanr(m[f], m['exec_ret'])
            shuf_ics.append(ic)
        perm_ics.append(np.nanmean(shuf_ics))
        
    p_val = np.mean(np.abs(perm_ics) >= np.abs(ic_full))
    
    results.append({
        'Feature': f.replace('_xs', ''),
        'IC': ic_full,
        'p-val': p_val,
        'IC_H1': ic_h1,
        'IC_H2': ic_h2,
        'IC_T1': ic_t1,
        'IC_T3': ic_t3,
        'T1_H1_ann': t1_h1 * 12,
        'T1_H2_ann': t1_h2 * 12
    })

res_df = pd.DataFrame(results)

print("\n" + "="*95)
print(f"{'Feature':<18s} {'IC(T2)':>7s} {'p-val':>6s} | {'H1 IC':>7s} {'H2 IC':>7s} | {'T+1 IC':>7s} {'T+3 IC':>7s} | {'T1_H1':>7s} {'T1_H2':>7s}")
print("-" * 95)
for _, r in res_df.sort_values('IC', ascending=False, key=abs).iterrows():
    print(f"{r['Feature']:<18s} {r['IC']:+7.3f} {r['p-val']:6.3f} | {r['IC_H1']:+7.3f} {r['IC_H2']:+7.3f} | {r['IC_T1']:+7.3f} {r['IC_T3']:+7.3f} | {r['T1_H1_ann']*100:+6.1f}% {r['T1_H2_ann']*100:+6.1f}%")
print("="*95)
