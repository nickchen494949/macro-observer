#!/usr/bin/env python3
"""
fetch_volume.py — daily share volume for every Yahoo-priced symbol (data/raw), for volume/turnover factors.
Same Yahoo rules as fetch_prices.py: Python urllib, strictly sequential, 5–10 s random spacing, stop on HTTP 429,
resumable. Scheduled by run_volume_later.sh to start after the dashboard's daily Yahoo batch (06:15 Beijing) so the
two never overlap with US-session live quotes.
Output: data/raw_volume/<SYMBOL>.json {symbol, dates, volume}
"""
import json, os, random, ssl, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')
OUT = os.path.join(HERE, 'data', 'raw_volume')
os.makedirs(OUT, exist_ok=True)


def fetch(sym):
    url = (f'https://{random.choice(["query1", "query2"])}.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym, safe="")}'
           f'?period1=1167609600&period2={int(time.time())}&interval=1d&includePrePost=false')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*', 'Referer': 'https://finance.yahoo.com'})
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=20) as r:
            raw = json.loads(r.read())
        res = raw['chart']['result'][0]
        ts, vol = res.get('timestamp') or [], res['indicators']['quote'][0].get('volume') or []
        d = [(time.strftime('%Y-%m-%d', time.gmtime(t)), v) for t, v in zip(ts, vol) if v is not None]
        return {'symbol': sym, 'dates': [a for a, _ in d], 'volume': [b for _, b in d]}, None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}'
    except Exception as e:  # noqa
        return None, str(e)


def main():
    syms = sorted(f[:-5] for f in os.listdir(RAW) if f.endswith('.json') and not f.startswith('_'))
    todo = [s for s in syms if not os.path.exists(os.path.join(OUT, f'{s}.json'))]
    print(len(todo), 'symbols', flush=True)
    for i, s in enumerate(todo):
        d, err = fetch(s)
        if err == 'HTTP 429':
            print('HTTP 429 — stopping', flush=True)
            sys.exit(2)
        if d and d['dates']:
            json.dump(d, open(os.path.join(OUT, f'{s}.json'), 'w'))
        print(f'[{i+1}/{len(todo)}] {s} {"ok" if d else err}', flush=True)
        time.sleep(random.uniform(5, 10))
    print('done', flush=True)


if __name__ == '__main__':
    main()
