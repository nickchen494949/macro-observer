#!/usr/bin/env python3
"""
fetch_prices.py — one-off download of daily adjusted closes for every ticker that
was ever in the S&P 500 since 2007-12 (point-in-time list from fja05680/sp500),
plus the 11 SPDR sector ETFs and benchmarks.

Respects the project's Yahoo rules (see root README):
  * Python urllib (same TLS fingerprint as fetch_yahoo.py), never Node.js
  * 5–10 s random delay between symbols, strictly sequential
  * stops immediately on HTTP 429
  * resumable: already-downloaded symbols are skipped (no repeat requests)

Output: data/raw/<SYMBOL>.json  {symbol, dates, close, adjclose}
"""
import json, os, random, ssl, sys, time, urllib.error, urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')
os.makedirs(RAW, exist_ok=True)

SECTOR_ETFS = ['XLK', 'XLC', 'XLY', 'XLF', 'XLI', 'XLU', 'XLE', 'XLRE', 'XLB', 'XLP', 'XLV']
BENCH = ['SPY', 'RSP']
PERIOD1 = 1167609600  # 2007-01-01


def yahoo_symbol(t):
    return t.replace('.', '-')


def universe():
    h = pd.read_csv(os.path.join(HERE, 'data', 'sp500_hist_components.csv'), parse_dates=['date'])
    h = h[h.date >= '2007-12-01']
    s = set()
    for t in h.tickers:
        s |= set(t.split(','))
    return sorted(s)


def fetch(sym):
    ctx = ssl.create_default_context()
    host = random.choice(['query1', 'query2'])
    url = (f'https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym, safe="")}'
           f'?period1={PERIOD1}&period2={int(time.time())}&interval=1d&events=div%7Csplit'
           f'&includeAdjustedClose=true&includePrePost=false')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*',
                                               'Referer': 'https://finance.yahoo.com'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
            raw = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'HTTP {e.code}'}
    except Exception as e:  # noqa
        return {'ok': False, 'error': str(e)}
    try:
        res = raw['chart']['result'][0]
        ts = res.get('timestamp') or []
        q = res['indicators']['quote'][0]['close']
        adj = res['indicators'].get('adjclose', [{}])[0].get('adjclose') or q
        out = {'symbol': sym, 'dates': [], 'close': [], 'adjclose': []}
        for t, c, a in zip(ts, q, adj):
            if c is None or a is None:
                continue
            out['dates'].append(time.strftime('%Y-%m-%d', time.gmtime(t)))
            out['close'].append(round(c, 4))
            out['adjclose'].append(round(a, 6))
        # split events (needed to put as-reported SEC EPS / share counts on the same basis as prices)
        sp = (res.get('events') or {}).get('splits') or {}
        out['splits'] = sorted([[time.strftime('%Y-%m-%d', time.gmtime(int(v['date']))),
                                 v.get('numerator'), v.get('denominator')] for v in sp.values()])
        return {'ok': True, 'data': out}
    except Exception as e:  # noqa
        return {'ok': False, 'error': f'parse: {e}'}


def main():
    syms = SECTOR_ETFS + BENCH + [yahoo_symbol(t) for t in universe()]
    failed_path = os.path.join(RAW, '_failed.json')
    failed = json.load(open(failed_path)) if os.path.exists(failed_path) else {}
    todo = [s for s in syms if not os.path.exists(os.path.join(RAW, f'{s}.json')) and s not in failed]

    def no_splits(s):
        p = os.path.join(RAW, f'{s}.json')
        return os.path.exists(p) and 'splits' not in json.load(open(p))
    # files saved before split events were recorded → refetch once (after the new symbols)
    todo += [s for s in syms if no_splits(s)]
    print(f'{len(syms)} symbols, {len(todo)} to fetch', flush=True)
    for i, s in enumerate(todo):
        r = fetch(s)
        if r['ok'] and r['data']['dates']:
            json.dump(r['data'], open(os.path.join(RAW, f'{s}.json'), 'w'))
            print(f'[{i+1}/{len(todo)}] {s} ok {r["data"]["dates"][0]}..{r["data"]["dates"][-1]}', flush=True)
        else:
            err = r.get('error', 'empty')
            print(f'[{i+1}/{len(todo)}] {s} FAIL {err}', flush=True)
            if err == 'HTTP 429':
                print('HTTP 429 — Yahoo rate limit. Stopping immediately (wait 12–24h).', flush=True)
                sys.exit(2)
            failed[s] = err
            json.dump(failed, open(failed_path, 'w'), indent=1)
        time.sleep(random.uniform(5, 10))
    print('done', flush=True)


if __name__ == '__main__':
    main()
