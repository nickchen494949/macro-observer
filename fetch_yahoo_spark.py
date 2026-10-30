#!/usr/bin/env python3
"""
fetch_yahoo_spark.py — latest regular-session price for MANY symbols in ONE request (Yahoo spark endpoint).
Called by server.js:  python3 fetch_yahoo_spark.py SYM1,SYM2,...   (max 20 symbols per call)
Prints JSON: {"ok":true,"data":{"XLK":{"price":..,"ts":..,"prev":..,"start":..,"end":..}, ...}}

Python urllib on purpose (Yahoo blocks Node.js by TLS fingerprint). Regular session only —
the spark endpoint rejects includePrePost; pre-market quotes come from fetch_yahoo_live.py.
"""
import sys, json, urllib.request, urllib.error, urllib.parse, ssl, random


def fetch(symbols):
    ctx = ssl.create_default_context()
    host = random.choice(['query1', 'query2'])
    q = urllib.parse.quote(','.join(symbols), safe=',')
    url = f'https://{host}.finance.yahoo.com/v8/finance/spark?symbols={q}&range=1d&interval=5m'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*',
                                               'Referer': 'https://finance.yahoo.com'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            raw = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    out = {}
    try:
        for sym, v in raw.items():
            if not isinstance(v, dict):
                continue
            price = ts = None
            for t, c in zip(v.get('timestamp') or [], v.get('close') or []):
                if c is not None and c == c:
                    price, ts = c, t
            prev = v.get('previousClose') or v.get('chartPreviousClose')
            if price is None or not prev:
                continue
            out[sym] = {'price': round(price, 4), 'ts': ts, 'prev': round(prev, 4),
                        'start': v.get('start'), 'end': v.get('end')}
        return {'ok': True, 'data': out}
    except Exception as e:
        return {'ok': False, 'error': f'parse: {e}'}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'ok': False, 'error': 'usage: fetch_yahoo_spark.py SYM1,SYM2,...'}))
        sys.exit(1)
    syms = [s for s in sys.argv[1].split(',') if s][:20]
    print(json.dumps(fetch(syms)))
