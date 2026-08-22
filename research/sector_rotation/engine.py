#!/usr/bin/env python3
"""
Sector Rotation Engine — Shared data + backtest infrastructure.

All bugs from code review fixed:
  1. Split-adjusted prices via yfinance (not raw Yahoo close)
  2. pct_change replaced with explicit ratio to avoid NaN forward-fill
  3. Next-trading-day execution via daily prices
  4. Purged walk-forward with proper label-end embargo
  5. Cross-sectional placebo (shuffle within each month)
  6. Proper group permutation (same row permutation for all features)
"""

import os, json, warnings, hashlib
import pandas as pd, numpy as np
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════
_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(_DIR, '..', '..'))
PE_DIR = os.path.join(_DIR, 'pe_data')
ADJ_CACHE = os.path.join(_DIR, 'adj_prices')

SECTORS = ['XLK', 'XLC', 'XLY', 'XLF', 'XLI', 'XLU', 'XLE', 'XLRE', 'XLB', 'XLP', 'XLV']
BENCHMARKS = ['SPY', 'QQQ', 'TLT']
ALL_TICKERS = SECTORS + BENCHMARKS

PE_MAP = {
    '20517_information_technology.csv': 'XLK',
    '20518_communication_services.csv': 'XLC',
    '20519_consumer_discretionary.csv': 'XLY',
    '20520_financials.csv': 'XLF',
    '20521_industrials.csv': 'XLI',
    '20522_utilities.csv': 'XLU',
    '20523_energy.csv': 'XLE',
    '20524_real_estate.csv': 'XLRE',
    '20525_materials.csv': 'XLB',
    '20526_consumer_staples.csv': 'XLP',
    '20527_health_care.csv': 'XLV',
}

NAMES = {
    'XLK': 'Tech', 'XLC': 'Comm', 'XLY': 'Disc', 'XLF': 'Fin', 'XLI': 'Ind',
    'XLU': 'Util', 'XLE': 'Enrg', 'XLRE': 'RE', 'XLB': 'Mat', 'XLP': 'Stpl',
    'XLV': 'Hlth',
}

FEAT_COLS = [
    'f_valuation', 'f_eps_rev', 'f_eps_rev_1m',
    'f_mom6', 'f_mom3', 'f_mom1',
    'f_pe_level', 'f_pe_chg3', 'f_dist_high6',
]


# ══════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════

def load_adjusted_prices(tickers=None, start='2002-01-01', end='2026-09-01',
                         force_refresh=False):
    """
    Load split-adjusted daily close prices via yfinance.
    Caches to adj_prices/<TICKER>.csv.

    FIX #1: Uses yfinance adjusted close, NOT raw Yahoo JSON close.
    This correctly handles stock splits (e.g., 2025 SPDR 2:1 splits).
    """
    import yfinance as yf
    import time

    if tickers is None:
        tickers = ALL_TICKERS

    os.makedirs(ADJ_CACHE, exist_ok=True)
    all_frames = {}

    for t in tickers:
        cache_fp = os.path.join(ADJ_CACHE, f'{t}.csv')

        if os.path.exists(cache_fp) and not force_refresh:
            df = pd.read_csv(cache_fp, parse_dates=['date'], index_col='date')
            if len(df) > 100:
                all_frames[t] = df
                continue

        # Download from yfinance (adjusted close)
        try:
            hist = yf.Ticker(t).history(start=start, end=end, interval='1d',
                                         auto_adjust=True)
            if hist.empty:
                print(f'  ⚠ {t}: no data from yfinance')
                continue

            df = pd.DataFrame({'adj_close': hist['Close']})
            df.index.name = 'date'
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            df.to_csv(cache_fp)
            all_frames[t] = df
            print(f'  ✓ {t}: {len(df)} days downloaded')
            time.sleep(1.0)
        except Exception as e:
            print(f'  ✗ {t}: {e}')

    return all_frames


def load_pe():
    """Load Koyfin forward PE CSVs. Drops XLC first-day anomaly."""
    frames = []
    for fname, ticker in PE_MAP.items():
        fp = os.path.join(PE_DIR, fname)
        if not os.path.exists(fp):
            continue
        df = pd.read_csv(fp)
        df.columns = [c.strip() for c in df.columns]
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['forward_pe']).set_index('date').sort_index()

        # XLC first-day anomaly: 10.13x is clearly wrong
        if ticker == 'XLC' and len(df) > 1 and df['forward_pe'].iloc[0] < 12:
            df = df.iloc[1:]

        m = df['forward_pe'].resample('ME').last().dropna().to_frame('fpe')
        m['ticker'] = ticker
        frames.append(m.reset_index())

    pe = pd.concat(frames, ignore_index=True)

    # Report actual coverage
    for t in SECTORS:
        sub = pe[pe['ticker'] == t]
        if len(sub) > 0:
            start = sub['date'].min().strftime('%Y-%m')
            end = sub['date'].max().strftime('%Y-%m')
        else:
            start = end = 'N/A'

    return pe


# ══════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════

def _safe_ratio(a, b, periods):
    """
    Compute a / a.shift(periods) - 1, returning NaN where either is NaN.

    FIX #2: Replaces pct_change() which may forward-fill NaN in older pandas.
    Explicit ratio guarantees NaN propagation.
    """
    shifted = b if b is not None else a.shift(periods)
    result = a / shifted - 1
    # Ensure NaN where input was NaN
    result[a.isna() | shifted.isna()] = np.nan
    return result


def build_features(daily_prices, pe, exclude_tickers=None):
    """
    Build monthly feature matrix from daily adjusted prices + PE data.

    Returns (df, feat_xs, daily_px) where:
      - df: monthly panel with features and execution returns
      - feat_xs: list of cross-sectional z-scored feature column names
      - daily_px: dict of daily price DataFrames (for execution return calc)
    """
    tickers = [t for t in SECTORS if t not in (exclude_tickers or [])]

    # Monthly adjusted close
    monthly_frames = []
    for t in tickers:
        if t not in daily_prices:
            continue
        dp = daily_prices[t].copy()
        m = dp['adj_close'].resample('ME').last().dropna().to_frame('close')
        m['ticker'] = t
        monthly_frames.append(m.reset_index())

    if not monthly_frames:
        return None, [], daily_prices

    panel = pd.concat(monthly_frames, ignore_index=True)
    panel['date'] = pd.to_datetime(panel['date']).dt.tz_localize(None)

    # Merge PE
    m = panel.merge(pe[['date', 'ticker', 'fpe']], on=['date', 'ticker'], how='left')

    # PE cap: null out extreme PE
    m.loc[(m['fpe'] > 50) | (m['fpe'] <= 0), 'fpe'] = np.nan

    all_feat = []
    for t in tickers:
        s = m[m['ticker'] == t].sort_values('date').copy()
        if len(s) < 25:
            continue

        # ── Valuation ──
        s['f_valuation'] = -s['fpe'].rolling(24, min_periods=12).apply(
            lambda x: (x.iloc[-1] - x.mean()) / (x.std() + 1e-9))

        # ── EPS Revision (FIX #2: explicit ratio, no pct_change) ──
        s['fwd_eps'] = s['close'] / s['fpe']  # NaN when fpe is NaN
        s['f_eps_rev'] = _safe_ratio(s['fwd_eps'], None, 3).clip(-0.5, 0.5)
        s['f_eps_rev_1m'] = _safe_ratio(s['fwd_eps'], None, 1).clip(-0.3, 0.3)

        # ── Momentum (FIX #2: explicit ratio) ──
        s['f_mom6'] = _safe_ratio(s['close'], None, 6)
        s['f_mom3'] = _safe_ratio(s['close'], None, 3)
        s['f_mom1'] = _safe_ratio(s['close'], None, 1)

        # ── PE level and change ──
        s['f_pe_level'] = s['fpe']
        s['f_pe_chg3'] = _safe_ratio(s['fpe'], None, 3)

        # ── Distance from 6M high ──
        s['f_dist_high6'] = s['close'] / s['close'].rolling(6).max() - 1

        # ── 3M training target ──
        # Target: 3M excess return vs cross-sectional median
        s['fwd_ret_3m_raw'] = _safe_ratio(s['close'].shift(-3), s['close'], 0)
        # i.e., close[T+3] / close[T] - 1, where shift(-3) brings future price

        # Actually let me be more explicit:
        future_3m = s['close'].shift(-3)
        s['fwd_ret_3m_raw'] = future_3m / s['close'] - 1
        s.loc[s['close'].isna() | future_3m.isna(), 'fwd_ret_3m_raw'] = np.nan

        all_feat.append(s)

    if not all_feat:
        return None, [], daily_prices

    df = pd.concat(all_feat, ignore_index=True)

    # Cross-sectional median for target
    df['fwd_ret_3m_median'] = df.groupby('date')['fwd_ret_3m_raw'].transform('median')
    df['target'] = df['fwd_ret_3m_raw'] - df['fwd_ret_3m_median']

    # ── Execution returns (FIX #3: next-trading-day via daily prices) ──
    df['exec_ret'] = np.nan
    signal_dates = sorted(df['date'].unique())

    for i, sig_date in enumerate(signal_dates[:-1]):
        next_sig_date = signal_dates[i + 1]

        for t in tickers:
            if t not in daily_prices:
                continue

            dp = daily_prices[t]
            # Entry: first trading day AFTER signal date
            entry_candidates = dp.index[dp.index > sig_date]
            if len(entry_candidates) == 0:
                continue
            entry_date = entry_candidates[0]
            entry_price = dp.loc[entry_date, 'adj_close']

            # Exit: first trading day AFTER next signal date
            exit_candidates = dp.index[dp.index > next_sig_date]
            if len(exit_candidates) == 0:
                continue
            exit_date = exit_candidates[0]
            exit_price = dp.loc[exit_date, 'adj_close']

            if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
                mask = (df['date'] == sig_date) & (df['ticker'] == t)
                df.loc[mask, 'exec_ret'] = exit_price / entry_price - 1

    # ── Cross-sectional z-score features ──
    feat_xs = []
    for c in FEAT_COLS:
        zc = c + '_xs'
        df[zc] = df.groupby('date')[c].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9) if x.std() > 0 else 0)
        feat_xs.append(zc)

    return df, feat_xs, daily_prices


# ══════════════════════════════════════════════════
# WALK-FORWARD ENGINE
# ══════════════════════════════════════════════════

def walk_forward_purged(df, feat_xs, top_n=1, start='2019-01', end='2026-06',
                        embargo_months=3,
                        exclude_years_test=None,
                        exclude_years_train=None,
                        exclude_labels_overlapping=None,
                        shuffle_labels=False, shuffle_seed=42,
                        shuffle_features=None,
                        model_type='rf'):
    """
    Purged walk-forward backtest.

    FIX #3: Uses exec_ret (next-trading-day) for P&L.
    FIX #4: exclude_labels_overlapping removes training obs whose 3M target
            overlaps with excluded years.
    FIX #5: shuffle_features uses same row permutation for grouped features.
    """
    dates = sorted(df['date'].unique())
    dates = [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]

    if exclude_years_test:
        dates = [d for d in dates if d.year not in exclude_years_test]

    results = []
    rng = np.random.RandomState(shuffle_seed)

    for pred_date in dates:
        # Purge: only train where 3M target has fully realized
        cutoff = pred_date - pd.DateOffset(months=embargo_months)
        train = df[df['date'] <= cutoff].dropna(subset=feat_xs + ['target']).copy()

        # FIX #4: exclude training obs whose label overlaps excluded years
        if exclude_years_train:
            train = train[~train['date'].dt.year.isin(exclude_years_train)]

        if exclude_labels_overlapping:
            # Remove obs where target horizon (date to date+3M) overlaps excluded years
            for excl_year in exclude_labels_overlapping:
                year_start = pd.Timestamp(f'{excl_year}-01-01')
                year_end = pd.Timestamp(f'{excl_year}-12-31')
                # obs at date S has target covering S to S+3M
                label_end = train['date'] + pd.DateOffset(months=3)
                overlap = (train['date'] <= year_end) & (label_end >= year_start)
                train = train[~overlap]

        test = df[df['date'] == pred_date].dropna(subset=feat_xs).copy()

        if len(train) < 100 or len(test) < 4:
            continue

        X_tr = train[feat_xs].values.copy()
        y_tr = train['target'].values.copy()

        # Placebo: shuffle labels
        if shuffle_labels:
            # FIX #5b: cross-sectional shuffle (within each month)
            train_copy = train.copy()
            for dt in train_copy['date'].unique():
                mask = train_copy['date'] == dt
                idx = np.where(mask.values)[0]
                if len(idx) > 1:
                    shuffled = rng.permutation(y_tr[idx])
                    y_tr[idx] = shuffled

        X_te = test[feat_xs].values.copy()

        # FIX #5: group permutation with same row indices
        if shuffle_features:
            perm_idx = rng.permutation(len(X_te))
            for sf in shuffle_features:
                if sf in feat_xs:
                    col_idx = feat_xs.index(sf)
                    X_te[:, col_idx] = X_te[perm_idx, col_idx]

        # Model
        if model_type == 'rf':
            mdl = RandomForestRegressor(n_estimators=200, max_depth=4,
                    min_samples_leaf=10, random_state=42, n_jobs=-1)
        elif model_type == 'ridge':
            mdl = Ridge(alpha=1.0)
        else:
            raise ValueError(f'Unknown model_type: {model_type}')

        mdl.fit(X_tr, y_tr)
        preds = mdl.predict(X_te)

        test = test.copy()
        test['pred'] = preds
        test = test.sort_values('pred', ascending=False)
        top = test.head(top_n)
        bot = test.tail(top_n)

        # P&L uses exec_ret (next-trading-day execution)
        top_ret = top['exec_ret'].mean() if top['exec_ret'].notna().any() else np.nan
        bot_ret = bot['exec_ret'].mean() if bot['exec_ret'].notna().any() else np.nan
        ew = test['exec_ret'].mean()
        ic = np.nan
        valid = test.dropna(subset=['exec_ret'])
        if len(valid) >= 5:
            ic = stats.spearmanr(valid['pred'], valid['exec_ret'])[0]

        results.append({
            'date': pred_date,
            'top_ret': top_ret, 'bot_ret': bot_ret,
            'spread': top_ret - bot_ret if pd.notna(bot_ret) else np.nan,
            'ew': ew, 'ic': ic,
            'top1': top['ticker'].iloc[0],
            'picks': ','.join(top['ticker'].tolist()),
        })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════

def calc_metrics(rets, label=''):
    """Standard performance metrics from a return series."""
    r = pd.Series(rets).dropna()
    n = len(r)
    if n < 4:
        return None
    cum = (1 + r).cumprod()
    years = n / 12
    cagr = cum.iloc[-1] ** (1 / years) - 1 if years > 0 else 0
    vol = r.std() * np.sqrt(12)
    sharpe = (r.mean() * 12) / vol if vol > 0 else 0
    down = r[r < 0]
    dv = down.std() * np.sqrt(12) if len(down) > 1 else vol
    sortino = (r.mean() * 12) / dv if dv > 0 else 0
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()
    return {
        'label': label, 'cagr': cagr, 'sharpe': sharpe, 'sortino': sortino,
        'mdd': mdd, 'n': n, 'wr': (r > 0).mean(),
    }


def fmt_metrics(m):
    """Format metrics dict as a fixed-width string."""
    return (f"{m['label']:<38s} {m['cagr']*100:+6.1f}% {m['sharpe']:6.2f}  "
            f"{m['sortino']:6.2f}  {m['mdd']*100:6.1f}% {m['wr']*100:4.0f}% {m['n']:4d}")


HDR = (f"{'Test':<38s} {'CAGR':>7s} {'Sharpe':>7s} {'Sortino':>8s} "
       f"{'MaxDD':>7s} {'WR':>5s} {'N':>5s}")
SEP = '─' * 88
