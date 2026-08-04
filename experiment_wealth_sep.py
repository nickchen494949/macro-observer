#!/usr/bin/env python3
"""
🧪 Inflation Forecast Experiment: Wealth Effect & SEP Revisions
   Target: Core PCE 3M annualized, 3 months ahead
   
   Model A: Baseline (8 features)
   Model B: Baseline + Wealth Effect
   Model C: Baseline + SEP Revisions
   Model D: Baseline + Wealth Effect + SEP Revisions
"""

import json
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from scipy import stats

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
FRED_DIR = os.path.join(DATA_DIR, 'fred')
VAL_DIR = os.path.join(DATA_DIR, 'valuation')

HORIZON = 3
MIN_TRAIN = 60

# ============================================
# DATA LOADING
# ============================================
def load_fred(sid):
    fpath = os.path.join(FRED_DIR, f'{sid}.json')
    if not os.path.exists(fpath): return None
    with open(fpath) as f: d = json.load(f)
    vals = d.get('values', [])
    if not vals: return None
    s = pd.Series([v[1] for v in vals], index=pd.to_datetime([v[0] for v in vals]), dtype=float, name=sid)
    return s[~s.index.duplicated(keep='last')].sort_index()

def to_monthly(s):
    if s is None or len(s) == 0: return None
    return s.resample('ME').last().dropna()

def ann3m(s):
    return (s / s.shift(3)).pow(4).subtract(1).multiply(100)

def yoy(s):
    return s.pct_change(12) * 100

def _load_inflation_pca():
    fpath = os.path.join(DATA_DIR, 'factor_model.json')
    if not os.path.exists(fpath): return None
    with open(fpath) as f: fm = json.load(f)
    inf = fm.get('factors', {}).get('inflation', {})
    filtered = inf.get('filtered', [])
    dates = inf.get('dates', [])
    if not filtered or not dates: return None
    s = pd.Series(filtered, index=pd.to_datetime(dates), name='inflation_pca', dtype=float)
    return to_monthly(s)

def _load_sep_revisions():
    fpath = os.path.join(VAL_DIR, 'sep_revisions.json')
    if not os.path.exists(fpath): return None
    with open(fpath) as f:
        d = json.load(f)
    
    dates, pce_rev, rate_rev = [], [], []
    for r in d.get('values', []):
        dates.append(pd.to_datetime(r['date']))
        # Use next year revision if current year is missing, otherwise current year
        pce = r['pce_rev'] if r['pce_rev'] != 0 else r['pce_next_rev']
        pce_rev.append(pce)
        rate_rev.append(r['rate_rev'])
        
    df = pd.DataFrame({'sep_pce_rev': pce_rev, 'sep_rate_rev': rate_rev}, index=dates)
    return df.resample('ME').last()

# ============================================
# BUILD DATASET
# ============================================
def build_dataset():
    pcepilfe = to_monthly(load_fred('PCEPILFE'))
    core_pce_3m = ann3m(pcepilfe)
    target = core_pce_3m.shift(-HORIZON)
    target.name = 'target'

    # --- BASELINE FEATURES ---
    feats_base = {
        'core_pce_3m': core_pce_3m,
        'core_pce_6m': (pcepilfe / pcepilfe.shift(6)).pow(2).subtract(1).multiply(100),
        'ppi_yoy': yoy(to_monthly(load_fred('PPIFIS'))),
        'import_yoy': yoy(to_monthly(load_fred('IR'))),
        'wage_yoy': yoy(to_monthly(load_fred('CES0500000003'))),
        'ulc_yoy': yoy(to_monthly(load_fred('ULCNFB'))),
        'breakeven_10y': to_monthly(load_fred('T10YIE')),
        'inflation_pca': _load_inflation_pca()
    }
    
    # --- WEALTH EFFECT FEATURES ---
    # Lagged 3 months to simulate wealth effect delay
    feats_wealth = {
        'home_price_yoy': yoy(to_monthly(load_fred('CSUSHPINSA'))).shift(3),
        'savings_rate': to_monthly(load_fred('PSAVERT')).shift(3),
        'net_worth_yoy': yoy(to_monthly(load_fred('TNWBSHNO'))).shift(3)
    }

    # --- SEP REVISIONS ---
    sep_df = _load_sep_revisions()
    feats_sep = {
        'sep_pce_rev': sep_df['sep_pce_rev'],
        'sep_rate_rev': sep_df['sep_rate_rev']
    }

    # Combine all
    all_feats = {**feats_base, **feats_wealth, **feats_sep}
    for k, v in all_feats.items():
        v.name = k

    df_features = pd.concat(list(all_feats.values()), axis=1)
    
    # Fill logic: Wealth and SEP are quarterly or irregular, so ffill without limit
    df_features['sep_pce_rev'] = df_features['sep_pce_rev'].fillna(0).rolling(6, min_periods=1).mean() # Smoothing sparse revisions
    df_features['sep_rate_rev'] = df_features['sep_rate_rev'].fillna(0).rolling(6, min_periods=1).mean()
    df_features = df_features.ffill()

    df_all = df_features.copy()
    df_all['target'] = target
    df_train = df_all.dropna()
    
    base_cols = list(feats_base.keys())
    wealth_cols = list(feats_wealth.keys())
    sep_cols = list(feats_sep.keys())

    return df_train, base_cols, wealth_cols, sep_cols

# ============================================
# MODELS
# ============================================
def predict_ar3(train, test_row):
    pce = train['core_pce_3m'].values
    tgt = train['target'].values
    if len(pce) < 24: return test_row['core_pce_3m']
    lag_cols = np.column_stack([pce[2:], pce[1:-1], pce[:-2]])
    tgt_ar = tgt[2:]
    valid = ~np.isnan(tgt_ar) & np.all(np.isfinite(lag_cols), axis=1)
    if valid.sum() < 24: return test_row['core_pce_3m']
    from sklearn.linear_model import LinearRegression
    lr = LinearRegression()
    lr.fit(lag_cols[valid], tgt_ar[valid])
    x = np.array([[test_row['core_pce_3m'], train['core_pce_3m'].iloc[-1], train['core_pce_3m'].iloc[-2]]])
    return lr.predict(x)[0]

def run_ensemble(X_train, y_train, X_test, train_df, test_row):
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train_s, y_train)
    p_ridge = ridge.predict(X_test_s)[0]
    
    rf = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=10, max_features='sqrt', random_state=42, n_jobs=-1)
    rf.fit(X_train_s, y_train)
    p_rf = rf.predict(X_test_s)[0]
    
    p_ar = predict_ar3(train_df, test_row)
    
    return (p_ridge + p_rf + p_ar) / 3.0

# ============================================
# WALK-FORWARD BACKTEST
# ============================================
def walk_forward():
    print('📦 Building dataset...')
    df, base_cols, wealth_cols, sep_cols = build_dataset()
    T = len(df)
    
    configs = {
        'A: Baseline': base_cols,
        'B: + Wealth Effect': base_cols + wealth_cols,
        'C: + SEP Revisions': base_cols + sep_cols,
        'D: + Wealth + SEP': base_cols + wealth_cols + sep_cols
    }
    
    results = {name: [] for name in configs}
    actual = []
    current = []
    
    print(f'🔄 Walk-forward backtest ({T - MIN_TRAIN} months)...')
    for t in range(MIN_TRAIN, T):
        train = df.iloc[:t]
        test_row = df.iloc[t]
        y_actual = test_row['target']
        
        actual.append(y_actual)
        current.append(test_row['core_pce_3m'])
        
        for name, cols in configs.items():
            X_train = train[cols].values
            y_train = train['target'].values
            X_test = test_row[cols].values.reshape(1, -1)
            pred = run_ensemble(X_train, y_train, X_test, train, test_row)
            results[name].append(pred)
            
    # Evaluation
    act = np.array(actual)
    cur = np.array(current)
    act_dir = (act > cur).astype(int)
    
    print('\n' + '=' * 60)
    print('📊 EVALUATION — Walk-Forward Out-of-Sample')
    print('=' * 60)
    
    for name in configs:
        pred = np.array(results[name])
        rmse = np.sqrt(np.mean((act - pred)**2))
        p_dir = (pred > cur).astype(int)
        dir_acc = np.mean(p_dir == act_dir) * 100
        print(f'  {name:20s}  RMSE={rmse:.3f}  Direction={dir_acc:.1f}%')
        
    print('\n── Diebold-Mariano Test (vs Baseline) ──')
    base_err = act - np.array(results['A: Baseline'])
    for name in ['B: + Wealth Effect', 'C: + SEP Revisions', 'D: + Wealth + SEP']:
        test_err = act - np.array(results[name])
        dm_stat, dm_pval = diebold_mariano(base_err, test_err, h=HORIZON)
        sig = '***' if dm_pval < 0.01 else '**' if dm_pval < 0.05 else '*' if dm_pval < 0.1 else 'ns'
        direction = '← New is better' if dm_stat > 0 else '→ Baseline better'
        print(f'  {name:20s} DM={dm_stat:+.3f} p={dm_pval:.4f} {sig} {direction}')

def diebold_mariano(errors1, errors2, h=1):
    d = errors1**2 - errors2**2
    T = len(d)
    d_bar = np.mean(d)
    gamma_0 = np.var(d, ddof=1)
    lrv = gamma_0
    for k in range(1, h):
        gamma_k = np.cov(d[k:], d[:-k])[0, 1]
        lrv += 2 * (1 - k / h) * gamma_k
    lrv = max(lrv, 1e-10)
    dm_stat = d_bar / np.sqrt(lrv / T)
    p_value = 2 * stats.norm.sf(abs(dm_stat))
    return dm_stat, p_value

if __name__ == '__main__':
    walk_forward()
