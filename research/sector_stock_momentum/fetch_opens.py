#!/usr/bin/env python3
"""
fetch_opens.py — daily OPEN prices for next-day-open execution (ML2_SPEC.md §2).
  Yahoo symbols of the S&P store (data/raw): open, close, adjclose → adjusted open = open × adjclose / close
  (full precision, no rounding). Same Yahoo rules as fetch_prices.py: Python urllib, strictly sequential, 5–10 s
  spacing (10–16 s outside 07:15–15:45 Beijing, when the dashboard's live quotes run), stop on HTTP 429, resumable.
  WIKI: adj_open is taken from the local bulk export (wiki_open mode, no download).
Output: data/raw_open/<SYMBOL>.json {symbol, source, dates, open, close, adjclose, adj_open}; data/raw_open/_log.json;
        data/wiki_bulk/wiki_open.parquet
"""
import json, os, random, ssl, sys, time, urllib.error, urllib.request, zipfile
from datetime import datetime

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'raw_open')
os.makedirs(OUT, exist_ok=True)


def pause():
    hm = int(datetime.now().strftime('%H%M'))
    time.sleep(random.uniform(5, 10) if 715 <= hm <= 1545 else random.uniform(10, 16))


def fetch(sym):
    url = (f'https://{random.choice(["query1", "query2"])}.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym, safe="")}'
           f'?period1=1167609600&period2={int(time.time())}&interval=1d&includeAdjustedClose=true&includePrePost=false')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*', 'Referer': 'https://finance.yahoo.com'})
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=20) as r:
            raw = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}'
    except Exception as e:  # noqa
        return None, str(e)
    try:
        res = raw['chart']['result'][0]
        q = res['indicators']['quote'][0]
        adj = res['indicators'].get('adjclose', [{}])[0].get('adjclose') or q['close']
        out = {'symbol': sym, 'source': 'yahoo', 'dates': [], 'open': [], 'close': [], 'adjclose': [], 'adj_open': []}
        for t, o, c, a in zip(res.get('timestamp') or [], q['open'], q['close'], adj):
            if o is None or c is None or a is None or c == 0:
                continue
            out['dates'].append(time.strftime('%Y-%m-%d', time.gmtime(t)))
            out['open'].append(o)
            out['close'].append(c)
            out['adjclose'].append(a)
            out['adj_open'].append(o * a / c)
        return out, None
    except Exception as e:  # noqa
        return None, f'parse: {e}'


def yahoo():
    syms = sorted(f[:-5] for f in os.listdir(os.path.join(HERE, 'data', 'raw')) if f.endswith('.json') and not f.startswith('_'))
    logp = os.path.join(OUT, '_log.json')
    log = json.load(open(logp)) if os.path.exists(logp) else {}
    todo = [s for s in syms if s not in log]
    print(len(todo), 'symbols', flush=True)
    for i, s in enumerate(todo):
        d, err = fetch(s)
        if err == 'HTTP 429':
            json.dump(log, open(logp, 'w'))
            print('HTTP 429 — stopping', flush=True)
            sys.exit(2)
        if d and d['dates']:
            json.dump(d, open(os.path.join(OUT, f'{s}.json'), 'w'))
            log[s] = 'ok'
        else:
            log[s] = err or 'empty'
        if i % 25 == 0:
            print(f'[{i+1}/{len(todo)}] {s} {log[s]}', flush=True)
            json.dump(log, open(logp, 'w'))
        pause()
    json.dump(log, open(logp, 'w'))
    print('done', flush=True)


def wiki_open():
    z = zipfile.ZipFile(os.path.join(HERE, 'data', 'wiki_bulk', 'WIKI_PRICES.zip'))
    parts = [ch[ch.date >= '2006-12-01'] for ch in pd.read_csv(z.open(z.namelist()[0]), usecols=['ticker', 'date', 'adj_open'],
                                                              parse_dates=['date'], chunksize=2_000_000)]
    df = pd.concat(parts, ignore_index=True)
    df['ticker'] = df.ticker.str.replace('_', '-', regex=False)
    df.to_parquet(os.path.join(HERE, 'data', 'wiki_bulk', 'wiki_open.parquet'), index=False)
    print('wiki opens', len(df))


if __name__ == '__main__':
    {'yahoo': yahoo, 'wiki_open': wiki_open}[sys.argv[1]]()
