#!/usr/bin/env python3
"""
smallcap_universe.py — AVAILABLE liquid non-S&P universe (not complete small/mid-cap history) (WINNERS_SPEC.md §5 / §5a).

Prices (adjusted close for returns, raw close × volume for dollar volume):
  1. S&P store (backtest.load_prices; identity-audited) for every ticker that was EVER an S&P 500 member — used in the
     months it is NOT a member (e.g. before joining). Volume: data/raw_volume (Yahoo) or WIKI.
  2. Yahoo current listings (data/raw_smallcap, fetch_smallcap.py).
  3. WIKI bulk (data/wiki_bulk/wiki_prices.parquet; includes delisted stocks; ends 2018-03-27).
  Same ticker in Yahoo and WIKI with overlapping dates: same company only if daily-return correlation on the overlap
  >= 0.9; otherwise WIKI is used up to its end, Yahoo from its own start, with a segment break.
Codex audit: current-listing collection plus WIKI history is survivorship-incomplete.
There is no historical market-cap bound; do not report this as a complete small/mid-cap universe.
Universe at month-end t: close >= 5 USD, median 63-session dollar volume >= 5 m USD, not an S&P 500 member at t,
full 12-1 momentum window inside one price segment.
Holding returns: backtest.Prices with this universe's daily / monthly prices and segments (fresh month-end quote rule,
exit at the last trade then cash; WIKI-only series ending at the 2018-03-27 freeze = source_gap, not a delisting).

  python3 smallcap_universe.py build     → data/smallcap/{daily_adj,daily_dv,seg}.parquet, coverage report (NO returns)
"""
import json, os, sys

import numpy as np
import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data', 'smallcap')
os.makedirs(D, exist_ok=True)
WIKI_END = pd.Timestamp('2018-03-27')


def _series(dates, vals):
    s = pd.Series(vals, index=pd.to_datetime(dates), dtype=float)
    return s[~s.index.duplicated(keep='last')].sort_index()


def raw_close_from_yahoo(j):
    """Yahoo 'close' is split-adjusted → multiply by every split AFTER the date to get the price that actually traded
    (needed for the 5-USD rule: otherwise later big splitters look like penny stocks in the past)."""
    c = _series(j['dates'], j['close'])
    f = pd.Series(1.0, index=c.index)
    for d, n, dd in j.get('splits') or []:
        r = (n or 1) / (dd or 1)
        f[f.index < pd.Timestamp(d)] *= r
    return c * f


def build():
    # 1) S&P store
    daily_sp, P_sp, aliases, bad = bt.load_prices()
    sp_ever = set(pd.read_csv(os.path.join(HERE, 'data', 'sp500_ticker_start_end.csv')).ticker.str.replace('.', '-', regex=False))
    adj, dv, src, cl = {}, {}, {}, {}
    vol_dir = os.path.join(HERE, 'data', 'raw_volume')
    for s in daily_sp.columns:
        if s not in sp_ever or s in bt.NON_STOCK:
            continue
        a = daily_sp[s].dropna()
        if a.empty:
            continue
        adj[s] = a
        src[s] = 'sp_store'
        vp = os.path.join(vol_dir, f'{s}.json')
        rp = os.path.join(HERE, 'data', 'raw', f'{s}.json')
        if os.path.exists(rp) and bt.PRICE_SOURCE.get(s) == 'yahoo':
            r = json.load(open(rp))
            cl[s] = raw_close_from_yahoo(r)
            if os.path.exists(vp):
                v = json.load(open(vp))
                dv[s] = (_series(r['dates'], r['close']) * _series(v['dates'], v['volume'])).dropna()
        else:
            tp = os.path.join(HERE, 'data', 'raw_tiingo', f'{s}.json')
            if os.path.exists(tp) and str(bt.PRICE_SOURCE.get(s)).startswith('tiingo'):
                r = json.load(open(tp))
                cl[s] = _series(r['dates'], r['close'])                   # Tiingo close is unadjusted
    # 2) Yahoo small/mid
    ydir = os.path.join(HERE, 'data', 'raw_smallcap')
    yahoo = {}
    for f in sorted(os.listdir(ydir)) if os.path.isdir(ydir) else []:
        if f.endswith('.json') and not f.startswith('_'):
            j = json.load(open(os.path.join(ydir, f)))
            yahoo[j['symbol']] = j
    # 3) WIKI bulk
    W = pd.read_parquet(os.path.join(HERE, 'data', 'wiki_bulk', 'wiki_prices.parquet'))
    W['dv'] = W.close * W.volume
    wiki = {t: g.set_index('date').sort_index() for t, g in W.groupby('ticker')}
    idlog = []
    for s, j in yahoo.items():
        a = _series(j['dates'], j['adjclose'])
        d_ = (_series(j['dates'], j['close']) * _series(j['dates'], [v if v is not None else np.nan for v in j['volume']])).dropna()
        if s in wiki and s not in adj:
            w = wiki[s]
            ov = a.index.intersection(w.index)
            if len(ov) >= 60:
                c = a.loc[ov].pct_change().corr(w.adj_close.loc[ov].pct_change())
            else:
                c = np.nan
            if len(ov) >= 60 and c >= 0.9:
                idlog.append((s, 'same company (overlap corr %.3f)' % c))
                adj[s], dv[s], src[s] = a, d_, 'yahoo'                     # Yahoo carries the full history
                cl[s] = raw_close_from_yahoo(j)
            else:
                # different companies (or no usable overlap): WIKI up to its end, Yahoo from its own start + 30 d gap
                w_end = w.index.max()
                y_part = a[a.index > w_end + pd.Timedelta(days=31)]
                idlog.append((s, f'split: WIKI to {w_end.date()} | Yahoo from {y_part.index.min().date() if len(y_part) else None} (corr {c})'))
                adj[s] = pd.concat([w.adj_close, y_part])
                yc = raw_close_from_yahoo(j)
                cl[s] = pd.concat([w.close, yc[yc.index > w_end + pd.Timedelta(days=31)]])
                dv[s] = pd.concat([w.dv, d_[d_.index > w_end + pd.Timedelta(days=31)]])
                src[s] = 'wiki|yahoo'
            continue
        if s not in adj:
            adj[s], dv[s], src[s] = a, d_, 'yahoo'
            cl[s] = raw_close_from_yahoo(j)
    for s, w in wiki.items():
        if s in adj:
            if s not in dv or dv[s].empty:
                dv[s] = w.dv.dropna()                                     # S&P-store names without Yahoo volume
            if s not in cl:
                cl[s] = w.close.dropna()
            continue
        adj[s], dv[s], src[s] = w.adj_close.dropna(), w.dv.dropna(), 'wiki'
        cl[s] = w.close.dropna()
    A = pd.DataFrame(adj).sort_index()
    A = A[A.index >= '2007-01-01']
    DV = pd.DataFrame(dv).reindex(index=A.index, columns=A.columns)
    CL = pd.DataFrame(cl).reindex(index=A.index, columns=A.columns)
    CL.to_parquet(os.path.join(D, 'daily_close_raw.parquet'))
    A.to_parquet(os.path.join(D, 'daily_adj.parquet'))
    DV.to_parquet(os.path.join(D, 'daily_dv.parquet'))
    pd.Series(src).to_csv(os.path.join(D, 'price_source.csv'), header=['source'])
    pd.DataFrame(idlog, columns=['ticker', 'identity_decision']).to_csv(os.path.join(D, 'identity_wiki_vs_yahoo.csv'), index=False)
    print('securities', A.shape[1], '| sources', pd.Series(src).value_counts().to_dict(), '| identity decisions', len(idlog))


def universe(A, DV, members_sp, form, close_raw=None):
    """dict t -> list of eligible tickers (price >= 5 by dollar-volume/adj proxy, liquidity, not S&P member)."""
    med_dv = DV.rolling(63, min_periods=40).median()
    pos = A.index.searchsorted(form, side='right') - 1
    out = {}
    for t, p in zip(form, pos):
        d = A.index[p]
        px = close_raw.loc[d] if close_raw is not None else A.loc[d]
        ok = (px >= 5) & (med_dv.loc[d] >= 5e6)
        names = set(ok[ok].index) - members_sp.get(t, set())
        out[t] = sorted(names)
    return out


def coverage():
    """Diagnostics only (no returns): universe size per month."""
    A = pd.read_parquet(os.path.join(D, 'daily_adj.parquet'))
    DV = pd.read_parquet(os.path.join(D, 'daily_dv.parquet'))
    form = pd.date_range('2009-12-31', '2026-08-31', freq='ME')
    raw, _ = bt.load_membership(form)
    CL = pd.read_parquet(os.path.join(D, 'daily_close_raw.parquet'))
    U = universe(A, DV, raw, form, CL.ffill(limit=5))
    print('raw-close coverage of securities:', round(CL.notna().any().mean(), 3))
    n = pd.Series({t: len(v) for t, v in U.items()})
    print('universe size: min', n.min(), 'median', int(n.median()), 'max', n.max())
    print(n.resample('YE').median().astype(int).to_dict())
    n.to_csv(os.path.join(D, 'universe_size.csv'), header=['n'])


if __name__ == '__main__':
    {'build': build, 'coverage': coverage}[sys.argv[1]]()
