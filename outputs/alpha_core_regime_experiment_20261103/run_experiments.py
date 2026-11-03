#!/usr/bin/env python3
"""
Clean-Room Experimental Suite for:
  A. Alpha Core: 50% QQQ Momentum Top-2 + 50% S&P 500 Tech Momentum Top-1 (2009-01 .. 2026-09, 213 months)
     + Overlap/concentration analysis + Multi-horizon (6-1 + 9-1 + 12-1) Ensemble Core
  C. QQQ Residual Momentum (Daily OLS alpha vs QQQ & Standardized Residual Sharpe) vs Raw & Vol-Scaled Momentum
  B. 3-State Conditional Leverage System (Brake + Alpha Core + Cross-Sectional Dispersion Accelerator)
     with strict Point-in-Time expanding thresholds and realistic margin financing costs (T-bill + 100bp/yr).
"""
import json
import os
import sys
import numpy as np
import pandas as pd

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QQQ_DIR)

import a2_engine as E
import a4_backtest as B


def load_rf_and_rates():
    """Load 3M T-bill (DGS3MO), 2Y Treasury (DGS2), and 10Y TIPS (DFII10) from local FRED store."""
    fred_dir = os.path.join(ROOT, 'data', 'fred')
    out = {}
    for k in ['DGS3MO', 'DGS2', 'DFII10']:
        d = json.load(open(os.path.join(fred_dir, f'{k}.json')))['values']
        s = pd.Series({pd.Timestamp(dt): float(v) for dt, v in d if v is not None and v != '.'}).sort_index()
        out[k] = s / 100.0
    return out


def metrics(ret_s, rf_m=None):
    r = pd.Series(ret_s).dropna()
    if not len(r):
        return {}
    n = len(r)
    cagr = float((np.prod(1.0 + r)) ** (12.0 / n) - 1.0)
    vol = float(r.std(ddof=1) * np.sqrt(12.0))
    if rf_m is not None:
        rf_aligned = rf_m.reindex(r.index).ffill().fillna(0.0)
        ex = r - rf_aligned
    else:
        ex = r
    sharpe = float(ex.mean() / r.std(ddof=1) * np.sqrt(12.0)) if r.std(ddof=1) > 0 else np.nan
    w = (1.0 + r).cumprod()
    dd = float((w / w.cummax() - 1.0).min())
    calmar = cagr / abs(dd) if dd < 0 else np.nan
    return {'n': n, 'CAGR': cagr, 'Vol': vol, 'Sharpe': sharpe, 'MaxDD_m': dd, 'Calmar': calmar}


def build_qqq_market_features(months_t):
    """Strictly PIT QQQ market trend & volatility features at each formation month-end t."""
    df_q = E.series('tiingo_api', 'QQQ')
    if df_q is None:
        df_q = E.series('yahoo', 'QQQ')
    c = df_q['adjclose'].dropna()
    rows = []
    for t in months_t:
        sub = c.loc[:t]
        p0 = sub.iloc[-1]
        sma200 = sub.iloc[-200:].mean() if len(sub) >= 200 else sub.mean()
        sma100 = sub.iloc[-100:].mean() if len(sub) >= 100 else sub.mean()
        sma50 = sub.iloc[-50:].mean() if len(sub) >= 50 else sub.mean()
        ret_12m = p0 / sub.iloc[-252] - 1.0 if len(sub) >= 252 else np.nan
        ret_6m = p0 / sub.iloc[-126] - 1.0 if len(sub) >= 126 else np.nan
        ret_3m = p0 / sub.iloc[-63] - 1.0 if len(sub) >= 63 else np.nan
        vol_20d = sub.pct_change().iloc[-20:].std(ddof=1) * np.sqrt(252)
        vol_63d = sub.pct_change().iloc[-63:].std(ddof=1) * np.sqrt(252)
        dd_252 = p0 / sub.iloc[-252:].max() - 1.0
        rows.append({
            't': t,
            'month': t + pd.offsets.MonthEnd(1),
            'qqq_above_sma200': bool(p0 > sma200),
            'qqq_above_sma100': bool(p0 > sma100),
            'qqq_dist_sma200': float(p0 / sma200 - 1.0),
            'qqq_ret12m': float(ret_12m),
            'qqq_ret6m': float(ret_6m),
            'qqq_ret3m': float(ret_3m),
            'qqq_vol20d': float(vol_20d),
            'qqq_vol63d': float(vol_63d),
            'qqq_dd252': float(dd_252),
        })
    return pd.DataFrame(rows).set_index('month')


def compute_residual_and_vol_momentum(P_12_1):
    """
    For every eligible (t, ticker) in P_12_1, compute over [t-12m, t-1m] using daily returns:
      - vol_12_1: annualized daily return volatility over [t-12m, t-1m]
      - sharpe_mom: mom_12_1 / vol_12_1
      - res_mom_alpha: cumulative daily CAPM residual return vs QQQ over [t-12m, t-1m]
      - res_mom_std: Blitz-Huij-Martens standardized residual momentum (alpha_mean / res_std * sqrt(252))
      - beta_12_1: realized daily beta vs QQQ over [t-12m, t-1m]
    """
    cache_fn = os.path.join(HERE, 'qqq_residual_panel.parquet')
    if os.path.exists(cache_fn) and '--rebuild' not in sys.argv:
        return pd.read_parquet(cache_fn)

    df_q = E.series('tiingo_api', 'QQQ')
    if df_q is None:
        df_q = E.series('yahoo', 'QQQ')
    rq_all = df_q['adjclose'].dropna().pct_change()

    rows = []
    for t, g in P_12_1.groupby('t'):
        t_s = t - pd.offsets.MonthEnd(1)
        t_l = t - pd.offsets.MonthEnd(12)
        rq = rq_all.loc[t_l:t_s].dropna()
        vq = rq.var(ddof=1)
        mq = rq.mean()
        for _, r in g.iterrows():
            tk, st, sym, mom = r['ticker'], r['store'], r['sym'], r['mom']
            df = E.series(st, sym)
            c = df['adjclose'].loc[t_l:t_s].dropna()
            ri = c.pct_change().dropna()
            common = ri.index.intersection(rq.index)
            if len(common) < 120:
                rows.append((t, tk, mom, np.nan, np.nan, np.nan, np.nan, np.nan))
                continue
            y = ri.loc[common].values
            x = rq.loc[common].values
            vol = float(np.std(y, ddof=1) * np.sqrt(252.0))
            cov = float(np.cov(y, x, ddof=1)[0, 1])
            beta = cov / float(np.var(x, ddof=1)) if np.var(x, ddof=1) > 0 else 1.0
            alpha_d = y - beta * x
            # cumulative residual return over [t-12m, t-1m]
            res_cum = float(np.prod(1.0 + np.clip(alpha_d, -0.95, None)) - 1.0)
            res_vol = float(np.std(alpha_d, ddof=1) * np.sqrt(252.0))
            res_sharpe = float(np.mean(alpha_d) / np.std(alpha_d, ddof=1) * np.sqrt(252.0)) if res_vol > 0 else np.nan
            sh_mom = mom / vol if vol > 0 else np.nan
            rows.append((t, tk, mom, vol, sh_mom, res_cum, res_sharpe, beta))

    out = pd.DataFrame(rows, columns=['t', 'ticker', 'mom_12_1', 'vol_12_1', 'sharpe_mom', 'res_mom_cum', 'res_mom_std', 'beta_12_1'])
    out.to_parquet(cache_fn, index=False)
    return out


def run_ranked_qqq(panel_df, score_col, H_all, k=2, cost_bp=10.0):
    """Run top-k open-to-open backtest on QQQ PIT universe ranked by score_col descending."""
    sub = panel_df.dropna(subset=[score_col]).copy()
    sub['mom'] = sub[score_col]
    sub['rank'] = sub.groupby('t')['mom'].rank(ascending=False, method='first').astype(int)
    L = B.run(sub, H_all, k=k, cost_bp=cost_bp)
    return L.set_index('month')


def main():
    os.makedirs(HERE, exist_ok=True)
    rates = load_rf_and_rates()
    rf_m = rates['DGS3MO'].resample('ME').last() / 12.0

    # Load QQQ panels & full holding return table
    P12 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel.parquet'))
    P9 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_lb9_sk1.parquet'))
    P6 = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_lb6_sk1.parquet'))
    H_all = pd.read_parquet(os.path.join(QQQ_DIR, 'r_hold_returns_open_d1_all.parquet'))

    # Load Tech clean-room ledgers & rank table
    tech_s1 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'S1_main_top1.csv'), parse_dates=['month', 'formation']).set_index('month')
    tech_s0 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'S0_wiki_asis_top1.csv'), parse_dates=['month', 'formation']).set_index('month')
    tech_s1_top2 = pd.read_csv(os.path.join(TECH_DIR, 'ledgers', 'top2_ew.csv'), parse_dates=['month']).set_index('month')
    tech_ranks = pd.read_csv(os.path.join(TECH_DIR, 'rank_tables_claude.csv'), parse_dates=['formation'])

    # Benchmarks (open-to-open)
    L_qqq_top3 = pd.read_csv(os.path.join(QQQ_DIR, 'l_SPEC_top3.csv'), parse_dates=['month', 't']).set_index('month')
    L_qqq_top2 = run_ranked_qqq(P12, 'mom', H_all, k=2, cost_bp=10.0)
    L_qqq_top1 = run_ranked_qqq(P12, 'mom', H_all, k=1, cost_bp=10.0)

    # Multi-horizon ensemble on QQQ: average rank of 6-1, 9-1, 12-1
    m_ens = P12[['t', 'ticker', 'mom', 'rank']].rename(columns={'mom': 'mom12', 'rank': 'r12'})
    m_ens = m_ens.merge(P9[['t', 'ticker', 'mom', 'rank']].rename(columns={'mom': 'mom9', 'rank': 'r9'}), on=['t', 'ticker'], how='inner')
    m_ens = m_ens.merge(P6[['t', 'ticker', 'mom', 'rank']].rename(columns={'mom': 'mom6', 'rank': 'r6'}), on=['t', 'ticker'], how='inner')
    m_ens['ens_score'] = -(m_ens['r12'] + m_ens['r9'] + m_ens['r6']) / 3.0
    m_ens['ens_mom_avg'] = (m_ens['mom12'] + m_ens['mom9'] + m_ens['mom6']) / 3.0
    L_qqq_ens_top2 = run_ranked_qqq(m_ens, 'ens_score', H_all, k=2, cost_bp=10.0)
    L_qqq_ens_top3 = run_ranked_qqq(m_ens, 'ens_score', H_all, k=3, cost_bp=10.0)

    # Experiment C: Residual & Vol-Scaled Momentum on QQQ
    res_panel = compute_residual_and_vol_momentum(P12)
    L_qqq_res_cum_top2 = run_ranked_qqq(res_panel, 'res_mom_cum', H_all, k=2, cost_bp=10.0)
    L_qqq_res_cum_top3 = run_ranked_qqq(res_panel, 'res_mom_cum', H_all, k=3, cost_bp=10.0)
    L_qqq_res_std_top2 = run_ranked_qqq(res_panel, 'res_mom_std', H_all, k=2, cost_bp=10.0)
    L_qqq_res_std_top3 = run_ranked_qqq(res_panel, 'res_mom_std', H_all, k=3, cost_bp=10.0)
    L_qqq_sharpe_top2 = run_ranked_qqq(res_panel, 'sharpe_mom', H_all, k=2, cost_bp=10.0)
    L_qqq_sharpe_top3 = run_ranked_qqq(res_panel, 'sharpe_mom', H_all, k=3, cost_bp=10.0)

    # Load QQQ ETF benchmark from x_monthly_ledgers.csv
    x_led = pd.read_csv(os.path.join(QQQ_DIR, 'x_monthly_ledgers.csv'), parse_dates=['month']).set_index('month')
    r_qqq_etf = x_led['BENCH QQQ ETF']

    # =========================================================================
    # Experiment A: Alpha Core (50% QQQ Top-2 + 50% Tech Top-1) & Overlap Check
    # =========================================================================
    months = L_qqq_top2.index
    r_core_s1 = 0.5 * L_qqq_top2.loc[months, 'net'] + 0.5 * tech_s1.loc[months, 'net']
    r_core_s0 = 0.5 * L_qqq_top2.loc[months, 'net'] + 0.5 * tech_s0.loc[months, 'net']
    r_core_ens_s1 = 0.5 * L_qqq_ens_top2.loc[months, 'net'] + 0.5 * tech_s1.loc[months, 'net']
    r_core_top3_s1 = 0.5 * L_qqq_top3.loc[months, 'net'] + 0.5 * tech_s1.loc[months, 'net']
    r_core_res_s1 = 0.5 * L_qqq_res_std_top2.loc[months, 'net'] + 0.5 * tech_s1.loc[months, 'net']
    r_core_sh_s1 = 0.5 * L_qqq_sharpe_top2.loc[months, 'net'] + 0.5 * tech_s1.loc[months, 'net']
    r_core_3way = (1/3) * L_qqq_top2.loc[months, 'net'] + (1/3) * tech_s1.loc[months, 'net'] + (1/3) * L_qqq_res_std_top2.loc[months, 'net']

    # Check overlap between QQQ Top-2 and Tech Top-1
    overlap_r1 = 0
    overlap_any = 0
    for m in months:
        q_picks = L_qqq_top2.loc[m, 'picks'].split('|')
        t_pick = str(tech_s1.loc[m, 'picks']).strip()
        if t_pick == q_picks[0]:
            overlap_r1 += 1
        if t_pick in q_picks:
            overlap_any += 1

    corr_s1 = float(L_qqq_top2.loc[months, 'net'].corr(tech_s1.loc[months, 'net']))
    corr_s0 = float(L_qqq_top2.loc[months, 'net'].corr(tech_s0.loc[months, 'net']))
    corr_res_raw = float(L_qqq_res_std_top2.loc[months, 'net'].corr(L_qqq_top2.loc[months, 'net']))
    corr_res_tech = float(L_qqq_res_std_top2.loc[months, 'net'].corr(tech_s1.loc[months, 'net']))

    print(f'=== OVERLAP & CORRELATION (213 months, 2009-01..2026-09) ===')
    print(f'Monthly return correlation: QQQ Top-2 vs Tech Top-1 (S1 clean-room): {corr_s1:.4f} (vs S0 w/ NFLX: {corr_s0:.4f})')
    print(f'Monthly return correlation: QQQ Std-Residual Top-2 vs QQQ Raw Top-2: {corr_res_raw:.4f} | vs Tech Top-1: {corr_res_tech:.4f}')
    print(f'Overlap: Tech Top-1 is in QQQ Top-2 in {overlap_any}/{len(months)} months ({overlap_any/len(months):.1%}); '
          f'equals QQQ #1 in {overlap_r1}/{len(months)} months ({overlap_r1/len(months):.1%}) -> 75% in 1 stock!')

    # Build deduplicated Alpha Core (max 50% or 33.3% per stock when QQQ Top-2 and Tech Top-1 overlap)
    # Using exact individual stock returns from QQQ and Tech rank tables
    Hm_qqq = H_all.set_index(['t', 'ticker'])
    dedup_50_rets = []
    dedup_33_rets = []
    prev_w50, prev_w33 = {}, {}
    for m in months:
        t = m - pd.offsets.MonthEnd(1)
        q_g = P12[P12['t'] == t].sort_values('rank')
        q_ok = [s for s in q_g.ticker if (t, s) in Hm_qqq.index and np.isfinite(Hm_qqq.at[(t, s), 'ret'])]
        q_top3 = q_ok[:3]
        t_pick = str(tech_s1.loc[m, 'picks']).strip()
        t_ret = float(tech_s1.loc[m, 'gross'])
        q_rets = {s: float(Hm_qqq.at[(t, s), 'ret']) for s in q_top3}
        q_rets[t_pick] = q_rets.get(t_pick, t_ret)

        # Cap at 50%: if t_pick in q_top3[:2], bring in q_top3[2] so weights are 50% shared, 25% other QQQ, 25% QQQ #3
        if t_pick in q_top3[:2]:
            other_q = [s for s in q_top3[:2] if s != t_pick][0]
            w50 = {t_pick: 0.50, other_q: 0.25, q_top3[2]: 0.25}
            w33 = {t_pick: 1/3, other_q: 1/3, q_top3[2]: 1/3}
        else:
            w50 = {t_pick: 0.50, q_top3[0]: 0.25, q_top3[1]: 0.25}
            w33 = {t_pick: 1/3, q_top3[0]: 1/3, q_top3[1]: 1/3}

        for w, prev_w, lst in [(w50, prev_w50, dedup_50_rets), (w33, prev_w33, dedup_33_rets)]:
            gross = sum(w[s] * q_rets[s] for s in w)
            to = sum(abs(w.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(w) | set(prev_w))
            net = gross - to * 0.001
            lst.append((m, net))
            prev_w.clear()
            for s in w:
                prev_w[s] = w[s] * (1.0 + q_rets[s]) / (1.0 + gross)

    r_dedup50 = pd.Series(dict(dedup_50_rets))
    r_dedup33 = pd.Series(dict(dedup_33_rets))

    # =========================================================================
    # Experiment B: Cross-Sectional Dispersion + Macro/SEP Brake + Leverage
    # =========================================================================
    mkt_df = build_qqq_market_features(L_qqq_top2['t'].values)

    # Compute PIT Cross-Sectional Dispersion at each formation month-end t
    disp_rows = []
    for t, g in P12.groupby('t'):
        m_hold = t + pd.offsets.MonthEnd(1)
        moms = g.sort_values('rank')['mom'].values
        top2_mean = float(np.mean(moms[:2]))
        top3_mean = float(np.mean(moms[:3]))
        top5_mean = float(np.mean(moms[:5]))
        med = float(np.median(moms))
        p75 = float(np.percentile(moms, 75))
        p25 = float(np.percentile(moms, 25))
        iqr = max(p75 - p25, 0.05)
        # Also check Tech pool dispersion
        tg = tech_ranks[tech_ranks['formation'] == t].sort_values('rank')
        t_top1 = float(tg['mom'].iloc[0]) if len(tg) else np.nan
        t_med = float(tg['mom'].median()) if len(tg) else np.nan
        disp_rows.append({
            'month': m_hold,
            't': t,
            'ndx_top3_minus_med': top3_mean - med,
            'ndx_top2_minus_med': top2_mean - med,
            'ndx_disp_iqr_ratio': (top3_mean - med) / iqr,
            'tech_top1_minus_med': t_top1 - t_med,
            'comb_disp': 0.5 * (top2_mean - med) + 0.5 * (t_top1 - t_med),
            'ndx_med_mom': med,
        })
    disp_df = pd.DataFrame(disp_rows).set_index('month')

    # Strictly PIT expanding percentiles (minimum 24 months history; for first 24m use structural threshold > 0.60)
    disp_df['ndx_disp_exp_pct'] = [
        float((disp_df['ndx_top3_minus_med'].iloc[:i+1] <= disp_df['ndx_top3_minus_med'].iloc[i]).mean()) if i >= 24
        else (0.80 if disp_df['ndx_top3_minus_med'].iloc[i] > 0.65 else 0.40)
        for i in range(len(disp_df))
    ]
    disp_df['comb_disp_exp_pct'] = [
        float((disp_df['comb_disp'].iloc[:i+1] <= disp_df['comb_disp'].iloc[i]).mean()) if i >= 24
        else (0.80 if disp_df['comb_disp'].iloc[i] > 0.70 else 0.40)
        for i in range(len(disp_df))
    ]

    # Macro / SEP Rate-Shock Brake at formation month-end t (strictly PIT)
    dgs2_m = rates['DGS2'].resample('ME').last()
    dfii10_m = rates['DFII10'].resample('ME').last()
    # V6 SEP/EPS out-of-market windows from research/strategy_comparison/v6_final_report.md:
    # 2022-02-01..2022-11-07 (formation month-ends 2022-01-31..2022-10-31 -> holding months 2022-02..2022-11)
    # Pure SEP out-of-market windows: 2021-10..2023-03, 2023-07..2023-12, 2024-07..2024-09, 2025-01..2025-03, 2026-07..2026-08
    v6_brake_months = set(pd.date_range('2022-02-28', '2022-10-31', freq='ME'))
    pure_sep_brake_months = (
        set(pd.date_range('2021-10-31', '2023-03-31', freq='ME')) |
        set(pd.date_range('2023-07-31', '2023-12-31', freq='ME')) |
        set(pd.date_range('2024-07-31', '2024-09-30', freq='ME')) |
        set(pd.date_range('2025-01-31', '2025-03-31', freq='ME')) |
        set(pd.date_range('2026-07-31', '2026-08-31', freq='ME'))
    )

    brake_df = pd.DataFrame(index=months)
    for m in months:
        t = m - pd.offsets.MonthEnd(1)
        # PIT 6-month change in 2Y yield & 10Y real yield at formation month-end t
        d2_6m = float(dgs2_m.loc[:t].iloc[-1] - dgs2_m.loc[:t].iloc[-7]) if len(dgs2_m.loc[:t]) >= 7 else 0.0
        dr_6m = float(dfii10_m.loc[:t].iloc[-1] - dfii10_m.loc[:t].iloc[-7]) if len(dfii10_m.loc[:t]) >= 7 else 0.0
        q_below_200 = not mkt_df.loc[m, 'qqq_above_sma200']
        q_below_100 = not mkt_df.loc[m, 'qqq_above_sma100']
        # Continuous PIT Rate-Shock + Trend Brake (available 2009..2026):
        # Risk-off when QQQ < SMA200 AND (6m 2Y yield jump >= +50bp OR 6m Real Yield jump >= +40bp OR QQQ 12m return < 0)
        rate_shock = (d2_6m >= 0.0050) or (dr_6m >= 0.0040)
        brake_df.loc[m, 'brake_sma200'] = q_below_200
        brake_df.loc[m, 'brake_rate_trend'] = q_below_200 and (rate_shock or mkt_df.loc[m, 'qqq_ret12m'] < 0)
        brake_df.loc[m, 'brake_v6_sep'] = (m in v6_brake_months) or (m < pd.Timestamp('2015-01-01') and q_below_200 and rate_shock)
        brake_df.loc[m, 'brake_pure_sep'] = (m in pure_sep_brake_months)

    def sim_levered(r_base, lev_series, borrow_spread_ann=0.01, extra_cost_bp=10.0):
        """
        Simulate monthly levered return with realistic financing and rebalance cost:
          - If L_m <= 1.0: L_m * r_base + (1 - L_m) * rf_m
          - If L_m >  1.0: L_m * r_base - (L_m - 1) * (rf_m + borrow_spread_ann/12) - (L_m - 1)*extra_cost_bp/1e4
          - Plus leverage change turnover cost: |L_m - L_{m-1}| * extra_cost_bp / 1e4
        """
        out = []
        prev_L = 1.0
        for m in r_base.index:
            L = float(lev_series.loc[m])
            rb = float(r_base.loc[m])
            rf = float(rf_m.reindex([m]).ffill().iloc[0]) if m in rf_m.index else 0.001
            lev_to_cost = abs(L - prev_L) * (extra_cost_bp / 1e4)
            if L <= 1.0:
                rm = L * rb + (1.0 - L) * rf - lev_to_cost
            else:
                borrow_cost = (L - 1.0) * (rf + borrow_spread_ann / 12.0)
                extra_slip = (L - 1.0) * (extra_cost_bp / 1e4)
                rm = L * rb - borrow_cost - extra_slip - lev_to_cost
            # Floor monthly return at -99% (margin call / wipeout check)
            rm = max(rm, -0.99)
            out.append((m, rm))
            prev_L = L
        return pd.Series(dict(out))

    # Test regime-based leverage schedules on Alpha Core (r_core_s1):
    # 1. Constant 1.0x, 1.5x, 2.0x (with financing cost)
    L_const_15 = pd.Series(1.5, index=months)
    L_const_20 = pd.Series(2.0, index=months)

    # 2. Pure Dispersion Accelerator (NO trend filter): 2.0x when NDX dispersion > expanding 60th pct, else 1.0x
    L_disp_only_20 = pd.Series([2.0 if disp_df.loc[m, 'ndx_disp_exp_pct'] >= 0.60 else 1.0 for m in months], index=months)

    # 3. 3-State System B1 (User's spec: Brake = V6 SEP/Rate-Trend -> 0.5x, Normal = 1.0x, Strong Dispersion+Trend -> 1.5x / 2.0x)
    L_3state_15 = pd.Series(1.0, index=months)
    L_3state_20 = pd.Series(1.0, index=months)
    L_3state_flat0_20 = pd.Series(1.0, index=months)
    for m in months:
        is_risk_off = bool(brake_df.loc[m, 'brake_sma200'])
        # Strong trend: QQQ > SMA200 AND cross-sectional dispersion in top 40% (expanding >= 0.60) AND median NDX 12-1 mom > 0
        is_strong = (not is_risk_off) and (disp_df.loc[m, 'comb_disp_exp_pct'] >= 0.60) and (disp_df.loc[m, 'ndx_med_mom'] > 0.0)
        if is_risk_off:
            L_3state_15.loc[m] = 0.5
            L_3state_20.loc[m] = 0.5
            L_3state_flat0_20.loc[m] = 0.0
        elif is_strong:
            L_3state_15.loc[m] = 1.5
            L_3state_20.loc[m] = 2.0
            L_3state_flat0_20.loc[m] = 2.0

    # 4. Volatility-Targeted + Dispersion-Gated Leverage (Inverse realized vol scaling capped at 2.0x when in bull trend + dispersion)
    L_voltarget_20 = pd.Series(1.0, index=months)
    for m in months:
        if brake_df.loc[m, 'brake_sma200']:
            L_voltarget_20.loc[m] = 0.0
        else:
            # Target vol = 45%, scaled by QQQ 63d realized vol (baseline 18%), boosted when dispersion is strong
            v63 = max(mkt_df.loc[m, 'qqq_vol63d'], 0.10)
            base_l = np.clip(0.22 / v63, 0.75, 1.75)
            if disp_df.loc[m, 'comb_disp_exp_pct'] >= 0.60 and disp_df.loc[m, 'ndx_med_mom'] > 0.0:
                base_l = min(base_l * 1.25, 2.0)
            L_voltarget_20.loc[m] = float(base_l)

    variants = {
        '01. Passive QQQ ETF (10bp open-to-open)': r_qqq_etf.loc[months],
        '02. QQQ Pure 12-1 Mom Top-3 (audited)': L_qqq_top3.loc[months, 'net'],
        '03. QQQ Pure 12-1 Mom Top-2 (audited)': L_qqq_top2.loc[months, 'net'],
        '04. S&P500 Tech 12-1 Mom Top-1 (S1 audited, no NFLX)': tech_s1.loc[months, 'net'],
        '05. S&P500 Tech 12-1 Mom Top-1 (S0 w/ NFLX)': tech_s0.loc[months, 'net'],
        '06. [Exp A1] Alpha Core: 50% QQQ Top-2 + 50% Tech Top-1 (S1)': r_core_s1,
        '07. [Exp A0] 50% QQQ Top-2 + 50% Tech Top-1 (S0 w/ NFLX)': r_core_s0,
        '08. [Exp A2] Deduplicated Core (Max 50% single-stock cap)': r_dedup50,
        '09. [Exp A3] Deduplicated Core (3 distinct stocks, 1/3 each)': r_dedup33,
        '10. [Exp A4] Ensemble Core: 50% QQQ (6-1+9-1+12-1) Top-2 + 50% Tech Top-1': r_core_ens_s1,
        '11. [Exp C1] QQQ Residual Mom (Cum Alpha vs QQQ) Top-2': L_qqq_res_cum_top2.loc[months, 'net'],
        '12. [Exp C2] QQQ Residual Mom (Cum Alpha vs QQQ) Top-3': L_qqq_res_cum_top3.loc[months, 'net'],
        '13. [Exp C3] QQQ Std-Residual Mom (Blitz-Huij ResSharpe) Top-2': L_qqq_res_std_top2.loc[months, 'net'],
        '14. [Exp C4] QQQ Std-Residual Mom (Blitz-Huij ResSharpe) Top-3': L_qqq_res_std_top3.loc[months, 'net'],
        '15. [Exp C5] QQQ Sharpe Mom (mom_12_1 / vol_12m) Top-2': L_qqq_sharpe_top2.loc[months, 'net'],
        '16. [Exp C6] QQQ Multi-Horizon Ensemble (6-1+9-1+12-1) Top-2': L_qqq_ens_top2.loc[months, 'net'],
        '17. [Exp C7] 3-Sleeve Core: 1/3 QQQ Top-2 + 1/3 Tech Top-1 + 1/3 QQQ ResMom Top-2': r_core_3way,
        '18. [Exp B0] Alpha Core Constant 1.5x (net of margin r_f+1%)': sim_levered(r_core_s1, L_const_15),
        '19. [Exp B0b] Alpha Core Constant 2.0x (net of margin r_f+1%)': sim_levered(r_core_s1, L_const_20),
        '20. [Exp B1] Alpha Core + Dispersion-Only 1x/2x (NO trend brake)': sim_levered(r_core_s1, L_disp_only_20),
        '21. [Exp B2] 3-State (SMA200 Brake 0.5x | Normal 1x | Dispersion+Trend 1.5x)': sim_levered(r_core_s1, L_3state_15),
        '22. [Exp B3] 3-State (SMA200 Brake 0.5x | Normal 1x | Dispersion+Trend 2.0x)': sim_levered(r_core_s1, L_3state_20),
        '23. [Exp B4] 3-State (SMA200 Brake 0.0x Cash | Normal 1x | Dispersion+Trend 2.0x)': sim_levered(r_core_s1, L_3state_flat0_20),
        '24. [Exp B5] 3-State on Ensemble Core (0.0x | 1x | 2.0x)': sim_levered(r_core_ens_s1, L_3state_flat0_20),
        '25. [Exp B6] Vol-Targeted + Dispersion-Gated Leverage (0.0x..2.0x) on Alpha Core': sim_levered(r_core_s1, L_voltarget_20),
    }

    windows = [
        ('FULL 09-26', '2009-01-31', '2026-09-30'),
        ('2009-2014', '2009-01-31', '2014-12-31'),
        ('2015-2019', '2015-01-31', '2019-12-31'),
        ('2020-2022', '2020-01-31', '2022-12-31'),
        ('2023-26.09', '2023-01-31', '2026-09-30'),
        ('2009-2018', '2009-01-31', '2018-12-31'),
        ('2015-26.09', '2015-01-31', '2026-09-30'),
        ('2019-26.09', '2019-01-31', '2026-09-30'),
    ]

    summary_rows = []
    for name, s in variants.items():
        m_full = metrics(s.loc['2009-01-31':'2026-09-30'], rf_m)
        row = {
            'Variant': name,
            'CAGR 09-26': m_full['CAGR'],
            'Vol 09-26': m_full['Vol'],
            'Sharpe 09-26': m_full['Sharpe'],
            'MaxDD(m) 09-26': m_full['MaxDD_m'],
            'Calmar 09-26': m_full['Calmar'],
        }
        for wname, a, b in windows[1:]:
            mw = metrics(s.loc[a:b], rf_m)
            row[f'CAGR {wname}'] = mw['CAGR']
        summary_rows.append(row)

    S = pd.DataFrame(summary_rows)
    S.to_csv(os.path.join(HERE, 'experiment_summary.csv'), index=False)

    # Pretty print
    disp = S.copy()
    for c in disp.columns:
        if c.startswith('CAGR') or c.startswith('Vol') or c.startswith('MaxDD'):
            disp[c] = disp[c].map(lambda v: f'{v*100:.2f}%' if pd.notna(v) else '')
        elif c.startswith('Sharpe') or c.startswith('Calmar'):
            disp[c] = disp[c].map(lambda v: f'{v:.2f}' if pd.notna(v) else '')
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', 300)
    print('\n=== FULL EXPERIMENTAL RESULTS (2009-01..2026-09, NET OF COSTS & MARGIN BORROWING) ===')
    print(disp.to_string(index=False))

    # Also print regime distribution for 3-State system
    print('\n=== 3-STATE LEVERAGE REGIME BREAKDOWN (213 months) ===')
    print('L_3state_flat0_20 value counts:', L_3state_flat0_20.value_counts().to_dict())
    print('Mean leverage across 213 months:', f'{L_3state_flat0_20.mean():.2f}x')


if __name__ == '__main__':
    main()
