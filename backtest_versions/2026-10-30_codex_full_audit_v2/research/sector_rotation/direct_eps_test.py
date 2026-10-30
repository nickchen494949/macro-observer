#!/usr/bin/env python3
"""
INHERITED EXPLORATORY CHALLENGER: ETF-price / sector-PE proxy
(Not direct EPS. Historical index/source vintages remain unverified.)

Hypothesis: 
  Analyst earnings upgrades -> subsequent sector relative outperformance
"""

from audit_scope import require_revised_history
require_revised_history()

import os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, load_pe, build_features, SECTORS, contiguous_cagr

daily = load_prices()
pe, pe_cov = load_pe()

# 1. Start with full raw dataset (lag=2). 
# We DO NOT restrict by the RF strict_universe_n=9 yet, 
# because we only care about eps data!
STRICT_N = len(SECTORS) - 1
df, _, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=STRICT_N)

def _ratio(series, periods):
    shifted = series.shift(periods)
    res = series / shifted - 1
    res[series.isna() | shifted.isna() | (shifted.abs() < 1e-9)] = np.nan
    return res

# 2. Compute magnitude and acceleration over FULL contiguous time series
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

# 3. Create our OWN definition of Universe Validity
# Must have return, magnitude, and acceleration
df_sig['my_valid'] = df_sig['eps_mag'].notna() & df_sig['eps_accel'].notna() & df_sig['exec_ret'].notna()

# Find months that have EXACTLY 10 valid sectors under OUR definition
valid_months = []
for dt in df_sig['date'].unique():
    m = df_sig[df_sig['date'] == dt]
    if m['my_valid'].sum() == STRICT_N:
        valid_months.append(dt)

MASTER_START = min(valid_months).strftime('%Y-%m')
valid_months = [dt for dt in valid_months if dt >= pd.Period(MASTER_START, 'M').start_time]

df_sig = df_sig[df_sig['date'].isin(valid_months)].copy()

# 4. Run the three distinct models
def evaluate_signal(df_eval, sig_col_mag, sig_col_acc, weight_mag, weight_acc, model_name):
    results = []
    dates = sorted(df_eval['date'].unique())
    
    for dt in dates:
        month_data = df_eval[df_eval['date'] == dt].copy()
        
        # Rank features cross-sectionally
        month_data['rank_mag'] = month_data[sig_col_mag].rank()
        month_data['rank_acc'] = month_data[sig_col_acc].rank()
        month_data['composite'] = (month_data['rank_mag'] * weight_mag) + (month_data['rank_acc'] * weight_acc)
        
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
    mean_ic = res['ic'].mean()
    
    # Calculate CAGRs across the ELIGIBLE months
    cagr_t3 = contiguous_cagr(res['top3'], res['date'])
    cagr_t1 = contiguous_cagr(res['top1'], res['date'])
    cagr_ew = contiguous_cagr(res['ew'], res['date'])
    cagr_hi = contiguous_cagr(res['high_t'], res['date'])
    cagr_md = contiguous_cagr(res['mid_t'], res['date'])
    cagr_lo = contiguous_cagr(res['low_t'], res['date'])
    
    print('=' * 80)
    print(f'📊 {model_name.upper()} (STRICT 10/10 - OWN UNIVERSE)')
    print('=' * 80)
    print(f'Start: {MASTER_START} | Eligible Months: {len(res)}')
    print(f'\n1. Rank IC: {mean_ic:+.3f}')
    print(f'2. Top3 vs EW: {cagr_t3*100:+.1f}% vs {cagr_ew*100:+.1f}% (Excess: {(cagr_t3 - cagr_ew)*100:+.1f}%)')
    print(f'3. Tercile Monotonicity (3/4/3):')
    print(f'   High: {cagr_hi*100:+.1f}%')
    print(f'   Mid:  {cagr_md*100:+.1f}%')
    print(f'   Low:  {cagr_lo*100:+.1f}%')
    print(f'   Is Monotonic? {"✅" if cagr_hi > cagr_md > cagr_lo else "❌"}')
    print(f'\nSecondary: Top1 vs EW: {cagr_t1*100:+.1f}% vs {cagr_ew*100:+.1f}% (Excess: {(cagr_t1 - cagr_ew)*100:+.1f}%)')
    print('\n')

evaluate_signal(df_sig, 'eps_mag', 'eps_accel', 1.0, 0.0, "Model A: Magnitude Only")
evaluate_signal(df_sig, 'eps_mag', 'eps_accel', 0.0, 1.0, "Model B: Acceleration Only")
evaluate_signal(df_sig, 'eps_mag', 'eps_accel', 0.5, 0.5, "Model C: 50/50 Composite")
