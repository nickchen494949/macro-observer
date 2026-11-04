#!/usr/bin/env python3
"""
run_four_experiments_abcd.py — Clean-Room Backtest of the User's 4 Focused Experiments (A, B, C, D)
====================================================================================================
Tests the exact 4 experiments specified by the user on top of the audited 3-leg engine (3S_G1_1k,
2009-01 .. 2026-09, 213 holding months, T+1 Open execution, 10bp/side single-account turnover cost):

  Experiment A — Unlevered Conviction Concentration (1.0x Total Exposure, Zero Margin):
    - In 3S_G1_1k (50% QQQ[2 stocks] + 25% Tech[1 stock] + 25% SPY[1 stock]), a 3-leg consensus
      month naturally holds 75% Consensus Stock + 25% QQQ #2 Stock.
    - Tests shifting that remaining 25% from QQQ's #2 stock to the #1 Consensus Stock (75% -> 100%)
      ONLY in high-conviction states (e.g., 3-Leg + Sub-Industry Group #1, 24 months), and also
      tests shifting weight on Shadow-Confirmed 2-Leg months (50% -> 75% or 85%), all at 1.0x.
    - Also provides a direct stock-level attribution table comparing the Consensus Stock's return
      vs the QQQ #2 Stock's return in those exact months.

  Experiment B — Upgraded SEP OFF Routing (25% SGOV + 25% Non-Tech Champion + 25% Tech + 25% SPY):
    - Compares 50% SGOV vs (25% SGOV + 25% Ex-IT Non-Tech Champion) during SEP OFF, both standalone
      and combined with Experiment A (unlevered) and Experiment C (burst leverage).

  Experiment C — Tiered Conviction Burst (Small Fixed Grid: 1.50x / 1.75x / 2.00x on 3-Leg + Group #1):
    - Tests scaling ordinary 3-Leg to 1.25x/1.50x, Shadow-Confirmed 2-Leg to 1.25x, and
      3-Leg + Sub-Industry Group #1 (or SOXX #1) to {1.50x, 1.75x, 2.00x}.
    - Tests both standard proportional sleeve scaling AND combined with Experiment A (100% stock
      concentration on 3-Leg + Group #1) and Experiment B (SEP OFF -> 25% SGOV + 25% Ex-IT).

  Experiment D — Single-Stock 2x Daily-Reset Leveraged ETF (Zero Margin Account):
    - Models exact day-by-day compounding (T+1 Open to T'+1 Open) of a 2x daily-reset ETF:
        R_etf,d = 2.0 * r_stock,d - (rf_daily + swap_spread_100bp + expense_115bp + tracking_50bp)/252
      which automatically captures exact daily variance drain / volatility decay (-sigma^2 * T)
      from the true daily price path.
    - Separately tests:
        (D1) Strict Point-in-Time actual US single-stock 2x ETF launch dates (e.g. NVDL 2022-12-13,
             AAPB 2022-08-09, AMDL 2024-03-19, MUU 2024-10-16, PLTU 2024-12-11; 1x stock before launch).
        (D2) Full-history synthetic 2x daily-reset single-stock ETF (2009-2026) to compare daily-reset
             ETF vs monthly-reset margin at identical effective exposure.
"""
import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
SEL_DIR = os.path.join(ROOT, 'outputs', 'core3_stock_selection_audit_20261103')
SPY_DIR = os.path.join(ROOT, 'outputs', 'core3_qqq_spy_g1_audit_20261103')
SEP_SCRIPT_DIR = os.path.join(ROOT, 'research', 'strategy_comparison')

for d in [QQQ_DIR, TECH_DIR, SEL_DIR, SPY_DIR, SEP_SCRIPT_DIR, HERE]:
    if d not in sys.path:
        sys.path.insert(0, d)

import a2_engine as QE
import c2_engine as TE
from run_qqq_spy_g1_audit import (
    simulate_single_sleeve,
    combine_sleeves,
    get_daily_stock_df,
)
from run_consensus_burst_audit import (
    COST_BP,
    load_all_inputs,
    build_monthly_regime_table,
    build_panel_lookups,
    annotate_3leg_ledger,
    compute_dynamic_daily_drawdowns,
    summarize_burst_variant,
)
from run_shadow_industry_and_sector_audit import (
    build_combined_tech_and_semi_panels,
)

# =============================================================================
# Actual US Single-Stock 2x Long ETF Launch Dates (Point-in-Time Verified)
# =============================================================================
ACTUAL_2X_ETF_LAUNCH = {
    'TSLA': '2022-08-09',  # TSLL (Direxion Daily TSLA Bull 1.5x/2x launched Aug 9, 2022)
    'AAPL': '2022-08-09',  # AAPB / AAPU (GraniteShares / Direxion launched Aug 9, 2022)
    'COIN': '2022-08-09',  # CONL (GraniteShares 2x COIN launched Aug 9, 2022)
    'NVDA': '2022-12-13',  # NVDL (GraniteShares 2x Long NVDA Daily ETF launched Dec 13, 2022)
    'META': '2022-12-13',  # FBL / METU (GraniteShares 2x Long META launched Dec 13, 2022)
    'MSFT': '2022-08-09',  # MSFU (Direxion Daily MSFT Bull 2x launched Aug 2022)
    'AMZN': '2022-08-09',  # AMZU (Direxion Daily AMZN Bull 2x launched Aug 2022)
    'GOOGL': '2022-08-09', # GGLL (Direxion Daily GOOGL Bull 2x launched Aug 2022)
    'GOOG': '2022-08-09',
    'NFLX': '2023-09-07',  # NFXL (Direxion Daily NFLX Bull 2x)
    'AMD':  '2024-03-19',  # AMDL (GraniteShares 2x Long AMD Daily ETF launched Mar 19, 2024)
    'AVGO': '2024-06-18',  # AVGU (Direxion Daily AVGO Bull 2x launched Jun 2024)
    'MU':   '2024-10-16',  # MUU (Direxion Daily MU Bull 2x launched Oct 16, 2024)
    'PLTR': '2024-12-11',  # PLTU (Direxion Daily PLTR Bull 2x launched Dec 11, 2024)
    'SMCI': '2024-03-20',  # SMCX
    'MRNA': '2024-08-01',
    'LLY':  '2024-07-17',  # ELIL
}


def compute_exact_daily_reset_2x_etf_monthly_ret(
    tk, utag, st, sym, t_date, next_t_date, rf_monthly, cal_days, spy_daily_c, spy_daily_o,
    lev_mult=2.0, expense_ann=0.0115, swap_spread_ann=0.0100, tracking_drag_ann=0.0050
):
    """
    Computes the exact T+1 Open -> T'+1 Open holding return of a daily-reset `lev_mult` (e.g. 2.0x)
    single-stock ETF using the underlying stock's true daily open and close prices:
      - Day 1 (entry at T+1 Open): r_1 = Close[d_1] / Open[d_1] - 1
      - Day k (k = 2..M, regular holding days): r_k = Close[d_k] / Close[d_{k-1}] - 1
      - Exit morning (exit at T'+1 Open): r_exit = Open[d_exit] / Close[d_M] - 1
      - Each step compounds:
          1 + R_etf,k = max(0.01, 1 + lev_mult * r_k - (lev_mult - 1.0) * daily_drag)
        where daily_drag = (rf_ann + swap_spread_ann + expense_ann + tracking_drag_ann) / 252.
    """
    df_s = get_daily_stock_df(utag, tk, t_date, st, sym, spy_daily_c, spy_daily_o)
    if df_s is None or len(df_s) == 0:
        return None, None

    c_s = df_s['adjclose'].dropna()
    o_s = df_s['adjopen_clean'].dropna()
    e_d = QE.first_td_after(t_date, 1)
    m_dt = t_date + pd.offsets.MonthEnd(1)
    x_d = QE.first_td_after(m_dt, 1)

    hold_days = [d for d in cal_days if (d >= e_d) and (d < x_d) and (d in c_s.index)]
    after_days = [d for d in cal_days if (d >= x_d) and (d in o_s.index)]
    if not hold_days:
        return None, None

    d1 = hold_days[0]
    rf_ann = (1.0 + float(rf_monthly)) ** 12 - 1.0
    daily_drag = (rf_ann + swap_spread_ann + expense_ann + tracking_drag_ann) / 252.0

    sub_rets = []
    o_d1 = o_s.get(d1, np.nan) if o_s is not None else np.nan
    c_d1 = c_s.get(d1, np.nan)
    if pd.notna(o_d1) and o_d1 > 0 and pd.notna(c_d1) and c_d1 > 0:
        r_intraday = float(c_d1 / o_d1 - 1.0)
        sub_rets.append((r_intraday, 1.0))
    else:
        prev_days = [d for d in c_s.index if d <= t_date]
        if prev_days and pd.notna(c_d1):
            r_intraday = float(c_d1 / c_s.loc[prev_days[-1]] - 1.0)
            sub_rets.append((r_intraday, 1.0))

    prev_c = c_d1
    for dk in hold_days[1:]:
        ck = c_s.get(dk, np.nan)
        if pd.notna(ck) and ck > 0 and pd.notna(prev_c) and prev_c > 0:
            rk = float(ck / prev_c - 1.0)
            sub_rets.append((rk, 1.0))
            prev_c = ck

    if after_days:
        d_ex = after_days[0]
        o_ex = o_s.get(d_ex, np.nan) if o_s is not None else np.nan
        if pd.notna(o_ex) and o_ex > 0 and pd.notna(prev_c) and prev_c > 0:
            r_ov = float(o_ex / prev_c - 1.0)
            sub_rets.append((r_ov, 0.0))

    if not sub_rets:
        return None, None

    eq_1x = 1.0
    eq_lev = 1.0
    for rk, drag_w in sub_rets:
        eq_1x *= (1.0 + rk)
        r_lev_step = lev_mult * rk - (lev_mult - 1.0) * daily_drag * drag_w
        eq_lev *= max(0.01, 1.0 + r_lev_step)

    return float(eq_lev - 1.0), float(eq_1x - 1.0)


def simulate_custom_allocation_portfolio(
    L_qqq, L_xlk, L_spy, regime_df, lookups, shadow_lk, extra_sleeves,
    cal_days, spy_daily_c, spy_daily_o, alloc_fn, etf_ret_cache=None
):
    """
    Monthly rebalanced single-account simulator supporting:
      - Custom 1x stock weights (`w_stocks`)
      - Custom 2x daily-reset single-stock ETF weights (`w_etf2x`)
      - SGOV/T-bill cash weight (`w_cash`)
      - Margin borrow fraction (`w_borrow`, charging `r_borrow`)
    """
    ret_map = lookups['ret_map']
    common_ym = list(L_qqq.index)
    prev_drifted_w = {}
    rows = []

    for ym in common_ym:
        r_qqq = L_qqq.loc[ym]
        r_xlk = L_xlk.loc[ym]
        r_spy = L_spy.loc[ym]
        reg_row = regime_df.loc[ym]
        t_date = pd.Timestamp(r_qqq['t_date'])
        s_rows = {k: v.loc[ym] for k, v in extra_sleeves.items()}

        w_stocks, w_etf2x, w_cash, w_borrow, r_cash, r_borrow = alloc_fn(
            ym, r_qqq, r_xlk, r_spy, reg_row, shadow_lk, s_rows
        )

        # Build metadata map for daily drawdown computation
        meta_comb = {}
        for _, r_s in [('qqq', r_qqq), ('xlk', r_xlk), ('spy', r_spy)] + list(s_rows.items()):
            for tk in r_s['weights_dict']:
                if tk not in meta_comb:
                    st, sym = r_s['store_map'].get(tk, ('yahoo', tk))
                    st_base = str(st).split(':')[0]
                    if tk in spy_daily_c.columns:
                        utag_tk = 'spy'
                    elif QE.series(st_base, sym) is not None:
                        utag_tk = 'qqq'
                    else:
                        utag_tk = 'xlk'
                    meta_comb[tk] = (utag_tk, st, sym)

        gross_1x = sum(w_tk * ret_map[(ym, tk)] for tk, w_tk in w_stocks.items() if w_tk > 0)
        gross_2x = 0.0
        effective_stock_w_for_dd = dict(w_stocks)

        for tk, w_e in w_etf2x.items():
            if w_e <= 0:
                continue
            r_etf = etf_ret_cache.get((ym, tk)) if etf_ret_cache is not None else None
            if r_etf is None:
                r_etf = ret_map[(ym, tk)]
                effective_stock_w_for_dd[tk] = effective_stock_w_for_dd.get(tk, 0.0) + w_e
            else:
                effective_stock_w_for_dd[tk] = effective_stock_w_for_dd.get(tk, 0.0) + 2.0 * w_e
            gross_2x += w_e * r_etf

        gross_total = gross_1x + gross_2x + w_cash * r_cash - w_borrow * r_borrow

        curr_pos = {}
        for tk, w_tk in w_stocks.items():
            if w_tk > 0:
                curr_pos[f'1x:{tk}'] = w_tk
        for tk, w_e in w_etf2x.items():
            if w_e > 0:
                curr_pos[f'2xETF:{tk}'] = w_e

        if not prev_drifted_w:
            to = float(sum(abs(v) for v in curr_pos.values()))
        else:
            all_k = set(curr_pos.keys()) | set(prev_drifted_w.keys())
            to = float(sum(abs(curr_pos.get(k, 0.0) - prev_drifted_w.get(k, 0.0)) for k in all_k))

        net_total = (1.0 + gross_total) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross_total

        end_eq = 1.0 + gross_total
        if end_eq > 0:
            prev_drifted_w = {}
            for tk, w_tk in w_stocks.items():
                if w_tk > 0:
                    prev_drifted_w[f'1x:{tk}'] = w_tk * (1.0 + ret_map[(ym, tk)]) / end_eq
            for tk, w_e in w_etf2x.items():
                if w_e > 0:
                    r_e = etf_ret_cache.get((ym, tk), ret_map[(ym, tk)]) if etf_ret_cache else ret_map[(ym, tk)]
                    prev_drifted_w[f'2xETF:{tk}'] = w_e * (1.0 + r_e) / end_eq
        else:
            prev_drifted_w = {}

        notional_exp = float(sum(w_stocks.values()) + 2.0 * sum(w_etf2x.values()))

        rows.append({
            'ym': ym,
            't_date': t_date,
            'gross': gross_total,
            'net': net_total,
            'turnover': to,
            'long_exp': notional_exp,
            'w_cash': w_cash,
            'w_borrow': w_borrow,
            'n_distinct': len(set(list(w_stocks.keys()) + list(w_etf2x.keys()))),
            'max_single_w': max(effective_stock_w_for_dd.values()) if effective_stock_w_for_dd else 0.0,
            'holdings_dict': effective_stock_w_for_dd,
            'meta_map': meta_comb,
            'net_financing_drag': w_borrow * r_borrow - w_cash * r_cash,
        })

    L_port = pd.DataFrame(rows).set_index('ym')
    dd_c56, dd_o2c = compute_dynamic_daily_drawdowns(L_port, cal_days, spy_daily_c, spy_daily_o)
    return L_port, dd_c56, dd_o2c


def classify_month_consensus_and_shadow(ym, r_qqq, r_xlk, r_spy, shadow_lk):
    """
    Returns detailed flags for month `ym`:
      - `is_3leg`: bool
      - `is_2leg`: bool
      - `ov_tk`: overlapping ticker
      - `other_q_tk`: the non-overlapping QQQ ticker (if QQQ is part of the overlap)
      - `is_soxx1`: bool (ov_tk is #1 in SOXX_Strict)
      - `is_subind_grp1`: bool (ov_tk's Sub-Industry Group is #1 in Tech)
      - `is_conf2`: bool (2-leg overlap confirmed by own Sector #1 or SOXX #1)
    """
    q_set = set(r_qqq['weights_dict'].keys())
    t_pick = list(r_xlk['weights_dict'].keys())[0]
    s_pick = list(r_spy['weights_dict'].keys())[0]

    t_in_q = t_pick in q_set
    s_in_q = s_pick in q_set
    t_eq_s = (t_pick == s_pick)

    is_3leg = t_eq_s and t_in_q
    is_2leg = (not is_3leg) and (t_eq_s or t_in_q or s_in_q)
    ov_tk = t_pick if (t_eq_s or t_in_q) else (s_pick if s_in_q else '')
    other_q_list = [x for x in q_set if x != ov_tk]
    other_q_tk = other_q_list[0] if len(other_q_list) == 1 else None

    is_soxx1 = (ov_tk != '') and (shadow_lk['soxx_strict_raw_top1'].get(ym, '') == ov_tk)
    sname = shadow_lk['stock_subind'].get((ym, ov_tk), 'Non_IT')
    sub_grp_rk = shadow_lk['subind_group_rk_mom'].get((ym, sname), 99)
    is_subind_grp1 = (sub_grp_rk == 1)

    sec_rk_raw = shadow_lk['sec_stock_rk_raw'].get((ym, ov_tk), 99)
    sec_rk_sh = shadow_lk['sec_stock_rk_sharpe'].get((ym, ov_tk), 99)

    # Confirmed 2-Leg:
    # Either (a) stock is #1 in its own GICS Sector by both Raw & Sharpe, OR
    #        (b) QQQ==SPY and stock is #1 in its own GICS Sector (Raw #1), OR
    #        (c) QQQ==Tech and stock is SOXX_Strict #1
    is_conf2 = False
    if is_2leg and ov_tk != '':
        if (sec_rk_raw == 1 and sec_rk_sh == 1) or (s_in_q and not t_in_q and sec_rk_raw == 1) or (t_in_q and not s_in_q and is_soxx1):
            is_conf2 = True

    return {
        'is_3leg': is_3leg,
        'is_2leg': is_2leg,
        'ov_tk': ov_tk,
        'other_q_tk': other_q_tk,
        'is_soxx1': is_soxx1,
        'is_subind_grp1': is_subind_grp1,
        'is_conf2': is_conf2,
        'sec_rk_raw': sec_rk_raw,
        'sec_rk_sh': sec_rk_sh,
    }


def main():
    print('=' * 105)
    print('RUNNING THE 4 FOCUSED EXPERIMENTS (A, B, C, D) ON 3S_G1_1k (2009-01 .. 2026-09)')
    print('=' * 105)

    (rf_monthly, cal_days, qqq_panel, tech_panel, spy_panel,
     spy_daily_c, spy_daily_o, c_qqq, c_spy, c_xlk) = load_all_inputs()

    formations = sorted(qqq_panel['t'].unique())
    regime_df = build_monthly_regime_table(formations, c_qqq, c_spy, c_xlk, rf_monthly)
    lookups = build_panel_lookups(qqq_panel, tech_panel, spy_panel, c_spy, cal_days, spy_daily_c)

    (soxx_strict_panel, smh_broad_panel, igv_software_panel,
     hw_storage_panel, shadow_lk) = build_combined_tech_and_semi_panels(qqq_panel, tech_panel, spy_panel)

    spec_sharpe = {'type': 'score', 'score_col': 'sharpe_mom_12_1'}
    spec_raw = {'type': 'score', 'score_col': 'mom_12_1'}

    L_qqq_g1_5 = simulate_single_sleeve(qqq_panel, spec_sharpe, k=2, k_keep=5)
    L_qqq_c3 = simulate_single_sleeve(qqq_panel, spec_sharpe, k=2, k_keep=2)
    L_xlk_c3 = simulate_single_sleeve(tech_panel, spec_raw, k=1, k_keep=1)
    L_spy_g1_3 = simulate_single_sleeve(spy_panel, spec_raw, k=1, k_keep=3)
    L_spy_c3 = simulate_single_sleeve(spy_panel, spec_raw, k=1, k_keep=1)

    L_3s_1k = annotate_3leg_ledger(
        combine_sleeves([(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_g1_3, 0.25)], ['qqq', 'xlk', 'spy']),
        lookups
    )
    L_3s_c3 = annotate_3leg_ledger(
        combine_sleeves([(L_qqq_c3, 0.50), (L_xlk_c3, 0.25), (L_spy_c3, 0.25)], ['qqq', 'xlk', 'spy']),
        lookups
    )

    # Non-Tech Ex-IT Champion sleeves for Experiment B
    spec_exit_raw = {'type': 'ex_it_score', 'score_col': 'mom_12_1'}
    L_exit_raw_g3 = simulate_single_sleeve(spy_panel, spec_exit_raw, k=1, k_keep=3)

    spy_no_it = spy_panel[spy_panel['sector'] != 'Information Technology'].copy()
    sec_rk_no_it = []
    for t_val, g in spy_no_it.groupby('t', sort=True):
        s_moms = g.groupby('sector')['sector_ew_mom_12_1'].first().sort_values(ascending=False)
        rk_map = {sec: i + 1 for i, sec in enumerate(s_moms.index)}
        g_copy = g.copy()
        g_copy['exit_sec_rk_mom'] = g_copy['sector'].map(rk_map)
        sec_rk_no_it.append(g_copy)
    spy_no_it = pd.concat(sec_rk_no_it, ignore_index=True)
    spec_exit_secrot_raw = {'type': 'sector_top', 'n_sec': 1, 'sec_rank_col': 'exit_sec_rk_mom', 'score_col': 'mom_12_1'}
    L_exit_secrot_g3 = simulate_single_sleeve(spy_no_it, spec_exit_secrot_raw, k=1, k_keep=3)

    extra_sleeves = {
        'exit_raw_g3': L_exit_raw_g3,
        'exit_secrot_g3': L_exit_secrot_g3,
    }

    # Control baseline 3S_G1_1k (1.0x always)
    def ctrl_alloc(ym, r_qqq, r_xlk, r_spy, reg, sh, sr):
        w = {}
        for tk, v in r_qqq['weights_dict'].items():
            w[tk] = w.get(tk, 0.0) + 0.50 * v
        for tk, v in r_xlk['weights_dict'].items():
            w[tk] = w.get(tk, 0.0) + 0.25 * v
        for tk, v in r_spy['weights_dict'].items():
            w[tk] = w.get(tk, 0.0) + 0.25 * v
        return w, {}, 0.0, 0.0, 0.0, 0.0

    L_ctrl, d56_ctrl, do2c_ctrl = simulate_custom_allocation_portfolio(
        L_qqq_g1_5, L_xlk_c3, L_spy_g1_3, regime_df, lookups, shadow_lk, extra_sleeves,
        cal_days, spy_daily_c, spy_daily_o, ctrl_alloc
    )
    ref_1k_r = L_ctrl['net']

    # =========================================================================
    # DIAGNOSTIC FOR EXPERIMENT A: CONSENSUS STOCK (75%) VS QQQ #2 STOCK (25%)
    # =========================================================================
    print('\n[Diagnostic A] Comparing Consensus Stock (75% weight) vs QQQ #2 Stock (25% weight) inside 3-Leg Consensus Months...')
    diag_a_rows = []
    for label, L_df in [('3S_G1_1k (QQQ Hold<=5)', L_3s_1k), ('3S_Core3_1a (QQQ Hard Top-2)', L_3s_c3)]:
        c3_df = L_df[L_df['state_main'] == '3_Triple_Consensus'].copy()
        for sub_name, mask_fn in [
            ('All 3-Leg Consensus Months', lambda ym, r: True),
            ('3-Leg + SubInd Group #1 (3-Layer Confirm)', lambda ym, r: (
                shadow_lk['subind_group_rk_mom'].get((ym, shadow_lk['stock_subind'].get((ym, r['ov_tickers']), 'Non_IT')), 99) == 1
            )),
            ('3-Leg + SubInd Group NOT #1 (Lone Outlier)', lambda ym, r: (
                shadow_lk['subind_group_rk_mom'].get((ym, shadow_lk['stock_subind'].get((ym, r['ov_tickers']), 'Non_IT')), 99) > 1
            )),
            ('3-Leg + SOXX_Strict #1 (Pure Semis)', lambda ym, r: shadow_lk['soxx_strict_raw_top1'].get(ym, '') == r['ov_tickers']),
        ]:
            sub_yms = [ym for ym, r in c3_df.iterrows() if mask_fn(ym, r)]
            r_cons = np.array([c3_df.loc[ym, 'ov_stock_ret'] for ym in sub_yms], dtype=float)
            r_qqq2 = np.array([c3_df.loc[ym, 'non_ov_stock_ret'] for ym in sub_yms], dtype=float)
            diff_arr = r_cons - r_qqq2
            n_m = len(sub_yms)
            cagr_cons = float(np.prod(1.0 + r_cons) ** (12.0 / n_m) - 1.0) if n_m > 0 else np.nan
            cagr_qqq2 = float(np.prod(1.0 + r_qqq2) ** (12.0 / n_m) - 1.0) if n_m > 0 else np.nan
            cagr_75_25 = float(np.prod(1.0 + 0.75 * r_cons + 0.25 * r_qqq2) ** (12.0 / n_m) - 1.0) if n_m > 0 else np.nan
            diag_a_rows.append({
                'Engine': label,
                'Slice': sub_name,
                'Months_N': n_m,
                'Consensus_Stock_Mean_1M': float(np.mean(r_cons)),
                'QQQ_2nd_Stock_Mean_1M': float(np.mean(r_qqq2)),
                'Spread_Mean_1M (Cons - QQQ2)': float(np.mean(diff_arr)),
                'Consensus_Stock_Ann_Compounded (100% Weight)': cagr_cons,
                'Standard_75_25_Ann_Compounded': cagr_75_25,
                'QQQ_2nd_Stock_Ann_Compounded': cagr_qqq2,
                'Consensus_Win_Rate': float(np.mean(r_cons > 0)),
                'QQQ_2nd_Win_Rate': float(np.mean(r_qqq2 > 0)),
                'Pct_Months_Cons_Beats_QQQ2': float(np.mean(r_cons > r_qqq2)),
            })

    df_diag_a = pd.DataFrame(diag_a_rows)
    df_diag_a.to_csv(os.path.join(HERE, '11a_expA_concentration_diagnostic.csv'), index=False)
    for _, r in df_diag_a.iterrows():
        print(f"  {r['Engine']:<28} | {r['Slice']:<45} | N={int(r['Months_N']):2d} | "
              f"Cons100%={r['Consensus_Stock_Ann_Compounded (100% Weight)']*100:6.1f}% (Mean {r['Consensus_Stock_Mean_1M']*100:+5.2f}%) | "
              f"75/25={r['Standard_75_25_Ann_Compounded']*100:6.1f}% | "
              f"QQQ#2={r['QQQ_2nd_Stock_Ann_Compounded']*100:6.1f}% (Mean {r['QQQ_2nd_Stock_Mean_1M']*100:+5.2f}%)")

    # =========================================================================
    # EXPERIMENTS A & B: UNLEVERED CONCENTRATION (1.0x) + SEP OFF ROUTING
    # =========================================================================
    print('\n[Experiments A & B] Running Unlevered Concentration (1.0x) and SEP OFF Routing Backtests...')

    def make_exp_ab_rule(conc_mode='none', sep_off_mode='none'):
        def _fn(ym, r_qqq, r_xlk, r_spy, reg, sh, sr):
            if sep_off_mode != 'none' and (not bool(reg['sep_on'])):
                w = {}
                for tk, v in r_xlk['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                for tk, v in r_spy['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                if sep_off_mode == 'sgov50':
                    return w, {}, 0.50, 0.0, float(reg['rf_monthly']), 0.0
                elif sep_off_mode == 'sgov25_exit_raw25':
                    for tk, v in sr['exit_raw_g3']['weights_dict'].items():
                        w[tk] = w.get(tk, 0.0) + 0.25 * v
                    return w, {}, 0.25, 0.0, float(reg['rf_monthly']), 0.0
                elif sep_off_mode == 'sgov25_exit_secrot25':
                    for tk, v in sr['exit_secrot_g3']['weights_dict'].items():
                        w[tk] = w.get(tk, 0.0) + 0.25 * v
                    return w, {}, 0.25, 0.0, float(reg['rf_monthly']), 0.0

            w = {}
            for tk, v in r_qqq['weights_dict'].items():
                w[tk] = w.get(tk, 0.0) + 0.50 * v
            for tk, v in r_xlk['weights_dict'].items():
                w[tk] = w.get(tk, 0.0) + 0.25 * v
            for tk, v in r_spy['weights_dict'].items():
                w[tk] = w.get(tk, 0.0) + 0.25 * v

            info = classify_month_consensus_and_shadow(ym, r_qqq, r_xlk, r_spy, sh)

            if info['is_3leg']:
                tk_c = info['ov_tk']
                if conc_mode in ('grp1_100', 'grp1_100_conf2_75') and info['is_subind_grp1']:
                    w = {tk_c: 1.00}
                elif conc_mode in ('all3_100', 'all3_100_conf2_75'):
                    w = {tk_c: 1.00}
                elif conc_mode == 'soxx_100' and info['is_soxx1']:
                    w = {tk_c: 1.00}
                elif conc_mode == 'grp1_100_other3_85':
                    if info['is_subind_grp1']:
                        w = {tk_c: 1.00}
                    elif info['other_q_tk'] is not None:
                        w = {tk_c: 0.85, info['other_q_tk']: 0.15}

            elif info['is_2leg'] and conc_mode in ('grp1_100_conf2_75', 'all3_100_conf2_75', 'conf2_75_only'):
                if info['is_conf2'] and info['ov_tk'] != '' and info['other_q_tk'] is not None:
                    w[info['ov_tk']] = w.get(info['ov_tk'], 0.0) + w.get(info['other_q_tk'], 0.0)
                    w.pop(info['other_q_tk'], None)

            return w, {}, 0.0, 0.0, 0.0, 0.0
        return _fn

    ab_configs = [
        ('AB_00_Baseline_3S_G1_1k (50/25/25 Always, 1.0x)', 'Baseline_1x', 'none', 'none'),
        # Experiment A alone (1.0x Always, Zero Margin)
        ('ExpA_1a_3Leg+SubIndGrp#1 -> 100% Consensus Stock (1.0x Always)', 'ExpA_Unlev_Conc', 'grp1_100', 'none'),
        ('ExpA_1b_All_3Leg -> 100% Consensus Stock (1.0x Always)', 'ExpA_Unlev_Conc', 'all3_100', 'none'),
        ('ExpA_1c_3Leg+SOXX#1 -> 100% Consensus Stock (1.0x Always)', 'ExpA_Unlev_Conc', 'soxx_100', 'none'),
        ('ExpA_1d_3Leg+Grp#1->100% | Other 3Leg->85% (1.0x Always)', 'ExpA_Unlev_Conc', 'grp1_100_other3_85', 'none'),
        ('ExpA_1e_Confirmed_2Leg -> 75% Concentration Only (1.0x Always)', 'ExpA_Unlev_Conc', 'conf2_75_only', 'none'),
        ('ExpA_1f_3Leg+Grp#1->100% | Confirmed_2Leg->75% (1.0x Always)', 'ExpA_Unlev_Conc', 'grp1_100_conf2_75', 'none'),
        ('ExpA_1g_All_3Leg->100% | Confirmed_2Leg->75% (1.0x Always)', 'ExpA_Unlev_Conc', 'all3_100_conf2_75', 'none'),
        # Experiment B alone (1.0x Always, SEP OFF comparison)
        ('ExpB_1a_SEP_OFF -> 50% SGOV + 25% Tech + 25% SPY (M2_1a)', 'ExpB_SEP_OFF', 'none', 'sgov50'),
        ('ExpB_1b_SEP_OFF -> 25% SGOV + 25% ExIT_Raw[<=3] + 25% Tech + 25% SPY (P4_4a)', 'ExpB_SEP_OFF', 'none', 'sgov25_exit_raw25'),
        ('ExpB_1c_SEP_OFF -> 25% SGOV + 25% ExIT_BestSec[<=3] + 25% Tech + 25% SPY', 'ExpB_SEP_OFF', 'none', 'sgov25_exit_secrot25'),
        # Experiment A + B Combined (Strictly Unlevered <= 1.0x!)
        ('ExpAB_2a_Unlev: SEP_OFF(25%SGOV+25%ExIT) + 3Leg_Grp#1(100% Stock)', 'ExpAB_Unlev_Comb', 'grp1_100', 'sgov25_exit_raw25'),
        ('ExpAB_2b_Unlev: SEP_OFF(25%SGOV+25%ExIT) + 3Leg_Grp#1(100%) + Conf2Leg(75%)', 'ExpAB_Unlev_Comb', 'grp1_100_conf2_75', 'sgov25_exit_raw25'),
        ('ExpAB_2c_Unlev: SEP_OFF(50%SGOV) + 3Leg_Grp#1(100%) + Conf2Leg(75%)', 'ExpAB_Unlev_Comb', 'grp1_100_conf2_75', 'sgov50'),
    ]

    ab_rows = []
    for v_name, fam, cm, sm in ab_configs:
        Lp, d56, do2c = simulate_custom_allocation_portfolio(
            L_qqq_g1_5, L_xlk_c3, L_spy_g1_3, regime_df, lookups, shadow_lk, extra_sleeves,
            cal_days, spy_daily_c, spy_daily_o, make_exp_ab_rule(cm, sm)
        )
        ab_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_ab = pd.DataFrame(ab_rows)
    df_ab.to_csv(os.path.join(HERE, '11b_expAB_unlevered_concentration_and_sepoff.csv'), index=False)
    for _, r in df_ab.iterrows():
        print(f"  {r['Variant']:<78} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"2022={r['Ret_2022']*100:+5.1f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    # =========================================================================
    # EXPERIMENT C & COMBINED A + B + C: TIERED CONVICTION BURST (1.5x / 1.75x / 2.0x)
    # =========================================================================
    print('\n[Experiment C & A+B+C] Running Tiered Conviction Burst Backtests (Fixed Grid: 1.50x / 1.75x / 2.00x)...')

    def make_exp_abc_rule(
        l_conf2=1.0,
        l_ord3=1.25,
        l_grp3=1.75,
        conc_grp3_100=False,
        conc_conf2_75=False,
        sep_off_mode='sgov25_exit_raw25',
        require_lowvol=True,
    ):
        def _fn(ym, r_qqq, r_xlk, r_spy, reg, sh, sr):
            if sep_off_mode != 'none' and (not bool(reg['sep_on'])):
                w = {}
                for tk, v in r_xlk['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                for tk, v in r_spy['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                if sep_off_mode == 'sgov50':
                    return w, {}, 0.50, 0.0, float(reg['rf_monthly']), 0.0
                elif sep_off_mode == 'sgov25_exit_raw25':
                    for tk, v in sr['exit_raw_g3']['weights_dict'].items():
                        w[tk] = w.get(tk, 0.0) + 0.25 * v
                    return w, {}, 0.25, 0.0, float(reg['rf_monthly']), 0.0
                elif sep_off_mode == 'sgov25_exit_secrot25':
                    for tk, v in sr['exit_secrot_g3']['weights_dict'].items():
                        w[tk] = w.get(tk, 0.0) + 0.25 * v
                    return w, {}, 0.25, 0.0, float(reg['rf_monthly']), 0.0

            w_base = {}
            for tk, v in r_qqq['weights_dict'].items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.50 * v
            for tk, v in r_xlk['weights_dict'].items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v
            for tk, v in r_spy['weights_dict'].items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v

            info = classify_month_consensus_and_shadow(ym, r_qqq, r_xlk, r_spy, sh)

            L = 1.0
            low_vol_ok = True
            if require_lowvol:
                low_vol_ok = (
                    bool(reg['sep_on'])
                    and (float(reg['qqq_vol21']) <= 0.30)
                    and (not bool(reg['dm_panic']))
                )

            if info['is_3leg']:
                if conc_grp3_100 and info['is_subind_grp1']:
                    w_base = {info['ov_tk']: 1.00}
                if low_vol_ok:
                    L = l_grp3 if info['is_subind_grp1'] else l_ord3

            elif info['is_2leg'] and info['is_conf2']:
                if conc_conf2_75 and info['ov_tk'] != '' and info['other_q_tk'] is not None:
                    w_base[info['ov_tk']] = w_base.get(info['ov_tk'], 0.0) + w_base.get(info['other_q_tk'], 0.0)
                    w_base.pop(info['other_q_tk'], None)
                if low_vol_ok:
                    L = l_conf2

            w_scaled = {tk: v * L for tk, v in w_base.items()}
            w_borrow = max(0.0, L - 1.0)
            r_borrow = float(reg['borrow_monthly']) if w_borrow > 0 else 0.0
            return w_scaled, {}, 0.0, w_borrow, 0.0, r_borrow
        return _fn

    c_configs = [
        # Reference M3_4a from previous audit
        ('Ref_M3_4a: SEP_OFF(50%SGOV) | SEP_ON+LowVol: All_3Leg=1.50x', 'Ref_M3_4a',
         1.00, 1.50, 1.50, False, False, 'sgov50', True),

        # Upgrade M3_4a with Exp B (25% SGOV + 25% Ex-IT)
        ('ExpBC_01: SEP_OFF(25%SGOV+25%ExIT) | SEP_ON+LowVol: All_3Leg=1.50x', 'ExpBC_Base',
         1.00, 1.50, 1.50, False, False, 'sgov25_exit_raw25', True),

        # --- Experiment C Pure Tiered Grid (Fixed 1.50x / 1.75x / 2.00x on 3-Leg + Group #1) ---
        ('ExpC_1a: SEP_OFF(25%SGOV+25%ExIT) | Ord3Leg=1.25x | 3Leg+Grp#1=1.75x', 'ExpC_Tiered3Leg',
         1.00, 1.25, 1.75, False, False, 'sgov25_exit_raw25', True),
        ('ExpC_1b: SEP_OFF(25%SGOV+25%ExIT) | Ord3Leg=1.50x | 3Leg+Grp#1=1.75x', 'ExpC_Tiered3Leg',
         1.00, 1.50, 1.75, False, False, 'sgov25_exit_raw25', True),
        ('ExpC_1c: SEP_OFF(25%SGOV+25%ExIT) | Ord3Leg=1.25x | 3Leg+Grp#1=2.00x', 'ExpC_Tiered3Leg',
         1.00, 1.25, 2.00, False, False, 'sgov25_exit_raw25', True),
        ('ExpC_1d: SEP_OFF(25%SGOV+25%ExIT) | Ord3Leg=1.50x | 3Leg+Grp#1=2.00x', 'ExpC_Tiered3Leg',
         1.00, 1.50, 2.00, False, False, 'sgov25_exit_raw25', True),

        # --- Experiment C with Confirmed 2-Leg = 1.25x + Tiered 3-Leg (1.50x / 1.75x / 2.00x) ---
        ('ExpBC_2a: SEP_OFF(25%SGOV+25%ExIT) | Conf2=1.25x | Ord3=1.50x | 3Leg+Grp#1=1.50x', 'ExpBC_Conf2_3',
         1.25, 1.50, 1.50, False, False, 'sgov25_exit_raw25', True),
        ('ExpBC_2b: SEP_OFF(25%SGOV+25%ExIT) | Conf2=1.25x | Ord3=1.25x | 3Leg+Grp#1=1.75x', 'ExpBC_Conf2_3',
         1.25, 1.25, 1.75, False, False, 'sgov25_exit_raw25', True),
        ('ExpBC_2c: SEP_OFF(25%SGOV+25%ExIT) | Conf2=1.25x | Ord3=1.50x | 3Leg+Grp#1=1.75x', 'ExpBC_Conf2_3',
         1.25, 1.50, 1.75, False, False, 'sgov25_exit_raw25', True),
        ('ExpBC_2d: SEP_OFF(25%SGOV+25%ExIT) | Conf2=1.25x | Ord3=1.50x | 3Leg+Grp#1=2.00x', 'ExpBC_Conf2_3',
         1.25, 1.50, 2.00, False, False, 'sgov25_exit_raw25', True),
        ('ExpBC_2e: SEP_OFF(50%SGOV) | Conf2=1.25x | Ord3=1.50x | 3Leg+Grp#1=1.75x', 'ExpBC_Conf2_3',
         1.25, 1.50, 1.75, False, False, 'sgov50', True),
        ('ExpBC_2f: SEP_OFF(50%SGOV) | Conf2=1.25x | Ord3=1.50x | 3Leg+Grp#1=2.00x', 'ExpBC_Conf2_3',
         1.25, 1.50, 2.00, False, False, 'sgov50', True),

        # --- Full Combination A + B + C (Concentration + SEP OFF Ex-IT + Tiered Leverage) ---
        ('ExpABC_3a: A(100%Grp#1)+B(ExIT)+C(Conf2=1.25x, Ord3=1.50x, Grp#1=1.50x)', 'ExpABC_Full',
         1.25, 1.50, 1.50, True, False, 'sgov25_exit_raw25', True),
        ('ExpABC_3b: A(100%Grp#1)+B(ExIT)+C(Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x)', 'ExpABC_Full',
         1.25, 1.50, 1.75, True, False, 'sgov25_exit_raw25', True),
        ('ExpABC_3c: A(100%Grp#1)+B(ExIT)+C(Conf2=1.25x, Ord3=1.50x, Grp#1=2.00x)', 'ExpABC_Full',
         1.25, 1.50, 2.00, True, False, 'sgov25_exit_raw25', True),
        ('ExpABC_3d: A(100%Grp#1 + 75%Conf2)+B(ExIT)+C(Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x)', 'ExpABC_Full',
         1.25, 1.50, 1.75, True, True, 'sgov25_exit_raw25', True),
        ('ExpABC_3e: A(100%Grp#1 + 75%Conf2)+B(ExIT)+C(Conf2=1.25x, Ord3=1.50x, Grp#1=2.00x)', 'ExpABC_Full',
         1.25, 1.50, 2.00, True, True, 'sgov25_exit_raw25', True),
        ('ExpABC_3f_UncondLev: A(100%Grp#1 + 75%Conf2)+B(ExIT)+C(Conf2=1.25x, Ord3=1.50x, Grp#1=2.00x, NoVolGate)', 'ExpABC_Full',
         1.25, 1.50, 2.00, True, True, 'sgov25_exit_raw25', False),
    ]

    c_rows = []
    for (v_name, fam, lc2, lo3, lg3, cg3, cc2, sm, rlv) in c_configs:
        Lp, d56, do2c = simulate_custom_allocation_portfolio(
            L_qqq_g1_5, L_xlk_c3, L_spy_g1_3, regime_df, lookups, shadow_lk, extra_sleeves,
            cal_days, spy_daily_c, spy_daily_o,
            make_exp_abc_rule(lc2, lo3, lg3, cg3, cc2, sm, rlv)
        )
        c_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_c = pd.DataFrame(c_rows)
    df_c.to_csv(os.path.join(HERE, '12_expC_and_ABC_tiered_burst.csv'), index=False)
    for _, r in df_c.iterrows():
        print(f"  {r['Variant']:<88} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"AvgExp={r['Avg_Gross_Exp']:4.2f}x | 2022={r['Ret_2022']*100:+5.1f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    # =========================================================================
    # EXPERIMENT D: SINGLE-STOCK 2x DAILY-RESET ETF (ZERO MARGIN ACCOUNT)
    # =========================================================================
    print('\n[Experiment D] Precomputing Exact Daily-Reset 2x Single-Stock ETF Monthly Returns (with Vol Decay + Fees)...')
    etf_ret_cache = {}
    etf_audit_rows = []
    common_ym = list(L_qqq_g1_5.index)

    for idx_i, ym in enumerate(common_ym):
        r_qqq = L_qqq_g1_5.loc[ym]
        r_xlk = L_xlk_c3.loc[ym]
        r_spy = L_spy_g1_3.loc[ym]
        info = classify_month_consensus_and_shadow(ym, r_qqq, r_xlk, r_spy, shadow_lk)
        if not (info['is_3leg'] or info['is_2leg']):
            continue

        t_date = pd.Timestamp(r_qqq['t_date'])
        next_t_date = pd.Timestamp(L_qqq_g1_5.loc[common_ym[idx_i + 1], 't_date']) if (idx_i + 1 < len(common_ym)) else (t_date + pd.offsets.MonthEnd(1))
        rf_m = float(regime_df.loc[ym, 'rf_monthly'])

        tk = info['ov_tk']
        if tk == '':
            continue

        # Metadata for daily price lookup
        if (ym, tk) not in lookups['meta_map']:
            continue
        utag, (st, sym) = lookups['meta_map'][(ym, tk)]

        r_2x, r_1x = compute_exact_daily_reset_2x_etf_monthly_ret(
            tk, utag, st, sym, t_date, next_t_date, rf_m, cal_days, spy_daily_c, spy_daily_o
        )
        if r_2x is not None:
            etf_ret_cache[(ym, tk)] = r_2x
            launch_dt = ACTUAL_2X_ETF_LAUNCH.get(tk)
            pit_avail = (launch_dt is not None) and (pd.Timestamp(t_date) >= pd.Timestamp(launch_dt))
            if info['is_3leg']:
                naive_2x = 2.0 * lookups['ret_map'][(ym, tk)]
                etf_audit_rows.append({
                    'ym': ym,
                    't_date': t_date.strftime('%Y-%m-%d'),
                    'ticker': tk,
                    'subind_group_is_1': info['is_subind_grp1'],
                    'actual_2x_etf_launch': launch_dt or 'None',
                    'pit_2x_etf_available': pit_avail,
                    'stock_1x_ret': lookups['ret_map'][(ym, tk)],
                    'naive_2x_ret_wrong': naive_2x,
                    'true_daily_reset_2x_etf_ret': r_2x,
                    'daily_reset_compound_minus_naive_2x': r_2x - naive_2x,
                })

    df_etf_audit = pd.DataFrame(etf_audit_rows)
    df_etf_audit.to_csv(os.path.join(HERE, '13b_expD_single_stock_2x_etf_monthly_audit.csv'), index=False)

    def make_exp_d_rule(
        trigger_mode='grp1_only',
        etf_weight_in_3leg=0.50,
        strict_pit_launch=True,
        sep_off_mode='sgov25_exit_raw25',
    ):
        def _fn(ym, r_qqq, r_xlk, r_spy, reg, sh, sr):
            if sep_off_mode != 'none' and (not bool(reg['sep_on'])):
                w = {}
                for tk, v in r_xlk['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                for tk, v in r_spy['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                if sep_off_mode == 'sgov50':
                    return w, {}, 0.50, 0.0, float(reg['rf_monthly']), 0.0
                elif sep_off_mode == 'sgov25_exit_raw25':
                    for tk, v in sr['exit_raw_g3']['weights_dict'].items():
                        w[tk] = w.get(tk, 0.0) + 0.25 * v
                    return w, {}, 0.25, 0.0, float(reg['rf_monthly']), 0.0

            w_1x = {}
            for tk, v in r_qqq['weights_dict'].items():
                w_1x[tk] = w_1x.get(tk, 0.0) + 0.50 * v
            for tk, v in r_xlk['weights_dict'].items():
                w_1x[tk] = w_1x.get(tk, 0.0) + 0.25 * v
            for tk, v in r_spy['weights_dict'].items():
                w_1x[tk] = w_1x.get(tk, 0.0) + 0.25 * v

            low_vol_ok = (
                bool(reg['sep_on'])
                and (float(reg['qqq_vol21']) <= 0.30)
                and (not bool(reg['dm_panic']))
            )
            if not low_vol_ok:
                return w_1x, {}, 0.0, 0.0, 0.0, 0.0

            w_2x = {}
            t_date = pd.Timestamp(r_qqq['t_date'])
            info = classify_month_consensus_and_shadow(ym, r_qqq, r_xlk, r_spy, sh)

            if info['is_3leg']:
                tk_c = info['ov_tk']
                launch_dt = ACTUAL_2X_ETF_LAUNCH.get(tk_c)
                can_use_etf = (not strict_pit_launch) or (launch_dt is not None and t_date >= pd.Timestamp(launch_dt))
                should_trigger = (trigger_mode in ('all_3leg', 'grp1_plus_conf2')) or (trigger_mode == 'grp1_only' and info['is_subind_grp1'])

                if should_trigger and can_use_etf and ((ym, tk_c) in etf_ret_cache):
                    if etf_weight_in_3leg >= 0.999:
                        w_1x = {}
                        w_2x = {tk_c: 1.00}
                    elif etf_weight_in_3leg >= 0.749:
                        w_1x[tk_c] = max(0.0, w_1x.get(tk_c, 0.75) - 0.75)
                        if w_1x.get(tk_c, 0.0) <= 1e-9:
                            w_1x.pop(tk_c, None)
                        w_2x = {tk_c: 0.75}
                    else:
                        w_1x[tk_c] = max(0.0, w_1x.get(tk_c, 0.75) - 0.50)
                        w_2x = {tk_c: 0.50}

            elif info['is_2leg'] and info['is_conf2'] and trigger_mode == 'grp1_plus_conf2':
                ov_tk = info['ov_tk']
                launch_dt = ACTUAL_2X_ETF_LAUNCH.get(ov_tk)
                can_use_etf = (not strict_pit_launch) or (launch_dt is not None and t_date >= pd.Timestamp(launch_dt))
                if can_use_etf and ((ym, ov_tk) in etf_ret_cache):
                    w_1x[ov_tk] = max(0.0, w_1x.get(ov_tk, 0.50) - 0.25)
                    w_2x = {ov_tk: 0.25}

            return w_1x, w_2x, 0.0, 0.0, 0.0, 0.0
        return _fn

    d_configs = [
        # D1: Strictly PIT Actual Single-Stock 2x ETF Launch Dates (Post-Aug 2022 only; 1x stock prior to launch)
        ('ExpD_1a_StrictPIT_Launch: 3Leg+Grp#1 -> 50% 2xETF (Eff 1.50x, Zero Margin)', 'ExpD_StrictPIT_2xETF',
         'grp1_only', 0.50, True, 'sgov25_exit_raw25'),
        ('ExpD_1b_StrictPIT_Launch: 3Leg+Grp#1 -> 75% 2xETF (Eff 1.75x, Zero Margin)', 'ExpD_StrictPIT_2xETF',
         'grp1_only', 0.75, True, 'sgov25_exit_raw25'),
        ('ExpD_1c_StrictPIT_Launch: 3Leg+Grp#1 -> 100% 2xETF (Eff 2.00x, Zero Margin)', 'ExpD_StrictPIT_2xETF',
         'grp1_only', 1.00, True, 'sgov25_exit_raw25'),
        ('ExpD_1d_StrictPIT_Launch: All_3Leg(75% 2xETF) + Conf2Leg(25% 2xETF)', 'ExpD_StrictPIT_2xETF',
         'grp1_plus_conf2', 0.75, True, 'sgov25_exit_raw25'),

        # D2: Full-History Daily-Reset 2x Single-Stock ETF Simulation (2009-2026, with Vol Decay + 2.65%/yr Drag)
        ('ExpD_2a_FullSim_DailyReset2x: 3Leg+Grp#1 -> 50% 2xETF (Eff 1.50x, Zero Margin)', 'ExpD_FullSim_2xETF',
         'grp1_only', 0.50, False, 'sgov25_exit_raw25'),
        ('ExpD_2b_FullSim_DailyReset2x: 3Leg+Grp#1 -> 75% 2xETF (Eff 1.75x, Zero Margin)', 'ExpD_FullSim_2xETF',
         'grp1_only', 0.75, False, 'sgov25_exit_raw25'),
        ('ExpD_2c_FullSim_DailyReset2x: 3Leg+Grp#1 -> 100% 2xETF (Eff 2.00x, Zero Margin)', 'ExpD_FullSim_2xETF',
         'grp1_only', 1.00, False, 'sgov25_exit_raw25'),
        ('ExpD_2d_FullSim_DailyReset2x: All_3Leg(75% 2xETF) + Conf2Leg(25% 2xETF)', 'ExpD_FullSim_2xETF',
         'grp1_plus_conf2', 0.75, False, 'sgov25_exit_raw25'),
    ]

    d_rows = []
    for v_name, fam, tm, ew, pit_l, sm in d_configs:
        Lp, d56, do2c = simulate_custom_allocation_portfolio(
            L_qqq_g1_5, L_xlk_c3, L_spy_g1_3, regime_df, lookups, shadow_lk, extra_sleeves,
            cal_days, spy_daily_c, spy_daily_o,
            make_exp_d_rule(tm, ew, pit_l, sm),
            etf_ret_cache=etf_ret_cache
        )
        d_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_d = pd.DataFrame(d_rows)
    df_d.to_csv(os.path.join(HERE, '13_expD_single_stock_2x_etf_backtests.csv'), index=False)
    for _, r in df_d.iterrows():
        print(f"  {r['Variant']:<88} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"AvgExp={r['Avg_Gross_Exp']:4.2f}x | 2022={r['Ret_2022']*100:+5.1f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    print('\nAll Experiments A, B, C, D completed and saved.')


if __name__ == '__main__':
    main()
