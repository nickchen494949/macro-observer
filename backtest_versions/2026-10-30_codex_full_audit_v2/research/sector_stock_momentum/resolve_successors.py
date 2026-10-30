#!/usr/bin/env python3
"""
resolve_successors.py — find the CURRENT ticker of renamed former members via SEC, and fetch its Yahoo history.

For every S&P member (since 2007-12) whose own Yahoo series does not cover its membership:
  CIK (data/fundamentals/cik_map.csv)  →  SEC company_tickers.json  →  ticker(s) the same filer trades under today.
If that ticker differs (e.g. ADS → BFH, Alliance Data → Bread Financial), its Yahoo history is downloaded
(Python urllib, 5–10 s spacing, stop on 429 — same rules as fetch_prices.py) and accepted only if it starts
≤ 10 days after the old ticker's first spell began. Accepted pairs are written to
data/sec_successor_aliases.csv (evidence = same SEC CIK) and picked up by ticker_aliases.py.
"""
import json, os, random, time

import pandas as pd

from fetch_prices import fetch

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')


def main():
    sp = pd.read_csv(os.path.join(HERE, 'data', 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    sp = sp[sp.end_date.isna() | (sp.end_date >= '2007-12-01')]
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    sec = pd.read_csv(os.path.join(HERE, 'data', 'sec_company_tickers.csv'))
    cur = sec.groupby('cik_str').ticker.apply(list).to_dict()
    members = set(sp.ticker)
    out_p = os.path.join(HERE, 'data', 'sec_successor_aliases.csv')
    done = pd.read_csv(out_p) if os.path.exists(out_p) else pd.DataFrame(columns=['old', 'new', 'cik', 'status'])
    rows = done.to_dict('records')
    seen = set(done.old)
    for r in cm.itertuples():
        t = r.ticker
        if t in seen:
            continue
        spells = sp[sp.ticker == t]
        if spells.empty:
            continue
        p = os.path.join(RAW, f"{t.replace('.', '-')}.json")
        start = max(spells.start_date.min(), pd.Timestamp('2007-01-10'))
        if os.path.exists(p) and pd.Timestamp(json.load(open(p))['dates'][0]) <= start + pd.Timedelta(days=10):
            continue
        succ = [x for x in cur.get(int(r.cik), []) if x.replace('-', '.') != t]
        succ = [x for x in succ if x.replace('-', '.') not in members or not os.path.exists(os.path.join(RAW, f'{x}.json'))][:1] \
            or [x for x in cur.get(int(r.cik), []) if x.replace('-', '.') != t][:1]
        if not succ:
            continue
        new = succ[0].replace('.', '-')
        q = os.path.join(RAW, f'{new}.json')
        if not os.path.exists(q):
            res = fetch(new)
            time.sleep(random.uniform(5, 10))
            if not res['ok'] or not res['data']['dates']:
                rows.append({'old': t, 'new': new, 'cik': int(r.cik), 'status': f"yahoo {res.get('error', 'empty')}"})
                print(t, '→', new, 'yahoo fail', res.get('error'), flush=True)
                if res.get('error') == 'HTTP 429':
                    break
                continue
            json.dump(res['data'], open(q, 'w'))
        first = pd.Timestamp(json.load(open(q))['dates'][0])
        ok = first <= start + pd.Timedelta(days=10)
        rows.append({'old': t, 'new': new, 'cik': int(r.cik),
                     'status': 'accepted' if ok else f'rejected: {new} history starts {first.date()}'})
        print(t, '→', new, rows[-1]['status'], flush=True)
        pd.DataFrame(rows).to_csv(out_p, index=False)
    pd.DataFrame(rows).to_csv(out_p, index=False)
    print('done', flush=True)


if __name__ == '__main__':
    main()
