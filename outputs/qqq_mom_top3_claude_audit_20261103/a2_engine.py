#!/usr/bin/env python3
"""
a2_engine.py — Claude clean-room price / signal / return engine for the QQQ 12-1 momentum audit.

Written from scratch. Imports nothing from the project's research code. Reads only raw vendor files:
  research/sector_stock_momentum/data/raw/*.json          Yahoo daily close + adjclose
  research/sector_stock_momentum/data/raw_open/*.json     Yahoo daily open + adj_open
  research/sector_stock_momentum/data/raw_ndx/*.json      Tiingo daily close + adjclose (NDX-only names)
  research/sector_stock_momentum/data/raw_tiingo/*.json   Tiingo daily close + adjclose (delisted names)
  research/sector_stock_momentum/data/raw_wiki/*.json     Quandl WIKI close + adjclose (to 2018-03)
  research/sector_stock_momentum/data/wiki_bulk/*.parquet Quandl WIKI bulk close/adj_close/adj_open
  research/sector_stock_momentum/data/raw_archive/*.json  archived adjusted closes (QSTK etc.)
  outputs/qqq_mom_top3_claude_audit_20261103/tiingo/*.json  Tiingo EOD fetched by this audit (adjOpen/adjClose)
  outputs/tech_top1_independent_audit_20261103/tiingo/*.json  same Tiingo endpoint, fetched 2026-11-02/03

Every ratio (momentum or holding return) is computed inside ONE series of ONE store, never across
stores, so different dividend-adjustment bases can never be mixed.
"""
import functools
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
D = os.path.join(ROOT, 'research', 'sector_stock_momentum', 'data')
TIINGO_DIRS = [os.path.join(HERE, 'tiingo'), os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103', 'tiingo')]

# ---------------------------------------------------------------------------------------------
# Identity map: Nasdaq-100 ticker valid at the time -> symbol under which a vendor stores the SAME
# security today. Each entry is a rename of one legal entity (same SEC filer), verified in a2b_identity.py
# by price overlap / SEC CIK where data allows. Applied only when the ticker itself has no series.
RENAME = {
    'PCLN': ('BKNG', 'Priceline Group renamed Booking Holdings 2018-02-27 (SEC CIK 1075531)'),
    'ERTS': ('EA', 'Electronic Arts Nasdaq symbol ERTS->EA 2011 (SEC CIK 712515)'),
    'HANS': ('MNST', 'Hansen Natural renamed Monster Beverage 2012-01-05 (SEC CIK 865752)'),
    'KFT': ('MDLZ', 'Kraft Foods Inc renamed Mondelez International 2012-10-01 (SEC CIK 1103982)'),
    'WFMI': ('WFM', 'Whole Foods Market symbol WFMI->WFM 2011 (SEC CIK 865436)'),
    'JOYG': ('JOY', 'Joy Global moved Nasdaq JOYG -> NYSE JOY 2011 (SEC CIK 801898)'),
    'CTRP': ('TCOM', 'Ctrip.com renamed Trip.com Group 2019-10-25, ADR symbol CTRP->TCOM'),
    'RIMM': ('BB', 'Research In Motion renamed BlackBerry 2013, RIMM->BBRY->BB'),
    'LINTA': ('QVCA', 'Liberty Interactive Series A reclassified as QVC Group tracking stock QVCA 2014-10'),
    'VIP': ('VEON', 'VimpelCom renamed VEON 2017, ADR symbol VIP->VEON'),
    'FB': ('META', 'Facebook renamed Meta Platforms, FB->META 2022-06-09 (SEC CIK 1326801)'),
    'DISCA': ('WBD', 'Discovery Series A became Warner Bros. Discovery 2022-04 (SEC CIK 1437107)'),
    'SYMC': ('GEN', 'Symantec -> NortonLifeLock (NLOK, 2019) -> Gen Digital (GEN, 2022) (SEC CIK 849399)'),
    'WLTW': ('WTW', 'Willis Towers Watson symbol WLTW->WTW 2022-01 (SEC CIK 1140536)'),
    'NLOK': ('GEN', 'NortonLifeLock renamed Gen Digital 2022-11, NLOK->GEN (SEC CIK 849399)'),
    'FOXA': ('TFCFA', 'Twenty-First Century Fox class A: after the Disney deal (2019-03) the old shares traded as TFCFA until 2019-03-20; '
                      'Tiingo TFCFA carries the 21CF history. New Fox Corp (FOXA from 2019-03) is a different series and is never spliced.'),
    'FOX': ('TFCF', 'Twenty-First Century Fox class B, same as above (TFCF).'),
    'FISV': ('FI', 'Fiserv symbol FISV->FI 2023-06 (SEC CIK 798354)'),
}
# Corporate actions that vendor adjustment factors get wrong (found by a7 identity / jump scans).
# ticker: (ex_date, true total return from the previous close to the ex-date close, evidence)
# All prices of every store BEFORE ex_date are rescaled so the prev->ex return equals the true value.
CORP_FIX = {
    'IACI': ('2008-08-21', 19.415 / 17.60 - 1,
             'IAC 2008-08-20 spin-off of HSNi/Ticketmaster/ILG/Tree.com (0.2/0.2/0.2/1/30 per share) + 1-for-2 reverse split. '
             'Old IACI close 2008-08-20 = 17.60; package on 2008-08-21 = 0.5*16.63 IACI + 0.2*15.29 HSNI + 0.2*23.09 TKTM '
             '+ 0.2*15.88 IILG + 1/30*7.46 TREE = 19.415 -> +10.31%. Tiingo adj implies +50.9%, WIKI adj implies -24.6%; both wrong. '
             'Unadjusted closes from Quandl WIKI; TKTM close from LA Times/Washington Post 2008-08-21 reports.'),
}
STORES_CLOSE = ['yahoo', 'tiingo_api', 'raw_ndx', 'raw_tiingo', 'raw_wiki', 'wikibulk', 'raw_archive']


def _json(fn):
    return json.load(open(fn))


@functools.lru_cache(maxsize=1)
def _wikibulk():
    w = pd.read_parquet(os.path.join(D, 'wiki_bulk', 'wiki_prices.parquet'), columns=['ticker', 'date', 'adj_close'])
    o = pd.read_parquet(os.path.join(D, 'wiki_bulk', 'wiki_open.parquet'))
    w = w.merge(o, on=['ticker', 'date'], how='left')
    w['date'] = pd.to_datetime(w['date'])
    return {k: g.set_index('date')[['adj_close', 'adj_open']].sort_index() for k, g in w.groupby('ticker')}


def _clean(s):
    s = s[~s.index.duplicated(keep='last')].sort_index()
    s = s.replace([np.inf, -np.inf], np.nan)
    return s[(s > 0)].dropna()


CUTOFF = None   # truncation test: if set, every series is physically cut at this date BEFORE any cleaning


def series(store, sym):
    """Return DataFrame[date -> adjclose, adjopen] for one store/symbol, or None (cut at CUTOFF if set)."""
    return _series_cut(store, sym, CUTOFF)


@functools.lru_cache(maxsize=None)
def _series_cut(store, sym, cutoff):
    df = _load(store, sym)
    if df is None:
        return None
    if cutoff is not None:
        df = df.loc[:pd.Timestamp(cutoff)]
    if not len(df):
        return None
    # Frozen-quote removal: some vendors keep repeating the last trade after a delisting
    # (e.g. Tiingo SGEN repeats 228.74 from 2023-12-13 to 2026). Any run of >=5 identical adj closes
    # keeps only its first observation. (Applied after the cut, so it only uses data known at the cut.)
    c = df['adjclose']
    same = c.eq(c.shift(1)) & c.notna()
    run_id = (~same).cumsum()
    run_len = same.groupby(run_id).transform('sum') + 1
    frozen = same & (run_len >= 5)
    df = df[~frozen]
    return df if len(df) else None


@functools.lru_cache(maxsize=None)
def _load(store, sym):
    try:
        if store == 'yahoo':
            fc = os.path.join(D, 'raw', f'{sym}.json')
            fo = os.path.join(D, 'raw_open', f'{sym}.json')
            if not os.path.exists(fc) and not os.path.exists(fo):
                return None
            if os.path.exists(fo):   # raw_open carries close/adjclose AND open/adj_open in one consistent download
                d = _json(fo)
                df = pd.DataFrame({'adjclose': d['adjclose'], 'adjopen': d['adj_open']}, index=pd.to_datetime(d['dates']))
            else:
                d = _json(fc)
                df = pd.DataFrame({'adjclose': d['adjclose'], 'adjopen': np.nan}, index=pd.to_datetime(d['dates']))
        elif store == 'tiingo_api':
            fn = next((os.path.join(t, f'{sym}.json') for t in TIINGO_DIRS if os.path.exists(os.path.join(t, f'{sym}.json'))), None)
            if fn is None:
                return None
            rows = _json(fn)['rows']
            df = pd.DataFrame(rows)
            df.index = pd.to_datetime(df['date'].str[:10])
            df = df.rename(columns={'adjClose': 'adjclose', 'adjOpen': 'adjopen'})[['adjclose', 'adjopen']]
        elif store in ('raw_ndx', 'raw_tiingo', 'raw_wiki', 'raw_archive'):
            fn = os.path.join(D, store, f'{sym}.json')
            if not os.path.exists(fn):
                return None
            d = _json(fn)
            df = pd.DataFrame({'adjclose': d['adjclose'], 'adjopen': np.nan}, index=pd.to_datetime(d['dates']))
        elif store == 'wikibulk':
            w = _wikibulk().get(sym)
            if w is None:
                return None
            df = w.rename(columns={'adj_close': 'adjclose', 'adj_open': 'adjopen'})
        else:
            raise ValueError(store)
    except Exception:
        return None
    df = df.apply(pd.to_numeric, errors='coerce')
    df = df[~df.index.duplicated(keep='last')].sort_index()
    df.loc[~(df['adjclose'] > 0), 'adjclose'] = np.nan
    df.loc[~(df['adjopen'] > 0), 'adjopen'] = np.nan
    df = df[df['adjclose'].notna() | df['adjopen'].notna()]
    fix = CORP_FIX.get(sym)
    if fix is not None and len(df):
        ex = pd.Timestamp(fix[0])
        pre, post = df['adjclose'].loc[:ex - pd.Timedelta(days=1)].dropna(), df['adjclose'].loc[ex:].dropna()
        if len(pre) and len(post) and post.index[0] == ex:
            k = (post.iloc[0] / pre.iloc[-1]) / (1 + fix[1])
            df.loc[df.index < ex, ['adjclose', 'adjopen']] *= k
    return df if len(df) else None


def candidates(tk):
    """(store, symbol) series to try for NDX ticker tk, in precedence order."""
    syms = [tk]
    if tk in RENAME and RENAME[tk][0] != tk:
        syms.append(RENAME[tk][0])
    out = []
    for sym in syms:
        for st in STORES_CLOSE:
            if series(st, sym) is not None:
                out.append((st, sym))
    return out


@functools.lru_cache(maxsize=1)
def calendar():
    """NYSE trading days = union of SPY dates from Yahoo and Tiingo (both are full-history ETFs)."""
    a = series('yahoo', 'SPY').index
    b = series('tiingo_api', 'SPY')
    idx = a.union(b.index) if b is not None else a
    return pd.DatetimeIndex(sorted(idx))


def month_ends(start, end):
    return pd.date_range(start, end, freq='ME')


def first_td_after(t, n=1):
    """n-th trading day strictly after t (n=1: first trading day of the next month when t is a month-end)."""
    cal = calendar()
    i = cal.searchsorted(pd.Timestamp(t), side='right') + (n - 1)
    return cal[i] if i < len(cal) else None


def last_td_on_or_before(t):
    cal = calendar()
    i = cal.searchsorted(pd.Timestamp(t), side='right') - 1
    return cal[i] if i >= 0 else None


def px_at(df, col, t, max_stale_days=7):
    """Last valid value of df[col] on or before t, provided it is at most max_stale_days old."""
    s = df[col].loc[:t].dropna()
    if not len(s):
        return np.nan, None
    d = s.index[-1]
    if (pd.Timestamp(t) - d).days > max_stale_days:
        return np.nan, d
    return float(s.iloc[-1]), d


def max_gap_days(df, a, b):
    s = df['adjclose'].loc[a:b].dropna()
    if len(s) < 2:
        return 9999
    return int(np.diff(s.index.values).astype('timedelta64[D]').astype(int).max())


def momentum(tk, t, lb=12, skip=1, max_gap=30):
    """12-1 momentum = P[end of month t-skip] / P[end of month t-lb] - 1, from ONE series.
    Requires: a price at month-end t (<=7d stale, i.e. still trading), at t-skip and at t-lb month-ends,
    and no internal gap > max_gap calendar days between t-lb and t (identity / halt protection)."""
    t = pd.Timestamp(t)
    t_s = (t - pd.offsets.MonthEnd(skip)) if skip else t
    t_l = t - pd.offsets.MonthEnd(lb)
    for st, sym in candidates(tk):
        df = series(st, sym)
        p0, _ = px_at(df, 'adjclose', t)
        ps, _ = px_at(df, 'adjclose', t_s)
        pl, _ = px_at(df, 'adjclose', t_l)
        if np.isfinite(p0) and np.isfinite(ps) and np.isfinite(pl):
            if max_gap_days(df, t_l - pd.Timedelta(days=7), t) > max_gap:
                continue
            return ps / pl - 1.0, st, sym
    return np.nan, None, None


OPEN_STORES = ['yahoo', 'tiingo_api', 'wikibulk']


def hold_return(tk, t, mode='open', open_stores=None, n_day=1):
    """Holding return for a position formed at month-end t.
    mode='open'      : adj open of first trading day after t  -> adj open of first trading day after t+1m
    mode='close_t1'  : adj close of that first trading day     -> adj close of the next month's first trading day
    mode='close_t0'  : adj close at month-end t                -> adj close at month-end t+1 (no execution lag)
    Delisting inside the month: exit at the last available adj close of the same series (flag 'delist_last_close').
    Returns (ret, store, sym, flag, entry_date, exit_date)."""
    t = pd.Timestamp(t)
    t1 = t + pd.offsets.MonthEnd(1)
    e_d, x_d = first_td_after(t, n_day), first_td_after(t1, n_day)
    stores = open_stores or OPEN_STORES
    syms = [tk] + ([RENAME[tk][0]] if tk in RENAME and RENAME[tk][0] != tk else [])
    if mode == 'open':
        for sym in syms:
            for st in stores:
                df = series(st, sym)
                if df is None or e_d not in df.index or not np.isfinite(df.at[e_d, 'adjopen']):
                    continue
                po = df.at[e_d, 'adjopen']
                if x_d is not None and x_d in df.index and np.isfinite(df.at[x_d, 'adjopen']):
                    r = df.at[x_d, 'adjopen'] / po - 1.0
                    return r, st, sym, 'open_to_open', e_d, x_d
                # exit open missing: delisted (or halted) before x_d?
                after = df['adjclose'].loc[e_d:x_d].dropna() if x_d is not None else df['adjclose'].loc[e_d:].dropna()
                if x_d is not None and df.index.max() < x_d and len(after):
                    return after.iloc[-1] / po - 1.0, st, sym, 'delist_last_close', e_d, after.index[-1]
        # no open anywhere -> close proxy (first trading day close -> next month first trading day close)
        mode = 'close_t1'
        flag_fallback = 'no_open_close_proxy'
    else:
        flag_fallback = mode
    for st, sym in candidates(tk):
        df = series(st, sym)
        if mode == 'close_t1':
            a_d, b_d = e_d, x_d
        else:
            a_d, b_d = last_td_on_or_before(t), last_td_on_or_before(t1)
        pa, da = px_at(df, 'adjclose', a_d, max_stale_days=0)
        if not np.isfinite(pa):
            continue
        pb, db = px_at(df, 'adjclose', b_d, max_stale_days=0) if b_d is not None else (np.nan, None)
        if np.isfinite(pb):
            return pb / pa - 1.0, st, sym, flag_fallback, a_d, b_d
        after = df['adjclose'].loc[a_d:b_d].dropna()
        if len(after) and df.index.max() < b_d:
            return after.iloc[-1] / pa - 1.0, st, sym, flag_fallback + '+delist_last_close', a_d, after.index[-1]
    return np.nan, None, None, 'unpriced', e_d, x_d


def load_members():
    M = pd.read_csv(os.path.join(HERE, 'u_monthly_members.csv'), parse_dates=['month_end'])
    return {t: sorted(g.ticker) for t, g in M.groupby('month_end')}
