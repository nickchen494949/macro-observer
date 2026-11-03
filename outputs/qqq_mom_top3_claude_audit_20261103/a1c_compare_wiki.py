#!/usr/bin/env python3
"""
a1c_compare_wiki.py — compare the YAML-derived PIT Nasdaq-100 roster with the independent snapshot
of the English-Wikipedia "Nasdaq-100" article live at each month-end (cached by a1b_fetch_wiki_ndx.py).

Parsing: take the components section (heading containing "omponent"), extract tickers from
"(TICK)", "{{NASDAQ|TICK}}"-style templates and table cells. Months whose snapshot yields < 90
tickers are reported as unparseable (article format did not contain a full list) rather than guessed.

Wikipedia edits can lag Nasdaq announcements by days/weeks, so each snapshot is compared both to the
YAML roster at the month-end and to the YAML roster on the revision's own timestamp.
Outputs: u_wiki_vs_yaml_monthly.csv, u_wiki_vs_yaml_disagreements.csv
"""
import glob
import json
import os
import re

import pandas as pd

import a1_universe as U

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = {'NASDAQ', 'NYSE', 'ADR', 'USA', 'US', 'CEO', 'ETF', 'GICS', 'NDX', 'QQQ', 'II', 'III', 'IV', 'LLC', 'PLC',
        'INC', 'NV', 'SA', 'AG', 'SE', 'CO', 'LTD', 'A', 'B', 'C', 'I', 'THE', 'AND', 'NA', 'N', 'S', 'P', 'SP'}
# share-class / punctuation variants that denote the same listing
NORM = {'BRK.B': 'BRKB', 'FOXA': 'FOXA'}


def components_section(w):
    m = re.search(r'\n(=+)\s*[^=\n]*(?:omponent|onstituent)[^=\n]*\1\s*\n', w)
    if not m:
        return None
    lvl = len(m.group(1))
    rest = w[m.end():]
    nxt = re.search(r'\n={%d}[^=]' % lvl if lvl > 1 else r'\n=[^=]', rest)
    # keep going through sub-headings, stop at the next heading of the same or higher level
    nxt = re.search(r'\n={1,%d}[^=\n][^\n]*?={1,%d}\s*\n' % (lvl, lvl), rest)
    return rest[: nxt.start()] if nxt else rest


def _chunk_tickers(chunk):
    """Tickers from list items ('#'/'*' lines) or table rows ('|' lines) of one chunk."""
    out = set()
    for line in chunk.split('\n'):
        ls = line.strip()
        if ls.startswith('#') or ls.startswith('*'):
            m = re.findall(r'\(\s*(?:NASDAQ:\s*)?([A-Z]{1,5})\s*\)', ls)
            m += [x.upper() for x in re.findall(r'\{\{\s*(?:nasdaq|NASDAQ|Nasdaq|NasdaqSymbol|nasdaqsymbol)\s*\|\s*([A-Za-z]{1,5})\s*[|}]', ls)]
            out |= set(m[:1])
        elif ls.startswith('|'):
            m = re.match(r'^\|\s*([A-Z]{1,5})\s*(\|\||$)', ls) or re.match(r'^\|\s*\{\{[^|}]*\|\s*([A-Z]{1,5})\s*\}\}', ls)
            if m:
                out.add(m.group(1))
            else:
                m = re.findall(r'\{\{\s*(?:nasdaq|NASDAQ|Nasdaq|NasdaqSymbol|nasdaqsymbol)\s*\|\s*([A-Za-z]{1,5})\s*[|}]', ls)
                out |= {x.upper() for x in m[:1]}
    return {NORM.get(x, x) for x in out if x not in STOP}


def _table_sets(w):
    """Ticker set of every wikitable: per row, the first cell that is a bare ticker."""
    out = []
    for tb in re.findall(r'\{\|.*?\n\|\}', w, re.S):
        got = set()
        for row in re.split(r'\n\|-', tb):
            cells = re.split(r'\|\||\n\||\n!|!!', row)
            for c in cells:
                c2 = re.sub(r'\{\{\s*(?:nasdaq|NASDAQ|Nasdaq|NasdaqSymbol|nasdaqsymbol)\s*\|\s*([A-Za-z]{1,5})\s*[|}][^}]*\}?\}?', r'\1', c).strip()
                c2 = re.sub(r'^style="[^"]*"\s*\|', '', c2).strip()
                if re.fullmatch(r'[A-Z]{1,5}', c2) and c2 not in STOP:
                    got.add(c2)
                    break
        out.append(got)
    return out


def tickers(sec, full=None):
    """Constituent list = the list/table whose size is plausible for the index (90..115 names, incl. AAPL),
    closest to 101. Change logs and 'historical components' tables are smaller/larger and lose."""
    cands = []
    for c in re.split(r'\n=+[^=\n]+=+\s*\n', sec or ''):
        cands.append(_chunk_tickers(c))
    if full is not None:
        cands += _table_sets(full)
    ok = [c for c in cands if 90 <= len(c) <= 115 and 'AAPL' in c]
    if not ok:
        return max(cands, key=len) if cands else set()
    return min(ok, key=lambda c: abs(len(c) - 101))


def main():
    years = U.load_years()
    rows, dis = [], []
    for f in sorted(glob.glob(os.path.join(HERE, 'wiki_ndx', '*.json'))):
        rec = json.load(open(f))
        me = pd.Timestamp(os.path.basename(f)[:-5])
        sec = components_section(rec['wikitext'])
        tk = tickers(sec, rec['wikitext'])
        rev_day = pd.Timestamp(rec['timestamp'][:10])
        y_me = U.members_on(years, me)
        y_rev = U.members_on(years, rev_day) if rev_day.year in years else set()
        parse_ok = len(tk) >= 90
        r = {'month_end': me.date(), 'revid': rec['revid'], 'rev_timestamp': rec['timestamp'], 'n_wiki': len(tk),
             'n_yaml': len(y_me), 'parse_ok': parse_ok}
        if parse_ok:
            a, b = tk - y_me, y_me - tk
            a2, b2 = tk - y_rev, y_rev - tk
            r.update({'only_wiki_vs_monthend': '|'.join(sorted(a)), 'only_yaml_vs_monthend': '|'.join(sorted(b)),
                      'n_diff_vs_monthend': len(a) + len(b),
                      'only_wiki_vs_revdate': '|'.join(sorted(a2)), 'only_yaml_vs_revdate': '|'.join(sorted(b2)),
                      'n_diff_vs_revdate': len(a2) + len(b2)})
            for s in a2:
                dis.append((me.date(), rec['timestamp'], s, 'in_wiki_not_yaml'))
            for s in b2:
                dis.append((me.date(), rec['timestamp'], s, 'in_yaml_not_wiki'))
        rows.append(r)
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(HERE, 'u_wiki_vs_yaml_monthly.csv'), index=False)
    D = pd.DataFrame(dis, columns=['month_end', 'rev_timestamp', 'ticker', 'side'])
    D.to_csv(os.path.join(HERE, 'u_wiki_vs_yaml_disagreements.csv'), index=False)
    ok = T[T.parse_ok]
    print(f'{len(T)} snapshots, parseable {len(ok)}; exact match vs revision-date roster: {(ok.n_diff_vs_revdate == 0).sum()}; '
          f'median diffs {ok.n_diff_vs_revdate.median()}, mean {ok.n_diff_vs_revdate.mean():.2f}')
    if len(D):
        print(D.groupby(['ticker', 'side']).size().sort_values(ascending=False).head(40).to_string())


if __name__ == '__main__':
    main()
