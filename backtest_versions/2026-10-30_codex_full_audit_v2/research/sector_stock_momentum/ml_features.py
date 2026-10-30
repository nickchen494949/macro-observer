#!/usr/bin/env python3
"""
ml_features.py — monthly point-in-time feature panel for ML stock picking (S&P 500, long-only).

One row per (formation month-end t, eligible ticker). Universe and returns come from the audited backtest
infrastructure (backtest.py): PIT membership, identity-checked prices, fresh month-end quote, sector as of t,
terminal events (resolutions / delisting / cash). Every feature uses information public at t.

Price features (daily adjusted closes, never bridging a price-segment gap):
  mom_12_1, mom_6_1, mom_3_1, rev_1m (last month), mom_12_1_secrel (minus sector mean),
  dist_sma200, above_sma200, dist_sma50, dist_52wh, vol_3m, vol_12m, beta_12m, maxret_1m, sector_mom
Fundamental features (SEC PIT store; each field gated by ITS OWN availability date):
  eps_g        TTM EPS YoY growth (prior TTM > 0)
  eps_g_m5     same, only if base-period net margin >= 5 %
  eps_g_sym    symmetric growth (bounded)
  deps_p       (TTM EPS − TTM EPS 1y ago) / price      [both on today's split basis]
  ep           TTM EPS / price (earnings yield)
  sue          (quarterly EPS − same quarter 1y ago) / std of the last 8 such differences
  margin       TTM net margin; margin_chg (YoY change)
  rev_g        TTM revenue YoY growth
  log_mcap     log(diluted shares × split factor after the shares' filing date × adjusted price) — a size PROXY
               (weighted-average diluted shares, dividend-adjusted price), gated by the shares' own filing date
  days_since_filing
Label: fwd_ret = holding-period return t → t+1 (same exit handling as the backtest); fwd_rank = cross-sectional
percentile of fwd_ret within month t.
"""
import os

import numpy as np
import pandas as pd

import backtest as bt
from fundamentals_pit import cik_valid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'ml')
os.makedirs(OUT, exist_ok=True)


def latest_fiscal_updates(x, available):
    """A late old-quarter filing must not replace a newer known fiscal quarter."""
    x = x.sort_values([available, 'period_end'], kind='mergesort')
    latest = x.groupby('cik').period_end.cummax()
    return x[x.period_end >= latest]


def price_features(daily, P, form):
    d = daily
    seg = bt.SEG_D.reindex(index=d.index, columns=d.columns) if bt.SEG_D is not None else None
    r = d.pct_change(fill_method=None)
    if seg is not None:
        r = r.where(seg == seg.shift(1))           # no return across a segment boundary
    sma200 = d.rolling(200, min_periods=180).mean()
    sma50 = d.rolling(50, min_periods=45).mean()
    hi252 = d.rolling(252, min_periods=200).max()
    vol63 = r.rolling(63, min_periods=50).std() * np.sqrt(252)
    vol252 = r.rolling(252, min_periods=200).std() * np.sqrt(252)
    spy = r['SPY']
    cov = r.rolling(252, min_periods=200).cov(spy)
    beta = cov.div(spy.rolling(252, min_periods=200).var(), axis=0)
    maxr = r.rolling(21, min_periods=15).max()
    # segment guard for the 252-day windows: same segment now and 252 sessions ago
    ok252 = (seg == seg.shift(252)) if seg is not None else True
    ok200 = (seg == seg.shift(199)) if seg is not None else True
    ok50 = (seg == seg.shift(49)) if seg is not None else True
    ok63 = (seg == seg.shift(63)) if seg is not None else True
    ok21 = (seg == seg.shift(21)) if seg is not None else True
    pos = d.index.searchsorted(form, side='right') - 1           # last session ≤ month-end
    if (pos < 0).any():
        raise ValueError('formation precedes the first price session')
    take = lambda x: x.iloc[pos].set_axis(form)
    px = take(d)
    feats = {
        'dist_sma200': take((d / sma200 - 1).where(ok200)), 'dist_sma50': take((d / sma50 - 1).where(ok50)),
        'dist_52wh': take((d / hi252 - 1).where(ok252)), 'vol_3m': take(vol63.where(ok63)), 'vol_12m': take(vol252.where(ok252)),
        'beta_12m': take(beta.where(ok252)), 'maxret_1m': take(maxr.where(ok21)),
    }
    feats['above_sma200'] = (feats['dist_sma200'] > 0).astype(float).where(feats['dist_sma200'].notna())
    for look, name in [(12, 'mom_12_1'), (6, 'mom_6_1'), (3, 'mom_3_1')]:
        feats[name] = bt.momentum(P, look).reindex(form)
    rev = P / P.shift(1) - 1
    if bt.SEG_M is not None:
        sg = bt.SEG_M.reindex(index=P.index, columns=P.columns)
        rev = rev.where(sg == sg.shift(1))
    feats['rev_1m'] = rev.reindex(form)
    return feats, px


def fundamental_panel(form):
    """Point-in-time fundamental features. EVERY feature has its own availability date = the latest first-public date
    of ALL its inputs (incl. the year-ago values it is compared with), and its own staleness (its fiscal quarter must
    have ended <= 200 days before t). (External audit 2026-10-29: margin used net-income / revenue TTM gated by the EPS
    date — AMD 2017-06-30 used a margin first public on 2018-02-28.)"""
    p = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'))
    p = p[p.cik.notna()].copy()
    p['cik'] = p.cik.astype('int64')
    p = p.sort_values(['cik', 'period_end'])
    one = pd.Timedelta(days=1)
    p['av_eps'] = p.eps_diluted_approx_ttm_available_date
    p['av_ni'] = p.net_income_ttm_available_date
    p['av_rev'] = p.revenue_ttm_available_date
    p['av_q'] = p.available_date
    p['margin'] = p.net_income_ttm / p.revenue_ttm.where(p.revenue_ttm > 0)
    # year-ago values (same fiscal quarter) WITH their availability dates
    pc = ['eps_diluted_approx_ttm_adj', 'margin', 'revenue_ttm', 'eps_diluted_approx_adj', 'av_eps', 'av_ni', 'av_rev', 'av_q']
    prior = p[['cik', 'period_end'] + pc].copy()
    prior['period_end'] = prior.period_end + pd.Timedelta(days=365)
    prior.columns = ['cik', 'period_end', 'ttm_prior', 'margin_prior', 'rev_prior', 'q_prior', 'av_eps_py', 'av_ni_py',
                     'av_rev_py', 'av_q_py']
    p = pd.merge_asof(p.sort_values('period_end'), prior.sort_values('period_end'), on='period_end', by='cik',
                      tolerance=pd.Timedelta(days=20), direction='nearest').sort_values(['cik', 'period_end'])
    t_, t0 = p.eps_diluted_approx_ttm_adj, p.ttm_prior
    p['eps_g'] = np.where(t0 > 0, t_ / t0 - 1, np.nan)
    p['eps_g_m5'] = np.where((t0 > 0) & (p.margin_prior >= 0.05), t_ / t0 - 1, np.nan)
    den = (t_.abs() + t0.abs()) / 2
    p['eps_g_sym'] = np.where(den > 0, (t_ - t0) / den, np.nan)
    p['deps'] = t_ - t0
    p['margin_chg'] = p.margin - p.margin_prior
    p['rev_g'] = np.where(p.rev_prior > 0, p.revenue_ttm / p.rev_prior - 1, np.nan)
    # SUE on quarterly EPS (common split basis)
    p['dq'] = p.eps_diluted_approx_adj - p.q_prior
    p['dq_std'] = p.groupby('cik').dq.transform(lambda s: s.shift(1).rolling(8, min_periods=4).std())
    p['sue'] = p.dq / p.dq_std.where(p.dq_std > 0)
    mx = lambda *c: pd.concat([p[x] for x in c], axis=1).max(axis=1, skipna=False)
    p['av_dq'] = mx('av_q', 'av_q_py')
    # the SUE denominator uses the previous 8 quarterly differences: public once the latest of them is public
    p['_dqns'] = p.av_dq.astype('int64').where(p.av_dq.notna()).astype(float)
    p['_dqns'] = p._dqns.where(p.dq.notna())
    p['av_dqstd'] = pd.to_datetime(p.groupby('cik')._dqns.transform(lambda s: s.shift(1).rolling(8, min_periods=4).max()))
    from fundamentals_pit import split_factor_after
    p['av_sh'] = p.filed_diluted_shares + one
    fac = [split_factor_after(t, f) if isinstance(t, str) and pd.notna(f) else np.nan
           for t, f in zip(p.ticker, p.filed_diluted_shares)]
    # shares: own filing date; same split basis as adjusted prices (external audit 2026-10-28: NVDA, WDC)
    p['diluted_shares_adj'] = p.diluted_shares * np.array(fac, dtype=float)
    avail = {
        'eps_diluted_approx_ttm_adj': mx('av_eps'),
        'eps_g': mx('av_eps', 'av_eps_py'), 'eps_g_sym': mx('av_eps', 'av_eps_py'), 'deps': mx('av_eps', 'av_eps_py'),
        'eps_g_m5': mx('av_eps', 'av_eps_py', 'av_ni_py', 'av_rev_py'),
        'margin': mx('av_ni', 'av_rev'), 'margin_chg': mx('av_ni', 'av_rev', 'av_ni_py', 'av_rev_py'),
        'rev_g': mx('av_rev', 'av_rev_py'),
        'days_since_filing': mx('av_q'),
        'diluted_shares_adj': mx('av_sh'),
    }
    grid = pd.DataFrame([(c, t) for c in p.cik.unique() for t in form], columns=['cik', 't']).sort_values('t')
    out = grid.copy()
    for f, av in avail.items():
        x = pd.DataFrame({'cik': p.cik.values, '_av': av.values, 'period_end': p.period_end.values,
                          f: (p[f].values if f != 'days_since_filing' else av.values)}).dropna(subset=['_av'])
        # A known new quarter with an undefined factor (e.g. prior EPS <= 0)
        # invalidates that factor; it must not revive an older positive growth.
        # ties in availability (several quarters first public the same day): the LATEST fiscal period wins
        x = latest_fiscal_updates(x, '_av')
        m = pd.merge_asof(grid, x, left_on='t', right_on='_av', by='cik', direction='backward')
        v = m[f] if f != 'days_since_filing' else (m.t - m['_av']).dt.days
        v = v.where((m.t - m.period_end).dt.days <= 200)              # each feature's own staleness
        out[f] = v.values
    out['sue'] = sue_asof(p, grid).values
    return out


def sue_asof(p, grid):
    """SUE computed AS OF each formation date from the quarters known then: latest known quarterly EPS change vs the
    same quarter a year earlier (dq, public when both quarters are), divided by the std of the previous <= 8 KNOWN dq
    values (at least 4). Truncation-invariant by construction (a quarter filed late cannot enter an earlier window)."""
    res = {}
    t_arr = np.array(sorted(grid.t.unique()), dtype='datetime64[ns]')
    for c, g in p[['cik', 'period_end', 'dq', 'av_dq']].dropna().groupby('cik'):
        g = g.sort_values('period_end')
        pe, dq, av = g.period_end.values, g.dq.values, g.av_dq.values
        for t in t_arr:
            k = av <= t
            if k.sum() < 5:
                continue
            pk, dk = pe[k], dq[k]
            i = len(pk) - 1                                   # latest known fiscal quarter
            if (t - pk[i]).astype('timedelta64[D]').astype(int) > 200:
                continue
            prev = dk[max(0, i - 8):i]
            if len(prev) < 4:
                continue
            sd = np.std(prev, ddof=1)
            if sd > 0:
                res[(c, t)] = dk[i] / sd
    idx = list(zip(grid.cik.values, grid.t.values.astype('datetime64[ns]')))
    return pd.Series([res.get(k, np.nan) for k in idx], index=grid.index)


def build():
    daily, P, aliases, bad = bt.load_prices()
    form = P.index[(P.index >= pd.Timestamp('2009-12-31')) & (P.index <= pd.Timestamp(bt.END) - pd.offsets.MonthEnd(1))]
    members_raw, _ = bt.load_membership(form)
    members = {t: {x for x in m if not any(a <= t <= b for a, b in bad.get(x, []))} for t, m in members_raw.items()}
    sec_df = bt.build_sector_table(aliases)
    secP, _ = bt.build_panel(sec_df, form)
    eng = bt.Engine(P, daily, members, secP, form)
    px_ = bt.Prices(daily, P, 0)
    res = bt.load_resolutions()
    pf, px = price_features(daily, P, form)
    F = fundamental_panel(form)
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    t2c = {t.replace('.', '-'): int(c) for t, c in zip(cm.ticker, cm.cik)}
    Fi = F.set_index(['t', 'cik'])
    rows = []
    for t in form:
        df, mom = eng.eligible(t, 12)
        if df.empty:
            continue
        sec_mean = df.groupby('sector').mom.transform('mean')
        for s in df.index:
            rec = {'t': t, 'ticker': s, 'sector': df.at[s, 'sector'], 'sector_mom': sec_mean[s],
                   'mom_12_1_secrel': df.at[s, 'mom'] - sec_mean[s]}
            for k, v in pf.items():
                rec[k] = v.at[t, s] if s in v.columns else np.nan
            c = t2c.get(s)
            if c is not None and not cik_valid(s, t):
                c = None                        # ticker's prices and mapped CIK are different companies at t
            if c is not None and (t, c) in Fi.index:
                f = Fi.loc[(t, c)]
                price = px.at[t, s]
                rec.update({k: f[k] for k in ['eps_g', 'eps_g_m5', 'eps_g_sym', 'margin', 'margin_chg', 'rev_g', 'sue',
                                              'days_since_filing']})
                rec['deps_p'] = f['deps'] / price if price and price > 0 else np.nan
                rec['ep'] = f['eps_diluted_approx_ttm_adj'] / price if price and price > 0 else np.nan
                sh = f['diluted_shares_adj']
                rec['log_mcap'] = np.log(sh * price) if np.isfinite(sh) and sh > 0 and price and price > 0 else np.nan
            r, st = px_.ret(t, s, res)
            rec['fwd_ret'], rec['exit_status'] = r, st
            rows.append(rec)
    X = pd.DataFrame(rows)
    # Unknown vendor/terminal outcomes are not known training labels. Preserve
    # the row and its baseline outcome for portfolio stress/provenance reporting.
    X['label_resolved'] = ~X.exit_status.isin(['source_gap', 'unresolved'])
    X['fwd_rank'] = X.fwd_ret.where(X.label_resolved).groupby(X.t).rank(pct=True)
    X.to_parquet(os.path.join(OUT, 'panel.parquet'), index=False)
    cov = X.drop(columns=['t', 'ticker', 'sector', 'fwd_ret', 'exit_status', 'fwd_rank']).notna().groupby(X.t.dt.year).mean()
    cov.round(2).to_csv(os.path.join(OUT, 'feature_coverage_by_year.csv'))
    print(X.shape, X.t.min().date(), X.t.max().date())
    print(cov.round(2).T.to_string())


if __name__ == '__main__':
    build()
