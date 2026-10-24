#!/usr/bin/env python3
"""
fetch_yahoo_live.py — latest price INCLUDING pre/post-market for one symbol (ONE request).
Called by server.js:  python3 fetch_yahoo_live.py SYMBOL
Prints JSON: {"ok":true,"symbol":"XLK","price":..., "price_ts":..., "prev_close":...,
              "pre_start":..., "reg_start":..., "reg_end":..., "session":"pre|regular|post|closed"}

Same rules as fetch_yahoo.py: Python urllib (Node.js gets TLS-fingerprint blocked by Yahoo),
never call this in a tight loop — the server enforces a cooldown and a 5-10s delay between symbols.
"""
import sys, json, urllib.request, urllib.error, ssl, random


def fetch(symbol):
    ctx = ssl.create_default_context()
    encoded = urllib.request.quote(symbol, safe='')
    host = random.choice(['query1', 'query2'])
    url = (f'https://{host}.finance.yahoo.com/v8/finance/chart/{encoded}'
           f'?range=1d&interval=5m&includePrePost=true')
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*', 'Referer': 'https://finance.yahoo.com'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            raw = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

    try:
        result = raw['chart']['result'][0]
        meta = result['meta']
        ts = result.get('timestamp') or []
        closes = result['indicators']['quote'][0]['close']
        price = price_ts = None
        for t, c in zip(ts, closes):
            if c is not None and c == c:
                price, price_ts = round(c, 4), t
        if price is None:
            return {'ok': False, 'error': 'no bars'}
        prev = meta.get('chartPreviousClose') or meta.get('previousClose')
        tp = meta.get('currentTradingPeriod') or {}
        pre, reg, post = tp.get('pre') or {}, tp.get('regular') or {}, tp.get('post') or {}
        if reg.get('start') and reg.get('end') and pre.get('start') and post.get('end'):
            if price_ts < pre['start'] or price_ts >= post['end']:
                session = 'closed'
            elif price_ts < reg['start']:
                session = 'pre'
            elif price_ts < reg['end']:
                session = 'regular'
            else:
                session = 'post'
        else:
            session = 'unknown'
        return {'ok': True, 'symbol': symbol, 'price': price, 'price_ts': price_ts,
                'prev_close': round(prev, 4) if prev else None,
                'pre_start': pre.get('start'), 'reg_start': reg.get('start'),
                'reg_end': reg.get('end'), 'session': session}
    except Exception as e:
        return {'ok': False, 'error': f'parse: {e}'}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'ok': False, 'error': 'usage: fetch_yahoo_live.py SYMBOL'}))
        sys.exit(1)
    print(json.dumps(fetch(sys.argv[1])))
