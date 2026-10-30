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

YAHOO_LOG = os.path.join(HERE, 'logs', 'fetch_sectors.log')

# Company names for removed tickers that Wikipedia's changes table does not name. These are only SEARCH
# HINTS: a CIK is accepted only if an EDGAR filer with that (normalised) name filed during the membership window.
NAME_HINTS = {
    'AABA': 'Yahoo Inc', 'ACS': 'Affiliated Computer Services', 'ANRZQ': 'Alpha Natural Resources',
    'ATGE': 'Adtalem Global Education', 'BDK': 'Black & Decker', 'BNI': 'Burlington Northern Santa Fe',
    'BTUUQ': 'Peabody Energy', 'CITGQ': 'CIT Group', 'EKDKQ': 'Eastman Kodak', 'HSH': 'Hillshire Brands',
    'JCP': 'Penney J C Co', 'MWV': 'MeadWestvaco', 'PBG': 'Pepsi Bottling Group', 'PX': 'Praxair',
    'QLGC': 'QLogic', 'RSHCQ': 'RadioShack', 'SUNEQ': 'SunEdison', 'WRK': 'WestRock', 'WYE': 'Wyeth',
    'LO': 'Lorillard', 'WIN': 'Windstream', 'WYND': 'Wyndham Worldwide', 'HOT': 'Starwood Hotel & Resorts Worldwide', 'TSS': 'Total System Services', 'MYL': 'Mylan', 'PKI': 'PerkinElmer', 'TMK': 'Torchmark', 'UTX': 'United Technologies',
    'BLL': 'Ball Corp', 'MMC': 'Marsh & McLennan', 'BK': 'Bank of New York Mellon', 'ANTM': 'Anthem',
    'ABC': 'AmerisourceBergen', 'CTL': 'CenturyLink', 'CBS': 'CBS Corp', 'HCP': 'HCP Inc', 'SYMC': 'Symantec',
    'NLOK': 'NortonLifeLock', 'PEAK': 'Healthpeak Properties', 'VIAC': 'ViacomCBS', 'BHGE': 'Baker Hughes',
    'FI': 'Fiserv', 'EQ': 'Embarq', 'JAVA': 'Sun Microsystems', 'LB': 'L Brands', 'BEAM': 'Beam Inc',
    'CCEP': 'Coca-Cola European Partners', 'CDAY': 'Ceridian HCM', 'DWDP': 'DowDuPont', 'CMCSK': 'Comcast',
}

# Hand-verified CIKs for tickers the automatic matcher got wrong (name re-use / ticker re-use).
# Each checked against EDGAR filer name + filing window (see git history 2026-10-28).
MANUAL_CIK = {
    'CA': 356028,      # CA, Inc. (not Cantaloupe)
    'BRCM': 1054374,   # Broadcom Corp (pre-2016; not Broadcom Ltd / Avago)
    'BBT': 92230,      # BB&T → Truist (same filer; ticker BBT later re-used)
    'PARA': 813828,    # Paramount Global / ViacomCBS (ticker PARA later re-used)
    'XRX': 108772,     # Xerox Corp 2009–2019 (Xerox Holdings 1770450 from 2019-11)
    # AGN: the AGN price series (and fja's AGN spell 1996-2020) is the Watson → Actavis → Allergan plc lineage
    # (close 64.77 on 2011-06-30 = Watson; Allergan Inc traded ~83 and is held separately as AGN-OLD). The old
    # mapping to Allergan Inc 850693 paired Allergan Inc fundamentals with Watson prices (found 2026-10-29 by
    # identity_screen_earnings.py, ratio 0.94). Actavis plc / Allergan plc 1578845 files from 2013-10; Watson /
    # Actavis Inc 884629 (2010-2013) is not mapped (single CIK per ticker) → fundamentals missing before 2013-10.
    'AGN': 1578845,
    'KRFT': 1545158,   # Kraft Foods Group 2012–2015 (not Kraft Foods Inc → Mondelez)
    'AIV': 922864,     # Apartment Investment & Management Co (not Apartment Income REIT spin-off)
}
# Members that never filed financial statements with the SEC (banks reporting to the FDIC, foreign
# 20-F filers): no SEC fundamentals exist — never matched.
NO_SEC_FILINGS = {'FRC': 'First Republic Bank — reported to FDIC', 'SBNY': 'Signature Bank — reported to FDIC',
                  'CCEP': 'Coca-Cola European Partners — foreign private issuer (20-F)'}

# SIC → GICS sector (coarse fallback when neither Wikipedia nor Yahoo has a sector)
def sic_to_sector(sic):
    try:
        s = int(sic)
    except Exception:  # noqa
        return None
    if 1000 <= s < 1500 and s not in (1311, 1381, 1382, 1389): return 'Materials'
    if s in (1311, 1381, 1382, 1389, 2911, 2990, 4610, 4612, 4613, 4922, 4923, 5171, 5172): return 'Energy'
    if 1500 <= s < 1800: return 'Industrials'
    if 4950 <= s < 4960: return 'Industrials'          # waste management (Stericycle, Republic, WM)
    if 8200 <= s < 8300: return 'Consumer Discretionary'   # education services (Apollo, DeVry)
    if s in (3651, 3630, 3634, 3639): return 'Consumer Discretionary'   # household audio / appliances (Harman, Whirlpool)
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
    n = re.sub(r'/[^/]*/?', ' ', str(name)).lower()     # EDGAR suffixes: "AETNA INC /PA/", "HARMAN … /DE/"
    n = re.sub(r'&', ' and ', n)
    n = re.sub(r'[^a-z0-9 ]', ' ', n)
    stop = {'inc', 'incorporated', 'corp', 'corporation', 'co', 'company', 'ltd', 'plc', 'the', 'group', 'holdings',
            'holding', 'llc', 'lp', 'sa', 'nv', 'de', 'new', 'cos', 'companies', 'international', 'intl'}
    words = [w for w in n.split() if w not in stop]
    out = []                                   # "c r bard" / "bard c r" → "cr bard" / "bard cr"
    for w in words:
        if len(w) == 1 and out and len(out[-1]) <= 3 and out[-1].isalpha() and getattr(norm, '_single', False):
            out[-1] += w
        else:
            out.append(w)
        norm._single = len(w) == 1
    norm._single = False
    return ' '.join(out)


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
    for t, n in zip(wiki.Symbol, wiki.Security):
        names.setdefault(t, n)
    for t, n in NAME_HINTS.items():
        names[t] = n                     # hand hints override Yahoo names of re-used tickers (EQ, JAVA, LB …)

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

    def overlap(cik, s, e):
        if cik not in fil.index:
            return -1
        r = fil.loc[cik]
        e = e if pd.notna(e) else pd.Timestamp.today()
        lo, hi = max(r['first'], s, pd.Timestamp('2009-04-01')), min(r['last'], e + pd.Timedelta(days=120))
        return (hi - lo).days

    def best(cands, s, e):
        cands = [c for c in cands if active(c, s, e)]
        return max(cands, key=lambda c: overlap(c, s, e)) if cands else None

    rows = []
    for t in tickers:
        sp = spans[spans.ticker == t]
        s, e = sp.start_date.min(), (sp.end_date.max() if sp.end_date.notna().all() else pd.NaT)
        cik, how, score = None, None, None
        if t in NO_SEC_FILINGS:
            rows.append({'ticker': t, 'cik': None, 'method': 'no_sec_filings: ' + NO_SEC_FILINGS[t], 'match_score': None,
                         'name_hint': names.get(t), 'edgar_name': None, 'member_start': s.date(),
                         'member_end': e.date() if pd.notna(e) else None})
            continue
        if t in MANUAL_CIK:
            cik, how = MANUAL_CIK[t], 'manual_verified'
        if cik is None and t in wiki_cik and pd.notna(wiki_cik[t]) and int(wiki_cik[t]) in fil.index:
            cik, how = int(wiki_cik[t]), 'wikipedia_current'
        if cik is None and t in names:
            n = norm(names[t])
            c = best(by_norm.get(n, set()), s, e)
            if c is not None:
                cik, how, score = c, 'name_exact', 1.0
            else:
                for k in difflib.get_close_matches(n, norm_keys, n=5, cutoff=0.88):
                    c = best(by_norm[k], s, e)
                    if c is not None:
                        cik, how, score = c, 'name_fuzzy', difflib.SequenceMatcher(None, n, k).ratio()
                        break
        if cik is None and t in sec_cik and active(int(sec_cik[t]), s, e):
            c = int(sec_cik[t])
            # tickers get re-used: if we know the historical name, it must resemble the EDGAR filer
            if t not in names or difflib.SequenceMatcher(None, norm(names[t]), norm(fil.name.get(c, ''))).ratio() >= 0.6:
                cik, how = c, 'sec_ticker_validated'
        if cik is None and t in names:
            # token match: every word of the hint appears in the EDGAR name (or vice versa), word order free
            hw = set(norm(names[t]).split())
            if hw:
                # one direction only: hint words ⊆ EDGAR words (the reverse matched "BANK FIRST" to First Republic)
                cands = [c for k_, cs in by_norm.items() for c in cs if hw <= set(k_.split())]
                c = best(set(cands), s, e)
                if c is not None:
                    cik, how, score = c, 'name_tokens', None
        rows.append({'ticker': t, 'cik': cik, 'method': how, 'match_score': score, 'name_hint': names.get(t),
                     'edgar_name': fil.name.get(cik) if cik is not None and cik in fil.index else None,
                     'member_start': s.date(), 'member_end': e.date() if pd.notna(e) else None})
    m = pd.DataFrame(rows)
    # renamed tickers inherit the successor's CIK (same filer) when they could not be matched directly
    import json as _json
    from ticker_aliases import build_aliases
    first = {}
    for d_ in [os.path.join(D, 'raw'), os.path.join(D, 'raw_tiingo')]:
        if os.path.isdir(d_):
            for f in os.listdir(d_):
                if f.endswith('.json') and not f.startswith('_'):
                    dd = _json.load(open(os.path.join(d_, f)))
                    if dd['dates']:
                        k = f[:-5]
                        first[k] = min(first.get(k, pd.Timestamp(dd['dates'][0])), pd.Timestamp(dd['dates'][0]))
    al, _ = build_aliases(first)
    tk2cik = dict(zip(m.ticker, m.cik))
    for r in al.itertuples():
        old, new = r.old, r.price_symbol.replace('-', '.')
        if pd.isna(tk2cik.get(old)) and pd.notna(tk2cik.get(new)):
            i = m.index[m.ticker == old]
            m.loc[i, ['cik', 'method']] = [tk2cik[new], f'alias_of_{new}']
            m.loc[i, 'edgar_name'] = fil.name.get(int(tk2cik[new]))
    m['cik'] = m.cik.astype('Int64')

    # sector: Wikipedia GICS / Yahoo (sectors.csv) → SIC fallback
    sec = pd.read_csv(os.path.join(D, 'sectors.csv'))
    sec = sec[sec.sector != 'UNKNOWN']
    secmap = dict(zip(sec.ticker.str.replace('-', '.', regex=False), zip(sec.sector, sec.source)))
    sic = sub.dropna(subset=['sic']).groupby('cik').sic.last()
    m['sic'] = [sic.get(c) if pd.notna(c) else None for c in m.cik]
    m['sic_sector'] = [sic_to_sector(x) if x is not None and pd.notna(x) else None for x in m.sic]
    # identity-safe order: Wikipedia GICS (current members) → SEC SIC of the matched filer → Yahoo (a former
    # member's Yahoo symbol may now belong to an unrelated company, e.g. S → SentinelOne)
    def pick(t, c):
        v = secmap.get(t)
        if v and v[1] == 'wikipedia_gics':
            return v
        if pd.notna(c) and c in sic.index and sic_to_sector(sic.get(c)):
            return sic_to_sector(sic.get(c)), 'sic_approx'
        return v if v else (None, None)
    m['sector'], m['sector_source'] = zip(*[pick(t, c) for t, c in zip(m.ticker, m.cik)])
    return m


def build_long(sub, cmap):
    good = cmap.dropna(subset=['cik', 'sector']).copy()
    # renamed companies share one CIK (BBT→TFC, HRS→LHX …): label rows with the CURRENT ticker,
    # keep every historical ticker in `all_tickers` so backtests can join on either
    good['_prio'] = (good.method != 'wikipedia_current').astype(int)
    alltk = good.groupby('cik').ticker.apply(lambda s: '|'.join(sorted(s)))
    cik2 = good.sort_values(['_prio', 'ticker']).drop_duplicates('cik').set_index('cik')[['ticker', 'sector']]
    cik2['all_tickers'] = alltk
    s = sub[sub.cik.isin(cik2.index)][['adsh', 'cik', 'form', 'fy', 'fp', 'fye', 'filed', 'accepted']]
    parts = []
    for p in sorted(glob.glob(os.path.join(RAW, 'num_*.parquet'))):
        n = pd.read_parquet(p)
        parts.append(n.merge(s, on='adsh', how='inner'))
    df = pd.concat(parts, ignore_index=True)
    df = df.join(cik2, on='cik')
    df['ddate'] = pd.to_datetime(df.ddate, format='%Y%m%d', errors='coerce')
    # FSDS rounds ddate to the NEAREST month-end, so a true period end can sit up to ~15 days before
    # ddate. A value whose rounded ddate is > 16 days after its own filing date cannot be an actual
    # (company tagging errors, e.g. PRGO 10-K filed 2013-08-15 with ddate 2013-12-31) → dropped & logged.
    bad = df[df.ddate > df.filed + pd.Timedelta(days=16)]
    bad[['ticker', 'cik', 'adsh', 'form', 'filed', 'tag', 'ddate', 'qtrs', 'value']].to_csv(
        os.path.join(F, 'dropped_future_dated_values.csv'), index=False)
    df = df[df.ddate <= df.filed + pd.Timedelta(days=16)]
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
        'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'SalesRevenueGoodsNet', 'SalesRevenueServicesNet',
                    'RevenueFromContractWithCustomerIncludingAssessedTax', 'InterestAndDividendIncomeOperating'],
        'diluted_shares': ['WeightedAverageNumberOfDilutedSharesOutstanding'],
    }
    # FSDS stores per-share units as 'USD' (numerator currency only); this filter mainly drops CAD/EUR/CNY… values
    UOM = {'eps_diluted': 'USD', 'eps_basic': 'USD', 'net_income': 'USD', 'revenue': 'USD',
           'diluted_shares': 'shares'}
    fr = long[long.is_first_report & long.qtrs.isin([1, 3, 4])]
    out, amb = [], []
    for field, tags in want.items():
        sub = fr[fr.tag.isin(tags) & (fr.uom == UOM[field])].copy()
        # ambiguity check: same company/period/duration/tag first-reported with >1 distinct value
        a = sub.groupby(['cik', 'tag', 'ddate', 'qtrs']).value.nunique()
        a = a[a > 1].reset_index().assign(field=field)
        amb.append(a)
        sub = sub[~sub.set_index(['cik', 'tag', 'ddate', 'qtrs']).index.isin(a.set_index(['cik', 'tag', 'ddate', 'qtrs']).index)]
        sub['prio'] = sub.tag.map({t: i for i, t in enumerate(tags)})
        # several tags can describe the same field (companies switch revenue tags, e.g. ASC 606 in 2018):
        # take the value that was PUBLIC FIRST (earliest filing), tag priority only breaks ties
        sub = sub.sort_values(['cik', 'ddate', 'qtrs', 'filed', 'prio']).drop_duplicates(['cik', 'ddate', 'qtrs'])
        q1 = sub[sub.qtrs == 1][['cik', 'ddate', 'value', 'filed', 'fy', 'fp', 'form']]
        q1 = q1.assign(field=field, derived=False)
        # Q4 = FY (qtrs=4) − 9M YTD (qtrs=3) for the same fiscal year (shares: use FY weighted average)
        fy = sub[sub.qtrs == 4][['cik', 'ddate', 'value', 'filed', 'fy', 'fp', 'form']]
        ytd = sub[sub.qtrs == 3][['cik', 'ddate', 'value']].rename(columns={'ddate': 'd9', 'value': 'v9'})
        fy = fy.assign(lo=fy.ddate - pd.Timedelta(days=105), hi=fy.ddate - pd.Timedelta(days=75))
        mg = fy.merge(ytd, on='cik')
        mg = fy.merge(ytd.merge(sub[sub.qtrs == 3][['cik', 'ddate', 'filed']].rename(columns={'ddate': 'd9', 'filed': 'f9'}),
                                on=['cik', 'd9']), on='cik')
        mg = mg[(mg.d9 >= mg.lo) & (mg.d9 <= mg.hi)].drop_duplicates(['cik', 'ddate'])
        mg['filed'] = mg[['filed', 'f9']].max(axis=1)      # a derived value is known only when ALL inputs are
        if field == 'diluted_shares':
            mg['value'] = mg['value']
        else:
            mg['value'] = mg['value'] - mg['v9']
        q4 = mg[['cik', 'ddate', 'value', 'filed', 'fy', 'fp', 'form']].assign(field=field, derived=True)
        # only add derived Q4 where no direct 3-month value exists
        have = set(zip(q1.cik, q1.ddate))
        q4 = q4[[(c, d) not in have for c, d in zip(q4.cik, q4.ddate)]]
        out.append(pd.concat([q1, q4]))
    pd.concat(amb).to_csv(os.path.join(F, 'ambiguous_values_excluded.csv'), index=False)
    x = pd.concat(out, ignore_index=True)
    piv = x.pivot_table(index=['cik', 'ddate'], columns='field', values='value', aggfunc='first')
    fpiv = x.pivot_table(index=['cik', 'ddate'], columns='field', values='filed', aggfunc='first')
    fpiv.columns = ['filed_' + c for c in fpiv.columns]          # each field keeps ITS OWN first-public date
    meta = (x.sort_values('filed').groupby(['cik', 'ddate'])
            .agg(fy=('fy', 'first'), fp=('fp', 'first'), form=('form', 'first'), q4_derived=('derived', 'max')))
    p = piv.join(fpiv).join(meta).reset_index().sort_values(['cik', 'ddate'])
    # row date = when this quarter's EPS (else net income) first became public
    p['filed'] = p.get('filed_eps_diluted', pd.Series(index=p.index, dtype='datetime64[ns]')).fillna(
        p.get('filed_net_income', pd.Series(index=p.index, dtype='datetime64[ns]')))
    # Q4 EPS = FY − 9M is NOT a reported number (share counts / dilution differ between periods).
    # Keep it only in *_approx columns; the reported columns stay empty for derived Q4 rows.
    for f in ['eps_diluted', 'eps_basic']:
        if f in p:
            p[f + '_approx'] = p[f]
            p.loc[p.q4_derived.fillna(False).astype(bool), f] = np.nan
    # TTM sums over the last 4 fiscal quarters (only if the 4 quarters are contiguous ≈ 1 year)
    # TTM EPS is built from the *_approx columns (it needs Q4) and is therefore itself approximate;
    # flows (net income, revenue) are additive, so their TTM is exact up to restatements.
    src = {'eps_diluted_approx': 'filed_eps_diluted', 'eps_basic_approx': 'filed_eps_basic',
           'net_income': 'filed_net_income', 'revenue': 'filed_revenue'}
    g = p.groupby('cik')
    span = (p.ddate - g.ddate.shift(3)).dt.days
    for f, fcol in src.items():
        if f in p and fcol in p:
            roll = g[f].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
            p[f + '_ttm'] = roll.where(span.between(250, 290))
            # a TTM value is public only once ALL 4 of its quarters are public
            fn = p[fcol].astype('int64').where(p[fcol].notna())
            known = fn.groupby(p.cik).transform(lambda s_: s_.rolling(4, min_periods=4).max())
            p[f + '_ttm_available_date'] = pd.to_datetime(known.where(p[f + '_ttm'].notna())) + pd.Timedelta(days=1)
    # quarterly row availability (this quarter's EPS / net income public) — conservative: next day after filing
    p['available_date'] = p.filed + pd.Timedelta(days=1)
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
    tk = long.drop_duplicates('cik').set_index('cik')[['ticker', 'all_tickers', 'sector']]
    p = p.join(tk, on='cik')
    cols = ['ticker', 'all_tickers', 'cik', 'sector', 'ddate', 'fy', 'fp', 'form', 'filed', 'available_date', 'q4_derived',
            'filed_eps_diluted', 'filed_eps_basic', 'filed_net_income', 'filed_revenue', 'filed_diluted_shares',
            'eps_diluted_approx_ttm_available_date', 'eps_basic_approx_ttm_available_date',
            'eps_diluted_approx_adj', 'eps_diluted_approx_ttm_adj', 'eps_basic_approx_ttm_adj',
            'net_income_ttm_available_date', 'revenue_ttm_available_date',
            'eps_diluted', 'eps_basic', 'eps_diluted_approx', 'eps_basic_approx', 'net_income', 'revenue',
            'diluted_shares', 'eps_diluted_approx_ttm', 'eps_basic_approx_ttm', 'net_income_ttm', 'revenue_ttm']
    # EPS on ONE share basis: each quarter is divided by the splits that happened after ITS OWN filing date
    # (= today's split-adjusted basis, same as Yahoo `close`), and only then summed into TTM.
    # (Summing raw quarters around a split mixes bases: NVDA 2024 3.71+4.92+5.98+0.67.)
    from fundamentals_pit import split_factor_after
    fac = [split_factor_after(t, f) if isinstance(t, str) and pd.notna(f) else np.nan
           for t, f in zip(p.ticker, p.filed_eps_diluted if 'filed_eps_diluted' in p else p.filed)]
    p['_fac'] = fac
    for f in ['eps_diluted_approx', 'eps_basic_approx']:
        if f in p:
            p[f + '_adj'] = p[f] / p['_fac']
            g = p.groupby('cik')
            roll = g[f + '_adj'].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
            span = (p.ddate - g.ddate.shift(3)).dt.days
            p[f + '_ttm_adj'] = roll.where(span.between(250, 290))
    p = p[[c for c in cols if c in p]].rename(columns={'ddate': 'period_end'})
    p.to_parquet(os.path.join(F, 'eps_quarterly_pit.parquet'), index=False)
    os.makedirs(os.path.join(F, 'by_sector'), exist_ok=True)
    for sec, g in p.groupby('sector'):
        g.to_csv(os.path.join(F, 'by_sector', sec.replace(' ', '_') + '_eps_quarterly_pit.csv'), index=False)
    print('eps panel rows', len(p), 'companies', p.cik.nunique())
    print(p.groupby('sector').cik.nunique())


if __name__ == '__main__':
    main()
