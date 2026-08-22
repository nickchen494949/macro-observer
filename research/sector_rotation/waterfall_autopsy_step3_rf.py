#!/usr/bin/env python3
"""
Waterfall Autopsy Step 3: Missing Data Drop-out (Dynamic Universe)
Test if deleting sectors with missing feature data (e.g., NaN PEs during crashes)
artificially inflated the old RF model's performance by implicitly helping it dodge landmines.
"""

import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor

from engine import load_prices, load_pe, build_features, SECTORS

print("="*80)
print("💀 WATERFALL AUTOPSY STEP 3: MISSING DATA DROP-OUT (DYNAMIC UNIVERSE)")
print("="*80)

daily = load_prices()
pe, pe_cov = load_pe()
NO_XLE_N = len(SECTORS) - 1
TARGET_TICKERS = [t for t in SECTORS if t != 'XLE']

print("Building Clean (Strict 10-Sector) Features...")
df_clean, feat_xs, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=NO_XLE_N
)

print("Building Buggy (Dynamic Universe) Features...")
df_buggy, _, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=None
)

dates = sorted(df_clean['date'].unique())
dates = [d for d in dates if d >= pd.Timestamp('2019-01-01')]

results = []
rng = np.random.RandomState(42)

print(f"Running Side-by-Side Walk-Forward over {len(dates)} months...\n")

for pred_date in dates:
    # ------------------------------------------------------------------
    # 1. BUGGY (DYNAMIC) EXECUTION
    # ------------------------------------------------------------------
    train_buggy = df_buggy[df_buggy['target_exit_date'] <= pred_date].dropna(subset=feat_xs + ['target']).copy()
    test_all_buggy = df_buggy[df_buggy['date'] == pred_date].copy()
    test_buggy = test_all_buggy.dropna(subset=feat_xs + ['exec_ret']).copy()
    
    buggy_n = len(test_buggy)
    buggy_ic = np.nan
    buggy_exc = 0.0
    dropped_ret = np.nan
    
    if train_buggy['date'].nunique() >= 12 and buggy_n > 0:
        mdl_buggy = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=10, random_state=42, n_jobs=-1)
        mdl_buggy.fit(train_buggy[feat_xs].values, train_buggy['target'].values)
        test_buggy['pred'] = mdl_buggy.predict(test_buggy[feat_xs].values)
        
        if buggy_n >= 3:
            buggy_ic = spearmanr(test_buggy['pred'], test_buggy['exec_ret'])[0]
            top3 = test_buggy.sort_values('pred', ascending=False).head(3)['exec_ret'].mean()
            ew = test_buggy['exec_ret'].mean()
            buggy_exc = top3 - ew
            
    # Calculate dropped sector performance
    dropped_tickers = set(TARGET_TICKERS) - set(test_buggy['ticker'])
    if len(dropped_tickers) > 0:
        d_rets = []
        for dtick in dropped_tickers:
            # Look up the actual real-world return from daily prices
            px = daily[dtick]['adj_close']
            cands = test_all_buggy[test_all_buggy['ticker'] == dtick]
            if len(cands) == 1:
                dr = cands['exec_ret'].iloc[0]
                if pd.notna(dr): d_rets.append(dr)
        if len(d_rets) > 0:
            dropped_ret = np.mean(d_rets)

    # ------------------------------------------------------------------
    # 2. CLEAN (STRICT) EXECUTION
    # ------------------------------------------------------------------
    test_all_clean = df_clean[df_clean['date'] == pred_date].copy()
    is_valid = test_all_clean['universe_valid'].iloc[0] if len(test_all_clean) > 0 else False
    
    clean_n = 10 if is_valid else 0
    clean_ic = np.nan
    clean_exc = 0.0
    
    if is_valid:
        train_clean = df_clean[(df_clean['target_exit_date'] <= pred_date) & (df_clean['universe_valid'])].dropna(subset=feat_xs + ['target']).copy()
        test_clean = test_all_clean.dropna(subset=feat_xs + ['exec_ret']).copy()
        
        if train_clean['date'].nunique() >= 12 and len(test_clean) == NO_XLE_N:
            mdl_clean = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=10, random_state=42, n_jobs=-1)
            mdl_clean.fit(train_clean[feat_xs].values, train_clean['target'].values)
            test_clean['pred'] = mdl_clean.predict(test_clean[feat_xs].values)
            
            clean_ic = spearmanr(test_clean['pred'], test_clean['exec_ret'])[0]
            top3 = test_clean.sort_values('pred', ascending=False).head(3)['exec_ret'].mean()
            ew = test_clean['exec_ret'].mean()
            clean_exc = top3 - ew
            
    results.append({
        'date': pred_date,
        'clean_n': clean_n,
        'clean_ic': clean_ic,
        'clean_exc': clean_exc,
        'buggy_n': buggy_n,
        'buggy_ic': buggy_ic,
        'buggy_exc': buggy_exc,
        'dropped_count': len(dropped_tickers),
        'dropped_ret': dropped_ret,
        'all_ew_ret': test_all_buggy['exec_ret'].mean() if len(test_all_buggy) > 0 else np.nan
    })

res_df = pd.DataFrame(results).dropna(subset=['buggy_ic']) # Only compare where buggy model traded

def print_comp(df, label):
    clean_ic = df['clean_ic'].mean()
    buggy_ic = df['buggy_ic'].mean()
    clean_exc = df['clean_exc'].mean() * 100
    buggy_exc = df['buggy_exc'].mean() * 100
    avg_buggy_n = df['buggy_n'].mean()
    
    drop_df = df[df['dropped_count'] > 0]
    dropped_ret = drop_df['dropped_ret'].mean() * 100
    bench_ret = drop_df['all_ew_ret'].mean() * 100
    
    print(f"[{label:^8s}] N={len(df):2d} Months")
    print(f"Metric       | Dynamic Bug (Old) | Strict Clean (New)| Alpha Illusion (Gap)")
    print("-" * 75)
    print(f"Rank IC      | {buggy_ic:>17.3f} | {clean_ic:>17.3f} | {(buggy_ic - clean_ic):+19.3f}")
    print(f"Top-3 Excess | {buggy_exc:>16.2f}% | {clean_exc:>16.2f}% | {(buggy_exc - clean_exc):+18.2f}%")
    print(f"Avg Pool Size| {avg_buggy_n:>17.1f} | {df['clean_n'].mean():>17.1f} |")
    print(f"\n[DROPPED SECTOR ANALYSIS for {label}]")
    if len(drop_df) > 0:
        print(f"Missing data occurred in {len(drop_df)} months.")
        print(f"Forward 1-Month Return of Deleted Sectors: {dropped_ret:+.2f}%")
        print(f"Forward 1-Month Return of ALL Sectors:     {bench_ret:+.2f}%")
        diff = dropped_ret - bench_ret
        print(f"Did deleting them save the model?         {'YES (Dodged a loser)' if diff < 0 else 'NO (Missed a winner)'} (Diff: {diff:+.2f}%)")
    else:
        print("No missing data in this period.")
    print("\n")

print("="*80)
print("💀 AUTOPSY RESULTS: THE COST OF DYNAMIC UNIVERSE DROP-OUTS")
print("="*80)

print_comp(res_df, "FULL")

h1 = res_df[res_df['date'] <= pd.Timestamp('2022-12-31')]
h2 = res_df[res_df['date'] >= pd.Timestamp('2023-01-01')]

if len(h1) > 0: print_comp(h1, "H1")
if len(h2) > 0: print_comp(h2, "H2")
