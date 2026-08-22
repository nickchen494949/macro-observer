#!/usr/bin/env python3
"""
Waterfall Autopsy Step 1: Timing Leakage (T+0 vs T+2 Execution)
Isolating the impact of the old model's time-travel execution flaw using the correct Static Real Yield signal.
"""

import os, json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, SECTORS

MACRO_SECTORS = SECTORS.copy()
SENSITIVE_SECTORS = ['XLK', 'XLC', 'XLU', 'XLRE']

FRED_DIR = "/Users/happygolucky/projects/宏观观察器/data/fred/"

def load_fred_series(filename):
    with open(os.path.join(FRED_DIR, filename), 'r') as f:
        data = json.load(f)
        if 'values' in data:
            df = pd.DataFrame(data['values'], columns=['date', 'value'])
        elif 'observations' in data:
            df = pd.DataFrame([{ 'date': obs['date'], 'value': float(obs['value']) } 
                               for obs in data['observations'] if obs['value'] != '.'])
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = df['value'].astype(float)
        return df.sort_values('date').reset_index(drop=True)

ry = load_fred_series('DFII10.json')
ry_daily = ry.set_index('date')['value']

daily = load_prices()
spy_px = daily['SPY']['adj_close']
month_ends = spy_px.index.to_period('M').unique()

def get_monthly_series(df):
    df = df.copy()
    df['ym'] = df['date'].dt.to_period('M')
    return df.groupby('ym').last()['value']

ry_m = get_monthly_series(ry)

macro_shocks = []
for me in month_ends:
    t0 = me
    t1 = me - 1
    if t0 not in ry_m.index or t1 not in ry_m.index: continue
    ry_shock = -(ry_m[t0] - ry_m[t1])
    macro_shocks.append({'date': me, 'ry_raw': ry_shock})

shocks_df = pd.DataFrame(macro_shocks).set_index('date').dropna()

results = []

for i, dt in enumerate(shocks_df.index):
    # Need next month for execution
    if i + 1 >= len(shocks_df.index): continue
    
    # Month-end timestamp (T+0)
    month_end_ts = pd.Timestamp(dt.end_time)
    spy_past = spy_px[spy_px.index <= month_end_ts]
    if len(spy_past) == 0: continue
    t0_date = spy_past.index[-1]
    
    # Correct T+2 execution Date
    next_month_start = pd.Timestamp(dt.end_time)
    next_month_end = pd.Timestamp((dt+1).end_time)
    spy_n_m = spy_px[(spy_px.index >= next_month_start) & (spy_px.index <= next_month_end)]
    if len(spy_n_m) < 2: continue
    t2_date = spy_n_m.index[1]
    
    # Exit date (next month T+2 for realistic, next month T+0 for cheating)
    # Actually, let's keep holding period exactly 1 month.
    # T+0 exit = next month's T+0
    # T+2 exit = next month's T+2
    
    spy_n_past = spy_px[spy_px.index <= next_month_end]
    if len(spy_n_past) == 0: continue
    n_t0_date = spy_n_past.index[-1]
    
    next_next_month_start = pd.Timestamp((dt+1).end_time)
    next_next_month_end = pd.Timestamp((dt+2).end_time)
    spy_nn_m = spy_px[(spy_px.index >= next_next_month_start) & (spy_px.index <= next_next_month_end)]
    if len(spy_nn_m) < 2: continue
    n_t2_date = spy_nn_m.index[1]
    
    # Fetch returns
    valid = True
    sec_ret_t0 = []
    sec_ret_t2 = []
    exps = []
    
    for sec in MACRO_SECTORS:
        px = daily[sec]['adj_close']
        if not all(d in px.index for d in [t0_date, n_t0_date, t2_date, n_t2_date]):
            valid = False
            break
        
        # Cheating: Enter at T0, Exit at next T0
        sec_ret_t0.append(px.loc[n_t0_date] / px.loc[t0_date] - 1)
        
        # Correct: Enter at T2, Exit at next T2
        sec_ret_t2.append(px.loc[n_t2_date] / px.loc[t2_date] - 1)
        
        exps.append(+1 if sec in SENSITIVE_SECTORS else 0)
        
    if not valid: continue
    
    ry_raw = shocks_df.loc[dt, 'ry_raw']
    scores = np.array(exps) * ry_raw
    
    ic_t0, _ = spearmanr(scores, sec_ret_t0)
    ic_t2, _ = spearmanr(scores, sec_ret_t2)
    
    results.append({
        'date': dt,
        'ic_t0': ic_t0,
        'ic_t2': ic_t2
    })

res_df = pd.DataFrame(results).dropna()

print("="*80)
print("💀 WATERFALL AUTOPSY STEP 1: TIMING LEAKAGE")
print("="*80)

def print_comp(df, label):
    t0_mean = df['ic_t0'].mean()
    t2_mean = df['ic_t2'].mean()
    diff = t0_mean - t2_mean
    print(f"[{label:^8s}] N={len(df):2d} Months")
    print(f"Time-Travel (T+0 Close) Rank IC: {t0_mean:+.3f}")
    print(f"Realistic   (T+2 Close) Rank IC: {t2_mean:+.3f}")
    print(f"Alpha Illusion (Leakage Gap):    {diff:+.3f}\n")

print_comp(res_df, "FULL")

h1 = res_df[res_df['date'] <= pd.Period('2022-12', 'M')]
h2 = res_df[res_df['date'] >= pd.Period('2023-01', 'M')]

print_comp(h1, "H1")
print_comp(h2, "H2")
