#!/usr/bin/env python3
"""
mom30_roe.py — user's idea: top-30 by 12-1 momentum → keep ROE > 20 % → buy the highest EPS improvement (1 stock).

ROE (point-in-time) = TTM net income / stockholders' equity at the same fiscal quarter end (SEC, first reported;
StockholdersEquity, fallback incl. non-controlling interest). Available once BOTH the TTM net income (all 4 quarters)
and that quarter's balance sheet were filed (+1 day); stale if the quarter ended > 200 days before t.
Negative / zero equity → ROE undefined → excluded.
EPS improvement: main = TTM EPS YoY growth (prior TTM > 0); variant = ΔTTM EPS / price.
No qualifying stock → cash. Costs 10 bp per side. Panel: results/ml/panel.parquet (audited universe + returns).
"""
import glob, os

import numpy as np
import pandas as pd

import backtest as bt
from sma200_overlay import run

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'ml')


def roe_panel(form):
    from ml_features import latest_fiscal_updates
    L = pd.concat([pd.read_parquet(p, columns=['cik', 'tag', 'ddate', 'qtrs', 'uom', 'value', 'filed', 'is_first_report'])
                   for p in glob.glob(os.path.join(HERE, 'data', 'fundamentals', 'pit_long', '*.parquet'))])
    eq = L[L.tag.isin(['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'])
           & (L.qtrs == 0) & (L.uom == 'USD') & L.is_first_report].copy()
    eq['prio'] = (eq.tag != 'StockholdersEquity').astype(int)
    eq = eq.sort_values(['cik', 'ddate', 'filed', 'prio']).drop_duplicates(['cik', 'ddate'])
    eq = eq.rename(columns={'ddate': 'period_end', 'value': 'equity', 'filed': 'filed_eq'})[['cik', 'period_end', 'equity', 'filed_eq']]
    eq['cik'] = eq.cik.astype('int64')
    p = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'),
                        columns=['cik', 'period_end', 'net_income_ttm', 'net_income_ttm_available_date'])
    p = p.dropna()
    p['cik'] = p.cik.astype('int64')
    p = pd.merge_asof(p.sort_values('period_end'), eq.sort_values('period_end'), on='period_end', by='cik',
                      tolerance=pd.Timedelta(days=10), direction='nearest').dropna(subset=['equity'])
    p['roe'] = np.where(p.equity > 0, p.net_income_ttm / p.equity, np.nan)
    p['avail'] = pd.concat([p.net_income_ttm_available_date, p.filed_eq + pd.Timedelta(days=1)], axis=1).max(axis=1)
    grid = pd.DataFrame([(c, t) for c in p.cik.unique() for t in form], columns=['cik', 't']).sort_values('t')
    # availability ties → latest fiscal period wins (stable sort), see ml_features.fundamental_panel
    g = pd.merge_asof(grid, latest_fiscal_updates(p, 'avail')[['cik', 'avail', 'period_end', 'roe']], left_on='t', right_on='avail',
                      by='cik', direction='backward')
    g = g[(g.t - g.period_end).dt.days <= 200]
    return g[['cik', 't', 'roe']]


def main():
    X = pd.read_parquet(os.path.join(OUT, 'panel.parquet'))
    form = pd.DatetimeIndex(sorted(X.t.unique()))
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    t2c = {t.replace('.', '-'): int(c) for t, c in zip(cm.ticker, cm.cik)}
    X['cik'] = X.ticker.map(t2c)
    from fundamentals_pit import cik_valid
    X.loc[[not cik_valid(s, t) for s, t in zip(X.ticker, X.t)], 'cik'] = np.nan   # (ticker, CIK) validity window
    X = X.merge(roe_panel(form), on=['cik', 't'], how='left')
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    stats_rows = []

    def pick(g, col, roe_min=0.20, n=30):
        top = g.sort_values(['mom_12_1', 'ticker'], ascending=[False, True]).head(n)
        c = top[(top.roe > roe_min) & top[col].notna()]
        stats_rows.append((g.t.iloc[0], int(top.roe.notna().sum()), int((top.roe > roe_min).sum()), len(c)))
        return None if c.empty else c.sort_values([col, 'ticker'], ascending=[False, True]).ticker.iloc[0]
    S = {'mom top-30 → ROE>20% → best EPS growth': run(X, lambda g: pick(g, 'eps_g'), rf)}
    diag = pd.DataFrame(stats_rows, columns=['t', 'top30_with_roe', 'top30_roe_gt20', 'candidates'])
    S['mom top-30 → ROE>20% → best ΔEPS/price'] = run(X, lambda g: pick(g, 'deps_p'), rf)
    for name, f in [('pure momentum top-1', 'sma200_pure_momentum_top_1.csv'),
                    ('pure momentum top-1 + SMA200', 'sma200_pure_momentum_top_1___SMA200.csv')]:
        S[name] = pd.read_csv(os.path.join(OUT, f), parse_dates=['month']).set_index('month')
    px = bt.Prices(*bt.load_prices()[:2], 0)
    spy = px.nxt['SPY'].reindex(form).set_axis(hold)
    periods = {'2012-01..2021-05': ('2012-01-31', '2021-05-31'), '2021-06..2026-09': ('2021-06-30', '2026-09-30'),
               '2023-01..2026-09': ('2023-01-31', '2026-09-30'), '2012-01..2025-12': ('2012-01-31', '2025-12-31'),
               '2012-01..2026-09': ('2012-01-31', '2026-09-30')}
    rows = []
    for name, df in list(S.items()) + [('SPY', None)]:
        for lab, (a, z) in periods.items():
            r = (spy if df is None else df.net).loc[a:z]
            s = bt.stats(r, rf)
            rows.append({'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'], 'maxDD': s['maxDD_month_end'],
                         'cash_months': 0 if df is None else int((df.pick == 'CASH').loc[a:z].sum())})
        if df is not None and 'top-30' in name:
            df.to_csv(os.path.join(OUT, 'mom30roe_' + ''.join(c if c.isalnum() else '_' for c in name)[:50] + '.csv'))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'mom30roe_summary.csv'), index=False)
    for lab in periods:
        x = R[R.period == lab].set_index('strategy')
        print(f'\n== {lab}')
        print(x.assign(CAGR=(x.CAGR * 100).round(1), Sharpe=x.Sharpe.round(2), maxDD=(x.maxDD * 100).round(0))[
            ['CAGR', 'Sharpe', 'maxDD', 'cash_months']].to_string())
    d = diag[diag.t >= '2011-12-31']
    print('\nper month (2012+): top-30 names with ROE data', round(d.top30_with_roe.mean(), 1), '| with ROE > 20%',
          round(d.top30_roe_gt20.mean(), 1), '| final candidates', round(d.candidates.mean(), 1))
    c = S['mom top-30 → ROE>20% → best EPS growth']
    lr = np.log1p(c.net.loc['2012':])
    print('top-5 months share', round(lr.sort_values().tail(5).sum() / lr.sum(), 2), '| most held',
          c.pick.loc['2012':].value_counts().head(8).to_dict())
    y = (1 + c.net.loc['2012':]).groupby(c.loc['2012':].index.year).prod() - 1
    print((y * 100).round(1).to_dict())


if __name__ == '__main__':
    main()
