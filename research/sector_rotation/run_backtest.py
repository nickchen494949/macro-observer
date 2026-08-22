#!/usr/bin/env python3
"""
🔬 Sector Rotation Backtest — REAL DATA ONLY
=============================================

Data:
  - Forward PE: Koyfin daily f_pe CSVs (pe_data/*.csv), ~2003→2026
  - Prices: local Yahoo cache (data/yahoo/*.json) + yfinance fallback
  - TLT/IEF: local cache or yfinance

Signals (all point-in-time):
  ① Relative Forward PE — PE z-score vs own 24-month history (cheaper = better)
  ② EPS Revision Proxy  — 3M change in implied Forward EPS = Price / PE
  ③ 6M Momentum — trailing price return
  ④ Rate Regime — TLT 3M trend → conditioning variable

Backtest:
  - Monthly rebalance (end-of-month)
  - Top 3 vs Bottom 3 sectors
  - Default sample: 2023-01 → 2026-06
"""

import os
import sys
import json
import warnings
import argparse
import pandas as pd
import numpy as np
from scipy import stats

warnings.filterwarnings('ignore')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
PE_DIR = os.path.join(SCRIPT_DIR, 'pe_data')

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

# Koyfin PE CSV → ETF ticker mapping
PE_FILE_MAP = {
    '20517_information_technology.csv': 'XLK',
    '20518_communication_services.csv': 'XLC',
    '20519_consumer_discretionary.csv': 'XLY',
    '20520_financials.csv':             'XLF',
    '20521_industrials.csv':            'XLI',
    '20522_utilities.csv':              'XLU',
    '20523_energy.csv':                 'XLE',
    '20524_real_estate.csv':            'XLRE',
    '20525_materials.csv':              'XLB',
    '20526_consumer_staples.csv':       'XLP',
    '20527_health_care.csv':            'XLV',
}

SECTOR_NAMES = {
    'XLK': 'Technology',     'XLC': 'Comm Svc',
    'XLY': 'Cons Disc',      'XLF': 'Financials',
    'XLI': 'Industrials',    'XLU': 'Utilities',
    'XLE': 'Energy',         'XLRE': 'Real Estate',
    'XLB': 'Materials',      'XLP': 'Cons Staples',
    'XLV': 'Health Care',
}

SECTOR_TICKERS = list(SECTOR_NAMES.keys())

PE_WINDOW = 24         # months rolling for PE z-score
EPS_REV_WINDOW = 3     # months for EPS revision
MOM_WINDOW = 6         # months for momentum
RATE_WINDOW = 3        # months for TLT trend
TOP_N = 3
DEFAULT_START = '2023-01'
DEFAULT_END = '2026-06'


# ═══════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════

def load_koyfin_pe():
    """Load REAL Koyfin Forward PE from pe_data/*.csv → monthly panel."""
    frames = []
    for fname, ticker in PE_FILE_MAP.items():
        fpath = os.path.join(PE_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  ✗ Missing: {fname}")
            continue
        df = pd.read_csv(fpath)
        df.columns = [c.strip() for c in df.columns]
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['forward_pe'])
        df['ticker'] = ticker

        # Resample daily → monthly (end-of-month average of last 5 trading days)
        df = df.set_index('date').sort_index()
        monthly = df['forward_pe'].resample('ME').last().dropna()
        mdf = monthly.to_frame('forward_pe').reset_index()
        mdf['ticker'] = ticker
        frames.append(mdf)
        print(f"  ✓ {ticker:4s} ({fname}): "
              f"{df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}, "
              f"{len(mdf)} months")

    if not frames:
        print("  ✗ No PE data loaded!")
        return None

    panel = pd.concat(frames, ignore_index=True)
    return panel


def load_local_yahoo(ticker):
    """Load price from local Yahoo JSON cache."""
    fname = ticker.replace('^', '_') + '.json'
    fpath = os.path.join(PROJ_DIR, 'data', 'yahoo', fname)
    if not os.path.exists(fpath):
        return None
    with open(fpath) as f:
        data = json.load(f)
    vals = data.get('values', [])
    if not vals:
        return None
    df = pd.DataFrame(vals, columns=['date', 'close'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    return df


def fetch_yfinance(tickers):
    """Fetch missing tickers from yfinance."""
    import yfinance as yf
    import time
    results = {}
    for t in tickers:
        print(f"  ↓ {t} from yfinance...", flush=True)
        try:
            hist = yf.Ticker(t).history(start='2002-01-01', end='2026-09-01', interval='1d')
            if hist.empty:
                continue
            df = pd.DataFrame({'close': hist['Close']})
            df.index = df.index.tz_localize(None)
            df.index.name = 'date'
            results[t] = df
            time.sleep(1.5)
        except Exception as e:
            print(f"    ✗ {t}: {e}")
    return results


def load_prices():
    """Load all prices: local first, yfinance for gaps."""
    need = SECTOR_TICKERS + ['TLT', 'IEF']
    prices = {}
    missing = []
    for t in need:
        df = load_local_yahoo(t)
        if df is not None and len(df) > 100:
            prices[t] = df
        else:
            missing.append(t)

    if missing:
        print(f"  Fetching {missing} from yfinance...")
        prices.update(fetch_yfinance(missing))

    return prices


def to_monthly(prices):
    """Daily → monthly EOM panel."""
    frames = []
    for t, df in prices.items():
        if df.index.tz is not None:
            df = df.copy()
            df.index = df.index.tz_localize(None)
        m = df['close'].resample('ME').last().dropna().to_frame('close')
        m['ticker'] = t
        m.index.name = 'date'
        frames.append(m.reset_index())
    panel = pd.concat(frames, ignore_index=True)
    panel['date'] = pd.to_datetime(panel['date']).dt.tz_localize(None)
    return panel.sort_values(['date', 'ticker']).reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════
# SIGNALS
# ═══════════════════════════════════════════════════════════════

def sig_valuation(panel, pe):
    """① Relative Forward PE z-score (cheaper = higher score)."""
    m = panel[panel['ticker'].isin(SECTOR_TICKERS)].merge(
        pe[['date', 'ticker', 'forward_pe']], on=['date', 'ticker'], how='inner'
    )
    out = []
    for t in SECTOR_TICKERS:
        s = m[m['ticker'] == t].sort_values('date').copy()
        if len(s) < 12:
            continue
        s['pe_z'] = s['forward_pe'].rolling(PE_WINDOW, min_periods=12).apply(
            lambda x: (x.iloc[-1] - x.mean()) / (x.std() + 1e-9)
        )
        s['valuation'] = -s['pe_z']  # cheaper = better
        out.append(s[['date', 'ticker', 'close', 'valuation', 'forward_pe']])
    return pd.concat(out, ignore_index=True) if out else None


def sig_eps_revision(panel, pe):
    """② EPS revision proxy: 3M change in Price/PE."""
    m = panel[panel['ticker'].isin(SECTOR_TICKERS)].merge(
        pe[['date', 'ticker', 'forward_pe']], on=['date', 'ticker'], how='inner'
    )
    out = []
    for t in SECTOR_TICKERS:
        s = m[m['ticker'] == t].sort_values('date').copy()
        if len(s) < EPS_REV_WINDOW + 1:
            continue
        s['fwd_eps'] = s['close'] / s['forward_pe'].replace(0, np.nan)
        s['eps_rev'] = s['fwd_eps'].pct_change(EPS_REV_WINDOW)
        out.append(s[['date', 'ticker', 'close', 'eps_rev', 'fwd_eps']])
    return pd.concat(out, ignore_index=True) if out else None


def sig_momentum(panel):
    """③ 6M price momentum."""
    out = []
    for t in SECTOR_TICKERS:
        s = panel[panel['ticker'] == t].sort_values('date').copy()
        if len(s) < MOM_WINDOW + 1:
            continue
        s['momentum'] = s['close'].pct_change(MOM_WINDOW)
        out.append(s[['date', 'ticker', 'close', 'momentum']])
    return pd.concat(out, ignore_index=True)


def rate_regime(panel):
    """TLT 3M return → rising/falling yields."""
    tlt = panel[panel['ticker'] == 'TLT'].sort_values('date').copy()
    tlt['tlt_3m'] = tlt['close'].pct_change(RATE_WINDOW)
    tlt['rising'] = (tlt['tlt_3m'] < 0).astype(int)
    return tlt[['date', 'tlt_3m', 'rising']]


# ═══════════════════════════════════════════════════════════════
# COMPOSITE
# ═══════════════════════════════════════════════════════════════

def composite(dfs_cols_weights):
    """Cross-sectional z-score → weighted sum."""
    base = None
    items = []
    for df, col, w in dfs_cols_weights:
        if df is None:
            continue
        sub = df[['date', 'ticker', 'close', col]].dropna(subset=[col])
        if base is None:
            base = sub.copy()
        else:
            base = base.merge(sub[['date', 'ticker', col]],
                              on=['date', 'ticker'], how='inner')
        items.append((col, w))

    if base is None or len(base) == 0:
        return None

    for col, w in items:
        z = col + '_z'
        base[z] = base.groupby('date')[col].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9) if len(x) > 1 else 0
        )

    base['composite'] = sum(w * base[c + '_z'] for c, w in items)
    return base


# ═══════════════════════════════════════════════════════════════
# BACKTEST
# ═══════════════════════════════════════════════════════════════

def backtest(sig_df, col, regime_df, holding=1, start=DEFAULT_START,
             end=DEFAULT_END, regime_filter=None):
    """Monthly L/S backtest. Top 3 − Bottom 3."""
    df = sig_df[sig_df['ticker'].isin(SECTOR_TICKERS)].dropna(subset=[col]).copy()

    # Forward returns
    px = df.pivot_table(index='date', columns='ticker', values='close', aggfunc='last')
    fwd = px.pct_change(holding).shift(-holding)
    fl = fwd.stack().reset_index()
    fl.columns = ['date', 'ticker', 'fwd_ret']

    df = df.merge(fl, on=['date', 'ticker'], how='inner')
    df = df[(df['date'] >= start) & (df['date'] <= end)]
    df = df.merge(regime_df[['date', 'rising']], on='date', how='left')

    if regime_filter == 'rising':
        df = df[df['rising'] == 1]
    elif regime_filter == 'falling':
        df = df[df['rising'] == 0]

    months = []
    ics = []
    for dt, g in df.groupby('date'):
        g = g.dropna(subset=['fwd_ret', col])
        if len(g) < TOP_N * 2:
            continue
        g = g.sort_values(col, ascending=False)
        top = g.head(TOP_N)
        bot = g.tail(TOP_N)
        sp = top['fwd_ret'].mean() - bot['fwd_ret'].mean()
        ic = stats.spearmanr(g[col], g['fwd_ret'])[0] if len(g) >= 5 else np.nan
        ics.append(ic)
        months.append({
            'date': dt,
            'top3': top['fwd_ret'].mean(),
            'bot3': bot['fwd_ret'].mean(),
            'spread': sp,
            'ew': g['fwd_ret'].mean(),
            'ic': ic,
            'top_names': ','.join(top['ticker'].tolist()),
            'bot_names': ','.join(bot['ticker'].tolist()),
        })

    if not months:
        return None

    mdf = pd.DataFrame(months)
    n = len(mdf)
    sp = mdf['spread']
    mu = sp.mean()
    ann = mu * 12 if holding == 1 else mu * (12 / holding)

    if holding > 1:
        t = _nw_t(sp.values, holding)
    else:
        se = sp.std() / np.sqrt(n)
        t = mu / se if se > 0 else 0

    return {
        'n': n, 'ann': ann, 't': t,
        'wr': (sp > 0).mean(),
        'ic': np.nanmean(ics),
        'top3_cagr': (1 + mdf['top3']).prod() ** (12 / n) - 1 if n > 0 else 0,
        'ew_cagr': (1 + mdf['ew']).prod() ** (12 / n) - 1 if n > 0 else 0,
        'df': mdf,
    }


def _nw_t(x, lags=3):
    n, mu = len(x), np.mean(x)
    e = x - mu
    v = np.mean(e ** 2)
    for j in range(1, lags + 1):
        v += 2 * (1 - j / (lags + 1)) * np.mean(e[j:] * e[:-j])
    se = np.sqrt(v / n)
    return mu / se if se > 0 else 0


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def pct(x): return f"{x*100:+.1f}%"
def f2(x):  return f"{x:.2f}"
def f3(x):  return f"{x:+.3f}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--holding', type=int, default=1, choices=[1, 3])
    parser.add_argument('--start', default=DEFAULT_START)
    parser.add_argument('--end', default=DEFAULT_END)
    args = parser.parse_args()

    print("=" * 72)
    print("🔬 SECTOR ROTATION BACKTEST — Koyfin Forward PE + Real Prices")
    print("=" * 72)

    # ── 1. Load PE ──
    print("\n[1] Loading Koyfin Forward PE (pe_data/)...")
    pe = load_koyfin_pe()
    if pe is None:
        print("FATAL: No PE data. Run download script first.")
        sys.exit(1)
    print(f"\n  Total: {len(pe):,d} sector-month PE observations")
    print(f"  Tickers: {sorted(pe['ticker'].unique())}")

    # ── 2. Load prices ──
    print("\n[2] Loading prices...")
    prices = load_prices()
    avail = [t for t in SECTOR_TICKERS if t in prices]
    miss = [t for t in SECTOR_TICKERS if t not in prices]
    print(f"  Available: {avail}")
    if miss:
        print(f"  ⚠ Missing: {miss}")

    panel = to_monthly(prices)
    print(f"  Panel: {len(panel):,d} rows, "
          f"{panel['date'].min().strftime('%Y-%m')} → {panel['date'].max().strftime('%Y-%m')}")

    # ── 3. Signals ──
    print("\n[3] Computing signals...")
    val = sig_valuation(panel, pe)
    eps = sig_eps_revision(panel, pe)
    mom = sig_momentum(panel)
    rr = rate_regime(panel)

    for name, df, col in [('Valuation', val, 'valuation'),
                           ('EPS Rev', eps, 'eps_rev'),
                           ('Momentum', mom, 'momentum')]:
        if df is not None:
            n = df[col].notna().sum()
            rng = f"{df['date'].min().strftime('%Y-%m')} → {df['date'].max().strftime('%Y-%m')}"
            print(f"  ✓ {name:12s}: {n:,d} obs  ({rng})")
        else:
            print(f"  ✗ {name}")

    rising_n = (rr['rising'] == 1).sum()
    print(f"  ✓ Rate regime: {rising_n} rising / {len(rr) - rising_n} falling months")

    # ── 4. Composites ──
    c_ve = composite([(val, 'valuation', 1.0), (eps, 'eps_rev', 1.0)])
    c_vem = composite([(val, 'valuation', 1.0), (eps, 'eps_rev', 1.0),
                        (mom, 'momentum', 0.5)])
    c_all = composite([(val, 'valuation', 1.0), (eps, 'eps_rev', 1.0),
                        (mom, 'momentum', 1.0)])

    # ── 5. Backtest ──
    h = args.holding
    s, e = args.start, args.end
    print(f"\n[4] Running backtests (hold={h}M, {s}→{e})...")
    print("=" * 72)

    header = f"{'Signal':<20s} {'Hold':>4s} {'Regime':<10s} {'AnnSprd':>8s} " \
             f"{'t':>6s} {'WR':>5s} {'IC':>7s} {'Top3':>7s} {'EqWt':>7s} {'N':>4s}"
    print(header)
    print("─" * 72)

    rows_csv = []

    def run(name, df, col, regime=None, hold=h):
        if df is None:
            return
        r = backtest(df, col, rr, holding=hold, start=s, end=e,
                     regime_filter=regime)
        if r is None:
            return
        rlabel = regime or 'all'
        line = f"{name:<20s} {hold:>3d}M {rlabel:<10s} " \
               f"{pct(r['ann']):>8s} {f2(r['t']):>6s} " \
               f"{pct(r['wr']):>5s} {f3(r['ic']):>7s} " \
               f"{pct(r['top3_cagr']):>7s} {pct(r['ew_cagr']):>7s} {r['n']:>4d}"
        print(line)
        rows_csv.append({
            'signal': name, 'hold': f'{hold}M', 'regime': rlabel,
            'ann_spread': round(r['ann'] * 100, 2),
            't_stat': round(r['t'], 2),
            'win_rate': round(r['wr'] * 100, 1),
            'rank_ic': round(r['ic'], 3),
            'top3_cagr': round(r['top3_cagr'] * 100, 2),
            'ew_cagr': round(r['ew_cagr'] * 100, 2),
            'n_months': r['n'],
        })
        # Save detail
        r['df'].to_csv(os.path.join(SCRIPT_DIR,
                       f'detail_{name}_{rlabel}_h{hold}.csv'), index=False)

    # --- Individual signals ---
    print("\n── Individual Signals ──")
    run('valuation', val, 'valuation')
    run('eps_revision', eps, 'eps_rev')
    run('momentum', mom, 'momentum')

    # --- Composites ---
    print("\n── Composites ──")
    run('val+eps', c_ve, 'composite')
    run('val+eps+mom', c_vem, 'composite')
    run('all_equal', c_all, 'composite')

    # --- Regime splits ---
    print("\n── Regime Splits (Valuation) ──")
    run('valuation', val, 'valuation', regime='rising')
    run('valuation', val, 'valuation', regime='falling')

    print("\n── Regime Splits (Val+EPS) ──")
    run('val+eps', c_ve, 'composite', regime='rising')
    run('val+eps', c_ve, 'composite', regime='falling')

    print("\n── Regime Splits (EPS Rev) ──")
    run('eps_revision', eps, 'eps_rev', regime='rising')
    run('eps_revision', eps, 'eps_rev', regime='falling')

    # --- 3M holding ---
    if h == 1:
        print("\n── 3-Month Holding Period ──")
        run('valuation', val, 'valuation', hold=3)
        run('eps_revision', eps, 'eps_rev', hold=3)
        run('val+eps', c_ve, 'composite', hold=3)
        run('val+eps+mom', c_vem, 'composite', hold=3)

    # ── Save ──
    if rows_csv:
        out = pd.DataFrame(rows_csv)
        outpath = os.path.join(SCRIPT_DIR, 'backtest_results.csv')
        out.to_csv(outpath, index=False)
        print(f"\n✅ Results → {outpath}")

    # ── Summary ──
    print("\n" + "=" * 72)
    print("📝 DATA AUDIT")
    print("=" * 72)
    print(f"""
  Forward PE source:  Koyfin f_pe (daily, resampled to monthly EOM)
  PE files:           {PE_DIR}/
  Price source:       local Yahoo cache + yfinance
  Sample:             {s} → {e}
  Point-in-time note: Koyfin f_pe is analyst consensus forward PE.
                      NOT retroactively revised like some S&P DJI feeds.
                      But see README caveat about Energy 2020 etc.
""")


if __name__ == '__main__':
    main()
