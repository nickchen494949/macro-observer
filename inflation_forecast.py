#!/usr/bin/env python3
"""
📐 Inflation Forecast Ensemble v3
   Target: Core PCE 3M annualized, 3 months ahead
   Models: AR(3) + Ridge + Random Forest + Equal-Weight Ensemble
   Walk-forward backtest, no look-ahead
"""

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from scipy import stats

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
FRED_DIR = os.path.join(DATA_DIR, 'fred')
OUTPUT_PATH = os.path.join(DATA_DIR, 'inflation_forecast.json')

HORIZON = 3
MIN_TRAIN = 60


# ============================================
# DATA LOADING (same as v2)
# ============================================
def load_fred(sid):
    fpath = os.path.join(FRED_DIR, f'{sid}.json')
    if not os.path.exists(fpath):
        return None
    with open(fpath) as f:
        d = json.load(f)
    vals = d.get('values', [])
    if not vals:
        return None
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
    with open(fpath) as f:
        fm = json.load(f)
    inf = fm.get('factors', {}).get('inflation', {})
    filtered = inf.get('filtered', [])
    dates = inf.get('dates', [])
    if not filtered or not dates: return None
    s = pd.Series(filtered, index=pd.to_datetime(dates), name='inflation_pca', dtype=float)
    return to_monthly(s)


# ============================================
# BUILD DATASET
# ============================================
def build_dataset():
    pcepilfe = to_monthly(load_fred('PCEPILFE'))
    if pcepilfe is None:
        raise ValueError('PCEPILFE not found')

    core_pce_3m = ann3m(pcepilfe)
    target = core_pce_3m.shift(-HORIZON)
    target.name = 'target'

    # Features
    feats = {}
    feats['core_pce_3m'] = core_pce_3m
    feats['core_pce_6m'] = (pcepilfe / pcepilfe.shift(6)).pow(2).subtract(1).multiply(100)

    ppifis = to_monthly(load_fred('PPIFIS'))
    if ppifis is not None: feats['ppi_yoy'] = yoy(ppifis)
    ir = to_monthly(load_fred('IR'))
    if ir is not None: feats['import_yoy'] = yoy(ir)
    wages = to_monthly(load_fred('CES0500000003'))
    if wages is not None: feats['wage_yoy'] = yoy(wages)
    ulc = to_monthly(load_fred('ULCNFB'))
    if ulc is not None: feats['ulc_yoy'] = yoy(ulc)
    t10yie = to_monthly(load_fred('T10YIE'))
    if t10yie is not None: feats['breakeven_10y'] = t10yie
    inf_pca = _load_inflation_pca()
    if inf_pca is not None: feats['inflation_pca'] = inf_pca

    for k, v in feats.items():
        v.name = k

    df_features = pd.concat(list(feats.values()), axis=1)

    # Training: limited ffill
    df_train_feat = df_features.ffill(limit=3)
    df_all = df_train_feat.copy()
    df_all['target'] = target
    df_train = df_all.dropna()

    # Prediction: unlimited ffill, clipped to last PCE date
    df_pred = df_features.ffill()
    last_pce = df_features['core_pce_3m'].dropna().index[-1]
    df_pred = df_pred.loc[:last_pce]
    df_latest = df_pred.dropna().iloc[-1:]

    feat_names = [c for c in df_train.columns if c != 'target']
    print(f'  Training: {len(df_train)} months ({df_train.index[0].strftime("%Y-%m")} ~ {df_train.index[-1].strftime("%Y-%m")})')
    print(f'  Latest: {df_latest.index[0].strftime("%Y-%m")}')
    print(f'  Features ({len(feat_names)}): {feat_names}')

    return df_train, df_latest


# ============================================
# INDIVIDUAL MODEL PREDICTORS
# ============================================
def predict_ar3(train, test_row):
    """AR(3) on core_pce_3m only."""
    pce = train['core_pce_3m'].values
    tgt = train['target'].values
    if len(pce) < 24:
        return test_row['core_pce_3m']
    lag_cols = np.column_stack([pce[2:], pce[1:-1], pce[:-2]])
    tgt_ar = tgt[2:]
    valid = ~np.isnan(tgt_ar) & np.all(np.isfinite(lag_cols), axis=1)
    if valid.sum() < 24:
        return test_row['core_pce_3m']
    from sklearn.linear_model import LinearRegression
    lr = LinearRegression()
    lr.fit(lag_cols[valid], tgt_ar[valid])
    x = np.array([[test_row['core_pce_3m'],
                    train['core_pce_3m'].iloc[-1],
                    train['core_pce_3m'].iloc[-2]]])
    return lr.predict(x)[0]


def predict_ridge(X_train_s, y_train, X_test_s):
    """Ridge regression on all features."""
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train_s, y_train)
    return ridge.predict(X_test_s)[0], ridge


def predict_rf(X_train_s, y_train, X_test_s, seed=42):
    """Random Forest on all features."""
    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=4,
        min_samples_leaf=10,
        max_features='sqrt',
        random_state=seed,
        n_jobs=-1,
    )
    rf.fit(X_train_s, y_train)
    return rf.predict(X_test_s)[0], rf


# ============================================
# WALK-FORWARD BACKTEST
# ============================================
def walk_forward(df):
    feat_cols = [c for c in df.columns if c != 'target']
    T = len(df)

    results = {
        'dates': [],
        'actual': [],
        'nochange': [],
        'ar3': [],
        'ridge': [],
        'rf': [],
        'ensemble': [],
    }

    for t in range(MIN_TRAIN, T):
        train = df.iloc[:t]
        test_row = df.iloc[t]
        y_actual = test_row['target']
        if np.isnan(y_actual):
            continue

        X_train = train[feat_cols].values
        y_train = train['target'].values
        X_test = test_row[feat_cols].values.reshape(1, -1)

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        # Individual models
        pred_nc = test_row['core_pce_3m']
        pred_ar = predict_ar3(train, test_row)
        pred_ridge, _ = predict_ridge(X_train_s, y_train, X_test_s)
        pred_rf, _ = predict_rf(X_train_s, y_train, X_test_s)

        # Equal-weight ensemble
        pred_ens = (pred_ar + pred_ridge + pred_rf) / 3.0

        results['dates'].append(df.index[t].strftime('%Y-%m-%d'))
        results['actual'].append(round(float(y_actual), 4))
        results['nochange'].append(round(float(pred_nc), 4))
        results['ar3'].append(round(float(pred_ar), 4))
        results['ridge'].append(round(float(pred_ridge), 4))
        results['rf'].append(round(float(pred_rf), 4))
        results['ensemble'].append(round(float(pred_ens), 4))

    return results


# ============================================
# EVALUATION
# ============================================
def evaluate(results):
    actual = np.array(results['actual'])
    models = {
        'Ensemble':  np.array(results['ensemble']),
        'Ridge':     np.array(results['ridge']),
        'RF':        np.array(results['rf']),
        'AR(3)':     np.array(results['ar3']),
        'No-Change': np.array(results['nochange']),
    }

    current = np.array(results['nochange'])
    actual_dir = (actual > current).astype(int)

    print('\n' + '=' * 70)
    print(f'📊 EVALUATION — {len(actual)} OOS monthly predictions')
    print('=' * 70)

    metrics = {}
    for name, pred in models.items():
        errors = actual - pred
        rmse = np.sqrt(np.mean(errors**2))
        mae = np.mean(np.abs(errors))
        pred_dir = (pred > current).astype(int)
        dir_acc = np.mean(pred_dir == actual_dir) * 100
        metrics[name] = {'rmse': round(rmse, 4), 'mae': round(mae, 4), 'direction_pct': round(dir_acc, 1)}

    # Print sorted by RMSE
    sorted_models = sorted(metrics.items(), key=lambda x: x[1]['rmse'])
    nc_rmse = metrics['No-Change']['rmse']
    for name, m in sorted_models:
        skill = (1 - m['rmse'] / nc_rmse) * 100
        marker = '👑' if name == sorted_models[0][0] else '  '
        print(f'  {marker} {name:12s}  RMSE={m["rmse"]:.3f}  MAE={m["mae"]:.3f}  Dir={m["direction_pct"]:.1f}%  Skill={skill:+.1f}%')

    # DM tests: ensemble vs each
    print('\n  ── Diebold-Mariano: Ensemble vs each ──')
    ens_errors = actual - models['Ensemble']
    dm_results = {}
    for name in ['No-Change', 'AR(3)', 'Ridge', 'RF']:
        base_errors = actual - models[name]
        dm_stat, dm_pval = diebold_mariano(ens_errors, base_errors, h=HORIZON)
        dm_results[name] = {'statistic': round(dm_stat, 3), 'p_value': round(dm_pval, 4)}
        sig = '***' if dm_pval < 0.01 else '**' if dm_pval < 0.05 else '*' if dm_pval < 0.1 else 'ns'
        direction = '← ens better' if dm_stat < 0 else '→ baseline better'
        print(f'    Ens vs {name:12s}  DM={dm_stat:+.3f}  p={dm_pval:.4f}  {sig}  {direction}')

    # Period breakdown
    dates = pd.to_datetime(results['dates'])
    periods = [
        ('Pre-COVID', dates < '2020-01-01'),
        ('2020-2023', (dates >= '2020-01-01') & (dates < '2023-06-01')),
        ('2023-2026', dates >= '2023-06-01'),
    ]
    print('\n  ── Period Breakdown (RMSE) ──')
    for label, mask in periods:
        n = mask.sum()
        if n < 5: continue
        print(f'  {label} (n={n}):')
        for name, pred in models.items():
            rmse = np.sqrt(np.mean((actual[mask] - pred[mask])**2))
            print(f'    {name:12s} {rmse:.3f}')

    # Non-overlapping quarterly
    q_idx = list(range(0, len(actual), HORIZON))
    if len(q_idx) >= 10:
        print(f'\n  ── Non-Overlapping Quarterly (n={len(q_idx)}) ──')
        for name, pred in models.items():
            rmse_q = np.sqrt(np.mean((actual[q_idx] - pred[q_idx])**2))
            dir_q = np.mean(((pred[q_idx] > current[q_idx]).astype(int)) == ((actual[q_idx] > current[q_idx]).astype(int))) * 100
            print(f'    {name:12s} RMSE={rmse_q:.3f}  Dir={dir_q:.1f}%')

    metrics['dm_tests'] = dm_results
    return metrics


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


# ============================================
# CURRENT PREDICTION
# ============================================
def current_prediction(df_train, df_latest):
    feat_cols = [c for c in df_train.columns if c != 'target']
    X_train = df_train[feat_cols].values
    y_train = df_train['target'].values

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)

    X_latest = df_latest[feat_cols].values
    X_latest_s = scaler.transform(X_latest)

    # Individual predictions
    pred_ar = predict_ar3(df_train, df_latest.iloc[0])
    pred_ridge, ridge_model = predict_ridge(X_train_s, y_train, X_latest_s)
    pred_rf, rf_model = predict_rf(X_train_s, y_train, X_latest_s)

    pred_ens = (pred_ar + pred_ridge + pred_rf) / 3.0

    current_3m = df_latest['core_pce_3m'].iloc[0]
    delta = pred_ens - current_3m
    direction = 'Cooling ↓' if delta < -0.1 else 'Warming ↑' if delta > 0.1 else 'Stable →'

    # Prediction interval from OOS ensemble residuals
    oos_errors = _get_ensemble_oos_errors(df_train, feat_cols)
    residual_std = np.std(oos_errors)
    ci_80 = [pred_ens - 1.28 * residual_std, pred_ens + 1.28 * residual_std]
    ci_95 = [pred_ens - 1.96 * residual_std, pred_ens + 1.96 * residual_std]

    # Feature importance from Ridge + RF
    ridge_imp = {col: round(float(ridge_model.coef_[i]), 4) for i, col in enumerate(feat_cols)}
    rf_imp = {col: round(float(v), 4) for col, v in zip(feat_cols, rf_model.feature_importances_)}

    print(f'\n  ── Current Ensemble Prediction ──')
    print(f'  Data as of:             {df_latest.index[0].strftime("%Y-%m")}')
    print(f'  Core PCE 3M now:        {current_3m:.2f}%')
    print(f'  Individual predictions:')
    print(f'    AR(3):   {pred_ar:.2f}%')
    print(f'    Ridge:   {pred_ridge:.2f}%')
    print(f'    RF:      {pred_rf:.2f}%')
    print(f'  Ensemble (equal wt):    {pred_ens:.2f}%')
    print(f'  Change:                 {delta:+.2f}pp → {direction}')
    print(f'  80% interval:           [{ci_80[0]:.2f}%, {ci_80[1]:.2f}%]')
    print(f'  95% interval:           [{ci_95[0]:.2f}%, {ci_95[1]:.2f}%]')

    return {
        'date': df_latest.index[0].strftime('%Y-%m-%d'),
        'current_pce3m': round(float(current_3m), 3),
        'predictions': {
            'ar3': round(float(pred_ar), 3),
            'ridge': round(float(pred_ridge), 3),
            'rf': round(float(pred_rf), 3),
            'ensemble': round(float(pred_ens), 3),
        },
        'predicted_pce3m_3m': round(float(pred_ens), 3),
        'delta_pp': round(float(delta), 3),
        'direction': direction,
        'ci_80': [round(float(ci_80[0]), 3), round(float(ci_80[1]), 3)],
        'ci_95': [round(float(ci_95[0]), 3), round(float(ci_95[1]), 3)],
        'residual_std': round(float(residual_std), 3),
        'ridge_importance': ridge_imp,
        'rf_importance': rf_imp,
    }


def _get_ensemble_oos_errors(df, feat_cols):
    T = len(df)
    errors = []
    for t in range(MIN_TRAIN, T):
        train = df.iloc[:t]
        test_row = df.iloc[t]
        y_actual = test_row['target']
        if np.isnan(y_actual): continue

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(train[feat_cols].values)
        X_test_s = scaler.transform(test_row[feat_cols].values.reshape(1, -1))

        pred_ar = predict_ar3(train, test_row)
        pred_ridge, _ = predict_ridge(X_train_s, train['target'].values, X_test_s)
        pred_rf, _ = predict_rf(X_train_s, train['target'].values, X_test_s)
        pred_ens = (pred_ar + pred_ridge + pred_rf) / 3.0
        errors.append(y_actual - pred_ens)
    return np.array(errors)


# ============================================
# MAIN
# ============================================
def main():
    print('📐 Inflation Forecast Ensemble v3')
    print('=' * 60)
    print(f'  Target: Core PCE 3M annualized, {HORIZON}M ahead')
    print(f'  Models: AR(3) + Ridge + Random Forest + Equal-Weight Ensemble')
    print(f'  Min training: {MIN_TRAIN} months')
    print()

    print('📦 Building dataset...')
    df_train, df_latest = build_dataset()

    print('\n🔄 Walk-forward backtest...')
    results = walk_forward(df_train)

    metrics = evaluate(results)

    prediction = current_prediction(df_train, df_latest)

    output = {
        'updated': datetime.utcnow().isoformat() + 'Z',
        'version': 'v3-ensemble',
        'target': 'Core PCE 3M annualized',
        'horizon_months': HORIZON,
        'models': ['AR(3)', 'Ridge(α=1)', 'RandomForest(200 trees)', 'EqualWeight Ensemble'],
        'n_features': len([c for c in df_train.columns if c != 'target']),
        'min_training_months': MIN_TRAIN,
        'n_predictions': len(results['actual']),
        'metrics': metrics,
        'prediction': prediction,
        'backtest': results,
    }

    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f'\n💾 Saved to {OUTPUT_PATH}')
    print('✅ Done.')


if __name__ == '__main__':
    main()
