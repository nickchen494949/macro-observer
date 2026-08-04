#!/usr/bin/env python3
"""
📐 Three-Factor PCA Shadow Model
   Growth / Inflation / Credit

Shadow model — runs alongside rule engine, never touches traffic lights.

Architecture:
  1. Load FRED data → align to monthly frequency
  2. Apply transforms (YoY, MoM, etc.)
  3. Standardize using EXPANDING WINDOW (no look-ahead)
  4. PCA extracts first principal component per group
  5. EWM smoothing (span=3) for noise reduction
  6. Trend state classification based on level + momentum
  7. Output: factor_model.json consumed by server.js

NOTE: PCA loadings are estimated on the full sample.
  True real-time would require rolling PCA, which is a future upgrade.
  Standardization is expanding-window, so z-scores are look-ahead-free.
"""

import json
import os
import sys
import warnings
import numpy as np
import pandas as pd
from datetime import datetime

warnings.filterwarnings('ignore')

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
FRED_DIR = os.path.join(DATA_DIR, 'fred')
OUTPUT_PATH = os.path.join(DATA_DIR, 'factor_model.json')

# ============================================
# INDICATOR GROUPS
# ============================================
# Each entry: (series_id, transform, label, sign)
#   sign: +1 = higher is "more of this factor", -1 = inverted
#   For Growth: +1 = stronger growth
#   For Inflation: +1 = higher inflation
#   For Credit: +1 = tighter/more stressed

GROWTH_INDICATORS = [
    ('INDPRO',              'yoy',     'Industrial Production YoY',    +1),
    ('PAYEMS',              'mom_abs', 'Nonfarm Payrolls MoM',         +1),
    ('USPRIV',              'mom_abs', 'Private Payrolls MoM',         +1),
    ('ICSA',                'raw',     'Initial Claims',               -1),  # higher = weaker
    ('AWHMAN',              'raw',     'Mfg Avg Weekly Hours',         +1),
    ('DPCERAM1M225NBEA',    'raw',     'Real PCE MoM%',                +1),
    ('UMCSENT',             'raw',     'Consumer Sentiment',           +1),
    ('NEWORDER',            'yoy',     'Core Capex Orders YoY',        +1),
    ('UNRATE',              'raw',     'Unemployment Rate',            -1),  # higher = weaker
    ('SAHMREALTIME',        'raw',     'Sahm Rule',                    -1),  # higher = weaker
    ('MARTSMPCSM44X72USS',  'mom_pct', 'Retail Sales Control MoM%',    +1),
    ('TEMPHELPS',           'yoy',     'Temp Help Services YoY',       +1),
    ('JTSQUR',              'raw',     'Quits Rate',                   +1),
]

INFLATION_INDICATORS = [
    ('PCEPILFE',            'yoy',     'Core PCE YoY',                 +1),
    ('PCEPI',               'yoy',     'Headline PCE YoY',             +1),
    ('CES0500000003',       'yoy',     'Avg Hourly Earnings YoY',      +1),
    ('CUSR0000SAH1',        'yoy',     'CPI Housing YoY',              +1),
    ('CUSR0000SACL1E',      'yoy',     'CPI Core Goods YoY',           +1),
    ('IR',                  'yoy',     'Import Prices YoY',            +1),
    ('PPIFIS',              'yoy',     'PPI Final Demand YoY',         +1),
    ('T10YIE',              'raw_m',   '10Y Breakeven',                +1),
    ('T5YIFR',              'raw_m',   '5Y5Y Forward',                 +1),
    ('MEDCPIM159SFRBCLE',   'raw',     'Median CPI YoY',               +1),
    ('TRMMEANCPIM159SFRBCLE','raw',    '16% Trimmed CPI YoY',          +1),
    ('ULCNFB',              'yoy',     'Unit Labor Cost YoY',          +1),
]

CREDIT_INDICATORS = [
    ('BAMLH0A0HYM2',       'raw_m',   'HY OAS',                       +1),  # higher = tighter
    ('BAMLC0A0CM',          'raw_m',   'IG OAS',                       +1),
    ('NFCI',                'raw_w',   'Chicago Fed NFCI',             +1),  # higher = tighter
    ('DRTSCILM',            'raw',     'SLOOS C&I Standards',          +1),  # higher = tighter
    ('DRTSCIS',             'raw',     'SLOOS Small Biz Standards',    +1),
    ('DRSDCILM',            'raw',     'SLOOS C&I Demand',             -1),  # lower = weaker demand
    ('BUSLOANS',            'yoy',     'C&I Loans YoY',                -1),  # lower = tighter
    ('CONSUMER',            'yoy',     'Consumer Loans YoY',           -1),
    ('DRCCLACBS',           'raw',     'CC Delinquency Rate',          +1),  # higher = stress
    ('DRSFRMACBS',          'raw',     'Mortgage Delinquency Rate',    +1),
    ('CORCCACBS',           'raw',     'Charge-Off Rate',              +1),
]

# ============================================
# DATA LOADING
# ============================================
def load_fred_series(series_id):
    fpath = os.path.join(FRED_DIR, f'{series_id}.json')
    if not os.path.exists(fpath):
        return None
    with open(fpath) as f:
        d = json.load(f)
    vals = d.get('values', [])
    if not vals:
        return None
    dates = [v[0] for v in vals]
    values = [v[1] for v in vals]
    s = pd.Series(values, index=pd.to_datetime(dates), name=series_id, dtype=float)
    s = s[~s.index.duplicated(keep='last')]
    return s.sort_index()


def to_monthly(s, method='last'):
    """Resample any frequency series to month-end."""
    if s is None or len(s) == 0:
        return None
    return s.resample('ME').last().dropna()


def apply_transform(s, transform):
    """Apply the specified transform to a monthly series."""
    if s is None:
        return None
    if transform == 'yoy':
        return s.pct_change(12) * 100
    elif transform == 'mom_abs':
        return s.diff(1)
    elif transform == 'mom_pct':
        return s.pct_change(1) * 100
    elif transform in ('raw', 'raw_m', 'raw_w'):
        return s  # already in the right form
    return s


# ============================================
# FACTOR ESTIMATION
# ============================================
def estimate_factor(indicators, factor_name, min_start='2006-01-01', min_warmup=36, verbose=True):
    """
    Fully expanding PCA — NO look-ahead at any stage.

    At each month t:
      1. Standardize using mean/std of data[0:t] only
      2. Fit PCA on data[0:t] only → get loadings at time t
      3. Project data[t] onto PC1 → factor score at time t

    The factor score at time t uses ONLY information available at t.
    PCA loadings evolve over time (they stabilize after ~60 months).
    EWM smoothing is causal (forward-only).
    """
    from sklearn.decomposition import PCA as skPCA

    series_list = []
    names = []

    for (sid, transform, label, sign) in indicators:
        raw = load_fred_series(sid)
        if raw is None:
            if verbose:
                print(f'  ⚠️  {sid}: not found, skipping')
            continue
        monthly = to_monthly(raw)
        if monthly is None or len(monthly) < 36:
            if verbose:
                print(f'  ⚠️  {sid}: too short ({len(monthly) if monthly is not None else 0} obs), skipping')
            continue
        transformed = apply_transform(monthly, transform)
        if transformed is None:
            continue
        transformed = transformed.dropna()
        if len(transformed) < 36:
            if verbose:
                print(f'  ⚠️  {sid}: too short after transform ({len(transformed)}), skipping')
            continue
        # Apply sign convention
        transformed = transformed * sign
        series_list.append(transformed)
        names.append(label)

    if len(series_list) < 3:
        print(f'  ❌ {factor_name}: fewer than 3 usable series, cannot estimate')
        return None

    # Build panel
    panel = pd.concat(series_list, axis=1)
    panel.columns = names
    panel = panel[panel.index >= min_start]

    # Forward-fill gaps up to 3 months (for quarterly data like SLOOS)
    panel = panel.ffill(limit=3)

    # Drop rows where too many values are missing
    panel = panel.dropna(thresh=max(3, len(names) // 2))

    if len(panel) < min_warmup + 12:
        print(f'  ❌ {factor_name}: insufficient data ({len(panel)} rows, need {min_warmup + 12})')
        return None

    if verbose:
        print(f'  📊 {factor_name}: {len(names)} series, {len(panel)} months ({panel.index[0].strftime("%Y-%m")} ~ {panel.index[-1].strftime("%Y-%m")})')

    # ── Fully expanding PCA ──
    T = len(panel)
    scores_raw = np.full(T, np.nan)
    loadings_history = []  # save loadings at each step for diagnostics
    var_explained_history = []

    for t in range(min_warmup, T):
        # Data available at time t: panel.iloc[0:t+1]
        window = panel.iloc[:t+1]

        # 1. Expanding standardization: mean/std from window only
        mean_t = window.mean()
        std_t = window.std()
        std_t[std_t == 0] = 1.0
        z_window = (window - mean_t) / std_t

        # Clean
        z_window = z_window.clip(-10, 10)
        z_window = z_window.replace([np.inf, -np.inf], np.nan)
        z_window = z_window.fillna(0)

        # 2. PCA on window — loadings estimated from data[:t] only
        try:
            pca = skPCA(n_components=1)
            pca.fit(z_window.values)
            # 3. Project current month onto PC1
            z_current = z_window.iloc[-1:].values
            score = pca.transform(z_current)[0, 0]
            scores_raw[t] = float(score)
            loadings_history.append({col: round(float(l), 4) for col, l in zip(names, pca.components_[0])})
            var_explained_history.append(round(float(pca.explained_variance_ratio_[0]), 4))
        except Exception as e:
            if verbose and t == T - 1:
                print(f'  ⚠️  PCA failed at t={t}: {e}')
            scores_raw[t] = np.nan
            loadings_history.append({})
            var_explained_history.append(None)

    # EWM smoothing (causal — forward only, never uses future data)
    scores_series = pd.Series(scores_raw, index=panel.index)
    smoothed_series = scores_series.ewm(span=3, adjust=False).mean()

    # Build output
    # Only include dates from warmup onward (before that, no estimates)
    valid_mask = ~np.isnan(scores_raw)
    dates_all = panel.index.strftime('%Y-%m-%d').tolist()

    latest_loadings = loadings_history[-1] if loadings_history else {}
    latest_var_exp = var_explained_history[-1] if var_explained_history else None

    result = {
        'name': factor_name,
        'method': 'Expanding PCA(k=1) + EWM(span=3)',
        'n_series': len(names),
        'series_used': names,
        'dates': dates_all,
        'filtered': [round(float(x), 4) if np.isfinite(x) else None for x in scores_raw],
        'smoothed': [round(float(x), 4) if np.isfinite(x) else None for x in smoothed_series.values],
        'filtered_se': [None] * T,  # PCA doesn't produce standard errors
        'loadings': latest_loadings,
        'variance_explained': latest_var_exp,
        'warmup_months': min_warmup,
        'loading_stability': _loading_stability(loadings_history, names),
    }

    if verbose:
        latest = scores_raw[-1]
        latest_sm = smoothed_series.iloc[-1]
        ve = latest_var_exp or 0
        print(f'    Expanding PCA variance explained (latest): {ve:.1%}')
        print(f'    Latest: {latest:.3f} (smoothed: {latest_sm:.3f})')
        ls = result.get('loading_stability', {})
        if ls:
            stable = sum(1 for v in ls.values() if v and v < 0.1)
            total = len(ls)
            print(f'    Loading stability: {stable}/{total} series have <0.1 std over last 24m')

    return result


def _loading_stability(loadings_history, names):
    """
    Measure how much PCA loadings have changed over the last 24 months.
    Lower = more stable = more trustworthy.
    Returns dict: {series_name: std of loading over last 24 months}
    """
    if len(loadings_history) < 24:
        return {}
    recent = loadings_history[-24:]
    stability = {}
    for name in names:
        vals = [l.get(name, np.nan) for l in recent]
        vals = [v for v in vals if v is not None and np.isfinite(v)]
        if len(vals) >= 12:
            stability[name] = round(float(np.std(vals)), 4)
    return stability


# ============================================
# REGIME DETECTION
# ============================================
def detect_trend_state(factor_values, dates):
    """
    Trend state classification based on factor level + momentum.
    NOT a statistical regime (no Markov switching). Returns labels for each date.
    """
    if factor_values is None or len(factor_values) < 6:
        return None
    
    s = pd.Series(factor_values, index=pd.to_datetime(dates), dtype=float)
    s = s.ffill().bfill()  # fill gaps, don't drop — keep alignment
    
    # 3-month momentum
    momentum = s.diff(3)
    
    regimes = []
    for i in range(len(s)):
        level = s.iloc[i]
        mom = momentum.iloc[i] if i >= 3 and pd.notna(momentum.iloc[i]) else 0
        
        if pd.isna(level):
            regimes.append('unknown')
        elif level > 1.0:
            regimes.append('elevated' if mom >= 0 else 'peaking')
        elif level > 0.3:
            regimes.append('rising' if mom > 0.1 else 'moderate')
        elif level > -0.3:
            regimes.append('neutral')
        elif level > -1.0:
            regimes.append('easing' if mom < -0.1 else 'low')
        else:
            regimes.append('depressed' if mom <= 0 else 'bottoming')
    
    return regimes


# ============================================
# AGREEMENT SCORING
# ============================================
def compute_agreement(factor_result, factor_type):
    """
    Compare factor regime with what the rule engine would say.
    factor_type: 'growth' (inverted: high = good), 'inflation', 'credit'
    """
    if factor_result is None:
        return None
    
    filtered = factor_result['filtered']
    if not filtered or filtered[-1] is None:
        return None
    
    latest = filtered[-1]
    
    # For growth: factor is positive = strong growth = rule engine should be green
    # For inflation: factor positive = high inflation = rule engine should be red
    # For credit: factor positive = tight credit = rule engine should be red
    
    if factor_type == 'growth':
        if latest < -1.0:
            return {'factor_signal': 'contraction', 'expected_rule': 'red', 'factor_value': latest}
        elif latest < -0.3:
            return {'factor_signal': 'slowing', 'expected_rule': 'yellow', 'factor_value': latest}
        elif latest > 0.3:
            return {'factor_signal': 'expansion', 'expected_rule': 'green', 'factor_value': latest}
        else:
            return {'factor_signal': 'neutral', 'expected_rule': 'green', 'factor_value': latest}
    elif factor_type == 'inflation':
        if latest > 1.0:
            return {'factor_signal': 'high_inflation', 'expected_rule': 'red', 'factor_value': latest}
        elif latest > 0.3:
            return {'factor_signal': 'rising', 'expected_rule': 'yellow', 'factor_value': latest}
        elif latest < -0.3:
            return {'factor_signal': 'disinflationary', 'expected_rule': 'green', 'factor_value': latest}
        else:
            return {'factor_signal': 'neutral', 'expected_rule': 'yellow', 'factor_value': latest}
    else:  # credit
        if latest > 1.0:
            return {'factor_signal': 'tight', 'expected_rule': 'red', 'factor_value': latest}
        elif latest > 0.3:
            return {'factor_signal': 'tightening', 'expected_rule': 'yellow', 'factor_value': latest}
        elif latest < -0.3:
            return {'factor_signal': 'easy', 'expected_rule': 'green', 'factor_value': latest}
        else:
            return {'factor_signal': 'neutral', 'expected_rule': 'green', 'factor_value': latest}


# ============================================
# MAIN
# ============================================
def main():
    print('📐 Three-Factor PCA Shadow Model')
    print('=' * 60)
    
    results = {
        'updated': datetime.utcnow().isoformat() + 'Z',
        'model': 'Expanding PCA(k=1) + causal EWM × 3 factors',
        'version': 'v0.3',
        'note': 'Shadow model — informational only, does not alter diagnostic lights or signals. No full-sample look-ahead in standardization or PCA loadings.',
        'factors': {},
        'agreement': {},
    }
    
    # Estimate each factor
    print('\n📈 GROWTH FACTOR')
    growth = estimate_factor(GROWTH_INDICATORS, 'Growth', verbose=True)
    if growth:
        growth['trend_states'] = detect_trend_state(growth['filtered'], growth['dates'])
        results['factors']['growth'] = growth
        results['agreement']['growth'] = compute_agreement(growth, 'growth')
    
    print('\n🔥 INFLATION FACTOR')
    inflation = estimate_factor(INFLATION_INDICATORS, 'Inflation', verbose=True)
    if inflation:
        inflation['trend_states'] = detect_trend_state(inflation['filtered'], inflation['dates'])
        results['factors']['inflation'] = inflation
        results['agreement']['inflation'] = compute_agreement(inflation, 'inflation')
    
    print('\n💳 CREDIT FACTOR')
    credit = estimate_factor(CREDIT_INDICATORS, 'Credit', verbose=True)
    if credit:
        credit['trend_states'] = detect_trend_state(credit['filtered'], credit['dates'])
        results['factors']['credit'] = credit
        results['agreement']['credit'] = compute_agreement(credit, 'credit')
    
    # Summary
    print('\n' + '=' * 60)
    print('📊 SUMMARY')
    print('=' * 60)
    
    for name, factor in results['factors'].items():
        f = factor['filtered']
        latest = f[-1] if f else None
        trend = factor['trend_states'][-1] if factor.get('trend_states') else '?'
        method = factor.get('method', '?')
        n = factor.get('n_series', 0)
        print(f'  {name:12s}: {latest:+.3f}  trend={trend:12s}  ({method}, {n} series)')
    
    print('\n  Agreement with rule engine:')
    for name, ag in results['agreement'].items():
        if ag:
            print(f'    {name:12s}: factor says "{ag["factor_signal"]}" → expect rule {ag["expected_rule"]}')
    
    # Save
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f'\n💾 Saved to {OUTPUT_PATH}')
    print('✅ Done.')


if __name__ == '__main__':
    main()
