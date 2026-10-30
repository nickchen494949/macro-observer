#!/usr/bin/env python3
"""
ndx_expand.py — do the strategies change when the universe grows from S&P 500 to S&P 500 ∪ Nasdaq-100?

Universe: ndx_universe.setup() (PIT S&P membership ∪ PIT Nasdaq-100 membership, same price/identity/sector rules).
Rules are NOT re-tuned — every strategy is the exact rule already reported for the S&P universe:
  A  SPEC: best 12-1 momentum stock inside the best sector (equal-weight sector momentum), 1 stock     (backtest.py)
  B  pure 12-1 momentum, top-1 stock, no sector filter                                                    (backtest.py)
  C  asymmetric 6-factor composite (log_mcap−, mom_3_1, mom_6_1, dist_sma200, gm_chg, eps_g; >= 4 of 6 present),
     tech top-5 inverse-vol / tech top-5 EW / tech top-1, with and without the XLK 200-day regime filter  (improve_v3.py)
Periods: A/B on holding months 2009-01..2026-09 with the frozen IS/OOS split (IS = first 149 months); C on 2012-01..2026-09
(and 2015-01..2026-09 as in improve_v3). Costs 10 bp per side on actual drifted turnover, before investment.
Sanity check first: the S&P-only universe rebuilt through the union loader must reproduce results/monthly_SPEC.csv.
Output: results/ndx/*
"""
import os, shutil

import numpy as np
import pandas as pd

import backtest as bt
import ndx_universe as nu

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results', 'ndx')
os.makedirs(OUT, exist_ok=True)
from improve_v3 import fixed_factors  # load only after the upstream audited selection has completed


def fmt(s):
    return f"{s['CAGR']*100:.1f}% / {s['Sharpe']:.2f} / {s['maxDD_month_end']*100:.0f}%"


def fundamentals_root():
    """Scratch root whose data/fundamentals/ = S&P store ∪ NDX store, for ml_features / explosive_factors readers."""
    root = os.path.join(OUT, '_union_scratch_fund')
    shutil.rmtree(root, ignore_errors=True)
    fd = os.path.join(root, 'data', 'fundamentals')
    os.makedirs(os.path.join(fd, 'pit_long'))
    a = pd.read_parquet(os.path.join(HERE, 'data', 'fundamentals', 'eps_quarterly_pit.parquet'))
    bp = os.path.join(HERE, 'data', 'fundamentals_ndx', 'eps_quarterly_pit.parquet')
    b = pd.read_parquet(bp) if os.path.exists(bp) else a.iloc[:0]
    b = b[~b.cik.isin(set(a.cik.dropna()))]
    pd.concat([a, b], ignore_index=True).to_parquet(os.path.join(fd, 'eps_quarterly_pit.parquet'), index=False)
    for src in ['fundamentals', 'fundamentals_ndx']:
        d = os.path.join(HERE, 'data', src, 'pit_long')
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            os.symlink(os.path.join(d, f), os.path.join(fd, 'pit_long', f'{src}_{f}'))
    return root


def t2c_map():
    cm = pd.read_csv(os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    out = {t.replace('.', '-'): [(int(c), None, None)] for t, c in zip(cm.ticker, cm.cik)}
    n = pd.read_csv(os.path.join(HERE, 'data', 'ndx_cik_map.csv'), parse_dates=['valid_from', 'valid_to'])
    sp_tk = set(out)
    for r in n.itertuples():
        if r.ticker in sp_tk:
            continue                                        # the S&P store already maps this ticker
        out.setdefault(r.ticker, []).append((int(r.cik), r.valid_from if pd.notna(r.valid_from) else None,
                                             r.valid_to if pd.notna(r.valid_to) else None))
    return out


def cik_at(entries, t):
    matches = {c for c, a, b in entries if (a is None or t >= a) and (b is None or t < b)}
    if len(matches) > 1:
        raise ValueError(f'ambiguous security identity at {t}: {sorted(matches)}')
    return next(iter(matches)) if matches else None


def build_panel(U, form):
    import ml_features as mlf
    import explosive_factors as ef
    daily, P = U['daily'], U['P']
    root = fundamentals_root()
    h_m, h_e = mlf.HERE, ef.HERE
    try:
        mlf.HERE, ef.HERE = root, root
        F = mlf.fundamental_panel(form)
        Q = ef.quarterly_factors(form)
    finally:
        mlf.HERE, ef.HERE = h_m, h_e
        shutil.rmtree(root, ignore_errors=True)
    pf, px = mlf.price_features(daily, P, form)
    smooth, _, _ = ef.price_extras(daily, P, form)
    Fi = F.set_index(['t', 'cik'])
    Qi = Q.set_index(['cik', 't'])
    t2c = t2c_map()
    eng = bt.Engine(P, daily, U['members'], U['secP'], form)
    pr = bt.Prices(daily, P, 0)
    res = bt.load_resolutions()
    rows = []
    for t in form:
        df, _ = eng.eligible(t, 12)
        for s in df.index:
            rec = {'t': t, 'ticker': s, 'sector': df.at[s, 'sector'], 'mom_12_1': df.at[s, 'mom'],
                   'in_sp': s in U['members_sp'].get(t, ()), 'in_ndx': s in U['members_nd'].get(t, ())}
            for k in pf:
                rec[k] = pf[k].at[t, s] if s in pf[k].columns else np.nan
            rec['smooth'] = smooth.at[t, s] if s in smooth.columns else np.nan
            rec['mom_accel'] = rec['mom_3_1'] - rec['mom_12_1'] * 3 / 11
            c = cik_at(t2c.get(s, []), t)
            from fundamentals_pit import cik_valid
            if c is not None and not cik_valid(s, t):
                c = None
            rec['cik'] = c
            if c is not None and (t, c) in Fi.index:
                f = Fi.loc[(t, c)]
                price = px.at[t, s]
                rec.update({k: f[k] for k in ['eps_g', 'eps_g_m5', 'eps_g_sym', 'margin', 'margin_chg', 'rev_g', 'sue']})
                rec['deps_p'] = f['deps'] / price if price and price > 0 else np.nan
                rec['ep'] = f['eps_diluted_approx_ttm_adj'] / price if price and price > 0 else np.nan
                sh = f['diluted_shares_adj']
                rec['log_mcap'] = np.log(sh * price) if np.isfinite(sh) and sh > 0 and price and price > 0 else np.nan
            if c is not None and (c, t) in Qi.index:
                rec.update({k: Qi.at[(c, t), k] for k in ['gm_chg', 'rd_int', 'eps_accel', 'rev_g_q', 'rev_accel']})
            r, st = pr.ret(t, s, res)
            rec['fwd_ret'], rec['exit_status'] = r, st
            rows.append(rec)
    return pd.DataFrame(rows)


def main():
    FIXED = fixed_factors()
    U = nu.setup('2008-12-31', '2026-08-31')
    form = U['form']
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    res = bt.load_resolutions()
    px = bt.Prices(U['daily'], U['P'], 0)
    n_is = int(round(len(hold) * bt.IS_FRAC))
    per = {'IS': (hold[0], hold[n_is - 1]), 'OOS': (hold[n_is], hold[-1]), 'FULL': (hold[0], hold[-1])}

    # ── coverage of the NDX additions ──
    cov = []
    for t in form:
        nd_only = U['members_nd'][t] - U['members_sp'].get(t, set())
        eng_rows = bt.Engine(U['P'], U['daily'], {t: nd_only}, U['secP'], form).eligible(t, 12)[0]
        cov.append({'month_end': t, 'ndx_members': len(U['members_nd'][t]), 'ndx_only_members': len(nd_only),
                    'ndx_only_eligible': len(eng_rows), 'union_members': len(U['members'][t])})
    cov = pd.DataFrame(cov)
    cov.to_csv(os.path.join(OUT, 'coverage_ndx_only.csv'), index=False)
    print('NDX-only members per month (median):', cov.ndx_only_members.median(), '| eligible:', cov.ndx_only_eligible.median())

    # ── sanity: S&P-only through the union loader vs the frozen run ──
    eng_sp = bt.Engine(U['P'], U['daily'], U['members_sp'], U['secP'], form)
    spec_sp = eng_sp.run(bt.SPEC, px, res)
    ref = pd.read_csv(os.path.join(HERE, 'results', 'monthly_SPEC.csv'), parse_dates=['month']).set_index('month')
    j = spec_sp.join(ref[['picks', 'net']], rsuffix='_ref', how='inner')
    same = (j.picks == j.picks_ref).mean()
    print(f'sanity: S&P-only SPEC via union loader — same picks {same:.1%} of {len(j)} months; '
          f'max |net diff| {np.nanmax(np.abs(j.net - j.net_ref)):.2e}')
    j[j.picks != j.picks_ref][['picks', 'picks_ref', 'net', 'net_ref']].to_csv(os.path.join(OUT, 'sanity_sp_only_diffs.csv'))
    if not spec_sp.index.equals(ref.index) or same != 1.0 or not np.allclose(j.net, j.net_ref, rtol=0, atol=1e-12):
        raise RuntimeError('NDX union loader failed mandatory S&P-only reproduction gate; do not publish mixed-universe performance')

    # ── A / B on the union ──
    eng = bt.Engine(U['P'], U['daily'], U['members'], U['secP'], form)
    S = {'A SPEC (S&P only)': spec_sp, 'A SPEC (S&P ∪ NDX)': eng.run(bt.SPEC, px, res),
         'B pure momentum top-1 (S&P only)': eng_sp.run(bt.SPEC, px, res, sector_filter=False),
         'B pure momentum top-1 (S&P ∪ NDX)': eng.run(bt.SPEC, px, res, sector_filter=False)}
    spy = pd.DataFrame({'net': px.nxt['SPY'].reindex(form).values}, index=hold)
    spy.rename_axis('month').to_csv(os.path.join(OUT, 'monthly_SPY_full.csv'))
    qqq_p = os.path.join(HERE, 'data', 'raw', 'QQQ.json')
    rows = []
    for name, df in list(S.items()) + [('SPY', spy)]:
        df.to_csv(os.path.join(OUT, 'monthly_' + ''.join(c if c.isalnum() else '_' for c in name) + '.csv'))
        for lab, (a, z) in per.items():
            stats = bt.stats(df.net.loc[a:z], rf)
            rows.append({'strategy': name, 'period': lab, 'v': fmt(stats),
                         'CAGR': stats['CAGR'], 'Sharpe': stats['Sharpe'], 'maxDD_month_end': stats['maxDD_month_end']})
    for name in ['A SPEC (S&P ∪ NDX)', 'B pure momentum top-1 (S&P ∪ NDX)']:
        df = S[name]
        ndx_only = [any(p not in U['members_sp'].get(f, set()) for p in pk.split('|'))
                    for f, pk in zip(df.formation, df.picks)]
        print(f'{name}: months holding an NDX-only name {np.mean(ndx_only):.1%}; most held:',
              df.picks.value_counts().head(8).to_dict())
    R = pd.DataFrame(rows)
    print(R.pivot(index='strategy', columns='period', values='v')[['IS', 'OOS', 'FULL']].to_string())

    # ── C: 6-factor composite on the union ──
    import improve_v3 as v3
    form_c = form[form >= pd.Timestamp('2011-12-31')]
    X = build_panel(U, form_c)
    X.to_parquet(os.path.join(OUT, 'panel_union.parquet'), index=False)
    X['score'] = v3.score_with(X, FIXED)
    Xs = X[X.in_sp].copy()
    Xs['score'] = v3.score_with(Xs, FIXED)              # S&P-only panel rebuilt the same way (comparison baseline)
    sc = X.groupby('in_sp').score.apply(lambda s: s.notna().mean())
    print('share of eligible rows with a composite score: S&P', round(sc.get(True, np.nan), 3),
          '| NDX-only', round(sc.get(False, np.nan), 3))
    daily = U['daily']
    s = daily['XLK'].dropna()
    sma = s.rolling(200).mean()
    idx = s.index.searchsorted(form_c, side='right') - 1
    below = dict(zip(form_c, s.iloc[idx].values < sma.iloc[idx].values))
    hold_c = form_c + pd.offsets.MonthEnd(1)
    rf_c = bt.load_rf(hold_c)
    from sma200_overlay import run
    pick = lambda g: None if g.dropna(subset=['score']).empty else \
        g.dropna(subset=['score']).sort_values(['score', 'ticker'], ascending=[False, True]).ticker.iloc[0]
    C = {}
    for uni, D in [('S&P only', Xs), ('S&P ∪ NDX', X)]:
        tech = D[D.sector == 'Information Technology']
        tech.attrs['formation_calendar'] = form_c
        D.attrs['formation_calendar'] = form_c
        C[f'C tech top-5 inv-vol ({uni})'] = v3.basket(tech, 'score', 5, rf_c, 'ivol')
        C[f'C tech top-5 EW ({uni})'] = v3.basket(tech, 'score', 5, rf_c)
        C[f'C tech top-1 ({uni})'] = run(tech, pick, rf_c)
        C[f'C all top-5 inv-vol ({uni})'] = v3.basket(D, 'score', 5, rf_c, 'ivol')
    for k in list(C):
        if 'inv-vol' in k and 'tech' in k:
            C[k + ' + XLK regime'] = v3.regime(C[k], below, rf_c)
    C['XLK'] = pd.DataFrame({'net': px.nxt['XLK'].reindex(form_c).values}, index=hold_c)
    C['SPY'] = pd.DataFrame({'net': px.nxt['SPY'].reindex(form_c).values}, index=hold_c)
    rows_c = []
    pc = {'2012-01..2022-12': ('2012-01-31', '2022-12-31'), '2023-01..2026-09': ('2023-01-31', '2026-09-30'),
          '2012-01..2026-09': ('2012-01-31', '2026-09-30'), '2015-01..2026-09': ('2015-01-31', '2026-09-30')}
    for name, df in C.items():
        df.to_csv(os.path.join(OUT, 'monthly_' + ''.join(ch if ch.isalnum() else '_' for ch in name) + '.csv'))
        for lab, (a, z) in pc.items():
            stats = bt.stats(df.net.loc[a:z], rf_c)
            rows_c.append({'strategy': name, 'period': lab, 'v': fmt(stats),
                           'CAGR': stats['CAGR'], 'Sharpe': stats['Sharpe'], 'maxDD_month_end': stats['maxDD_month_end'],
                           'performance_role': ('includes factor-selection sample' if name.startswith('C ') and a < '2023-01-31' else 'retrospective')})
    RC = pd.DataFrame(rows_c)
    pd.concat([R, RC]).to_csv(os.path.join(OUT, 'summary.csv'), index=False)
    print(RC.pivot(index='strategy', columns='period', values='v')[list(pc)].to_string())
    t1 = C['C tech top-1 (S&P ∪ NDX)']
    print('union tech top-1 most held:', t1.pick.value_counts().head(10).to_dict())
    tops = X.dropna(subset=['score'])
    tops = tops[tops.sector == 'Information Technology'].sort_values(['t', 'score', 'ticker'], ascending=[True, False, True]).groupby('t').head(5)
    print('union tech top-5: share of slots taken by NDX-only names', round((~tops.in_sp).mean(), 3),
          '| most frequent NDX-only:', tops[~tops.in_sp].ticker.value_counts().head(10).to_dict())


if __name__ == '__main__':
    main()
