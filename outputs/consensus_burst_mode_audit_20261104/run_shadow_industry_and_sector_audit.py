#!/usr/bin/env python3
"""
run_shadow_industry_and_sector_audit.py — Clean-Room Audit of Shadow Industry/Sector Confirmers
(`Broad + Sector + Industry`) vs Non-Tech Sector Champion Legs vs 5-Leg Semiconductor Stacking
================================================================================================
Tests the user's two-part hypothesis across 2009-01 .. 2026-09 (213 holding months):

  1. Priority #1 (Shadow Confirmers — Zero Change to Base 50% QQQ + 25% Tech + 25% SPY Capital):
       - Builds strictly PIT Sub-Industry & Sector Shadow Champions at every formation date t:
           * `SOXX_Strict`: Pure GICS Semiconductors & Semiconductor Equipment (S&P 500 + NDX)
           * `SMH_Broad`: Semiconductors + Memory/Storage (`SNDK, WDC, STX`) + EDA (`SNPS, CDNS`)
           * `IGV_Software`: Systems & Application Software + Internet Services
           * `Tech_Hardware`: Technology Hardware, Storage, Networking & Electronic Equipment
           * 10 Non-Tech GICS Sector Champions: `XLE` (Energy), `XLV` (Health Care), `XLI` (Industrials),
             `XLF` (Financials), `XLY` (Consumer Discretionary), `XLU` (Utilities), `XLC` (Comm Services),
             `XLB` (Materials), `XLP` (Consumer Staples), `XLRE` (Real Estate)
       - Tests whether adding Layer 3 (`Industry / Sub-Industry Confirmation`) on top of 3-Leg and
         2-Leg Consensus improves next-1m return, win rate, and Sharpe across BOTH 2009-2018 and 2019-2026:
           * Dimension A: Stock is 3-Leg Consensus + `#1` in `SOXX_Strict` / `SMH_Broad` / `Software`
           * Dimension B: Stock is 3-Leg Consensus + `#1` in its Sub-Industry by BOTH `Raw Momentum`
             AND `Sharpe-Momentum` (Cross-Metric Industry Champion)
           * Dimension C: Stock is 3-Leg Consensus + its Sub-Industry Group (`SOXX` vs `Software` vs `Hardware`)
             has the `#1` Group Momentum inside Tech AND Tech is a Top-2 Sector in S&P 500
             (`Broad + Sector Group + Industry Group` Triple Layer Confirmation)
           * Dimension D: Upgrading `2-Leg Overlap (QQQ == SPY or QQQ == Tech)` into "Shadow 3-Leg Consensus"
             when confirmed by its own Sector/Sub-Industry Shadow Champion (`XLV #1`, `XLY #1`, `SOXX #1`, etc.).

  2. Priority #2 (True Non-Tech Sector Champion Leg vs 5-Leg Semiconductor-Stacked Strawman):
       - Evaluates standalone 2009-2026 performance of every Sector & Sub-Industry Champion sleeve.
       - Compares:
           * The "Bad Strawman" 5-Leg Semiconductor-Stacked Portfolio (`QQQ + XLK + SOXX + SMH + SPY`)
           * 4-Leg Diversified Portfolios adding a Dedicated Non-Tech Sector Champion (`Ex-IT Best Sector -> Top-1`
             or `Ex-IT Raw/Sharpe Top-1`)
           * 3-Leg Pure Split (`50% QQQ + 25% Tech + 25% Ex-IT Non-Tech`) vs `3S_G1_1k` (`50% QQQ + 25% Tech + 25% SPY`,
             showing why `SPY` acts as an automatic dynamic switch between Tech Confirmer and Non-Tech Champion!)
           * Dynamic Regime Routing to Non-Tech Champion + SGOV when `SEP == OFF` or when Non-Tech Sector leads Tech.
"""
import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
SEL_DIR = os.path.join(ROOT, 'outputs', 'core3_stock_selection_audit_20261103')
SPY_DIR = os.path.join(ROOT, 'outputs', 'core3_qqq_spy_g1_audit_20261103')
SEP_SCRIPT_DIR = os.path.join(ROOT, 'research', 'strategy_comparison')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)
sys.path.insert(0, SEL_DIR)
sys.path.insert(0, SPY_DIR)
sys.path.insert(0, SEP_SCRIPT_DIR)
sys.path.insert(0, HERE)

import a2_engine as QE
import c2_engine as TE
from run_qqq_spy_g1_audit import (
    simulate_single_sleeve,
    combine_sleeves,
)
from run_consensus_burst_audit import (
    load_all_inputs,
    build_monthly_regime_table,
    build_panel_lookups,
    annotate_3leg_ledger,
    summarize_bucket_rows,
    simulate_dynamic_portfolio,
    summarize_burst_variant,
)

# =============================================================================
# 1. Strictly Point-in-Time Tech Sub-Industry Classification (`SOXX`, `SMH`, `Software`, `Hardware`)
# =============================================================================
# Pure GICS Semiconductors & Semiconductor Equipment (S&P 500 + Nasdaq-100 historical & current constituents)
SOXX_STRICT_TICKERS = {
    'ADI', 'ALAB', 'ALTR', 'AMAT', 'AMD', 'ARM', 'ASML', 'ATML', 'AVGO', 'BRCM',
    'ENPH', 'FSLR', 'GFS', 'INTC', 'IPGP', 'KLAC', 'LLTC', 'LRCX', 'LSI', 'MCHP',
    'MPWR', 'MRVL', 'MU', 'MXIM', 'NSM', 'NVDA', 'NVLS', 'NXPI', 'ON', 'PMCS',
    'Q', 'QCOM', 'QRVO', 'SEDG', 'SUNEQ', 'SWKS', 'TER', 'TXN', 'WFR', 'XLNX',
}

# Broad Semiconductor / Memory / EDA Ecosystem (adds NAND/HDD Memory & Storage `SNDK, WDC, STX` + EDA `SNPS, CDNS`)
SMH_BROAD_TICKERS = SOXX_STRICT_TICKERS | {'SNDK', 'WDC', 'STX', 'SNPS', 'CDNS'}

# Storage & Hardware / Networking / EMS inside IT
HARDWARE_STORAGE_TICKERS = {
    'A', 'AAPL', 'ANET', 'APH', 'CIEN', 'COHR', 'CSCO', 'DELL', 'EMC', 'FFIV',
    'FLEX', 'FLIR', 'GLW', 'HPE', 'HPQ', 'HRS', 'IPGP', 'JAVA', 'JBL', 'JNPR',
    'KEYS', 'LITE', 'LOGI', 'LXK', 'MOLX', 'MSI', 'NTAP', 'QLGC', 'ROP', 'SMCI',
    'SNDK', 'STX', 'TDY', 'TEL', 'TLAB', 'TRMB', 'VIAV', 'WDC', 'XRX', 'ZBRA',
}


def get_it_subindustry(tk):
    if tk in SOXX_STRICT_TICKERS:
        return 'Semiconductors_SOXX'
    elif tk in {'SNDK', 'WDC', 'STX', 'NTAP', 'EMC', 'QLGC'}:
        return 'Memory_Storage'
    elif tk in HARDWARE_STORAGE_TICKERS:
        return 'Hardware_Networking'
    else:
        return 'Software_Services'


def build_combined_tech_and_semi_panels(qqq_panel, tech_panel, spy_panel):
    """
    Builds specialized monthly candidate panels for:
      1. `soxx_strict_panel`: PIT S&P 500 IT + Nasdaq-100 Semiconductor & Semi Equipment stocks
      2. `smh_broad_panel`: `soxx_strict` + Memory/Storage (`SNDK, WDC, STX`) + EDA (`SNPS, CDNS`)
      3. `igv_software_panel`: PIT S&P 500 IT Software & Services stocks
      4. `hw_storage_panel`: PIT S&P 500 IT Hardware, Storage & Networking stocks
      5. `sector_panels[sec_name]`: PIT S&P 500 stocks in each of the 11 GICS sectors
    Also computes at each formation date `t`:
      - Sub-industry equal-weighted `mom_12_1` and `sharpe_mom_12_1` inside Tech (`Semis_SOXX`,
        `Memory_Storage`, `Software_Services`, `Hardware_Networking`) and their group ranks (`1..4`).
      - Stock rank within its Sub-Industry by BOTH `mom_12_1` (`subind_rk_raw`) and `sharpe_mom_12_1` (`subind_rk_sharpe`).
      - Stock rank within its GICS Sector by BOTH `mom_12_1` (`sec_stock_rk_raw`) and `sharpe_mom_12_1` (`sec_stock_rk_sharpe`).
    """
    # Combine tech_panel with any NDX-only semiconductor/tech stocks from qqq_panel
    cols_common = ['t', 'ticker', 'mom_12_1', 'mom_6_1', 'vol_12_1', 'sharpe_mom_12_1', 'hold_ret', 'store', 'sym']
    tp_sub = tech_panel[cols_common].copy()
    qp_sub = qqq_panel[cols_common].copy()

    # Union at each formation date t (preferring tech_panel row if ticker is in both)
    combined_it = pd.concat([tp_sub, qp_sub], ignore_index=True)
    combined_it = combined_it.drop_duplicates(subset=['t', 'ticker'], keep='first').copy()
    combined_it['subind'] = combined_it['ticker'].apply(get_it_subindustry)

    soxx_strict_panel = combined_it[combined_it['ticker'].isin(SOXX_STRICT_TICKERS)].copy()
    smh_broad_panel = combined_it[combined_it['ticker'].isin(SMH_BROAD_TICKERS)].copy()
    igv_software_panel = tech_panel[tech_panel['ticker'].apply(get_it_subindustry) == 'Software_Services'].copy()
    hw_storage_panel = tech_panel[tech_panel['ticker'].isin(HARDWARE_STORAGE_TICKERS)].copy()

    # Build lookup of Shadow Champions & Group Ranks at every formation month `ym`
    shadow_lk = {
        'soxx_strict_raw_top1': {},
        'soxx_strict_sharpe_top1': {},
        'soxx_strict_raw_top2': {},
        'smh_broad_raw_top1': {},
        'smh_broad_sharpe_top1': {},
        'subind_rk_raw': {},
        'subind_rk_sharpe': {},
        'subind_group_rk_mom': {},
        'subind_group_rk_sharpe': {},
        'sec_stock_rk_raw': {},
        'sec_stock_rk_sharpe': {},
        'sec_group_rk_mom': {},
        'sec_group_rk_sharpe': {},
        'stock_sector': {},
        'stock_subind': {},
        'best_exit_sector_mom': {},
        'tech_sector_mom': {},
    }

    # 1. Sub-industry rankings at each formation date t
    for t_val, g in combined_it.groupby('t', sort=True):
        ym = (pd.Timestamp(t_val) + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        g_valid = g[g['mom_12_1'].notna() & g['hold_ret'].notna()].copy()

        # SOXX Strict Champions
        g_soxx = g_valid[g_valid['ticker'].isin(SOXX_STRICT_TICKERS)]
        if not g_soxx.empty:
            s_raw = g_soxx.sort_values(['mom_12_1', 'ticker'], ascending=[False, True])
            s_sh = g_soxx.sort_values(['sharpe_mom_12_1', 'ticker'], ascending=[False, True])
            shadow_lk['soxx_strict_raw_top1'][ym] = s_raw['ticker'].iloc[0]
            shadow_lk['soxx_strict_raw_top2'][ym] = set(s_raw['ticker'].iloc[:2])
            shadow_lk['soxx_strict_sharpe_top1'][ym] = s_sh['ticker'].iloc[0]

        # SMH Broad Champions
        g_smh = g_valid[g_valid['ticker'].isin(SMH_BROAD_TICKERS)]
        if not g_smh.empty:
            s_raw = g_smh.sort_values(['mom_12_1', 'ticker'], ascending=[False, True])
            s_sh = g_smh.sort_values(['sharpe_mom_12_1', 'ticker'], ascending=[False, True])
            shadow_lk['smh_broad_raw_top1'][ym] = s_raw['ticker'].iloc[0]
            shadow_lk['smh_broad_sharpe_top1'][ym] = s_sh['ticker'].iloc[0]

        # Within each IT sub-industry (on S&P IT + NDX IT): stock ranks and group momentum
        sub_grp_mom = {}
        sub_grp_sh = {}
        for sub_name, g_sub in g_valid.groupby('subind'):
            sub_grp_mom[sub_name] = float(g_sub['mom_12_1'].mean())
            sub_grp_sh[sub_name] = float(g_sub['sharpe_mom_12_1'].mean())
            sr_raw = g_sub.sort_values(['mom_12_1', 'ticker'], ascending=[False, True]).reset_index(drop=True)
            sr_sh = g_sub.sort_values(['sharpe_mom_12_1', 'ticker'], ascending=[False, True]).reset_index(drop=True)
            for idx, tk in enumerate(sr_raw['ticker']):
                shadow_lk['subind_rk_raw'][(ym, tk)] = idx + 1
                shadow_lk['stock_subind'][(ym, tk)] = sub_name
            for idx, tk in enumerate(sr_sh['ticker']):
                shadow_lk['subind_rk_sharpe'][(ym, tk)] = idx + 1

        # Rank sub-industries 1..4 by group mean mom_12_1 and sharpe_mom_12_1
        for rk_i, (sname, _) in enumerate(sorted(sub_grp_mom.items(), key=lambda x: -x[1])):
            shadow_lk['subind_group_rk_mom'][(ym, sname)] = rk_i + 1
        for rk_i, (sname, _) in enumerate(sorted(sub_grp_sh.items(), key=lambda x: -x[1])):
            shadow_lk['subind_group_rk_sharpe'][(ym, sname)] = rk_i + 1

    # 2. Sector-level rankings across all 11 GICS sectors in spy_panel
    for t_val, g in spy_panel.groupby('t', sort=True):
        ym = (pd.Timestamp(t_val) + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        g_valid = g[g['mom_12_1'].notna() & g['hold_ret'].notna()].copy()

        exit_sec_moms = []
        for sec_name, g_sec in g_valid.groupby('sector'):
            sec_rk_m = int(g_sec['sector_rank_mom'].iloc[0])
            sec_rk_s = int(g_sec['sector_rank_sharpe'].iloc[0])
            sec_ew_m = float(g_sec['sector_ew_mom_12_1'].iloc[0])
            if sec_name == 'Information Technology':
                shadow_lk['tech_sector_mom'][ym] = sec_ew_m
            else:
                exit_sec_moms.append(sec_ew_m)

            sr_raw = g_sec.sort_values(['mom_12_1', 'ticker'], ascending=[False, True]).reset_index(drop=True)
            sr_sh = g_sec.sort_values(['sharpe_mom_12_1', 'ticker'], ascending=[False, True]).reset_index(drop=True)
            for idx, tk in enumerate(sr_raw['ticker']):
                shadow_lk['sec_stock_rk_raw'][(ym, tk)] = idx + 1
                shadow_lk['stock_sector'][(ym, tk)] = sec_name
                shadow_lk['sec_group_rk_mom'][(ym, tk)] = sec_rk_m
                shadow_lk['sec_group_rk_sharpe'][(ym, tk)] = sec_rk_s
            for idx, tk in enumerate(sr_sh['ticker']):
                shadow_lk['sec_stock_rk_sharpe'][(ym, tk)] = idx + 1

        shadow_lk['best_exit_sector_mom'][ym] = max(exit_sec_moms) if exit_sec_moms else 0.0

    return soxx_strict_panel, smh_broad_panel, igv_software_panel, hw_storage_panel, shadow_lk


# =============================================================================
# 2. Main Execution Pipeline
# =============================================================================
def main():
    print('=' * 105)
    print('RUNNING SHADOW INDUSTRY/SECTOR CONFIRMER & NON-TECH SECTOR CHAMPION AUDIT (2009-01 .. 2026-09)')
    print('=' * 105)

    (rf_monthly, cal_days, qqq_panel, tech_panel, spy_panel,
     spy_daily_c, spy_daily_o, c_qqq, c_spy, c_xlk) = load_all_inputs()

    formations = sorted(qqq_panel['t'].unique())
    regime_df = build_monthly_regime_table(formations, c_qqq, c_spy, c_xlk, rf_monthly)
    lookups = build_panel_lookups(qqq_panel, tech_panel, spy_panel, c_spy, cal_days, spy_daily_c)

    (soxx_strict_panel, smh_broad_panel, igv_software_panel,
     hw_storage_panel, shadow_lk) = build_combined_tech_and_semi_panels(qqq_panel, tech_panel, spy_panel)

    # Base Sleeves
    spec_sharpe = {'type': 'score', 'score_col': 'sharpe_mom_12_1'}
    spec_raw = {'type': 'score', 'score_col': 'mom_12_1'}

    L_qqq_g1_5 = simulate_single_sleeve(qqq_panel, spec_sharpe, k=2, k_keep=5)
    L_qqq_c3 = simulate_single_sleeve(qqq_panel, spec_sharpe, k=2, k_keep=2)
    L_xlk_c3 = simulate_single_sleeve(tech_panel, spec_raw, k=1, k_keep=1)
    L_spy_g1_3 = simulate_single_sleeve(spy_panel, spec_raw, k=1, k_keep=3)
    L_spy_c3 = simulate_single_sleeve(spy_panel, spec_raw, k=1, k_keep=1)

    # Base 3-Leg Ledgers
    L_3s_1k = annotate_3leg_ledger(
        combine_sleeves([(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_g1_3, 0.25)], ['qqq', 'xlk', 'spy']),
        lookups
    )
    L_3s_1a = annotate_3leg_ledger(
        combine_sleeves([(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_c3, 0.25)], ['qqq', 'xlk', 'spy']),
        lookups
    )
    L_3s_c3 = annotate_3leg_ledger(
        combine_sleeves([(L_qqq_c3, 0.50), (L_xlk_c3, 0.25), (L_spy_c3, 0.25)], ['qqq', 'xlk', 'spy']),
        lookups
    )

    # =========================================================================
    # PART 1: PRIORITY #1 — SHADOW INDUSTRY / SECTOR CONFIRMATION DIAGNOSTIC TABLE
    # =========================================================================
    print('\n[Part 1/4] Building Priority #1 Shadow Industry / Sector Confirmer Diagnostic Table...')

    def enrich_with_shadow_signals(L_df):
        L = L_df.copy()
        is_soxx_raw1 = []
        is_soxx_sh1 = []
        is_smh_raw1 = []
        is_smh_sh1 = []
        subind_name_l = []
        subind_rk_raw_l = []
        subind_rk_sh_l = []
        subind_grp_rk_l = []
        sec_rk_raw_l = []
        sec_rk_sh_l = []
        sec_grp_rk_l = []
        qqq_rk_l = []
        spy_rk_l = []

        for ym, row in L.iterrows():
            ov_tks = [x for x in row['ov_tickers'].split('|') if x]
            tk = ov_tks[0] if ov_tks else ''
            is_soxx_raw1.append(tk != '' and shadow_lk['soxx_strict_raw_top1'].get(ym, '') == tk)
            is_soxx_sh1.append(tk != '' and shadow_lk['soxx_strict_sharpe_top1'].get(ym, '') == tk)
            is_smh_raw1.append(tk != '' and shadow_lk['smh_broad_raw_top1'].get(ym, '') == tk)
            is_smh_sh1.append(tk != '' and shadow_lk['smh_broad_sharpe_top1'].get(ym, '') == tk)

            sname = shadow_lk['stock_subind'].get((ym, tk), 'Non_IT')
            subind_name_l.append(sname)
            subind_rk_raw_l.append(shadow_lk['subind_rk_raw'].get((ym, tk), 99))
            subind_rk_sh_l.append(shadow_lk['subind_rk_sharpe'].get((ym, tk), 99))
            subind_grp_rk_l.append(shadow_lk['subind_group_rk_mom'].get((ym, sname), 99))

            sec_rk_raw_l.append(shadow_lk['sec_stock_rk_raw'].get((ym, tk), 99))
            sec_rk_sh_l.append(shadow_lk['sec_stock_rk_sharpe'].get((ym, tk), 99))
            sec_grp_rk_l.append(shadow_lk['sec_group_rk_mom'].get((ym, tk), 99))
            qqq_rk_l.append(lookups['qqq_rk_map'].get((ym, tk), 99))
            spy_rk_l.append(lookups['spy_rk_map'].get((ym, tk), 99))

        L['is_soxx_raw1'] = is_soxx_raw1
        L['is_soxx_sh1'] = is_soxx_sh1
        L['is_smh_raw1'] = is_smh_raw1
        L['is_smh_sh1'] = is_smh_sh1
        L['subind_name'] = subind_name_l
        L['subind_rk_raw'] = subind_rk_raw_l
        L['subind_rk_sh'] = subind_rk_sh_l
        L['subind_grp_rk'] = subind_grp_rk_l
        L['sec_rk_raw'] = sec_rk_raw_l
        L['sec_rk_sh'] = sec_rk_sh_l
        L['sec_grp_rk'] = sec_grp_rk_l
        L['qqq_rk'] = qqq_rk_l
        L['spy_rk'] = spy_rk_l
        return L

    L1k_sh = enrich_with_shadow_signals(L_3s_1k)
    L1a_sh = enrich_with_shadow_signals(L_3s_1a)
    Lc3_sh = enrich_with_shadow_signals(L_3s_c3)

    sh_diag_rows = []
    sh_subperiod_rows = []

    for m_label, L_sh in [
        ('3S_G1_1k (50% QQQ[<=5]+25% Tech[1]+25% SPY[<=3])', L1k_sh),
        ('3S_G1_1a (50% QQQ[<=5]+25% Tech[1]+25% SPY[1])', L1a_sh),
        ('3S_Core3_1a (Unbuffered Hard Top-2/1/1)', Lc3_sh),
    ]:
        s3 = L_sh[L_sh['state_main'] == '3_Triple_Consensus']
        s2 = L_sh[L_sh['state_main'] == '2_Two_Leg_Overlap']
        s0 = L_sh[L_sh['state_main'] == '0_No_Overlap']

        buckets = [
            ('0_No_Overlap (Baseline 0-Leg)', s0),
            ('2_Two_Leg_Overlap (All 2-Leg)', s2),
            ('  2_Leg | NOT Confirmed by Sector/Ind Sharpe #1', s2[s2['sec_rk_sh'] > 1]),
            ('  2_Leg | Confirmed: Stock is Sector Raw#1 & Sharpe#1', s2[(s2['sec_rk_raw'] == 1) & (s2['sec_rk_sh'] == 1)]),
            ('  2_Leg | QQQ==SPY Confirmed by Own Sector #1 (XLV/XLY/XLC/Storage)', s2[(s2['state_sub'] == '2c_QQQ_eq_SPY_only') & (s2['sec_rk_raw'] == 1)]),
            ('  2_Leg | QQQ==Tech Confirmed by SOXX #1 (while SPY in Non-Tech)', s2[(s2['state_sub'] == '2b_QQQ_eq_Tech_only') & s2['is_soxx_raw1']]),
            ('3_Triple_Consensus (All 3-Leg Baseline)', s3),
            ('  3_Leg | Sub-Industry = SOXX_Strict #1 (Pure Semis: NVDA/MU/AMD/LRCX)', s3[s3['is_soxx_raw1']]),
            ('  3_Leg | Sub-Industry = SMH_Broad #1 (Semis + Memory/Storage WDC)', s3[s3['is_smh_raw1']]),
            ('  3_Leg | Sub-Industry = Software #1 (PLTR/FB/EA)', s3[s3['subind_name'] == 'Software_Services']),
            ('  3_Leg | Cross-Metric Confirmed: SOXX Raw#1 AND SOXX Sharpe#1', s3[s3['is_soxx_raw1'] & s3['is_soxx_sh1']]),
            ('  3_Leg | Cross-Metric Confirmed: Any SubInd Raw#1 AND Sharpe#1', s3[(s3['subind_rk_raw'] == 1) & (s3['subind_rk_sh'] == 1)]),
            ('  3_Leg | SubInd Raw#1 but NOT SubInd Sharpe#1 (High-Vol Jump)', s3[(s3['subind_rk_raw'] == 1) & (s3['subind_rk_sh'] > 1)]),
            ('  3_Leg | 3-Layer Group Confirmed: Stock 3-Leg + SubInd Group #1 in Tech', s3[s3['subind_grp_rk'] == 1]),
            ('  3_Leg | Stock 3-Leg but SubInd Group NOT #1 in Tech (Lone Outlier)', s3[s3['subind_grp_rk'] > 1]),
            ('  3_Leg | Super-Crown: 3-Leg + SubInd Group #1 + Tech Sector Top-2 + Sharpe#1',
             s3[(s3['subind_grp_rk'] == 1) & (s3['sec_grp_rk'] <= 2) & (s3['subind_rk_sh'] == 1)]),
        ]

        for b_name, b_df in buckets:
            if len(b_df) > 0:
                sh_diag_rows.append(summarize_bucket_rows(m_label, b_name, b_df, rf_monthly))

        # Check First Half (2009-2018) vs Second Half (2019-2026) on 3S_G1_1k key shadow states
        if '3S_G1_1k' in m_label:
            for half_name, h_df in [
                ('FirstHalf_2009_2018 (120m)', L_sh.loc['2009-01':'2018-12']),
                ('SecondHalf_2019_2026 (93m)', L_sh.loc['2019-01':'2026-09']),
            ]:
                hs3 = h_df[h_df['state_main'] == '3_Triple_Consensus']
                hs2 = h_df[h_df['state_main'] == '2_Two_Leg_Overlap']
                for b_name, b_df in [
                    ('3_Leg_All', hs3),
                    ('3_Leg + SOXX_Strict #1', hs3[hs3['is_soxx_raw1']]),
                    ('3_Leg + SMH_Broad #1', hs3[hs3['is_smh_raw1']]),
                    ('3_Leg + SubInd Raw#1 & Sharpe#1', hs3[(hs3['subind_rk_raw'] == 1) & (hs3['subind_rk_sh'] == 1)]),
                    ('3_Leg + SubInd Group #1 in Tech', hs3[hs3['subind_grp_rk'] == 1]),
                    ('3_Leg + SubInd Group NOT #1', hs3[hs3['subind_grp_rk'] > 1]),
                    ('2_Leg + Confirmed Sector Raw#1 & Sharpe#1', hs2[(hs2['sec_rk_raw'] == 1) & (hs2['sec_rk_sh'] == 1)]),
                    ('2_Leg + NOT Sector Sharpe#1', hs2[hs2['sec_rk_sh'] > 1]),
                ]:
                    if len(b_df) > 0:
                        sh_subperiod_rows.append(summarize_bucket_rows(f'3S_G1_1k [{half_name}]', b_name, b_df, rf_monthly))

    df_sh_diag = pd.DataFrame([x for x in sh_diag_rows if x is not None])
    df_sh_diag.to_csv(os.path.join(HERE, '07_shadow_industry_confirmer_diagnostic.csv'), index=False)

    df_sh_sub = pd.DataFrame([x for x in sh_subperiod_rows if x is not None])
    df_sh_sub.to_csv(os.path.join(HERE, '07b_shadow_confirmer_subperiod_split.csv'), index=False)

    print('--- PART 1: SHADOW CONFIRMER DIAGNOSTIC ON 3S_G1_1k ---')
    for _, r in df_sh_diag[df_sh_diag['Strategy'].str.startswith('3S_G1_1k')].iterrows():
        print(f"  {r['Consensus_State']:<74} | N={int(r['Months_N']):3d} ({r['Share_Pct']*100:4.1f}%) | "
              f"Mean={r['Mean_Mo_Ret']*100:+5.2f}% | CAGR={r['Ann_Compounded_Ret']*100:6.2f}% | "
              f"Win={r['Win_Rate']*100:5.1f}% | SR={r['Ann_Sharpe_Excess']:4.2f} | Worst={r['Worst_Mo_Ret']*100:+6.2f}%")

    print('\n--- PART 1B: SUBPERIOD STABILITY (2009-2018 vs 2019-2026) ON 3S_G1_1k ---')
    for _, r in df_sh_sub.iterrows():
        print(f"  {r['Strategy']:<36} | {r['Consensus_State']:<42} | N={int(r['Months_N']):2d} | "
              f"Mean={r['Mean_Mo_Ret']*100:+5.2f}% | CAGR={r['Ann_Compounded_Ret']*100:6.2f}% | "
              f"Win={r['Win_Rate']*100:5.1f}% | SR={r['Ann_Sharpe_Excess']:4.2f}")

    # =========================================================================
    # PART 2: STANDALONE PERFORMANCE OF ALL SECTOR & SUB-INDUSTRY CHAMPION SLEEVES
    # =========================================================================
    print('\n[Part 2/4] Simulating Standalone Sector & Industry Champion Sleeves (2009-2026)...')

    # Simulate standalone Sub-Industry sleeves
    L_soxx_raw_1 = simulate_single_sleeve(soxx_strict_panel, spec_raw, k=1, k_keep=1)
    L_soxx_raw_g3 = simulate_single_sleeve(soxx_strict_panel, spec_raw, k=1, k_keep=3)
    L_soxx_sh_1 = simulate_single_sleeve(soxx_strict_panel, spec_sharpe, k=1, k_keep=1)
    L_soxx_sh_g3 = simulate_single_sleeve(soxx_strict_panel, spec_sharpe, k=1, k_keep=3)

    L_smh_raw_1 = simulate_single_sleeve(smh_broad_panel, spec_raw, k=1, k_keep=1)
    L_smh_raw_g3 = simulate_single_sleeve(smh_broad_panel, spec_raw, k=1, k_keep=3)
    L_smh_sh_g3 = simulate_single_sleeve(smh_broad_panel, spec_sharpe, k=1, k_keep=3)

    L_igv_raw_1 = simulate_single_sleeve(igv_software_panel, spec_raw, k=1, k_keep=1)
    L_hw_raw_1 = simulate_single_sleeve(hw_storage_panel, spec_raw, k=1, k_keep=1)

    # Simulate Ex-IT (10 Non-Tech S&P 500 Sectors) Champion Sleeves
    spec_exit_raw = {'type': 'ex_it_score', 'score_col': 'mom_12_1'}
    spec_exit_sh = {'type': 'ex_it_score', 'score_col': 'sharpe_mom_12_1'}

    L_exit_raw_1 = simulate_single_sleeve(spy_panel, spec_exit_raw, k=1, k_keep=1)
    L_exit_raw_g3 = simulate_single_sleeve(spy_panel, spec_exit_raw, k=1, k_keep=3)
    L_exit_sh_1 = simulate_single_sleeve(spy_panel, spec_exit_sh, k=1, k_keep=1)
    L_exit_sh_g3 = simulate_single_sleeve(spy_panel, spec_exit_sh, k=1, k_keep=3)

    # Ex-IT Best Sector Rotation -> Top-1 Stock (Rank 10 Non-Tech sectors by EW mom_12_1, pick #1 stock in #1 Non-Tech sector)
    spy_no_it = spy_panel[spy_panel['sector'] != 'Information Technology'].copy()
    # Recompute sector rank among the 10 Non-Tech sectors
    sec_rk_no_it = []
    for t_val, g in spy_no_it.groupby('t', sort=True):
        s_moms = g.groupby('sector')['sector_ew_mom_12_1'].first().sort_values(ascending=False)
        rk_map = {sec: i + 1 for i, sec in enumerate(s_moms.index)}
        g_copy = g.copy()
        g_copy['exit_sec_rk_mom'] = g_copy['sector'].map(rk_map)
        sec_rk_no_it.append(g_copy)
    spy_no_it = pd.concat(sec_rk_no_it, ignore_index=True)

    spec_exit_secrot_raw = {'type': 'sector_top', 'n_sec': 1, 'sec_rank_col': 'exit_sec_rk_mom', 'score_col': 'mom_12_1'}
    L_exit_secrot_1 = simulate_single_sleeve(spy_no_it, spec_exit_secrot_raw, k=1, k_keep=1)
    L_exit_secrot_g3 = simulate_single_sleeve(spy_no_it, spec_exit_secrot_raw, k=1, k_keep=3)

    # Individual GICS Sector Top-1 Sleeves (XLE, XLV, XLI, XLF, XLY, XLU, XLB, XLP)
    sector_etf_map = [
        ('XLE_Energy', 'Energy'),
        ('XLV_HealthCare', 'Health Care'),
        ('XLI_Industrials', 'Industrials'),
        ('XLF_Financials', 'Financials'),
        ('XLY_ConsDisc', 'Consumer Discretionary'),
        ('XLU_Utilities', 'Utilities'),
        ('XLB_Materials', 'Materials'),
        ('XLP_ConsStaples', 'Consumer Staples'),
    ]
    L_indiv_sectors = {}
    for stag, sname in sector_etf_map:
        sub_p = spy_panel[spy_panel['sector'] == sname].copy()
        L_indiv_sectors[stag] = simulate_single_sleeve(sub_p, spec_raw, k=1, k_keep=3)

    def summarize_standalone_sleeve(name, group_tag, L_s):
        r = L_s['net'].astype(float)
        n = len(r)
        idx_dt = pd.to_datetime(r.index + '-01') + pd.offsets.MonthEnd(1)
        r_s = pd.Series(r.values, index=idx_dt)
        cagr = float((np.prod(1.0 + r_s.values)) ** (12.0 / n) - 1.0)
        vol = float(r_s.std(ddof=1) * np.sqrt(12.0))
        rf_al = rf_monthly.reindex(r_s.index).ffill().fillna(0.0)
        sr = float((r_s - rf_al).mean() / r_s.std(ddof=1) * np.sqrt(12.0))
        w = np.concatenate([[1.0], np.cumprod(1.0 + r_s.values)])
        mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
        ret_2022 = float(np.prod(1.0 + r_s.loc['2022-01-01':'2022-12-31'].values) - 1.0)
        cagr_09_18 = float((np.prod(1.0 + r_s.loc['2009-01-31':'2018-12-31'].values)) ** (12.0 / 120.0) - 1.0)
        cagr_19_26 = float((np.prod(1.0 + r_s.loc['2019-01-31':'2026-09-30'].values)) ** (12.0 / 93.0) - 1.0)
        corr_qqq = float(r.corr(L_qqq_g1_5['net']))
        corr_xlk = float(r.corr(L_xlk_c3['net']))
        # Overlap with XLK Top-1 pick
        ov_xlk = float(np.mean([
            len(set(L_s.loc[ym, 'picks'].split('|')) & set(L_xlk_c3.loc[ym, 'picks'].split('|'))) > 0
            for ym in r.index
        ]))
        return {
            'Sleeve_Name': name,
            'Category': group_tag,
            'CAGR_09_26': cagr,
            'Sharpe': sr,
            'Ann_Vol': vol,
            'Monthly_MaxDD': mdd,
            'CAGR_2009_2018': cagr_09_18,
            'CAGR_2019_2026': cagr_19_26,
            'Ret_2022': ret_2022,
            'Corr_with_QQQ_Sleeve': corr_qqq,
            'Corr_with_Tech_Sleeve': corr_xlk,
            'Pick_Overlap_with_Tech_Pct': ov_xlk,
        }

    standalone_list = [
        ('QQQ_Sharpe_G1_Hold5 (Ref Leg 1)', 'Core_Sleeves', L_qqq_g1_5),
        ('XLK_Tech_Raw_Hard1 (Ref Leg 2)', 'Core_Sleeves', L_xlk_c3),
        ('SPY_AllSector_Raw_G1_Hold3 (Ref Leg 3)', 'Core_Sleeves', L_spy_g1_3),
        ('SOXX_Strict_Raw_Hard1 (Pure Semis)', 'Tech_SubIndustries', L_soxx_raw_1),
        ('SOXX_Strict_Raw_G1_Hold3 (Pure Semis)', 'Tech_SubIndustries', L_soxx_raw_g3),
        ('SOXX_Strict_Sharpe_Hard1 (Pure Semis)', 'Tech_SubIndustries', L_soxx_sh_1),
        ('SOXX_Strict_Sharpe_G1_Hold3 (Pure Semis)', 'Tech_SubIndustries', L_soxx_sh_g3),
        ('SMH_Broad_Raw_Hard1 (Semis+Memory+EDA)', 'Tech_SubIndustries', L_smh_raw_1),
        ('SMH_Broad_Raw_G1_Hold3 (Semis+Memory+EDA)', 'Tech_SubIndustries', L_smh_raw_g3),
        ('SMH_Broad_Sharpe_G1_Hold3 (Semis+Memory+EDA)', 'Tech_SubIndustries', L_smh_sh_g3),
        ('IGV_Software_Raw_Hard1 (S&P Software)', 'Tech_SubIndustries', L_igv_raw_1),
        ('Tech_Hardware_Storage_Raw_Hard1', 'Tech_SubIndustries', L_hw_raw_1),
        ('ExIT_NonTech_Raw_Hard1 (Best Stock Across 10 Non-IT Sectors)', 'NonTech_Champions', L_exit_raw_1),
        ('ExIT_NonTech_Raw_G1_Hold3 (Best Stock Across 10 Non-IT Sectors)', 'NonTech_Champions', L_exit_raw_g3),
        ('ExIT_NonTech_Sharpe_Hard1 (10 Non-IT Sectors)', 'NonTech_Champions', L_exit_sh_1),
        ('ExIT_NonTech_Sharpe_G1_Hold3 (10 Non-IT Sectors)', 'NonTech_Champions', L_exit_sh_g3),
        ('ExIT_BestSector_Top1_Hard1 (Top Non-IT Sector -> Top-1 Stock)', 'NonTech_Champions', L_exit_secrot_1),
        ('ExIT_BestSector_Top1_G1_Hold3 (Top Non-IT Sector -> Top-1 Stock)', 'NonTech_Champions', L_exit_secrot_g3),
    ]
    for stag, _ in sector_etf_map:
        standalone_list.append((f'{stag}_Top1_G1_Hold3', 'Single_Sector_Champions', L_indiv_sectors[stag]))

    df_standalone = pd.DataFrame([summarize_standalone_sleeve(n, c, l) for n, c, l in standalone_list])
    df_standalone.to_csv(os.path.join(HERE, '08_standalone_sector_and_industry_sleeves.csv'), index=False)

    print('--- PART 2: STANDALONE SECTOR & SUB-INDUSTRY SLEEVES ---')
    for _, r in df_standalone.iterrows():
        print(f"  {r['Sleeve_Name']:<62} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | 2022={r['Ret_2022']*100:+6.1f}% | "
              f"CorrTech={r['Corr_with_Tech_Sleeve']:4.2f} | OvTech={r['Pick_Overlap_with_Tech_Pct']*100:4.1f}%")

    # =========================================================================
    # PART 3: SHADOW CONFIRMER CONVICTION SIZING BACKTESTS (PRIORITY #1)
    # =========================================================================
    print('\n[Part 3/4] Backtesting Shadow Industry/Sector Confirmer Conviction Sizing...')

    base_3s_1k = {'qqq': L_qqq_g1_5, 'xlk': L_xlk_c3, 'spy': L_spy_g1_3}

    def make_shadow_conviction_rule(mode_type, require_sep_lowvol=False):
        def rule_fn(ym, r_qqq, r_xlk, r_spy, reg_row, lk):
            q_w = r_qqq['weights_dict']
            t_w = r_xlk['weights_dict']
            s_w = r_spy['weights_dict']
            w_base = {}
            for tk, v in q_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.50 * v
            for tk, v in t_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v
            for tk, v in s_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v

            q_set = set(q_w.keys())
            t_pick = list(t_w.keys())[0]
            s_pick = list(s_w.keys())[0]
            t_in_q = t_pick in q_set
            s_in_q = s_pick in q_set
            t_eq_s = (t_pick == s_pick)

            is_3leg = t_eq_s and t_in_q
            is_2leg = (not is_3leg) and (t_eq_s or t_in_q or s_in_q)
            ov_tk = t_pick if (t_eq_s or t_in_q) else (s_pick if s_in_q else '')

            is_soxx1 = (ov_tk != '') and (shadow_lk['soxx_strict_raw_top1'].get(ym, '') == ov_tk)
            is_smh1 = (ov_tk != '') and (shadow_lk['smh_broad_raw_top1'].get(ym, '') == ov_tk)
            sname = shadow_lk['stock_subind'].get((ym, ov_tk), 'Non_IT')
            sub_rk_raw = shadow_lk['subind_rk_raw'].get((ym, ov_tk), 99)
            sub_rk_sh = shadow_lk['subind_rk_sharpe'].get((ym, ov_tk), 99)
            sub_grp_rk = shadow_lk['subind_group_rk_mom'].get((ym, sname), 99)
            sec_rk_raw = shadow_lk['sec_stock_rk_raw'].get((ym, ov_tk), 99)
            sec_rk_sh = shadow_lk['sec_stock_rk_sharpe'].get((ym, ov_tk), 99)

            gate_ok = True
            if require_sep_lowvol:
                gate_ok = bool(reg_row['sep_on']) and (float(reg_row['qqq_vol21']) <= 0.30) and (not bool(reg_row['dm_panic']))

            mult = 1.0
            state = 'Normal_1x'

            if mode_type == 'ctrl_1x':
                mult = 1.0
            elif mode_type == 'base_3leg_150':
                if is_3leg and gate_ok:
                    mult = 1.50
                    state = '3Leg_1.5x'
            elif mode_type == 'soxx_only_150':
                # Only boost 1.50x when 3-Leg Consensus AND SOXX_Strict #1
                if is_3leg and is_soxx1 and gate_ok:
                    mult = 1.50
                    state = '3Leg_SOXX1_1.5x'
            elif mode_type == 'tiered_soxx_125_150':
                # Non-SOXX 3-Leg gets 1.25x, SOXX #1 3-Leg gets 1.50x
                if is_3leg and gate_ok:
                    mult = 1.50 if is_soxx1 else 1.25
                    state = '3Leg_SOXX_1.5x' if is_soxx1 else '3Leg_Other_1.25x'
            elif mode_type == 'subind_group1_150':
                # Only boost 1.50x when 3-Leg Consensus AND its Sub-Industry Group is #1 in Tech
                if is_3leg and (sub_grp_rk == 1) and gate_ok:
                    mult = 1.50
                    state = '3Leg_SubIndGrp1_1.5x'
            elif mode_type == 'tiered_subind_grp_125_160':
                # 3-Leg with SubInd Group #1 gets 1.60x; 3-Leg with SubInd Group >1 gets 1.20x
                if is_3leg and gate_ok:
                    mult = 1.60 if (sub_grp_rk == 1) else 1.20
                    state = '3Leg_Grp1_1.6x' if (sub_grp_rk == 1) else '3Leg_GrpOther_1.2x'
            elif mode_type == 'cross_metric_subind_150':
                # Boost 1.50x on 3-Leg when stock is #1 in its Sub-Industry by BOTH Raw and Sharpe-Mom
                if is_3leg and (sub_rk_raw == 1) and (sub_rk_sh == 1) and gate_ok:
                    mult = 1.50
                    state = '3Leg_DualRank1_1.5x'
            elif mode_type == 'shadow_upgrade_2leg_125_3leg_150':
                # 3-Leg gets 1.50x; 2-Leg gets 1.25x ONLY when confirmed by own Sector Raw#1 & Sharpe#1
                if is_3leg and gate_ok:
                    mult = 1.50
                    state = '3Leg_1.5x'
                elif is_2leg and (sec_rk_raw == 1) and (sec_rk_sh == 1) and gate_ok:
                    mult = 1.25
                    state = '2Leg_ShadowConfirmed_1.25x'

            w_stocks = {tk: v * mult for tk, v in w_base.items()}
            w_cash = max(0.0, 1.0 - mult)
            w_borrow = max(0.0, mult - 1.0)
            r_borrow = float(reg_row['borrow_monthly'])
            return w_stocks, w_cash, 0.0, w_borrow, r_borrow, state
        return rule_fn

    L_ctrl_1k, d56_ctrl, do2c_ctrl = simulate_dynamic_portfolio(
        base_3s_1k, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o,
        make_shadow_conviction_rule('ctrl_1x')
    )
    ref_1k_r = L_ctrl_1k['net']

    sh_bt_configs = [
        ('SH_00_3S_G1_1k_Unlevered_Ctrl (1.0x Always)', 'Shadow_Ctrl', 'ctrl_1x', False),
        ('SH_01_Ref_All_3Leg -> 1.50x (Unconditional 3-Leg)', 'Shadow_Uncond', 'base_3leg_150', False),
        ('SH_1a_3Leg + SOXX_Strict #1 Only -> 1.50x (Semis Only)', 'Shadow_Uncond', 'soxx_only_150', False),
        ('SH_1b_Tiered: 3Leg_SOXX#1 -> 1.50x | 3Leg_NonSOXX -> 1.25x', 'Shadow_Uncond', 'tiered_soxx_125_150', False),
        ('SH_1c_3Leg + SubInd_Group_#1 -> 1.50x (3-Layer Group Confirm)', 'Shadow_Uncond', 'subind_group1_150', False),
        ('SH_1d_Tiered: 3Leg+SubIndGrp#1 -> 1.60x | Other 3Leg -> 1.20x', 'Shadow_Uncond', 'tiered_subind_grp_125_160', False),
        ('SH_1e_3Leg + SubInd Raw#1 & Sharpe#1 -> 1.50x', 'Shadow_Uncond', 'cross_metric_subind_150', False),
        ('SH_1f_3Leg(1.50x) + Shadow-Confirmed 2Leg(1.25x)', 'Shadow_Uncond', 'shadow_upgrade_2leg_125_3leg_150', False),
        # With SEP == ON + LowVol Crash Protection
        ('SH_2a_SEP_LowVol + 3Leg + SubInd_Group_#1 -> 1.50x', 'Shadow_CrashProt', 'subind_group1_150', True),
        ('SH_2b_SEP_LowVol + Tiered (3Leg+Grp#1=1.60x | Other3Leg=1.20x)', 'Shadow_CrashProt', 'tiered_subind_grp_125_160', True),
        ('SH_2c_SEP_LowVol + 3Leg(1.50x) + Shadow-Confirmed 2Leg(1.25x)', 'Shadow_CrashProt', 'shadow_upgrade_2leg_125_3leg_150', True),
    ]

    sh_bt_rows = []
    for v_name, fam, mtype, req_gate in sh_bt_configs:
        Lp, d56, do2c = simulate_dynamic_portfolio(
            base_3s_1k, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o,
            make_shadow_conviction_rule(mtype, require_sep_lowvol=req_gate)
        )
        sh_bt_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_sh_bt = pd.DataFrame(sh_bt_rows)
    df_sh_bt.to_csv(os.path.join(HERE, '09_shadow_confirmer_conviction_backtests.csv'), index=False)

    print('--- PART 3: SHADOW CONFIRMER CONVICTION SIZING BACKTESTS ---')
    for _, r in df_sh_bt.iterrows():
        print(f"  {r['Variant']:<66} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"AvgExp={r['Avg_Gross_Exp']:4.2f}x | t={r['NW_t_vs_Ctrl']:+5.2f}")

    # =========================================================================
    # PART 4: PRIORITY #2 — NON-TECH SECTOR CHAMPION LEG VS 5-LEG SEMI STRAWMAN
    # =========================================================================
    print('\n[Part 4/4] Auditing Non-Tech Sector Champion Legs vs 5-Leg Semiconductor Strawman...')

    # Extend lookups['ret_map'] with any SOXX/SMH NDX-only stocks if needed (already in qqq_panel!)
    def simulate_multi_sleeve_portfolio(sleeve_dict, weights_fn):
        """
        General multi-sleeve single-account portfolio simulator for any number of sleeves
        (`qqq`, `xlk`, `spy`, `soxx`, `smh`, `exit_raw`, `exit_secrot`, `exit_sh`).
        """
        common_ym = L_qqq_g1_5.index
        ret_map = lookups['ret_map']
        prev_drifted_w = {}
        rows = []

        for ym in common_ym:
            t_date = pd.Timestamp(L_qqq_g1_5.at[ym, 't_date'])
            reg_row = regime_df.loc[ym]
            s_rows = {k: v.loc[ym] for k, v in sleeve_dict.items()}

            # weights_fn returns (sleeve_weights_dict, cash_weight, cash_ret)
            sw_dict, w_cash, r_cash = weights_fn(ym, s_rows, reg_row, shadow_lk)

            w_stocks = {}
            meta_comb = {}
            for skey, w_s in sw_dict.items():
                if w_s <= 0:
                    continue
                r_s = s_rows[skey]
                utag = 'qqq' if skey.startswith(('qqq', 'soxx', 'smh')) else ('xlk' if skey == 'xlk' else 'spy')
                for tk, v in r_s['weights_dict'].items():
                    w_stocks[tk] = w_stocks.get(tk, 0.0) + w_s * v
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

            gross_stocks = sum(w_tk * ret_map[(ym, tk)] for tk, w_tk in w_stocks.items())
            gross_total = gross_stocks + w_cash * r_cash

            if not prev_drifted_w:
                to = sum(abs(w_tk) for w_tk in w_stocks.values())
            else:
                all_tks = set(w_stocks.keys()) | set(prev_drifted_w.keys())
                to = float(sum(abs(w_stocks.get(tk, 0.0) - prev_drifted_w.get(tk, 0.0)) for tk in all_tks))

            net_total = (1.0 + gross_total) * ((1.0 - 0.0010) ** to) - 1.0 if to > 0 else gross_total

            end_eq = 1.0 + gross_total
            prev_drifted_w = {
                tk: w_tk * (1.0 + ret_map[(ym, tk)]) / end_eq
                for tk, w_tk in w_stocks.items()
            } if end_eq > 0 else {}

            rows.append({
                'ym': ym,
                't_date': t_date,
                'gross': gross_total,
                'net': net_total,
                'turnover': to,
                'long_exp': float(sum(w_stocks.values())),
                'w_cash': w_cash,
                'w_borrow': 0.0,
                'n_distinct': len(w_stocks),
                'max_single_w': max(w_stocks.values()) if w_stocks else 0.0,
                'holdings_dict': dict(w_stocks),
                'meta_map': meta_comb,
                'net_financing_drag': -w_cash * r_cash,
            })

        L_port = pd.DataFrame(rows).set_index('ym')
        from run_consensus_burst_audit import compute_dynamic_daily_drawdowns
        dd_c56, dd_o2c = compute_dynamic_daily_drawdowns(L_port, cal_days, spy_daily_c, spy_daily_o)
        return L_port, dd_c56, dd_o2c

    all_sleeves = {
        'qqq': L_qqq_g1_5,
        'xlk': L_xlk_c3,
        'spy': L_spy_g1_3,
        'soxx_raw': L_soxx_raw_1,
        'soxx_g3': L_soxx_raw_g3,
        'smh_sh': L_smh_sh_g3,
        'exit_raw_g3': L_exit_raw_g3,
        'exit_raw_1': L_exit_raw_1,
        'exit_sh_g3': L_exit_sh_g3,
        'exit_secrot_g3': L_exit_secrot_g3,
    }

    def static_w(d):
        return lambda ym, sr, reg, sh: (d, 0.0, 0.0)

    def sep_off_to_exit_and_sgov(ym, sr, reg, sh):
        if bool(reg['sep_on']):
            return ({'qqq': 0.50, 'xlk': 0.25, 'spy': 0.25}, 0.0, 0.0)
        else:
            # When SEP OFF: shut QQQ (50% -> 0%), allocate 25% to Non-Tech Champion + 25% to SGOV!
            return ({'qqq': 0.00, 'xlk': 0.25, 'spy': 0.25, 'exit_raw_g3': 0.25}, 0.25, float(reg['rf_monthly']))

    def non_tech_sector_leads_tech_tilt(ym, sr, reg, sh):
        # When Best Non-Tech Sector EW Momentum > Tech Sector EW Momentum by > 5%, shift 15% to Ex-IT
        best_exit_m = sh['best_exit_sector_mom'].get(ym, 0.0)
        tech_m = sh['tech_sector_mom'].get(ym, 0.0)
        if best_exit_m > tech_m + 0.05:
            return ({'qqq': 0.45, 'xlk': 0.15, 'spy': 0.20, 'exit_raw_g3': 0.20}, 0.0, 0.0)
        else:
            return ({'qqq': 0.50, 'xlk': 0.25, 'spy': 0.25}, 0.0, 0.0)

    arch_configs = [
        # Baseline 3-Leg
        ('P4_00_3S_G1_1k_Baseline (50% QQQ + 25% XLK + 25% SPY)', 'Baseline_3Leg',
         static_w({'qqq': 0.50, 'xlk': 0.25, 'spy': 0.25})),

        # --- A. The "Bad Strawman": 5-Leg Semiconductor Stacking (QQQ + XLK + SOXX + SMH + SPY) ---
        ('P4_1a_Strawman_5Leg_EW (20% QQQ + 20% XLK + 20% SOXX + 20% SMH + 20% SPY)', 'Bad_Strawman_5Leg_Semi',
         static_w({'qqq': 0.20, 'xlk': 0.20, 'soxx_raw': 0.20, 'smh_sh': 0.20, 'spy': 0.20})),
        ('P4_1b_Strawman_5Leg_40QQQ (40% QQQ + 15% XLK + 15% SOXX + 15% SMH + 15% SPY)', 'Bad_Strawman_5Leg_Semi',
         static_w({'qqq': 0.40, 'xlk': 0.15, 'soxx_raw': 0.15, 'smh_sh': 0.15, 'spy': 0.15})),
        ('P4_1c_Strawman_Replace_XLK_with_SOXX (50% QQQ + 25% SOXX_Pure + 25% SPY)', 'Bad_Strawman_5Leg_Semi',
         static_w({'qqq': 0.50, 'soxx_raw': 0.25, 'spy': 0.25})),

        # --- B. Adding a Dedicated 4th Leg: Non-Tech Sector Champion (`Ex-IT`) ---
        ('P4_2a_4Leg_ExIT_RawG3 (50% QQQ + 20% XLK + 15% SPY + 15% ExIT_Raw[<=3])', '4Leg_With_NonTech_Champ',
         static_w({'qqq': 0.50, 'xlk': 0.20, 'spy': 0.15, 'exit_raw_g3': 0.15})),
        ('P4_2b_4Leg_ExIT_RawG3_40_20_20_20 (40% QQQ + 20% XLK + 20% SPY + 20% ExIT_Raw[<=3])', '4Leg_With_NonTech_Champ',
         static_w({'qqq': 0.40, 'xlk': 0.20, 'spy': 0.20, 'exit_raw_g3': 0.20})),
        ('P4_2c_4Leg_ExIT_SecRot (50% QQQ + 20% XLK + 15% SPY + 15% ExIT_BestSec_Top1[<=3])', '4Leg_With_NonTech_Champ',
         static_w({'qqq': 0.50, 'xlk': 0.20, 'spy': 0.15, 'exit_secrot_g3': 0.15})),
        ('P4_2d_4Leg_ExIT_SharpeG3 (50% QQQ + 20% XLK + 15% SPY + 15% ExIT_Sharpe[<=3])', '4Leg_With_NonTech_Champ',
         static_w({'qqq': 0.50, 'xlk': 0.20, 'spy': 0.15, 'exit_sh_g3': 0.15})),

        # --- C. 3-Leg Pure Orthogonal Split: 50% QQQ + 25% Tech + 25% Ex-IT (vs 25% All-Sector SPY) ---
        ('P4_3a_3Leg_PureExIT (50% QQQ + 25% XLK + 25% ExIT_Raw[<=3] — Never Overlaps Tech)', '3Leg_Pure_ExIT_Split',
         static_w({'qqq': 0.50, 'xlk': 0.25, 'exit_raw_g3': 0.25})),
        ('P4_3b_3Leg_PureExIT_SecRot (50% QQQ + 25% XLK + 25% ExIT_BestSec_Top1[<=3])', '3Leg_Pure_ExIT_Split',
         static_w({'qqq': 0.50, 'xlk': 0.25, 'exit_secrot_g3': 0.25})),

        # --- D. Dynamic Non-Tech Sector Champion Routing (Best of Both Worlds!) ---
        ('P4_4a_Dynamic_SEP_OFF_ExIT (SEP ON: 50/25/25 | SEP OFF: 0% QQQ+25% XLK+25% SPY+25% ExIT+25% SGOV)', 'Dynamic_NonTech_Routing',
         sep_off_to_exit_and_sgov),
        ('P4_4b_Dynamic_SectorLead_Tilt (Tilt 20% to ExIT only when Best Non-IT Sector Mom > Tech + 5%)', 'Dynamic_NonTech_Routing',
         non_tech_sector_leads_tech_tilt),
    ]

    arch_rows = []
    for v_name, fam, w_fn in arch_configs:
        Lp, d56, do2c = simulate_multi_sleeve_portfolio(all_sleeves, w_fn)
        arch_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_arch = pd.DataFrame(arch_rows)
    df_arch.to_csv(os.path.join(HERE, '10_nontech_champion_vs_5leg_strawman.csv'), index=False)

    print('--- PART 4: NON-TECH SECTOR CHAMPION LEG VS 5-LEG SEMICONDUCTOR STRAWMAN ---')
    for _, r in df_arch.iterrows():
        print(f"  {r['Variant']:<78} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"2022={r['Ret_2022']*100:+6.1f}% | Ex22={r['CAGR_Ex2022']*100:6.2f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    print('\nAll Part 1-4 CSVs saved successfully.')


if __name__ == '__main__':
    main()
