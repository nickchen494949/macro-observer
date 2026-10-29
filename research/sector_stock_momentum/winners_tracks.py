#!/usr/bin/env python3
"""
winners_tracks.py — WINNERS_SPEC.md tracks 3 (risk-controlled momentum) and 2 (predict explosive stocks), S&P 500.

  python3 winners_tracks.py      → results/winners/summary.csv, monthly_*.csv, candidates.json
"""
import json, os

import numpy as np
import pandas as pd

import backtest as bt
from factor_screen import FACTORS, ranked

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'winners')
os.makedirs(OUT, exist_ok=True)
PERIODS = {'2010-2019': ('2010-01-31', '2019-12-31'), '2013-2019': ('2013-01-31', '2019-12-31'),
           '2020-2026.09': ('2020-01-31', '2026-09-30'), 'full 2010-2026.09': ('2010-01-31', '2026-09-30')}


def setup():
    daily, P, aliases, bad = bt.load_prices()
    form = P.index[(P.index >= pd.Timestamp('2009-12-31')) & (P.index <= pd.Timestamp('2026-08-31'))]
    raw, _ = bt.load_membership(form)
    members = {t: {x for x in m if not any(a <= t <= b for a, b in bad.get(x, []))} for t, m in raw.items()}
    secP, _ = bt.build_panel(bt.build_sector_table(aliases), form)
    eng = bt.Engine(P, daily, members, secP, form)
    px = bt.Prices(daily, P, 0)
    res = bt.load_resolutions()
    rf = bt.load_rf(pd.date_range('2009-01-31', '2026-10-31', freq='ME'))
    r = daily.pct_change(fill_method=None)
    seg = bt.SEG_D.reindex(index=daily.index, columns=daily.columns)
    r = r.where(seg == seg.shift(1))
    vol63 = r.rolling(63, min_periods=50).std() * np.sqrt(252)
    return dict(daily=daily, P=P, form=form, eng=eng, px=px, res=res, rf=rf, ret_d=r, vol63=vol63)


def last_session(daily, t):
    return daily.index[daily.index.searchsorted(t, side='right') - 1]


# ───────────── generic portfolio engine (weights per month, exposure, costs, daily NAV) ─────────────
def run_weights(S, W, exposure=None, cap_cost=0.0, label='', stress=None):
    """W: {formation t: {ticker: weight}} (weights sum to 1); exposure: {t: e} (0 … 1.5); cash earns T-bill,
    borrowing (e > 1) pays T-bill + 1 %/yr. Returns monthly frame (net, gross, turnover, exposure, picks)."""
    px, res, rf = S['px'], S['res'], S['rf']
    rows, w_prev = [], {}
    for t in sorted(W):
        w = W[t]
        e = 1.0 if exposure is None else float(exposure.get(t, 1.0))
        m = t + pd.offsets.MonthEnd(1)
        rfm = float(rf.get(m, 0))
        rets = {s: px.ret(t, s, res) for s in w}
        if stress is not None:                              # unknown outcome (no quote after purchase) → stress return
            rets = {s: ((stress, st) if st in ('unresolved', 'source_gap') else (r_, st)) for s, (r_, st) in rets.items()}
        r_stk = sum(w[s] * rets[s][0] for s in w) if w else 0.0
        target = {s: w[s] * e for s in w}
        turn = sum(abs(target.get(s, 0) - w_prev.get(s, 0)) for s in set(target) | set(w_prev))
        cash = 1 - e
        gross = e * r_stk + (cash * rfm if cash > 0 else cash * (rfm + 0.01 / 12))
        net = gross - turn * bt.COST_PER_SIDE
        grow = {s: target[s] * (1 + rets[s][0]) for s in w if rets[s][1] == 'ok'}
        w_prev = {s: v / (1 + gross) for s, v in grow.items()} if gross > -1 else {}
        rows.append({'month': m, 'net': net, 'gross': gross, 'turnover': turn, 'exposure': e,
                     'picks': '|'.join(w), 'weights': '|'.join(f'{w[s]:.5f}' for s in w)})
    return pd.DataFrame(rows).set_index('month')


def daily_nav(S, df):
    daily = S['daily']
    out, level = [], 1.0
    for m, row in df.iterrows():
        t0 = last_session(daily, m - pd.offsets.MonthEnd(1))
        days = daily.index[(daily.index > t0) & (daily.index <= m)]
        if not len(days):
            continue
        names = row.picks.split('|') if isinstance(row.picks, str) and row.picks else []
        if names:
            w = np.array([float(x) for x in row.weights.split('|')])
            seg = daily[names].loc[t0:m].ffill()
            # weights may sum to < 1 (cash inside tranches); the cash part has no intra-month price path
            rel = pd.Series(1 + ((seg / seg.iloc[0]).fillna(1.0).values - 1) @ w, index=seg.index).loc[days]
            rel = 1 + row.exposure * (rel - 1)
        elif row.exposure == 0 or abs(row.gross - float(S['rf'].get(m, 0))) < 1e-9 or str(row.get('cash_month', '')) == 'True':
            rel = pd.Series(1.0, index=days)                     # genuinely in cash
        else:
            raise ValueError(f'daily_nav: no holdings recorded for {m} — refusing to invent a smooth path')
        k = (1 + row.net) / rel.iloc[-1]
        path = level * rel * (k ** (np.arange(1, len(rel) + 1) / len(rel)))
        out.append(path)
        level = float(path.iloc[-1])
    return pd.concat(out)


def stats_block(S, df, name):
    rows = []
    nav = daily_nav(S, df)
    for lab, (a, z) in PERIODS.items():
        r = df.net.loc[a:z]
        if len(r) < 12:
            continue
        s = bt.stats(r, S['rf'])
        n = nav.loc[pd.Timestamp(a) - pd.offsets.MonthEnd(1):z]
        n = n / n.iloc[0]
        lr = np.log1p(r)
        y = (1 + r).groupby(r.index.year).prod() - 1
        rows.append({'strategy': name, 'period': lab, 'CAGR': s['CAGR'], 'Sharpe': s['Sharpe'], 'vol': s['vol'],
                     'maxDD_month_end': s['maxDD_month_end'], 'maxDD_daily': float((n / n.cummax() - 1).min()),
                     'losing_years': ','.join(str(k) for k, v in y.items() if v < 0),
                     'best5_months_share': float(lr.nlargest(5).sum() / lr.sum()) if lr.sum() > 0 else np.nan,
                     'avg_exposure': df.exposure.loc[a:z].mean()})
    return rows


def tranche_ledger(S, W, hold=6, stress=None):
    """Overlapping-tranche portfolio with a REAL holdings ledger (external audit 2026-10-29: the old version re-averaged
    tranche returns every month, i.e. silently rebalanced, and its daily NAV had no holdings).
    Month i < hold: 1/(hold−i) of the not-yet-invested cash funds a new tranche; afterwards the tranche that has been held
    `hold` months is sold and its proceeds fund the new tranche (equal value in its top-N stocks). Positions drift with
    their own returns; a stock that stops trading (terminal event) becomes cash inside its tranche (T-bill); idle cash
    earns the T-bill. Costs: 10 bp × value actually sold + bought. Records start-of-month holdings for the daily NAV."""
    px, res, rf = S['px'], S['res'], S['rf']
    months = sorted(W)
    idle, tranches, rows = 1.0, [], []
    for i, t in enumerate(months):
        m = t + pd.offsets.MonthEnd(1)
        rfm = float(rf.get(m, 0))
        nav0 = idle + sum(sum(tr['pos'].values()) + tr['cash'] for tr in tranches)
        traded = 0.0
        if i < hold:
            fund = idle / (hold - i)
            idle -= fund
        else:
            old = tranches.pop(0)
            traded += sum(old['pos'].values())
            fund = sum(old['pos'].values()) + old['cash']
        names = list(W[t])
        traded += fund
        fund -= traded * bt.COST_PER_SIDE
        tranches.append({'pos': {s: fund / len(names) for s in names}, 'cash': 0.0})
        nav_start = idle + sum(sum(tr['pos'].values()) + tr['cash'] for tr in tranches)
        agg = {}
        for tr in tranches:
            for s, v in tr['pos'].items():
                agg[s] = agg.get(s, 0.0) + v
        weights = {s: v / nav_start for s, v in agg.items()}
        for tr in tranches:                                 # one month of returns
            newpos = {}
            for s, v in tr['pos'].items():
                r_, st = px.ret(t, s, res)
                if stress is not None and st in ('unresolved', 'source_gap'):
                    r_ = stress
                if st == 'ok':
                    newpos[s] = v * (1 + r_)
                else:
                    tr['cash'] += v * (1 + r_)              # exited during the month → cash
            tr['pos'] = newpos
            tr['cash'] *= 1 + rfm
        idle *= 1 + rfm
        nav1 = idle + sum(sum(tr['pos'].values()) + tr['cash'] for tr in tranches)
        net = nav1 / nav0 - 1
        gross = nav1 / nav_start * (nav_start / nav0) - 1 + traded * bt.COST_PER_SIDE / nav0
        rows.append({'month': m, 'net': net, 'gross': gross, 'turnover': traded / nav0, 'exposure': 1.0,
                     'picks': '|'.join(weights), 'weights': '|'.join(f'{w:.6f}' for w in weights.values())})
    return pd.DataFrame(rows).set_index('month')


# ───────────── track 3 ─────────────
def track3(S, stress=None, only=None):
    """only: optional set of strategy names to build (holdout exam); stress: return for unknown-outcome exits."""
    daily, form, eng = S['daily'], S['form'], S['eng']
    spy = daily['SPY'].dropna()
    sma = spy.rolling(200).mean()
    spy_r = spy.pct_change()
    v3m = spy_r.rolling(63).std()
    v3m_med5y = v3m.rolling(1260, min_periods=750).median()
    below, crash = {}, {}
    for t in form:
        d = last_session(spy, t)
        below[t] = bool(spy.loc[d] < sma.loc[d])
        i = spy.index.get_loc(d)
        r24 = spy.iloc[i] / spy.iloc[max(0, i - 504)] - 1
        crash[t] = bool(r24 < 0 and v3m.loc[d] > v3m_med5y.loc[d])
    out = {}
    for N in (5, 10, 20):
        for wt in ('ew', 'ivol'):
            W = {}
            for t in form:
                df, _ = eng.eligible(t, 12)
                if df.empty:
                    continue
                top = bt.rank_desc(df.mom).index[:N].tolist()
                if wt == 'ivol':
                    v = S['vol63'].loc[last_session(daily, t), top].clip(lower=0.05).fillna(S['vol63'].loc[last_session(daily, t), top].median())
                    iv = (1 / v)
                    W[t] = (iv / iv.sum()).to_dict()
                else:
                    W[t] = {s: 1 / len(top) for s in top}
            base = f'T3 mom top-{N} {wt}'
            out[base] = run_weights(S, W, stress=stress)
            # daily returns of the base portfolio (for the vol target, known at t)
            nav = daily_nav(S, out[base])
            dr = nav.pct_change()
            expo = {}
            for k, (a, b, c, cap) in {'+market': (1, 0, 0, 1.0), '+crash': (0, 1, 0, 1.0), '+voltarget': (0, 0, 1, 1.0),
                                      '+all': (1, 1, 1, 1.0), '+voltarget lev1.5': (0, 0, 1, 1.5),
                                      '+all lev1.5': (1, 1, 1, 1.5)}.items():
                e = {}
                for t in W:
                    x = 1.0
                    if c:
                        hist = dr.loc[:t].dropna().iloc[-63:]
                        x = min(cap, 0.25 / (hist.std() * np.sqrt(252))) if len(hist) >= 40 else 1.0
                    if b and crash.get(t):
                        x *= 0.5
                    if a and below.get(t):
                        x = 0.0
                    e[t] = x
                if only is None or base + ' ' + k in only:
                    out[base + ' ' + k] = run_weights(S, W, e, stress=stress)
            print('  track 3:', base, 'done', flush=True)
    return out


# ───────────── track 2 ─────────────
def track2(S):
    import lightgbm as lgb
    X = pd.read_parquet(os.path.join(HERE, 'results', 'factor_screen', 'panel_screen.parquet'))
    E = pd.read_parquet(os.path.join(HERE, 'results', 'explosive', 'panel_explosive_ear.parquet'),
                        columns=['t', 'ticker', 'fwd6', 'explosive6'])
    X = X.merge(E, on=['t', 'ticker'], how='left', suffixes=('', '_e'))
    X['bust6'] = (X.groupby('t').fwd6.rank(pct=True) <= 0.05).astype(float).where(X.fwd6.notna())
    R = ranked(X, FACTORS, fill=False).values
    yr = X.t.dt.year.values
    p_exp = np.full(len(X), np.nan)
    p_bust = np.full(len(X), np.nan)
    for Y in range(2013, 2027):
        tr = (X.t <= pd.Timestamp(f'{Y-1}-06-30')).values & X.explosive6.notna().values
        te = yr == Y
        if not te.any():
            continue
        for lab, arr in (('explosive6', p_exp), ('bust6', p_bust)):
            m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=31, min_child_samples=200,
                                   subsample=0.8, subsample_freq=1, random_state=7, verbose=-1)
            m.fit(R[tr], X[lab].values[tr].astype(int))
            arr[te] = m.predict_proba(R[te])[:, 1]
        print('  track 2: test year', Y, 'done', flush=True)
    X['S1'] = p_exp
    X['S2'] = p_exp - p_bust
    X[['t', 'ticker', 'S1', 'S2', 'explosive6', 'bust6']].to_parquet(os.path.join(OUT, 'track2_scores.parquet'), index=False)
    out = {}
    px, res, rf = S['px'], S['res'], S['rf']
    for sc in ('S1', 'S2'):
        for N in (1, 5, 10):
            W = {}
            for t, g in X.dropna(subset=[sc]).groupby('t'):
                top = g.sort_values([sc, 'ticker'], ascending=[False, True]).ticker.head(N).tolist()
                W[t] = {s: 1 / len(top) for s in top}
            out[f'T2 {sc} top-{N} hold1m'] = run_weights(S, W)
            out[f'T2 {sc} top-{N} hold6m'] = tranche_ledger(S, W, 6)
    return out


def main():
    S = setup()
    allres = {}
    allres.update(track3(S))
    allres.update(track2(S))
    ew = S['P'].index  # equal-weight universe and SPY benchmarks
    px = S['px']
    form = S['form']
    W_ew = {}
    for t in form:
        df, _ = S['eng'].eligible(t, 12)
        W_ew[t] = {s: 1 / len(df) for s in df.index}
    allres['BENCH equal-weight S&P members'] = run_weights(S, W_ew)
    allres['BENCH SPY'] = run_weights(S, {t: {'SPY': 1.0} for t in form})
    allres['BENCH pure momentum top-1'] = run_weights(S, {t: {bt.rank_desc(S['eng'].eligible(t, 12)[0].mom).index[0]: 1.0}
                                                         for t in form})
    rows = []
    for name, df in allres.items():
        safe = ''.join(c if c.isalnum() else '_' for c in name)
        df.to_csv(os.path.join(OUT, f'monthly_{safe}.csv'))
        if not df.picks.astype(str).str.len().gt(0).any():
            df = df.assign(picks='', weights='')
        rows += stats_block(S, df, name)
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, 'summary.csv'), index=False)
    # final candidates (WINNERS_SPEC §4): 2010-2019 month-end maxDD better than −50 %, top-3 by 2010-2019 CAGR,
    # at most 2 per family (T2 / T3); benchmarks excluded
    d = T[(T.period == '2010-2019') & ~T.strategy.str.startswith('BENCH') & (T.maxDD_month_end > -0.50)]
    d = d.sort_values('CAGR', ascending=False)
    cand, fam = [], {}
    for r in d.itertuples():
        f = r.strategy.split()[0]
        if fam.get(f, 0) < 2:
            cand.append(r.strategy)
            fam[f] = fam.get(f, 0) + 1
        if len(cand) == 3:
            break
    # the FROZEN candidates (git f2a1e11) are not overwritten by a re-run; a re-run writes candidates_rerun.json
    frozen = os.path.join(OUT, 'candidates.json')
    json.dump({'candidates': cand, 'benchmark': 'BENCH pure momentum top-1', 'rule': 'WINNERS_SPEC §4'},
              open(os.path.join(OUT, 'candidates_rerun.json' if os.path.exists(frozen) else 'candidates.json'), 'w'),
              indent=1, ensure_ascii=False)
    # supplementary list (WINNERS_SPEC §5c): same rule on the COMMON window 2013-2019 (labelled post-hoc)
    d2 = T[(T.period == '2013-2019') & ~T.strategy.str.startswith('BENCH') & (T.maxDD_month_end > -0.50)]
    d2 = d2.sort_values('CAGR', ascending=False)
    sup, fam = [], {}
    for r in d2.itertuples():
        f = r.strategy.split()[0]
        if fam.get(f, 0) < 2:
            sup.append(r.strategy)
            fam[f] = fam.get(f, 0) + 1
        if len(sup) == 3:
            break
    json.dump({'supplementary_candidates': sup, 'rule': 'WINNERS_SPEC §5c (common window 2013-2019; post-hoc)'},
              open(os.path.join(OUT, 'candidates_supplementary.json'), 'w'), indent=1, ensure_ascii=False)
    print('SUPPLEMENTARY CANDIDATES (§5c, post-hoc):', sup)
    pd.set_option('display.width', 250)
    v = T.copy()
    v['v'] = (v.CAGR * 100).round(1).astype(str) + '% / ' + v.Sharpe.round(2).astype(str) + ' / ' + \
        (v.maxDD_daily * 100).round(0).astype(str) + '%'
    print(v.pivot(index='strategy', columns='period', values='v')[list(PERIODS)].to_string())
    print('\nFINAL CANDIDATES (rule §4):', cand)


if __name__ == '__main__':
    main()
