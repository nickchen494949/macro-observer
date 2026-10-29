#!/usr/bin/env python3
"""
ml2_run.py — ML2 experiment exactly as frozen in ML2_SPEC.md (git fb73f32).

  python3 ml2_run.py check     # builds labels / features / folds and prints COVERAGE ONLY (no performance)
  python3 ml2_run.py run       # the experiment → results/ml2/

Execution (§2): formation at month-end t; buy at the next session's OPEN, sell at the open of the first session after
the next month-end (open-to-open). Adjusted open = Yahoo open × adjclose / close (data/raw_open), WIKI adj_open; a
security without opens is executed at the next-session CLOSE on both legs (bt.Prices lag 1) and counted. Terminal
events follow the backtest (verified payouts; last trade then cash); positions with no quote at all: 0 % (stress
−30 % / −100 % reported).
"""
import json, os, sys

import numpy as np
import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'ml2')
os.makedirs(OUT, exist_ok=True)
POOL = 50
TEST_YEARS = list(range(2015, 2027))
A_COLS = ['mom_12_1', 'mom_6_1', 'mom_3_1', 'rev_1m', 'dist_sma200', 'dist_sma50', 'dist_52wh', 'vol_3m', 'vol_12m',
          'beta_12m', 'maxret_1m', 'smooth', 'mom_accel', 'dv_ratio', 'mkt_ret12', 'mkt_above200', 'mkt_vol3m', 'sector_mom']
B_ADD = ['eps_g', 'eps_g_sym', 'deps_p', 'ep', 'sue', 'margin', 'margin_chg', 'rev_g', 'log_mcap', 'sp', 'bm', 'roe', 'gp_a',
         'accruals', 'leverage', 'asset_turn', 'inv_turn', 'cfo_yield', 'net_issuance', 'days_since_filing', 'ear']
from ml2_features import HIST
C_ADD = HIST + ['ear_sum4']
SETS = {'A': A_COLS, 'B': A_COLS + B_ADD, 'C': A_COLS + B_ADD + C_ADD}
GRID = {'ridge': [{'alpha': a} for a in (1.0, 10.0, 100.0)],
        'lgbm': [{'num_leaves': n} for n in (7, 15)]}


# ───────────── prices: adjusted opens on the store's columns ─────────────
def _parse_source(ps, s):
    """PRICE_SOURCE string → list of (vendor, symbol, cut) in time order; part i is used for dates < cut_i and
    >= cut_{i-1}. Examples: 'yahoo', 'wiki<2018-03-27|yahoo', 'alias:META:yahoo', 'tiingo:BHI<2017-07-03|yahoo:BKR'."""
    if ps.startswith('alias:'):
        _, sym, rest = ps.split(':', 2)
        return _parse_source(rest, sym)
    out = []
    for part in ps.split('|'):
        cut = None
        if '<' in part:
            part, c = part.split('<', 1)
            cut = pd.Timestamp(c[:10])
        tok = part.split(':')
        vendor = tok[0]
        sym = s
        if vendor in ('yahoo', 'tiingo', 'wiki') and len(tok) > 1:
            sym = tok[1]
        elif vendor == 'archive' and len(tok) > 2:
            sym = tok[2]
        out.append((vendor, sym, cut))
    return out


def build_opens(daily):
    """adjusted opens aligned to the store's columns; only for the parts priced by Yahoo or WIKI"""
    O = pd.DataFrame(np.nan, index=daily.index, columns=daily.columns)
    od = os.path.join(HERE, 'data', 'raw_open')
    W = pd.read_parquet(os.path.join(HERE, 'data', 'wiki_bulk', 'wiki_open.parquet'))
    wiki = {t: g.set_index('date').adj_open for t, g in W.groupby('ticker')}
    cache = {}

    def yopen(sym):
        if sym not in cache:
            p = os.path.join(od, f'{sym}.json')
            if os.path.exists(p):
                j = json.load(open(p))
                x = pd.Series(j['adj_open'], index=pd.to_datetime(j['dates']), dtype=float)
                cache[sym] = x[~x.index.duplicated(keep='last')]
            else:
                cache[sym] = None
        return cache[sym]
    for s in daily.columns:
        parts = _parse_source(str(bt.PRICE_SOURCE.get(s, '')), s)
        col = pd.Series(np.nan, index=daily.index)
        lo = None
        for vendor, sym, cut in parts:
            x = yopen(sym) if vendor == 'yahoo' else wiki.get(sym) if vendor == 'wiki' else None
            m = np.ones(len(daily.index), bool)
            if lo is not None:
                m &= daily.index >= lo
            if cut is not None:
                m &= daily.index < cut
            if x is not None:
                col[m] = x.reindex(daily.index)[m]
            lo = cut
        O[s] = col.where(daily[s].notna())               # same security / segment as the store's close
    return O


class OpenPrices:
    """ret(t, s): open-to-open holding return for formation t (falls back to next-session close on both legs)."""
    def __init__(self, daily, P, O):
        self.daily, self.P, self.O = daily, P, O
        self.close1 = bt.Prices(daily, P, 1)                      # next-session close execution (fallback + statuses)
        self.sess = daily['SPY'].dropna().index
        self.used_open, self.used_close = 0, 0

    def _next_session(self, t):
        i = self.sess.searchsorted(t, side='right')
        return self.sess[i] if i < len(self.sess) else None

    def ret(self, t, s, res):
        r1, st = self.close1.ret(t, s, res)
        if st != 'ok':
            return r1, st
        d0 = self._next_session(t)
        d1 = self._next_session(t + pd.offsets.MonthEnd(1))
        if d0 is None or d1 is None or s not in self.O.columns:
            self.used_close += 1
            return r1, st
        o0, o1 = self.O.at[d0, s], self.O.at[d1, s]
        seg = bt.SEG_D
        same = seg is None or s not in seg.columns or seg.at[d0, s] == seg.at[d1, s]
        if np.isfinite(o0) and np.isfinite(o1) and o0 > 0 and same:
            self.used_open += 1
            return float(o1 / o0 - 1), 'ok'
        self.used_close += 1
        return r1, st


# ───────────── panel ─────────────
def build_panel(daily, P, px):
    from ml2_features import history_features
    X = pd.read_parquet(os.path.join(HERE, 'results', 'factor_screen', 'panel_screen.parquet'))
    X = X[X.t >= '2010-12-31'].copy()
    form = pd.DatetimeIndex(sorted(X.t.unique()))
    # pool: top-50 12-1 momentum among the eligible members of the month (deterministic tie-break by ticker)
    X = X.sort_values(['t', 'mom_12_1', 'ticker'], ascending=[True, False, True])
    X['mom_rank'] = X.groupby('t').cumcount() + 1
    # market context and dollar-volume trend
    spy = daily['SPY'].dropna()
    pos = spy.index.searchsorted(form, side='right') - 1
    sma = spy.rolling(200).mean()
    vol3 = spy.pct_change().rolling(63).std() * np.sqrt(252)
    ctx = pd.DataFrame({'t': form, 'mkt_ret12': (spy.iloc[pos].values / spy.shift(252).iloc[pos].values - 1),
                        'mkt_above200': (spy.iloc[pos].values > sma.iloc[pos].values).astype(float),
                        'mkt_vol3m': vol3.iloc[pos].values})
    X = X.merge(ctx, on='t', how='left')
    dvr = {}
    vd = os.path.join(HERE, 'data', 'raw_volume')
    for f in os.listdir(vd):
        if f.endswith('.json') and not f.startswith('_'):
            j = json.load(open(os.path.join(vd, f)))
            r = json.load(open(os.path.join(HERE, 'data', 'raw', f))) if os.path.exists(os.path.join(HERE, 'data', 'raw', f)) else None
            if r is None:
                continue
            v = pd.Series(j['volume'], index=pd.to_datetime(j['dates']), dtype=float)
            c = pd.Series(r['close'], index=pd.to_datetime(r['dates']), dtype=float)
            dv = (v * c.reindex(v.index)).dropna()
            ratio = dv.rolling(63, min_periods=40).median() / dv.rolling(252, min_periods=180).median()
            dvr[f[:-5]] = ratio
    DVR = pd.DataFrame(dvr)
    dpos = DVR.index.searchsorted(form, side='right') - 1
    DVR_m = DVR.iloc[dpos].set_axis(form)
    X['dv_ratio'] = [DVR_m.at[t, s] if s in DVR_m.columns else np.nan for t, s in zip(X.t, X.ticker)]
    H = history_features(form)
    X = X.merge(H, on=['t', 'cik'], how='left')
    # label: open-to-open holding return (same function for every model and benchmark)
    res = bt.load_resolutions()
    lab = [px.ret(t, s, res) for t, s in zip(X.t, X.ticker)]
    X['ret_oo'] = [r for r, _ in lab]
    X['status_oo'] = [s for _, s in lab]
    return X


def model_fit_predict(kind, params, tr, te, cols):
    from factor_screen import ranked
    import lightgbm as lgb
    from sklearn.linear_model import Ridge
    both = pd.concat([tr, te])
    R = ranked(both, cols, fill=False)
    y = tr.groupby('t').ret_oo.rank(pct=True).values - 0.5
    if kind == 'ridge':
        F = R.fillna(0.0)
        miss = R[cols].isna().astype(float).add_suffix('_na')
        F = pd.concat([F, miss], axis=1).values
        m = Ridge(alpha=params['alpha']).fit(F[:len(tr)], y)
        return m.predict(F[len(tr):])
    m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=params['num_leaves'], max_depth=3,
                          min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=7,
                          verbose=-1).fit(R.values[:len(tr)], y)
    return m.predict(R.values[len(tr):])


def topk_weights(D, score_col, k):
    W = {}
    for t, g in D.dropna(subset=[score_col]).groupby('t', sort=True):
        top = g.sort_values([score_col, 'ticker'], ascending=[False, True]).ticker.head(k).tolist()
        W[t] = {s: 1 / len(top) for s in top}
    return W


def net_cagr(S, W):
    import winners_tracks as wt
    if not W:
        return -np.inf
    df = wt.run_weights(S, W)
    r = df.net
    return (1 + r).prod() ** (12 / len(r)) - 1


def walk_forward(X, S, kind, cols, k, pool_only=True):
    """returns test-period predictions (score) and the chosen params per test year"""
    D = X[X.mom_rank <= POOL] if pool_only else X
    D = D[D.ret_oo.notna()].copy()
    D['score'] = np.nan
    chosen = {}
    for Y in TEST_YEARS:
        tr_end = pd.Timestamp(f'{Y-3}-11-30')                 # embargo: last training label ends before validation
        val = D[(D.t.dt.year >= Y - 2) & (D.t.dt.year <= Y - 1)]
        tr = D[(D.t >= '2011-01-31') & (D.t <= tr_end)]
        te = D[D.t.dt.year == Y]
        if te.empty or tr.empty:
            continue
        best, best_v = None, -np.inf
        for params in GRID[kind]:
            v = val.copy()
            v['s'] = model_fit_predict(kind, params, tr, v, cols)
            c = net_cagr(S, topk_weights(v, 's', k))
            if c > best_v:
                best, best_v = params, c
        chosen[Y] = (best, best_v)
        tr2 = D[(D.t >= '2011-01-31') & (D.t <= pd.Timestamp(f'{Y-1}-11-30'))]
        D.loc[te.index, 'score'] = model_fit_predict(kind, best, tr2, te, cols)
    return D, chosen


def check():
    daily, P, aliases, bad = bt.load_prices()
    O = build_opens(daily)
    px = OpenPrices(daily, P, O)
    X = build_panel(daily, P, px)
    X.to_parquet(os.path.join(OUT, 'panel_ml2.parquet'), index=False)
    pool = X[X.mom_rank <= POOL]
    print('panel', X.shape, '| pool rows', len(pool), '| months', pool.t.nunique())
    print('open execution share (pool rows):', round(px.used_open / max(1, px.used_open + px.used_close), 3),
          '| next-close fallback rows:', px.used_close)
    cov = pool[SETS['C']].notna().mean().round(2)
    print('feature coverage in the pool:', cov.to_dict())
    print('label status in pool:', pool.status_oo.value_counts().to_dict())


def run():
    import winners_tracks as wt
    lp = os.path.join(HERE, 'data', 'raw_open', '_log.json')
    log = json.load(open(lp)) if os.path.exists(lp) else {}
    n_raw = len([f for f in os.listdir(os.path.join(HERE, 'data', 'raw')) if f.endswith('.json') and not f.startswith('_')])
    if len(log) < n_raw:
        raise SystemExit(f'opens download incomplete ({len(log)}/{n_raw}) — ML2 runs on the complete data')
    daily, P, aliases, bad = bt.load_prices()
    O = build_opens(daily)
    px = OpenPrices(daily, P, O)
    X = build_panel(daily, P, px)
    X.to_parquet(os.path.join(OUT, 'panel_ml2.parquet'), index=False)
    S = {'px': px, 'res': bt.load_resolutions(), 'daily': daily,
         'rf': bt.load_rf(pd.date_range('2009-01-31', '2026-10-31', freq='ME'))}
    test_mask = lambda D: D[(D.t.dt.year >= TEST_YEARS[0]) & (D.t.dt.year <= TEST_YEARS[-1])]
    strategies, chosen_all, preds = {}, {}, []
    for kind in ('ridge', 'lgbm'):
        for setname, cols in SETS.items():
            for k in (1, 3):
                D, chosen = walk_forward(X, S, kind, cols, k, pool_only=True)
                name = f'{setname}-{kind} Top{k}'
                strategies[name] = topk_weights(test_mask(D), 'score', k)
                chosen_all[name] = {str(y): [v[0], float(v[1])] for y, v in chosen.items()}
                preds.append(test_mask(D)[['t', 'ticker', 'score', 'ret_oo']].assign(strategy=name))
                print('  done', name, flush=True)
    # benchmarks (same pool, same execution and costs)
    Pm = test_mask(X[(X.mom_rank <= POOL) & X.ret_oo.notna()])
    for k in (1, 3):
        strategies[f'BENCH momentum Top{k}'] = {t: {s_: 1 / k for s_ in g.sort_values(['mom_rank']).ticker.head(k)} for t, g in Pm.groupby('t')}
    for k in (1, 3):
        D, chosen = walk_forward(X, S, 'lgbm', SETS['C'], k, pool_only=False)
        strategies[f'BENCH full-universe C-lgbm Top{k}'] = topk_weights(test_mask(D), 'score', k)
        chosen_all[f'BENCH full-universe C-lgbm Top{k}'] = {str(y): [v[0], float(v[1])] for y, v in chosen.items()}
    form_t = sorted(Pm.t.unique())
    strategies['BENCH SPY'] = {t: {'SPY': 1.0} for t in form_t}
    json.dump(chosen_all, open(os.path.join(OUT, 'chosen_params.json'), 'w'), indent=1, default=str)
    pd.concat(preds).to_parquet(os.path.join(OUT, 'predictions_test.parquet'), index=False)
    # ── ledgers and statistics ──
    PER = {'2015-2019': ('2015-01-31', '2019-12-31'), '2020-2022': ('2020-01-31', '2022-12-31'),
           '2023-2026.09': ('2023-01-31', '2026-09-30'), 'TEST 2015-2026.09': ('2015-01-31', '2026-09-30')}
    wt.PERIODS = PER
    monthly, rows = {}, []
    for name, W in strategies.items():
        for stress_lab, stress in [('base', None), ('stress -30%', -0.30), ('stress -100%', -1.0)]:
            df = wt.run_weights(S, W, stress=stress)
            df = df.loc['2015-01-31':'2026-09-30']
            if stress is None:
                monthly[name] = df
                df.to_csv(os.path.join(OUT, 'monthly_' + ''.join(c if c.isalnum() else '_' for c in name) + '.csv'))
                for rec in wt.stats_block(S, df, name):
                    rows.append(rec)
                y = (1 + df.net).groupby(df.index.year).prod() - 1
                for yr, v in y.items():
                    rows.append({'strategy': name, 'period': f'year {yr}', 'CAGR': v})
            else:
                r = df.net
                rows.append({'strategy': name, 'period': f'TEST 2015-2026.09 {stress_lab}', 'CAGR': (1 + r).prod() ** (12 / len(r)) - 1})
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, 'summary.csv'), index=False)
    # layered comparisons: A vs momentum, B vs A, C vs B (per model, per Top-k)
    comp = []
    for kind in ('ridge', 'lgbm'):
        for k in (1, 3):
            pairs = [(f'A-{kind} Top{k}', f'BENCH momentum Top{k}'), (f'B-{kind} Top{k}', f'A-{kind} Top{k}'),
                     (f'C-{kind} Top{k}', f'B-{kind} Top{k}')]
            for x, ybase in pairs:
                a, b = monthly[x].net, monthly[ybase].net
                j = pd.concat([a, b], axis=1, keys=[x, ybase]).dropna()
                bs = bt.paired_bootstrap([j[x], j[ybase]], S['rf'], n=2000)
                ca = (1 + j[x]).prod() ** (12 / len(j)) - 1
                cb = (1 + j[ybase]).prod() ** (12 / len(j)) - 1
                yd = ((1 + j[x]).groupby(j.index.year).prod() - (1 + j[ybase]).groupby(j.index.year).prod())
                comp.append({'comparison': f'{x} vs {ybase}', 'CAGR_x': ca, 'CAGR_base': cb, 'CAGR_diff': ca - cb,
                             'CAGR_diff_p5_p50_p95': bs.get(f'{x} minus {ybase}: CAGR diff p5/p50/p95'),
                             'share_resamples_diff_le_0': bs.get(f'{x} minus {ybase}: share of resamples with CAGR diff <= 0'),
                             'years_x_better': int((yd > 0).sum()), 'years': int(len(yd))})
    C = pd.DataFrame(comp)
    C.to_csv(os.path.join(OUT, 'layered_comparisons.csv'), index=False)
    # ranking accuracy (diagnostic) and deflated Sharpe of the best of the 12 model lines
    P_ = pd.concat(preds)
    ic = P_.groupby(['strategy', 't']).apply(lambda g: g.score.rank().corr(g.ret_oo.rank()), include_groups=False).groupby('strategy').mean()
    ic.to_csv(os.path.join(OUT, 'ic_test.csv'))
    model_names = [n for n in monthly if not n.startswith('BENCH')]
    srs = [monthly[n].net.mean() / monthly[n].net.std() for n in model_names]
    best = max(model_names, key=lambda n: (1 + monthly[n].net).prod())
    dsr = bt.deflated_sharpe(monthly[best].net.values, srs, len(monthly[best]))
    meta = {'pool': POOL, 'test_years': TEST_YEARS, 'trials': {'model_configs': 6, 'topk_lines': 12,
            'param_grid': {k: len(v) for k, v in GRID.items()}, 'benchmarks': 5},
            'open_execution_share': px.used_open / max(1, px.used_open + px.used_close),
            'best_model_line_by_test_CAGR': best, 'deflated_sharpe_prob_best_of_12': dsr[0]}
    json.dump(meta, open(os.path.join(OUT, 'meta.json'), 'w'), indent=1, default=float)
    pd.set_option('display.width', 250)
    v = T[T.period.isin(list(PER))].copy()
    v['v'] = (v.CAGR * 100).round(1).astype(str) + '% / ' + v.Sharpe.round(2).astype(str) + ' / ' + (v.maxDD_daily * 100).round(0).astype(str) + '%'
    print(v.pivot(index='strategy', columns='period', values='v')[list(PER)].to_string())
    print(C.round(3).to_string(index=False))
    print(json.dumps(meta, indent=1, default=float))


if __name__ == '__main__':
    {'check': check, 'run': run}[sys.argv[1]]()
