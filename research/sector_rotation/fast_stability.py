import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from engine import load_prices, load_pe, build_features, SECTORS

daily = load_prices()
pe, pe_cov = load_pe()

STRICT_N = len(SECTORS) - 1
dfs = {}

for lag in [1, 2, 3]:
    df_l, fx, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=lag, strict_universe_n=STRICT_N)
    dfs[lag] = df_l[df_l['universe_valid']].copy()

valid_dates = []
for dt in sorted(dfs[2]['date'].unique()):
    m1 = dfs[1][dfs[1]['date'] == dt].dropna(subset=fx + ['exec_ret'])
    m2 = dfs[2][dfs[2]['date'] == dt].dropna(subset=fx + ['exec_ret'])
    m3 = dfs[3][dfs[3]['date'] == dt].dropna(subset=fx + ['exec_ret'])
    if len(m1) == STRICT_N and len(m2) == STRICT_N and len(m3) == STRICT_N:
        valid_dates.append(dt)

df_main = dfs[2][dfs[2]['date'].isin(valid_dates)].sort_values(['date', 'ticker']).reset_index(drop=True)
df_lag1 = dfs[1][dfs[1]['date'].isin(valid_dates)].sort_values(['date', 'ticker']).reset_index(drop=True)
df_lag3 = dfs[3][dfs[3]['date'].isin(valid_dates)].sort_values(['date', 'ticker']).reset_index(drop=True)

N_PERM = 500
dates = sorted(df_main['date'].unique())
N_DATES = len(dates)

# Pre-extract data into numpy arrays for speed
# Shape: (N_DATES, STRICT_N)
feat_arrays = {f: np.zeros((N_DATES, STRICT_N)) for f in fx}
ret_arrays = np.zeros((N_DATES, STRICT_N))

for i, dt in enumerate(dates):
    m = df_main[df_main['date'] == dt]
    ret_arrays[i] = m['exec_ret'].values
    for f in fx:
        feat_arrays[f][i] = m[f].values

def fast_spearman(x, y):
    # x and y are (N_DATES, STRICT_N)
    # compute spearman per row
    ics = []
    for i in range(N_DATES):
        ic, _ = spearmanr(x[i], y[i])
        ics.append(ic)
    return np.nanmean(ics)

max_abs_ic_null = []
for seed in range(N_PERM):
    rng = np.random.RandomState(seed)
    shuf_ret = np.array([rng.permutation(r) for r in ret_arrays])
    
    feat_ics = []
    for f in fx:
        feat_ics.append(np.abs(fast_spearman(feat_arrays[f], shuf_ret)))
        
    max_abs_ic_null.append(np.max(feat_ics))

max_abs_ic_null = np.array(max_abs_ic_null)

h1_mask = df_main['date'] <= '2022-12-31'
h2_mask = df_main['date'] >= '2023-01-01'

def run_ic_eval(df, f):
    ics = []
    t1_exc = []
    for dt in df['date'].unique():
        m = df[df['date'] == dt]
        ic, _ = spearmanr(m[f], m['exec_ret'])
        ics.append(ic)
        m_s = m.sort_values(f, ascending=False)
        t1 = m_s.head(1)['exec_ret'].mean()
        ew = m['exec_ret'].mean()
        t1_exc.append(t1 - ew)
    return np.nanmean(ics) if len(ics) else np.nan, np.nanmean(t1_exc) if len(t1_exc) else np.nan

results = []
for f in fx:
    ic_h1, t1_h1 = run_ic_eval(df_main[h1_mask], f)
    ic_h2, t1_h2 = run_ic_eval(df_main[h2_mask], f)
    ic_full, t1_full = run_ic_eval(df_main, f)
    
    ic_t1, _ = run_ic_eval(df_lag1, f)
    ic_t3, _ = run_ic_eval(df_lag3, f)
    
    n_extreme = np.sum(max_abs_ic_null >= np.abs(ic_full))
    p_val = (1 + n_extreme) / (N_PERM + 1)
    
    results.append({
        'Feature': f.replace('_xs', ''),
        'IC': ic_full,
        'p-val': p_val,
        'IC_H1': ic_h1,
        'IC_H2': ic_h2,
        'IC_T1': ic_t1,
        'IC_T3': ic_t3,
        'T1_H1_ann': t1_h1 * 12,
        'T1_H2_ann': t1_h2 * 12
    })

res_df = pd.DataFrame(results)
print("\n" + "="*95)
print(f"{'Feature':<18s} {'IC(T2)':>7s} {'p-val':>6s} | {'H1 IC':>7s} {'H2 IC':>7s} | {'T+1 IC':>7s} {'T+3 IC':>7s} | {'T1_H1':>7s} {'T1_H2':>7s}")
print("-" * 95)
for _, r in res_df.sort_values('IC', ascending=False, key=abs).iterrows():
    print(f"{r['Feature']:<18s} {r['IC']:+7.3f} {r['p-val']:6.3f} | {r['IC_H1']:+7.3f} {r['IC_H2']:+7.3f} | {r['IC_T1']:+7.3f} {r['IC_T3']:+7.3f} | {r['T1_H1_ann']*100:+6.1f}% {r['T1_H2_ann']*100:+6.1f}%")
print("="*95)
