#!/usr/bin/env python3
"""
a0_fetch_tiingo.py — independent second vendor (Tiingo EOD: open/close/adjOpen/adjClose) for every
name that ever ranked Top-6 by 12-1 momentum in the PIT Nasdaq-100, plus a few gap candidates.

Free tier = 50 requests/hour -> one request every 75 s, sequential, resumable, stops on HTTP 429.
Usage: python3 a0_fetch_tiingo.py tiingo_priority.txt
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'tiingo')
os.makedirs(OUT, exist_ok=True)
ENV = os.path.join(HERE, '..', '..', 'research', 'sector_stock_momentum', '.env')
SPACING = 75


def token():
    for line in open(ENV):
        if line.startswith('TIINGO_API_KEY='):
            return line.strip().split('=', 1)[1]
    sys.exit('TIINGO_API_KEY missing')


def fetch(sym, tok):
    url = (f'https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(sym.lower())}/prices'
           f'?startDate=2007-01-01&format=json&token={tok}')
    req = urllib.request.Request(url, headers={'Content-Type': 'application/json', 'User-Agent': 'macro-observer audit'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}'
    except Exception as e:  # noqa
        return None, str(e)


def main():
    tok = token()
    syms = [s.strip() for s in open(sys.argv[1]) if s.strip()]
    logp = os.path.join(OUT, '_log.json')
    log = json.load(open(logp)) if os.path.exists(logp) else {}
    todo = [s for s in syms if s not in log]
    print(f'{len(todo)} to fetch (~{len(todo) * SPACING / 3600:.1f} h)', flush=True)
    for i, s in enumerate(todo):
        data, err = fetch(s, tok)
        if err == 'HTTP 429':
            print(f'{s} HTTP 429 -> stop', flush=True)
            sys.exit(2)
        if err:
            log[s] = err
        elif not data:
            log[s] = 'empty'
        else:
            rows = [{k: r.get(k) for k in ('date', 'open', 'close', 'adjOpen', 'adjClose', 'divCash', 'splitFactor')} for r in data]
            json.dump({'symbol': s, 'source': 'tiingo', 'rows': rows}, open(os.path.join(OUT, f'{s}.json'), 'w'))
            log[s] = f"ok {rows[0]['date'][:10]}..{rows[-1]['date'][:10]} n={len(rows)}"
        print(f'[{i + 1}/{len(todo)}] {s} {log[s]}', flush=True)
        json.dump(log, open(logp, 'w'), indent=1)
        time.sleep(SPACING)
    print('done', flush=True)


if __name__ == '__main__':
    main()
