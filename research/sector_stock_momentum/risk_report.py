#!/usr/bin/env python3
"""
risk_report.py — risk numbers that the monthly tables hide (external audit 2026-10-28, points 4 and 7).

For each composite portfolio (results/explosive/v3_*.csv, written by improve_v3.py) and XLK / SPY:
  * daily NAV rebuilt from the actual holdings and weights (drifting inside the month; a stock that stops trading is
    held flat at its last price). Each month's daily path is scaled so its month-end equals the reported monthly net
    return exactly (this spreads the trading cost / terminal-payout differences over the month); the largest
    month-end gap between the unscaled daily path and the reported GROSS return is printed as a check.
  * month-end max drawdown (what the tables showed) vs DAILY max drawdown
  * annualised volatility (monthly × √12) and daily (× √252)
  * calendar-year returns (2026 is January–September only, flagged as partial)
  * concentration: share of the period's total net log return earned by the best 5 months and by the 2 largest
    contributing stocks (single-stock strategies)
  * sub-period CAGR inside the retrospective holdout: 2023–2024, 2023–2025, 2023–2026-09
Output: results/explosive/risk_report.csv, risk_calendar_years.csv, risk_daily_nav.parquet
"""
import glob, os

import numpy as np
import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'explosive')
PERIODS = {'2012-01..2026-09': ('2012-01-31', '2026-09-30'), '2015-01..2026-09': ('2015-01-31', '2026-09-30'),
           '2023-01..2026-09': ('2023-01-31', '2026-09-30')}
SUB = {'2023-01..2024-12': ('2023-01-31', '2024-12-31'), '2023-01..2025-12': ('2023-01-31', '2025-12-31'),
       '2023-01..2026-09': ('2023-01-31', '2026-09-30')}


def nav_daily(df, daily):
    """df: monthly rows indexed by holding month with net, pick, optional picks / weights / gross."""
    out, level, gaps = [], 1.0, []
    for m, row in df.sort_index().iterrows():
        t = m - pd.offsets.MonthEnd(1)
        t0 = daily.index[daily.index.searchsorted(t, side='right') - 1]
        days = daily.index[(daily.index > t0) & (daily.index <= m)]
        if not len(days):
            continue
        if isinstance(row.get('picks'), str) and row.get('picks'):
            names = row.picks.split('|')
            w = np.array([float(x) for x in row.weights.split('|')])
        elif isinstance(row.get('pick'), str) and not row.pick.startswith('CASH') and row.pick != 'basket':
            names, w = [row.pick], np.array([1.0])
        else:
            names, w = [], np.array([])
        if names:
            seg = daily[names].loc[t0:m].ffill()
            rel = (seg / seg.iloc[0]).fillna(1.0).values @ w
            rel = pd.Series(rel, index=seg.index).loc[days]
        else:
            rel = pd.Series(1.0, index=days)
        if 'gross' in row and np.isfinite(row.get('gross', np.nan)):
            gaps.append(abs(rel.iloc[-1] - (1 + row.gross)))
        k = (1 + row.net) / rel.iloc[-1]
        path = level * rel * (k ** (np.arange(1, len(rel) + 1) / len(rel)))
        out.append(path)
        level = float(path.iloc[-1])
    return pd.concat(out), (max(gaps) if gaps else np.nan)


def mdd(x):
    x = pd.concat([pd.Series([1.0]), x.reset_index(drop=True)]) if x.iloc[0] != 1 else x
    return float((x / x.cummax() - 1).min())


def main():
    daily = bt.load_prices()[0]
    files = sorted(glob.glob(os.path.join(OUT, 'v3_*.csv')))
    files = [f for f in files if not f.endswith('v3_summary.csv')]
    def rd(f):
        d = pd.read_csv(f, index_col=0)
        d.index = pd.to_datetime(d.index)
        d.index.name = 'month'
        return d
    S = {os.path.basename(f)[3:-4]: rd(f) for f in files}
    rf_all = bt.load_rf(pd.date_range('2009-01-31', '2026-09-30', freq='ME'))
    rows, years, navs = [], [], {}
    for name, df in S.items():
        df = df.loc['2012-01-31':'2026-09-30']
        if name in ('XLK', 'SPY'):
            nav = daily[name].dropna().loc['2011-12-30':'2026-09-30']
            nav = nav / nav.iloc[0]
            gap = np.nan
        else:
            nav, gap = nav_daily(df, daily)
        navs[name] = nav
        for lab, (a, z) in PERIODS.items():
            r = df.net.loc[a:z]
            if len(r) < 6:
                continue
            s = bt.stats(r, rf_all)
            n = nav.loc[pd.Timestamp(a) - pd.offsets.MonthEnd(1):z]
            n = n / n.iloc[0]
            dr = n.pct_change().dropna()
            lr = np.log1p(r)
            rec = {'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'], 'vol_monthly_ann': s['vol'],
                   'vol_daily_ann': dr.std() * np.sqrt(252), 'maxDD_month_end': s['maxDD_month_end'], 'maxDD_daily': mdd(n),
                   'best5_months_share_of_log_return': float(lr.nlargest(5).sum() / lr.sum()) if lr.sum() > 0 else np.nan,
                   'daily_vs_reported_gross_max_gap': gap}
            if 'pick' in df and df.pick.ne('basket').any() and 'picks' not in df:
                by = lr.groupby(df.pick.loc[a:z]).sum().sort_values(ascending=False)
                rec['top2_stocks'] = ', '.join(f'{k} {v / lr.sum():.0%}' for k, v in by.head(2).items())
            rows.append(rec)
        y = (1 + df.net).groupby(df.index.year).prod() - 1
        for yr, v in y.items():
            years.append({'strategy': name, 'year': yr, 'net_return': v, 'partial': 'Jan-Sep only' if yr == 2026 else ''})
        for lab, (a, z) in SUB.items():
            r = df.net.loc[a:z]
            rows.append({'strategy': name, 'period': 'sub ' + lab, 'CAGR': (1 + r).prod() ** (12 / len(r)) - 1})
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, 'risk_report.csv'), index=False)
    Y = pd.DataFrame(years)
    Y.to_csv(os.path.join(OUT, 'risk_calendar_years.csv'), index=False)
    pd.DataFrame(navs).to_parquet(os.path.join(OUT, 'risk_daily_nav.parquet'))
    pd.set_option('display.width', 250)
    show = R[~R.period.str.startswith('sub')].copy()
    for c in ['CAGR', 'vol_monthly_ann', 'vol_daily_ann', 'maxDD_month_end', 'maxDD_daily', 'best5_months_share_of_log_return']:
        show[c] = (show[c] * 100).round(1)
    print(show.round(3).to_string(index=False))
    sub = R[R.period.str.startswith('sub')].pivot(index='strategy', columns='period', values='CAGR').mul(100).round(1)
    print(sub.to_string())
    neg = Y[Y.net_return < 0]
    print('losing calendar years:', neg.groupby('strategy').year.apply(list).to_dict())


if __name__ == '__main__':
    main()
