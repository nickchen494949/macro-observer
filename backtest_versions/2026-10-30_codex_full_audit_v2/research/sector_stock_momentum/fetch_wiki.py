#!/usr/bin/env python3
"""
fetch_wiki.py — last-resort fill from Nasdaq Data Link WIKI/PRICES (community EOD prices, frozen 2018-03-27).

Used ONLY for S&P members whose history neither Yahoo, Tiingo nor a verified rename can supply — mostly
companies acquired 2009–2017 whose ticker was later recycled (SNDK, BRCM, LLTC, HAR, DTV, BMC …) and the
"old company" spells of re-used tickers (old DOW, CEG, DELL, 21st-Century-Fox FOXA/FOX).

Quality gate: WIKI is unmaintained, so before use it is compared with Yahoo on VALIDATION tickers that both
sources carry; month-end adjusted returns must agree (median |diff| and 99th pct are reported in
data/raw_wiki/_validation.json). Every WIKI price used in the backtest is tagged source='wiki'.

Output: data/raw_wiki/<SYMBOL>.json  {symbol, source, dates, close, adjclose, splits}
Key:    NASDAQ_DATA_LINK_API_KEY in this folder's .env (git-ignored). 1 request / 1.5 s.
"""
import json, os, sys, time, urllib.error, urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'raw_wiki')
os.makedirs(OUT, exist_ok=True)
VALIDATION = ['AAPL', 'JPM', 'XOM', 'JNJ', 'PG', 'KO', 'MSFT', 'INTC', 'CAT', 'MMM', 'GE', 'WMT', 'HD', 'PFE',
              'MRK', 'CVX', 'IBM', 'ORCL', 'CSCO', 'BA']


def key():
    for line in open(os.path.join(HERE, '.env')):
        if line.startswith('NASDAQ_DATA_LINK_API_KEY='):
            return line.strip().split('=', 1)[1]
    sys.exit('NASDAQ_DATA_LINK_API_KEY missing in .env')


def fetch(sym, k):
    url = (f'https://data.nasdaq.com/api/v3/datatables/WIKI/PRICES.json?ticker={urllib.request.quote(sym)}'
           f'&date.gte=2006-12-01&qopts.columns=ticker,date,close,adj_close,split_ratio&api_key={k}')
    rows, cursor = [], None
    while True:
        u = url + (f'&qopts.cursor_id={cursor}' if cursor else '')
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'macro-observer research'}), timeout=60) as r:
                j = json.loads(r.read())
        except urllib.error.HTTPError as e:
            return None, f'HTTP {e.code}'
        rows += j['datatable']['data']
        cursor = j.get('meta', {}).get('next_cursor_id')
        if not cursor:
            break
        time.sleep(1.5)
    return rows, None


def candidates():
    """Members since 2007-12 whose Yahoo series is missing or starts after one of their spells began."""
    sp = pd.read_csv(os.path.join(HERE, 'data', 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    sp = sp[(sp.end_date.isna() | (sp.end_date >= '2007-12-01')) & (sp.start_date <= '2018-03-27')]
    out = []
    for t, spells in sp.groupby('ticker'):
        p = os.path.join(HERE, 'data', 'raw', f"{t.replace('.', '-')}.json")
        if os.path.exists(p):
            s0 = pd.Timestamp(json.load(open(p))['dates'][0])
            if all(s0 <= max(r.start_date, pd.Timestamp('2007-01-10')) + pd.Timedelta(days=10) for r in spells.itertuples()):
                continue
        out.append(t)
    return out


def save(sym, rows):
    df = pd.DataFrame(rows, columns=['ticker', 'date', 'close', 'adj_close', 'split_ratio']).sort_values('date')
    out = {'symbol': sym.replace('.', '-'), 'source': 'wiki', 'dates': df.date.tolist(),
           'close': df.close.round(4).tolist(), 'adjclose': df.adj_close.round(6).tolist(),
           'splits': [[d, float(r), 1.0] for d, r in zip(df.date, df.split_ratio) if r and r != 1]}
    json.dump(out, open(os.path.join(OUT, f"{out['symbol']}.json"), 'w'))
    return df


def validate(k):
    res = {}
    for t in VALIDATION:
        rows, err = fetch(t, k)
        time.sleep(1.5)
        if err or not rows:
            res[t] = err or 'empty'
            continue
        w = pd.DataFrame(rows, columns=['ticker', 'date', 'close', 'adj_close', 'split_ratio'])
        w = pd.Series(w.adj_close.values, index=pd.to_datetime(w.date)).sort_index()
        y = json.load(open(os.path.join(HERE, 'data', 'raw', f'{t}.json')))
        y = pd.Series(y['adjclose'], index=pd.to_datetime(y['dates'])).sort_index()
        rw = w.resample('ME').last().pct_change()
        ry = y.resample('ME').last().pct_change()
        d = (rw - ry).loc['2008-01-31':'2018-02-28'].dropna().abs()
        res[t] = {'months': int(len(d)), 'median_abs_diff': float(d.median()), 'p99_abs_diff': float(d.quantile(.99)),
                  'max_abs_diff': float(d.max())}
        print('validate', t, res[t], flush=True)
    allv = [v for v in res.values() if isinstance(v, dict)]
    summ = {'tickers': len(allv), 'median_of_median_abs_diff': float(np.median([v['median_abs_diff'] for v in allv])),
            'worst_p99': float(max(v['p99_abs_diff'] for v in allv)), 'worst_max': float(max(v['max_abs_diff'] for v in allv))}
    json.dump({'summary': summ, 'per_ticker': res}, open(os.path.join(OUT, '_validation.json'), 'w'), indent=1)
    print('VALIDATION', summ, flush=True)
    return summ


def main():
    k = key()
    if not os.path.exists(os.path.join(OUT, '_validation.json')):
        validate(k)
    logp = os.path.join(OUT, '_log.json')
    log = json.load(open(logp)) if os.path.exists(logp) else {}
    todo = [t for t in candidates() if t not in log]
    print(f'{len(todo)} candidates', flush=True)
    for i, t in enumerate(todo):
        rows, err = fetch(t, k)
        if err:
            log[t] = err
            print(f'[{i+1}/{len(todo)}] {t} FAIL {err}', flush=True)
            if err == 'HTTP 429':
                json.dump(log, open(logp, 'w'), indent=1)
                sys.exit(2)
        elif not rows:
            log[t] = 'not in WIKI'
            print(f'[{i+1}/{len(todo)}] {t} not in WIKI', flush=True)
        else:
            df = save(t, rows)
            log[t] = f'ok {df.date.iloc[0]}..{df.date.iloc[-1]}'
            print(f'[{i+1}/{len(todo)}] {t} {log[t]}', flush=True)
        json.dump(log, open(logp, 'w'), indent=1)
        time.sleep(1.5)
    print('done', flush=True)


if __name__ == '__main__':
    main()
