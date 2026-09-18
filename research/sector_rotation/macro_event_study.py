#!/usr/bin/env python3
"""
Macro Event Study: Reaction Time of Sectors to Real Yield Shocks
Tracks Day 0, Day 1, Day 5, and Day 20 cumulative spread returns after a daily macro shock.
"""

import os, json
import numpy as np
import pandas as pd
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
ry = ry.set_index('date')['value'].dropna()

# Daily real yield changes
ry_diff = ry.diff().dropna()
# Rolling 252-day std dev (shifted by 1 to be past-only)
ry_std = ry_diff.rolling(252).std().shift(1)

# Define shocks: > 1 std dev move in a single day based on PAST 1 YEAR
drop_mask = (ry_diff < -ry_std)
rise_mask = (ry_diff > ry_std)

raw_drop_events = drop_mask[drop_mask].index
raw_rise_events = rise_mask[rise_mask].index

daily = load_prices()
spy_px = daily['SPY']['adj_close']
trading_days = spy_px.index

def decluster_events(dates, min_gap_trading_days=5):
    if len(dates) == 0: return dates
    clean = [dates[0]]
    for dt in dates[1:]:
        if dt not in trading_days or clean[-1] not in trading_days: continue
        loc_curr = trading_days.get_loc(dt)
        loc_prev = trading_days.get_loc(clean[-1])
        if (loc_curr - loc_prev) >= min_gap_trading_days:
            clean.append(dt)
    return pd.DatetimeIndex(clean)

drop_events = decluster_events(raw_drop_events)
rise_events = decluster_events(raw_rise_events)

def get_event_returns(event_dates, label):
    results = []
    
    for dt in event_dates:
        if dt not in trading_days:
            continue
            
        loc = trading_days.get_loc(dt)
        
        # Need enough forward data and past data
        if loc + 20 >= len(trading_days) or loc - 1 < 0:
            continue
            
        t0 = trading_days[loc]
        t_minus_1 = trading_days[loc - 1]
        t1 = trading_days[loc + 1]
        t5 = trading_days[loc + 5]
        t20 = trading_days[loc + 20]
        
        res = {'date': t0, 'ry_diff_0': ry_diff.loc[t0]}
        
        # Calculate what Real Yield did from Day 1 to Day 5 (T+5 value - T0 value)
        res['ry_diff_1_to_5'] = ry_diff.loc[(ry_diff.index > t0) & (ry_diff.index <= t5)].sum()
        
        valid = True
        sec_px = {}
        for sec in MACRO_SECTORS:
            px = daily[sec]['adj_close']
            if not all(d in px.index for d in [t_minus_1, t0, t1, t5, t20]):
                valid = False
                break
            sec_px[sec] = px
            
        if not valid:
            continue
            
        # Calculate returns
        sens_ret_0 = np.mean([sec_px[s].loc[t0]/sec_px[s].loc[t_minus_1] - 1 for s in SENSITIVE_SECTORS])
        rest_ret_0 = np.mean([sec_px[s].loc[t0]/sec_px[s].loc[t_minus_1] - 1 for s in REST_SECTORS])
        res['Day0_Spread'] = sens_ret_0 - rest_ret_0
        
        sens_ret_1 = np.mean([sec_px[s].loc[t1]/sec_px[s].loc[t0] - 1 for s in SENSITIVE_SECTORS])
        rest_ret_1 = np.mean([sec_px[s].loc[t1]/sec_px[s].loc[t0] - 1 for s in REST_SECTORS])
        res['Day1_Spread'] = sens_ret_1 - rest_ret_1
        
        sens_ret_5 = np.mean([sec_px[s].loc[t5]/sec_px[s].loc[t0] - 1 for s in SENSITIVE_SECTORS])
        rest_ret_5 = np.mean([sec_px[s].loc[t5]/sec_px[s].loc[t0] - 1 for s in REST_SECTORS])
        res['Day5_Spread'] = sens_ret_5 - rest_ret_5
        
        sens_ret_20 = np.mean([sec_px[s].loc[t20]/sec_px[s].loc[t0] - 1 for s in SENSITIVE_SECTORS])
        rest_ret_20 = np.mean([sec_px[s].loc[t20]/sec_px[s].loc[t0] - 1 for s in REST_SECTORS])
        res['Day20_Spread'] = sens_ret_20 - rest_ret_20
        
        results.append(res)
        
    return pd.DataFrame(results)

drop_df = get_event_returns(drop_events, "Yield Drop")
rise_df = get_event_returns(rise_events, "Yield Rise")

print("="*80)
print("⏱️  MACRO EVENT STUDY: REACTION TIME TO REAL YIELD SHOCKS")
print("Using Past-252-Day Rolling 1 Std Dev Threshold & 5-Trading-Day Declustering")
print(f"Median Daily Std Dev of Real Yield: {ry_std.median() * 100:.1f} bps")
print("="*80)

def print_study(df, label, expected_dir):
    n = len(df)
    d0 = df['Day0_Spread'].mean() * 10000 # in bps
    d1 = df['Day1_Spread'].mean() * 10000
    d5 = df['Day5_Spread'].mean() * 10000
    d20 = df['Day20_Spread'].mean() * 10000
    
    w0 = np.mean((df['Day0_Spread'] > 0) if expected_dir == '+' else (df['Day0_Spread'] < 0)) * 100
    w1 = np.mean((df['Day1_Spread'] > 0) if expected_dir == '+' else (df['Day1_Spread'] < 0)) * 100
    w5 = np.mean((df['Day5_Spread'] > 0) if expected_dir == '+' else (df['Day5_Spread'] < 0)) * 100
    w20 = np.mean((df['Day20_Spread'] > 0) if expected_dir == '+' else (df['Day20_Spread'] < 0)) * 100
    
    print(f"\n[{label}] N = {n} Events")
    print(f"{'Horizon':<15s} | {'Mean Spread (bps)':>18s} | {'Direction Hit %':>18s}")
    print("-" * 57)
    print(f"{'Day 0 (Shock)':<15s} | {d0:>18.1f} | {w0:>17.1f}%")
    print(f"{'Day 1-1':<15s} | {d1:>18.1f} | {w1:>17.1f}%")
    print(f"{'Day 1-5':<15s} | {d5:>18.1f} | {w5:>17.1f}%")
    print(f"{'Day 1-20':<15s} | {d20:>18.1f} | {w20:>17.1f}%")

print_study(drop_df, "REAL YIELD DROPS (Expected Spread: POSITIVE)", '+')
print_study(rise_df, "REAL YIELD RISES (Expected Spread: NEGATIVE)", '-')

print("\n" + "="*80)
print("🔍 ASYMMETRY CHECK: IS IT DELAYED REACTION OR CONTINUED STIMULUS?")
print("Sub-dividing the 1-5 Day horizon for Yield Drops based on future yield movement.")
print("="*80)

# Group 1: Yield continued to fall (stimulus continued)
drop_cont = drop_df[drop_df['ry_diff_1_to_5'] < 0]
# Group 2: Yield stopped falling or rose (stimulus stopped)
drop_stop = drop_df[drop_df['ry_diff_1_to_5'] >= 0]

def print_subgroup(df, label):
    n = len(df)
    d5 = df['Day5_Spread'].mean() * 10000
    w5 = np.mean(df['Day5_Spread'] > 0) * 100
    print(f"[{label}] N = {n:3d} | Mean Day 1-5 Spread: {d5:>6.1f} bps | Hit Rate: {w5:>4.1f}%")

print_subgroup(drop_cont, "Group 1: Yield Continued to Drop  ")
print_subgroup(drop_stop, "Group 2: Yield Stopped/Reversed   ")


