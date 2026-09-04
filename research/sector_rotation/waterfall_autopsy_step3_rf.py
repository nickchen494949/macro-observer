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

#!/usr/bin/env python3
"""
Waterfall Autopsy Step 3: Missing Data Drop-out (Dynamic Universe) Decomposition
Deconstructs the old model's excess return exactly into:
(C - A) = (C - B) + (B - A)
Where:
A: Equal weight return of all 10 sectors
B: Equal weight return of surviving (valid) sectors
C: Top-3 return picked by RF from surviving sectors
"""

import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from collections import defaultdict

from engine import load_prices, load_pe, build_features, SECTORS

print("="*80)
print("💀 WATERFALL AUTOPSY STEP 3: SURVIVORSHIP BIAS DECOMPOSITION")
print("="*80)

daily = load_prices()
pe, pe_cov = load_pe()
TARGET_TICKERS = [t for t in SECTORS if t != 'XLE']

print("Building Dynamic Universe Features (Old Buggy Model)...")
df_buggy, feat_xs, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=None
)

dates = sorted(df_buggy['date'].unique())
dates = [d for d in dates if d >= pd.Timestamp('2019-01-01')]

results = []
rng = np.random.RandomState(42)
drop_counts = defaultdict(list)

print(f"Running Decomposition Walk-Forward over {len(dates)} months...\n")

for pred_date in dates:
    test_all = df_buggy[(df_buggy['date'] == pred_date) & (df_buggy['ticker'].isin(TARGET_TICKERS))].copy()
    
    # We must be able to calculate A (Return of ALL 10 sectors)
    # Get true forward returns directly from daily prices to be safe
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
        continue # Skip if we can't even form the true 10-sector universe
        
    A_ret = np.mean(list(all_rets.values()))
    
    # Identify surviving vs dropped sectors (Buggy Logic)
    test_survivors = test_all.dropna(subset=feat_xs).copy()
    survivors = test_survivors['ticker'].tolist()
    dropped = list(set(TARGET_TICKERS) - set(survivors))
    
    if len(survivors) < 3:
        continue # Can't pick top 3
        
    B_ret = np.mean([all_rets[s] for s in survivors])
    dropped_ret = np.mean([all_rets[d] for d in dropped]) if dropped else np.nan
    
    # Track who dropped when
    for d in dropped:
        drop_counts[d].append(pred_date.year)
        
    # Train RF on historical survivors
    train_buggy = df_buggy[df_buggy['target_exit_date'] <= pred_date].dropna(subset=feat_xs + ['target']).copy()
    if train_buggy['date'].nunique() < 12:
        continue
        
    mdl = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=10, random_state=42, n_jobs=-1)
    mdl.fit(train_buggy[feat_xs].values, train_buggy['target'].values)
    
    test_survivors['pred'] = mdl.predict(test_survivors[feat_xs].values)
    top3_tickers = test_survivors.sort_values('pred', ascending=False).head(3)['ticker'].tolist()
    
    C_ret = np.mean([all_rets[t] for t in top3_tickers])
    
    results.append({
        'date': pred_date,
        'A_ret': A_ret,
        'B_ret': B_ret,
        'C_ret': C_ret,
        'survivor_count': len(survivors),
        'dropped_ret': dropped_ret,
        'survivor_ret': B_ret,
        'dropped_minus_survivor': dropped_ret - B_ret if dropped else np.nan
    })

res_df = pd.DataFrame(results)

def print_decomp(df, label):
    if len(df) == 0: return
    
    # Means in bps per month
    A = df['A_ret'].mean() * 10000
    B = df['B_ret'].mean() * 10000
    C = df['C_ret'].mean() * 10000
    
    total_adv = C - A
    menu_adv = B - A
    rf_adv = C - B
    
    avg_pool = df['survivor_count'].mean()
    
    print(f"[{label:^8s}] N={len(df):2d} Months")
    print(f"1. Total 10-Sector Universe Avg (A) : {A:>6.1f} bps")
    print(f"2. Surviving Sector Menu Avg (B)    : {B:>6.1f} bps")
    print(f"3. RF Top-3 Picks Avg (C)           : {C:>6.1f} bps")
    print("-" * 50)
    print(f"Total Observed Advantage (C - A)    : {total_adv:>+6.1f} bps / mo")
    print(f"  ├─ Menu Survivorship Bias (B - A) : {menu_adv:>+6.1f} bps / mo")
    print(f"  └─ True RF Stock Picking (C - B)  : {rf_adv:>+6.1f} bps / mo")
    print(f"Avg Menu Size: {avg_pool:.1f} / 10.0\n")

print_decomp(res_df, "FULL")
print_decomp(res_df[res_df['date'] <= pd.Timestamp('2022-12-31')], "H1")
print_decomp(res_df[res_df['date'] >= pd.Timestamp('2023-01-01')], "H2")

print("="*80)
print("🔍 DROPPED SECTOR ANALYSIS (Direct Comparison)")
print("="*80)
drop_df = res_df.dropna(subset=['dropped_minus_survivor'])

if len(drop_df) > 0:
    diff_mean = drop_df['dropped_minus_survivor'].mean() * 10000
    print(f"Months with Drop-outs: {len(drop_df)}")
    print(f"Avg Monthly Penalty (Dropped minus Survivors): {diff_mean:+.1f} bps")
    
    # Bootstrap CI for the penalty
    np.random.seed(42)
    boot = [np.mean(np.random.choice(drop_df['dropped_minus_survivor'].values, size=len(drop_df), replace=True)) * 10000 for _ in range(10000)]
    print(f"95% CI of Penalty: [{np.percentile(boot, 2.5):+.1f}, {np.percentile(boot, 97.5):+.1f}] bps\n")
    
    print("Who was dropped and when?")
    for t in sorted(drop_counts.keys()):
        yrs = sorted(list(set(drop_counts[t])))
        print(f"  {t:<5s}: {len(drop_counts[t]):2d} times (Years: {yrs})")
else:
    print("No drop-outs occurred in the testing period.")
