#!/usr/bin/env python3
"""
fetch_sectors.py — sector labels for every universe ticker.

  1. Current S&P 500 members  → GICS sector from Wikipedia (data/wiki_current_constituents.csv)
  2. Former members that still have Yahoo price data → Yahoo `sector`, mapped to GICS names
     (sequential, 5–10 s random delay, stop on 429, resumable)

Output: data/sectors.csv  (ticker, sector, source)
"""
import json, os, random, sys, time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')
OUT = os.path.join(HERE, 'data', 'sectors.csv')

YAHOO_TO_GICS = {
    'Technology': 'Information Technology',
    'Financial Services': 'Financials',
    'Consumer Cyclical': 'Consumer Discretionary',
    'Consumer Defensive': 'Consumer Staples',
    'Healthcare': 'Health Care',
    'Communication Services': 'Communication Services',
    'Industrials': 'Industrials',
    'Energy': 'Energy',
    'Basic Materials': 'Materials',
    'Real Estate': 'Real Estate',
    'Utilities': 'Utilities',
}


def main():
    import yfinance as yf
    wiki = pd.read_csv(os.path.join(HERE, 'data', 'wiki_current_constituents.csv'))
    rows = {s.replace('.', '-'): (sec, 'wikipedia_gics') for s, sec in zip(wiki.Symbol, wiki['GICS Sector'])}
    if os.path.exists(OUT):
        prev = pd.read_csv(OUT)
        for t, sec, src in prev.itertuples(index=False):
            rows.setdefault(t, (sec, src))
    have = [f[:-5] for f in os.listdir(RAW) if f.endswith('.json') and not f.startswith('_')]
    etfs = {'XLK', 'XLC', 'XLY', 'XLF', 'XLI', 'XLU', 'XLE', 'XLRE', 'XLB', 'XLP', 'XLV', 'SPY', 'RSP'}
    todo = sorted(t for t in have if t not in rows and t not in etfs)
    print(f'{len(todo)} former members need a Yahoo sector', flush=True)

    def save():
        pd.DataFrame([(t, s, src) for t, (s, src) in sorted(rows.items())],
                     columns=['ticker', 'sector', 'source']).to_csv(OUT, index=False)

    for i, t in enumerate(todo):
        try:
            info = yf.Ticker(t).info or {}
            ysec = info.get('sector')
            sec = YAHOO_TO_GICS.get(ysec, 'UNKNOWN')
            rows[t] = (sec, 'yahoo')
            print(f'[{i+1}/{len(todo)}] {t} {ysec} -> {sec} | {info.get("longName")}', flush=True)
        except Exception as e:  # noqa
            msg = str(e)
            print(f'[{i+1}/{len(todo)}] {t} FAIL {msg[:120]}', flush=True)
            if '429' in msg or 'Too Many Requests' in msg:
                save(); print('429 — stopping.', flush=True); sys.exit(2)
            rows[t] = ('UNKNOWN', 'yahoo_fail')
        if (i + 1) % 10 == 0:
            save()
        time.sleep(random.uniform(5, 10))
    save()
    print('done', flush=True)


if __name__ == '__main__':
    main()
