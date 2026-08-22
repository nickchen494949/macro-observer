#!/usr/bin/env python3
"""
PREREGISTERED CHALLENGER: Direct EPS Consensus
(Proxy Version until constituent-level data is provided)

Hypothesis: 
  Analyst earnings upgrades -> subsequent sector relative outperformance

Signals:
  1. Revision Magnitude: 1M NTM EPS revision
  2. Revision Breadth: (Up - Down) / Total  [REQUIRES CONSTITUENT DATA - SKIPPED IN PROXY]
  3. Revision Acceleration: 1M revision - prior 3M average revision

Execution:
  T+2 strict implementation, calendar preserved, exactly identical to v8.2 baseline.

Outcomes (NO ML):
  1. Cross-sectional Rank IC
  2. Top3 - EW
  3. Tercile Monotonicity (High vs Mid vs Low)
"""

import os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, load_pe, build_features, calc_metrics, fmt_metrics, SECTORS

# ── 1. Load Strict Aligned Universe ──
daily = load_prices()
pe, pe_cov = load_pe()

# Use 10-sector (no XLE) as the baseline for clean testing
df, _, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=len(SECTORS)-1)
valid_dates = df[df['universe_valid']]['date']
MASTER_START = valid_dates.min().strftime('%Y-%m')

df = df[df['date'] >= pd.Period(MASTER_START, 'M').start_time].copy()

# ── 2. Construct Direct EPS Signals ──
# Until constituent data is injected, we use the ETF-implied proxy

def _ratio(series, periods):
    shifted = series.shift(periods)
    res = series / shifted - 1
    res[series.isna() | shifted.isna() | (shifted.abs() < 1e-9)] = np.nan
    return res

# Calculate raw signals per ticker
signals = []
for t in df['ticker'].unique():
    s = df[df['ticker'] == t].sort_values('date').copy()
    
    # 1. Magnitude: 1M change
    s['eps_mag'] = _ratio(s['fwd_eps'], 1)
    
    # 2. Acceleration: 1M change - prior 3M avg change
    # Prior 3M avg change = (change from T-4 to T-1) / 3
    eps_prev_1 = s['fwd_eps'].shift(1)
    eps_prev_4 = s['fwd_eps'].shift(4)
    prior_3m_avg = (eps_prev_1 / eps_prev_4 - 1) / 3
    prior_3m_avg[eps_prev_1.isna() | eps_prev_4.isna() | (eps_prev_4.abs() < 1e-9)] = np.nan
    
    s['eps_accel'] = s['eps_mag'] - prior_3m_avg
    
    signals.append(s)

df_sig = pd.concat(signals)

# ── 3. Cross-Sectional Ranking ──
results = []
dates = sorted(df_sig['date'].unique())

for dt in dates:
    month_data = df_sig[df_sig['date'] == dt].dropna(subset=['eps_mag', 'eps_accel', 'exec_ret']).copy()
    
    if len(month_data) < 4:
        continue
        
    # We test a simple equal-weight composite of Magnitude & Acceleration ranks
    month_data['rank_mag'] = month_data['eps_mag'].rank()
    month_data['rank_acc'] = month_data['eps_accel'].rank()
    month_data['composite'] = month_data['rank_mag'] + month_data['rank_acc']
    
    month_data = month_data.sort_values('composite', ascending=False)
    
    n_sectors = len(month_data)
    t3 = month_data.head(3)['exec_ret'].mean()
    t1 = month_data.head(1)['exec_ret'].mean()
    b3 = month_data.tail(3)['exec_ret'].mean()
    ew = month_data['exec_ret'].mean()
    
    ic, _ = spearmanr(month_data['composite'], month_data['exec_ret'])
    
    # Terciles
    t_size = n_sectors // 3
    high_t = month_data.iloc[:t_size]['exec_ret'].mean()
    mid_t  = month_data.iloc[t_size:2*t_size]['exec_ret'].mean()
    low_t  = month_data.iloc[2*t_size:]['exec_ret'].mean()
    
    results.append({
        'date': dt,
        'ic': ic,
        'top3': t3,
        'top1': t1,
        'bot3': b3,
        'ew': ew,
        'high_t': high_t,
        'mid_t': mid_t,
        'low_t': low_t
    })

res = pd.DataFrame(results).dropna()

print('=' * 80)
print('📊 DIRECT EPS CONSENSUS (PROXY) - PREREGISTERED TEST')
print('=' * 80)
print(f'Start: {MASTER_START} | Months: {len(res)}')

# ── 4. Primary Outcomes ──
mean_ic = res['ic'].mean()
print(f'\n1. Rank IC: {mean_ic:+.3f}')

cagr_t3 = (1 + res['top3']).cumprod().iloc[-1] ** (12 / len(res)) - 1
cagr_ew = (1 + res['ew']).cumprod().iloc[-1] ** (12 / len(res)) - 1
print(f'2. Top3 vs EW: {cagr_t3*100:+.1f}% vs {cagr_ew*100:+.1f}% (Excess: {(cagr_t3 - cagr_ew)*100:+.1f}%)')

cagr_hi = (1 + res['high_t']).cumprod().iloc[-1] ** (12 / len(res)) - 1
cagr_md = (1 + res['mid_t']).cumprod().iloc[-1] ** (12 / len(res)) - 1
cagr_lo = (1 + res['low_t']).cumprod().iloc[-1] ** (12 / len(res)) - 1

print(f'3. Tercile Monotonicity:')
print(f'   High: {cagr_hi*100:+.1f}%')
print(f'   Mid:  {cagr_md*100:+.1f}%')
print(f'   Low:  {cagr_lo*100:+.1f}%')
print(f'   Is Monotonic? {"✅" if cagr_hi > cagr_md > cagr_lo else "❌"}')

cagr_t1 = (1 + res['top1']).cumprod().iloc[-1] ** (12 / len(res)) - 1
print(f'\nSecondary: Top1 vs EW: {cagr_t1*100:+.1f}% vs {cagr_ew*100:+.1f}% (Excess: {(cagr_t1 - cagr_ew)*100:+.1f}%)')

print('\nTo execute true non-proxy version, supply constituent breadth data.')
