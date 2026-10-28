#!/usr/bin/env python3
"""
backtest.py — "Best stock in the best sector" momentum rotation, S&P 500, 2009-01 → 2026-09.

Rule (user spec)
  At every month-end t:
    1. Score each GICS sector by 12-1 momentum  (P[t-1] / P[t-12] - 1, skip the latest month)
    2. Pick the #1 sector
    3. Inside that sector, buy the single stock with the highest 12-1 momentum
    4. Hold for one month, rebalance at t+1
  Sample split 70 / 30 by month count: in-sample (IS) then out-of-sample (OOS).

Bias controls
  * Point-in-time S&P 500 membership (fja05680/sp500) — a stock is only eligible in months
    in which it was actually an index member (no "buy TSLA in 2012" look-ahead).
  * Signals use month-end t data only; returns are t → t+1.
  * Costs: 10 bp per side on traded weight (reported gross and net).
  * Residual survivorship: former members that Yahoo no longer carries (mostly acquired /
    bankrupt names) cannot be priced and are excluded. See REPORT.md.

Variants
  sector score:  'ew'  = equal-weighted mean 12-1 of the sector's eligible members (main)
                 'etf' = 12-1 of the SPDR sector ETF (XLK, XLF, …; XLRE from 2016, XLC from 2019)
  Plus an IS-only parameter grid (lookback × #sectors × #stocks × score) — the IS-best
  configuration is then evaluated once on OOS.
"""
import json, os, itertools

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')
RES = os.path.join(HERE, 'results')
os.makedirs(RES, exist_ok=True)

START, END = '2009-01-31', '2026-09-30'          # holding-month range (month-end labels)
IS_FRAC = 0.70
COST_PER_SIDE = 0.0010
ETF_SECTOR = {'XLK': 'Information Technology', 'XLC': 'Communication Services', 'XLY': 'Consumer Discretionary',
              'XLF': 'Financials', 'XLI': 'Industrials', 'XLU': 'Utilities', 'XLE': 'Energy',
              'XLRE': 'Real Estate', 'XLB': 'Materials', 'XLP': 'Consumer Staples', 'XLV': 'Health Care'}
NON_STOCK = set(ETF_SECTOR) | {'SPY', 'RSP'}


# ───────────────────────────── data ─────────────────────────────
def load_prices():
    """Monthly (month-end) adjusted close panel + last-available daily price (for delisting)."""
    series = {}
    for f in os.listdir(RAW):
        if not f.endswith('.json') or f.startswith('_'):
            continue
        d = json.load(open(os.path.join(RAW, f)))
        s = pd.Series(d['adjclose'], index=pd.to_datetime(d['dates']), dtype=float)
        s = s[~s.index.duplicated(keep='last')].sort_index()
        series[d['symbol']] = s
    daily = pd.DataFrame(series).sort_index()
    # month-end panel: last available price inside each calendar month
    monthly = daily.resample('ME').last()
    # mask months with no trade at all in that month (resample.last would otherwise be NaN anyway)
    counts = daily.resample('ME').count()
    monthly = monthly.where(counts > 0)
    return daily, monthly


def load_membership(month_ends):
    h = pd.read_csv(os.path.join(HERE, 'data', 'sp500_hist_components.csv'), parse_dates=['date'])
    h = h.sort_values('date')
    out = {}
    for t in month_ends:
        row = h[h.date <= t]
        if row.empty:
            continue
        out[t] = {x.replace('.', '-') for x in row.tickers.iloc[-1].split(',')}
    return out


def load_sectors():
    s = pd.read_csv(os.path.join(HERE, 'data', 'sectors.csv'))
    s = s[s.sector.notna() & (s.sector != 'UNKNOWN')]
    return dict(zip(s.ticker, s.sector))


def load_rf(month_ends):
    """3M T-bill (FRED DGS3MO, read-only from the dashboard cache), monthly rate for month t→t+1."""
    p = os.path.join(HERE, '..', '..', 'data', 'fred', 'DGS3MO.json')
    d = json.load(open(p))
    s = pd.Series({pd.Timestamp(a): b for a, b in d['values'] if b is not None}, dtype=float).sort_index()
    m = s.resample('ME').last().reindex(month_ends).ffill()
    rf = (m / 100 / 12)
    rf.to_csv(os.path.join(HERE, 'data', 'rf_monthly.csv'), header=['rf_monthly'])
    return rf


# ───────────────────────────── engine ─────────────────────────────
def momentum(monthly, look, skip=1):
    return monthly.shift(skip) / monthly.shift(look) - 1


def run(cfg, P, daily, members, sectors, ret_fwd, months):
    """cfg: look, n_sec, n_stk, score. Returns DataFrame indexed by holding month (t+1)."""
    look, n_sec, n_stk, score = cfg['look'], cfg['n_sec'], cfg['n_stk'], cfg['score']
    mom = MOM_CACHE.setdefault(look, momentum(P, look))
    rows, prev_w = [], {}
    for t in months:                                   # t = formation month-end
        mem = members.get(t, set())
        m_t = mom.loc[t]
        elig = [s for s in mem if s in sectors and s in m_t.index and np.isfinite(m_t[s])
                and np.isfinite(P.at[t, s])]
        if not elig:
            continue
        df = pd.DataFrame({'mom': m_t[elig], 'sector': [sectors[s] for s in elig]})
        if score == 'ew':
            sec_score = df.groupby('sector').mom.mean()
        else:  # etf
            e = {ETF_SECTOR[k]: m_t.get(k, np.nan) for k in ETF_SECTOR}
            sec_score = pd.Series(e).dropna()
            sec_score = sec_score[sec_score.index.isin(df.sector.unique())]
        top_secs = sec_score.sort_values(ascending=False).index[:n_sec].tolist()
        picks = []
        for sec in top_secs:
            picks += df[df.sector == sec].mom.sort_values(ascending=False).index[:n_stk].tolist()
        w = {s: 1 / len(picks) for s in picks}
        r = np.mean([ret_fwd(t, s) for s in picks])
        turn = sum(abs(w.get(k, 0) - prev_w.get(k, 0)) for k in set(w) | set(prev_w))
        cost = turn * COST_PER_SIDE
        prev_w = w
        rows.append({'formation': t, 'month': t + pd.offsets.MonthEnd(1), 'sectors': '|'.join(top_secs),
                     'picks': '|'.join(picks), 'pick_mom': float(df.loc[picks, 'mom'].mean()),
                     'sector_score': float(sec_score[top_secs].mean()), 'gross': r,
                     'turnover': turn, 'net': r - cost})
    return pd.DataFrame(rows).set_index('month')


MOM_CACHE = {}


def make_ret_fwd(P, daily):
    nxt = P.shift(-1) / P - 1
    cache = {}

    def f(t, s):
        v = nxt.at[t, s]
        if np.isfinite(v):
            return float(v)
        # delisted / data gap during month t+1 → exit at last available daily close after t
        key = (t, s)
        if key not in cache:
            d = daily[s].loc[t:t + pd.offsets.MonthEnd(1)].dropna()
            cache[key] = float(d.iloc[-1] / P.at[t, s] - 1) if len(d) else 0.0
        return cache[key]
    return f


# ───────────────────────────── stats ─────────────────────────────
def stats(r, rf, bench=None):
    r = r.dropna()
    if len(r) < 3:
        return {}
    rf = rf.reindex(r.index).fillna(0)
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    ex = r - rf
    out = {
        'months': len(r),
        'CAGR': eq.iloc[-1] ** (1 / yrs) - 1,
        'vol': r.std() * np.sqrt(12),
        'Sharpe': ex.mean() / ex.std() * np.sqrt(12) if ex.std() > 0 else np.nan,
        'maxDD': (eq / eq.cummax() - 1).min(),
        'hit_rate': (r > 0).mean(),
        'best_m': r.max(), 'worst_m': r.min(),
        't_stat_excess': ex.mean() / (ex.std() / np.sqrt(len(ex))),
        'total_return': eq.iloc[-1] - 1,
    }
    if bench is not None:
        b = bench.reindex(r.index)
        a = (r - b).dropna()
        out['beat_bench_months'] = (a > 0).mean()
        out['excess_vs_bench_ann'] = a.mean() * 12
        out['IR_vs_bench'] = a.mean() / a.std() * np.sqrt(12)
        X = np.vstack([np.ones(len(b)), (b - rf.reindex(b.index)).values]).T
        y = ex.reindex(b.index).values
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        se = np.sqrt(np.sum(resid ** 2) / (len(y) - 2) * np.linalg.inv(X.T @ X).diagonal())
        out['alpha_ann'] = coef[0] * 12
        out['alpha_t'] = coef[0] / se[0]
        out['beta'] = coef[1]
    return out


def fmt(st):
    pct = {'CAGR', 'vol', 'maxDD', 'hit_rate', 'best_m', 'worst_m', 'total_return', 'beat_bench_months',
           'excess_vs_bench_ann', 'alpha_ann'}
    return {k: (f'{v*100:.1f}%' if k in pct else (f'{v:.2f}' if isinstance(v, float) else v)) for k, v in st.items()}


# ───────────────────────────── main ─────────────────────────────
def main():
    daily, P = load_prices()
    months_all = P.index[(P.index >= pd.Timestamp(START) - pd.offsets.MonthEnd(1)) &
                         (P.index <= pd.Timestamp(END) - pd.offsets.MonthEnd(1))]
    members = load_membership(months_all)
    sectors = load_sectors()
    hold_months = months_all + pd.offsets.MonthEnd(1)
    rf = load_rf(hold_months)
    ret_fwd = make_ret_fwd(P, daily)

    n_is = int(round(len(hold_months) * IS_FRAC))
    is_idx, oos_idx = hold_months[:n_is], hold_months[n_is:]
    split = {'IS': (is_idx[0], is_idx[-1]), 'OOS': (oos_idx[0], oos_idx[-1])}
    print(f'Holding months {hold_months[0].date()} → {hold_months[-1].date()} ({len(hold_months)}); '
          f'IS {is_idx[0].date()}→{is_idx[-1].date()} ({len(is_idx)}), OOS {oos_idx[0].date()}→{oos_idx[-1].date()} ({len(oos_idx)})')

    # coverage diagnostics
    cov = []
    for t in months_all:
        mem = members.get(t, set())
        priced = [s for s in mem if s in P.columns and np.isfinite(P.at[t, s])]
        withsec = [s for s in priced if s in sectors]
        cov.append({'month': t.date(), 'members': len(mem), 'priced': len(priced), 'priced_with_sector': len(withsec)})
    cov = pd.DataFrame(cov)
    cov.to_csv(os.path.join(RES, 'universe_coverage.csv'), index=False)
    print('coverage (priced_with_sector / members): first', cov.iloc[0].to_dict(), 'last', cov.iloc[-1].to_dict())

    bench = {}
    for b in ['SPY', 'RSP']:
        bench[b] = (P[b].shift(-1) / P[b] - 1).reindex(months_all).set_axis(hold_months)

    # ── 1. user spec + structural variants ──
    specs = {
        'SPEC: best stock in best sector (EW sector score)': dict(look=12, n_sec=1, n_stk=1, score='ew'),
        'SPEC: best stock in best sector (ETF sector score)': dict(look=12, n_sec=1, n_stk=1, score='etf'),
        'Ref: EW all stocks of best sector (EW score)': dict(look=12, n_sec=1, n_stk=9999, score='ew'),
        'Ref: best sector ETF only': None,
        'Ref: top-1 stock whole S&P (no sector filter)': 'top1',
        'Ref: top-10 stocks whole S&P': 'top10',
    }
    results = {}
    for name, cfg in specs.items():
        if isinstance(cfg, dict):
            results[name] = run(cfg, P, daily, members, sectors, ret_fwd, months_all)
        elif cfg is None:
            mom = momentum(P, 12)
            rows, prev = [], None
            for t in months_all:
                m = mom.loc[t, [k for k in ETF_SECTOR]].dropna()
                k = m.idxmax()
                r = float(P.shift(-1).at[t, k] / P.at[t, k] - 1)
                turn = 0 if k == prev else (1 if prev is None else 2)
                prev = k
                rows.append({'month': t + pd.offsets.MonthEnd(1), 'picks': k, 'gross': r, 'turnover': turn,
                             'net': r - turn * COST_PER_SIDE})
            results[name] = pd.DataFrame(rows).set_index('month')
        else:
            n = 1 if cfg == 'top1' else 10
            sec_all = {s: 'ALL' for s in sectors}
            results[name] = run(dict(look=12, n_sec=1, n_stk=n, score='ew'), P, daily, members, sec_all,
                                ret_fwd, months_all)

    summary = {}
    for name, df in results.items():
        summary[name] = {}
        for lab, (a, b) in {'FULL': (hold_months[0], hold_months[-1]), **split}.items():
            for kind in ['gross', 'net']:
                summary[name][f'{lab}_{kind}'] = stats(df[kind].loc[a:b], rf, bench['SPY'])
    for b in bench:
        summary[f'Bench: {b}'] = {f'{lab}_gross': stats(bench[b].loc[a:c], rf, None if b == 'SPY' else bench['SPY'])
                                  for lab, (a, c) in {'FULL': (hold_months[0], hold_months[-1]), **split}.items()}

    # ── 2. IS-only grid search → evaluate chosen config OOS ──
    grid = []
    for look, n_sec, n_stk, score in itertools.product([3, 6, 9, 12], [1, 2, 3], [1, 3, 5, 10], ['ew', 'etf']):
        cfg = dict(look=look, n_sec=n_sec, n_stk=n_stk, score=score)
        df = run(cfg, P, daily, members, sectors, ret_fwd, months_all)
        si = stats(df['net'].loc[split['IS'][0]:split['IS'][1]], rf)
        so = stats(df['net'].loc[split['OOS'][0]:split['OOS'][1]], rf)
        grid.append({**cfg, 'IS_CAGR': si['CAGR'], 'IS_Sharpe': si['Sharpe'], 'IS_maxDD': si['maxDD'],
                     'OOS_CAGR': so['CAGR'], 'OOS_Sharpe': so['Sharpe'], 'OOS_maxDD': so['maxDD']})
    grid = pd.DataFrame(grid).sort_values('IS_Sharpe', ascending=False)
    grid.to_csv(os.path.join(RES, 'grid_is_oos.csv'), index=False)
    best = grid.iloc[0]
    rank_corr = grid[['IS_Sharpe', 'OOS_Sharpe']].corr(method='spearman').iloc[0, 1]
    best_cfg = dict(look=int(best.look), n_sec=int(best.n_sec), n_stk=int(best.n_stk), score=best.score)
    best_df = run(best_cfg, P, daily, members, sectors, ret_fwd, months_all)
    results['IS-selected config'] = best_df
    summary['IS-selected config'] = {f'{lab}_{k}': stats(best_df[k].loc[a:b], rf, bench['SPY'])
                                     for lab, (a, b) in {'FULL': (hold_months[0], hold_months[-1]), **split}.items()
                                     for k in ['gross', 'net']}
    spec_rank = grid.reset_index(drop=True).query("look==12 and n_sec==1 and n_stk==1 and score=='ew'").index[0] + 1

    # ── calendar-year returns ──
    yr = {}
    for name, df in results.items():
        yr[name] = (1 + df['net']).groupby(df.index.year).prod() - 1
    for b in bench:
        yr[b] = (1 + bench[b]).groupby(bench[b].index.year).prod() - 1
    pd.DataFrame(yr).to_csv(os.path.join(RES, 'calendar_year_returns_net.csv'))

    # ── save ──
    for name, df in results.items():
        safe = ''.join(c if c.isalnum() else '_' for c in name)[:60]
        df.to_csv(os.path.join(RES, f'monthly_{safe}.csv'))
    meta = {'split': {k: [str(a.date()), str(b.date())] for k, (a, b) in split.items()},
            'n_months': len(hold_months), 'cost_per_side': COST_PER_SIDE,
            'is_selected_cfg': best_cfg, 'grid_size': len(grid), 'grid_rank_of_spec_by_IS_Sharpe': int(spec_rank),
            'grid_IS_vs_OOS_sharpe_spearman': rank_corr,
            'grid_OOS_sharpe_median': grid.OOS_Sharpe.median(), 'grid_IS_sharpe_median': grid.IS_Sharpe.median()}
    json.dump({'meta': meta, 'summary': summary}, open(os.path.join(RES, 'summary.json'), 'w'), indent=1, default=float)

    # print key table
    for name in summary:
        print(f'\n== {name}')
        for k, v in summary[name].items():
            if not v:
                continue
            f = fmt(v)
            print(f"  {k:10s} CAGR {f['CAGR']:>7} vol {f['vol']:>7} Sharpe {f['Sharpe']:>5} maxDD {f['maxDD']:>7} "
                  f"alpha {f.get('alpha_ann','-'):>7} (t {f.get('alpha_t','-')}) beta {f.get('beta','-')} "
                  f"beatSPY {f.get('beat_bench_months','-')}")
    print('\nmeta', json.dumps(meta, default=float, indent=1))
    print('\nTop grid (by IS Sharpe):\n', grid.head(10).to_string(index=False))

    # ── chart ──
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        plot = {'SPEC (EW score), net': results['SPEC: best stock in best sector (EW sector score)']['net'],
                'SPEC (ETF score), net': results['SPEC: best stock in best sector (ETF sector score)']['net'],
                'EW best sector, net': results['Ref: EW all stocks of best sector (EW score)']['net'],
                'SPY': bench['SPY'], 'RSP (EW S&P)': bench['RSP']}
        for lab, r in plot.items():
            eq = (1 + r.fillna(0)).cumprod()
            ax[0].plot(eq.index, eq.values, label=lab, lw=1.6 if 'SPEC' in lab else 1.1)
            ax[1].plot(eq.index, (eq / eq.cummax() - 1).values, lw=1)
        for a in ax:
            a.axvline(split['OOS'][0], color='k', ls='--', lw=1)
        ax[0].set_yscale('log'); ax[0].legend(); ax[0].grid(alpha=.3)
        ax[0].set_title('Best stock (12-1) in best sector (12-1), monthly rebalance — IS | OOS split at dashed line')
        ax[1].set_ylabel('Drawdown'); ax[1].grid(alpha=.3)
        fig.tight_layout(); fig.savefig(os.path.join(RES, 'equity_curve.png'), dpi=130)
    except Exception as e:  # noqa
        print('chart failed', e)


if __name__ == '__main__':
    main()
