#!/usr/bin/env python3
"""
PREREGISTERED CHALLENGER: Direct EPS Consensus
(Proxy Version until constituent-level data is provided)

Hypothesis: 
  Analyst earnings upgrades -> subsequent sector relative outperformance
"""

import os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, load_pe, build_features, SECTORS

daily = load_prices()
pe, pe_cov = load_pe()

# Use 10-sector (no XLE) as the baseline for clean testing
STRICT_N = len(SECTORS) - 1
df, _, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=STRICT_N)

# Filter for STRICT UNIVERSE ONLY
df = df[df['universe_valid']].copy()
MASTER_START = df['date'].min().strftime('%Y-%m')
df = df[df['date'] >= pd.Period(MASTER_START, 'M').start_time].copy()

def _ratio(series, periods):
    shifted = series.shift(periods)
    res = series / shifted - 1
    res[series.isna() | shifted.isna() | (shifted.abs() < 1e-9)] = np.nan
    return res

signals = []
for t in df['ticker'].unique():
    s = df[df['ticker'] == t].sort_values('date').copy()
    s['eps_mag'] = _ratio(s['fwd_eps'], 1)
    
    eps_prev_1 = s['fwd_eps'].shift(1)
    eps_prev_4 = s['fwd_eps'].shift(4)
    prior_3m_avg = (eps_prev_1 / eps_prev_4 - 1) / 3
    prior_3m_avg[eps_prev_1.isna() | eps_prev_4.isna() | (eps_prev_4.abs() < 1e-9)] = np.nan
    
    s['eps_accel'] = s['eps_mag'] - prior_3m_avg
    signals.append(s)

df_sig = pd.concat(signals)

results = []
dates = sorted(df_sig['date'].unique())

for dt in dates:
    month_data = df_sig[df_sig['date'] == dt].dropna(subset=['eps_mag', 'eps_accel', 'exec_ret']).copy()
    
    # STRICT 10-SECTOR ENFORCEMENT
    if len(month_data) != STRICT_N:
        continue
        
    month_data['rank_mag'] = month_data['eps_mag'].rank()
    month_data['rank_acc'] = month_data['eps_accel'].rank()
    month_data['composite'] = month_data['rank_mag'] + month_data['rank_acc']
    
    month_data = month_data.sort_values('composite', ascending=False)
    
    t3 = month_data.head(3)['exec_ret'].mean()
    t1 = month_data.head(1)['exec_ret'].mean()
    b3 = month_data.tail(3)['exec_ret'].mean()
    ew = month_data['exec_ret'].mean()
    
    ic, _ = spearmanr(month_data['composite'], month_data['exec_ret'])
    
    # Top 3 / Mid 4 / Bottom 3
    high_t = month_data.iloc[:3]['exec_ret'].mean()
    mid_t  = month_data.iloc[3:7]['exec_ret'].mean()
    low_t  = month_data.iloc[7:]['exec_ret'].mean()
    
    results.append({
        'date': dt, 'ic': ic, 'top3': t3, 'top1': t1, 'bot3': b3, 'ew': ew,
        'high_t': high_t, 'mid_t': mid_t, 'low_t': low_t
    })

res = pd.DataFrame(results).dropna()

print('=' * 80)
print('📊 DIRECT EPS CONSENSUS (PROXY) - PREREGISTERED TEST (STRICT 10/10)')
print('=' * 80)
print(f'Start: {MASTER_START} | Months: {len(res)}')

mean_ic = res['ic'].mean()
print(f'\n1. Rank IC: {mean_ic:+.3f}')

cagr_t3 = (1 + res['top3']).cumprod().iloc[-1] ** (12 / len(res)) - 1
cagr_ew = (1 + res['ew']).cumprod().iloc[-1] ** (12 / len(res)) - 1
print(f'2. Top3 vs EW: {cagr_t3*100:+.1f}% vs {cagr_ew*100:+.1f}% (Excess: {(cagr_t3 - cagr_ew)*100:+.1f}%)')

cagr_hi = (1 + res['high_t']).cumprod().iloc[-1] ** (12 / len(res)) - 1
cagr_md = (1 + res['mid_t']).cumprod().iloc[-1] ** (12 / len(res)) - 1
cagr_lo = (1 + res['low_t']).cumprod().iloc[-1] ** (12 / len(res)) - 1

print(f'3. Tercile Monotonicity (3/4/3):')
print(f'   High: {cagr_hi*100:+.1f}%')
print(f'   Mid:  {cagr_md*100:+.1f}%')
print(f'   Low:  {cagr_lo*100:+.1f}%')
print(f'   Is Monotonic? {"✅" if cagr_hi > cagr_md > cagr_lo else "❌"}')

cagr_t1 = (1 + res['top1']).cumprod().iloc[-1] ** (12 / len(res)) - 1
print(f'\nSecondary: Top1 vs EW: {cagr_t1*100:+.1f}% vs {cagr_ew*100:+.1f}% (Excess: {(cagr_t1 - cagr_ew)*100:+.1f}%)')
