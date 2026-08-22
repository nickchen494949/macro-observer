#!/usr/bin/env python3
"""
Sector Rotation Engine v4 — Shared data + backtest infrastructure.

v4 fixes (from code review):
  1. Two price series: split-only-adjusted for EPS, total-return for P&L
  2. Placebo uses fixed fake history per seed (pre-shuffled once)
  3. Strict year exclusion checks execution date overlap, not just signal year
  4. Benchmark uses exact same execution dates as strategy
  5. Explicit ratio for all % changes (no pct_change NaN bug)
  6. Proper group permutation (shared row permutation)
  7. Cross-sectional placebo (shuffle within each month)
"""

import os, json, warnings
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
PRICE_CACHE = os.path.join(_DIR, 'adj_prices')

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

def load_prices(tickers=None, start='2002-01-01', end='2026-09-01',
                force_refresh=False):
    """
    Load daily prices via yfinance. Saves TWO columns per ticker:

      adj_close       — split + dividend adjusted (for P&L / momentum)
      split_adj_close — split-only adjusted (for EPS proxy = price / PE)

    FIX v4: auto_adjust=True adjusts for dividends too, which contaminates
    EPS = Price / PE. We now compute split-only-adjusted prices using
    yfinance's split history.
    """
    import yfinance as yf
    import time

    if tickers is None:
        tickers = ALL_TICKERS

    os.makedirs(PRICE_CACHE, exist_ok=True)
    all_frames = {}

    for t in tickers:
        cache_fp = os.path.join(PRICE_CACHE, f'{t}.csv')

        if os.path.exists(cache_fp) and not force_refresh:
            df = pd.read_csv(cache_fp, parse_dates=['date'], index_col='date')
            if len(df) > 100 and 'split_adj_close' in df.columns:
                all_frames[t] = df
                continue

        try:
            tk = yf.Ticker(t)

            # Download with auto_adjust=False to get BOTH raw and adjusted
            hist = tk.history(start=start, end=end, interval='1d',
                              auto_adjust=False)
            if hist.empty:
                print(f'  ⚠ {t}: no data')
                continue

            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)

            # Total-return adjusted close (splits + dividends)
            adj_close = hist['Adj Close'] if 'Adj Close' in hist.columns else hist['Close']

            # Split-only adjusted close
            raw_close = hist['Close']

            # Get split history
            try:
                splits = tk.splits
                if splits is not None and len(splits) > 0:
                    # Build cumulative split factor (latest = 1.0, going backward)
                    cum_split = pd.Series(1.0, index=raw_close.index)
                    for split_date, ratio in splits.items():
                        sd = split_date
                        if hasattr(sd, 'tz') and sd.tz is not None:
                            sd = sd.tz_localize(None)
                        if ratio > 0:
                            # ratio = 2.0 for 2:1 split → old price was 2x, divide by ratio
                            cum_split[cum_split.index < sd] *= (1.0 / ratio)
                    split_adj = raw_close * cum_split
                else:
                    split_adj = raw_close.copy()
            except Exception:
                split_adj = raw_close.copy()

            df = pd.DataFrame({
                'adj_close': adj_close,
                'split_adj_close': split_adj,
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
    """Load Koyfin forward PE CSVs. Drops XLC first-day anomaly."""
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
    """
    series[t] / series[t-periods] - 1, NaN-safe.
    No pct_change, no forward-fill risk.
    """
    shifted = series.shift(periods)
    result = series / shifted - 1
    result[series.isna() | shifted.isna() | (shifted.abs() < 1e-9)] = np.nan
    return result


def build_features(daily_prices, pe, exclude_tickers=None,
                   train_start=None):
    """
    Build monthly feature matrix.

    Uses split_adj_close for EPS proxy (no dividend contamination).
    Uses adj_close for momentum and P&L.
    """
    tickers = [t for t in SECTORS if t not in (exclude_tickers or [])]

    # Monthly prices (both series)
    monthly_frames = []
    for t in tickers:
        if t not in daily_prices:
            continue
        dp = daily_prices[t].copy()
        if 'split_adj_close' not in dp.columns:
            # Fallback: use adj_close for both
            dp['split_adj_close'] = dp['adj_close']
        # Monthly: last value
        m_adj = dp['adj_close'].resample('ME').last().dropna()
        m_split = dp['split_adj_close'].resample('ME').last().dropna()
        m = pd.DataFrame({
            'close': m_adj,          # total-return adjusted → momentum, P&L
            'close_eps': m_split,    # split-only adjusted → EPS proxy
        })
        m['ticker'] = t
        monthly_frames.append(m.reset_index())

    if not monthly_frames:
        return None, [], daily_prices

    panel = pd.concat(monthly_frames, ignore_index=True)
    panel['date'] = pd.to_datetime(panel['date']).dt.tz_localize(None)

    # Merge PE
    pe_data = pe[0] if isinstance(pe, tuple) else pe
    m = panel.merge(pe_data[['date', 'ticker', 'fpe']], on=['date', 'ticker'], how='left')
    m.loc[(m['fpe'] > 50) | (m['fpe'] <= 0), 'fpe'] = np.nan

    all_feat = []
    for t in tickers:
        s = m[m['ticker'] == t].sort_values('date').copy()
        if len(s) < 25:
            continue

        # ── Valuation (uses PE directly) ──
        s['f_valuation'] = -s['fpe'].rolling(24, min_periods=12).apply(
            lambda x: (x.iloc[-1] - x.mean()) / (x.std() + 1e-9))

        # ── EPS Revision: uses split-only price / PE ──
        s['fwd_eps'] = s['close_eps'] / s['fpe']
        s['f_eps_rev'] = _safe_ratio(s['fwd_eps'], 3).clip(-0.5, 0.5)
        s['f_eps_rev_1m'] = _safe_ratio(s['fwd_eps'], 1).clip(-0.3, 0.3)

        # ── Momentum: uses total-return adjusted price ──
        s['f_mom6'] = _safe_ratio(s['close'], 6)
        s['f_mom3'] = _safe_ratio(s['close'], 3)
        s['f_mom1'] = _safe_ratio(s['close'], 1)

        # ── PE level and change ──
        s['f_pe_level'] = s['fpe']
        s['f_pe_chg3'] = _safe_ratio(s['fpe'], 3)

        # ── Distance from 6M high (total-return) ──
        s['f_dist_high6'] = s['close'] / s['close'].rolling(6).max() - 1

        # ── 3M training target (total-return excess vs median) ──
        future_3m = s['close'].shift(-3)
        s['fwd_ret_3m_raw'] = future_3m / s['close'] - 1
        s.loc[s['close'].isna() | future_3m.isna(), 'fwd_ret_3m_raw'] = np.nan

        all_feat.append(s)

    if not all_feat:
        return None, [], daily_prices

    df = pd.concat(all_feat, ignore_index=True)

    # Cross-sectional median target
    df['fwd_ret_3m_median'] = df.groupby('date')['fwd_ret_3m_raw'].transform('median')
    df['target'] = df['fwd_ret_3m_raw'] - df['fwd_ret_3m_median']

    # ── Execution returns via daily prices (next-trading-day) ──
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

            # Entry: first trading day AFTER signal month-end
            entry_cands = dp.index[dp.index > sig_date]
            if len(entry_cands) == 0:
                continue
            entry_dt = entry_cands[0]
            entry_px = dp.loc[entry_dt, 'adj_close']

            # Exit: first trading day AFTER next signal month-end
            exit_cands = dp.index[dp.index > next_sig_date]
            if len(exit_cands) == 0:
                continue
            exit_dt = exit_cands[0]
            exit_px = dp.loc[exit_dt, 'adj_close']

            if pd.notna(entry_px) and pd.notna(exit_px) and entry_px > 0:
                mask = (df['date'] == sig_date) & (df['ticker'] == t)
                df.loc[mask, 'exec_ret'] = exit_px / entry_px - 1
                df.loc[mask, 'entry_date'] = entry_dt
                df.loc[mask, 'exit_date'] = exit_dt

    # Optional: filter to common universe start
    if train_start:
        df = df[df['date'] >= pd.Timestamp(train_start)].copy()

    # Cross-sectional z-score features
    feat_xs = []
    for c in FEAT_COLS:
        zc = c + '_xs'
        df[zc] = df.groupby('date')[c].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9) if x.std() > 0 else 0)
        feat_xs.append(zc)

    return df, feat_xs, daily_prices


# ══════════════════════════════════════════════════
# BENCHMARK (same execution dates as strategy)
# ══════════════════════════════════════════════════

def compute_benchmark_returns(daily_prices, signal_dates, ticker='SPY'):
    """
    Compute benchmark returns using EXACT same execution dates as strategy.

    FIX v4: Previously benchmark used month-end-to-month-end, while strategy
    used next-trading-day. Now both use identical entry/exit dates.
    """
    if ticker not in daily_prices:
        return pd.Series(dtype=float)

    dp = daily_prices[ticker]
    rets = []

    for i, sig_date in enumerate(signal_dates[:-1]):
        next_sig = signal_dates[i + 1]

        entry_cands = dp.index[dp.index > sig_date]
        exit_cands = dp.index[dp.index > next_sig]

        if len(entry_cands) == 0 or len(exit_cands) == 0:
            continue

        entry_px = dp.loc[entry_cands[0], 'adj_close']
        exit_px = dp.loc[exit_cands[0], 'adj_close']

        if pd.notna(entry_px) and pd.notna(exit_px) and entry_px > 0:
            rets.append({'date': sig_date, 'ret': exit_px / entry_px - 1})

    return pd.DataFrame(rets).set_index('date')['ret'] if rets else pd.Series(dtype=float)


# ══════════════════════════════════════════════════
# PLACEBO (fixed fake history per seed)
# ══════════════════════════════════════════════════

def make_placebo_df(df, seed):
    """
    Create a fixed fake-history DataFrame for one placebo iteration.

    FIX v4: Previously reshuffled training labels at every prediction date,
    meaning 2020-06's label changed depending on which month we predicted.
    Now each seed creates ONE fixed permutation of sector-target assignments
    within each month, used consistently throughout the entire walk-forward.
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
    Purged walk-forward backtest.

    FIX v4: Strict year exclusion checks entry_date/exit_date overlap,
    not just signal year. Placebo is handled externally via make_placebo_df().
    """
    dates = sorted(df['date'].unique())
    dates = [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]

    # Strict year exclusion: remove signal dates whose EXECUTION overlaps
    if exclude_years_test:
        clean_dates = []
        for d in dates:
            row = df[df['date'] == d].iloc[0] if len(df[df['date'] == d]) > 0 else None
            if row is None:
                continue
            entry = row.get('entry_date', pd.NaT)
            exit_ = row.get('exit_date', pd.NaT)
            # If we don't have dates, fall back to signal year
            if pd.isna(entry) or pd.isna(exit_):
                if d.year not in exclude_years_test:
                    clean_dates.append(d)
                continue
            # Check if execution period overlaps any excluded year
            overlaps = False
            for excl_year in exclude_years_test:
                year_start = pd.Timestamp(f'{excl_year}-01-01')
                year_end = pd.Timestamp(f'{excl_year}-12-31')
                if entry <= year_end and exit_ >= year_start:
                    overlaps = True
                    break
            if not overlaps:
                clean_dates.append(d)
        dates = clean_dates

    results = []
    rng = np.random.RandomState(42)

    for pred_date in dates:
        cutoff = pred_date - pd.DateOffset(months=embargo_months)
        train = df[df['date'] <= cutoff].dropna(subset=feat_xs + ['target']).copy()

        # Remove training labels that overlap excluded years
        if exclude_labels_overlapping:
            for excl_year in exclude_labels_overlapping:
                year_start = pd.Timestamp(f'{excl_year}-01-01')
                year_end = pd.Timestamp(f'{excl_year}-12-31')
                label_end = train['date'] + pd.DateOffset(months=3)
                overlap = (train['date'] <= year_end) & (label_end >= year_start)
                train = train[~overlap]

        test = df[df['date'] == pred_date].dropna(subset=feat_xs).copy()

        if len(train) < 100 or len(test) < 4:
            continue

        X_tr = train[feat_xs].values.copy()
        y_tr = train['target'].values.copy()
        X_te = test[feat_xs].values.copy()

        # Group permutation (same row permutation for all features)
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
