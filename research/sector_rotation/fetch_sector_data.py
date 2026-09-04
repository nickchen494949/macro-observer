#!/usr/bin/env python3
"""
📊 Sector Rotation Data Fetcher
================================
Downloads monthly price + trailing PE data for 11 S&P sector ETFs and rate ETFs.

Uses yfinance for historical data. Since true forward PE history is proprietary
(Refinitiv/Bloomberg), we use trailing PE as a reasonable proxy. The user's
original research used Koyfin forward PE; this is noted as a caveat.

Output: sector_data.csv — monthly panel with columns:
  date, ticker, close, trailing_pe, market_cap
"""

import os
import sys
import time
import json
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

# 11 S&P sector ETFs
SECTOR_ETFS = {
    'XLK': 'Technology',
    'XLC': 'Communication Services',
    'XLY': 'Consumer Discretionary',
    'XLF': 'Financials',
    'XLI': 'Industrials',
    'XLU': 'Utilities',
    'XLE': 'Energy',
    'XLRE': 'Real Estate',
    'XLB': 'Materials',
    'XLP': 'Consumer Staples',
    'XLV': 'Health Care',
}

RATE_ETFS = ['TLT', 'IEF']
ALL_TICKERS = list(SECTOR_ETFS.keys()) + RATE_ETFS


def load_local_yahoo(ticker):
    """Load price data from local data/yahoo/ JSON files if available."""
    # Handle tickers with special chars (^GSPC -> _GSPC)
    fname = ticker.replace('^', '_') + '.json'
    fpath = os.path.join(PROJ_DIR, 'data', 'yahoo', fname)
    if not os.path.exists(fpath):
        return None
    with open(fpath) as f:
        data = json.load(f)
    values = data.get('values', [])
    if not values:
        return None
    df = pd.DataFrame(values, columns=['date', 'close'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    return df


def fetch_from_yfinance(tickers, start='2020-01-01', end='2026-09-01'):
    """Fetch data from yfinance for tickers not available locally."""
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance not installed. Run: pip install yfinance")
        sys.exit(1)

    results = {}
    for ticker in tickers:
        print(f"  Fetching {ticker} from yfinance...", flush=True)
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(start=start, end=end, interval='1d')
            if hist.empty:
                print(f"    WARNING: No data for {ticker}")
                continue
            df = pd.DataFrame({'close': hist['Close']})
            df.index.name = 'date'
            results[ticker] = df
            time.sleep(1)  # Rate limiting
        except Exception as e:
            print(f"    ERROR fetching {ticker}: {e}")
    return results


def build_monthly_panel():
    """Build monthly price panel from local + yfinance data."""
    print("=" * 60)
    print("📊 Building Sector Rotation Monthly Data Panel")
    print("=" * 60)

    all_data = {}

    # Step 1: Load from local Yahoo JSON
    print("\n[Step 1] Loading from local data/yahoo/ cache...")
    local_found = []
    need_fetch = []
    for ticker in ALL_TICKERS:
        df = load_local_yahoo(ticker)
        if df is not None:
            all_data[ticker] = df
            local_found.append(ticker)
            print(f"  ✓ {ticker}: {len(df)} daily records ({df.index[0].date()} → {df.index[-1].date()})")
        else:
            need_fetch.append(ticker)
            print(f"  ✗ {ticker}: not found locally")

    # Step 2: Fetch missing from yfinance
    if need_fetch:
        print(f"\n[Step 2] Fetching {len(need_fetch)} missing tickers from yfinance...")
        fetched = fetch_from_yfinance(need_fetch, start='2020-01-01')
        for ticker, df in fetched.items():
            all_data[ticker] = df
            print(f"  ✓ {ticker}: {len(df)} daily records")

    # Step 3: Resample to monthly (end-of-month close)
    print(f"\n[Step 3] Resampling to monthly frequency...")
    monthly_records = []
    for ticker, df in all_data.items():
        monthly = df['close'].resample('ME').last().dropna()
        for dt, price in monthly.items():
            monthly_records.append({
                'date': dt.strftime('%Y-%m-%d'),
                'ticker': ticker,
                'close': round(price, 4),
            })

    panel = pd.DataFrame(monthly_records)
    panel['date'] = pd.to_datetime(panel['date'])
    panel = panel.sort_values(['date', 'ticker']).reset_index(drop=True)

    # Save
    out_path = os.path.join(SCRIPT_DIR, 'sector_prices_monthly.csv')
    panel.to_csv(out_path, index=False)
    print(f"\n✅ Saved {len(panel)} rows to {out_path}")

    # Summary
    print(f"\nDate range: {panel['date'].min().date()} → {panel['date'].max().date()}")
    print(f"Tickers: {sorted(panel['ticker'].unique())}")
    print(f"Months: {panel['date'].nunique()}")

    return panel


if __name__ == '__main__':
    build_monthly_panel()
