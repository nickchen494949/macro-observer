#!/usr/bin/env python3
"""
identity_check.py — does the price series we hold for an S&P 500 membership spell belong to THAT company?

The price-integrity rules (series must exist before the spell starts, gap splitting, aliases) cannot tell two
listed companies apart. Two independent checks:

1. MARKET-CAP PLAUSIBILITY (catches tiny companies that later took a big company's ticker: EP → Empire
   Petroleum, CPWR → TetriDyn/Ocean Thermal). For every quarter of a spell:
       cap = shares outstanding (SEC, first reported, CIK matched to the ticker) × UNADJUSTED close at that date
   (Yahoo/Tiingo `close` is split-adjusted to today → multiplied back by the splits that came later).
   An S&P 500 member below US$ 300 m for the median quarter of its spell is implausible → spell flagged.
   If no SEC shares exist (pre-XBRL / unmatched) the check is skipped and reported as such.

2. CROSS-SOURCE AGREEMENT (catches an acquirer taking over the target's ticker, where Yahoo silently relabels
   the target's history: JCI before 2016-09 = Tyco, DD before 2017-09 = Dow). Monthly returns of the series used
   are compared with WIKI (independent source frozen 2018-03) over the spell; correlation < 0.9 or more than
   2 months differing by > 5 % → flagged for resolution.

Output: data/identity_flags.csv (ticker, spell, check, metric, detail). Flags are resolved in
data/identity_resolutions.csv (action = exclude_until / use_source_until, with evidence) and applied by backtest.py.
"""
import glob, json, os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data')


def load_json_close(path):
    d = json.load(open(path))
    s_close = pd.Series(d.get('close'), index=pd.to_datetime(d['dates']), dtype=float)
    s_adj = pd.Series(d['adjclose'], index=pd.to_datetime(d['dates']), dtype=float)
    splits = [(pd.Timestamp(a), (n or 1) / (dd or 1)) for a, n, dd in d.get('splits', [])]
    return s_close[~s_close.index.duplicated()], s_adj[~s_adj.index.duplicated()], splits, d.get('source', 'yahoo')


def unadjusted(close, splits, source):
    """Yahoo `close` is split-adjusted to today; Tiingo/WIKI `close` is the raw historical print."""
    if source in ('tiingo', 'wiki'):
        return close
    f = pd.Series(1.0, index=close.index)
    for d, r in splits:
        f[f.index < d] *= r
    return close * f


def main():
    import backtest as bt
    daily, P, aliases, bad = bt.load_prices()
    src = bt.PRICE_SOURCE
    sp = pd.read_csv(os.path.join(D, 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    sp['ticker'] = sp.ticker.str.replace('.', '-', regex=False)
    sp = sp[sp.end_date.isna() | (sp.end_date >= '2008-12-01')]
    cm = pd.read_csv(os.path.join(D, 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    t2c = {t.replace('.', '-'): int(c) for t, c in zip(cm.ticker, cm.cik)}
    # shares: weighted-average DILUTED shares of each fiscal quarter (first reported) — the most consistently tagged
    # share count in XBRL (cover-page counts are often missing or in odd units)
    eps = pd.read_parquet(os.path.join(D, 'fundamentals', 'eps_quarterly_pit.parquet'),
                          columns=['cik', 'period_end', 'diluted_shares'])
    eps = eps.dropna(subset=['diluted_shares'])
    eps = eps[eps.diluted_shares > 1e5]
    shares = {int(c): g.set_index('period_end').diluted_shares.sort_index() for c, g in eps.groupby('cik')}
    # fallback: cover-page shares outstanding (dei) for filers without a diluted-share series
    longs = pd.concat([pd.read_parquet(p, columns=['cik', 'tag', 'ddate', 'value', 'is_first_report'])
                       for p in glob.glob(os.path.join(D, 'fundamentals', 'pit_long', '*.parquet'))])
    dei = longs[(longs.tag == 'EntityCommonStockSharesOutstanding') & longs.is_first_report & (longs.value > 1e6)]
    for c, g in dei.groupby('cik'):
        if int(c) not in shares:
            shares[int(c)] = g.drop_duplicates('ddate').set_index('ddate').value.sort_index()

    # raw files per symbol, in the same precedence the backtest used
    def raw_path(sym):
        s = src.get(sym, 'yahoo')
        base = s.split(':')[1] if s.startswith('alias:') else sym
        kind = s.split(':')[-1] if s.startswith('alias:') else s.split('<')[0].split('|')[0]
        for k, d_ in [('tiingo', 'raw_tiingo'), ('wiki', 'raw_wiki'), ('yahoo', 'raw')]:
            if kind.startswith(k):
                p = os.path.join(D, d_, f'{base}.json')
                if os.path.exists(p):
                    return p
        p = os.path.join(D, 'raw', f'{base}.json')
        return p if os.path.exists(p) else None

    flags = []
    for r in sp.itertuples():
        sym = r.ticker
        if sym not in daily.columns or not daily[sym].notna().any():
            continue
        a = max(r.start_date, pd.Timestamp('2008-12-31'))
        b = r.end_date if pd.notna(r.end_date) else pd.Timestamp('2026-09-30')
        spell = f'{r.start_date.date()}..{b.date()}'
        # ── 1. market cap ──
        cik = t2c.get(sym)
        p = raw_path(sym)
        if cik in shares and p:
            close, adj, splits, source = load_json_close(p)
            if close.notna().any():
                raw = unadjusted(close, splits, source)
                s_ = shares[cik]
                q = pd.date_range(a, b, freq='QE')
                caps = []
                for d in q:
                    px = raw.loc[:d].dropna()
                    sv = s_.loc[:d]
                    if len(px) and len(sv) and (d - px.index[-1]).days < 10 and (d - sv.index[-1]).days < 200:
                        caps.append(px.iloc[-1] * sv.iloc[-1])
                if len(caps) >= 4:
                    med = float(np.median(caps))
                    if med < 3e8:
                        flags.append({'ticker': sym, 'spell': spell, 'check': 'market_cap', 'metric': round(med / 1e6, 1),
                                      'detail': f'median cap ${med/1e6:,.0f}m over {len(caps)} quarters '
                                                f'(source {src.get(sym)}, CIK {cik}) — implausible for an S&P 500 member'})
        # ── 2. cross-source ──
        wp = os.path.join(D, 'raw_wiki_check', f'{sym}.json')
        if not os.path.exists(wp):
            wp = os.path.join(D, 'raw_wiki', f'{sym}.json')
        if os.path.exists(wp) and 'wiki' not in str(src.get(sym)):
            w = json.load(open(wp))
            ws = pd.Series(w['adjclose'], index=pd.to_datetime(w['dates'])).sort_index()
            ws = ws[~ws.index.duplicated()]
            rw = ws.resample('ME').last().pct_change(fill_method=None)
            ru = daily[sym].resample('ME').last().pct_change(fill_method=None)
            x = pd.concat([ru, rw], axis=1).dropna().loc[a:min(b, pd.Timestamp('2018-02-28'))]
            if len(x) >= 12:
                c = x.corr().iloc[0, 1]
                n5 = int(((x.iloc[:, 0] - x.iloc[:, 1]).abs() > 0.05).sum())
                if c < 0.9 or n5 > 2:
                    flags.append({'ticker': sym, 'spell': spell, 'check': 'cross_source_vs_wiki', 'metric': round(c, 3),
                                  'detail': f'{len(x)} months, corr {c:.3f}, {n5} months |diff|>5% '
                                            f'(used: {src.get(sym)}; first diff month '
                                            f'{x[(x.iloc[:,0]-x.iloc[:,1]).abs()>0.05].index.min()})'})
    out = pd.DataFrame(flags)
    out.to_csv(os.path.join(D, 'identity_flags.csv'), index=False)
    print(len(out), 'flags')
    print(out.to_string(index=False) if len(out) else '')


if __name__ == '__main__':
    main()
