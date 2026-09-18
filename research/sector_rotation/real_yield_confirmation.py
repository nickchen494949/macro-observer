#!/usr/bin/env python3
"""
Real Yield Confirmation Test
Deep dive into the only signal to survive FWER correction.
"""

import os, json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, SECTORS

MACRO_SECTORS = SECTORS.copy()
SENSITIVE_SECTORS = ['XLK', 'XLC', 'XLU', 'XLRE']
REST_SECTORS = [s for s in MACRO_SECTORS if s not in SENSITIVE_SECTORS]

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

def get_monthly_series(df):
    df = df.copy()
    df['ym'] = df['date'].dt.to_period('M')
    return df.groupby('ym').last()['value']

ry_m = get_monthly_series(ry)

daily = load_prices()
spy_daily = daily['SPY']['adj_close']
month_ends = spy_daily.index.to_period('M').unique()

macro_shocks = []
for me in month_ends:
    t0 = me
    t1 = me - 1
    if t0 not in ry_m.index or t1 not in ry_m.index: continue
    
    # Real Yield Shock: -(t0 - t1) -> drop is positive
    ry_shock = -(ry_m[t0] - ry_m[t1])
    macro_shocks.append({'date': me, 'ry_raw': ry_shock})

shocks_df = pd.DataFrame(macro_shocks).set_index('date').dropna()

z_shocks = []
for i, dt in enumerate(shocks_df.index):
    past = shocks_df.iloc[max(0, i-60):i]
    if len(past) < 24: continue
    
    curr = shocks_df.iloc[i]
    mean = past.mean()
    std = past.std().replace(0, np.nan)
    z = (curr - mean) / std
    z_shocks.append({'date': dt, 'ry_z': z['ry_raw'], 'ry_raw': curr['ry_raw']})

z_df = pd.DataFrame(z_shocks).set_index('date').dropna()

def get_exec_returns(lag=2, holding_months=1):
    exec_rets = []
    for dt in z_df.index:
        start_ts = pd.Timestamp(dt.end_time)
        end_ts = pd.Timestamp((dt+1).end_time)
        spy_m_data = spy_daily.loc[(spy_daily.index >= start_ts) & (spy_daily.index <= end_ts)]
        if len(spy_m_data) < lag: continue
        entry_date = spy_m_data.index[lag-1]
        
        next_dt = dt + holding_months
        n_start_ts = pd.Timestamp(next_dt.end_time)
        n_end_ts = pd.Timestamp((next_dt+1).end_time)
        spy_n_m_data = spy_daily.loc[(spy_daily.index >= n_start_ts) & (spy_daily.index <= n_end_ts)]
        if len(spy_n_m_data) < lag: continue
        exit_date = spy_n_m_data.index[lag-1]
        
        valid = True
        sec_prices = {}
        for sec in MACRO_SECTORS:
            sd = daily[sec]['adj_close']
            if entry_date not in sd.index or exit_date not in sd.index:
                valid = False
                break
            sec_prices[sec] = (sd.loc[entry_date], sd.loc[exit_date])
            
        if valid:
            for sec, (ep, xp) in sec_prices.items():
                exec_rets.append({'date': dt, 'ticker': sec, 'exec_ret': xp/ep - 1})
    return pd.DataFrame(exec_rets)

ret_df = get_exec_returns(lag=2, holding_months=1)

results = []
ret_arrays = []

for dt in ret_df['date'].unique():
    m = ret_df[ret_df['date'] == dt]
    if len(m) != 11: continue
    
    sens_ret = m[m['ticker'].isin(SENSITIVE_SECTORS)]['exec_ret'].mean()
    rest_ret = m[m['ticker'].isin(REST_SECTORS)]['exec_ret'].mean()
    group_spread = sens_ret - rest_ret
    
    exps = [+1 if s in SENSITIVE_SECTORS else 0 for s in m['ticker']]
    scores = np.array(exps) * z_df.loc[dt, 'ry_z']
    ic, _ = spearmanr(scores, m['exec_ret'])
    
    results.append({
        'date': dt,
        'ry_z': z_df.loc[dt, 'ry_z'],
        'ry_raw': z_df.loc[dt, 'ry_raw'],
        'group_spread': group_spread,
        'ic': ic
    })
    
    # Store ordered array for permutation (same order as MACRO_SECTORS)
    m_sorted = m.set_index('ticker').loc[MACRO_SECTORS]
    ret_arrays.append(m_sorted['exec_ret'].values)

res_df = pd.DataFrame(results).dropna()

# Magnitude Buckets using ry_raw
drops = res_df[res_df['ry_raw'] > 0]
rises = res_df[res_df['ry_raw'] <= 0]
res_df['bucket'] = np.nan
res_df.loc[drops.index, 'bucket'] = pd.qcut(drops['ry_raw'], 2, labels=['Small Drop', 'Large Drop'])
res_df.loc[rises.index, 'bucket'] = pd.qcut(rises['ry_raw'], 2, labels=['Large Rise', 'Small Rise'])

print("="*80)
print("🔍 REAL YIELD SPREAD CONFIRMATION")
print("="*80)

def print_split(df, label):
    ic = df['ic'].mean()
    spread_ic, _ = spearmanr(df['ry_raw'], df['group_spread'])
    ann_spread = (1 + df['group_spread']).cumprod().iloc[-1] ** (12 / len(df)) - 1
    win_rate = (df['group_spread'] * df['ry_raw'] > 0).mean()
    print(f"[{label:^10s}] Months: {len(df):2d} | 11-sec Rank IC: {ic:+.3f} | Spread IC: {spread_ic:+.3f} | Ann Spread: {ann_spread*100:+.1f}% | Win Rate (Raw): {win_rate*100:.1f}%")

print_split(res_df, "FULL")

h1 = res_df[res_df['date'] <= pd.Period('2022-12', 'M')]
h2 = res_df[res_df['date'] >= pd.Period('2023-01', 'M')]

print("\n--- TIME STABILITY (FIXED CALENDAR) ---")
print_split(h1, "H1")
print_split(h2, "H2")

print("\n--- LAG ROBUSTNESS (FULL) ---")
for lag in [1, 2, 3]:
    rdf = get_exec_returns(lag=lag, holding_months=1)
    if len(rdf) == 0: continue
    
    l_ics, l_spreads, l_raws = [], [], []
    for dt in rdf['date'].unique():
        m = rdf[rdf['date'] == dt]
        if len(m) != 11: continue
        sens = m[m['ticker'].isin(SENSITIVE_SECTORS)]['exec_ret'].mean()
        rest = m[m['ticker'].isin(REST_SECTORS)]['exec_ret'].mean()
        z = z_df.loc[dt, 'ry_z']
        raw = z_df.loc[dt, 'ry_raw']
        exps = [+1 if s in SENSITIVE_SECTORS else 0 for s in m['ticker']]
        ic, _ = spearmanr(np.array(exps)*z, m['exec_ret'])
        l_ics.append(ic)
        l_spreads.append(sens - rest)
        l_raws.append(raw)
        
    s_ic, _ = spearmanr(l_raws, l_spreads)
    a_sp = (1 + pd.Series(l_spreads)).cumprod().iloc[-1] ** (12 / len(l_spreads)) - 1
    win_rate = np.mean(np.array(l_spreads) * np.array(l_raws) > 0)
    print(f"[T+{lag}] Rank IC: {np.mean(l_ics):+.3f} | Spread IC: {s_ic:+.3f} | Ann Spread: {a_sp*100:+.1f}% | Win Rate: {win_rate*100:.1f}%")

print("\n--- HOLDING PERIOD (FULL) ---")
for h_months in [1, 3]:
    rdf = get_exec_returns(lag=2, holding_months=h_months)
    if len(rdf) == 0: continue
    
    l_ics, l_spreads, l_raws = [], [], []
    for dt in rdf['date'].unique():
        m = rdf[rdf['date'] == dt]
        if len(m) != 11: continue
        sens = m[m['ticker'].isin(SENSITIVE_SECTORS)]['exec_ret'].mean()
        rest = m[m['ticker'].isin(REST_SECTORS)]['exec_ret'].mean()
        z = z_df.loc[dt, 'ry_z']
        raw = z_df.loc[dt, 'ry_raw']
        exps = [+1 if s in SENSITIVE_SECTORS else 0 for s in m['ticker']]
        ic, _ = spearmanr(np.array(exps)*z, m['exec_ret'])
        l_ics.append(ic)
        l_spreads.append(sens - rest)
        l_raws.append(raw)
        
    s_ic, _ = spearmanr(l_raws, l_spreads)
    avg_sp = np.mean(l_spreads)
    win_rate = np.mean(np.array(l_spreads) * np.array(l_raws) > 0)
    
    if h_months == 1:
        a_sp = (1 + pd.Series(l_spreads)).cumprod().iloc[-1] ** (12 / len(l_spreads)) - 1
        print(f"[{h_months}M Hold] Rank IC: {np.mean(l_ics):+.3f} | Spread IC: {s_ic:+.3f} | Ann Compound Spread Stat: {a_sp*100:+.1f}% | Win Rate: {win_rate*100:.1f}%")
    else:
        print(f"[{h_months}M Hold] Rank IC: {np.mean(l_ics):+.3f} | Spread IC: {s_ic:+.3f} | Avg Spread: {avg_sp*100:+.2f}% | Win Rate: {win_rate*100:.1f}%")

print("\n--- MAGNITUDE DEPENDENCE ---")
bucket_stats = res_df.groupby('bucket', observed=False).agg(
    Months=('group_spread', 'count'),
    Avg_Spread=('group_spread', lambda x: np.mean(x)*100),
).reset_index()

for _, r in bucket_stats.iterrows():
    bk = r['bucket']
    if pd.isna(bk): continue
    sub = res_df[res_df['bucket'] == bk]
    if 'Rise' in bk:
        wr = np.mean(sub['group_spread'] < 0) * 100
        print(f"{bk:<12s} | N={r['Months']:2d} | Spread: {r['Avg_Spread']:+5.2f}% | Direction Correct (Spread < 0): {wr:5.1f}%")
    else:
        wr = np.mean(sub['group_spread'] > 0) * 100
        print(f"{bk:<12s} | N={r['Months']:2d} | Spread: {r['Avg_Spread']:+5.2f}% | Direction Correct (Spread > 0): {wr:5.1f}%")

print("\n--- EXACT TEST: 330 FIXED 4-SECTOR BASKETS ---")
import itertools
all_baskets = list(itertools.combinations(MACRO_SECTORS, 4))
null_spread_ics_exact = []
real_spread_ic, _ = spearmanr(res_df['ry_raw'], res_df['group_spread'])

for basket in all_baskets:
    l_spreads = []
    for m_sorted_rets in ret_arrays:
        sens_r = np.mean([m_sorted_rets[MACRO_SECTORS.index(s)] for s in basket])
        rest_r = np.mean([m_sorted_rets[MACRO_SECTORS.index(s)] for s in MACRO_SECTORS if s not in basket])
        l_spreads.append(sens_r - rest_r)
    s_ic, _ = spearmanr(res_df['ry_raw'], l_spreads)
    null_spread_ics_exact.append(s_ic)

p_val_exact = (1 + np.sum(np.abs(null_spread_ics_exact) >= np.abs(real_spread_ic))) / (len(all_baskets) + 1)
rank_exact = np.sum(np.abs(null_spread_ics_exact) >= np.abs(real_spread_ic)) + 1
print(f"Spread IC p-value (exact): {p_val_exact:.4f} | Real Rank: {rank_exact} / {len(all_baskets)+1}")

print("\n--- TIME-SHIFT TEST ---")
null_spread_ics_time = []
shifts = list(range(1, len(res_df)))
for shift in shifts:
    shifted_raw = np.roll(res_df['ry_raw'].values, shift)
    s_ic, _ = spearmanr(shifted_raw, res_df['group_spread'])
    null_spread_ics_time.append(s_ic)

p_val_time = (1 + np.sum(np.abs(null_spread_ics_time) >= np.abs(real_spread_ic))) / (len(shifts) + 1)
rank_time = np.sum(np.abs(null_spread_ics_time) >= np.abs(real_spread_ic)) + 1
print(f"Spread IC p-value (time-shift): {p_val_time:.4f} | Real Rank: {rank_time} / {len(shifts)+1}")

