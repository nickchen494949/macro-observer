#!/usr/bin/env python3
"""
winners_holdout.py — the ONE-SHOT small/mid-cap exam of the frozen candidates (WINNERS_SPEC.md §4, §5, §5a;
candidates in results/winners/candidates.json, frozen in git before this file existed).

  python3 winners_holdout.py prep    # prices → monthly P / segments, universe, features (prints coverage only)
  python3 winners_holdout.py run     # runs the frozen candidates ONCE and writes results/winners_holdout/

Candidates are run with their frozen definitions:
  BENCH pure momentum top-1   : highest 12-1 momentum in the universe, 1 stock, monthly
  T3 mom top-5 ew +crash      : top-5 12-1 momentum, equal weight, exposure halved when SPY 24-m return < 0 and SPY
                                3-m vol > its 5-y median (same SPY signal as on S&P)
  T2 S1 top-5 hold1m / hold6m : the track-2 LightGBM P(explosive) models trained on the S&P panel exactly as in
                                winners_tracks.py (test year Y, training formations <= (Y-1)-06-30), applied to this
                                universe's features (ranked within the month inside this universe). Fundamentals only
                                for securities mapped to an SEC CIK (S&P store cik_map, or SEC current ticker list
                                for Yahoo-confirmed listings) were planned, but §5b sets ALL fundamentals missing in the
                                holdout (having fundamentals = survived / joined the S&P later → look-ahead); price factors only.
Primary window: holding months 2010-01 … 2018-02. Secondary: 2018-03 … 2026-09 (survivorship gap; stress: a held
stock whose price series ends without a delisting record is charged −30 % / −100 % in its last month).
"""
import glob, json, os, shutil, sys

import numpy as np
import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data', 'smallcap')
OUT = os.path.join(HERE, 'results', 'winners_holdout')
os.makedirs(OUT, exist_ok=True)
PRIMARY = ('2010-01-31', '2018-02-28')
SECONDARY = ('2018-03-31', '2026-09-30')


def segments(A):
    seg = {}
    for s in A.columns:
        x = A[s].dropna()
        if x.empty:
            continue
        gaps = np.r_[0, (np.diff(x.index.values).astype('timedelta64[D]').astype(int) > 30).cumsum()]
        seg[s] = pd.Series(gaps.astype(float), index=x.index)
    return pd.DataFrame(seg).reindex(index=A.index, columns=A.columns)


def monthly(A, mkt):
    P = A.resample('ME').last().where(A.resample('ME').count() > 0)
    obs = pd.DataFrame(np.where(A.notna().values, A.index.values[:, None], np.datetime64('NaT')), index=A.index, columns=A.columns)
    last_obs = obs.resample('ME').max()
    mkt_last = mkt.dropna().index.to_series().resample('ME').max()
    fresh = last_obs.ge(mkt_last - pd.Timedelta(days=7), axis=0)
    return P.where(fresh.reindex(index=P.index, columns=P.columns).fillna(False))


def load(form):
    A = pd.read_parquet(os.path.join(D, 'daily_adj.parquet'))
    DV = pd.read_parquet(os.path.join(D, 'daily_dv.parquet'))
    CL = pd.read_parquet(os.path.join(D, 'daily_close_raw.parquet'))
    src = pd.read_csv(os.path.join(D, 'price_source.csv'), index_col=0).source
    daily_sp = bt.load_prices()[0]                              # also sets bt.SEG_D for the S&P store
    seg_sp = bt.SEG_D
    spy = daily_sp['SPY']
    A = A.reindex(A.index.union(spy.dropna().index)).sort_index()
    A = A[A.index >= '2007-01-01']
    A['SPY'] = spy
    DV = DV.reindex(index=A.index)
    CL = CL.reindex(index=A.index)
    seg = segments(A)
    for s in A.columns:                                         # S&P store names keep their audited segment ids
        if src.get(s) == 'sp_store' and s in seg_sp.columns:
            seg[s] = seg_sp[s].reindex(A.index)
    P = monthly(A, spy)
    bt.SEG_D = seg
    bt.SEG_M = seg.resample('ME').last().reindex(P.index)
    bt.WIKI_SYMS = {s for s in A.columns if src.get(s) == 'wiki' and A[s].last_valid_index() is not None
                    and abs((A[s].last_valid_index() - pd.Timestamp('2018-03-27')).days) <= 5}
    bt.PRICE_SOURCE = src.to_dict()
    raw, _ = bt.load_membership(form)
    from smallcap_universe import universe
    U = universe(A.drop(columns=['SPY']), DV.drop(columns=['SPY'], errors='ignore'), raw, form, CL.ffill(limit=5))
    mom = bt.momentum(P, 12)
    U = {t: [s for s in v if s in mom.columns and np.isfinite(mom.at[t, s])] for t, v in U.items()}
    return A, P, U, mom, src


def prep():
    form = pd.date_range('2009-12-31', '2026-08-31', freq='ME')
    A, P, U, mom, src = load(form)
    n = pd.Series({t: len(v) for t, v in U.items()})
    print('eligible universe (with 12-1 momentum): median', int(n.median()), '| by year', n.resample('YE').median().astype(int).to_dict())
    held_src = pd.Series([src.get(s) for v in U.values() for s in v]).value_counts(normalize=True).round(3).to_dict()
    print('price source share of eligible stock-months:', held_src)


# ───────────── features for the track-2 model (same 47 factors; missing where not computable) ─────────────
def cik_map(src):
    """ticker → [(cik, valid_from)] for securities whose price series is identity-confirmed for that filer."""
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    out = {t.replace('.', '-'): [(int(c), None)] for t, c in zip(cm.ticker, cm.cik)}
    j = json.load(open(os.path.join(HERE, 'data', 'sec_company_tickers_exchange.json')))
    ex = pd.DataFrame(j['data'], columns=j['fields'])
    ex['ysym'] = ex.ticker.str.replace('.', '-', regex=False)
    first = {}
    ydir = os.path.join(HERE, 'data', 'raw_smallcap')
    for r in ex.itertuples():
        s = r.ysym
        if s in out or src.get(s) not in ('yahoo', 'wiki|yahoo'):
            continue
        vf = None
        if src.get(s) == 'wiki|yahoo':                    # the WIKI part is a different company → CIK only for Yahoo part
            w = pd.read_parquet(os.path.join(HERE, 'data', 'wiki_bulk', 'wiki_prices.parquet'), filters=[('ticker', '==', s)])
            vf = w.date.max() + pd.Timedelta(days=31)
        out[s] = [(int(r.cik), vf)]
    return out


def build_fundamentals(tmap):
    import build_fundamentals as bf
    F = os.path.join(HERE, 'data', 'fundamentals_smallcap')
    os.makedirs(os.path.join(F, 'pit_long'), exist_ok=True)
    sp_cik = set(pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).cik.dropna().astype(int))
    rows = [(t, c) for t, v in tmap.items() for c, _ in v if c not in sp_cik]
    cm = pd.DataFrame(rows, columns=['ticker', 'cik']).drop_duplicates('cik')
    cm['sector'] = 'smallcap'
    cm['method'] = 'sec_current_ticker'
    keep = bf.F
    try:
        bf.F = F
        sub = bf.load_raw()
        long = bf.build_long(sub, cm)
        long.drop(columns=['fye']).to_parquet(os.path.join(F, 'pit_long', 'smallcap.parquet'), index=False)
        p = bf.eps_panel(long)
    finally:
        bf.F = keep
    from fundamentals_pit import split_factor_after
    tk = long.drop_duplicates('cik').set_index('cik')[['ticker', 'all_tickers', 'sector']]
    p = p.join(tk, on='cik')
    p['_fac'] = [split_factor_after(t, f) if isinstance(t, str) and pd.notna(f) else np.nan
                 for t, f in zip(p.ticker, p.filed_eps_diluted if 'filed_eps_diluted' in p else p.filed)]
    for f in ['eps_diluted_approx', 'eps_basic_approx']:
        if f in p:
            p[f + '_adj'] = p[f] / p['_fac']
            g = p.groupby('cik')
            roll = g[f + '_adj'].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
            span = (p.ddate - g.ddate.shift(3)).dt.days
            p[f + '_ttm_adj'] = roll.where(span.between(250, 290))
    p = p.drop(columns=['_fac']).rename(columns={'ddate': 'period_end'})
    p.to_parquet(os.path.join(F, 'eps_quarterly_pit.parquet'), index=False)
    print('small/mid fundamentals: CIKs requested', cm.cik.nunique(), '| with SEC data', p.cik.nunique(), flush=True)
    return F


def features(A, P, U, form, src):
    import ml_features as mlf
    import explosive_factors as ef
    import factor_screen as fs
    pf, pxm = mlf.price_features(A, P, form)
    smooth, _, _ = ef.price_extras(A, P, form)
    tmap = cik_map(src)
    Fdir = build_fundamentals(tmap)
    root = os.path.join(HERE, 'data', '_smallcap_scratch')
    shutil.rmtree(root, ignore_errors=True)
    fd = os.path.join(root, 'data', 'fundamentals')
    os.makedirs(os.path.join(fd, 'pit_long'))
    a = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'))
    b = pd.read_parquet(os.path.join(Fdir, 'eps_quarterly_pit.parquet'))
    pd.concat([a, b[~b.cik.isin(set(a.cik.dropna()))]], ignore_index=True).to_parquet(os.path.join(fd, 'eps_quarterly_pit.parquet'), index=False)
    for d_ in [os.path.join(HERE, 'data', 'fundamentals', 'pit_long'), os.path.join(Fdir, 'pit_long')]:
        for f in os.listdir(d_):
            os.symlink(os.path.join(d_, f), os.path.join(fd, 'pit_long', os.path.basename(d_.rstrip('/').split('/')[-2]) + '_' + f))
    keep = (mlf.HERE, ef.HERE, fs.HERE)
    try:
        mlf.HERE = ef.HERE = fs.HERE = root
        Fp = mlf.fundamental_panel(form).set_index(['t', 'cik'])
        Q = ef.quarterly_factors(form).set_index(['cik', 't'])
        rows = [(t, s) for t in form for s in U.get(t, [])]
        G = pd.DataFrame(rows, columns=['t', 'ticker'])
        G['cik'] = [next((c for c, vf in tmap.get(s, []) if vf is None or t >= vf), np.nan) for t, s in zip(G.t, G.ticker)]
        N = fs.build_new(G.dropna(subset=['cik']))
    finally:
        mlf.HERE, ef.HERE, fs.HERE = keep
        shutil.rmtree(root, ignore_errors=True)
    X = G.copy()
    for k in ['dist_sma200', 'dist_sma50', 'dist_52wh', 'vol_3m', 'vol_12m', 'beta_12m', 'maxret_1m', 'mom_12_1', 'mom_6_1',
              'mom_3_1', 'rev_1m']:
        X[k] = [pf[k].at[t, s] if s in pf[k].columns else np.nan for t, s in zip(X.t, X.ticker)]
    X['smooth'] = [smooth.at[t, s] if s in smooth.columns else np.nan for t, s in zip(X.t, X.ticker)]
    X['mom_accel'] = X.mom_3_1 - X.mom_12_1 * 3 / 11
    for k in ['mom_12_1_secrel', 'sector_mom', 'ear', 'ear_sum4']:
        X[k] = np.nan                                         # no sector / no earnings dates for the holdout universe
    fcols = ['eps_g', 'eps_g_m5', 'eps_g_sym', 'margin', 'margin_chg', 'rev_g', 'sue']
    for k in fcols + ['deps_p', 'ep', 'log_mcap']:
        X[k] = np.nan
    ok = [(t, c) in Fp.index if pd.notna(c) else False for t, c in zip(X.t, X.cik)]
    for i in np.where(ok)[0]:
        t, s, c = X.t.iat[i], X.ticker.iat[i], int(X.cik.iat[i])
        f = Fp.loc[(t, c)]
        price = pxm.at[t, s] if s in pxm.columns else np.nan
        for k in fcols:
            X.iat[i, X.columns.get_loc(k)] = f[k]
        if price and price > 0:
            X.iat[i, X.columns.get_loc('deps_p')] = f['deps'] / price
            X.iat[i, X.columns.get_loc('ep')] = f['eps_diluted_approx_ttm_adj'] / price
            sh = f['diluted_shares_adj']
            if np.isfinite(sh) and sh > 0:
                X.iat[i, X.columns.get_loc('log_mcap')] = np.log(sh * price)
    for k in ['eps_accel', 'rev_g_q', 'rev_accel', 'gm_chg', 'rd_int']:
        X[k] = [Q.at[(int(c), t), k] if pd.notna(c) and (int(c), t) in Q.index else np.nan for t, c in zip(X.t, X.cik)]
    N['cik'] = N.cik.astype(float)
    X = X.merge(N, on=['t', 'cik'], how='left')
    mcap = np.exp(X.log_mcap)
    X['sp'] = X.revenue_ttm / mcap
    X['bm'] = X.equity / mcap
    X['div_yield'] = X['div'] / mcap
    X['buyback_yield'] = X.rep / mcap
    X['cfo_yield'] = X.cfo / mcap
    X = X.drop(columns=['revenue_ttm', 'equity', 'div', 'rep', 'cfo'])
    # WINNERS_SPEC §5b: whether a small/mid stock HAS fundamentals reveals its future (still listed today / future S&P
    # member) → every fundamental factor is set missing for the whole holdout universe; only price factors remain
    price_cols = ['mom_12_1', 'mom_6_1', 'mom_3_1', 'rev_1m', 'mom_accel', 'smooth', 'dist_sma200', 'dist_sma50',
                  'dist_52wh', 'vol_3m', 'vol_12m', 'beta_12m', 'maxret_1m']
    for k in fs.FACTORS:
        if k not in price_cols:
            X[k] = np.nan
    X.to_parquet(os.path.join(OUT, 'features_holdout.parquet'), index=False)
    cov = X[fs.FACTORS].notna().mean().round(3)
    print('feature coverage in the holdout universe:', cov.to_dict(), flush=True)
    return X


def t2_scores(Xh):
    """Track-2 scores from LightGBM trained on the S&P panel exactly as in winners_tracks.track2 (test years 2013-2026,
    training formations <= (Y-1)-06-30): S1 = P(explosive6), S2 = P(explosive6) − P(bust6)."""
    import lightgbm as lgb
    from factor_screen import FACTORS, ranked
    X = pd.read_parquet(os.path.join(HERE, 'results', 'factor_screen', 'panel_screen.parquet'))
    E = pd.read_parquet(os.path.join(HERE, 'results', 'explosive', 'panel_explosive_ear.parquet'), columns=['t', 'ticker', 'fwd6', 'explosive6'])
    X = X.merge(E, on=['t', 'ticker'], how='left')
    X['bust6'] = (X.groupby('t').fwd6.rank(pct=True) <= 0.05).astype(float).where(X.fwd6.notna())
    R = ranked(X, FACTORS, fill=False).values
    Rh = ranked(Xh, FACTORS, fill=False).values
    yh = Xh.t.dt.year.values
    pe, pb = np.full(len(Xh), np.nan), np.full(len(Xh), np.nan)
    for Y in range(2013, 2027):
        te = yh == Y
        tr = (X.t <= pd.Timestamp(f'{Y-1}-06-30')).values & X.explosive6.notna().values
        if not te.any():
            continue
        for lab, arr in (('explosive6', pe), ('bust6', pb)):
            m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=31, min_child_samples=200,
                                   subsample=0.8, subsample_freq=1, random_state=7, verbose=-1)
            m.fit(R[tr], X[lab].values[tr].astype(int))
            arr[te] = m.predict_proba(Rh[te])[:, 1]
    return pd.Series(pe, index=Xh.index), pd.Series(pe - pb, index=Xh.index)


class _Elig:
    """adapter so winners_tracks.track3 can run on the holdout universe"""
    def __init__(self, U, mom):
        self.U, self.mom = U, mom

    def eligible(self, t, look):
        v = self.U.get(t, [])
        return pd.DataFrame({'mom': self.mom.loc[t, v]}, index=pd.Index(v, name='tk')), None


def run():
    lp = os.path.join(HERE, 'data', 'raw_smallcap', '_log.json')
    cand = pd.read_csv(os.path.join(HERE, 'data', 'smallcap_candidates.csv'))
    log = json.load(open(lp)) if os.path.exists(lp) else {}
    missing = [s for s in cand.ysym if s not in log]
    if missing or not log.get('_retry_done'):
        raise SystemExit(f'download not complete (missing {len(missing)}, retry pass done: {bool(log.get("_retry_done"))}) '
                         '— the exam runs once, on the complete data (WINNERS_SPEC §5c.4)')
    fails = [(s, log[s]) for s in cand.ysym if not str(log[s]).startswith('ok')]
    pd.DataFrame(fails, columns=['symbol', 'status']).to_csv(os.path.join(OUT, 'download_failures.csv'), index=False)
    import winners_tracks as wt
    frozen = json.load(open(os.path.join(HERE, 'results', 'winners', 'candidates.json')))['candidates']
    sup_p = os.path.join(HERE, 'results', 'winners', 'candidates_supplementary.json')
    sup = json.load(open(sup_p))['supplementary_candidates'] if os.path.exists(sup_p) else []
    names = ['BENCH pure momentum top-1'] + frozen + [x for x in sup if x not in frozen]
    form = pd.date_range('2009-12-31', '2026-08-31', freq='ME')
    A, P, U, mom, src = load(form)
    Xh = features(A, P, U, form, src)
    Xh['S1'], Xh['S2'] = t2_scores(Xh)
    r = A.pct_change(fill_method=None).where(bt.SEG_D == bt.SEG_D.shift(1))
    S = {'px': bt.Prices(A, P, 0), 'res': bt.load_resolutions(), 'daily': A, 'form': form, 'eng': _Elig(U, mom),
         'vol63': r.rolling(63, min_periods=50).std() * np.sqrt(252),
         'rf': bt.load_rf(pd.date_range('2009-01-31', '2026-10-31', freq='ME'))}
    wt.PERIODS = {'PRIMARY 2010-01..2018-02': PRIMARY, 'PRIMARY from 2013 (T2 starts 2013)': ('2013-01-31', PRIMARY[1]),
                  'SECONDARY 2018-03..2026-09 (survivorship-biased)': SECONDARY}
    rows = []
    for stress_lab, stress in [('base (unknown outcome = 0 %)', None), ('stress −30 %', -0.30), ('stress −100 %', -1.0)]:
        res = {}
        W1 = {t: {bt.rank_desc(mom.loc[t, v]).index[0]: 1.0} for t, v in U.items() if v}
        res['BENCH pure momentum top-1'] = wt.run_weights(S, W1, stress=stress)
        t3 = [n for n in names if n.startswith('T3')]
        if t3:
            res.update(wt.track3(S, stress=stress, only=set(t3)))
        for n in [n for n in names if n.startswith('T2')]:
            _, sc, topn, hold = n.split()
            N = int(topn.split('-')[1])
            W = {}
            for t, g in Xh.dropna(subset=[sc]).groupby('t'):
                top = g.sort_values([sc, 'ticker'], ascending=[False, True]).ticker.head(N).tolist()
                W[t] = {s_: 1 / len(top) for s_ in top}
            res[n] = wt.run_weights(S, W, stress=stress) if hold == 'hold1m' else wt.tranche_ledger(S, W, 6, stress=stress)
        if stress is None:
            WE = {t: {s_: 1 / len(v) for s_ in v} for t, v in U.items() if v}
            res['REF equal-weight holdout universe'] = wt.run_weights(S, WE)
            res['REF SPY'] = wt.run_weights(S, {t: {'SPY': 1.0} for t in form})
        for name, df in res.items():
            if name not in names and not name.startswith('REF'):
                continue
            safe = ''.join(c if c.isalnum() else '_' for c in f'{name} {stress_lab}')
            df.to_csv(os.path.join(OUT, f'monthly_{safe}.csv'))
            for rec in wt.stats_block(S, df, name):
                rec['scenario'] = stress_lab
                rec['list'] = ('benchmark' if name.startswith('BENCH') else 'frozen' if name in frozen
                               else 'supplementary (post-hoc)' if name in sup else 'reference')
                rows.append(rec)
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, 'summary.csv'), index=False)
    v = T.copy()
    v['v'] = (v.CAGR * 100).round(1).astype(str) + '% / ' + v.Sharpe.round(2).astype(str) + ' / ' + (v.maxDD_daily * 100).round(0).astype(str) + '%'
    pd.set_option('display.width', 250)
    print(v.pivot_table(index=['scenario', 'list', 'strategy'], columns='period', values='v', aggfunc='first').to_string())
    print('download failures:', len(fails))
