#!/usr/bin/env python3
"""
Waterfall Autopsy Step 2: The Price Adjustment Bug (Dividend Contamination)
The old model calculated Forward EPS as (Price / PE). 
However, it used Total-Return Adjusted Price (which subtracts historical dividends)
instead of Split-Only Adjusted Price. 
This caused high-dividend sectors (Utilities, Real Estate) to have artificially
steep historical price curves, which translated into artificially high EPS growth!
"""

import os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor

from engine import load_prices, load_pe, build_features, SECTORS

print("="*80)
print("💀 WATERFALL AUTOPSY STEP 2: PRICE ADJUSTMENT BUG")
print("="*80)

print("Loading data...")
daily_correct = load_prices()
pe, pe_cov = load_pe()

NO_XLE_N = len(SECTORS) - 1

# 1. Realistic Correct Baseline
print("Building Realistic features...")
df_clean, feat_xs, _ = build_features(
    daily_correct, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=NO_XLE_N
)

# 2. Buggy Price Baseline
# To re-introduce the bug, we overwrite 'split_adj_close' with 'adj_close'.
# This forces the engine to calculate EPS using dividend-contaminated prices,
# artificially inflating the EPS momentum of high-yield sectors.
print("Building Buggy (Dividend-Contaminated) features...")
daily_buggy = {}
for t in SECTORS:
    if t in daily_correct:
        df_bug = daily_correct[t].copy()
        df_bug['split_adj_close'] = df_bug['adj_close']
        daily_buggy[t] = df_bug

df_buggy, _, _ = build_features(
    daily_buggy, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=NO_XLE_N
)

def run_rf_walk_forward(df, label):
    dates = sorted(df['date'].unique())
    dates = [d for d in dates if d >= pd.Timestamp('2019-01-01')]
    
    results = []
    for pred_date in dates:
        test_all = df[df['date'] == pred_date].copy()
        is_valid = test_all['universe_valid'].iloc[0] if len(test_all) > 0 else False
        
        if not is_valid: continue
            
        train = df[(df['target_exit_date'] <= pred_date) & (df['universe_valid'])].dropna(subset=feat_xs + ['target']).copy()
        test = test_all.dropna(subset=feat_xs + ['exec_ret']).copy()
        
        train_months = train['date'].nunique()
        if train_months < 12 or len(test) < NO_XLE_N:
            continue
            
        X_tr = train[feat_xs].values
        y_tr = train['target'].values
        X_te = test[feat_xs].values
        
        mdl = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=10, random_state=42, n_jobs=-1)
        mdl.fit(X_tr, y_tr)
        preds = mdl.predict(X_te)
        
        test['pred'] = preds
        ic = spearmanr(test['pred'], test['exec_ret'])[0]
        
        test = test.sort_values('pred', ascending=False)
        top3 = test.head(3)['exec_ret'].mean()
        ew = test['exec_ret'].mean()
        exc = top3 - ew
        
        results.append({
            'date': pred_date,
            'ic': ic,
            'exc': exc
        })
    return pd.DataFrame(results)

print("\nRunning Walk-Forward for Realistic Model...")
res_clean = run_rf_walk_forward(df_clean, "Clean")

print("Running Walk-Forward for Buggy Model...")
res_buggy = run_rf_walk_forward(df_buggy, "Buggy")

# Align dates to ensure fair comparison
common_dates = set(res_clean['date']).intersection(set(res_buggy['date']))
res_clean = res_clean[res_clean['date'].isin(common_dates)].sort_values('date')
res_buggy = res_buggy[res_buggy['date'].isin(common_dates)].sort_values('date')

merged = pd.merge(
    res_clean.rename(columns={'ic': 'ic_clean', 'exc': 'exc_clean'}),
    res_buggy.rename(columns={'ic': 'ic_buggy', 'exc': 'exc_buggy'}),
    on='date'
)

def print_comp(df, label):
    ic_bug = df['ic_buggy'].mean()
    ic_cln = df['ic_clean'].mean()
    exc_bug = df['exc_buggy'].mean() * 100
    exc_cln = df['exc_clean'].mean() * 100
    
    print(f"[{label:^8s}] N={len(df):2d} Months")
    print(f"Metric       | Buggy Price (Old) | Realistic Price | Alpha Illusion (Gap)")
    print("-" * 75)
    print(f"Rank IC      | {ic_bug:>17.3f} | {ic_cln:>15.3f} | {(ic_bug - ic_cln):+19.3f}")
    print(f"Top-3 Excess | {exc_bug:>16.2f}% | {exc_cln:>14.2f}% | {(exc_bug - exc_cln):+18.2f}%\n")

print("\n" + "="*80)
print("💀 AUTOPSY RESULTS: THE COST OF PRICE DATA CORRUPTION")
print("="*80)

print_comp(merged, "FULL")

h1 = merged[merged['date'] <= pd.Timestamp('2022-12-31')]
h2 = merged[merged['date'] >= pd.Timestamp('2023-01-01')]

print_comp(h1, "H1")
print_comp(h2, "H2")
