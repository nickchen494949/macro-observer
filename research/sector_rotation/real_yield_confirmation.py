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
    z_shocks.append({'date': dt, 'ry_z': z['ry_raw']})

z_df = pd.DataFrame(z_shocks).set_index('date').dropna()

def get_exec_returns(lag=2, holding_months=1):
    exec_rets = []
    for dt in z_df.index:
        # Determine entry date
        start_ts = pd.Timestamp(dt.end_time)
        end_ts = pd.Timestamp((dt+1).end_time)
        spy_m_data = spy_daily.loc[(spy_daily.index >= start_ts) & (spy_daily.index <= end_ts)]
        if len(spy_m_data) < lag: continue
        entry_date = spy_m_data.index[lag-1]
        
        # Determine exit date
        next_dt = dt + holding_months
        n_start_ts = pd.Timestamp(next_dt.end_time)
        n_end_ts = pd.Timestamp((next_dt+1).end_time)
        spy_n_m_data = spy_daily.loc[(spy_daily.index >= n_start_ts) & (spy_daily.index <= n_end_ts)]
        if len(spy_n_m_data) < lag: continue
        exit_date = spy_n_m_data.index[lag-1]
        
        # Require 11/11 valid
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

# Run standard T+2, 1M holding
ret_df = get_exec_returns(lag=2, holding_months=1)

results = []
for dt in ret_df['date'].unique():
    m = ret_df[ret_df['date'] == dt]
    if len(m) != 11: continue
    
    sens_ret = m[m['ticker'].isin(SENSITIVE_SECTORS)]['exec_ret'].mean()
    rest_ret = m[m['ticker'].isin(REST_SECTORS)]['exec_ret'].mean()
    group_spread = sens_ret - rest_ret
    
    # 11-sector IC using the old raw exposures
    exps = [+1 if s in SENSITIVE_SECTORS else 0 for s in m['ticker']]
    scores = np.array(exps) * z_df.loc[dt, 'ry_z']
    ic, _ = spearmanr(scores, m['exec_ret'])
    
    results.append({
        'date': dt,
        'ry_z': z_df.loc[dt, 'ry_z'],
        'group_spread': group_spread,
        'ic': ic
    })

res_df = pd.DataFrame(results).dropna()
res_df['ry_z_bucket'] = pd.qcut(res_df['ry_z'], 4, labels=['Large Rise', 'Small Rise', 'Small Drop', 'Large Drop'])

print("="*80)
print("🔍 REAL YIELD SPREAD CONFIRMATION")
print("="*80)

def print_split(df, label):
    ic = df['ic'].mean()
    # Spread IC: correlation between real yield drop shock and the spread
    spread_ic, _ = spearmanr(df['ry_z'], df['group_spread'])
    ann_spread = (1 + df['group_spread']).cumprod().iloc[-1] ** (12 / len(df)) - 1
    win_rate = (df['group_spread'] * df['ry_z'] > 0).mean()
    print(f"[{label:^10s}] Months: {len(df):2d} | 11-sec Rank IC: {ic:+.3f} | Spread IC: {spread_ic:+.3f} | Ann Spread: {ann_spread*100:+.1f}% | Win Rate: {win_rate*100:.1f}%")

print_split(res_df, "FULL")

mid_idx = len(res_df) // 2
h1 = res_df.iloc[:mid_idx]
h2 = res_df.iloc[mid_idx:]

print("\n--- TIME STABILITY ---")
print_split(h1, "H1")
print_split(h2, "H2")

print("\n--- LAG ROBUSTNESS (FULL) ---")
for lag in [1, 2, 3]:
    rdf = get_exec_returns(lag=lag, holding_months=1)
    if len(rdf) == 0: continue
    
    l_ics = []
    l_spreads = []
    l_zs = []
    for dt in rdf['date'].unique():
        m = rdf[rdf['date'] == dt]
        if len(m) != 11: continue
        sens = m[m['ticker'].isin(SENSITIVE_SECTORS)]['exec_ret'].mean()
        rest = m[m['ticker'].isin(REST_SECTORS)]['exec_ret'].mean()
        z = z_df.loc[dt, 'ry_z']
        exps = [+1 if s in SENSITIVE_SECTORS else 0 for s in m['ticker']]
        ic, _ = spearmanr(np.array(exps)*z, m['exec_ret'])
        l_ics.append(ic)
        l_spreads.append(sens - rest)
        l_zs.append(z)
        
    s_ic, _ = spearmanr(l_zs, l_spreads)
    a_sp = (1 + pd.Series(l_spreads)).cumprod().iloc[-1] ** (12 / len(l_spreads)) - 1
    print(f"[T+{lag}] Rank IC: {np.mean(l_ics):+.3f} | Spread IC: {s_ic:+.3f} | Ann Spread: {a_sp*100:+.1f}%")

print("\n--- HOLDING PERIOD (FULL) ---")
for h_months in [1, 3]:
    rdf = get_exec_returns(lag=2, holding_months=h_months)
    if len(rdf) == 0: continue
    
    l_ics = []
    l_spreads = []
    l_zs = []
    for dt in rdf['date'].unique():
        m = rdf[rdf['date'] == dt]
        if len(m) != 11: continue
        sens = m[m['ticker'].isin(SENSITIVE_SECTORS)]['exec_ret'].mean()
        rest = m[m['ticker'].isin(REST_SECTORS)]['exec_ret'].mean()
        z = z_df.loc[dt, 'ry_z']
        exps = [+1 if s in SENSITIVE_SECTORS else 0 for s in m['ticker']]
        ic, _ = spearmanr(np.array(exps)*z, m['exec_ret'])
        l_ics.append(ic)
        l_spreads.append(sens - rest)
        l_zs.append(z)
        
    s_ic, _ = spearmanr(l_zs, l_spreads)
    # Annualize based on months
    a_sp = (1 + pd.Series(l_spreads)).cumprod().iloc[-1] ** (12 / (len(l_spreads)*h_months)) - 1
    print(f"[{h_months}M Hold] Rank IC: {np.mean(l_ics):+.3f} | Spread IC: {s_ic:+.3f} | Ann Spread: {a_sp*100:+.1f}%")

print("\n--- MAGNITUDE DEPENDENCE ---")
bucket_stats = res_df.groupby('ry_z_bucket', observed=False).agg(
    Months=('group_spread', 'count'),
    Avg_Spread=('group_spread', lambda x: np.mean(x)*100),
    Win_Rate=('group_spread', lambda x: np.mean(x > 0)*100)
).reset_index()

# For 'Rise' buckets, the prediction is that spread should be NEGATIVE
# So 'correct direction' is spread < 0
# For 'Drop' buckets, the prediction is spread > 0
for _, r in bucket_stats.iterrows():
    bk = r['ry_z_bucket']
    if 'Rise' in bk:
        # subset df
        sub = res_df[res_df['ry_z_bucket'] == bk]
        wr = np.mean(sub['group_spread'] < 0) * 100
        print(f"{bk:<12s} | N={r['Months']:2d} | Spread: {r['Avg_Spread']:+5.2f}% | Direction Correct (Spread < 0): {wr:5.1f}%")
    else:
        print(f"{bk:<12s} | N={r['Months']:2d} | Spread: {r['Avg_Spread']:+5.2f}% | Direction Correct (Spread > 0): {r['Win_Rate']:5.1f}%")

