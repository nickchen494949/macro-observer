#!/usr/bin/env python3
"""
a1_universe.py — Claude clean-room audit of "QQQ Pure 12-1 Momentum Top-3".

Step 1: Point-in-time Nasdaq-100 membership, rebuilt ONLY from the raw jmccarrell/n100tickers
YAML change logs (copied verbatim into research/.../data/nasdaq100_src). No project .py is imported,
no project-derived membership CSV is used (ndx_monthly_members.csv is read only for the final diff).

Rules
  * membership on calendar day d = tickers_on_Jan_1(year) + all dated changes with date <= d
    ("union" = added effective that day, "difference" = removed effective that day)
  * formation month-end t: membership as of t (changes dated <= t)
  * internal consistency: applying year Y changes must reproduce tickers_on_Jan_1(Y+1)

Outputs
  u_monthly_members.csv     month_end,ticker
  u_yaml_chain_check.csv    year-to-year consistency
  u_diff_vs_project.csv     my roster vs project ndx_monthly_members.csv
"""
import glob
import os

import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', 'research', 'sector_stock_momentum', 'data', 'nasdaq100_src')
PROJ = os.path.join(HERE, '..', '..', 'research', 'sector_stock_momentum', 'data', 'ndx_monthly_members.csv')


def load_years():
    years = {}
    for f in sorted(glob.glob(os.path.join(SRC, 'n100-ticker-changes-*.yaml'))):
        # BaseLoader keeps every scalar a string: safe_load turns the ticker "ON" into bool True
        d = yaml.load(open(f), Loader=yaml.BaseLoader)
        ch = []
        for k, v in (d.get('changes') or {}).items():
            v = v or {}
            ch.append((pd.Timestamp(str(k)), set(v.get('union') or []), set(v.get('difference') or [])))
        ch.sort(key=lambda x: x[0])
        years[int(d['year'])] = (set(d['tickers_on_Jan_1']), ch)
    return years


def members_on(years, day):
    day = pd.Timestamp(day)
    s, ch = years[day.year]
    s = set(s)
    for dt, add, rem in ch:
        if dt <= day:
            s -= rem
            s |= add
    return s


def main():
    years = load_years()
    # chain check
    rows = []
    for y in sorted(years):
        if y + 1 not in years:
            continue
        end = members_on(years, f'{y}-12-31')
        nxt = years[y + 1][0]
        rows.append({'year': y, 'n_end_of_year': len(end), 'n_jan1_next': len(nxt),
                     'missing_in_next': '|'.join(sorted(end - nxt)), 'extra_in_next': '|'.join(sorted(nxt - end))})
    chain = pd.DataFrame(rows)
    chain.to_csv(os.path.join(HERE, 'u_yaml_chain_check.csv'), index=False)
    bad = chain[(chain.missing_in_next != '') | (chain.extra_in_next != '')]
    print(f'YAML chain check: {len(chain)} year transitions, {len(bad)} inconsistent')
    if len(bad):
        print(bad.to_string())

    # monthly roster
    months = pd.date_range('2007-12-31', '2026-09-30', freq='ME')
    out = []
    for t in months:
        for s in sorted(members_on(years, t)):
            out.append((t.date().isoformat(), s))
    M = pd.DataFrame(out, columns=['month_end', 'ticker'])
    M.to_csv(os.path.join(HERE, 'u_monthly_members.csv'), index=False)
    n = M.groupby('month_end').size()
    print(f'Monthly roster: {len(months)} months, members/month min {n.min()} median {int(n.median())} max {n.max()}')

    # diff vs project-derived roster (read only for comparison)
    P = pd.read_csv(PROJ)
    a = set(map(tuple, M.values))
    b = set(map(tuple, P[['month_end', 'ticker']].astype(str).values))
    only_me = sorted(a - b)
    only_proj = sorted(b - a)
    d = pd.DataFrame([(m, s, 'only_claude') for m, s in only_me] + [(m, s, 'only_project') for m, s in only_proj],
                     columns=['month_end', 'ticker', 'side'])
    d.to_csv(os.path.join(HERE, 'u_diff_vs_project.csv'), index=False)
    common = sorted(set(M.month_end) & set(P.month_end.astype(str)))
    print(f'Diff vs project ndx_monthly_members.csv over {len(common)} common months: '
          f'only_claude={len(only_me)}, only_project={len(only_proj)}')
    if len(d):
        print(d.groupby(['side', 'ticker']).size().head(40).to_string())


if __name__ == '__main__':
    main()
