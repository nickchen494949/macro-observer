#!/usr/bin/env python3
"""
Sector Rotation Engine v5

v5 fixes:
  1. 🔴 Split price: Yahoo Close IS already split-adjusted. No manual split math.
  2. 🔴 Benchmark: walk_forward returns entry/exit dates, benchmark reuses them exactly.
  3. 🟠 Fixed universe: auto-detect common feature start.
  4. 🟠 Pass criteria: excess return vs aligned benchmark.
  5. 🟡 Permutation importance: N_PERM repeats per group.
"""

import os, warnings
import pandas as pd, numpy as np
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

warnings.filterwarnings('ignore')

CACHE_VERSION = 5  # bump to invalidate old adj_prices/ cache

_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(_DIR, '..', '..'))
PE_DIR = os.path.join(_DIR, 'pe_data')
PRICE_CACHE = os.path.join(_DIR, 'adj_prices')

SECTORS = ['XLK', 'XLC', 'XLY', 'XLF', 'XLI', 'XLU', 'XLE', 'XLRE', 'XLB', 'XLP', 'XLV']
BENCHMARKS = ['SPY', 'QQQ']
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

def load_prices(tickers=None, start='2002-01-01', end='2026-09-01',
                force_refresh=False):
    """
    Load daily prices via yfinance. Saves TWO columns:

      split_adj_close — Yahoo 'Close' (already split-adjusted, NO dividends)
                        → for EPS proxy = price / PE
      adj_close       — Yahoo 'Adj Close' (split + dividend adjusted)
                        → for momentum, target, P&L

    FIX v5: Yahoo's Close IS already split-adjusted in historical data.
    We were double-adjusting by manually applying tk.splits on top.
    Now just use hist['Close'] directly.
    """
    import yfinance as yf
    import time

    if tickers is None:
        tickers = ALL_TICKERS

    os.makedirs(PRICE_CACHE, exist_ok=True)
    version_fp = os.path.join(PRICE_CACHE, '.cache_version')

    # Invalidate old cache
    cached_ver = 0
    if os.path.exists(version_fp):
        try:
            cached_ver = int(open(version_fp).read().strip())
        except Exception:
            pass
    if cached_ver < CACHE_VERSION:
        force_refresh = True
        # Write new version marker
        with open(version_fp, 'w') as f:
            f.write(str(CACHE_VERSION))

    all_frames = {}

    for t in tickers:
        cache_fp = os.path.join(PRICE_CACHE, f'{t}.csv')

        if os.path.exists(cache_fp) and not force_refresh:
            df = pd.read_csv(cache_fp, parse_dates=['date'], index_col='date')
            if len(df) > 100 and 'split_adj_close' in df.columns:
                all_frames[t] = df
                continue

        try:
            hist = yf.Ticker(t).history(start=start, end=end, interval='1d',
                                         auto_adjust=False)
            if hist.empty:
                print(f'  ⚠ {t}: no data')
                continue

            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)

            # ═══════════════════════════════════════
            # FIX v5: NO manual split adjustment!
            #
            # Yahoo Close = already split-adjusted (no dividends)
            # Yahoo Adj Close = split + dividend adjusted
            # ═══════════════════════════════════════
            df = pd.DataFrame({
                'adj_close': hist['Adj Close'].astype(float),
                'split_adj_close': hist['Close'].astype(float),
            })
            df.index.name = 'date'
            df.to_csv(cache_fp)
            all_frames[t] = df
            print(f'  ✓ {t}: {len(df)} days ({df.index[0].strftime("%Y-%m")} → '
                  f'{df.index[-1].strftime("%Y-%m")})')
            time.sleep(1.0)
        except Exception as e:
            print(f'  ✗ {t}: {e}')

    return all_frames


def load_pe():
    """Load Koyfin forward PE CSVs."""
    frames = []
    coverage = {}
    for fname, ticker in PE_MAP.items():
        fp = os.path.join(PE_DIR, fname)
        if not os.path.exists(fp):
            continue
        df = pd.read_csv(fp)
        df.columns = [c.strip() for c in df.columns]
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['forward_pe']).set_index('date').sort_index()

        if ticker == 'XLC' and len(df) > 1 and df['forward_pe'].iloc[0] < 12:
            df = df.iloc[1:]

        coverage[ticker] = (df.index[0].strftime('%Y-%m'), df.index[-1].strftime('%Y-%m'))
        m = df['forward_pe'].resample('ME').last().dropna().to_frame('fpe')
        m['ticker'] = ticker
        frames.append(m.reset_index())

    return pd.concat(frames, ignore_index=True), coverage


# ══════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════

def _safe_ratio(series, periods):
    """series[t] / series[t-periods] - 1, NaN-safe. No pct_change."""
    shifted = series.shift(periods)
    result = series / shifted - 1
    result[series.isna() | shifted.isna() | (shifted.abs() < 1e-9)] = np.nan
    return result


def common_feature_start(df, feat_xs, expected_n):
    """Find first month where all expected sectors have all features."""
    good = df.dropna(subset=feat_xs).groupby('date')['ticker'].nunique()
    candidates = good[good >= expected_n]
    return candidates.index.min() if len(candidates) > 0 else None


def build_features(daily_prices, pe, exclude_tickers=None):
    """
    Build monthly feature matrix.

    split_adj_close → EPS proxy (no dividend contamination)
    adj_close → momentum, P&L
    """
    tickers = [t for t in SECTORS if t not in (exclude_tickers or [])]

    pe_data = pe[0] if isinstance(pe, tuple) else pe

    monthly_frames = []
    for t in tickers:
        if t not in daily_prices:
            continue
        dp = daily_prices[t].copy()
        if 'split_adj_close' not in dp.columns:
            dp['split_adj_close'] = dp['adj_close']
        m_adj = dp['adj_close'].resample('ME').last().dropna()
        m_split = dp['split_adj_close'].resample('ME').last().dropna()
        m = pd.DataFrame({
            'close': m_adj,          # total-return → momentum, target, P&L
            'close_eps': m_split,    # split-only → EPS proxy
        })
        m['ticker'] = t
        monthly_frames.append(m.reset_index())

    if not monthly_frames:
        return None, [], daily_prices

    panel = pd.concat(monthly_frames, ignore_index=True)
    panel['date'] = pd.to_datetime(panel['date']).dt.tz_localize(None)

    m = panel.merge(pe_data[['date', 'ticker', 'fpe']], on=['date', 'ticker'], how='left')
    m.loc[(m['fpe'] > 50) | (m['fpe'] <= 0), 'fpe'] = np.nan

    all_feat = []
    for t in tickers:
        s = m[m['ticker'] == t].sort_values('date').copy()
        if len(s) < 25:
            continue

        s['f_valuation'] = -s['fpe'].rolling(24, min_periods=12).apply(
            lambda x: (x.iloc[-1] - x.mean()) / (x.std() + 1e-9))

        # EPS proxy: split-only price / PE
        s['fwd_eps'] = s['close_eps'] / s['fpe']
        s['f_eps_rev'] = _safe_ratio(s['fwd_eps'], 3).clip(-0.5, 0.5)
        s['f_eps_rev_1m'] = _safe_ratio(s['fwd_eps'], 1).clip(-0.3, 0.3)

        # Momentum: total-return price
        s['f_mom6'] = _safe_ratio(s['close'], 6)
        s['f_mom3'] = _safe_ratio(s['close'], 3)
        s['f_mom1'] = _safe_ratio(s['close'], 1)

        s['f_pe_level'] = s['fpe']
        s['f_pe_chg3'] = _safe_ratio(s['fpe'], 3)
        s['f_dist_high6'] = s['close'] / s['close'].rolling(6).max() - 1

        # 3M training target (total-return)
        future_3m = s['close'].shift(-3)
        s['fwd_ret_3m_raw'] = future_3m / s['close'] - 1
        s.loc[s['close'].isna() | future_3m.isna(), 'fwd_ret_3m_raw'] = np.nan

        all_feat.append(s)

    if not all_feat:
        return None, [], daily_prices

    df = pd.concat(all_feat, ignore_index=True)

    df['fwd_ret_3m_median'] = df.groupby('date')['fwd_ret_3m_raw'].transform('median')
    df['target'] = df['fwd_ret_3m_raw'] - df['fwd_ret_3m_median']

    # ── Execution returns + dates via daily prices ──
    df['exec_ret'] = np.nan
    df['entry_date'] = pd.NaT
    df['exit_date'] = pd.NaT
    signal_dates = sorted(df['date'].unique())

    for i, sig_date in enumerate(signal_dates[:-1]):
        next_sig_date = signal_dates[i + 1]
        for t in tickers:
            if t not in daily_prices:
                continue
            dp = daily_prices[t]
            entry_cands = dp.index[dp.index > sig_date]
            exit_cands = dp.index[dp.index > next_sig_date]
            if len(entry_cands) == 0 or len(exit_cands) == 0:
                continue
            entry_dt = entry_cands[0]
            exit_dt = exit_cands[0]
            entry_px = dp.loc[entry_dt, 'adj_close']
            exit_px = dp.loc[exit_dt, 'adj_close']
            if pd.notna(entry_px) and pd.notna(exit_px) and entry_px > 0:
                mask = (df['date'] == sig_date) & (df['ticker'] == t)
                df.loc[mask, 'exec_ret'] = exit_px / entry_px - 1
                df.loc[mask, 'entry_date'] = entry_dt
                df.loc[mask, 'exit_date'] = exit_dt

    # Cross-sectional z-score
    feat_xs = []
    for c in FEAT_COLS:
        zc = c + '_xs'
        df[zc] = df.groupby('date')[c].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9) if x.std() > 0 else 0)
        feat_xs.append(zc)

    return df, feat_xs, daily_prices


# ══════════════════════════════════════════════════
# BENCHMARK (exact same entry/exit dates as strategy)
# ══════════════════════════════════════════════════

def compute_benchmark_aligned(daily_prices, strategy_results, ticker='SPY'):
    """
    FIX v5: Benchmark uses EXACT entry_date/exit_date from strategy results.
    No independent date calculation. Guaranteed same N and same periods.
    """
    if ticker not in daily_prices:
        return pd.Series(dtype=float)

    dp = daily_prices[ticker]
    rets = []

    for _, row in strategy_results.iterrows():
        entry = row.get('entry_date')
        exit_ = row.get('exit_date')
        if pd.isna(entry) or pd.isna(exit_):
            rets.append(np.nan)
            continue

        # Find nearest trading day (in case exact date not in index)
        entry_idx = dp.index.searchsorted(entry)
        exit_idx = dp.index.searchsorted(exit_)

        if entry_idx >= len(dp) or exit_idx >= len(dp):
            rets.append(np.nan)
            continue

        entry_px = dp.iloc[entry_idx]['adj_close']
        exit_px = dp.iloc[exit_idx]['adj_close']

        if pd.notna(entry_px) and pd.notna(exit_px) and entry_px > 0:
            rets.append(exit_px / entry_px - 1)
        else:
            rets.append(np.nan)

    return pd.Series(rets, index=strategy_results['date'].values)


# ══════════════════════════════════════════════════
# PLACEBO
# ══════════════════════════════════════════════════

def make_placebo_df(df, seed):
    """
    One fixed fake history: shuffle sector-target assignments within each month.
    Used consistently across entire walk-forward.
    """
    rng = np.random.RandomState(seed)
    df_p = df.copy()
    for dt in df_p['date'].unique():
        mask = df_p['date'] == dt
        vals = df_p.loc[mask, 'target'].values.copy()
        if len(vals) > 1:
            df_p.loc[mask, 'target'] = rng.permutation(vals)
    return df_p


# ══════════════════════════════════════════════════
# WALK-FORWARD ENGINE
# ══════════════════════════════════════════════════

def walk_forward_purged(df, feat_xs, top_n=1, start='2019-01', end='2026-06',
                        embargo_months=3,
                        exclude_years_test=None,
                        exclude_labels_overlapping=None,
                        shuffle_features=None,
                        model_type='rf'):
    """
    Purged walk-forward.

    FIX v5: Returns entry_date/exit_date per row so benchmark can reuse exactly.
    """
    dates = sorted(df['date'].unique())
    dates = [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]

    # Strict year exclusion by execution date overlap
    if exclude_years_test:
        clean = []
        for d in dates:
            rows = df[df['date'] == d]
            if len(rows) == 0:
                continue
            entry = rows['entry_date'].dropna()
            exit_ = rows['exit_date'].dropna()
            if len(entry) == 0 or len(exit_) == 0:
                if d.year not in exclude_years_test:
                    clean.append(d)
                continue
            any_entry = entry.iloc[0]
            any_exit = exit_.iloc[0]
            overlaps = False
            for ey in exclude_years_test:
                ys = pd.Timestamp(f'{ey}-01-01')
                ye = pd.Timestamp(f'{ey}-12-31')
                if any_entry <= ye and any_exit >= ys:
                    overlaps = True
                    break
            if not overlaps:
                clean.append(d)
        dates = clean

    results = []
    rng = np.random.RandomState(42)

    for pred_date in dates:
        cutoff = pred_date - pd.DateOffset(months=embargo_months)
        train = df[df['date'] <= cutoff].dropna(subset=feat_xs + ['target']).copy()

        if exclude_labels_overlapping:
            for ey in exclude_labels_overlapping:
                ys = pd.Timestamp(f'{ey}-01-01')
                ye = pd.Timestamp(f'{ey}-12-31')
                label_end = train['date'] + pd.DateOffset(months=3)
                overlap = (train['date'] <= ye) & (label_end >= ys)
                train = train[~overlap]

        test = df[df['date'] == pred_date].dropna(subset=feat_xs).copy()

        if len(train) < 100 or len(test) < 4:
            continue

        X_tr = train[feat_xs].values.copy()
        y_tr = train['target'].values.copy()
        X_te = test[feat_xs].values.copy()

        if shuffle_features:
            perm_idx = rng.permutation(len(X_te))
            for sf in shuffle_features:
                if sf in feat_xs:
                    col_idx = feat_xs.index(sf)
                    X_te[:, col_idx] = X_te[perm_idx, col_idx]

        if model_type == 'rf':
            mdl = RandomForestRegressor(n_estimators=200, max_depth=4,
                    min_samples_leaf=10, random_state=42, n_jobs=-1)
        elif model_type == 'ridge':
            mdl = Ridge(alpha=1.0)
        else:
            raise ValueError(f'Unknown: {model_type}')

        mdl.fit(X_tr, y_tr)
        preds = mdl.predict(X_te)

        test['pred'] = preds
        test = test.sort_values('pred', ascending=False)
        top = test.head(top_n)
        bot = test.tail(top_n)

        top_ret = top['exec_ret'].mean() if top['exec_ret'].notna().any() else np.nan
        bot_ret = bot['exec_ret'].mean() if bot['exec_ret'].notna().any() else np.nan
        ew = test['exec_ret'].mean()
        valid = test.dropna(subset=['exec_ret'])
        ic = stats.spearmanr(valid['pred'], valid['exec_ret'])[0] if len(valid) >= 5 else np.nan

        # FIX v5: capture entry/exit dates for benchmark alignment
        top_entry = top['entry_date'].dropna().iloc[0] if top['entry_date'].notna().any() else pd.NaT
        top_exit = top['exit_date'].dropna().iloc[0] if top['exit_date'].notna().any() else pd.NaT

        results.append({
            'date': pred_date,
            'entry_date': top_entry,
            'exit_date': top_exit,
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
    return (f"{m['label']:<40s} {m['cagr']*100:+6.1f}% {m['sharpe']:6.2f}  "
            f"{m['sortino']:6.2f}  {m['mdd']*100:6.1f}% {m['wr']*100:4.0f}% {m['n']:4d}")


HDR = (f"{'Test':<40s} {'CAGR':>7s} {'Sharpe':>7s} {'Sortino':>8s} "
       f"{'MaxDD':>7s} {'WR':>5s} {'N':>5s}")
SEP = '─' * 90
