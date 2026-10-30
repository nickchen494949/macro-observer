#!/usr/bin/env python3
"""
fetch_smallcap.py — daily prices (close, adjusted close, splits, volume) for the BROAD US universe beyond S&P 500 /
Nasdaq-100: every NYSE / Nasdaq company that filed a 10-K / 10-Q with the SEC since 2017 (data/smallcap_candidates.csv,
from SEC company_tickers_exchange.json; SPACs excluded), not already priced in data/raw, raw_ndx or raw_tiingo.
These are TODAY's listings — companies delisted before today are covered only by the WIKI bulk file (to 2018-03);
post-2018 delistings are a known survivorship gap (documented in the report).

Yahoo rules (same as fetch_prices.py): Python urllib, strictly sequential, 5–10 s random spacing, stop on HTTP 429,
resumable; runs only inside the Beijing window 07:15–15:45 (after the dashboard's daily batch, before the US
pre-market live-quote window) — run_smallcap_window.sh restarts it in the next window.
Output: data/raw_smallcap/<SYMBOL>.json {symbol, dates, close, adjclose, volume, splits, source}; data/raw_smallcap/_log.json
"""
import json, os, random, ssl, sys, time, urllib.error, urllib.request
from datetime import datetime

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'raw_smallcap')
os.makedirs(OUT, exist_ok=True)
PERIOD1 = 1167609600          # 2007-01-01


def safe_hours():
    hm = int(datetime.now().strftime('%H%M'))
    return 715 <= hm <= 1545


def in_window():
    # user instruction 2026-10-29 17:36: keep downloading outside the safe window (SMALLCAP_NO_WINDOW=1); outside the
    # safe hours the spacing is widened (see pause()) because the dashboard's live-quote requests run at the same time
    return safe_hours() or os.environ.get('SMALLCAP_NO_WINDOW') == '1'


def pause():
    time.sleep(random.uniform(5, 10) if safe_hours() else random.uniform(10, 16))


def fetch(sym):
    url = (f'https://{random.choice(["query1", "query2"])}.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym, safe="")}'
           f'?period1={PERIOD1}&period2={int(time.time())}&interval=1d&events=div%7Csplit&includeAdjustedClose=true&includePrePost=false')
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
        ts = res.get('timestamp') or []
        q = res['indicators']['quote'][0]
        adj = res['indicators'].get('adjclose', [{}])[0].get('adjclose') or q['close']
        out = {'symbol': sym, 'source': 'yahoo', 'dates': [], 'close': [], 'adjclose': [], 'volume': []}
        for t, c, a, v in zip(ts, q['close'], adj, q.get('volume') or [None] * len(ts)):
            if c is None or a is None:
                continue
            out['dates'].append(time.strftime('%Y-%m-%d', time.gmtime(t)))
            out['close'].append(round(c, 4))
            out['adjclose'].append(round(a, 6))
            out['volume'].append(v)
        sp = (res.get('events') or {}).get('splits') or {}
        out['splits'] = sorted([[time.strftime('%Y-%m-%d', time.gmtime(int(v['date']))), v.get('numerator'), v.get('denominator')]
                                for v in sp.values()])
        return out, None
    except Exception as e:  # noqa
        return None, f'parse: {e}'


def main():
    c = pd.read_csv(os.path.join(HERE, 'data', 'smallcap_candidates.csv'))
    logp = os.path.join(OUT, '_log.json')
    log = json.load(open(logp)) if os.path.exists(logp) else {}
    todo = [s for s in c.ysym if s not in log]          # first pass
    print(f'{len(todo)} symbols left', flush=True)
    for i, s in enumerate(todo):
        if not in_window():
            print('outside the 07:15-15:45 Beijing window — pausing', flush=True)
            sys.exit(3)
        d, err = fetch(s)
        if err == 'HTTP 429':
            print('HTTP 429 — Yahoo rate limit. Stopping immediately.', flush=True)
            json.dump(log, open(logp, 'w'))
            sys.exit(2)
        if d and d['dates']:
            json.dump(d, open(os.path.join(OUT, f'{s}.json'), 'w'))
            log[s] = f"ok {d['dates'][0]}..{d['dates'][-1]}"
        else:
            log[s] = err or 'empty'
        if i % 25 == 0:
            print(f'[{i+1}/{len(todo)}] {s} {log[s]}', flush=True)
            json.dump(log, open(logp, 'w'))
        pause()
    json.dump(log, open(logp, 'w'))
    # one retry pass over every symbol whose first attempt did not return data (external audit 2026-10-29: a logged
    # failure must not count as "downloaded"); the exam requires this pass to be complete
    if not log.get('_retry_done'):
        retry = [s for s in c.ysym if not str(log.get(s, '')).startswith('ok')]
        print(f'retry pass: {len(retry)} symbols', flush=True)
        for s in retry:
            if not in_window():
                print('outside the window — pausing retry pass', flush=True)
                json.dump(log, open(logp, 'w'))
                sys.exit(3)
            d, err = fetch(s)
            if err == 'HTTP 429':
                json.dump(log, open(logp, 'w'))
                sys.exit(2)
            if d and d['dates']:
                json.dump(d, open(os.path.join(OUT, f'{s}.json'), 'w'))
                log[s] = f"ok {d['dates'][0]}..{d['dates'][-1]} (retry)"
            else:
                log[s] = f"failed twice: {err or 'empty'}"
            json.dump(log, open(logp, 'w'))
            pause()
        log['_retry_done'] = True
        json.dump(log, open(logp, 'w'))
    print('done', flush=True)


if __name__ == '__main__':
    main()
