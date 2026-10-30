#!/usr/bin/env python3
"""convert_wiki_bulk.py — Nasdaq Data Link WIKI/PRICES full export (data/wiki_bulk/WIKI_PRICES.zip, snapshot of the
frozen 2018-03-27 table) → data/wiki_bulk/wiki_prices.parquet (ticker, date, close, adj_close, volume, split_ratio),
rows from 2006-12-01. Quality of WIKI vs Yahoo is documented in data/raw_wiki/_validation.json."""
import os, zipfile
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
z = zipfile.ZipFile(os.path.join(HERE, 'data', 'wiki_bulk', 'WIKI_PRICES.zip'))
name = z.namelist()[0]
parts = []
for ch in pd.read_csv(z.open(name), usecols=['ticker', 'date', 'close', 'adj_close', 'volume', 'split_ratio'],
                      parse_dates=['date'], chunksize=2_000_000):
    parts.append(ch[ch.date >= '2006-12-01'])
df = pd.concat(parts, ignore_index=True)
df['ticker'] = df.ticker.str.replace('_', '-', regex=False)
df.to_parquet(os.path.join(HERE, 'data', 'wiki_bulk', 'wiki_prices.parquet'), index=False)
print(len(df), 'rows', df.ticker.nunique(), 'tickers', df.date.min().date(), df.date.max().date())
