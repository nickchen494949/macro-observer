#!/usr/bin/env python3
"""
factor_screen.py — one-shot "factor health check" (rules frozen in FACTOR_SCREEN_SPEC.md before any result).

  python3 factor_screen.py build     # new fundamental factors + merged panel  → results/factor_screen/panel_screen.parquet
  python3 factor_screen.py screen    # methods 1/3/4 on 2010-01..2019-11 formations, verdicts → screen_table.csv
"""
import glob, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'factor_screen')
os.makedirs(OUT, exist_ok=True)
DEV = (pd.Timestamp('2010-01-31'), pd.Timestamp('2019-11-30'))
RETRO = (pd.Timestamp('2019-12-31'), pd.Timestamp('2026-08-31'))
PRICE = ['mom_12_1', 'mom_6_1', 'mom_3_1', 'rev_1m', 'mom_12_1_secrel', 'sector_mom', 'mom_accel', 'smooth', 'dist_sma200',
         'dist_sma50', 'dist_52wh', 'vol_3m', 'vol_12m', 'beta_12m', 'maxret_1m', 'ear', 'ear_sum4']
EARN = ['eps_g', 'eps_g_m5', 'eps_g_sym', 'deps_p', 'sue', 'eps_accel', 'rev_g', 'rev_g_q', 'rev_accel', 'margin',
        'margin_chg', 'gm_chg', 'rd_int']
VALUE = ['ep', 'log_mcap', 'sp', 'bm', 'div_yield']
EFF = ['inv_turn', 'inv_turn_chg', 'inv_minus_sales_g', 'asset_turn', 'gp_a']
QUAL = ['roe', 'accruals', 'leverage', 'net_issuance', 'buyback_yield', 'cfo_yield', 'asset_g']
FACTORS = PRICE + EARN + VALUE + EFF + QUAL
GROUP = {**{f: '价格' for f in PRICE}, **{f: '盈利增长' for f in EARN}, **{f: '估值规模' for f in VALUE},
         **{f: '效率库存' for f in EFF}, **{f: '质量资本' for f in QUAL}}


# ───────────────────────── new fundamental factors ─────────────────────────
def first_reports(L, tags, qtrs):
    x = L[L.tag.isin(tags) & (L.qtrs == qtrs) & (L.uom == 'USD') & L.is_first_report].copy()
    x['prio'] = x.tag.map({t: i for i, t in enumerate(tags)})
    x = x.sort_values(['cik', 'ddate', 'filed', 'prio']).drop_duplicates(['cik', 'ddate'])
    return x[['cik', 'ddate', 'value', 'filed']].assign(cik=lambda d: d.cik.astype('int64'))


def yoy(df, cols):
    """join the same table one year earlier (ddate − 365 days ± 20) → <col>_py and filed_py."""
    prior = df[['cik', 'ddate', 'avail'] + cols].copy()
    prior['ddate'] = prior.ddate + pd.Timedelta(days=365)
    prior = prior.rename(columns={**{c: c + '_py' for c in cols}, 'avail': 'avail_py'})
    return pd.merge_asof(df.sort_values('ddate'), prior.sort_values('ddate'), on='ddate', by='cik',
                         tolerance=pd.Timedelta(days=20), direction='nearest')


def asof(grid, tab, col, avail, stale_days):
    from ml_features import latest_fiscal_updates
    x = tab.dropna(subset=[avail])[['cik', avail, 'ddate', col]]
    x = latest_fiscal_updates(x.rename(columns={'ddate': 'period_end'}), avail).rename(columns={'period_end': 'ddate'})
    m = pd.merge_asof(grid.sort_values('t'), x, left_on='t', right_on=avail, by='cik', direction='backward')
    m.loc[(m.t - m.ddate).dt.days > stale_days, col] = np.nan
    return m.set_index(['t', 'cik'])[col]


def build_new(grid):
    from fundamentals_pit import split_factor_after
    L = pd.concat([pd.read_parquet(f, columns=['cik', 'tag', 'ddate', 'qtrs', 'uom', 'value', 'filed', 'is_first_report'])
                   for f in glob.glob(os.path.join(HERE, 'data', 'fundamentals', 'pit_long', '*.parquet'))])
    L['ddate'] = pd.to_datetime(L.ddate)
    L['filed'] = pd.to_datetime(L.filed)
    p = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'))
    p = p[p.cik.notna()].copy()
    p['cik'] = p.cik.astype('int64')
    p = p.rename(columns={'period_end': 'ddate'})
    # ── quarter-end balance items, matched with TTM revenue / net income of the same fiscal quarter ──
    bal = {}
    for name, tags in {'inv': ['InventoryNet'], 'assets': ['Assets'], 'equity': ['StockholdersEquity'],
                       'liab': ['Liabilities']}.items():
        bal[name] = first_reports(L, tags, 0).rename(columns={'value': name, 'filed': 'f_' + name})
    Q = p[['cik', 'ddate', 'revenue_ttm', 'revenue_ttm_available_date', 'net_income_ttm', 'net_income_ttm_available_date',
           'diluted_shares', 'filed_diluted_shares', 'ticker']].copy()
    for name, b in bal.items():
        Q = pd.merge_asof(Q.sort_values('ddate'), b.sort_values('ddate'), on='ddate', by='cik',
                          tolerance=pd.Timedelta(days=10), direction='nearest')
    one = pd.Timedelta(days=1)
    Q['av_rev'] = Q.revenue_ttm_available_date
    Q['av_ni'] = Q.net_income_ttm_available_date
    for name in bal:
        Q['av_' + name] = Q['f_' + name] + one
    mx = lambda *c: pd.concat([Q[x] for x in c], axis=1).max(axis=1, skipna=False)
    Q['inv_turn'] = Q.revenue_ttm / Q.inv.where(Q.inv > 0)
    Q['avail_inv_turn'] = mx('av_rev', 'av_inv')
    Q['asset_turn'] = Q.revenue_ttm / Q.assets.where(Q.assets > 0)
    Q['avail_asset_turn'] = mx('av_rev', 'av_assets')
    Q['roe'] = Q.net_income_ttm / Q.equity.where(Q.equity > 0)
    Q['avail_roe'] = mx('av_ni', 'av_equity')
    Q['leverage'] = Q.liab / Q.assets.where(Q.assets > 0)
    Q['avail_leverage'] = mx('av_liab', 'av_assets')
    fac = [split_factor_after(t, f) if isinstance(t, str) and pd.notna(f) else np.nan
           for t, f in zip(Q.ticker, Q.filed_diluted_shares)]
    Q['sh_adj'] = Q.diluted_shares * np.array(fac, dtype=float)
    Q['av_sh'] = Q.filed_diluted_shares + one
    # year-over-year versions (each derived value public only when ALL inputs incl. last year's are)
    Q['avail'] = Q.avail_inv_turn
    Qy = yoy(Q[['cik', 'ddate', 'avail', 'inv_turn', 'inv', 'revenue_ttm']].copy(), ['inv_turn', 'inv', 'revenue_ttm'])
    Qy['inv_turn_chg'] = Qy.inv_turn - Qy.inv_turn_py
    Qy['inv_minus_sales_g'] = (Qy.inv / Qy.inv_py.where(Qy.inv_py > 0) - 1) - (Qy.revenue_ttm / Qy.revenue_ttm_py.where(Qy.revenue_ttm_py > 0) - 1)
    Qy['avail_yoy'] = pd.concat([Qy.avail, Qy.avail_py], axis=1).max(axis=1, skipna=False)
    Q['avail'] = Q.av_assets
    Qa = yoy(Q[['cik', 'ddate', 'avail', 'assets']].copy(), ['assets'])
    Qa['asset_g'] = Qa.assets / Qa.assets_py.where(Qa.assets_py > 0) - 1
    Qa['avail_ag'] = pd.concat([Qa.avail, Qa.avail_py], axis=1).max(axis=1, skipna=False)
    Q['avail'] = Q.av_sh
    Qs = yoy(Q[['cik', 'ddate', 'avail', 'sh_adj']].copy(), ['sh_adj'])
    Qs['net_issuance'] = Qs.sh_adj / Qs.sh_adj_py.where(Qs.sh_adj_py > 0) - 1
    Qs['avail_ni'] = pd.concat([Qs.avail, Qs.avail_py], axis=1).max(axis=1, skipna=False)
    # ── annual flows (10-K, qtrs = 4) ──
    A = first_reports(L, ['NetCashProvidedByUsedInOperatingActivities', 'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'], 4) \
        .rename(columns={'value': 'cfo', 'filed': 'f_cfo'})
    for name, tags in {'rep': ['PaymentsForRepurchaseOfCommonStock'],
                       'div': ['PaymentsOfDividendsCommonStock', 'PaymentsOfDividends'],
                       'gp': ['GrossProfit'], 'cost': ['CostOfRevenue', 'CostOfGoodsAndServicesSold'],
                       'ni_a': ['NetIncomeLoss', 'ProfitLoss']}.items():
        A = A.merge(first_reports(L, tags, 4).rename(columns={'value': name, 'filed': 'f_' + name}), on=['cik', 'ddate'], how='outer')
    A = pd.merge_asof(A.sort_values('ddate'), bal['assets'].sort_values('ddate'), on='ddate', by='cik',
                      tolerance=pd.Timedelta(days=10), direction='nearest')
    A = pd.merge_asof(A.sort_values('ddate'), Q[['cik', 'ddate', 'revenue_ttm', 'av_rev']].sort_values('ddate'), on='ddate',
                      by='cik', tolerance=pd.Timedelta(days=20), direction='nearest')
    # gross profit: the reported GrossProfit tag or revenue − cost of revenue — whichever was PUBLIC FIRST (a GrossProfit
    # value first reported years later as a comparative must not replace a fallback that was already public; found by
    # pit_fundamentals_truncation_test.py, MSFT FY2011)
    fb = A.revenue_ttm - A.cost
    f_fb = pd.concat([A.av_rev - one, A.f_cost], axis=1).max(axis=1, skipna=False)
    use_fb = fb.notna() & f_fb.notna() & (A.gp.isna() | A.f_gp.isna() | (f_fb < A.f_gp))
    A['gp_val'] = fb.where(use_fb, A.gp)
    A['f_gpv'] = f_fb.where(use_fb, A.f_gp)
    am = lambda *c: pd.concat([A[x] for x in c], axis=1).max(axis=1, skipna=False) + one
    A['gp_a'] = A.gp_val / A.assets.where(A.assets > 0)
    A['avail_gp_a'] = am('f_gpv', 'f_assets')
    A['accruals'] = (A.ni_a - A.cfo) / A.assets.where(A.assets > 0)
    A['avail_acc'] = am('f_ni_a', 'f_cfo', 'f_assets')
    A['avail_cfo'] = A.f_cfo + one
    A['avail_rep'] = A.f_rep + one
    A['avail_div'] = A.f_div + one
    # ── as-of each formation date ──
    out = pd.DataFrame(index=pd.MultiIndex.from_frame(grid[['t', 'cik']].drop_duplicates()))
    Q['avail_rev_ttm'] = Q.av_rev
    Q['avail_eq'] = Q.av_equity
    spec = [(Q, 'inv_turn', 'avail_inv_turn', 200), (Q, 'asset_turn', 'avail_asset_turn', 200), (Q, 'roe', 'avail_roe', 200),
            (Q, 'leverage', 'avail_leverage', 200), (Qy, 'inv_turn_chg', 'avail_yoy', 200),
            (Qy, 'inv_minus_sales_g', 'avail_yoy', 200), (Qa, 'asset_g', 'avail_ag', 200), (Qs, 'net_issuance', 'avail_ni', 200),
            (A, 'gp_a', 'avail_gp_a', 455), (A, 'accruals', 'avail_acc', 455), (A, 'cfo', 'avail_cfo', 455),
            (A, 'rep', 'avail_rep', 455), (A, 'div', 'avail_div', 455), (Q, 'revenue_ttm', 'avail_rev_ttm', 200),
            (Q, 'equity', 'avail_eq', 200)]
    g = grid[['t', 'cik']].drop_duplicates().dropna()
    g['cik'] = g.cik.astype('int64')
    for tab, col, av, st in spec:
        out[col] = asof(g, tab, col, av, st).reindex(out.index)
    return out.reset_index()


def build():
    X = pd.read_parquet(os.path.join(HERE, 'results', 'ml', 'panel.parquet'))
    E = pd.read_parquet(os.path.join(HERE, 'results', 'explosive', 'panel_explosive_ear.parquet'),
                        columns=['t', 'ticker', 'cik', 'smooth', 'mom_accel', 'eps_accel', 'rev_g_q', 'rev_accel', 'gm_chg',
                                 'rd_int', 'ear', 'ear_sum4'])
    X = X.merge(E, on=['t', 'ticker'], how='left')
    N = build_new(X.dropna(subset=['cik']))
    N.to_parquet(os.path.join(OUT, 'new_fundamentals.parquet'), index=False)
    X = X.merge(N, on=['t', 'cik'], how='left')
    mcap = np.exp(X.log_mcap)
    X['sp'] = X.revenue_ttm / mcap
    X['bm'] = X.equity / mcap
    X['div_yield'] = X['div'] / mcap
    X['buyback_yield'] = X.rep / mcap
    X['cfo_yield'] = X.cfo / mcap
    X = X.drop(columns=['revenue_ttm', 'equity', 'div', 'rep', 'cfo'])
    X.to_parquet(os.path.join(OUT, 'panel_screen.parquet'), index=False)
    dev = X[(X.t >= DEV[0]) & (X.t <= DEV[1])]
    cov = dev[FACTORS].notna().mean().round(3)
    print(X.shape, '| coverage in dev (share of stock-months):')
    print(cov.to_string())


# ───────────────────────── methods ─────────────────────────
def nw_se(x, lag=3):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return np.nan, n
    e = x - x.mean()
    v = e @ e / n
    for L_ in range(1, lag + 1):
        v += 2 * (1 - L_ / (lag + 1)) * (e[L_:] @ e[:-L_]) / n
    return np.sqrt(max(0.0, v) / n), n


def monthly_ic(D, f):
    rows = []
    for t, g in D.groupby('t'):
        if 'label_resolved' in g:
            g = g[g.label_resolved]
        g = g[[f, 'fwd_ret']].dropna()
        if len(g) < 30:
            continue
        ic = g[f].rank().corr(g.fwd_ret.rank())
        k = max(1, int(round(len(g) * 0.1)))
        s = g.sort_values(f)
        rows.append((t, ic, s.fwd_ret.iloc[-k:].mean() - s.fwd_ret.iloc[:k].mean()))
    return pd.DataFrame(rows, columns=['t', 'ic', 'spread']).set_index('t')


def romano_wolf(IC, n_boot=2000, block=6, seed=7):
    """IC: DataFrame months × factors (NaN allowed). Studentized stepdown, stationary bootstrap on months."""
    from backtest import stationary_bootstrap_idx
    M = IC.values
    T, K = M.shape
    mean = np.nanmean(M, axis=0)
    se = np.array([nw_se(M[:, k])[0] for k in range(K)])
    valid = np.isfinite(mean) & np.isfinite(se) & (se > 0)
    tstat = np.divide(np.abs(mean), se, out=np.zeros(K), where=valid)
    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, K))
    for b in range(n_boot):
        i = stationary_bootstrap_idx(T, block, rng)
        boot[b] = np.divide(np.abs(np.nanmean(M[i], axis=0) - mean), se,
                            out=np.zeros(K), where=valid)
    order = np.argsort(-tstat)
    p = np.empty(K)
    prev = 0.0
    for j, k in enumerate(order):
        rest = order[j:]
        mx = boot[:, rest].max(axis=1)
        pj = max(prev, float((1 + (mx >= tstat[k]).sum()) / (n_boot + 1))) if valid[k] else 1.0
        p[k] = pj
        prev = pj
    return pd.Series(p, index=IC.columns), pd.Series(np.divide(mean, se, out=np.full(K, np.nan), where=valid), index=IC.columns)


def known_training_mask(dates, first_test_formation, first='2010-01-31'):
    """A next-month label must be complete BEFORE the first prediction formation."""
    return (dates >= pd.Timestamp(first)) & ((dates + pd.offsets.MonthEnd(1)) < pd.Timestamp(first_test_formation))


def development_sign_share(ic, mean):
    """Never include retrospective December 2019 in the development-year verdict."""
    s = ic.loc[DEV[0]:DEV[1]]
    annual = s.groupby(s.index.year).mean().reindex(range(2010, 2020))
    return float((np.sign(annual) == np.sign(mean)).mean())


def ranked(D, cols, fill=True):
    R = D.groupby('t')[cols].rank(pct=True) - 0.5
    return R.fillna(0.0) if fill else R


def stability(D, n_rep=200, seed=7):
    from sklearn.linear_model import lasso_path
    Xr = ranked(D, FACTORS).values
    y = (D.groupby('t').fwd_ret.rank(pct=True) - 0.5).values
    months = D.t.values
    um = np.unique(months)
    # alpha grid: from "no factor selected" down to "exactly 5 selected on all dev data"
    a_max = np.abs(Xr.T @ (y - y.mean())).max() / len(y)
    alphas_f, coefs_f, _ = lasso_path(Xr, y - y.mean(), alphas=a_max * np.logspace(0, -3, 200))
    nsel = (np.abs(coefs_f) > 0).sum(axis=0)
    a_min = alphas_f[np.argmax(nsel >= 5)]
    grid = np.logspace(np.log10(a_max), np.log10(a_min), 10)
    rng = np.random.default_rng(seed)
    hits = np.zeros((len(grid), len(FACTORS)))
    for r in range(n_rep):
        pick = rng.choice(um, size=len(um) // 2, replace=False)
        m = np.isin(months, pick)
        Xs, ys = Xr[m], y[m] - y[m].mean()
        _, coefs, _ = lasso_path(Xs, ys, alphas=grid)
        hits += (np.abs(coefs.T) > 0)
    prob = (hits / n_rep).max(axis=0)
    return pd.Series(prob, index=FACTORS), grid, int(nsel[np.argmax(nsel >= 5)])


def perm_importance(D, seed=7):
    import lightgbm as lgb
    R = ranked(D, FACTORS, fill=False)
    y = D.groupby('t').fwd_ret.rank(pct=True).values
    years = D.t.dt.year.values
    rng = np.random.default_rng(seed)
    imp = {f: [] for f in FACTORS}
    base_ic = {}
    for Y in range(2015, 2020):
        te = years == Y
        tr = known_training_mask(D.t, D.loc[te, 't'].min()).values
        mdl = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=31, min_child_samples=200,
                                subsample=0.8, subsample_freq=1, random_state=7, verbose=-1, n_jobs=2)
        mdl.fit(R.values[tr], y[tr])
        Te = R[te].copy()
        tt, fr = D.t.values[te], D.fwd_ret.values[te]

        def ic_of(M):
            pr = mdl.predict(M.values)
            df = pd.DataFrame({'t': tt, 'p': pr, 'r': fr}).dropna()
            return df.groupby('t').apply(lambda g: g.p.rank().corr(g.r.rank()), include_groups=False).mean()
        b = ic_of(Te)
        base_ic[Y] = b
        for f in FACTORS:
            drops = []
            for _ in range(3):
                P = Te.copy()
                P[f] = P.groupby(tt)[f].transform(lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).values)
                drops.append(b - ic_of(P))
            imp[f].append(float(np.mean(drops)))
        print(f'  LightGBM test year {Y}: base IC {b:.4f}', flush=True)
    I = pd.DataFrame(imp, index=range(2015, 2020)).T
    return I, base_ic


def screen():
    X = pd.read_parquet(os.path.join(OUT, 'panel_screen.parquet'))
    X = X[X.fwd_ret.notna() & X.get('label_resolved', ~X.exit_status.isin(['source_gap', 'unresolved']))]
    D = X[(X.t >= DEV[0]) & (X.t <= DEV[1])].copy()
    Rt = X[(X.t >= RETRO[0]) & (X.t <= RETRO[1])].copy()
    print('dev stock-months', len(D), 'months', D.t.nunique(), '| retro months', Rt.t.nunique(), flush=True)
    ICs, SPs, ICr, yearly = {}, {}, {}, {}
    for f in FACTORS:
        m = monthly_ic(D, f)
        ICs[f], SPs[f] = m.ic, m.spread
        r = monthly_ic(Rt, f)
        ICr[f] = r.ic
        yd, yr = m.ic.groupby(m.index.year).mean(), r.ic.groupby(r.index.year).mean()
        yd.index = ['dev_' + str(y) for y in yd.index]
        yr.index = ['retro_' + str(y) for y in yr.index]
        yearly[f] = pd.concat([yd, yr])
    IC = pd.DataFrame(ICs)
    rw_p, tstat = romano_wolf(IC)
    from scipy.stats import norm
    raw_p = pd.Series(2 * (1 - norm.cdf(np.abs(tstat))), index=FACTORS)
    order = raw_p.sort_values().index
    holm, prev = {}, 0.0
    for i, f in enumerate(order):
        v = min(1.0, (len(order) - i) * raw_p[f])
        prev = max(prev, v)
        holm[f] = prev
    holm = pd.Series(holm)
    print('method 1 done', flush=True)
    stab, grid, nsel = stability(D)
    print('method 3 (stability selection) done; alpha grid', np.round(grid, 6).tolist(), 'selects', nsel, 'on full dev', flush=True)
    I, base_ic = perm_importance(D)
    print('method 4 (LightGBM permutation) done', flush=True)
    Y = pd.DataFrame(yearly).T
    Y.to_csv(os.path.join(OUT, 'yearly_ic.csv'))
    rows = []
    for f in FACTORS:
        mu = IC[f].mean()
        n_m = int(IC[f].notna().sum())
        same = development_sign_share(IC[f], mu)
        imp_pos = int((I.loc[f] > 0).sum())
        rr = ICr[f]
        se_r, _ = nw_se(rr.values) if len(rr) > 12 else (np.nan, 0)
        if n_m < 60:
            v = '不确定（数据不足）'
        elif rw_p[f] < 0.05 and same >= 0.7 and (stab[f] >= 0.6 or imp_pos >= 4):
            v = '有用'
        elif abs(tstat[f]) < 1.5 and stab[f] < 0.3 and I.loc[f].mean() <= 0:
            v = '没用'
        else:
            v = '不确定'
        rows.append({'factor': f, 'group': GROUP[f], 'verdict': v, 'direction': '高=好' if mu > 0 else '低=好',
                     'dev_months': n_m, 'IC_mean': mu, 't_NW': tstat[f], 'p_Holm': holm[f], 'p_RomanoWolf': rw_p[f],
                     'spread_top_minus_bottom_ann': SPs[f].mean() * 12, 'years_same_sign': same,
                     'stability_prob': stab[f], 'perm_imp_mean': I.loc[f].mean(), 'perm_imp_years_pos': imp_pos,
                     'retro_IC_2020_2026': rr.mean(), 'retro_t': rr.mean() / se_r if se_r else np.nan,
                     **{f'IC_{y}': Y.loc[f, y] for y in Y.columns}})
    T = pd.DataFrame(rows).sort_values(['verdict', 'p_RomanoWolf'])
    T.to_csv(os.path.join(OUT, 'screen_table.csv'), index=False)
    I.to_csv(os.path.join(OUT, 'perm_importance_by_year.csv'))
    pd.Series(base_ic).to_csv(os.path.join(OUT, 'lgbm_base_ic_by_year.csv'))
    pd.set_option('display.width', 250)
    cols = ['factor', 'group', 'verdict', 'direction', 'IC_mean', 't_NW', 'p_RomanoWolf', 'years_same_sign', 'stability_prob',
            'perm_imp_years_pos', 'retro_IC_2020_2026']
    print(T[cols].round(3).to_string(index=False))
    print('\nverdicts:', T.verdict.value_counts().to_dict())


if __name__ == '__main__':
    {'build': build, 'screen': screen}[sys.argv[1]]()
