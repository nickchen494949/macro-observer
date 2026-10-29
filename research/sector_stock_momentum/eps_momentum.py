#!/usr/bin/env python3
"""
eps_momentum.py — "top-10 EPS growth, then the highest-momentum stock among them (if momentum > 0)".

Exploratory variant requested after the sector-momentum study. Re-uses the audited infrastructure of
backtest.py (point-in-time membership, identity-checked prices, terminal events, costs, statistics).

At each month-end t (all inputs public at t):
  EPS growth  = TTM diluted EPS (common split basis, eps_diluted_approx_ttm_adj) of the latest fiscal quarter whose
                4 quarters are all public at t (quarter ended ≤ 200 days before t), divided by the TTM EPS of the
                same quarter one year earlier, minus 1. Requires prior TTM EPS > 0.
  Variant B   = (TTM EPS − TTM EPS a year earlier) / price at t      (robust to tiny positive bases)
  Pick        = top 10 by EPS growth → highest 12-1 momentum among them, only if momentum > 0; otherwise cash.
NOTE: the 2021-06 … 2026-09 period has already been looked at for other strategies (retrospective holdout), and
every additional idea tested on the same history adds data-snooping risk.
"""
import os

import numpy as np
import pandas as pd

import backtest as bt
from fundamentals_pit import cik_valid

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results', 'eps_momentum')
os.makedirs(RES, exist_ok=True)


def growth_panel(form, P):
    p = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'),
                        columns=['cik', 'period_end', 'eps_diluted_approx_ttm_adj', 'eps_diluted_approx_ttm_available_date',
                                 'net_income_ttm', 'revenue_ttm', 'net_income_ttm_available_date', 'revenue_ttm_available_date'])
    p = p.dropna(subset=['eps_diluted_approx_ttm_adj', 'eps_diluted_approx_ttm_available_date'])
    p = p.rename(columns={'eps_diluted_approx_ttm_adj': 'ttm', 'eps_diluted_approx_ttm_available_date': 'avail'})
    p['margin'] = p.net_income_ttm / p.revenue_ttm.where(p.revenue_ttm > 0)
    # margin is public only when net income AND revenue TTM are (external audit 2026-10-29: AMD 2017)
    p['av_margin'] = pd.concat([p.net_income_ttm_available_date, p.revenue_ttm_available_date], axis=1).max(axis=1, skipna=False)
    p['cik'] = p.cik.astype('int64')
    p = p.sort_values(['cik', 'period_end'])
    prior = p[['cik', 'period_end', 'ttm', 'margin', 'avail', 'av_margin']].copy()
    prior['period_end'] = prior.period_end + pd.Timedelta(days=365)
    prior = prior.rename(columns={'ttm': 'ttm_prior', 'margin': 'margin_prior', 'avail': 'avail_py',
                                  'av_margin': 'av_margin_py'}).sort_values('period_end')
    p = pd.merge_asof(p.sort_values('period_end'), prior, on='period_end', by='cik', tolerance=pd.Timedelta(days=20),
                      direction='nearest')
    p = p.dropna(subset=['ttm_prior'])
    # every value in this panel is used only once ALL inputs incl. the year-ago EPS / margin are public
    p['avail'] = pd.concat([p.avail, p.avail_py], axis=1).max(axis=1, skipna=False)
    p['margin_prior'] = p.margin_prior.where(p.av_margin_py <= p.avail)        # growth_margin5 needs it public too
    p['growth'] = np.where(p.ttm_prior > 0, p.ttm / p.ttm_prior - 1, np.nan)
    p['dEPS'] = p.ttm - p.ttm_prior
    # protections against a tiny base: (1) base-period net margin >= 5 %, (2) symmetric growth (bounded −200…+200 %)
    p['growth_margin5'] = np.where((p.ttm_prior > 0) & (p.margin_prior >= 0.05), p.ttm / p.ttm_prior - 1, np.nan)
    den = (p.ttm.abs() + p.ttm_prior.abs()) / 2
    p['growth_sym'] = np.where(den > 0, (p.ttm - p.ttm_prior) / den, np.nan)
    # for every month-end: latest row PUBLIC at t (all 4 quarters filed) with a fresh fiscal quarter
    grid = pd.DataFrame([(c, t) for c in p.cik.unique() for t in form], columns=['cik', 't']).sort_values('t')
    # availability ties → latest fiscal period wins (stable sort), see ml_features.fundamental_panel
    g = pd.merge_asof(grid, p.sort_values(['avail', 'period_end'], kind='mergesort'), left_on='t', right_on='avail', by='cik', direction='backward')
    g = g[(g.t - g.period_end).dt.days <= 200]
    return g[['cik', 't', 'period_end', 'growth', 'growth_margin5', 'growth_sym', 'dEPS', 'ttm', 'ttm_prior']]


def main():
    daily, P, aliases, bad = bt.load_prices()
    form = P.index[(P.index >= pd.Timestamp(bt.START) - pd.offsets.MonthEnd(1)) &
                   (P.index <= pd.Timestamp(bt.END) - pd.offsets.MonthEnd(1))]
    hold = form + pd.offsets.MonthEnd(1)
    members_raw, _ = bt.load_membership(form)
    members = {t: {x for x in m if not any(a <= t <= b for a, b in bad.get(x, []))} for t, m in members_raw.items()}
    sec_df = bt.build_sector_table(aliases)
    secP, _ = bt.build_panel(sec_df, form)
    eng = bt.Engine(P, daily, members, secP, form)
    px = bt.Prices(daily, P, 0)
    res = bt.load_resolutions()
    rf = bt.load_rf(hold)
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    t2c = {t.replace('.', '-'): int(c) for t, c in zip(cm.ticker, cm.cik)}
    G = growth_panel(form, P)
    Gi = G.set_index(['t', 'cik'])

    def run(variant, top_n=10, require_pos=True, pick='mom'):
        rows, w_pre, cov = [], {}, []
        for t in form:
            df, mom = eng.eligible(t, 12)
            if df.empty:
                continue
            df['cik'] = [t2c.get(s) if cik_valid(s, t) else None for s in df.index]   # (ticker, CIK) validity window
            gv = []
            for s, c in zip(df.index, df.cik):
                key = (t, c)
                if c is not None and key in Gi.index:
                    r = Gi.loc[key]
                    gv.append(r.dEPS / P.at[t, s] if variant == 'deps_p' else r[variant])
                else:
                    gv.append(np.nan)
            df['g'] = gv
            have = df.g.notna()
            cov.append((t, len(df), int(have.sum())))
            cand = bt.rank_desc(df.g[have]).index[:top_n]
            if pick == 'ew':
                picks = list(cand)
            else:
                m = df.loc[cand, 'mom']
                m = m[m > 0] if require_pos else m
                picks = bt.rank_desc(m).index[:1].tolist()
            if not picks:                                    # no qualifying stock → cash
                turn = sum(w_pre.values())
                r = float(rf.get(t + pd.offsets.MonthEnd(1), 0))
                rows.append({'formation': t, 'month': t + pd.offsets.MonthEnd(1), 'picks': 'CASH', 'gross': r,
                             'turnover': turn, 'net': r - turn * bt.COST_PER_SIDE, 'n_with_eps': int(have.sum()),
                             'exit_status': 'cash'})
                w_pre = {}
                continue
            w = {s: 1 / len(picks) for s in picks}
            rr, st = zip(*[px.ret(t, s, res) for s in picks])
            turn = sum(abs(w.get(k, 0) - w_pre.get(k, 0)) for k in set(w) | set(w_pre))
            r = float(np.dot([w[s] for s in picks], rr))
            grow = {s: w[s] * (1 + x) for s, x, z in zip(picks, rr, st) if z == 'ok'}
            w_pre = {s: v / (1 + r) for s, v in grow.items()} if r > -1 else {}
            rows.append({'formation': t, 'month': t + pd.offsets.MonthEnd(1), 'picks': '|'.join(picks), 'gross': r,
                         'turnover': turn, 'net': r - turn * bt.COST_PER_SIDE, 'n_with_eps': int(have.sum()),
                         'pick_growth': float(df.loc[picks, 'g'].mean()), 'pick_mom': float(df.loc[picks, 'mom'].mean()),
                         'exit_status': '|'.join(st)})
        return pd.DataFrame(rows).set_index('month'), pd.DataFrame(cov, columns=['t', 'eligible', 'with_eps'])

    R = {}
    R['A: top-10 EPS growth → best momentum (>0) else cash'], cov = run('growth')
    R['B: top-10 ΔEPS/price → best momentum (>0) else cash'], _ = run('deps_p')
    R['F: top-10 EPS growth, base margin >= 5% → best momentum (>0) else cash'], _ = run('growth_margin5')
    R['G: top-10 symmetric EPS growth → best momentum (>0) else cash'], _ = run('growth_sym')
    R['C: top-10 EPS growth, equal weight (no momentum)'], _ = run('growth', pick='ew')
    R['D: top-10 ΔEPS/price, equal weight'], _ = run('deps_p', pick='ew')
    R['E: pure momentum top-1 (reference)'] = eng.run(bt.SPEC, px, res, sector_filter=False)
    spy = px.nxt['SPY'].reindex(form).set_axis(hold)
    n_is = int(round(len(hold) * bt.IS_FRAC))
    periods = {'IS 2009-01..2021-05': (hold[0], hold[n_is - 1]), 'IS 2012-01..2021-05 (EPS data usable)':
               (pd.Timestamp('2012-01-31'), hold[n_is - 1]), 'OOS 2021-06..2026-09': (hold[n_is], hold[-1]),
               'FULL 2012-01..2026-09': (pd.Timestamp('2012-01-31'), hold[-1]),
               'FULL 2012-01..2025-12': (pd.Timestamp('2012-01-31'), pd.Timestamp('2025-12-31'))}
    out = []
    for name, df in list(R.items()) + [('SPY', None)]:
        for lab, (a, z) in periods.items():
            r = (spy if df is None else df['net']).loc[a:z]
            s = bt.stats(r, rf, None if df is None else spy)
            out.append({'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'],
                        'maxDD': s['maxDD_month_end'], 'vol': s['vol'],
                        'cash_months': int((df.picks == 'CASH').loc[a:z].sum()) if df is not None and 'picks' in df else 0})
        if df is not None:
            safe = ''.join(c if c.isalnum() else '_' for c in name)[:50]
            df.to_csv(os.path.join(RES, f'monthly_{safe}.csv'))
    out = pd.DataFrame(out)
    out.to_csv(os.path.join(RES, 'summary.csv'), index=False)
    cov['pct'] = cov.with_eps / cov.eligible
    cov.to_csv(os.path.join(RES, 'eps_coverage.csv'), index=False)
    pd.set_option('display.width', 200)
    for lab in periods:
        x = out[out.period == lab].set_index('strategy')[['CAGR', 'Sharpe', 'maxDD', 'vol', 'cash_months']]
        print(f'\n== {lab}\n', x.assign(CAGR=(x.CAGR * 100).round(1), maxDD=(x.maxDD * 100).round(0),
                                         vol=(x.vol * 100).round(0), Sharpe=x.Sharpe.round(2)).to_string())
    print('\nEPS coverage of eligible members, by year:')
    print(cov.groupby(cov.t.dt.year).pct.mean().round(2).to_string())
    A = R['A: top-10 EPS growth → best momentum (>0) else cash']
    lr = np.log1p(A.net.loc['2012-01-31':])
    print('\nA: top-5 months share', round(lr.sort_values().tail(5).sum() / lr.sum(), 2),
          '| most held', A.picks.value_counts().head(8).to_dict())
    print(A.loc['2021-06-30':].sort_values('net', ascending=False).head(6)[['picks', 'net', 'pick_growth', 'pick_mom']])


if __name__ == '__main__':
    main()
