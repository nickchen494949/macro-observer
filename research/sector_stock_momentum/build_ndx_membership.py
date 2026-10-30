#!/usr/bin/env python3
"""
build_ndx_membership.py — point-in-time Nasdaq-100 membership at every month-end (2007-12 … 2026-09).

Source: jmccarrell/n100tickers (MIT), YAML files copied verbatim to data/nasdaq100_src/ (commit in SOURCE.txt).
Semantics identical to n100tickers.tickers_as_of(): start from `tickers_on_Jan_1` of the year, apply every
change whose effective date <= the query date. Tickers are the symbols that traded AT THAT DATE (PCLN not BKNG).

Output: data/ndx_monthly_members.csv  (month_end, ticker)   — tickers in Yahoo format ('.' → '-')
        data/ndx_ticker_spells.csv     (ticker, first_month_end, last_month_end, n_months)
        data/ndx_spells.csv            (ticker, start_date, end_date) exact spells from the change dates
"""
import os, sys, datetime
import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'data', 'nasdaq100_src')


def load_year(y):
    return yaml.load(open(os.path.join(SRC, f"n100-ticker-changes-{y}.yaml"), encoding="utf-8"), Loader=yaml.BaseLoader)  # BaseLoader: keep "ON" as a string


def tickers_as_of(d):
    y = load_year(d.year)
    res = set(str(x) for x in y['tickers_on_Jan_1'])
    for k in sorted((y.get('changes') or {}).keys(), key=str):
        kd = k if isinstance(k, datetime.date) else datetime.date.fromisoformat(str(k))
        if kd <= d:
            ops = y['changes'][k]
            for op, xs in ops.items():
                xs = set(str(x) for x in xs)
                if op == 'union':
                    res |= xs
                elif op == 'difference':
                    res -= xs
                else:
                    raise ValueError(op)
    return res


def main():
    mes = pd.date_range('2007-12-31', '2026-09-30', freq='ME')
    rows = []
    for t in mes:
        for tk in sorted(tickers_as_of(t.date())):
            rows.append((t.date().isoformat(), tk.replace('.', '-')))
    df = pd.DataFrame(rows, columns=['month_end', 'ticker'])
    df.to_csv(os.path.join(HERE, 'data', 'ndx_monthly_members.csv'), index=False)
    sp = df.groupby('ticker').month_end.agg(['min', 'max', 'count']).reset_index()
    sp.columns = ['ticker', 'first_month_end', 'last_month_end', 'n_months']
    sp.to_csv(os.path.join(HERE, 'data', 'ndx_ticker_spells.csv'), index=False)
    # exact membership spells from the change dates (start = effective date, end = day before removal)
    ev = set()
    for y in range(2007, 2027):
        ev.add(datetime.date(y, 1, 1))
        for k in (load_year(y).get('changes') or {}):
            ev.add(datetime.date.fromisoformat(str(k)))
    ev = sorted(e for e in ev if e <= datetime.date(2026, 9, 30))
    open_, spells = {}, []
    prev = set()
    for e in ev:
        cur = tickers_as_of(e)
        for tk in cur - prev:
            open_[tk] = e
        for tk in prev - cur:
            spells.append((tk.replace('.', '-'), open_.pop(tk), e - datetime.timedelta(days=1)))
        prev = cur
    for tk, s in open_.items():
        spells.append((tk.replace('.', '-'), s, None))
    sp_df = pd.DataFrame(spells, columns=['ticker', 'start_date', 'end_date']).sort_values(['ticker', 'start_date'])
    # 2007-01-01 is the coverage start, not an addition date: mark it as "member since before 2007"
    sp_df['start_is_coverage_start'] = sp_df.start_date == datetime.date(2007, 1, 1)
    sp_df.to_csv(os.path.join(HERE, 'data', 'ndx_spells.csv'), index=False)
    print(f'{len(sp_df)} spells written to data/ndx_spells.csv')
    cnt = df.groupby('month_end').size()
    print(f'{len(mes)} month-ends, {df.ticker.nunique()} unique tickers, members/month min {cnt.min()} max {cnt.max()}')
    # sanity checks against the upstream test-suite facts
    assert 'PCLN' in tickers_as_of(datetime.date(2010, 1, 1))
    assert [('OKTA' in tickers_as_of(datetime.date(y, 1, 1))) for y in (2020, 2021, 2022, 2023)] == [False, True, True, False]
    assert len(tickers_as_of(datetime.date(2020, 9, 1))) == 103
    print('upstream sanity checks PASS')


if __name__ == '__main__':
    main()
