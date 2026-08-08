import json
import pandas as pd
import numpy as np
from scipy import stats
import os

print("--- NEAR_EXACT_SPX_AVERAGE_DAILY_RC10_REFERENCE vs VC_V1 Proxy ---")
print("Disclaimer: This validates volatility-control mechanics only, not industry AUM or actual dollar flows.\n")
print("Implementation Note (UNKNOWN Math): We use simple daily returns (pct_change) and standard sample std dev (ddof=1) for both models, as the exact official variance equation remains UNKNOWN.\n")

# 1. Load Data
try:
    with open('../../data/fred/SP500.json', 'r') as f:
        spx_data = json.load(f)['values']
except Exception as e:
    # Try alternate path if running from root
    with open('data/fred/SP500.json', 'r') as f:
        spx_data = json.load(f)['values']

# Sort by date
spx_df = pd.DataFrame(spx_data, columns=['date', 'value'])
spx_df['date'] = pd.to_datetime(spx_df['date'])
spx_df = spx_df.sort_values('date').reset_index(drop=True)

# 2. Calculate Returns and Base Volatilities
spx_df['return'] = spx_df['value'].pct_change()
spx_df['vol20'] = spx_df['return'].rolling(window=20).std(ddof=1) * np.sqrt(252) * 100
spx_df['vol40'] = spx_df['return'].rolling(window=40).std(ddof=1) * np.sqrt(252) * 100
spx_df['vol60'] = spx_df['return'].rolling(window=60).std(ddof=1) * np.sqrt(252) * 100

spx_df = spx_df.dropna(subset=['vol60']).copy()

# ==========================================
# 3. Reference Model: NEAR_EXACT_SPX_AVERAGE_DAILY_RC10
# ==========================================
# Rule: higher of 20d and 40d
spx_df['ref_selected_vol'] = spx_df[['vol20', 'vol40']].max(axis=1)

# Target Exposure (T)
spx_df['ref_target_exp'] = 10.0 / spx_df['ref_selected_vol']

# Effective Exposure (T) is min(Target_Exp_{T-2}, 1.0)
spx_df['ref_effective_exp'] = spx_df['ref_target_exp'].shift(2).clip(upper=1.0)

# Delta Exposure
spx_df['ref_delta_exp'] = spx_df['ref_effective_exp'].diff()

# ==========================================
# 4. Proxy V1 Model: VC V1
# ==========================================
# Rule: 0.65 * 20d + 0.35 * 60d
spx_df['v1_vol'] = 0.65 * spx_df['vol20'] + 0.35 * spx_df['vol60']
spx_df['v1_target_exp'] = (10.0 / spx_df['v1_vol']).clip(lower=0, upper=1.5)

# V1 uses an exponentially weighted moving average (lambda = 0.25)
# actualExposureToday = actualExposureYesterday + (targetExposureToday - actualExposureYesterday) * 0.25
v1_exp = []
prev_exp = spx_df['v1_target_exp'].iloc[0] # Seed
for target in spx_df['v1_target_exp']:
    current_exp = prev_exp + (target - prev_exp) * 0.25
    v1_exp.append(current_exp)
    prev_exp = current_exp

spx_df['v1_effective_exp'] = v1_exp
spx_df['v1_delta_exp'] = spx_df['v1_effective_exp'].diff()

spx_df = spx_df.dropna(subset=['ref_delta_exp', 'v1_delta_exp']).copy()

# ==========================================
# 5. Output Audit Table (Last 10 Dates)
# ==========================================
print("--- Sample Audit Table (Last 10 Dates) ---")
audit_df = spx_df.tail(10).copy()
# Shift dates to show T-2 observation date
audit_df['source_observation_date'] = audit_df['date'].shift(2)

print(f"{'Date (T)':<12} | {'Obs Date(T-2)':<13} | {'20d Vol':<8} | {'40d Vol':<8} | {'Sel Vol':<8} | {'Tgt Exp':<8} | {'Eff Exp':<8} | {'Delta Exp':<8}")
print("-" * 105)
for i in range(2, 10):
    row = audit_df.iloc[i]
    obs_date = audit_df.iloc[i-2]['date'].strftime('%Y-%m-%d')
    print(f"{row['date'].strftime('%Y-%m-%d'):<12} | {obs_date:<13} | {row['vol20']:<8.2f} | {row['vol40']:<8.2f} | {row['ref_selected_vol']:<8.2f} | {row['ref_target_exp']:<8.2f} | {row['ref_effective_exp']:<8.4f} | {row['ref_delta_exp']:<8.4f}")
print("\n")

# ==========================================
# 6. Compare Reference vs V1
# ==========================================
print("--- Comparison Metrics: Reference vs VC V1 ---")

# A. Exposure Level Correlation
level_pearson, _ = stats.pearsonr(spx_df['ref_effective_exp'], spx_df['v1_effective_exp'])
level_spearman, _ = stats.spearmanr(spx_df['ref_effective_exp'], spx_df['v1_effective_exp'])
print(f"Exposure Level Pearson Correlation:  {level_pearson:.4f}")
print(f"Exposure Level Spearman Correlation: {level_spearman:.4f}")

# B. Daily Delta-Exposure Correlation
delta_pearson, _ = stats.pearsonr(spx_df['ref_delta_exp'], spx_df['v1_delta_exp'])
delta_spearman, _ = stats.spearmanr(spx_df['ref_delta_exp'], spx_df['v1_delta_exp'])
print(f"Daily Delta-Exp Pearson Correlation: {delta_pearson:.4f}")
print(f"Daily Delta-Exp Spearman Correlation:{delta_spearman:.4f}")

# C. Buy / Sell / Neutral Direction Agreement
def get_dir(x):
    if x > 0.0005: return 1
    elif x < -0.0005: return -1
    return 0
dir_ref = spx_df['ref_delta_exp'].apply(get_dir)
dir_v1 = spx_df['v1_delta_exp'].apply(get_dir)
dir_agreement = (dir_ref == dir_v1).mean()
print(f"Directional Agreement (Buy/Sell/Neu): {dir_agreement * 100:.2f}%")

# D. Top 5% Absolute Delta-Exposure Event Overlap
q95_ref = spx_df['ref_delta_exp'].abs().quantile(0.95)
q95_v1 = spx_df['v1_delta_exp'].abs().quantile(0.95)

top_ref_idx = spx_df.index[spx_df['ref_delta_exp'].abs() >= q95_ref]
top_v1_idx = spx_df.index[spx_df['v1_delta_exp'].abs() >= q95_v1]
overlap = len(top_ref_idx.intersection(top_v1_idx))
total_top_ref = len(top_ref_idx)
print(f"Top 5% Extreme Event Overlap:        {overlap} / {total_top_ref} ({overlap/total_top_ref*100:.2f}%)")

# E. Lead/Lag Correlation from -5 to +5 sessions
print("\nLead/Lag Delta-Exposure Correlation (Ref vs V1 shifted by Lag):")
# If Lag > 0, we compare Ref[t] with V1[t - lag].
# A positive correlation at lag > 0 means Reference LEADS V1 (V1 reacts to what Reference did earlier).
# A positive correlation at lag < 0 means Reference LAGS V1 (V1 reacts before Reference).
for lag in range(-5, 6):
    shifted_v1 = spx_df['v1_delta_exp'].shift(lag)
    valid_idx = shifted_v1.notna() & spx_df['ref_delta_exp'].notna()
    corr, _ = stats.pearsonr(spx_df.loc[valid_idx, 'ref_delta_exp'], shifted_v1.loc[valid_idx])
    
    if lag < 0:
        label = f"Ref LAGS V1 by {abs(lag)}d"
    elif lag > 0:
        label = f"Ref LEADS V1 by {lag}d"
    else:
        label = f"Concurrent (Lag 0)"
    
    print(f"  {label:<22}: {corr:.4f}")

