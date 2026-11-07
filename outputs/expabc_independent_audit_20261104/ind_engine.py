#!/usr/bin/env python3
"""
ind_engine.py — INDEPENDENT from-scratch engine for the 2-leg strategy (G1_SPY_2e).

Shares NO code with the project pipeline (no a2_engine / c2_engine / backtest.py / run_qqq_spy_g1_audit).
Inputs are raw files only:
  * Nasdaq-100 membership : research/.../data/nasdaq100_src/n100-ticker-changes-YYYY.yaml (raw change logs)
  * S&P 500 membership    : research/.../data/sp500_hist_components.csv (raw daily snapshots, fja05680)
  * Prices                : raw vendor JSON (Yahoo raw_open / raw, Tiingo JSON, archive) + Quandl WIKI bulk parquet

Strategy (frozen spec under audit):
  Leg A 50%: Nasdaq-100 members, score = mom_12_1 / vol_12_1, buy Top-2, keep a holding while rank <= 5.
  Leg B 50%: S&P 500 members,    score = mom_12_1,            buy Top-1, keep the holding while rank <= 3.
  mom_12_1 = P(last close <= ME(t-1)) / P(last close <= ME(t-12)) - 1 ; vol = std(daily ret in (ME(t-12), ME(t-1)]) * sqrt(252)
  Signal at month-end close t; trade at the adjusted OPEN of the first session after t; hold to the adjusted OPEN of
  the first session of the following month. 10 bp per side on traded notional. 1.0x, cash 0%.
"""
import functools
import glob
import json
import os

import numpy as np
import pandas as pd
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
D = os.path.join(ROOT, 'research', 'sector_stock_momentum', 'data')
TIINGO_DIRS = [os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103', 'tiingo'),
               os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103', 'tiingo'),
               os.path.join(D, 'raw_tiingo')]
FORM_START, FORM_END = pd.Timestamp('2008-12-31'), pd.Timestamp('2026-08-31')
COST = 0.0010


# ----------------------------------------------------------------------------- membership
def ndx_members():
    years = {}
    for f in sorted(glob.glob(os.path.join(D, 'nasdaq100_src', 'n100-ticker-changes-*.yaml'))):
        d = yaml.load(open(f), Loader=yaml.BaseLoader)  # BaseLoader: keep 'ON' as a string
        ch = sorted([(pd.Timestamp(str(k)), set((v or {}).get('union') or []), set((v or {}).get('difference') or []))
                     for k, v in (d.get('changes') or {}).items()], key=lambda x: x[0])
        years[int(d['year'])] = (set(d['tickers_on_Jan_1']), ch)
    out = {}
    for t in pd.date_range(FORM_START, FORM_END, freq='ME'):
        s, ch = years[t.year]
        s = set(s)
        for dt, add, rem in ch:
            if dt <= t:
                s = (s - rem) | add
        out[t] = s
    return out


def spx_members():
    C = pd.read_csv(os.path.join(D, 'sp500_hist_components.csv'), parse_dates=['date']).sort_values('date')
    out = {}
    for t in pd.date_range(FORM_START, FORM_END, freq='ME'):
        row = C[C['date'] <= t].iloc[-1]
        out[t] = set(str(row['tickers']).split(','))
    return out


# ----------------------------------------------------------------------------- prices
def _df(dates, close, opn=None):
    df = pd.DataFrame({'c': pd.to_numeric(pd.Series(close), errors='coerce').values,
                       'o': (pd.to_numeric(pd.Series(opn), errors='coerce').values if opn is not None else np.nan)},
                      index=pd.to_datetime(pd.Series(dates).astype(str).str[:10]))
    df = df[~df.index.duplicated(keep='last')].sort_index()
    df.loc[~(df['c'] > 0), 'c'] = np.nan
    df.loc[~(df['o'] > 0), 'o'] = np.nan
    df = df[df['c'].notna()]
    # drop frozen quotes (>=5 identical closes in a row keep first) — stale vendor padding after delisting
    same = df['c'].eq(df['c'].shift(1))
    run = (~same).cumsum()
    rl = same.groupby(run).transform('sum') + 1
    df = df[~(same & (rl >= 5))]
    return df if len(df) else None


@functools.lru_cache(maxsize=None)
def wiki_all():
    w = pd.read_parquet(os.path.join(D, 'wiki_bulk', 'wiki_prices.parquet'), columns=['ticker', 'date', 'adj_close'])
    o = pd.read_parquet(os.path.join(D, 'wiki_bulk', 'wiki_open.parquet'))
    w = w.merge(o, on=['ticker', 'date'], how='left')
    return {k: g for k, g in w.groupby('ticker')}


@functools.lru_cache(maxsize=None)
def load(source, sym):
    try:
        if source == 'yahoo':
            for sub in ('raw_open', 'raw'):
                p = os.path.join(D, sub, f'{sym}.json')
                if os.path.exists(p):
                    j = json.load(open(p))
                    return _df(j['dates'], j['adjclose'], j.get('adj_open'))
            return None
        if source == 'tiingo':
            for td in TIINGO_DIRS:
                p = os.path.join(td, f'{sym}.json')
                if os.path.exists(p):
                    j = json.load(open(p))
                    if 'rows' in j:
                        r = pd.DataFrame(j['rows'])
                        return _df(r['date'], r['adjClose'], r.get('adjOpen'))
                    return _df(j['dates'], j['adjclose'], None)
            return None
        if source in ('archive', 'raw_ndx'):
            p = os.path.join(D, 'raw_archive' if source == 'archive' else 'raw_ndx', f'{sym}.json')
            if os.path.exists(p):
                j = json.load(open(p))
                return _df(j['dates'], j['adjclose'], j.get('adj_open'))
            return None
        if source == 'wiki':
            g = wiki_all().get(sym)
            if g is None:
                return None
            return _df(g['date'], g['adj_close'], g['adj_open'] if 'adj_open' in g else None)
    except Exception:
        return None
    return None


SOURCES = ('yahoo', 'tiingo', 'wiki', 'archive', 'raw_ndx')

# v2: explicit, audited identity table. Each entry = SAME legal entity renamed (or vendor stores it under another symbol).
#   HANS -> MNST   Hansen Natural renamed Monster Beverage (2012-01), same SEC filer
#   FOX/FOXA       21st Century Fox; renamed TFCF/TFCFA 2019-01 before the Disney deal (delisted 2019-03-20);
#                  new Fox Corp trades as FOX/FOXA from 2019-03 (Yahoo files start 2019-03, cannot leak into old dates)
#   HFC -> DINO    HollyFrontier -> HF Sinclair (vendor history continuous)
#   NLOK -> GEN    Symantec -> NortonLifeLock -> Gen Digital, same filer
#   BLL -> BALL    Ball Corp ticker change 2022, same filer
#   LB -> BBWI     L Brands renamed Bath & Body Works 2021, same filer
#   COG -> CTRA    Cabot Oil & Gas -> Coterra 2021, same filer (wiki COG also valid pre-2018)
#   TEVA, FER      only stored in raw_ndx
ALIASES = {
    'HANS': [('yahoo', 'MNST')],
    'FOX': [('tiingo', 'TFCF'), ('wiki', 'FOX'), ('yahoo', 'FOX')],
    'FOXA': [('tiingo', 'TFCFA'), ('wiki', 'FOXA'), ('yahoo', 'FOXA')],
    'HFC': [('tiingo', 'DINO'), ('yahoo', 'DINO')],
    'NLOK': [('yahoo', 'GEN')],
    'BLL': [('yahoo', 'BALL')],
    'LB': [('yahoo', 'BBWI')],
    'COG': [('wiki', 'COG'), ('tiingo', 'CTRA')],
}
# Reused tickers where the naive vendor symbol is a DIFFERENT company for the membership dates -> do not price naively
UNSAFE_NAIVE = {'LSI'}   # Yahoo 'LSI' = Life Storage (not LSI Corp); wiki 'LSI' = LSI Corp
# Documented corporate-action fix (vendor adjustments wrong): IAC 2008-08-21 spin-offs + 1:2 reverse split.
# True package return that day = +10.31% (unadjusted closes, see qqq audit CORP_FIX evidence). Applied to every vendor copy.
CORP_FIX = {'IACI': ('2008-08-21', 19.415 / 17.60 - 1)}


def candidate_series(tk):
    out = []
    for src, sym in ALIASES.get(tk, []):
        out.append((src, sym))
    if tk in UNSAFE_NAIVE:
        out.append(('wiki', tk))
        return out
    for src in SOURCES:
        for sym in syms_for(tk):
            out.append((src, sym))
    return list(dict.fromkeys(out))


def load_fixed(src, sym):
    df = load(src, sym)
    if df is None or sym not in CORP_FIX:
        return df
    ex, true_r = pd.Timestamp(CORP_FIX[sym][0]), CORP_FIX[sym][1]
    pre, post = df['c'].loc[:ex - pd.Timedelta(days=1)], df['c'].loc[ex:]
    if len(pre) and len(post) and post.index[0] == ex:
        k = (post.iloc[0] / pre.iloc[-1]) / (1 + true_r)
        df = df.copy()
        df.loc[df.index < ex, ['c', 'o']] *= k
    return df


def syms_for(tk):
    s = [tk, tk.replace('.', '-'), tk.replace('.', '_'), tk.replace('.', '')]
    return list(dict.fromkeys(s))


@functools.lru_cache(maxsize=1)
def calendar():
    return load('yahoo', 'SPY').index


def first_session_after(dt):
    cal = calendar()
    i = cal.searchsorted(pd.Timestamp(dt), side='right')
    return cal[i] if i < len(cal) else None


def px_on_or_before(df, dt, stale=7):
    s = df['c'].loc[:dt]
    if not len(s) or (pd.Timestamp(dt) - s.index[-1]).days > stale:
        return np.nan
    return float(s.iloc[-1])


def features(df, t):
    t1, t12 = t - pd.offsets.MonthEnd(1), t - pd.offsets.MonthEnd(12)
    p0, p1, p12 = px_on_or_before(df, t), px_on_or_before(df, t1), px_on_or_before(df, t12)
    if not (np.isfinite(p0) and np.isfinite(p1) and np.isfinite(p12)):
        return None
    w = df['c'].loc[:t1]
    w = w.loc[w.index >= w.loc[:t12].index[-1]]       # from last close <= ME(t-12) through ME(t-1)
    if len(w) < 121:
        return None
    gaps = np.diff(w.index.values).astype('timedelta64[D]').astype(int)
    if gaps.max() > 30:                                 # halt / identity protection
        return None
    r = w.pct_change().dropna().values
    mom = p1 / p12 - 1.0
    vol = float(np.std(r, ddof=1) * np.sqrt(252.0))
    return mom, vol


def hold_return(df, t):
    d0 = first_session_after(t)
    d1 = first_session_after(t + pd.offsets.MonthEnd(1))
    if d0 is None or d0 not in df.index:
        return np.nan, 'no_entry'
    o0 = df.at[d0, 'o'] if np.isfinite(df.at[d0, 'o']) else np.nan
    if d1 is not None and d1 in df.index:
        o1 = df.at[d1, 'o']
        if np.isfinite(o0) and np.isfinite(o1):
            return o1 / o0 - 1.0, 'open_open'
        return df.at[d1, 'c'] / df.at[d0, 'c'] - 1.0, 'close_proxy'
    after = df['c'].loc[d0:d1] if d1 is not None else df['c'].loc[d0:]
    if len(after) and df.index.max() < (d1 or df.index.max() + pd.Timedelta(days=1)):
        base = o0 if np.isfinite(o0) else df.at[d0, 'c']
        return after.iloc[-1] / base - 1.0, 'delist_last_close'
    return np.nan, 'unpriced'


def resolve(tk, t):
    """First (source, sym) whose series yields valid features at t. Returns (src, sym, df, mom, vol) or None."""
    for src, sym in candidate_series(tk):
        df = load_fixed(src, sym)
        if df is None:
            continue
        f = features(df, t)
        if f is not None:
            return src, sym, df, f[0], f[1]
    return None


def best_hold_return(tk, t, feat_df):
    """Spec = open-to-open. Use any same-identity series that has REAL opens at entry and exit and agrees with the
    feature series on the entry-day close (<=2%: same company). Otherwise fall back to the feature series."""
    d0 = first_session_after(t)
    d1 = first_session_after(t + pd.offsets.MonthEnd(1))
    r_feat, fl_feat = hold_return(feat_df, t)
    if fl_feat == 'open_open' or d0 is None or d1 is None or d0 not in feat_df.index:
        return r_feat, fl_feat, None
    c_ref_0 = feat_df.at[d0, 'c']
    c_ref_m1 = px_on_or_before(feat_df, t - pd.offsets.MonthEnd(1), stale=7)
    for src, sym in candidate_series(tk):
        df = load_fixed(src, sym)
        if df is None or df is feat_df or d0 not in df.index or d1 not in df.index:
            continue
        if not (np.isfinite(df.at[d0, 'o']) and np.isfinite(df.at[d1, 'o'])):
            continue
        # identity check: the close-to-close move from ME(t-1) to d0 must agree within 2% (scale-free)
        c_m1 = px_on_or_before(df, t - pd.offsets.MonthEnd(1), stale=7)
        if not (np.isfinite(c_m1) and np.isfinite(c_ref_m1)):
            continue
        if abs((df.at[d0, 'c'] / c_m1) / (c_ref_0 / c_ref_m1) - 1) > 0.02:
            continue
        return df.at[d1, 'o'] / df.at[d0, 'o'] - 1.0, f'open_open_via_{src}:{sym}', (src, sym)
    return r_feat, fl_feat, None


def build_panel(members):
    rows = []
    for t, mem in sorted(members.items()):
        for tk in sorted(mem):
            r = resolve(tk, t)
            if r is None:
                rows.append((t, tk, None, None, np.nan, np.nan, np.nan, 'no_valid_series'))
                continue
            src, sym, df, mom, vol = r
            hr, fl, _ = best_hold_return(tk, t, df)
            rows.append((t, tk, src, sym, mom, vol, hr, fl))
    P = pd.DataFrame(rows, columns=['t', 'ticker', 'src', 'sym', 'mom', 'vol', 'hold_ret', 'ret_flag'])
    P['sharpe'] = P['mom'] / P['vol']
    return P


# ----------------------------------------------------------------------------- sleeve rules (signal only; uses NO future info)
def sleeve_picks(P, score, k, keep):
    """Returns {t: [picks]} using only the score at t. Ranking never looks at hold_ret."""
    held, out = [], {}
    for t, g in P[P[score].notna()].groupby('t', sort=True):
        ranked = list(g.sort_values([score, 'ticker'], ascending=[False, True])['ticker'])
        rank = {x: i + 1 for i, x in enumerate(ranked)}
        kept = [x for x in held if rank.get(x, 10 ** 9) <= keep]
        kept = sorted(kept, key=lambda x: rank[x])[:k]
        for x in ranked:
            if len(kept) >= k:
                break
            if x not in kept:
                kept.append(x)
        held = kept
        out[t] = list(kept)
    return out


def simulate(P_by_leg, picks_by_leg, leg_w, single_account=True):
    """
    Single-account simulation: target weights = sum over legs of leg_w * 1/k per pick (overlaps net).
    Turnover measured against drifted weights of the WHOLE portfolio (includes cross-leg rebalancing).
    Return per month = sum(w * r) ; cost = COST * turnover (initial buy counts 1.0).
    """
    months = sorted(set.intersection(*[set(p) for p in picks_by_leg.values()]))
    ret_lookup = {}
    for leg, P in P_by_leg.items():
        for t, tk, r in P[['t', 'ticker', 'hold_ret']].itertuples(index=False):
            ret_lookup[(leg, t, tk)] = r
    prev, rows = {}, []
    for t in months:
        w = {}
        for leg, pk in picks_by_leg.items():
            for tk in pk[t]:
                w[tk] = w.get(tk, 0.0) + leg_w[leg] / len(pk[t])
        r = {}
        for tk in w:
            vals = [ret_lookup.get((leg, t, tk)) for leg in picks_by_leg if tk in picks_by_leg[leg][t]]
            vals = [v for v in vals if v is not None and np.isfinite(v)]
            r[tk] = vals[0] if vals else np.nan
        to = sum(abs(w.get(x, 0.0) - prev.get(x, 0.0)) for x in set(w) | set(prev)) if prev else 1.0
        gross = sum(w[x] * r[x] for x in w)
        net = gross - COST * to
        denom = sum(w[x] * (1 + r[x]) for x in w)
        prev = {x: w[x] * (1 + r[x]) / denom for x in w}
        rows.append({'t': t, 'weights': w, 'rets': r, 'gross': gross, 'turnover': to, 'net': net})
    return pd.DataFrame(rows).set_index('t')
