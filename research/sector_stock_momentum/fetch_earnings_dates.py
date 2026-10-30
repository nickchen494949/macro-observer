#!/usr/bin/env python3
"""
fetch_earnings_dates.py — real earnings-announcement dates from SEC EDGAR (free).

For every CIK in data/fundamentals/cik_map.csv: data.sec.gov/submissions/CIK##########.json (+ its older 'files'
pages) → every 8-K whose items include 2.02 ("Results of Operations and Financial Condition" = earnings release),
with filing date and acceptance timestamp. A release accepted after 16:00 New York time moves the price on the next
session. Output: data/earnings_dates.csv (cik, ticker, filing_date, acceptance, reaction_date).
SEC fair access: declared User-Agent, <= 5 requests / second, resumable.
"""
import json, os, subprocess, time, urllib.error, urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'data', 'sec_submissions')
os.makedirs(CACHE, exist_ok=True)
EMAIL = subprocess.run(['git', 'config', 'user.email'], capture_output=True, text=True, cwd=HERE).stdout.strip()
UA = f'macro-observer research {EMAIL}'


def get(url, path):
    if os.path.exists(path):
        return json.load(open(path))
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            json.dump(d, open(path, 'w'))
            time.sleep(0.22)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except Exception:  # noqa
            time.sleep(5 * (attempt + 1))
    return None


def rows_from(block):
    out = []
    for f, d, a, it in zip(block.get('form', []), block.get('filingDate', []), block.get('acceptanceDateTime', []),
                           block.get('items', [])):
        if f in ('8-K', '8-K/A') and '2.02' in str(it):
            out.append((d, a, f))
    return out


def main():
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    ciks = sorted({int(c) for c in cm.cik})
    t_of = cm.dropna(subset=['cik']).groupby('cik').ticker.first().to_dict()
    rows = []
    for i, c in enumerate(ciks):
        d = get(f'https://data.sec.gov/submissions/CIK{c:010d}.json', os.path.join(CACHE, f'{c}.json'))
        if not d:
            continue
        rr = rows_from(d.get('filings', {}).get('recent', {}))
        for f in d.get('filings', {}).get('files', []):
            x = get(f'https://data.sec.gov/submissions/{f["name"]}', os.path.join(CACHE, f['name']))
            if x:
                rr += rows_from(x)
        rows += [(c, t_of.get(c), a, b, f) for a, b, f in rr]
        if i % 50 == 0:
            print(f'[{i+1}/{len(ciks)}] cik {c}: {len(rr)} earnings 8-Ks', flush=True)
    df = pd.DataFrame(rows, columns=['cik', 'ticker', 'filing_date', 'acceptance', 'form']).drop_duplicates(['cik', 'filing_date'])
    df['filing_date'] = pd.to_datetime(df.filing_date)
    acc = pd.to_datetime(df.acceptance, errors='coerce', utc=True).dt.tz_convert('America/New_York')
    after_close = acc.dt.hour >= 16
    df['reaction_date'] = df.filing_date + pd.to_timedelta(after_close.astype(int), unit='D')   # next calendar day; aligned to a session later
    df = df.sort_values(['cik', 'filing_date'])
    df.to_csv(os.path.join(HERE, 'data', 'earnings_dates.csv'), index=False)
    print('done', len(df), 'earnings releases for', df.cik.nunique(), 'companies', df.filing_date.min(), '→', df.filing_date.max())


if __name__ == '__main__':
    main()
