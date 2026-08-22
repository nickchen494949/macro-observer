#!/usr/bin/env python3
"""
Dynamic Realized Beta Test
Tests if a rolling 252-day empirical beta to Real Yield outperforms the static theoretical +1/0 basket.
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
spy_ret = spy_px.pct_change()
month_ends = spy_px.index.to_period('M').unique()

# Calculate monthly shocks (using the same Z-score logic as before to be comparable)
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

# Pre-calculate daily aligned data for rolling OLS
# X = -(Δ Real Yield)
aligned_df = pd.DataFrame({'spy': spy_ret, 'ry': ry_daily})
aligned_df = aligned_df.dropna()
aligned_df['X'] = -(aligned_df['ry'].diff())

sec_returns = {sec: daily[sec]['adj_close'].pct_change() for sec in MACRO_SECTORS}

betas_dict = {sec: [] for sec in MACRO_SECTORS}
valid_months = []

for dt in z_df.index:
    end_date = pd.Timestamp(dt.end_time)
    
    # 252 trading days lookback
    past_252 = aligned_df[aligned_df.index <= end_date].tail(252).copy()
    if len(past_252) < 126:
        continue
    
    month_valid = True
    sec_betas = {}
    
    for sec in MACRO_SECTORS:
        # Align sector returns
        past_sec = sec_returns[sec][sec_returns[sec].index.isin(past_252.index)]
        if len(past_sec) < 126:
            month_valid = False
            break
            
        temp = pd.DataFrame({'X': past_252['X'], 'sec': past_sec})
        temp = temp.dropna()
        if len(temp) < 126:
            month_valid = False
            break
            
        temp['Y'] = temp['sec'] - past_252['spy']
        
        # cov(X, Y) / var(X)
        cov = temp['X'].cov(temp['Y'])
        var = temp['X'].var()
        beta = cov / var if var > 0 else 0
        sec_betas[sec] = beta
        
    if month_valid:
        valid_months.append(dt)
        for sec in MACRO_SECTORS:
            betas_dict[sec].append({'date': dt, 'beta': sec_betas[sec]})

# Flatten betas
flat_betas = []
for sec, b_list in betas_dict.items():
    for item in b_list:
        flat_betas.append({'date': item['date'], 'ticker': sec, 'beta': item['beta']})
beta_df = pd.DataFrame(flat_betas).set_index(['date', 'ticker'])

# ── EXECUTION RETURNS (T+2, etc) ──
def get_exec_returns(lag=2):
    exec_rets = []
    for dt in valid_months:
        start_ts = pd.Timestamp(dt.end_time)
        end_ts = pd.Timestamp((dt+1).end_time)
        spy_m_data = spy_px.loc[(spy_px.index >= start_ts) & (spy_px.index <= end_ts)]
        if len(spy_m_data) < lag: continue
        entry_date = spy_m_data.index[lag-1]
        
        next_dt = dt + 1
        n_start_ts = pd.Timestamp(next_dt.end_time)
        n_end_ts = pd.Timestamp((next_dt+1).end_time)
        spy_n_m_data = spy_px.loc[(spy_px.index >= n_start_ts) & (spy_px.index <= n_end_ts)]
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

results = []
for lag in [1, 2, 3]:
    ret_df = get_exec_returns(lag=lag)
    if len(ret_df) == 0: continue
    
    dyn_ics = []
    stat_ics = []
    dyn_t3 = []
    stat_t3 = []
    ew_ret = []
    
    for dt in ret_df['date'].unique():
        m = ret_df[ret_df['date'] == dt].copy()
        if len(m) != 11: continue
        
        ry_z = z_df.loc[dt, 'ry_z']
        
        # Dynamic Signal
        dyn_scores = []
        for sec in m['ticker']:
            b = beta_df.loc[(dt, sec), 'beta']
            dyn_scores.append(b * ry_z)
        
        # Static Signal
        stat_scores = []
        for sec in m['ticker']:
            exps = +1 if sec in SENSITIVE_SECTORS else 0
            stat_scores.append(exps * ry_z)
            
        m['dyn_score'] = dyn_scores
        m['stat_score'] = stat_scores
        
        d_ic, _ = spearmanr(dyn_scores, m['exec_ret'])
        s_ic, _ = spearmanr(stat_scores, m['exec_ret'])
        
        dyn_ics.append(d_ic)
        stat_ics.append(s_ic)
        
        # Top 3 EW
        m_dyn = m.sort_values('dyn_score', ascending=False)
        m_stat = m.sort_values('stat_score', ascending=False)
        
        dyn_t3.append(m_dyn.iloc[:3]['exec_ret'].mean())
        stat_t3.append(m_stat.iloc[:3]['exec_ret'].mean())
        ew_ret.append(m['exec_ret'].mean())
        
        if lag == 2:
            results.append({
                'date': dt,
                'dyn_ic': d_ic,
                'stat_ic': s_ic,
                'dyn_t3': dyn_t3[-1],
                'stat_t3': stat_t3[-1],
                'ew': ew_ret[-1]
            })

    print(f"\n[LAG T+{lag}] Months: {len(ret_df['date'].unique())}")
    print(f"Static Rank IC:  {np.nanmean(stat_ics):+.3f}")
    print(f"Dynamic Rank IC: {np.nanmean(dyn_ics):+.3f}")

res_df = pd.DataFrame(results).dropna()

print("\n" + "="*80)
print("🎯 DYNAMIC REALIZED BETA vs STATIC EXPOSURE (T+2)")
print("="*80)

def print_regime(df, label):
    stat_ic = df['stat_ic'].mean()
    dyn_ic = df['dyn_ic'].mean()
    
    ew = df['ew'].mean()
    stat_t3 = df['stat_t3'].mean()
    dyn_t3 = df['dyn_t3'].mean()
    
    stat_exc = stat_t3 - ew
    dyn_exc = dyn_t3 - ew
    
    print(f"[{label:^8s}] N={len(df):2d} | Rank IC: Static {stat_ic:+.3f} vs Dynamic {dyn_ic:+.3f} | Top3 Excess: Static {stat_exc*100:+.2f}% vs Dynamic {dyn_exc*100:+.2f}%")

print_regime(res_df, "FULL")

h1 = res_df[res_df['date'] <= pd.Period('2022-12', 'M')]
h2 = res_df[res_df['date'] >= pd.Period('2023-01', 'M')]

print("\n--- TIME STABILITY ---")
print_regime(h1, "H1")
print_regime(h2, "H2")
