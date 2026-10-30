#!/usr/bin/env python3
"""
fetch_wiki_crosscheck.py — identity cross-check source. Downloads WIKI history for every S&P member
(spell before 2018) that IS priced from Yahoo, so Yahoo's history can be compared with an independent
source. Catches "acquirer took the target's ticker" errors (Yahoo JCI before 2016 = Tyco, etc.):
Yahoo silently re-labels the old history, WIKI froze before many of those events.
Output: data/raw_wiki_check/<SYMBOL>.json  (same format as fetch_wiki.py). 1 request / 1.5 s.
"""
import json, os, time
import pandas as pd
from fetch_wiki import fetch, key

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'raw_wiki_check')
os.makedirs(OUT, exist_ok=True)


def main():
    k = key()
    sp = pd.read_csv(os.path.join(HERE, 'data', 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    sp = sp[(sp.end_date.isna() | (sp.end_date >= '2007-12-01')) & (sp.start_date <= '2018-03-27')]
    todo = sorted(t for t in sp.ticker.unique() if os.path.exists(os.path.join(HERE, 'data', 'raw', f"{t.replace('.', '-')}.json")))
    logp = os.path.join(OUT, '_log.json')
    log = json.load(open(logp)) if os.path.exists(logp) else {}
    todo = [t for t in todo if t not in log]
    print(len(todo), 'tickers', flush=True)
    for i, t in enumerate(todo):
        rows, err = fetch(t.replace('-', '.'), k)
        if err or not rows:
            log[t] = err or 'not in WIKI'
        else:
            df = pd.DataFrame(rows, columns=['ticker', 'date', 'close', 'adj_close', 'split_ratio']).sort_values('date')
            json.dump({'symbol': t.replace('.', '-'), 'source': 'wiki', 'dates': df.date.tolist(),
                       'close': df.close.tolist(), 'adjclose': df.adj_close.tolist()},
                      open(os.path.join(OUT, f"{t.replace('.', '-')}.json"), 'w'))
            log[t] = 'ok'
        if i % 25 == 0:
            print(f'[{i+1}/{len(todo)}] {t} {log[t]}', flush=True)
            json.dump(log, open(logp, 'w'))
        time.sleep(1.5)
    json.dump(log, open(logp, 'w'))
    print('done', flush=True)


if __name__ == '__main__':
    main()
