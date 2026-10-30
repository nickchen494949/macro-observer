#!/usr/bin/env python3
"""
explosive_factors.py — which factors catch "explosive" stocks BEFORE they explode?

Pre-declared design (written before looking at any result, 2026-10-28 22:50):
  Target      explosive6 = next-6-month return in the top 5 % of all eligible members that month
              doubler12  = next-12-month return >= +100 %                     (second definition)
  Universes   all eligible S&P 500 members; Information Technology only (GICS as of t)
  Dev         formation months 2012-01 … 2022-06 (6-month outcomes end by 2022-12)
  Holdout     formation months 2023-01 … 2026-03
  Metric      lift = hit rate of the factor's top decile / base rate, per month; t-stat of (hit − base) with
              Newey–West (lag 6, overlapping windows)
  Selection   a factor is "useful" if dev lift >= 1.2 and t >= 2 (all-S&P, explosive6). The composite is the
              equal-weight mean rank of the useful factors (direction as tested); it is then checked on holdout
              (lift) and as a portfolio (top-1, top-5; all S&P and tech), costs 10 bp per side.
New factors (all public at t): eps_accel, rev_g_q, rev_accel, gm_chg, rd_int, smooth (continuous momentum, "frog in
the pan"), mom_accel; plus existing ones from results/ml/panel.parquet.
"""
import glob, os

import numpy as np
import pandas as pd

import backtest as bt
from sma200_overlay import run
from legacy_portfolio import score_basket
from ml_features import latest_fiscal_updates

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'explosive')
os.makedirs(OUT, exist_ok=True)
DEV = ('2012-01-31', '2022-06-30')
HOLD = ('2023-01-31', '2026-03-31')


def quarterly_factors(form):
    p = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'),
                        columns=['cik', 'period_end', 'eps_diluted_approx_adj', 'revenue', 'filed_eps_diluted',
                                 'filed_revenue', 'available_date'])
    p = p[p.cik.notna()].copy()
    p['cik'] = p.cik.astype('int64')
    L = pd.concat([pd.read_parquet(f, columns=['cik', 'tag', 'ddate', 'qtrs', 'uom', 'value', 'filed', 'is_first_report'])
                   for f in glob.glob(os.path.join(HERE, 'data', 'fundamentals', 'pit_long', '*.parquet'))])
    L = L[(L.qtrs == 1) & (L.uom == 'USD') & L.is_first_report]
    for tag, name in [('GrossProfit', 'gp'), ('ResearchAndDevelopmentExpense', 'rd')]:
        x = L[L.tag == tag].sort_values(['cik', 'ddate', 'filed']).drop_duplicates(['cik', 'ddate'])
        x = x.rename(columns={'ddate': 'period_end', 'value': name, 'filed': 'filed_' + name})[['cik', 'period_end', name, 'filed_' + name]]
        x['cik'] = x.cik.astype('int64')
        p = pd.merge_asof(p.sort_values('period_end'), x.sort_values('period_end'), on='period_end', by='cik',
                          tolerance=pd.Timedelta(days=10), direction='nearest')
    p = p.sort_values(['cik', 'period_end'])
    p['gm'] = p.gp / p.revenue.where(p.revenue > 0)
    p['rd_int'] = p.rd / p.revenue.where(p.revenue > 0)
    prior = p[['cik', 'period_end', 'eps_diluted_approx_adj', 'revenue', 'gm', 'filed_eps_diluted', 'filed_revenue', 'filed_gp']].copy()
    prior['period_end'] += pd.Timedelta(days=365)
    prior.columns = ['cik', 'period_end', 'eps_py', 'rev_py', 'gm_py', 'f_eps_py', 'f_rev_py', 'f_gp_py']
    p = pd.merge_asof(p.sort_values('period_end'), prior.sort_values('period_end'), on='period_end', by='cik',
                      tolerance=pd.Timedelta(days=20), direction='nearest').sort_values(['cik', 'period_end'])
    den = (p.eps_diluted_approx_adj.abs() + p.eps_py.abs()) / 2
    p['eps_gs_q'] = np.where(den > 0, (p.eps_diluted_approx_adj - p.eps_py) / den, np.nan)
    p['rev_g_q'] = np.where(p.rev_py > 0, p.revenue / p.rev_py - 1, np.nan)
    p['gm_chg'] = p.gm - p.gm_py
    g = p.groupby('cik')
    p['eps_accel'] = p.eps_gs_q - g.eps_gs_q.shift(1)
    p['rev_accel'] = p.rev_g_q - g.rev_g_q.shift(1)
    # availability: each derived value is public only when ALL its inputs are — this quarter, the previous quarter
    # (accelerations) AND the year-ago quarters they are compared with (external audit 2026-10-29: year-ago inputs were
    # not gated). Missing input date → value not available (skipna=False).
    one = pd.Timedelta(days=1)
    mx = lambda *c: pd.concat(list(c), axis=1).max(axis=1, skipna=False)
    p['f_eps_q'] = mx(p.filed_eps_diluted, p.f_eps_py)
    p['f_rev_q'] = mx(p.filed_revenue, p.f_rev_py)
    g = p.groupby('cik')
    p['av_eps'] = mx(p.f_eps_q, g.f_eps_q.shift(1)) + one
    p['av_revq'] = p.f_rev_q + one
    p['av_rev'] = mx(p.f_rev_q, g.f_rev_q.shift(1)) + one
    p['av_gm'] = mx(p.filed_gp, p.filed_revenue, p.f_gp_py, p.f_rev_py) + one
    p['av_rd'] = mx(p.filed_rd, p.filed_revenue) + one
    grid = pd.DataFrame([(c, t) for c in p.cik.unique() for t in form], columns=['cik', 't']).sort_values('t')
    out = grid.copy()
    for av, cols in {'av_eps': ['eps_accel'], 'av_revq': ['rev_g_q'], 'av_rev': ['rev_accel'], 'av_gm': ['gm_chg'],
                     'av_rd': ['rd_int']}.items():
        # availability ties → latest fiscal period wins (stable sort), see ml_features.fundamental_panel
        x = latest_fiscal_updates(p.dropna(subset=[av])[['cik', av, 'period_end'] + cols], av)
        m = pd.merge_asof(grid, x, left_on='t', right_on=av, by='cik', direction='backward')
        stale = (m.t - m.period_end).dt.days > 200
        for c in cols:
            m.loc[stale, c] = np.nan
        out = out.merge(m[['cik', 't'] + cols], on=['cik', 't'], how='left')
    return out


def price_extras(daily, P, form):
    r = daily.pct_change(fill_method=None)
    seg = bt.SEG_D.reindex(index=daily.index, columns=daily.columns)
    r = r.where(seg == seg.shift(1))
    pos = (r > 0).astype(float).where(r.notna())
    neg = (r < 0).astype(float).where(r.notna())
    # window t-252 … t-21 sessions (skip the last month, like 12-1 momentum)
    pf = pos.shift(21).rolling(231, min_periods=180).mean()
    nf = neg.shift(21).rolling(231, min_periods=180).mean()
    same_window = (seg.shift(21) == seg.shift(252)) & (seg == seg.shift(21))
    pf, nf = pf.where(same_window), nf.where(same_window)
    idx = daily.index.searchsorted(form, side='right') - 1
    take = lambda x: x.iloc[idx].set_axis(form)
    m12 = bt.momentum(P, 12).reindex(form)
    ID = np.sign(m12) * (take(nf) - take(pf))
    smooth = -ID                                            # higher = more continuous (frog-in-the-pan)
    fwd6 = (P.shift(-6) / P - 1).reindex(form)
    fwd12 = (P.shift(-12) / P - 1).reindex(form)
    sg = bt.SEG_M.reindex(index=P.index, columns=P.columns)
    fwd6 = fwd6.where((sg.shift(-6) == sg).reindex(form))
    fwd12 = fwd12.where((sg.shift(-12) == sg).reindex(form))
    return smooth, fwd6, fwd12


def terminal_aware_fwd(X, daily, P, k):
    """Compound the backtest's monthly holding returns t→t+k for every panel row (bt.Prices.ret: ok / resolved_manual /
    delisted_in_month). After a terminal event the position is cash at the T-bill rate. A row is labelled only if its
    whole window is resolved; 'unresolved' / 'source_gap' (no price at all, outcome unknown) → NaN, counted in status."""
    px = bt.Prices(daily, P, 0)
    res = bt.load_resolutions()
    months = P.index
    rf = bt.load_rf(months + pd.offsets.MonthEnd(1))
    pos = {t: i for i, t in enumerate(months)}
    out, st = np.full(len(X), np.nan), np.empty(len(X), dtype=object)
    last = pd.Timestamp(bt.END)                     # last complete holding month (2026-09)
    for j, (t, s) in enumerate(zip(X.t, X.ticker)):
        i = pos[t]
        if i + k >= len(months) or months[i + k] > last:
            st[j] = 'window_not_complete'
            continue
        g, status = 1.0, 'ok'
        for m in range(k):
            tm = months[i + m]
            if status == 'ok':
                r, stt = px.ret(tm, s, res)
                if stt in ('unresolved', 'source_gap'):
                    status = stt
                    break
                g *= 1 + r
                if stt != 'ok':
                    status = 'terminal:' + stt
            else:
                g *= 1 + float(rf.get(tm + pd.offsets.MonthEnd(1), 0))
        st[j] = status
        if status in ('ok',) or status.startswith('terminal:'):
            out[j] = g - 1
    return out, st


def nw_t(x, lag=6):
    x = pd.Series(x).dropna().values
    n = len(x)
    if n < 12:
        return np.nan
    e = x - x.mean()
    v = e @ e / n
    for L in range(1, lag + 1):
        v += 2 * (1 - L / (lag + 1)) * (e[L:] @ e[:-L]) / n
    return x.mean() / np.sqrt(v / n)


def lift_table(D, factors, target, months):
    rows = []
    sub = D[D.t.isin(months) & D[target].notna()]
    for f, sign in factors.items():
        per = []
        for t, g in sub.groupby('t'):
            g = g[g[f].notna()]
            if len(g) < 30:
                continue
            k = max(1, int(round(len(g) * 0.10)))
            top = g.assign(s=sign * g[f]).sort_values(['s', 'ticker'], ascending=[False, True]).head(k)
            per.append((t, top[target].mean(), g[target].mean()))
        if not per:
            continue
        pr = pd.DataFrame(per, columns=['t', 'hit', 'base'])
        lift = pr.hit.mean() / pr.base.mean()
        rows.append({'factor': f, 'direction': '+' if sign > 0 else '−', 'months': len(pr), 'hit_rate_top10%': pr.hit.mean(),
                     'base_rate': pr.base.mean(), 'lift': lift, 't_NW': nw_t(pr.hit - pr.base),
                     'share_of_years_lift>1': float((pr.assign(y=pr.t.dt.year).groupby('y').apply(
                         lambda q: q.hit.mean() / max(q.base.mean(), 1e-9)) > 1).mean())})
    return pd.DataFrame(rows, columns=['factor', 'direction', 'months', 'hit_rate_top10%', 'base_rate',
                                      'lift', 't_NW', 'share_of_years_lift>1']).sort_values('lift', ascending=False)


def main():
    X = pd.read_parquet(os.path.join(HERE, 'results', 'ml', 'panel.parquet'))
    form = pd.DatetimeIndex(sorted(X.t.unique()))
    daily, P, aliases, bad = bt.load_prices()
    cache = os.path.join(OUT, 'panel_explosive.parquet')
    # Rebuild from the current corrected base panel. An old derived cache has no
    # binding to the source/features and must not silently bypass the audit.
    smooth, fwd6, fwd12 = price_extras(daily, P, form)
    X['smooth'] = [smooth.at[t, s] if s in smooth.columns else np.nan for t, s in zip(X.t, X.ticker)]
    # 6- / 12-month labels: universe and ranks are fixed at formation t; the path is the backtest's own monthly holding
    # return (terminal events: verified payouts, exit at the last trade then T-bill cash). The old price-ratio labels
    # (P[t+6]/P[t]) silently dropped every stock without a price at t+6 — e.g. cash-acquired XLNX / ATVI (external audit)
    X['fwd6'], X['fwd6_status'] = terminal_aware_fwd(X, daily, P, 6)
    X['fwd12'], X['fwd12_status'] = terminal_aware_fwd(X, daily, P, 12)
    X['mom_accel'] = X.mom_3_1 - X.mom_12_1 * 3 / 11
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    X['cik'] = X.ticker.map({t.replace('.', '-'): int(c) for t, c in zip(cm.ticker, cm.cik)})
    from fundamentals_pit import cik_valid
    X.loc[[not cik_valid(s, t) for s, t in zip(X.ticker, X.t)], 'cik'] = np.nan
    X = X.merge(quarterly_factors(form), on=['cik', 't'], how='left')
    X['explosive6'] = (X.groupby('t').fwd6.rank(pct=True) >= 0.95).astype(float).where(X.fwd6.notna())
    X['doubler12'] = (X.fwd12 >= 1.0).astype(float).where(X.fwd12.notna())
    X.to_parquet(os.path.join(OUT, 'panel_explosive.parquet'), index=False)
    return analyse(X, form, daily, P)


def analyse(X, form, daily, P):
    # downside twin: the same factor may also pick the next-6m BOTTOM 5 % (lottery stocks)
    X['bust6'] = (X.groupby('t').fwd6.rank(pct=True) <= 0.05).astype(float).where(X.fwd6.notna())
    FACT = {'mom_12_1': 1, 'mom_6_1': 1, 'mom_3_1': 1, 'mom_accel': 1, 'dist_52wh': 1, 'smooth': 1, 'dist_sma200': 1,
            'vol_3m': 1, 'maxret_1m': 1, 'eps_g': 1, 'eps_g_m5': 1, 'eps_accel': 1, 'sue': 1, 'deps_p': 1, 'rev_g': 1,
            'rev_g_q': 1, 'rev_accel': 1, 'margin_chg': 1, 'gm_chg': 1, 'rd_int': 1, 'ep': -1, 'log_mcap': -1}
    dev_m = form[(form >= DEV[0]) & (form <= DEV[1])]
    hold_m = form[(form >= HOLD[0]) & (form <= HOLD[1])]
    tech = X[X.sector == 'Information Technology']
    res = {}
    for uni, D in [('all', X), ('tech', tech)]:
        for target in ['explosive6', 'doubler12', 'bust6']:
            for lab, months in [('dev', dev_m), ('holdout', hold_m)]:
                # Twelve-month outcomes must end by the same development cutoff;
                # do not let the diagnostic use 2023 labels in a 2022 dev period.
                k = 12 if target == 'doubler12' else 6
                end = pd.Timestamp('2022-12-31') if lab == 'dev' else pd.Timestamp(bt.END)
                available_months = months[months + pd.offsets.MonthEnd(k) <= end]
                tb = lift_table(D, FACT, target, available_months)
                tb.to_csv(os.path.join(OUT, f'lift_{uni}_{target}_{lab}.csv'), index=False)
                res[(uni, target, lab)] = tb
    pd.set_option('display.width', 220)
    d = res[('all', 'explosive6', 'dev')].set_index('factor')
    h = res[('all', 'explosive6', 'holdout')].set_index('factor')
    td = res[('tech', 'explosive6', 'dev')].set_index('factor')
    th = res[('tech', 'explosive6', 'holdout')].set_index('factor')
    bd = res[('all', 'bust6', 'dev')].set_index('factor')
    show = pd.DataFrame({'dev_lift': d.lift, 'dev_t': d.t_NW, 'dev_years>1': d['share_of_years_lift>1'],
                         'hold_lift': h.lift, 'hold_t': h.t_NW, 'tech_dev_lift': td.lift, 'tech_hold_lift': th.lift,
                         'dev_BUST_lift': bd.lift}).round(2)
    print('ALL S&P, target = top-5% next-6m return (base rate 5%). Factor top decile:')
    print(show.sort_values('dev_lift', ascending=False).to_string())
    useful = [f for f in d.index if d.at[f, 'lift'] >= 1.2 and d.at[f, 't_NW'] >= 2]
    print('\nUSEFUL (pre-declared rule: dev lift >= 1.2 and t >= 2):', useful)
    # composite of useful factors → holdout lift + portfolios
    for c in useful:
        r = X.groupby('t')[c].rank(pct=True)
        X['r_' + c] = r if FACT[c] > 0 else 1 - r
    cols_u = ['r_' + c for c in useful]
    X['score'] = X[cols_u].mean(axis=1).where(X[cols_u].notna().sum(axis=1) >= int(np.ceil(len(cols_u) * 2 / 3)))
    FACT2 = {'score': 1}
    for uni, D in [('all', X), ('tech', X[X.sector == 'Information Technology'])]:
        for lab, months in [('dev', dev_m), ('holdout', hold_m)]:
            for tg in ['explosive6', 'bust6']:
                tb = lift_table(D, FACT2, tg, months)
                if len(tb):
                    r = tb.iloc[0]
                    print(f'composite [{uni}] {lab} {tg}: lift {r.lift:.2f} (t {r.t_NW:.2f}), hit {r["hit_rate_top10%"]:.3f} vs base {r.base_rate:.3f}')
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    best = lambda g: None if g.dropna(subset=['score']).empty else g.dropna(subset=['score']).sort_values(['score', 'ticker'], ascending=[False, True]).ticker.iloc[0]
    S = {'composite top-1 (all S&P)': run(X, best, rf), 'composite top-1 (tech)': run(X[X.sector == 'Information Technology'], best, rf)}
    for uni, D in [('all S&P', X), ('tech', X[X.sector == 'Information Technology'])]:
        S[f'composite top-5 ({uni})'] = score_basket(D, 'score', 5, rf, forms=form)
    px = bt.Prices(daily, P, 0)
    for k in ['SPY', 'XLK']:
        S[k] = pd.DataFrame({'net': px.nxt[k].reindex(form).values, 'pick': k}, index=hold)
    rows = []
    for name, df in S.items():
        df.to_csv(os.path.join(OUT, 'v1_' + ''.join(c if c.isalnum() else '_' for c in name) + '.csv'))
        for lab, (a, z) in {'2012-01..2022-12 (dev)': ('2012-01-31', '2022-12-31'), '2023-01..2026-09 (holdout)': ('2023-01-31', '2026-09-30'),
                            '2012-01..2026-09': ('2012-01-31', '2026-09-30')}.items():
            s = bt.stats(df.net.loc[a:z], rf)
            rows.append({'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'], 'maxDD': s['maxDD_month_end'],
                         'validation': 'retrospective test' if a >= '2023-01-31' else 'in-sample factor selection; not investable historical selection',
                         'cost_basis': 'gross benchmark' if name in ('SPY', 'XLK') else 'actual drifted turnover, 10bp/side'})
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'composite_portfolios.csv'), index=False)
    print()
    print(R.pivot(index='strategy', columns='period', values='CAGR').mul(100).round(1).astype(str) + '% / ' +
          R.pivot(index='strategy', columns='period', values='Sharpe').round(2).astype(str))
    c = S['composite top-1 (tech)']
    print('\ntech composite top-1 most held:', c.pick.loc['2012':].value_counts().head(8).to_dict())


if __name__ == '__main__':
    main()
