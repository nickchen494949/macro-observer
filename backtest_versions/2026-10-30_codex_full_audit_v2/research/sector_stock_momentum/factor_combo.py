#!/usr/bin/env python3
"""
factor_combo.py — do factors work in COMBINATION? (rules frozen in FACTOR_COMBO_SPEC.md before any result)

  python3 factor_combo.py
Families: A pre-specified classic composites (8), B ML models on all 47 factors (walk-forward), C data-driven
interaction search (search 2010-2015, test 2016-2019). Output: results/factor_combo/.
"""
import os

import numpy as np
import pandas as pd

import backtest as bt
from factor_screen import FACTORS, monthly_ic, nw_se, romano_wolf, ranked, known_training_mask

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'factor_combo')
os.makedirs(OUT, exist_ok=True)
DEV = (pd.Timestamp('2010-01-31'), pd.Timestamp('2019-11-30'))
RETRO = (pd.Timestamp('2019-12-31'), pd.Timestamp('2026-08-31'))
CLASSIC = {
    'A1 价值+动量': ['bm', 'ep', 'sp', 'mom_12_1'],
    'A2 质量+价值': ['roe', 'gp_a', '-accruals', '-leverage', 'bm', 'ep'],
    'A3 动量+低波动': ['mom_12_1', '-vol_3m'],
    'A4 动量+盈利惊喜': ['mom_12_1', 'sue', 'ear'],
    'A5 GARP': ['rev_g', 'eps_g_sym', 'roe', 'ep'],
    'A6 动量+营收毛利加速': ['mom_6_1', 'rev_accel', 'gm_chg'],
    'A7 质量+动量+价值': ['roe', 'gp_a', '-accruals', 'mom_12_1', 'bm', 'ep'],
    'A8 动量+短期反转': ['mom_12_1', '-rev_1m'],
}


def composite(D, items):
    cols = []
    for it in items:
        f, s = (it[1:], -1) if it.startswith('-') else (it, 1)
        r = D.groupby('t')[f].rank(pct=True)
        cols.append(r if s > 0 else 1 - r)
    M = pd.concat(cols, axis=1)
    return M.mean(axis=1).where(M.notna().sum(axis=1) >= int(np.ceil(len(items) / 2)))


def top_portfolio(D, score, frac=0.10):
    """Top-decile equal weight, one month, cost 10 bp per side × turnover (drifted weights)."""
    from legacy_portfolio import run_portfolio
    forms = pd.DatetimeIndex(sorted(D.t.unique()))
    rf = bt.load_rf(forms + pd.offsets.MonthEnd(1))
    def target(g):
        n_all = len(g)
        g = g.dropna(subset=['_s'])
        if g.empty:
            return {}
        k = max(1, int(np.ceil(n_all * frac)))
        sel = g.sort_values(['_s', 'ticker'], ascending=[False, True]).head(k)
        return {s: 1 / len(sel) for s in sel.ticker}
    return run_portfolio(D.assign(_s=score), target, rf, forms=forms)


def ic_of_score(D, score):
    return monthly_ic(D.assign(_s=score), '_s').ic


# ── B: walk-forward ML on all 47 factors ──
def walk_forward(X, model, years):
    import lightgbm as lgb
    from sklearn.linear_model import Ridge, Lasso
    Rf = ranked(X, FACTORS, fill=True).values
    Rn = ranked(X, FACTORS, fill=False).values
    resolved = X.get('label_resolved', ~X.exit_status.isin(['source_gap', 'unresolved']))
    known_ret = X.fwd_ret.where(resolved)
    y = (known_ret.groupby(X.t).rank(pct=True) - 0.5).values
    yr = X.t.dt.year.values
    pred = np.full(len(X), np.nan)
    chosen = {}
    for Y in years:
        te = yr == Y
        if not te.any():
            continue
        tr = known_training_mask(X.t, X.loc[te, 't'].min()).values & np.isfinite(y)
        if model == 'ridge':
            m = Ridge(alpha=10.0).fit(Rf[tr], y[tr])
            pred[te] = m.predict(Rf[te])
        elif model == 'lasso':
            grid = np.logspace(-5, -2, 12)
            best, best_ic = grid[0], -np.inf
            for a in grid:
                ics = []
                for v in range(Y - 3, Y):                       # time-series CV inside the training years
                    va = (yr == v) & tr
                    trv = (known_training_mask(X.t, X.loc[va, 't'].min()).values & np.isfinite(y)) if va.any() else np.zeros(len(X), bool)
                    if trv.sum() == 0 or va.sum() == 0:
                        continue
                    p = Lasso(alpha=a, max_iter=5000).fit(Rf[trv], y[trv]).predict(Rf[va])
                    df = pd.DataFrame({'t': X.t.values[va], 'p': p, 'r': X.fwd_ret.values[va]})
                    ics.append(df.groupby('t').apply(lambda g: g.p.rank().corr(g.r.rank()), include_groups=False).mean())
                ic = np.nanmean(ics) if ics else -np.inf
                if ic > best_ic:
                    best, best_ic = a, ic
            m = Lasso(alpha=best, max_iter=5000).fit(Rf[tr], y[tr])
            chosen[Y] = (float(best), int((np.abs(m.coef_) > 0).sum()))
            pred[te] = m.predict(Rf[te])
        else:
            m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=31, min_child_samples=200,
                                  subsample=0.8, subsample_freq=1, random_state=7, verbose=-1, n_jobs=2).fit(Rn[tr], y[tr])
            pred[te] = m.predict(Rn[te])
    return pd.Series(pred, index=X.index), chosen


# ── C: interaction search ──
def pair_search(S):
    rows = []
    months = sorted(S.t.unique())
    acc = {}
    for t in months:
        g = S[S.t == t]
        for A in FACTORS:
            a = g[A]
            if a.notna().sum() < 100:
                continue
            sub = g[a >= a.quantile(0.70)]
            if len(sub) < 30:
                continue
            resolved = sub.get('label_resolved', ~sub.exit_status.isin(['source_gap', 'unresolved']))
            ry = sub.fwd_ret.where(resolved).rank()
            ics = sub[FACTORS].rank().corrwith(ry)
            cnt = sub[FACTORS].where(resolved, axis=0).notna().sum()
            for B, v in ics.items():
                if B != A and cnt[B] >= 30 and np.isfinite(v):
                    acc.setdefault((A, B), []).append(v)
    for (A, B), v in acc.items():
        se, n = nw_se(np.array(v))
        if n >= 36:
            rows.append({'A_condition_top30': A, 'B_signal': B, 'months': n, 'IC': float(np.mean(v)), 't': float(np.mean(v) / se)})
    return pd.DataFrame(rows).assign(abs_t=lambda d: d.t.abs()).sort_values('abs_t', ascending=False)


def pair_score(D, A, B, sign):
    sc = pd.Series(np.nan, index=D.index)
    for t, g in D.groupby('t'):
        a = g[A]
        sub = g[(a >= a.quantile(0.70)) & g[B].notna()]
        sc.loc[sub.index] = sign * sub[B].rank(pct=True)
    return sc


def year_same_sign(ic):
    y = ic.groupby(ic.index.year).mean()
    return float((np.sign(y) == np.sign(ic.mean())).mean()), y


def ann(r):
    r = r.dropna()
    return (1 + r).prod() ** (12 / len(r)) - 1 if len(r) else np.nan


def main():
    X = pd.read_parquet(os.path.join(HERE, 'results', 'factor_screen', 'panel_screen.parquet'))
    # Eligibility is known at formation. Missing future outcomes must not remove
    # candidates before ranking; the ledger rejects an unpriceable selected stock.
    X = X[X.t >= DEV[0]].reset_index(drop=True)
    dev = (X.t >= DEV[0]) & (X.t <= DEV[1])
    retro = (X.t >= RETRO[0]) & (X.t <= RETRO[1])
    from legacy_portfolio import run_portfolio
    forms = pd.DatetimeIndex(sorted(X.t.unique()))
    rf = bt.load_rf(forms + pd.offsets.MonthEnd(1))
    px = bt.Prices(*bt.load_prices()[:2], 0)
    spy_rows = pd.DataFrame({'t': forms, 'ticker': 'SPY',
                            'fwd_ret': px.nxt['SPY'].reindex(forms).values, 'exit_status': 'ok'})
    def spy_for(index):
        ff = pd.DatetimeIndex(index) - pd.offsets.MonthEnd(1)
        return run_portfolio(spy_rows, lambda g: {'SPY': 1.0}, rf, forms=ff)
    spy_for(forms + pd.offsets.MonthEnd(1)).to_csv(os.path.join(OUT, 'monthly_BENCH_SPY.csv'))
    top_portfolio(X, pd.Series(0.0, index=X.index), frac=1.0).to_csv(os.path.join(OUT, 'monthly_BENCH_EW_universe.csv'))
    rows, yearly = [], {}

    def evaluate(fam, name, score, mask_eval, extra=None):
        D = X[mask_eval]
        ic = ic_of_score(D, score[mask_eval])
        Dr = X[retro]
        icr = ic_of_score(Dr, score[retro]) if score[retro].notna().any() else pd.Series(dtype=float)
        # One actual portfolio crosses the development/retrospective boundary.
        # Concatenating two independently reset ledgers invents a fresh cash account.
        combined = mask_eval | retro
        Dc = X[combined]
        all_pf = top_portfolio(Dc, score[combined])
        all_ew = top_portfolio(Dc, pd.Series(0.0, index=Dc.index), frac=1.0).net
        e_months = pd.DatetimeIndex(sorted(D.t.unique())) + pd.offsets.MonthEnd(1)
        r_months = pd.DatetimeIndex(sorted(Dr.t.unique())) + pd.offsets.MonthEnd(1)
        pf, pfr = all_pf.loc[e_months], all_pf.loc[r_months]
        ew, ewr = all_ew.loc[e_months], all_ew.loc[r_months]
        spy_continuous = spy_for(all_pf.index).net
        se, n = nw_se(ic.values)
        same, y = year_same_sign(ic)
        y.index = [f'eval_{i}' for i in y.index]
        yr_r = icr.groupby(icr.index.year).mean() if len(icr) else pd.Series(dtype=float)
        yr_r.index = [f'retro_{i}' for i in yr_r.index]
        yearly[name] = pd.concat([y, yr_r])          # labels distinct (2019 occurs in both eval and retro)
        e_months = pf.index
        rec = {'family': fam, 'combo': name, 'eval_months': n, 'IC_mean': ic.mean(), 't_NW': ic.mean() / se,
               'years_same_sign': same, 'top10_net_ann': ann(pf.net), 'EW_universe_ann': ann(ew.reindex(e_months)),
               'SPY_net_ann': ann(spy_continuous.loc[e_months]),
               'top10_minus_EW_ann': ann(pf.net) - ann(ew.reindex(e_months)), 'turnover_mean': pf.turnover.mean(),
               'retro_IC_2020_2026': icr.mean() if len(icr) else np.nan,
               'retro_top10_minus_EW_ann': (ann(pfr.net) - ann(ewr.reindex(pfr.index))) if len(pfr) else np.nan,
               'EW_cost_basis': '10bp per side, actual drifted turnover; continuous evaluation-to-retrospective ledger'}
        if extra:
            rec.update(extra)
        rows.append(rec)
        safe = ''.join(c if c.isalnum() else '_' for c in name)
        pd.concat([pf.assign(period='eval'), pfr.assign(period='retro')]).to_csv(os.path.join(OUT, f'monthly_{safe}.csv'))
        return ic

    # A
    icA = {}
    for name, items in CLASSIC.items():
        sc = composite(X, items)
        icA[name] = evaluate('A 经典组合', name, sc, dev.values)
    pA, _ = romano_wolf(pd.DataFrame(icA))
    print('family A done', flush=True)
    # B
    icB, lasso_info = {}, {}
    for mdl in ['ridge', 'lasso', 'lgbm']:
        pred, chosen = walk_forward(X, mdl, range(2013, 2027))
        lasso_info[mdl] = chosen
        mask = ((X.t.dt.year >= 2013) & (X.t <= DEV[1])).values
        icB[f'B {mdl}'] = evaluate('B 机器学习（47 因子）', f'B {mdl}', pred, mask)
        print('  model', mdl, 'done', flush=True)
    pB, _ = romano_wolf(pd.DataFrame(icB))
    print('family B done; lasso alpha/#factors by year:', lasso_info['lasso'], flush=True)
    # C
    # The 2015-12 label finishes at the first 2016 test formation; purge it.
    S = X[known_training_mask(X.t, pd.Timestamp('2016-01-31'))]
    top = pair_search(S)
    top.head(30).to_csv(os.path.join(OUT, 'pair_search_top.csv'), index=False)
    test_mask = ((X.t >= pd.Timestamp('2016-01-31')) & (X.t <= DEV[1])).values
    icC, names_C = {}, []
    for r in top.head(10).itertuples():
        sign = 1 if r.t > 0 else -1
        name = f'C {r.B_signal}{"(+)" if sign > 0 else "(−)"} | {r.A_condition_top30} 前30%'
        sc = pair_score(X, r.A_condition_top30, r.B_signal, sign)
        icC[name] = evaluate('C 交互（搜索 2010–15，检验 2016–19）', name, sc, test_mask,
                             {'search_t_2010_2015': r.t})
        names_C.append(name)
    from scipy.stats import norm
    tC = {k: v.mean() / nw_se(v.values)[0] for k, v in icC.items()}
    rawC = {k: 2 * (1 - norm.cdf(abs(v))) for k, v in tC.items()}
    holm, prev = {}, 0.0
    for i, k in enumerate(sorted(rawC, key=rawC.get)):
        prev = max(prev, min(1.0, (len(rawC) - i) * rawC[k]))
        holm[k] = prev
    print('family C done', flush=True)
    T = pd.DataFrame(rows)
    adj = {**pA.to_dict(), **{k: float(v) for k, v in pB.items()}, **holm}   # pB is keyed by 'B ridge' etc.
    T['p_adjusted'] = T.combo.map(adj)

    def verdict(r):
        if r.p_adjusted < 0.05 and r.years_same_sign >= 0.7 and r.top10_minus_EW_ann > 0:
            return '有用'
        if abs(r.t_NW) < 1.5 or r.top10_minus_EW_ann < 0:
            return '没用'
        return '不确定'
    T['verdict'] = T.apply(verdict, axis=1)
    T.to_csv(os.path.join(OUT, 'combo_table.csv'), index=False)
    pd.DataFrame(yearly).T.to_csv(os.path.join(OUT, 'yearly_ic.csv'))
    pd.set_option('display.width', 250)
    show = T[['family', 'combo', 'verdict', 'IC_mean', 't_NW', 'p_adjusted', 'years_same_sign', 'top10_net_ann',
              'EW_universe_ann', 'top10_minus_EW_ann', 'retro_IC_2020_2026', 'retro_top10_minus_EW_ann']].copy()
    print(show.round(3).to_string(index=False))
    print('\nverdicts:', T.verdict.value_counts().to_dict())


if __name__ == '__main__':
    main()
