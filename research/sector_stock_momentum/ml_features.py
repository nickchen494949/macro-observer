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
    pos = d.index.searchsorted(form, side='right') - 1           # last session ≤ month-end
    take = lambda x: x.iloc[pos].set_axis(form)
    px = take(d)
    feats = {
        'dist_sma200': take(d / sma200 - 1), 'dist_sma50': take(d / sma50 - 1),
        'dist_52wh': take((d / hi252 - 1).where(ok252)), 'vol_3m': take(vol63), 'vol_12m': take(vol252.where(ok252)),
        'beta_12m': take(beta.where(ok252)), 'maxret_1m': take(maxr),
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
    p = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'))
    p = p[p.cik.notna()].copy()
    p['cik'] = p.cik.astype('int64')
    p = p.sort_values(['cik', 'period_end'])
    p['margin'] = p.net_income_ttm / p.revenue_ttm.where(p.revenue_ttm > 0)
    # year-ago values (same fiscal quarter)
    prior = p[['cik', 'period_end', 'eps_diluted_approx_ttm_adj', 'margin', 'revenue_ttm', 'eps_diluted_approx_adj']].copy()
    prior['period_end'] = prior.period_end + pd.Timedelta(days=365)
    prior.columns = ['cik', 'period_end', 'ttm_prior', 'margin_prior', 'rev_prior', 'q_prior']
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
    # availability: TTM-based features need all 4 quarters public; quarterly ones need this quarter's EPS
    p['avail_ttm'] = p.eps_diluted_approx_ttm_available_date
    p['avail_rev'] = p.revenue_ttm_available_date if 'revenue_ttm_available_date' in p else p.avail_ttm
    p['avail_q'] = p.available_date
    # shares: (1) gated by THEIR OWN first-public date (filed_diluted_shares), not the EPS row's date (external audit
    # 2026-10-28: e.g. WDC 2020-09 quarter, shares first filed 2021-11-04); (2) put on the SAME split basis as the
    # adjusted prices: × every split after the shares' filing date (NVDA 2020-12: 630m × 40 → size proxy 329 bn, not 8 bn)
    from fundamentals_pit import split_factor_after
    p['avail_sh'] = p.filed_diluted_shares + pd.Timedelta(days=1)
    fac = [split_factor_after(t, f) if isinstance(t, str) and pd.notna(f) else np.nan
           for t, f in zip(p.ticker, p.filed_diluted_shares)]
    p['diluted_shares_adj'] = p.diluted_shares * np.array(fac, dtype=float)
    p['sh_period_end'] = p.period_end
    grid = pd.DataFrame([(c, t) for c in p.cik.unique() for t in form], columns=['cik', 't']).sort_values('t')
    out = grid.copy()
    blocks = {'avail_ttm': ['eps_diluted_approx_ttm_adj', 'eps_g', 'eps_g_m5', 'eps_g_sym', 'deps', 'margin', 'margin_chg'],
              'avail_rev': ['rev_g'], 'avail_q': ['sue', 'period_end'], 'avail_sh': ['diluted_shares_adj', 'sh_period_end']}
    for av, cols in blocks.items():
        # ties in the availability date (several fiscal quarters first public on the same day, e.g. a 10-K/A or a
        # catch-up filing): the LATEST fiscal period must win → stable sort by (availability, period_end)
        x = p.dropna(subset=[av]).sort_values([av, 'period_end'], kind='mergesort')[['cik', av] + cols]
        x = x.loc[:, ~x.columns.duplicated()]
        m = pd.merge_asof(grid, x, left_on='t', right_on=av, by='cik', direction='backward')
        if 'period_end' in cols:
            m['days_since_filing'] = (m.t - m[av]).dt.days
            m['q_age'] = (m.t - m.period_end).dt.days
        m = m.drop(columns=[av])
        out = out.merge(m, on=['cik', 't'], how='left')
    # stale fundamentals (fiscal quarter ended > 200 days before t) are not used
    stale = out.q_age > 200
    for c in [c for c in out.columns if c not in ('cik', 't', 'q_age', 'period_end', 'diluted_shares_adj', 'sh_period_end')]:
        out.loc[stale, c] = np.nan
    out.loc[(out.t - out.sh_period_end).dt.days > 200, 'diluted_shares_adj'] = np.nan     # shares: own staleness
    return out.drop(columns=['period_end', 'sh_period_end'])


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
    X['fwd_rank'] = X.groupby('t').fwd_ret.rank(pct=True)
    X.to_parquet(os.path.join(OUT, 'panel.parquet'), index=False)
    cov = X.drop(columns=['t', 'ticker', 'sector', 'fwd_ret', 'exit_status', 'fwd_rank']).notna().groupby(X.t.dt.year).mean()
    cov.round(2).to_csv(os.path.join(OUT, 'feature_coverage_by_year.csv'))
    print(X.shape, X.t.min().date(), X.t.max().date())
    print(cov.round(2).T.to_string())


if __name__ == '__main__':
    build()
