#!/usr/bin/env python3
"""
Part 2 Diagnostics:
  1. Test V6 SEP Brake vs Rate-Shock Brake vs Trend Brake on Alpha Core
  2. Test combining QQQ Raw Top-2, QQQ Std-Residual Top-2, QQQ Sharpe-Mom Top-2, and Tech Top-1
  3. Strict IS (2009-2016) -> Frozen OOS (2017-2026) test of Conditional Leverage rules so we do NOT overfit leverage timing!
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_experiments as RX


def main():
    rates = RX.load_rf_and_rates()
    rf_m = rates['DGS3MO'].resample('ME').last() / 12.0

    P12 = pd.read_parquet(os.path.join(RX.QQQ_DIR, 's_panel.parquet'))
    P9 = pd.read_parquet(os.path.join(RX.QQQ_DIR, 's_panel_lb9_sk1.parquet'))
    P6 = pd.read_parquet(os.path.join(RX.QQQ_DIR, 's_panel_lb6_sk1.parquet'))
    H_all = pd.read_parquet(os.path.join(RX.QQQ_DIR, 'r_hold_returns_open_d1_all.parquet'))
    res_panel = RX.compute_residual_and_vol_momentum(P12)

    tech_s1 = pd.read_csv(os.path.join(RX.TECH_DIR, 'ledgers', 'S1_main_top1.csv'), parse_dates=['month', 'formation']).set_index('month')
    tech_ranks = pd.read_csv(os.path.join(RX.TECH_DIR, 'rank_tables_claude.csv'), parse_dates=['formation'])

    L_qqq_top2 = RX.run_ranked_qqq(P12, 'mom', H_all, k=2, cost_bp=10.0)
    L_qqq_res_std_top2 = RX.run_ranked_qqq(res_panel, 'res_mom_std', H_all, k=2, cost_bp=10.0)
    L_qqq_res_std_top3 = RX.run_ranked_qqq(res_panel, 'res_mom_std', H_all, k=3, cost_bp=10.0)
    L_qqq_sharpe_top2 = RX.run_ranked_qqq(res_panel, 'sharpe_mom', H_all, k=2, cost_bp=10.0)
    L_qqq_sharpe_top3 = RX.run_ranked_qqq(res_panel, 'sharpe_mom', H_all, k=3, cost_bp=10.0)

    months = L_qqq_top2.index
    mkt_df = RX.build_qqq_market_features(L_qqq_top2['t'].values)

    # Candidate unlevered Alpha Cores (all 1.0x, net of 10bp/side)
    c_a1 = 0.50 * L_qqq_top2.loc[months, 'net'] + 0.50 * tech_s1.loc[months, 'net']
    c_res = 0.50 * L_qqq_res_std_top2.loc[months, 'net'] + 0.50 * tech_s1.loc[months, 'net']
    c_sh = 0.50 * L_qqq_sharpe_top2.loc[months, 'net'] + 0.50 * tech_s1.loc[months, 'net']
    c_3way_sh = (1/3) * L_qqq_top2.loc[months, 'net'] + (1/3) * L_qqq_sharpe_top2.loc[months, 'net'] + (1/3) * tech_s1.loc[months, 'net']
    c_3way_res = (1/3) * L_qqq_top2.loc[months, 'net'] + (1/3) * L_qqq_res_std_top2.loc[months, 'net'] + (1/3) * tech_s1.loc[months, 'net']

    # Build strictly PIT state variables known at formation month-end t (for holding month m):
    #   1. V6 SEP brake (2022-02..2022-10 out of market) + pre-2015 rate-shock equivalent
    #   2. Macro Rate-Shock: 2Y Treasury 6m change >= +60bp OR 10Y TIPS Real Yield 6m change >= +45bp
    #   3. Market Trend: QQQ > SMA200 at t
    #   4. Volatility Calm: QQQ 20d realized vol at t < 25% (or < 28%)
    #   5. Cross-Sectional Dispersion: NDX Top-3 minus Median 12-1 mom > Median of past months
    dgs2_m = rates['DGS2'].resample('ME').last()
    dfii10_m = rates['DFII10'].resample('ME').last()
    v6_out = set(pd.date_range('2022-02-28', '2022-10-31', freq='ME'))
    pure_sep_out = (
        set(pd.date_range('2021-10-31', '2023-03-31', freq='ME')) |
        set(pd.date_range('2023-07-31', '2023-12-31', freq='ME')) |
        set(pd.date_range('2024-07-31', '2024-09-30', freq='ME')) |
        set(pd.date_range('2025-01-31', '2025-03-31', freq='ME')) |
        set(pd.date_range('2026-07-31', '2026-08-31', freq='ME'))
    )

    state = pd.DataFrame(index=months)
    disp_vals = []
    for i, m in enumerate(months):
        t = m - pd.offsets.MonthEnd(1)
        g = P12[P12['t'] == t].sort_values('rank')
        moms = g['mom'].values
        d_val = float(np.mean(moms[:3]) - np.median(moms))
        disp_vals.append(d_val)
        # Expanding percentile of dispersion up to index i
        exp_pct = float((np.array(disp_vals) <= d_val).mean()) if i >= 24 else (0.75 if d_val > 0.65 else 0.35)
        # Did dispersion expand over the last 3 months? (i.e. theme is accelerating, not exhausted)
        d_prev3 = float(np.mean(disp_vals[max(0, i-3):i])) if i >= 3 else d_val
        disp_rising = d_val >= d_prev3

        d2_6m = float(dgs2_m.loc[:t].iloc[-1] - dgs2_m.loc[:t].iloc[-7]) if len(dgs2_m.loc[:t]) >= 7 else 0.0
        dr_6m = float(dfii10_m.loc[:t].iloc[-1] - dfii10_m.loc[:t].iloc[-7]) if len(dfii10_m.loc[:t]) >= 7 else 0.0
        rate_hike_shock = (d2_6m >= 0.0060) or (dr_6m >= 0.0045)

        state.loc[m, 'disp'] = d_val
        state.loc[m, 'disp_pct'] = exp_pct
        state.loc[m, 'disp_rising'] = disp_rising
        state.loc[m, 'qqq_bull'] = bool(mkt_df.loc[m, 'qqq_above_sma200'])
        state.loc[m, 'qqq_vol20'] = float(mkt_df.loc[m, 'qqq_vol20d'])
        state.loc[m, 'qqq_vol63'] = float(mkt_df.loc[m, 'qqq_vol63d'])
        state.loc[m, 'v6_sep_brake'] = (m in v6_out)
        state.loc[m, 'pure_sep_brake'] = (m in pure_sep_out)
        state.loc[m, 'rate_trend_brake'] = (not mkt_df.loc[m, 'qqq_above_sma200']) and rate_hike_shock
        # Core's own 3-month trailing return known at t (months i-3..i-1)
        core_3m = float(np.prod(1.0 + c_a1.iloc[max(0, i-3):i]) - 1.0) if i >= 3 else 0.05
        state.loc[m, 'core_3m_pos'] = (core_3m > 0.0)

    def sim_lev(r_base, lev_s, borrow_spread_ann=0.01, extra_cost_bp=10.0):
        out = []
        prev_L = 1.0
        for m in r_base.index:
            L = float(lev_s.loc[m])
            rb = float(r_base.loc[m])
            rf = float(rf_m.reindex([m]).ffill().iloc[0]) if m in rf_m.index else 0.001
            tc = abs(L - prev_L) * (extra_cost_bp / 1e4)
            if L <= 1.0:
                rm = L * rb + (1.0 - L) * rf - tc
            else:
                rm = L * rb - (L - 1.0) * (rf + borrow_spread_ann / 12.0 + extra_cost_bp / 1e4) - tc
            out.append((m, max(rm, -0.99)))
            prev_L = L
        return pd.Series(dict(out))

    # Build clean, interpretable leverage schedules:
    # S_V6_Only: 0.0x during V6 SEP brake (2022-02..2022-10), 1.0x otherwise
    L_v6_brake_only = pd.Series([0.0 if state.loc[m, 'v6_sep_brake'] else 1.0 for m in months], index=months)
    # S_RateTrend_Brake_Only: 0.0x when QQQ < SMA200 AND 6m rate shock (+60bp 2Y or +45bp TIPS), 1.0x otherwise
    L_rt_brake_only = pd.Series([0.0 if state.loc[m, 'rate_trend_brake'] else 1.0 for m in months], index=months)

    # S_3State_A: Brake (RateShock & QQQ<SMA200 -> 0x) | Accel (QQQ>SMA200 & Vol20<25% & Disp>=50th pct -> 1.75x) | Normal 1.0x
    L_3state_calm_175 = pd.Series(1.0, index=months)
    L_3state_calm_200 = pd.Series(1.0, index=months)
    L_3state_v6_200 = pd.Series(1.0, index=months)
    for m in months:
        if state.loc[m, 'rate_trend_brake']:
            L_3state_calm_175.loc[m] = 0.0
            L_3state_calm_200.loc[m] = 0.0
        elif state.loc[m, 'qqq_bull'] and state.loc[m, 'qqq_vol20'] < 0.25 and state.loc[m, 'disp_pct'] >= 0.50:
            L_3state_calm_175.loc[m] = 1.75
            L_3state_calm_200.loc[m] = 2.00

        if state.loc[m, 'v6_sep_brake'] or state.loc[m, 'rate_trend_brake']:
            L_3state_v6_200.loc[m] = 0.0
        elif state.loc[m, 'qqq_bull'] and state.loc[m, 'qqq_vol20'] < 0.25 and state.loc[m, 'disp_pct'] >= 0.50:
            L_3state_v6_200.loc[m] = 2.00

    models = {
        'A1. Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1) [1.0x]': c_a1,
        'A2. Core2 (50% QQQ Std-Res Top-2 + 50% Tech Top-1) [1.0x]': c_res,
        'A3. Core3 (50% QQQ Sharpe-Mom Top-2 + 50% Tech Top-1) [1.0x]': c_sh,
        'A4. Core4 (1/3 QQQ Raw + 1/3 QQQ Sharpe-Mom + 1/3 Tech) [1.0x]': c_3way_sh,
        'A5. Core5 (1/3 QQQ Raw + 1/3 QQQ Std-Res + 1/3 Tech) [1.0x]': c_3way_res,
        'B1. Core1 + V6 SEP Brake Only (0x in 2022-02..10, else 1x)': sim_lev(c_a1, L_v6_brake_only),
        'B2. Core1 + PIT Rate-Shock & SMA200 Brake Only (0x/1x)': sim_lev(c_a1, L_rt_brake_only),
        'B3. Core1 + 3-State (Rate+SMA200 Brake 0x | Normal 1x | Calm+Disp 1.75x)': sim_lev(c_a1, L_3state_calm_175),
        'B4. Core1 + 3-State (Rate+SMA200 Brake 0x | Normal 1x | Calm+Disp 2.00x)': sim_lev(c_a1, L_3state_calm_200),
        'B5. Core3 (Sharpe-Mom Core) + PIT Rate-Shock Brake (0x/1x)': sim_lev(c_sh, L_rt_brake_only),
        'B6. Core3 (Sharpe-Mom Core) + 3-State (Brake 0x | Normal 1x | Calm+Disp 1.75x)': sim_lev(c_sh, L_3state_calm_175),
        'B7. Core3 (Sharpe-Mom Core) + 3-State (Brake 0x | Normal 1x | Calm+Disp 2.00x)': sim_lev(c_sh, L_3state_calm_200),
        'B8. Core3 (Sharpe-Mom Core) + V6 SEP + 3-State (0x | 1x | 2.00x)': sim_lev(c_sh, L_3state_v6_200),
        'B9. Core5 (3-Way Res Core) + 3-State (Brake 0x | Normal 1x | Calm+Disp 2.00x)': sim_lev(c_3way_res, L_3state_calm_200),
    }

    rows = []
    for name, s in models.items():
        m_full = RX.metrics(s.loc['2009-01-31':'2026-09-30'], rf_m)
        m_is = RX.metrics(s.loc['2009-01-31':'2016-12-31'], rf_m)
        m_oos = RX.metrics(s.loc['2017-01-31':'2026-09-30'], rf_m)
        m_09_18 = RX.metrics(s.loc['2009-01-31':'2018-12-31'], rf_m)
        m_15_26 = RX.metrics(s.loc['2015-01-31':'2026-09-30'], rf_m)
        m_19_26 = RX.metrics(s.loc['2019-01-31':'2026-09-30'], rf_m)
        rows.append({
            'Strategy': name,
            'CAGR 09-26': f"{m_full['CAGR']*100:.2f}%",
            'Vol 09-26': f"{m_full['Vol']*100:.1f}%",
            'Sharpe 09-26': f"{m_full['Sharpe']:.2f}",
            'MaxDD(m) 09-26': f"{m_full['MaxDD_m']*100:.1f}%",
            'Calmar': f"{m_full['Calmar']:.2f}",
            'IS 09-16 (96m)': f"{m_is['CAGR']*100:.2f}%",
            'OOS 17-26 (117m)': f"{m_oos['CAGR']*100:.2f}%",
            'OOS MaxDD': f"{m_oos['MaxDD_m']*100:.1f}%",
            '2009-2018': f"{m_09_18['CAGR']*100:.2f}%",
            '2015-2026': f"{m_15_26['CAGR']*100:.2f}%",
            '2019-2026': f"{m_19_26['CAGR']*100:.2f}%",
        })
    df_out = pd.DataFrame(rows)
    df_out.to_csv(os.path.join(HERE, 'experiment_part2_summary.csv'), index=False)
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', 320)
    print(df_out.to_string(index=False))
    print('\nRegime counts for L_3state_calm_200:', L_3state_calm_200.value_counts().to_dict(), f'mean={L_3state_calm_200.mean():.2f}x')
    print('Months where rate_trend_brake triggered (0x):', [str(m.date())[:7] for m in months if state.loc[m, 'rate_trend_brake']])


if __name__ == '__main__':
    main()
