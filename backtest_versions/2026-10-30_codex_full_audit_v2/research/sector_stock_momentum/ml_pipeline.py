#!/usr/bin/env python3
"""
ml_pipeline.py — walk-forward ML stock picking, following ML_SPEC.md exactly.

  python3 ml_pipeline.py dev       # stage 1: development walk-forward 2014-01..2022-12, choose model + rule,
                                   #          write results/ml/selection.json  (commit BEFORE stage 2)
  python3 ml_pipeline.py holdout   # stage 2: frozen choice, holdout 2023-01..2026-09, run once
"""
import json, os, sys

import numpy as np
import pandas as pd

import backtest as bt
from legacy_portfolio import run_portfolio, score_basket

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'ml')
FEATS = ['mom_12_1', 'mom_6_1', 'mom_3_1', 'rev_1m', 'mom_12_1_secrel', 'sector_mom', 'dist_sma200', 'above_sma200',
         'dist_sma50', 'dist_52wh', 'vol_3m', 'vol_12m', 'beta_12m', 'maxret_1m', 'eps_g', 'eps_g_m5', 'eps_g_sym',
         'deps_p', 'ep', 'sue', 'margin', 'margin_chg', 'rev_g', 'log_mcap', 'days_since_filing']
FUND = ['eps_g', 'eps_g_m5', 'eps_g_sym', 'deps_p', 'ep', 'sue', 'margin', 'margin_chg', 'rev_g', 'log_mcap',
        'days_since_filing']
COMPOSITE = ['mom_12_1', 'eps_g_m5', 'deps_p', 'sue', 'ep', 'dist_52wh']
MODELS = ['mom', 'composite', 'ridge', 'lgbm_s', 'lgbm_m', 'lgbm_rank']
RULES = ['top1', 'top1_sma200']
DEV = (pd.Timestamp('2014-01-31'), pd.Timestamp('2022-12-31'))      # holding months used for selection
HOLD = (pd.Timestamp('2023-01-31'), pd.Timestamp('2026-09-30'))
TRAIN_START = pd.Timestamp('2010-12-31')                              # first formation used for training
SEED = 7


def load_panel():
    X = pd.read_parquet(os.path.join(OUT, 'panel.parquet'))
    X['hold'] = X.t + pd.offsets.MonthEnd(1)
    R = X[['t']].copy()
    for f in FEATS:                                   # cross-sectional percentile ranks, centred on 0
        R[f] = X.groupby('t')[f].rank(pct=True) - 0.5
    X = pd.concat([X, R.drop(columns='t').add_prefix('r_')], axis=1)
    X['has_fund'] = X[FUND].notna().any(axis=1).astype(float)
    return X


def fit_predict(model, train, test):
    rf = ['r_' + f for f in FEATS]
    if model == 'mom':
        return test['r_mom_12_1'].fillna(-1).values
    if model == 'composite':
        return test[['r_' + f for f in COMPOSITE]].mean(axis=1, skipna=True).fillna(-1).values
    if model == 'ridge':
        from sklearn.linear_model import Ridge
        cols = rf + ['has_fund']
        m = Ridge(alpha=10.0).fit(train[cols].fillna(0).values, train.fwd_rank.values - 0.5)
        return m.predict(test[cols].fillna(0).values)
    import lightgbm as lgb
    if model in ('lgbm_s', 'lgbm_m'):
        p = dict(objective='regression', learning_rate=0.03, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1,
                 seed=SEED, verbose=-1, deterministic=True, num_threads=4,
                 num_leaves=15 if model == 'lgbm_s' else 31, min_data_in_leaf=200 if model == 'lgbm_s' else 100)
        m = lgb.train(p, lgb.Dataset(train[rf].values, train.fwd_rank.values),
                      num_boost_round=300 if model == 'lgbm_s' else 500)
        return m.predict(test[rf].values)
    if model == 'lgbm_rank':
        tr = train.sort_values('t')
        lab = (tr.fwd_rank * 10).clip(0, 9.999).astype(int).values
        grp = tr.groupby('t').size().values
        p = dict(objective='lambdarank', learning_rate=0.03, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.7,
                 bagging_fraction=0.8, bagging_freq=1, seed=SEED, verbose=-1, deterministic=True, num_threads=4,
                 lambdarank_truncation_level=20)
        m = lgb.train(p, lgb.Dataset(tr[rf].values, lab, group=grp), num_boost_round=300)
        return m.predict(test[rf].values)
    raise ValueError(model)


def walk_forward(X, model, years):
    """Refit each January; training = formations from TRAIN_START whose label is known (formation ≤ prior month-end)."""
    out = []
    for y in years:
        test = X[X.hold.dt.year == y]
        if test.empty:
            continue
        first_form = test.t.min()
        train = X[(X.t >= TRAIN_START) & (X.hold <= first_form) & X.fwd_rank.notna()]
        # label of formation s is known at s+1 ≤ first_form  ⇔  s < first_form
        test = test.copy()
        test['score'] = fit_predict(model, train, test)
        out.append(test)
    return pd.concat(out)


def portfolio(S, rule, rf):
    def target(g):
        g = g.dropna(subset=['score'])
        g = g if rule == 'top1' else g[g.dist_sma200 > 0]
        if g.empty:
            return {}
        pick = g.sort_values(['score', 'ticker'], ascending=[False, True]).ticker.iloc[0]
        return {pick: 1.0}
    return run_portfolio(S, target, rf)


def topn(S, n, rf):
    return score_basket(S, 'score', n, rf).net


def ic_series(S):
    S = S[S.fwd_rank.notna()]
    return S.groupby('t').apply(lambda g: g.score.rank().corr(g.fwd_ret.rank()))


def summarize(r, rf, spy=None):
    s = bt.stats(r, rf, spy)
    return {k: s.get(k) for k in ['months', 'CAGR', 'Sharpe', 'vol', 'maxDD_month_end', 'alpha_ann', 'alpha_t_NW']}


def main(stage):
    X = load_panel()
    form_all = sorted(X.t.unique())
    hold = pd.DatetimeIndex(form_all) + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    if stage not in ('dev', 'holdout'):
        raise ValueError('stage must be dev or holdout')
    if stage == 'dev':
        years = range(DEV[0].year, DEV[1].year + 1)
        res, preds = {}, {}
        for m in MODELS:
            S = walk_forward(X, m, years)
            preds[m] = S
            ic = ic_series(S)
            res[m] = {'mean_IC': float(ic.mean()), 'IC_t': float(ic.mean() / ic.std() * np.sqrt(len(ic))),
                      'months': int(len(ic))}
            for rule in RULES:
                pf = portfolio(S, rule, rf)
                pf.to_csv(os.path.join(OUT, f'dev_{m}_{rule}.csv'))
                res[m][rule] = summarize(pf.net.loc[DEV[0]:DEV[1]], rf)
            for n in (5, 20):
                pf = score_basket(S, 'score', n, rf)
                pf.to_csv(os.path.join(OUT, f'dev_{m}_top{n}.csv'))
                res[m][f'top{n}'] = summarize(pf.net.loc[DEV[0]:DEV[1]], rf)
            print(m, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res[m].items() if not isinstance(v, dict)}),
                  '| top1 Sharpe', round(res[m]['top1']['Sharpe'], 2), 'sma200', round(res[m]['top1_sma200']['Sharpe'], 2),
                  '| top20 Sharpe', round(res[m]['top20']['Sharpe'], 2), flush=True)
        best = max(MODELS, key=lambda m: res[m]['mean_IC'])
        rule = max(RULES, key=lambda r: res[best][r]['Sharpe'])
        # deflated Sharpe over the 12 model × rule combinations (monthly SR)
        from scipy.stats import norm
        srs = np.array([res[m][r]['Sharpe'] / np.sqrt(12) for m in MODELS for r in RULES])
        N, T = len(srs), res[best][rule]['months']
        emc = 0.5772156649
        sr0 = np.sqrt(srs.var(ddof=1)) * ((1 - emc) * norm.ppf(1 - 1 / N) + emc * norm.ppf(1 - 1 / (N * np.e)))
        chosen_r = portfolio(preds[best], rule, rf).net.loc[DEV[0]:DEV[1]]
        dsr, _, _ = bt.deflated_sharpe(chosen_r - rf.reindex(chosen_r.index), srs, T)
        sel = {'chosen_model': best, 'chosen_rule': rule, 'selection_metric': 'mean monthly Spearman IC, dev 2014-2022',
               'deflated_sharpe_prob_chosen_dev': dsr, 'dev_results': res,
               'audit_status': 'corrected retrospective rerun; independently review before approval',
               'limitations': ['Close at formation is an idealised execution assumption',
                               'DSR counts only the frozen 12 primary trials, not all previous research',
                               'Source/terminal unknown outcomes remain baseline assumptions, not certified prices']}
        json.dump(sel, open(os.path.join(OUT, 'selection.json'), 'w'), indent=1, default=float)
        if best.startswith('lgbm'):
            import lightgbm as lgb  # noqa — importance of the chosen model fitted on all dev data
        print('\nCHOSEN:', best, rule, '| deflated Sharpe prob (12 trials):', round(dsr, 3))
        return
    # ── stage 2: holdout, frozen choice ──
    sel = json.load(open(os.path.join(OUT, 'selection.json')))
    best, rule = sel['chosen_model'], sel['chosen_rule']
    years = range(HOLD[0].year, HOLD[1].year + 1)
    out = {}
    # User requested all existing candidates. These are transparent retrospective
    # diagnostics; they do not change the development-only chosen model/rule.
    for m in MODELS:
        S = walk_forward(X, m, years)
        ic = ic_series(S)
        out[m] = {'mean_IC': float(ic.mean()), 'IC_t': float(ic.mean() / ic.std() * np.sqrt(len(ic)))}
        for r in RULES:
            pf = portfolio(S, r, rf)
            pf.to_csv(os.path.join(OUT, f'holdout_{m}_{r}.csv'))
            out[m][r] = summarize(pf.net.loc[HOLD[0]:HOLD[1]], rf)
        for n in (5, 20):
            pf = score_basket(S, 'score', n, rf)
            pf.to_csv(os.path.join(OUT, f'holdout_{m}_top{n}.csv'))
            out[m][f'top{n}'] = summarize(pf.net.loc[HOLD[0]:HOLD[1]], rf)
    json.dump({'chosen': [best, rule], 'holdout': out, 'status': 'retrospective; not untouched holdout'},
              open(os.path.join(OUT, 'holdout.json'), 'w'), indent=1, default=float)
    for m, v in out.items():
        print(m, 'IC', round(v['mean_IC'], 4), 't', round(v['IC_t'], 2), '|',
              ' | '.join(f"{k}: {v[k]['CAGR']*100:.1f}%/{v[k]['Sharpe']:.2f}/{v[k]['maxDD_month_end']*100:.0f}%"
                         for k in RULES + ['top5', 'top20']))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'dev')
