#!/usr/bin/env python3
"""
build_fundamentals.py — turn the raw SEC quarterly extracts into a point-in-time (PIT)
fundamentals store for the S&P 500 universe (all members since 2008), split by GICS sector.

Inputs
  data/fundamentals/sec_raw/{sub,num}_<q>.parquet   (fetch_sec_fundamentals.py)
  data/sp500_ticker_start_end.csv                    (point-in-time membership spans)
  data/wiki_current_constituents.csv                 (current members: GICS sector + CIK)
  data/wiki_changes.csv                              (added/removed names → helps map delisted tickers)
  data/sec_company_tickers.csv                       (SEC current ticker → CIK)
  data/sectors.csv                                   (sector for every priced ticker)

Outputs (data/fundamentals/)
  cik_map.csv                 ticker → CIK, how it was matched, sector
  pit_long/<Sector>.parquet   every value as first reported + every later revision
                              (cols: ticker, cik, sector, tag, ddate, qtrs, uom, value, adsh, form,
                               fy, fp, filed, accepted, is_first_report)
  eps_quarterly_pit.parquet   one row per company × fiscal quarter, AS FIRST REPORTED:
                              EPS diluted/basic, net income, revenue, diluted shares,
                              TTM versions, and `available_date` (= filing date + 1 day)
  by_sector/<Sector>_eps_quarterly_pit.csv   same table split by sector (easy to open)
"""
import difflib, glob, os, re

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data')
F = os.path.join(D, 'fundamentals')
RAW = os.path.join(F, 'sec_raw')

YAHOO_LOG = os.path.join(HERE, 'fetch_sectors.log')

# SIC → GICS sector (coarse fallback when neither Wikipedia nor Yahoo has a sector)
def sic_to_sector(sic):
    try:
        s = int(sic)
    except Exception:  # noqa
        return None
    if 1000 <= s < 1500 and s not in (1311, 1381, 1382, 1389): return 'Materials'
    if s in (1311, 1381, 1382, 1389, 2911, 2990, 4610, 4612, 4613, 4922, 4923, 5171, 5172): return 'Energy'
    if 1500 <= s < 1800: return 'Industrials'
    if s in (2833, 2834, 2835, 2836, 3826, 3841, 3842, 3843, 3844, 3845, 3851, 5047, 5122, 8000, 8011, 8050, 8060,
             8062, 8071, 8090, 8093, 6324): return 'Health Care'
    if s in (3570, 3571, 3572, 3575, 3576, 3577, 3578, 3579, 3661, 3663, 3669, 3670, 3672, 3674, 3677, 3678, 3679,
             3825, 3827, 7370, 7371, 7372, 7373, 7374, 7379, 3559): return 'Information Technology'
    if s in (4800, 4812, 4813, 4822, 4833, 4841, 4899, 2711, 2721, 2731, 7812, 7819, 7822, 7829, 7830, 7841, 7900): return 'Communication Services'
    if 4900 <= s < 5000: return 'Utilities'
    if s in (6798,) or 6500 <= s < 6600: return 'Real Estate'
    if 6000 <= s < 6800: return 'Financials'
    if 2000 <= s < 2200 or s in (5140, 5141, 5149, 5180, 5190, 5400, 5411, 5412, 2840, 2844): return 'Consumer Staples'
    if 2800 <= s < 3000 or 2400 <= s < 2700 or 3200 <= s < 3400: return 'Materials'
    if 5000 <= s < 6000 or 7000 <= s < 7100 or s in (3711, 3714, 3751, 2300, 2320, 3021, 3942, 3944, 7510): return 'Consumer Discretionary'
    return 'Industrials'


def norm(name):
    n = str(name).lower()
    n = re.sub(r'&', ' and ', n)
    n = re.sub(r'[^a-z0-9 ]', ' ', n)
    stop = {'inc', 'incorporated', 'corp', 'corporation', 'co', 'company', 'ltd', 'plc', 'the', 'group', 'holdings',
            'holding', 'llc', 'lp', 'sa', 'nv', 'de', 'new', 'cos', 'companies', 'international', 'intl'}
    return ' '.join(w for w in n.split() if w not in stop)


def load_raw():
    subs = [pd.read_parquet(p) for p in sorted(glob.glob(os.path.join(RAW, 'sub_*.parquet')))]
    sub = pd.concat(subs, ignore_index=True)
    sub['filed'] = pd.to_datetime(sub.filed, format='%Y%m%d', errors='coerce')
    return sub


def build_cik_map(sub):
    spans = pd.read_csv(os.path.join(D, 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    spans = spans[spans.end_date.isna() | (spans.end_date >= '2008-01-01')]
    tickers = sorted(spans.ticker.unique())
    wiki = pd.read_csv(os.path.join(D, 'wiki_current_constituents.csv'))
    wiki_cik = dict(zip(wiki.Symbol, wiki.CIK))
    sec_t = pd.read_csv(os.path.join(D, 'sec_company_tickers.csv'))
    sec_cik = dict(zip(sec_t.ticker.str.replace('-', '.', regex=False), sec_t.cik_str))
    ch = pd.read_csv(os.path.join(D, 'wiki_changes.csv'))
    names = {}
    for t, n in list(zip(ch.removed_ticker, ch.removed_name)) + list(zip(ch.added_ticker, ch.added_name)):
        if isinstance(t, str) and isinstance(n, str):
            names.setdefault(t, n)
    # Yahoo longName printed by fetch_sectors.py
    if os.path.exists(YAHOO_LOG):
        for line in open(YAHOO_LOG):
            m = re.match(r'\[\d+/\d+\] (\S+) .*\| (.+)$', line.strip())
            if m and m.group(2) != 'None':
                names.setdefault(m.group(1).replace('-', '.'), m.group(2))

    # EDGAR filer windows + names
    fil = sub.groupby('cik').agg(first=('filed', 'min'), last=('filed', 'max'), name=('name', 'last'))
    allnames = sub[['cik', 'name']].drop_duplicates()
    allnames['n'] = allnames.name.map(norm)
    by_norm = allnames.groupby('n').cik.apply(set).to_dict()
    norm_keys = list(by_norm)

    def active(cik, s, e):
        if cik not in fil.index:
            return False
        r = fil.loc[cik]
        e = e if pd.notna(e) else pd.Timestamp.today()
        return r['first'] <= e + pd.Timedelta(days=120) and r['last'] >= max(s, pd.Timestamp('2009-06-01')) - pd.Timedelta(days=30)

    rows = []
    for t in tickers:
        sp = spans[spans.ticker == t]
        s, e = sp.start_date.min(), (sp.end_date.max() if sp.end_date.notna().all() else pd.NaT)
        cik, how, score = None, None, None
        if t in wiki_cik and pd.notna(wiki_cik[t]):
            cik, how = int(wiki_cik[t]), 'wikipedia_current'
        if cik is None and t in names:
            n = norm(names[t])
            cands = by_norm.get(n, set())
            cands = [c for c in cands if active(c, s, e)]
            if len(cands) == 1:
                cik, how, score = cands[0], 'name_exact', 1.0
            else:
                for k in difflib.get_close_matches(n, norm_keys, n=5, cutoff=0.88):
                    cc = [c for c in by_norm[k] if active(c, s, e)]
                    if cc:
                        cik, how, score = cc[0], 'name_fuzzy', difflib.SequenceMatcher(None, n, k).ratio()
                        break
        if cik is None and t in sec_cik and active(int(sec_cik[t]), s, e):
            cik, how = int(sec_cik[t]), 'sec_ticker_validated'
        rows.append({'ticker': t, 'cik': cik, 'method': how, 'match_score': score, 'name_hint': names.get(t),
                     'edgar_name': fil.name.get(cik) if cik is not None and cik in fil.index else None,
                     'member_start': s.date(), 'member_end': e.date() if pd.notna(e) else None})
    m = pd.DataFrame(rows)
    m['cik'] = m.cik.astype('Int64')

    # sector: Wikipedia GICS / Yahoo (sectors.csv) → SIC fallback
    sec = pd.read_csv(os.path.join(D, 'sectors.csv'))
    sec = sec[sec.sector != 'UNKNOWN']
    secmap = dict(zip(sec.ticker.str.replace('-', '.', regex=False), zip(sec.sector, sec.source)))
    sic = sub.dropna(subset=['sic']).groupby('cik').sic.last()
    m['sector'], m['sector_source'] = zip(*[
        secmap.get(t) if t in secmap else ((sic_to_sector(sic.get(c)), 'sic_approx') if pd.notna(c) and c in sic.index
                                           else (None, None)) for t, c in zip(m.ticker, m.cik)])
    return m


def build_long(sub, cmap):
    good = cmap.dropna(subset=['cik', 'sector'])
    cik2 = good.drop_duplicates('cik').set_index('cik')[['ticker', 'sector']]
    s = sub[sub.cik.isin(cik2.index)][['adsh', 'cik', 'form', 'fy', 'fp', 'fye', 'filed', 'accepted']]
    parts = []
    for p in sorted(glob.glob(os.path.join(RAW, 'num_*.parquet'))):
        n = pd.read_parquet(p)
        parts.append(n.merge(s, on='adsh', how='inner'))
    df = pd.concat(parts, ignore_index=True)
    df = df.join(cik2, on='cik')
    df['ddate'] = pd.to_datetime(df.ddate, format='%Y%m%d', errors='coerce')
    # a reported actual cannot be dated after its own filing (company tagging errors, e.g. PRGO 10-K 2013-08)
    df = df[df.ddate <= df.filed]
    df = df.sort_values(['cik', 'tag', 'ddate', 'qtrs', 'uom', 'filed', 'accepted'])
    key = ['cik', 'tag', 'ddate', 'qtrs', 'uom']
    df['is_first_report'] = ~df.duplicated(key, keep='first')
    # keep first report + any later filing that CHANGES the value (restatement); identical repeats add no info
    prev = df.groupby(key, sort=False).value.shift()
    df = df[df.is_first_report | (df.value.round(6) != prev.round(6))]
    return df


def eps_panel(long):
    """Quarterly, as-first-reported panel with derived Q4 and TTM, plus availability date."""
    want = {
        'eps_diluted': ['EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted'],
        'eps_basic': ['EarningsPerShareBasic', 'EarningsPerShareBasicAndDiluted'],
        'net_income': ['NetIncomeLoss', 'ProfitLoss'],
        'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet',
                    'RevenueFromContractWithCustomerIncludingAssessedTax', 'InterestAndDividendIncomeOperating'],
        'diluted_shares': ['WeightedAverageNumberOfDilutedSharesOutstanding'],
    }
    fr = long[long.is_first_report & long.qtrs.isin([1, 3, 4])]
    out = []
    for field, tags in want.items():
        sub = fr[fr.tag.isin(tags)].copy()
        sub['prio'] = sub.tag.map({t: i for i, t in enumerate(tags)})
        sub = sub.sort_values(['cik', 'ddate', 'qtrs', 'prio']).drop_duplicates(['cik', 'ddate', 'qtrs'])
        q1 = sub[sub.qtrs == 1][['cik', 'ddate', 'value', 'filed', 'fy', 'fp', 'form']]
        q1 = q1.assign(field=field, derived=False)
        # Q4 = FY (qtrs=4) − 9M YTD (qtrs=3) for the same fiscal year (shares: use FY weighted average)
        fy = sub[sub.qtrs == 4][['cik', 'ddate', 'value', 'filed', 'fy', 'fp', 'form']]
        ytd = sub[sub.qtrs == 3][['cik', 'ddate', 'value']].rename(columns={'ddate': 'd9', 'value': 'v9'})
        fy = fy.assign(lo=fy.ddate - pd.Timedelta(days=105), hi=fy.ddate - pd.Timedelta(days=75))
        mg = fy.merge(ytd, on='cik')
        mg = mg[(mg.d9 >= mg.lo) & (mg.d9 <= mg.hi)].drop_duplicates(['cik', 'ddate'])
        if field == 'diluted_shares':
            mg['value'] = mg['value']
        else:
            mg['value'] = mg['value'] - mg['v9']
        q4 = mg[['cik', 'ddate', 'value', 'filed', 'fy', 'fp', 'form']].assign(field=field, derived=True)
        # only add derived Q4 where no direct 3-month value exists
        have = set(zip(q1.cik, q1.ddate))
        q4 = q4[[(c, d) not in have for c, d in zip(q4.cik, q4.ddate)]]
        out.append(pd.concat([q1, q4]))
    x = pd.concat(out, ignore_index=True)
    piv = x.pivot_table(index=['cik', 'ddate'], columns='field', values='value', aggfunc='first')
    meta = (x.sort_values('filed').groupby(['cik', 'ddate'])
            .agg(filed=('filed', 'max'), fy=('fy', 'first'), fp=('fp', 'first'), form=('form', 'first'),
                 q4_derived=('derived', 'max')))
    p = piv.join(meta).reset_index().sort_values(['cik', 'ddate'])
    # TTM sums over the last 4 fiscal quarters (only if the 4 quarters are contiguous ≈ 1 year)
    for f in ['eps_diluted', 'eps_basic', 'net_income', 'revenue']:
        if f in p:
            g = p.groupby('cik')
            roll = g[f].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
            span = (p.ddate - g.ddate.shift(3)).dt.days
            p[f + '_ttm'] = roll.where(span.between(250, 290))
    # a TTM value is only known once ALL 4 quarters are filed
    fnum = p.filed.astype('int64')
    p['ttm_known_date'] = pd.to_datetime(fnum.groupby(p.cik).transform(lambda s: s.rolling(4, min_periods=1).max()))
    p['available_date'] = p.ttm_known_date + pd.Timedelta(days=1)   # conservative: next day after filing
    return p


def main():
    sub = load_raw()
    print('filings loaded', len(sub), 'quarters', sub.filed.min(), '→', sub.filed.max())
    cmap = build_cik_map(sub)
    cmap.to_csv(os.path.join(F, 'cik_map.csv'), index=False)
    print('CIK map:', cmap.method.value_counts(dropna=False).to_dict())
    print('sector source:', cmap.sector_source.value_counts(dropna=False).to_dict())

    long = build_long(sub, cmap)
    os.makedirs(os.path.join(F, 'pit_long'), exist_ok=True)
    for sec, g in long.groupby('sector'):
        g.drop(columns=['fye']).to_parquet(os.path.join(F, 'pit_long', sec.replace(' ', '_') + '.parquet'), index=False)
    print('long rows', len(long), 'companies', long.cik.nunique())

    p = eps_panel(long)
    tk = long.drop_duplicates('cik').set_index('cik')[['ticker', 'sector']]
    p = p.join(tk, on='cik')
    cols = ['ticker', 'cik', 'sector', 'ddate', 'fy', 'fp', 'form', 'filed', 'available_date', 'q4_derived',
            'eps_diluted', 'eps_basic', 'net_income', 'revenue', 'diluted_shares',
            'eps_diluted_ttm', 'eps_basic_ttm', 'net_income_ttm', 'revenue_ttm']
    p = p[[c for c in cols if c in p]].rename(columns={'ddate': 'period_end'})
    p.to_parquet(os.path.join(F, 'eps_quarterly_pit.parquet'), index=False)
    os.makedirs(os.path.join(F, 'by_sector'), exist_ok=True)
    for sec, g in p.groupby('sector'):
        g.to_csv(os.path.join(F, 'by_sector', sec.replace(' ', '_') + '_eps_quarterly_pit.csv'), index=False)
    print('eps panel rows', len(p), 'companies', p.cik.nunique())
    print(p.groupby('sector').cik.nunique())


if __name__ == '__main__':
    main()
