#!/usr/bin/env python3
"""
fetch_ndx_meta.py — identity + classification metadata for Nasdaq-100 names that the S&P store does not carry.

1. Wikipedia "List of NASDAQ-100 companies" table (current members only; Wikipedia gives ICB, NOT GICS)
   → data/ndx_wiki_current.csv  (fetched via the MediaWiki parse API; revision id recorded)
2. SEC submissions JSON (data.sec.gov, 0.25 s spacing, SEC fair-access User-Agent) for every CIK in
   data/ndx_cik_map.csv → SIC code, filer name history, form types (10-K vs 20-F/40-F)
   → cached in data/sec_submissions/CIK##########.json (same cache as fetch_earnings_dates.py)
"""
import io, json, os, subprocess, time, urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
EMAIL = subprocess.run(['git', 'config', 'user.email'], capture_output=True, text=True, cwd=HERE).stdout.strip()
UA = {'User-Agent': f'macro-observer research {EMAIL}', 'Accept-Encoding': 'identity'}


def wiki():
    u = 'https://en.wikipedia.org/w/api.php?action=parse&page=List_of_NASDAQ-100_companies&prop=text|revid&format=json&formatversion=2'
    j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
    tabs = pd.read_html(io.StringIO(j['parse']['text']))
    t = [x for x in tabs if any('Ticker' in str(c) for c in x.columns) and any('ICB' in str(c) for c in x.columns)][0]
    t.columns = [str(c) for c in t.columns]
    t['wiki_revid'] = j['parse']['revid']
    t.to_csv(os.path.join(HERE, 'data', 'ndx_wiki_current.csv'), index=False)
    print('wiki rows', len(t), 'revid', j['parse']['revid'], list(t.columns))


def sec():
    cm = pd.read_csv(os.path.join(HERE, 'data', 'ndx_cik_map.csv'))
    os.makedirs(os.path.join(HERE, 'data', 'sec_submissions'), exist_ok=True)
    for c in sorted(set(cm.cik.dropna().astype(int))):
        p = os.path.join(HERE, 'data', 'sec_submissions', f'CIK{c:010d}.json')
        if os.path.exists(p):
            continue
        u = f'https://data.sec.gov/submissions/CIK{c:010d}.json'
        try:
            open(p, 'wb').write(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
            print('ok', c)
        except Exception as e:  # noqa
            print('FAIL', c, e)
        time.sleep(0.25)


if __name__ == '__main__':
    wiki()
    sec()
