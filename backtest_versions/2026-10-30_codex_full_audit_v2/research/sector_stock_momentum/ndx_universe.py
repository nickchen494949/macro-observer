#!/usr/bin/env python3
"""
ndx_universe.py — S&P 500 ∪ Nasdaq-100 universe on top of the audited backtest infrastructure.

Nothing in backtest.py is edited. `load_union()` temporarily swaps three module globals of backtest.py:
  read_spells  → S&P spells ∪ Nasdaq-100 spells (data/ndx_spells.csv, tickers mapped by data/ndx_symbol_map.csv),
                 so the SAME integrity rules apply to NDX names (segment kept only if it overlaps a membership spell;
                 a spell is untrusted if the price series starts after it)
  RAW_TIINGO   → a scratch folder with links to data/raw_tiingo/* + Tiingo files of data/raw_ndx/*
  RAW_WIKI     → a scratch folder with links to data/raw_wiki/*   + WIKI files of data/raw_ndx/*
  RES          → results/ndx/ (load_prices writes price_integrity.csv etc.; the S&P result files stay untouched)
Membership at month-end t = S&P members (bt.load_membership) ∪ NDX members (data/ndx_monthly_members.csv, mapped).
Sectors = bt.build_sector_table ∪ data/ndx_sectors.csv (only for tickers the S&P table does not know), then the same
historical GICS rebuild (historical_sectors.build_panel).
"""
import os, shutil

import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data')
RES_NDX = os.path.join(HERE, 'results', 'ndx')
SCRATCH = os.path.join(D, '_union_scratch')          # rebuilt on every call, git-ignored


def symbol_map():
    """NDX ticker → universe symbol (renames / existing S&P columns); None = not usable (skip / gap)."""
    mp = pd.read_csv(os.path.join(D, 'ndx_symbol_map.csv'))
    out = {}
    for r in mp.itertuples():
        out[r.ndx_ticker] = r.target if r.action in ('map_existing', 'fetch_tiingo', 'fetch_wiki') else None
    return out


def ndx_spells():
    sp = pd.read_csv(os.path.join(D, 'ndx_spells.csv'), parse_dates=['start_date', 'end_date'])
    m = symbol_map()
    sp['ticker'] = [m.get(t, t) for t in sp.ticker]
    sp = sp.dropna(subset=['ticker'])
    # members since before the 2007-01-01 coverage start: the true start is unknown but earlier → keep 2007-01-01,
    # the integrity rule then asks for prices from <= 2007-01-10 + 10 days (same as for S&P spells before 2007)
    return sp[['ticker', 'start_date', 'end_date']]


def ndx_members(month_ends):
    mm = pd.read_csv(os.path.join(D, 'ndx_monthly_members.csv'), parse_dates=['month_end'])
    m = symbol_map()
    mm['sym'] = [m.get(t, t) for t in mm.ticker]
    mm = mm.dropna(subset=['sym'])
    g = mm.groupby('month_end').sym.apply(set)
    return {t: g.get(t, set()) for t in month_ends}


def _scratch():
    if os.path.isdir(SCRATCH):
        shutil.rmtree(SCRATCH)
    import json
    dirs = {}
    for k, base in [('tiingo', bt.RAW_TIINGO), ('wiki', bt.RAW_WIKI)]:
        d = os.path.join(SCRATCH, k)
        os.makedirs(d)
        for f in os.listdir(base):
            if f.endswith('.json') and not f.startswith('_'):
                os.symlink(os.path.join(base, f), os.path.join(d, f))
        dirs[k] = d
    clash = []
    nd = os.path.join(D, 'raw_ndx')
    for f in sorted(os.listdir(nd)) if os.path.isdir(nd) else []:
        if not f.endswith('.json') or f.startswith('_'):
            continue
        j = json.load(open(os.path.join(nd, f)))
        if not j.get('covers_membership'):
            continue                                   # identity check failed at download → not used
        dst = os.path.join(dirs[j['source']], f)
        if os.path.exists(dst):
            clash.append(f)
            continue                                   # the S&P store's file wins
        os.symlink(os.path.join(nd, f), dst)
    return dirs, clash


def load_union():
    os.makedirs(RES_NDX, exist_ok=True)
    dirs, clash = _scratch()
    saved = (bt.read_spells, bt.RAW_TIINGO, bt.RAW_WIKI, bt.RES)
    orig = bt.read_spells

    def read_spells_union():
        return pd.concat([orig(), ndx_spells()], ignore_index=True)
    try:
        bt.read_spells, bt.RAW_TIINGO, bt.RAW_WIKI, bt.RES = read_spells_union, dirs['tiingo'], dirs['wiki'], RES_NDX
        daily, P, aliases, bad = bt.load_prices()
    finally:
        bt.read_spells, bt.RAW_TIINGO, bt.RAW_WIKI, bt.RES = saved
        shutil.rmtree(SCRATCH, ignore_errors=True)
    if clash:
        print('raw_ndx files shadowed by the S&P store (not used):', clash)
    return daily, P, aliases, bad


def sector_table(aliases):
    s = bt.build_sector_table(aliases)
    n = pd.read_csv(os.path.join(D, 'ndx_sectors.csv'))
    n = n[~n.ticker.isin(s.ticker)][['ticker', 'sector', 'source', 'industry']]
    return pd.concat([s, n], ignore_index=True)


def setup(first_formation, last_formation):
    """Everything a strategy needs, for S&P ∪ NDX. Returns dict."""
    daily, P, aliases, bad = load_union()
    form = P.index[(P.index >= pd.Timestamp(first_formation)) & (P.index <= pd.Timestamp(last_formation))]
    sp_raw, _ = bt.load_membership(form)
    nd = ndx_members(form)
    clean = lambda mem, t: {x for x in mem if not any(a <= t <= b for a, b in bad.get(x, []))}
    members_sp = {t: clean(m, t) for t, m in sp_raw.items()}
    members_nd = {t: clean(nd.get(t, set()), t) for t in form}
    members = {t: members_sp.get(t, set()) | members_nd.get(t, set()) for t in form}
    sec_df = sector_table(aliases)
    secP, secFlag = bt.build_panel(sec_df, form)
    return dict(daily=daily, P=P, aliases=aliases, bad=bad, form=form, members=members, members_sp=members_sp,
                members_nd=members_nd, secP=secP, secFlag=secFlag, sec_df=sec_df)
