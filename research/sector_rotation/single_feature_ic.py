#!/usr/bin/env python3
"""
Single Feature Autopsy
Tests the cross-sectional Rank IC and Top bucket returns for all 9 individual features 
used in the original RF model, to see which "parts" actually carry signal.
"""

import os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, load_pe, build_features, FEAT_COLS, SECTORS

print("Loading data...")
daily = load_prices()
pe, pe_cov = load_pe()

STRICT_N = len(SECTORS) - 1
df, feat_xs, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=STRICT_N)

# STRICT UNIVERSE ONLY
df = df[df['universe_valid']].copy()
MASTER_START = df['date'].min().strftime('%Y-%m')
df = df[df['date'] >= pd.Period(MASTER_START, 'M').start_time].copy()

results = []

print(f"\nAnalyzing {len(feat_xs)} features over {df['date'].nunique()} months (Start: {MASTER_START})...\n")

for f in feat_xs:
    ics = []
    t1s = []
    t3s = []
    ews = []
    
    for dt in sorted(df['date'].unique()):
        month = df[df['date'] == dt].dropna(subset=[f, 'exec_ret'])
        if len(month) != STRICT_N: 
            continue
        
        ic, _ = spearmanr(month[f], month['exec_ret'])
        ics.append(ic)
        
        m_sorted = month.sort_values(f, ascending=False)
        t1s.append(m_sorted.head(1)['exec_ret'].mean())
        t3s.append(m_sorted.head(3)['exec_ret'].mean())
        ews.append(month['exec_ret'].mean())
        
    n = len(ics)
    if n == 0: continue
    
    mean_ic = np.nanmean(ics)
    t1_s = pd.Series(t1s).fillna(0.0)
    t3_s = pd.Series(t3s).fillna(0.0)
    ew_s = pd.Series(ews).fillna(0.0)
    
    c_t1 = (1 + t1_s).cumprod().iloc[-1] ** (12 / n) - 1
    c_t3 = (1 + t3_s).cumprod().iloc[-1] ** (12 / n) - 1
    c_ew = (1 + ew_s).cumprod().iloc[-1] ** (12 / n) - 1
    
    results.append({
        'Feature': f.replace('_xs', ''),
        'Rank IC': mean_ic,
        'Top1-EW': c_t1 - c_ew,
        'Top3-EW': c_t3 - c_ew,
        'Top1': c_t1,
        'Top3': c_t3,
        'EW': c_ew
    })

res_df = pd.DataFrame(results).sort_values('Rank IC', ascending=False)

print(f"{'Feature':<20s} {'Rank IC':>8s} {'Top1-EW':>9s} {'Top3-EW':>9s} {'Top1':>7s} {'Top3':>7s} {'EW':>7s}")
print("-" * 75)
for _, r in res_df.iterrows():
    print(f"{r['Feature']:<20s} {r['Rank IC']:+8.3f} {r['Top1-EW']*100:+8.1f}% {r['Top3-EW']*100:+8.1f}% "
          f"{r['Top1']*100:+6.1f}% {r['Top3']*100:+6.1f}% {r['EW']*100:+6.1f}%")
