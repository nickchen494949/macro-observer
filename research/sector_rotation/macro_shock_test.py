#!/usr/bin/env python3
"""
Macro Shock Sensitivity Test (Preregistered v1)
11 Sectors, strictly predefined directional exposures.
Normalized composite scoring.
Past-only rolling Z-score.
Point-in-Time ALFRED vintage growth.
Fast Max-Stat FWER.
"""

import os, json
import numpy as np
import pandas as pd
from engine import load_prices, SECTORS

MACRO_SECTORS = SECTORS.copy()

# Exposure Matrix v1 (Frozen)
EXPOSURE_MATRIX = {
    'XLK':  [+1,  0,  0,  0, +1],
    'XLC':  [+1,  0,  0,  0,  0],
    'XLY':  [ 0, +1, -1, +1,  0],
    'XLF':  [ 0, +1,  0, +1,  0],
    'XLI':  [ 0, +1,  0, +1, +1],
    'XLU':  [+1, -1,  0, -1,  0],
    'XLE':  [ 0,  0, +1,  0, +1],
    'XLRE': [+1,  0,  0, +1,  0],
    'XLB':  [ 0, +1,  0, +1, +1],
    'XLP':  [ 0, -1,  0, -1,  0],
    'XLV':  [ 0, -1,  0, -1,  0],
}

# L2 Normalize the exposures
norm_exposure = {}
for sec, exps in EXPOSURE_MATRIX.items():
    sq_sum = sum(x**2 for x in exps)
    divisor = np.sqrt(sq_sum) if sq_sum > 0 else 1.0
    norm_exposure[sec] = [x / divisor for x in exps]

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
oil = load_fred_series('DCOILWTICO.json')
dbaa = load_fred_series('DBAA.json')
daaa = load_fred_series('DAAA.json')
usd = load_fred_series('DTWEXBGS.json')

with open(os.path.join(FRED_DIR, 'INDPRO_vintage.json'), 'r') as f:
    indpro_raw = json.load(f)['observations']
indpro_df = pd.DataFrame(indpro_raw)
indpro_df['date'] = pd.to_datetime(indpro_df['date'])
indpro_df['realtime_start'] = pd.to_datetime(indpro_df['realtime_start'])

def get_monthly_series(df):
    df = df.copy()
    df['ym'] = df['date'].dt.to_period('M')
    return df.groupby('ym').last()['value']

ry_m = get_monthly_series(ry)
oil_m = get_monthly_series(oil)
dbaa_m = get_monthly_series(dbaa)
daaa_m = get_monthly_series(daaa)
usd_m = get_monthly_series(usd)

credit_m = dbaa_m - daaa_m

daily = load_prices()
month_ends = daily['SPY'].index.to_period('M').unique()

macro_shocks = []

for me in month_ends:
    pred_date = me.end_time.date()
    
    t0 = me
    t1 = me - 1
    
    if t0 not in ry_m.index or t1 not in ry_m.index: continue
    if t0 not in oil_m.index or t1 not in oil_m.index: continue
    if t0 not in credit_m.index or t1 not in credit_m.index: continue
    if t0 not in usd_m.index or t1 not in usd_m.index: continue
    
    ry_shock = -(ry_m[t0] - ry_m[t1])
    oil_shock = np.log(oil_m[t0] / oil_m[t1]) if oil_m[t1] > 0 else np.nan
    credit_shock = -(credit_m[t0] - credit_m[t1])
    usd_shock = -np.log(usd_m[t0] / usd_m[t1]) if usd_m[t1] > 0 else np.nan
    
    pit_ip = indpro_df[indpro_df['realtime_start'].dt.date <= pred_date].copy()
    if len(pit_ip) == 0: continue
    pit_latest = pit_ip.sort_values('realtime_start').groupby('date').last().reset_index()
    pit_latest = pit_latest.sort_values('date')
    if len(pit_latest) < 2: continue
    
    val_t0 = pit_latest.iloc[-1]['value']
    val_t1 = pit_latest.iloc[-2]['value']
    growth_shock = np.log(val_t0 / val_t1) if val_t1 > 0 else np.nan
    
    macro_shocks.append({
        'date': me,
        'ry_raw': ry_shock,
        'growth_raw': growth_shock,
        'oil_raw': oil_shock,
        'credit_raw': credit_shock,
        'usd_raw': usd_shock
    })

shocks_df = pd.DataFrame(macro_shocks).set_index('date').dropna()

z_shocks = []
for i, dt in enumerate(shocks_df.index):
    past = shocks_df.iloc[max(0, i-60):i]
    if len(past) < 24: continue
    
    curr = shocks_df.iloc[i]
    mean = past.mean()
    std = past.std()
    
    # Avoid division by zero
    std = std.replace(0, np.nan)
    z = (curr - mean) / std
    
    z_shocks.append({
        'date': dt,
        'ry_z': z['ry_raw'],
        'growth_z': z['growth_raw'],
        'oil_z': z['oil_raw'],
        'credit_z': z['credit_raw'],
        'usd_z': z['usd_raw']
    })

z_df = pd.DataFrame(z_shocks).set_index('date').dropna()

# ── SECTOR EXECUTION RETURNS (T+2) ──
exec_rets = []
spy_daily = daily['SPY']['adj_close']
for dt in z_df.index:
    start_ts = pd.Timestamp(dt.end_time)
    end_ts = pd.Timestamp((dt+1).end_time)
    spy_m_data = spy_daily.loc[(spy_daily.index >= start_ts) & (spy_daily.index <= end_ts)]
    if len(spy_m_data) < 2: continue
    # iloc[0] is T+1, iloc[1] is T+2
    entry_date = spy_m_data.index[1]
    
    next_dt = dt + 1
    n_start_ts = pd.Timestamp(next_dt.end_time)
    n_end_ts = pd.Timestamp((next_dt+1).end_time)
    spy_n_m_data = spy_daily.loc[(spy_daily.index >= n_start_ts) & (spy_daily.index <= n_end_ts)]
    if len(spy_n_m_data) < 2: continue
    exit_date = spy_n_m_data.index[1]
    
    # Require ALL 11 sectors to have prices on BOTH entry_date and exit_date
    month_valid = True
    sec_prices = {}
    for sec in MACRO_SECTORS:
        if entry_date not in daily[sec]['adj_close'].index or exit_date not in daily[sec]['adj_close'].index:
            month_valid = False
            break
        sec_prices[sec] = (daily[sec]['adj_close'].loc[entry_date], daily[sec]['adj_close'].loc[exit_date])
    
    if month_valid:
        for sec, (entry_px, exit_px) in sec_prices.items():
            exec_ret = exit_px / entry_px - 1
            exec_rets.append({'date': dt, 'ticker': sec, 'exec_ret': exec_ret})

ret_df = pd.DataFrame(exec_rets)

valid_dates = ret_df.groupby('date').size()
valid_dates = valid_dates[valid_dates == 11].index

results = []
for dt in valid_dates:
    z_row = z_df.loc[dt]
    m_ret = ret_df[ret_df['date'] == dt].copy()
    
    m_ret['ry_score'] = 0.0
    m_ret['growth_score'] = 0.0
    m_ret['oil_score'] = 0.0
    m_ret['credit_score'] = 0.0
    m_ret['usd_score'] = 0.0
    m_ret['composite'] = 0.0
    
    for _, row in m_ret.iterrows():
        sec = row['ticker']
        n_exps = norm_exposure[sec]
        r_exps = EXPOSURE_MATRIX[sec]
        
        # Composite uses Normalized Exposure
        ry_s_n = n_exps[0] * z_row['ry_z']
        gr_s_n = n_exps[1] * z_row['growth_z']
        oi_s_n = n_exps[2] * z_row['oil_z']
        cr_s_n = n_exps[3] * z_row['credit_z']
        us_s_n = n_exps[4] * z_row['usd_z']
        comp = ry_s_n + gr_s_n + oi_s_n + cr_s_n + us_s_n
        
        # Individuals use Raw Exposure
        ry_s = r_exps[0] * z_row['ry_z']
        gr_s = r_exps[1] * z_row['growth_z']
        oi_s = r_exps[2] * z_row['oil_z']
        cr_s = r_exps[3] * z_row['credit_z']
        us_s = r_exps[4] * z_row['usd_z']
        
        m_ret.loc[m_ret['ticker'] == sec, 'ry_score'] = ry_s
        m_ret.loc[m_ret['ticker'] == sec, 'growth_score'] = gr_s
        m_ret.loc[m_ret['ticker'] == sec, 'oil_score'] = oi_s
        m_ret.loc[m_ret['ticker'] == sec, 'credit_score'] = cr_s
        m_ret.loc[m_ret['ticker'] == sec, 'usd_score'] = us_s
        m_ret.loc[m_ret['ticker'] == sec, 'composite'] = comp
        
    results.append(m_ret)

if not results:
    print("No valid months found!")
    sys.exit(0)

final_df = pd.concat(results).sort_values(['date', 'ticker'])

# Fast spearman implementation
def fast_spearman_3d(X, Y):
    # X, Y: (N_DATES, 11)
    # returns mean IC across dates
    X_rank = pd.DataFrame(X).rank(axis=1).values
    Y_rank = pd.DataFrame(Y).rank(axis=1).values
    X_mean = X_rank.mean(axis=1, keepdims=True)
    Y_mean = Y_rank.mean(axis=1, keepdims=True)
    X_diff = X_rank - X_mean
    Y_diff = Y_rank - Y_mean
    cov = np.sum(X_diff * Y_diff, axis=1)
    std_X = np.sqrt(np.sum(X_diff**2, axis=1))
    std_Y = np.sqrt(np.sum(Y_diff**2, axis=1))
    corrs = cov / (std_X * std_Y)
    return np.nanmean(corrs)

def evaluate_score(df, score_col):
    dates_arr = df['date'].unique()
    X = np.zeros((len(dates_arr), 11))
    Y = np.zeros((len(dates_arr), 11))
    
    t3_ret, b3_ret, ew_ret = [], [], []
    t1_exc = []
    hi, mid, lo = [], [], []
    
    for i, dt in enumerate(dates_arr):
        m = df[df['date'] == dt].copy()
        X[i] = m[score_col].values
        Y[i] = m['exec_ret'].values
        
        m = m.sort_values(score_col, ascending=False)
        t1 = m.iloc[0]['exec_ret']
        t3 = m.iloc[:3]['exec_ret'].mean()
        b3 = m.iloc[-3:]['exec_ret'].mean()
        ew = m['exec_ret'].mean()
        
        t1_exc.append(t1 - ew)
        t3_ret.append(t3)
        b3_ret.append(b3)
        ew_ret.append(ew)
        
        hi.append(m.iloc[:4]['exec_ret'].mean())
        mid.append(m.iloc[4:7]['exec_ret'].mean())
        lo.append(m.iloc[7:]['exec_ret'].mean())
        
    mean_ic = fast_spearman_3d(X, Y)
    
    t3_s = pd.Series(t3_ret).fillna(0.0)
    ew_s = pd.Series(ew_ret).fillna(0.0)
    
    n = len(dates_arr)
    c_t3 = (1 + t3_s).cumprod().iloc[-1] ** (12 / n) - 1
    c_ew = (1 + ew_s).cumprod().iloc[-1] ** (12 / n) - 1
    c_t1 = (1 + pd.Series(t1_exc) + pd.Series(ew_ret)).cumprod().iloc[-1] ** (12 / n) - 1
    
    c_hi = (1 + pd.Series(hi)).cumprod().iloc[-1] ** (12 / n) - 1
    c_md = (1 + pd.Series(mid)).cumprod().iloc[-1] ** (12 / n) - 1
    c_lo = (1 + pd.Series(lo)).cumprod().iloc[-1] ** (12 / n) - 1
    
    return mean_ic, c_t3, c_ew, c_t1, c_hi, c_md, c_lo

print("="*80)
print("📊 MACRO SHOCK SENSITIVITY TEST (11 SECTORS)")
print("="*80)
print(f"Eligible Months: {len(valid_dates)}")
print(f"Period: {valid_dates.min()} to {valid_dates.max()}")

comp_ic, comp_t3, comp_ew, comp_t1, comp_hi, comp_md, comp_lo = evaluate_score(final_df, 'composite')
print("\n[PRIMARY] COMPOSITE SCORE:")
print(f"Rank IC: {comp_ic:+.3f}")
print(f"Top3 vs EW: {comp_t3*100:+.1f}% vs {comp_ew*100:+.1f}% (Excess: {(comp_t3-comp_ew)*100:+.1f}%)")
print("Tercile Monotonicity (4/3/4):")
print(f"  High: {comp_hi*100:+.1f}%")
print(f"  Mid:  {comp_md*100:+.1f}%")
print(f"  Low:  {comp_lo*100:+.1f}%")
print(f"  Monotonic? {'✅' if comp_hi > comp_md > comp_lo else '❌'}")
print(f"Top1 Excess: {(comp_t1-comp_ew)*100:+.1f}%")

print("\n[SECONDARY] INDIVIDUAL SHOCKS:")
channels = ['ry_score', 'growth_score', 'oil_score', 'credit_score', 'usd_score']
res = []
for ch in channels:
    ic, t3, ew, t1, _, _, _ = evaluate_score(final_df, ch)
    res.append({'Channel': ch.replace('_score', ''), 'IC': ic, 'Top1_Exc': t1-ew, 'Top3_Exc': t3-ew})

res_df = pd.DataFrame(res)
print(f"{'Channel':<15s} {'IC':>7s} {'Top1_Exc':>10s} {'Top3_Exc':>10s}")
print("-" * 45)
for _, r in res_df.iterrows():
    print(f"{r['Channel']:<15s} {r['IC']:+7.3f} {r['Top1_Exc']*100:+9.1f}% {r['Top3_Exc']*100:+9.1f}%")

print("\nRunning Max-Stat FWER (500 perms)...", flush=True)

N_PERM = 500
dates_arr = final_df['date'].unique()
N_DATES = len(dates_arr)

Y = np.zeros((N_DATES, 11))
X_feat = {c: np.zeros((N_DATES, 11)) for c in channels + ['composite']}
for i, dt in enumerate(dates_arr):
    m = final_df[final_df['date'] == dt]
    Y[i] = m['exec_ret'].values
    for c in channels + ['composite']:
        X_feat[c][i] = m[c].values

max_abs_ic_null = []
comp_ic_null = []
for seed in range(N_PERM):
    rng = np.random.RandomState(seed)
    # Shuffle returns for each date
    shuf_Y = np.array([rng.permutation(r) for r in Y])
    
    # Composite Raw
    comp_ic_null.append(np.abs(fast_spearman_3d(X_feat['composite'], shuf_Y)))
    
    # Individual Max-Stat
    feat_ics = []
    for c in channels:
        feat_ics.append(np.abs(fast_spearman_3d(X_feat[c], shuf_Y)))
    max_abs_ic_null.append(np.max(feat_ics))

comp_ic_null = np.array(comp_ic_null)
max_abs_ic_null = np.array(max_abs_ic_null)

comp_pval = (1 + np.sum(comp_ic_null >= np.abs(comp_ic))) / (N_PERM + 1)
print(f"\nComposite Score Raw p-val: {comp_pval:.3f}")

print("\nIndividual Shocks FWER p-val:")
for c in channels:
    real_ic, _, _, _, _, _, _ = evaluate_score(final_df, c)
    p_val = (1 + np.sum(max_abs_ic_null >= np.abs(real_ic))) / (N_PERM + 1)
    print(f"  {c.replace('_score', ''):<10s} IC: {real_ic:+.3f} | FWER p-val: {p_val:.3f}")
print("\nDone.")
