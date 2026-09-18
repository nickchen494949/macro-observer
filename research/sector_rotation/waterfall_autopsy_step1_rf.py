#!/usr/bin/env python3
"""
Waterfall Autopsy Step 1: Timing Leakage on the Old RF Model
Using the original 9 features, training the exact same RandomForest, 
and changing ONLY the execution pricing from realistic T+2 to time-travel T+0.
"""

import os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor

from engine import load_prices, load_pe, build_features, SECTORS

print("="*80)
print("💀 WATERFALL AUTOPSY STEP 1: TIMING LEAKAGE (OLD RF MODEL)")
print("="*80)

print("Loading data and building features...")
daily = load_prices()
pe, pe_cov = load_pe()

# Build realistic T+2 dataframe
# We exclude XLE exactly like the "final correct model" for the old RF
NO_XLE_N = len(SECTORS) - 1
df_t2, feat_xs, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=NO_XLE_N
)

# Also explicitly calculate T+0 returns
# T+0 means we enter on the exact signal date (month-end close)
t0_returns = []
for t in SECTORS:
    if t == 'XLE': continue
    px = daily[t]['adj_close']
    for sig_date in df_t2['date'].unique():
        ts_sig = pd.Timestamp(sig_date)
        
        # Entry at T0 (Month End Close)
        past_px = px[px.index <= ts_sig]
        if len(past_px) == 0: continue
        entry_t0 = past_px.index[-1]
        
        # Exit at next month's T0
        next_sig = df_t2['date'][df_t2['date'] > ts_sig].min()
        if pd.isna(next_sig): continue
        ts_next = pd.Timestamp(next_sig)
        past_next = px[px.index <= ts_next]
        if len(past_next) == 0: continue
        exit_t0 = past_next.index[-1]
        
        ret_t0 = px.loc[exit_t0] / px.loc[entry_t0] - 1
        t0_returns.append({'date': sig_date, 'ticker': t, 'exec_ret_t0': ret_t0})

df_t0_rets = pd.DataFrame(t0_returns)
df_t2 = pd.merge(df_t2, df_t0_rets, on=['date', 'ticker'], how='left')

# Walk-forward loop exactly mimicking the old model
dates = sorted(df_t2['date'].unique())
dates = [d for d in dates if d >= pd.Timestamp('2019-01-01')]

results = []
rng = np.random.RandomState(42)

print(f"Running RF Walk-Forward over {len(dates)} months...")
for pred_date in dates:
    test_all = df_t2[df_t2['date'] == pred_date].copy()
    is_valid = test_all['universe_valid'].iloc[0] if len(test_all) > 0 else False
    
    if not is_valid:
        continue
        
    train = df_t2[(df_t2['target_exit_date'] <= pred_date) & (df_t2['universe_valid'])].dropna(subset=feat_xs + ['target']).copy()
    test = test_all.dropna(subset=feat_xs + ['exec_ret', 'exec_ret_t0']).copy()
    
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
    
    # Calculate IC
    ic_t2 = spearmanr(test['pred'], test['exec_ret'])[0]
    ic_t0 = spearmanr(test['pred'], test['exec_ret_t0'])[0]
    
    # Calculate Top-3 EW
    test = test.sort_values('pred', ascending=False)
    top3 = test.head(3)
    
    t2_top3 = top3['exec_ret'].mean()
    t2_ew = test['exec_ret'].mean()
    t2_exc = t2_top3 - t2_ew
    
    t0_top3 = top3['exec_ret_t0'].mean()
    t0_ew = test['exec_ret_t0'].mean()
    t0_exc = t0_top3 - t0_ew
    
    results.append({
        'date': pred_date,
        'ic_t2': ic_t2,
        'ic_t0': ic_t0,
        'exc_t2': t2_exc,
        'exc_t0': t0_exc
    })

res_df = pd.DataFrame(results).dropna()

def print_comp(df, label):
    ic_t0 = df['ic_t0'].mean()
    ic_t2 = df['ic_t2'].mean()
    exc_t0 = df['exc_t0'].mean() * 100
    exc_t2 = df['exc_t2'].mean() * 100
    
    print(f"[{label:^8s}] N={len(df):2d} Months")
    print(f"Metric       | Time-Travel (T+0) | Realistic (T+2) | Alpha Illusion (Gap)")
    print("-" * 75)
    print(f"Rank IC      | {ic_t0:>17.3f} | {ic_t2:>15.3f} | {(ic_t0 - ic_t2):+19.3f}")
    print(f"Top-3 Excess | {exc_t0:>16.2f}% | {exc_t2:>14.2f}% | {(exc_t0 - exc_t2):+18.2f}%\n")

print("\n" + "="*80)
print("💀 AUTOPSY RESULTS: THE COST OF TIME-TRAVEL")
print("="*80)

print_comp(res_df, "FULL")

h1 = res_df[res_df['date'] <= pd.Timestamp('2022-12-31')]
h2 = res_df[res_df['date'] >= pd.Timestamp('2023-01-01')]

print_comp(h1, "H1")
print_comp(h2, "H2")
