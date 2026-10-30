#!/usr/bin/env python3
"""
ml2_features.py — input sets for ML2 (ML2_SPEC.md §3).

  history_features(form, root=HERE) → C-group "financial trajectory" features per (t, cik), computed AS OF each
      formation date from the quarters public then (truncation-invariant by construction; covered by
      pit_fundamentals_truncation_test.py):
        rev_g_q0..q3, rev_g_slope          last 4 known quarterly revenue YoY growths (newest first) and their slope
        epsg_q0..q3, epsg_slope            same for symmetric quarterly EPS YoY growth
        gm_chg_4q, nm_chg_4q               change of quarterly gross / net margin over the last 4 known quarters
        rev_accel_streak                   consecutive known quarters with rising revenue YoY growth
        eps_beat_streak                    consecutive known quarters with EPS above the year-ago quarter
        inv_rev_chg                        inventory / TTM revenue now minus one year earlier
        cfo_ni, cfo_ni_chg                 annual operating cash flow / annual net income, and change vs the prior year
  Every quarterly value's availability = latest first-public date of its inputs (incl. the year-ago quarter).
"""
import glob, os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = ['rev_g_q0', 'rev_g_q1', 'rev_g_q2', 'rev_g_q3', 'rev_g_slope', 'epsg_q0', 'epsg_q1', 'epsg_q2', 'epsg_q3',
        'epsg_slope', 'gm_chg_4q', 'nm_chg_4q', 'rev_accel_streak', 'eps_beat_streak', 'inv_rev_chg', 'cfo_ni', 'cfo_ni_chg']


def _first(L, tags, qtrs):
    x = L[L.tag.isin(tags) & (L.qtrs == qtrs) & (L.uom == 'USD') & L.is_first_report].copy()
    x['prio'] = x.tag.map({t: i for i, t in enumerate(tags)})
    x = x.sort_values(['cik', 'ddate', 'filed', 'prio']).drop_duplicates(['cik', 'ddate'])
    return x[['cik', 'ddate', 'value', 'filed']].assign(cik=lambda d: d.cik.astype('int64'))


def quarterly_table(root=HERE):
    one = pd.Timedelta(days=1)
    p = pd.read_parquet(os.path.join(root, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'))
    p = p[p.cik.notna()].copy()
    p['cik'] = p.cik.astype('int64')
    p = p.rename(columns={'period_end': 'ddate'}).sort_values(['cik', 'ddate'])
    L = pd.concat([pd.read_parquet(f, columns=['cik', 'tag', 'ddate', 'qtrs', 'uom', 'value', 'filed', 'is_first_report'])
                   for f in glob.glob(os.path.join(root, 'data', 'fundamentals', 'pit_long', '*.parquet'))])
    L['ddate'] = pd.to_datetime(L.ddate)
    L['filed'] = pd.to_datetime(L.filed)
    gp = _first(L, ['GrossProfit'], 1).rename(columns={'value': 'gp', 'filed': 'f_gp'})
    inv = _first(L, ['InventoryNet'], 0).rename(columns={'value': 'inv', 'filed': 'f_inv'})
    q = p[['cik', 'ddate', 'revenue', 'filed_revenue', 'net_income', 'filed_net_income', 'eps_diluted_approx_adj',
           'filed_eps_diluted', 'revenue_ttm', 'revenue_ttm_available_date']].copy()
    for t in (gp, inv):
        q = pd.merge_asof(q.sort_values('ddate'), t.sort_values('ddate'), on='ddate', by='cik',
                          tolerance=pd.Timedelta(days=10), direction='nearest')
    q = q.sort_values(['cik', 'ddate'])
    prior = q[['cik', 'ddate', 'revenue', 'filed_revenue', 'eps_diluted_approx_adj', 'filed_eps_diluted', 'inv', 'f_inv',
               'revenue_ttm', 'revenue_ttm_available_date']].copy()
    prior['ddate'] = prior.ddate + pd.Timedelta(days=365)
    prior.columns = ['cik', 'ddate'] + [c + '_py' for c in prior.columns[2:]]
    q = pd.merge_asof(q.sort_values('ddate'), prior.sort_values('ddate'), on='ddate', by='cik',
                      tolerance=pd.Timedelta(days=20), direction='nearest').sort_values(['cik', 'ddate'])
    mx = lambda *c: pd.concat([q[x] for x in c], axis=1).max(axis=1, skipna=False)
    q['rev_g'] = np.where(q.revenue_py > 0, q.revenue / q.revenue_py - 1, np.nan)
    q['av_rev_g'] = mx('filed_revenue', 'filed_revenue_py') + one
    den = (q.eps_diluted_approx_adj.abs() + q.eps_diluted_approx_adj_py.abs()) / 2
    q['epsg'] = np.where(den > 0, (q.eps_diluted_approx_adj - q.eps_diluted_approx_adj_py) / den, np.nan)
    q['beat'] = (q.eps_diluted_approx_adj > q.eps_diluted_approx_adj_py).astype(float).where(q.eps_diluted_approx_adj_py.notna() & q.eps_diluted_approx_adj.notna())
    q['av_epsg'] = mx('filed_eps_diluted', 'filed_eps_diluted_py') + one
    q['gm'] = q.gp / q.revenue.where(q.revenue > 0)
    q['av_gm'] = mx('f_gp', 'filed_revenue') + one
    q['nm'] = q.net_income / q.revenue.where(q.revenue > 0)
    q['av_nm'] = mx('filed_net_income', 'filed_revenue') + one
    q['inv_rev'] = q.inv / q.revenue_ttm.where(q.revenue_ttm > 0)
    q['inv_rev_py'] = q.inv_py / q.revenue_ttm_py.where(q.revenue_ttm_py > 0)
    q['inv_rev_chg'] = q.inv_rev - q.inv_rev_py
    q['av_inv'] = pd.concat([q.f_inv + one, q.revenue_ttm_available_date, q.f_inv_py + one, q.revenue_ttm_available_date_py],
                            axis=1).max(axis=1, skipna=False)
    # annual cash flow vs net income
    cfo = _first(L, ['NetCashProvidedByUsedInOperatingActivities', 'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'], 4) \
        .rename(columns={'value': 'cfo', 'filed': 'f_cfo'})
    ni = _first(L, ['NetIncomeLoss', 'ProfitLoss'], 4).rename(columns={'value': 'ni', 'filed': 'f_ni'})
    A = cfo.merge(ni, on=['cik', 'ddate'], how='inner').sort_values(['cik', 'ddate'])
    A['cfo_ni'] = A.cfo / A.ni.where(A.ni.abs() > 0)
    A['av_cfo_ni'] = pd.concat([A.f_cfo, A.f_ni], axis=1).max(axis=1, skipna=False) + one
    return q, A


def _series_asof(vals, av, pe, t, k):
    """last k values (newest first) among rows public at t with non-missing value, plus their period_ends."""
    m = (av <= t) & np.isfinite(vals)
    v, d = vals[m], pe[m]
    return v[-k:][::-1], d[-k:][::-1]


def history_features(form, root=HERE):
    q, A = quarterly_table(root)
    T = np.array(sorted(pd.DatetimeIndex(form)), dtype='datetime64[ns]')
    out = []
    Ag = {c: g for c, g in A.groupby('cik')}
    for c, g in q.groupby('cik'):
        pe = g.ddate.values
        arr = {k: g[k].values.astype(float) for k in ['rev_g', 'epsg', 'beat', 'gm', 'nm', 'inv_rev_chg']}
        av = {k: g[a].values for k, a in [('rev_g', 'av_rev_g'), ('epsg', 'av_epsg'), ('beat', 'av_epsg'),
                                           ('gm', 'av_gm'), ('nm', 'av_nm'), ('inv_rev_chg', 'av_inv')]}
        ga = Ag.get(c)
        for t in T:
            rec = {'t': t, 'cik': c}
            fresh = lambda d: len(d) and (t - d[0]).astype('timedelta64[D]').astype(int) <= 200
            v, d = _series_asof(arr['rev_g'], av['rev_g'], pe, t, 6)
            if fresh(d):
                for i in range(min(4, len(v))):
                    rec[f'rev_g_q{i}'] = v[i]
                if len(v) >= 4:
                    rec['rev_g_slope'] = np.polyfit(np.arange(4), v[:4][::-1], 1)[0]
                st = 0
                for i in range(len(v) - 1):
                    if v[i] > v[i + 1]:
                        st += 1
                    else:
                        break
                rec['rev_accel_streak'] = st
            v, d = _series_asof(arr['epsg'], av['epsg'], pe, t, 4)
            if fresh(d):
                for i in range(len(v)):
                    rec[f'epsg_q{i}'] = v[i]
                if len(v) >= 4:
                    rec['epsg_slope'] = np.polyfit(np.arange(4), v[::-1], 1)[0]
            v, d = _series_asof(arr['beat'], av['beat'], pe, t, 8)
            if fresh(d):
                st = 0
                for x in v:
                    if x == 1:
                        st += 1
                    else:
                        break
                rec['eps_beat_streak'] = st
            for k, name in [('gm', 'gm_chg_4q'), ('nm', 'nm_chg_4q')]:
                v, d = _series_asof(arr[k], av[k], pe, t, 5)
                if fresh(d) and len(v) >= 5 and (d[0] - d[4]).astype('timedelta64[D]').astype(int) in range(330, 400):
                    rec[name] = v[0] - v[4]
            v, d = _series_asof(arr['inv_rev_chg'], av['inv_rev_chg'], pe, t, 1)
            if fresh(d):
                rec['inv_rev_chg'] = v[0]
            if ga is not None:
                m = (ga.av_cfo_ni.values <= t) & np.isfinite(ga.cfo_ni.values.astype(float))
                vv, dd = ga.cfo_ni.values[m].astype(float), ga.ddate.values[m]
                if len(vv) and (t - dd[-1]).astype('timedelta64[D]').astype(int) <= 455:
                    rec['cfo_ni'] = vv[-1]
                    if len(vv) >= 2 and (dd[-1] - dd[-2]).astype('timedelta64[D]').astype(int) in range(330, 400):
                        rec['cfo_ni_chg'] = vv[-1] - vv[-2]
            if len(rec) > 2:
                out.append(rec)
    H = pd.DataFrame(out)
    for k in HIST:
        if k not in H:
            H[k] = np.nan
    H['t'] = pd.to_datetime(H.t)
    return H[['t', 'cik'] + HIST]
