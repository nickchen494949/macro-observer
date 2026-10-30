#!/usr/bin/env python3
"""
fetch_tiingo.py — fill price history that Yahoo no longer carries (acquired / delisted S&P members,
e.g. HES, PXD, DFS, XLNX, CELG, EA, AVB) from Tiingo's free EOD API.

Free-tier limits: 50 requests / hour, 1 000 / day, 500 unique symbols / month → one request every
75 s (48 / hour), strictly sequential, stop on HTTP 429, resumable.

Which tickers:  S&P members since 2007-12 whose Yahoo series is missing or starts after a membership
                spell begins (cannot be the security that was in the index), AND that Tiingo's
                supported_tickers list shows with a date range covering that spell.
Identity check: after download the series must start ≤ spell start + 10 days (or ≤ 2007-01-10) and
                must not end > 60 days before the spell ends; otherwise it is kept out (logged).
Output:         data/raw_tiingo/<SYMBOL>.json  {symbol, dates, close, adjclose, splits, source}
Key:            TIINGO_API_KEY in this folder's .env (git-ignored).
"""
import json, os, sys, time, urllib.error, urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'raw_tiingo')
os.makedirs(OUT, exist_ok=True)
SPACING = 75


def key():
    for line in open(os.path.join(HERE, '.env')):
        if line.startswith('TIINGO_API_KEY='):
            return line.strip().split('=', 1)[1]
    sys.exit('TIINGO_API_KEY missing in .env')


def plan():
    tt = pd.read_csv(os.path.join(HERE, 'data', 'tiingo_supported_tickers.csv'), dtype=str)
    tt = tt[tt.priceCurrency == 'USD']
    tt['startDate'] = pd.to_datetime(tt.startDate, errors='coerce')
    tt['endDate'] = pd.to_datetime(tt.endDate, errors='coerce')
    sp = pd.read_csv(os.path.join(HERE, 'data', 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    sp = sp[sp.end_date.isna() | (sp.end_date >= '2007-12-01')]
    todo = []
    for t, spells in sp.groupby('ticker'):
        y = t.replace('.', '-')
        p = os.path.join(HERE, 'data', 'raw', f'{y}.json')
        if os.path.exists(p):
            d = json.load(open(p))
            s0 = pd.Timestamp(d['dates'][0])
            if not any(s0 > max(r.start_date, pd.Timestamp('2007-01-10')) + pd.Timedelta(days=10)
                       for r in spells.itertuples()):
                continue                                   # Yahoo already covers every spell
        s = spells.start_date.min()
        e = spells.end_date.max() if spells.end_date.notna().all() else pd.Timestamp('2100-01-01')
        c = tt[tt.ticker.str.upper() == y.upper()]
        ok = c[(c.startDate <= max(s, pd.Timestamp('2007-01-10')) + pd.Timedelta(days=10)) &
               (c.endDate >= min(e, pd.Timestamp('2026-10-01')) - pd.Timedelta(days=60))]
        if len(ok):
            todo.append((y, spells))
    # successors of renamed tickers whose Yahoo history does not reach back to the predecessor's spells
    # (successor, predecessor): judged against the predecessor's spells
    for succ, old in EXTRA.items():
        p = os.path.join(HERE, 'data', 'raw', f'{succ}.json')
        sp_old = sp[sp.ticker == old]
        if os.path.exists(p):
            s0 = pd.Timestamp(json.load(open(p))['dates'][0])
            if all(s0 <= max(r.start_date, pd.Timestamp('2007-01-10')) + pd.Timedelta(days=10) for r in sp_old.itertuples()):
                continue
        if succ not in [t for t, _ in todo]:
            todo.append((succ, sp_old))
    return todo


EXTRA = {'HWM': 'ARNC', 'GAP': 'GPS', 'FBIN': 'FBHS', 'TT': 'IR',
         'SIVBQ': 'SIVB',   # SVB Financial kept trading OTC as SIVBQ after the 2023 failure (same security)
         'FRCB': 'FRC',     # First Republic Bank OTC after 2023 failure
         'TNL': 'WYND',     # Wyndham Worldwide → Wyndham Destinations → Travel + Leisure (same filer)
         'BHI': 'BHGE',     # old Baker Hughes Inc (until 2017-07-03), see TIME_SPLIT in ticker_aliases.py
         'DAY': 'CDAY',     # Dayforce (ex Ceridian) — Yahoo has no DAY file
         'DINO': 'HFC',     # HF Sinclair incl. HollyFrontier history
         'VIAC': 'CBS'}     # Tiingo lists a VIAC row 2005-12-05..2019-12-04 = CBS Corp before the ViacomCBS rename
EXTRA_UNTIL = {'BHI': '2017-07-03', 'VIAC': '2019-12-04'}   # only the predecessor spell part before this date must be covered


def fetch(sym, token):
    url = (f'https://api.tiingo.com/tiingo/daily/{urllib.request.quote(sym.lower())}/prices'
           f'?startDate=2007-01-01&format=json&token={token}')
    req = urllib.request.Request(url, headers={'Content-Type': 'application/json', 'User-Agent': 'macro-observer research'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}'
    except Exception as e:  # noqa
        return None, str(e)


def main():
    token = key()
    todo = plan()
    done = {f[:-5] for f in os.listdir(OUT) if f.endswith('.json')}
    logp = os.path.join(OUT, '_log.json')
    log = json.load(open(logp)) if os.path.exists(logp) else {}
    todo = [(s, sp) for s, sp in todo if s not in done and s not in log]
    print(f'{len(todo)} symbols to fetch from Tiingo (~{len(todo) * SPACING / 3600:.1f} h)', flush=True)
    for i, (sym, spells) in enumerate(todo):
        data, err = fetch(sym, token)
        if err:
            print(f'[{i+1}/{len(todo)}] {sym} FAIL {err}', flush=True)
            if err == 'HTTP 429':
                print('HTTP 429 — Tiingo limit reached. Stopping (resume later).', flush=True)
                sys.exit(2)
            log[sym] = err
        elif not data:
            log[sym] = 'empty'
            print(f'[{i+1}/{len(todo)}] {sym} empty', flush=True)
        else:
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df.date).dt.tz_localize(None)
            first, last = df.date.min(), df.date.max()
            until = pd.Timestamp(EXTRA_UNTIL[sym]) if sym in EXTRA_UNTIL else None
            cover = all(first <= max(r.start_date, pd.Timestamp('2007-01-10')) + pd.Timedelta(days=10) and
                        (last >= min(r.end_date if pd.notna(r.end_date) else pd.Timestamp('2100-01-01'),
                                     until or pd.Timestamp('2100-01-01')) - pd.Timedelta(days=60)
                         if (pd.notna(r.end_date) or until) else True)
                        for r in spells.itertuples() if pd.isna(r.end_date) or r.end_date >= pd.Timestamp('2007-12-01'))
            out = {'symbol': sym, 'source': 'tiingo', 'dates': df.date.dt.strftime('%Y-%m-%d').tolist(),
                   'close': df['close'].round(4).tolist(), 'adjclose': df['adjClose'].round(6).tolist(),
                   'splits': [[d.strftime('%Y-%m-%d'), float(f), 1.0] for d, f in zip(df.date, df.splitFactor) if f != 1],
                   'covers_membership': bool(cover)}
            json.dump(out, open(os.path.join(OUT, f'{sym}.json'), 'w'))
            log[sym] = 'ok' if cover else 'ok_but_does_not_cover_membership'
            print(f'[{i+1}/{len(todo)}] {sym} {log[sym]} {first.date()}..{last.date()}', flush=True)
        json.dump(log, open(logp, 'w'), indent=1)
        time.sleep(SPACING)
    print('done', flush=True)


if __name__ == '__main__':
    main()
