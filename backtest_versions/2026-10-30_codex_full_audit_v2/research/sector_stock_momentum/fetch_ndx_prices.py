#!/usr/bin/env python3
"""
fetch_ndx_prices.py — prices for Nasdaq-100 members that the S&P 500 store does not already carry.

Which symbols: every NDX ticker (data/ndx_spells.csv) whose membership reaches the backtest period, that is not
a price column of the audited S&P store (backtest.load_prices, incl. verified renames), and is not handled in
data/ndx_symbol_map.csv as map_existing / skip / gap. data/ndx_symbol_map.csv also gives renamed targets
(CTRP→TCOM, RIMM→BB, LINTA→QVCA, VIP→VEON) and the WIKI-only names.
Sources: Tiingo free EOD (75 s spacing, stop on HTTP 429) and Nasdaq Data Link WIKI (frozen 2018-03-27; quality
validated in data/raw_wiki/_validation.json). Yahoo is NOT used here (Yahoo only in the safe morning window).
Identity check: series must start <= spell start + 10 days (or <= 2007-01-10 for members since before 2007) and
must not end > 60 days before the spell ends (WIKI: before min(spell end, 2018-03-27)). Result in 'covers_membership'.
Output: data/raw_ndx/<SYMBOL>.json  {symbol, source, dates, close, adjclose, splits, covers_membership, for_ndx_tickers}
        data/raw_ndx/_log.json
Kept separate from data/raw*/ so the frozen S&P results cannot change.
"""
import json, os, sys, time

import pandas as pd

import fetch_tiingo as ft
import fetch_wiki as fw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'raw_ndx')
os.makedirs(OUT, exist_ok=True)
FIRST_FORMATION = pd.Timestamp('2008-12-31')
WIKI_END = pd.Timestamp('2018-03-27')


def plan():
    import backtest as bt
    daily = bt.load_prices()[0]
    sp = pd.read_csv(os.path.join(HERE, 'data', 'ndx_spells.csv'), parse_dates=['start_date', 'end_date'])
    mp = pd.read_csv(os.path.join(HERE, 'data', 'ndx_symbol_map.csv')).set_index('ndx_ticker')
    mm = pd.read_csv(os.path.join(HERE, 'data', 'ndx_monthly_members.csv'), parse_dates=['month_end'])
    at_formation = set(mm.ticker[mm.month_end >= FIRST_FORMATION])    # member at >= 1 formation month-end
    todo = {}
    for tk, g in sp.groupby('ticker'):
        if tk not in at_formation:
            continue
        if tk in mp.index:
            a = mp.at[tk, 'action']
            if not a.startswith('fetch_'):
                continue
            target, src = mp.at[tk, 'target'], a.split('_', 1)[1]
        elif tk in daily.columns:
            continue
        else:
            target, src = tk, 'tiingo'
        e = todo.setdefault(target, {'source': src, 'for': [], 'spells': []})
        e['for'].append(tk)
        e['spells'] += [(r.start_date, r.end_date, r.start_is_coverage_start) for r in g.itertuples()]
    return todo


def covers(first, last, spells, src):
    ok = True
    for s, e, cov in spells:
        need0 = pd.Timestamp('2007-01-10') if cov else s + pd.Timedelta(days=10)
        end = e if pd.notna(e) else pd.Timestamp('2100-01-01')
        if src == 'wiki':
            end = min(end, WIKI_END)
        if pd.notna(e) and e < FIRST_FORMATION - pd.Timedelta(days=400):
            continue                                      # spell long before the sample: irrelevant
        ok &= first <= max(need0, pd.Timestamp('2007-01-10')) and last >= min(end, pd.Timestamp('2026-10-01')) - pd.Timedelta(days=60)
    return bool(ok)


def main():
    todo = plan()
    logp = os.path.join(OUT, '_log.json')
    log = json.load(open(logp)) if os.path.exists(logp) else {}
    order = sorted(todo, key=lambda s: (todo[s]['source'] != 'wiki', s))     # WIKI first (fast), then Tiingo
    order = [s for s in order if s not in log]
    n_t = sum(todo[s]['source'] == 'tiingo' for s in order)
    print(f'{len(order)} symbols to fetch ({n_t} Tiingo, ~{n_t * ft.SPACING / 60:.0f} min)', flush=True)
    tk_t, tk_w = None, None
    for i, sym in enumerate(order):
        e = todo[sym]
        if e['source'] == 'wiki':
            tk_w = tk_w or fw.key()
            rows, err = fw.fetch(sym, tk_w)
            if err or not rows:
                log[sym] = err or 'empty'
            else:
                df = pd.DataFrame(rows, columns=['ticker', 'date', 'close', 'adj_close', 'split_ratio']).sort_values('date')
                dates = pd.to_datetime(df.date)
                cov = covers(dates.min(), dates.max(), e['spells'], 'wiki')
                out = {'symbol': sym, 'source': 'wiki', 'dates': df.date.tolist(), 'close': df.close.round(4).tolist(),
                       'adjclose': df.adj_close.round(6).tolist(),
                       'splits': [[d, float(r), 1.0] for d, r in zip(df.date, df.split_ratio) if r and r != 1],
                       'covers_membership': cov, 'for_ndx_tickers': e['for']}
                json.dump(out, open(os.path.join(OUT, f'{sym}.json'), 'w'))
                log[sym] = f"wiki {'ok' if cov else 'ok_but_does_not_cover_membership'} {dates.min().date()}..{dates.max().date()}"
            time.sleep(1.5)
        else:
            tk_t = tk_t or ft.key()
            data, err = ft.fetch(sym, tk_t)
            if err == 'HTTP 429':
                print('HTTP 429 — Tiingo limit reached. Stopping (resume later).', flush=True)
                json.dump(log, open(logp, 'w'), indent=1)
                sys.exit(2)
            if err or not data:
                log[sym] = err or 'empty'
            else:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df.date).dt.tz_localize(None)
                cov = covers(df.date.min(), df.date.max(), e['spells'], 'tiingo')
                out = {'symbol': sym, 'source': 'tiingo', 'dates': df.date.dt.strftime('%Y-%m-%d').tolist(),
                       'close': df['close'].round(4).tolist(), 'adjclose': df['adjClose'].round(6).tolist(),
                       'splits': [[d.strftime('%Y-%m-%d'), float(f), 1.0] for d, f in zip(df.date, df.splitFactor) if f != 1],
                       'covers_membership': cov, 'for_ndx_tickers': e['for']}
                json.dump(out, open(os.path.join(OUT, f'{sym}.json'), 'w'))
                log[sym] = f"tiingo {'ok' if cov else 'ok_but_does_not_cover_membership'} {df.date.min().date()}..{df.date.max().date()}"
        print(f'[{i+1}/{len(order)}] {sym} (for {",".join(e["for"])}): {log[sym]}', flush=True)
        json.dump(log, open(logp, 'w'), indent=1)
        if e['source'] == 'tiingo' and i + 1 < len(order):
            time.sleep(ft.SPACING)
    print('done', flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--plan':
        for s, e in sorted(plan().items()):
            print(s, e['source'], e['for'])
    else:
        main()
