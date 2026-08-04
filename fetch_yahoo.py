#!/usr/bin/env python3
"""
fetch_yahoo.py  — fetch closing prices from Yahoo Finance chart API.
Called by server.js:  python3 fetch_yahoo.py SYMBOL [RANGE]
Prints JSON to stdout: {"ok":true,"symbol":"AAPL","data":[["2026-07-10",100.0],...]}

Uses Python's urllib which has a different TLS fingerprint than Node.js,
bypassing Yahoo's bot-detection that blocks Node.js.
"""
import sys, json, urllib.request, urllib.error, ssl, time, random

def fetch(symbol, range_='5d'):
    ctx = ssl.create_default_context()
    encoded = urllib.request.quote(symbol, safe='')
    host = random.choice(['query1', 'query2'])
    url = f'https://{host}.finance.yahoo.com/v8/finance/chart/{encoded}?range={range_}&interval=1d&includePrePost=false'
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': '*/*',
        'Referer': 'https://finance.yahoo.com',
    }
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
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        data = []
        for ts, cl in zip(timestamps, closes):
            if cl is not None and cl == cl:  # not None, not NaN
                date = time.strftime('%Y-%m-%d', time.gmtime(ts))
                data.append([date, round(cl, 4)])
        return {'ok': True, 'symbol': symbol, 'data': data}
    except Exception as e:
        return {'ok': False, 'error': f'parse: {e}'}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'ok': False, 'error': 'usage: fetch_yahoo.py SYMBOL [RANGE]'}))
        sys.exit(1)
    symbol = sys.argv[1]
    range_ = sys.argv[2] if len(sys.argv) > 2 else '5d'
    print(json.dumps(fetch(symbol, range_)))
