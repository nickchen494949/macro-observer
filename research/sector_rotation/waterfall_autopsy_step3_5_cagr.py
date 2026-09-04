#!/usr/bin/env python3
"""
Waterfall Autopsy Step 3.5: The CAGR Decomposition (Beta vs Alpha vs Time Compression)
Deconstructs the old model's historical ~15% CAGR to find out how much was simply 
the market going up (Beta), how much was time-compression from dropping missing months, 
and how much was actual RF excess return (Alpha).
"""

import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor

from engine import load_prices, load_pe, build_features, SECTORS

print("="*80)
print("💀 WATERFALL AUTOPSY STEP 3.5: CAGR DECOMPOSITION")
print("="*80)

daily = load_prices()
pe, pe_cov = load_pe()
TARGET_TICKERS = [t for t in SECTORS if t != 'XLE']

print("Building Dynamic Universe Features (Old Buggy Model)...")
df_buggy, feat_xs, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=None
)

dates = sorted(df_buggy['date'].unique())
dates = [d for d in dates if d >= pd.Timestamp('2019-01-01') and d <= pd.Timestamp('2026-06-30')]

results = []
rng = np.random.RandomState(42)

print(f"Running Full Calendar Walk-Forward over {len(dates)} months...\n")

for pred_date in dates:
    test_all = df_buggy[(df_buggy['date'] == pred_date) & (df_buggy['ticker'].isin(TARGET_TICKERS))].copy()
    
    # Baseline Returns
    spy_cands = daily['SPY']['adj_close']
    spy_entry = spy_cands[spy_cands.index <= pred_date]
    next_sig = df_buggy['date'][df_buggy['date'] > pred_date].min()
    spy_exit = spy_cands[spy_cands.index <= next_sig] if pd.notna(next_sig) else spy_cands
    
    spy_ret = 0.0
    if len(spy_entry) > 0 and len(spy_exit) > 0:
        spy_ret = spy_exit.iloc[-1] / spy_entry.iloc[-1] - 1
        
    all_rets = {}
    valid = True
    
    for t in TARGET_TICKERS:
        px = daily[t]['adj_close']
        cands = test_all[test_all['ticker'] == t]
        if len(cands) == 1:
            r = cands['exec_ret'].iloc[0]
            if pd.isna(r): 
                valid = False
            else:
                all_rets[t] = r
        else:
            valid = False
            
    if not valid or len(all_rets) != 10:
        continue
        
    ew_ret = np.mean(list(all_rets.values()))
    
    # Buggy Execution (Dynamic Universe)
    test_survivors = test_all.dropna(subset=feat_xs).copy()
    train_buggy = df_buggy[df_buggy['target_exit_date'] <= pred_date].dropna(subset=feat_xs + ['target']).copy()
    
    rf_ret = np.nan
    if train_buggy['date'].nunique() >= 12 and len(test_survivors) >= 3:
        mdl = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=10, random_state=42, n_jobs=-1)
        mdl.fit(train_buggy[feat_xs].values, train_buggy['target'].values)
        
        test_survivors['pred'] = mdl.predict(test_survivors[feat_xs].values)
        top3_tickers = test_survivors.sort_values('pred', ascending=False).head(3)['ticker'].tolist()
        rf_ret = np.mean([all_rets[t] for t in top3_tickers])
        
    results.append({
        'date': pred_date,
        'spy_ret': spy_ret,
        'ew_ret': ew_ret,
        'rf_ret': rf_ret
    })

res_df = pd.DataFrame(results).sort_values('date')

# 1. Continuous Calendar compounding (Missed months = 0% CASH return)
res_df['rf_continuous'] = res_df['rf_ret'].fillna(0.0)

# Calculate Cumulative Returns
def calc_cagr(rets_series):
    # Standard formula: (1 + total_return) ^ (12 / N_months) - 1
    # We use N_months = len(res_df) which represents the true elapsed calendar time!
    total_ret = np.prod(1 + rets_series)
    cagr = (total_ret ** (12 / len(res_df))) - 1
    return cagr * 100

spy_cagr = calc_cagr(res_df['spy_ret'])
ew_cagr = calc_cagr(res_df['ew_ret'])
rf_cont_cagr = calc_cagr(res_df['rf_continuous'])

# 2. Compressed Calendar compounding (The old bug)
# If the old code just dropped NaN rows, it shrank the denominator of time!
valid_rf = res_df.dropna(subset=['rf_ret'])
compressed_years = len(valid_rf) / 12.0
total_rf_ret = np.prod(1 + valid_rf['rf_ret'])
rf_compressed_cagr = (total_rf_ret ** (1 / compressed_years) - 1) * 100 if compressed_years > 0 else 0.0

print("\n" + "="*80)
print("🔍 CAGR DECOMPOSITION RESULTS (2019-01 to 2026-06)")
print("="*80)
print(f"Total Calendar Months Elapsed: {len(res_df)}")
print(f"Months actually traded by RF : {len(valid_rf)}")
print(f"Months skipped (missing data): {len(res_df) - len(valid_rf)}")
print("-" * 50)
print(f"1. Market Base (SPY CAGR)                   : {spy_cagr:>6.2f}%")
print(f"2. Sector Base (Equal-Weight 10 CAGR)       : {ew_cagr:>6.2f}%")
print(f"3. Old RF (Continuous Calendar + CASH)      : {rf_cont_cagr:>6.2f}%")
print(f"4. Old RF (Time-Compressed Bug)             : {rf_compressed_cagr:>6.2f}%")
print("-" * 50)

true_alpha = rf_cont_cagr - ew_cagr
compression_illusion = rf_compressed_cagr - rf_cont_cagr

print("\n[ DECOMPOSING THE OLD '15% CAGR' REPORT ]")
print(f"  Base Market/Sector Trend (Beta) : {ew_cagr:>5.2f}%")
print(f"+ True RF Stock Picking (Alpha)   : {true_alpha:>+5.2f}%")
print(f"+ Time Compression Illusion       : {compression_illusion:>+5.2f}%")
print("--------------------------------------------------")
print(f"= Reported Old Model CAGR         : {rf_compressed_cagr:>5.2f}%\n")
