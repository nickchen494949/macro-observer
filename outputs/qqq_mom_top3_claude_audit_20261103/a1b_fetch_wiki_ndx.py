#!/usr/bin/env python3
"""
a1b_fetch_wiki_ndx.py — independent SECOND source for Nasdaq-100 membership.

For every formation month-end 2008-12 .. 2026-09 download the English-Wikipedia "Nasdaq-100" article
revision that was live at that month-end (MediaWiki API, rvstart=<month-end 23:59:59Z>, rvdir=older,
rvlimit=1). Raw wikitext is cached in wiki_ndx/<YYYY-MM-DD>.json (revid, timestamp, wikitext).
Parsing happens in a1c_compare_wiki.py. Polite: 1 request / 1.5 s, resumable.
"""
import json
import os
import time
import urllib.parse
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'wiki_ndx')
os.makedirs(OUT, exist_ok=True)
API = 'https://en.wikipedia.org/w/api.php'
UA = 'macro-observer-research-audit/1.0 (personal research; contact via github nickchen494949)'


def fetch(title, ts):
    q = {'action': 'query', 'prop': 'revisions', 'titles': title, 'rvlimit': '1', 'rvdir': 'older',
         'rvstart': ts, 'rvprop': 'ids|timestamp|content', 'rvslots': 'main', 'format': 'json',
         'formatversion': '2'}
    req = urllib.request.Request(API + '?' + urllib.parse.urlencode(q), headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    p = d['query']['pages'][0]
    rv = p['revisions'][0]
    return {'title': title, 'revid': rv['revid'], 'timestamp': rv['timestamp'],
            'wikitext': rv['slots']['main']['content']}


def main():
    months = pd.date_range('2008-12-31', '2026-09-30', freq='ME')
    for t in months:
        fn = os.path.join(OUT, f'{t.date()}.json')
        if os.path.exists(fn):
            continue
        ts = f'{t.date()}T23:59:59Z'
        for attempt in range(6):
            try:
                rec = fetch('Nasdaq-100', ts)
                json.dump(rec, open(fn, 'w'))
                print(t.date(), rec['revid'], rec['timestamp'], len(rec['wikitext']), flush=True)
                break
            except Exception as e:  # noqa
                print(t.date(), 'ERR', e, flush=True)
                time.sleep(60 * (attempt + 1))
        time.sleep(5)
    print('done', flush=True)


if __name__ == '__main__':
    main()
