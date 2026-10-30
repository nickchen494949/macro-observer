"""
ticker_aliases.py — security identity across ticker changes (MMC→MRSH, FB→META, ANTM→ELV …).

Problem: the membership file lists the ticker that was valid at each date, but Yahoo stores the
whole price history under the CURRENT ticker (the old symbol is gone or re-used by someone else,
e.g. FB is now an unrelated security). Without this map a renamed member looks "missing" for its
entire pre-rename history.

Rule (otherwise the pair is logged as 'rejected' for manual review):
  1. fja05680: ticker A's membership ends within ±3 days of ticker B's membership start
  2. Wikipedia changes table does NOT list A as removed / B as added around that date
  3. Yahoo: B's price history starts ≥ 365 days before the switch date (B carries A's history)
  4. IDENTITY evidence, at least one of:
       (a) A and B (or B's later chain successor) have the same SEC CIK, or
       (b) B is a current member whose Wikipedia "Date added" is ≥ 365 days before the switch
           (B was already in the index under another ticker) and A's CIK, if known, does not differ.
     (Rules 1–3 alone are NOT enough: the 2008–10 Wikipedia changes table is incomplete, so real
      replacements such as BSC→ISRG would otherwise pass.)
If several A's qualify for one B, the one sharing the CIK wins; if still ambiguous → rejected.
Share classes (GOOG/GOOGL, FOX/FOXA …) are never merged because their memberships overlap.
"""
import json, os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data')


# Renames the automatic rule cannot prove (old ticker has no CIK match in our map). Each one is the SAME
# legal entity / SEC filer before and after (checked against EDGAR filer history):
MANUAL = {
    'LB': ('BBWI', 'L Brands renamed Bath & Body Works Inc, same filer CIK 701985 (2021)'),
    'CTL': ('LUMN', 'CenturyLink renamed Lumen Technologies, same filer CIK 18926 (2020)'),
    'CBS': ('VIAC', 'CBS Corp absorbed Viacom and renamed ViacomCBS, same filer CIK 813828 (2019)'),
    'VIAC': ('PARA', 'ViacomCBS renamed Paramount Global, same filer CIK 813828 (2022)'),
    'HCP': ('PEAK', 'HCP Inc renamed Healthpeak Properties, same filer CIK 765880 (2019)'),
    'SYMC': ('NLOK', 'Symantec renamed NortonLifeLock, same filer CIK 849399 (2019)'),
    'UTX': ('RTX', 'United Technologies renamed Raytheon Technologies, same filer CIK 101829 (2020)'),
    'GPS': ('GAP', 'Gap Inc changed ticker GPS→GAP (2024), same filer CIK 39911'),
    'FBHS': ('FBIN', 'Fortune Brands Home & Security renamed Fortune Brands Innovations, same filer CIK 1519751 (2022)'),
    'KORS': ('CPRI', 'Michael Kors Holdings renamed Capri Holdings, same filer CIK 1530721 (2018)'),
    'COG': ('CTRA', 'Cabot Oil & Gas renamed Coterra Energy, same filer CIK 858470 (2021)'),
    'DISCA': ('WBD', 'Discovery Inc (Series A) became Warner Bros. Discovery common, same filer CIK 1437107 (2022)'),
    'ARNC': ('HWM', 'Arconic Inc (formerly Alcoa Inc) renamed Howmet Aerospace, same filer CIK 4281 (2020)'),
    'WLTW': ('WTW', 'Willis Towers Watson ticker WLTW→WTW (2022), same filer CIK 1140536'),
    'SIVB': ('SIVBQ', 'SVB Financial Group: after the March-2023 failure the same shares traded OTC as SIVBQ'),
    'FRC': ('FRCB', 'First Republic Bank: after the May-2023 failure the same shares traded OTC as FRCB'),
    'WYND': ('TNL', 'Wyndham Worldwide → Wyndham Destinations (2018) → Travel + Leisure Co (2021), same filer CIK 1361658'),
    'CDAY': ('DAY', 'Ceridian HCM renamed Dayforce, ticker CDAY→DAY 2024-02-01, same filer CIK 1725057'),
    'HFC': ('DINO', 'HollyFrontier became HF Sinclair (DINO) in 2022; Tiingo carries the HollyFrontier history under DINO'),
    'DWDP': ('DD', 'DowDuPont renamed DuPont de Nemours, ticker DWDP→DD 2019-06-03, same filer CIK 1666700 '
                   '(only the 2017-09-01..2019-06-02 segment of the DD series is DowDuPont; segment breaks separate it)'),
}
# Tickers that denote DIFFERENT companies before/after a date inside ONE membership spell.
# Before the date the index security is priced from the given successor ticker; a new price segment
# starts at the date so momentum/returns never bridge the two companies.
TIME_SPLIT = {   # ticker: (date, symbol priced BEFORE the date, symbol priced FROM the date, why)
    'IR': ('2020-03-02', 'TT', 'IR', 'Ingersoll-Rand plc (renamed Trane Technologies, ticker TT, same filer CIK 1466258) '
                                     'until 2020-03-02; afterwards Ingersoll Rand Inc (ex Gardner Denver)'),
    'BHGE': ('2017-07-03', 'BHI', 'BKR', 'old Baker Hughes Inc (BHI) until the 2017-07-03 GE Oil & Gas combination; '
                                        'afterwards Baker Hughes, a GE company (BHGE) = today\'s BKR'),
}
# NOT aliased on purpose: DISCK (class C traded separately from DISCA until 2022 — using WBD would duplicate
# DISCA), share classes in general.


def build_aliases(first_price_date):
    """first_price_date: dict yahoo_symbol → first date with a price. Returns (accepted, rejected) DataFrames."""
    sp = pd.read_csv(os.path.join(D, 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    ch = pd.read_csv(os.path.join(D, 'wiki_changes.csv'))
    ch['date'] = pd.to_datetime(ch.date, errors='coerce')
    cmap_p = os.path.join(D, 'fundamentals', 'cik_map.csv')
    cik = dict(pd.read_csv(cmap_p)[['ticker', 'cik']].dropna().values) if os.path.exists(cmap_p) else {}
    wiki = pd.read_csv(os.path.join(D, 'wiki_current_constituents.csv'))
    cik.update({t: c for t, c in zip(wiki.Symbol, wiki.CIK)})

    def listed(tk, col, d):
        x = ch[(ch[col] == tk) & ((ch.date - d).abs() <= pd.Timedelta(days=7))]
        return len(x) > 0

    y = lambda t: t.replace('.', '-')
    added = dict(zip(wiki.Symbol, pd.to_datetime(wiki['Date added'], errors='coerce')))
    acc, rej = [], []
    # walk newest → oldest so a later rename (PEAK→DOC) lends its CIK to the earlier one (HCP→PEAK)
    succ = {}
    def cik_of(t):
        seen = set()
        while t not in cik and t in succ and t not in seen:
            seen.add(t); t = succ[t]
        return cik.get(t)
    starts = sp.sort_values('start_date', ascending=False)
    for b in starts.itertuples():
        if b.start_date < pd.Timestamp('2008-01-01'):
            continue
        cands = sp[sp.end_date.notna() & ((sp.end_date - b.start_date).abs() <= pd.Timedelta(days=3)) & (sp.ticker != b.ticker)]
        cands = [a for a in cands.ticker if not listed(a, 'removed_ticker', b.start_date)]
        if not cands or listed(b.ticker, 'added_ticker', b.start_date):
            continue
        fp = first_price_date.get(y(b.ticker))
        carries = fp is not None and fp <= b.start_date - pd.Timedelta(days=365)
        cb = cik_of(b.ticker)
        same = [a for a in cands if cb is not None and cik.get(a) == cb]
        if len(same) == 1:
            cands, evidence = same, 'same_cik'
        else:
            cands = [a for a in cands if cik.get(a) is None or cik.get(a) == cb]
            old_member = b.ticker in added and pd.notna(added[b.ticker]) and \
                added[b.ticker] <= b.start_date - pd.Timedelta(days=365)
            evidence = 'wiki_date_added' if old_member else None
        row = {'old': cands[0] if len(cands) == 1 else '|'.join(cands), 'new': b.ticker,
               'switch_date': b.start_date.date(), 'new_first_price': fp.date() if fp is not None else None,
               'evidence': evidence}
        if len(cands) == 1 and carries and evidence:
            acc.append(row)
            succ[cands[0]] = b.ticker
        else:
            row['why'] = ('ambiguous' if len(cands) > 1 else 'no candidate' if not cands
                          else 'no identity evidence' if not evidence else 'new ticker has no earlier price history')
            rej.append(row)
    done = {r['old'] for r in acc}
    # renames found via SEC: same CIK now trades under another ticker (resolve_successors.py)
    sp_ = os.path.join(D, 'sec_successor_aliases.csv')
    if os.path.exists(sp_):
        def overlap(a, b):          # share classes (FOX/FOXA, GOOG/GOOGL) are members at the same time
            A, B = sp[sp.ticker == a], sp[sp.ticker == b.replace('-', '.')]
            return any(x.start_date < (y.end_date if pd.notna(y.end_date) else pd.Timestamp('2100-01-01')) and
                       y.start_date < (x.end_date if pd.notna(x.end_date) else pd.Timestamp('2100-01-01'))
                       for x in A.itertuples() for y in B.itertuples())
        for r in pd.read_csv(sp_).itertuples():
            if r.status == 'accepted' and r.old not in done and r.old not in MANUAL and not overlap(r.old, r.new):
                acc.append({'old': r.old, 'new': r.new.replace('-', '.'), 'switch_date': None, 'new_first_price': None,
                            'evidence': f'sec_current_ticker_same_cik {int(r.cik)}'})
                done.add(r.old)
    for a, (b, why) in MANUAL.items():
        if a not in done:
            acc.append({'old': a, 'new': b, 'switch_date': None, 'new_first_price': None, 'evidence': 'manual: ' + why})
    acc = pd.DataFrame(acc)
    # resolve chains (HCP→PEAK→DOC): map every old ticker to the LAST ticker in its chain
    if len(acc):
        nxt = dict(zip(acc.old, acc.new))
        def final(t):
            seen = set()
            while t in nxt and t not in seen:
                seen.add(t); t = nxt[t]
            return t
        acc['price_symbol'] = [y(final(t)) for t in acc.new]
    return acc, pd.DataFrame(rej)


if __name__ == '__main__':
    raw = os.path.join(D, 'raw')
    fpd = {}
    for f in os.listdir(raw):
        if f.endswith('.json') and not f.startswith('_'):
            d = json.load(open(os.path.join(raw, f)))
            if d['dates']:
                fpd[f[:-5]] = pd.Timestamp(d['dates'][0])
    a, r = build_aliases(fpd)
    print('accepted\n', a.to_string(index=False))
    print('rejected\n', r.to_string(index=False))
