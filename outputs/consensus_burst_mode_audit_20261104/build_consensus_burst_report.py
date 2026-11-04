#!/usr/bin/env python3
"""
build_consensus_burst_report.py — Generates CONSENSUS_BURST_MODE_AUDIT_REPORT.md
"""
import os
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def fmt_pct(v, d=2, sign=False):
    if pd.isna(v):
        return 'N/A'
    s = f'{v * 100:+0.{d}f}%' if sign else f'{v * 100:0.{d}f}%'
    return s


def fmt_num(v, d=2, sign=False):
    if pd.isna(v):
        return 'N/A'
    return f'{v:+0.{d}f}' if sign else f'{v:0.{d}f}'


def main():
    df_diag = pd.read_csv(os.path.join(HERE, '01_consensus_overlap_diagnostic.csv'))
    df_sub = pd.read_csv(os.path.join(HERE, '01b_consensus_subperiod_and_robustness.csv'))
    df_m1 = pd.read_csv(os.path.join(HERE, '02_mode1_consensus_conviction_sizing.csv'))
    df_m2 = pd.read_csv(os.path.join(HERE, '03_mode2_sep_and_trend_qqq_routing.csv'))
    df_m2_attr = pd.read_csv(os.path.join(HERE, '03b_sep_and_sma200_sleeve_attribution.csv'))
    df_m3 = pd.read_csv(os.path.join(HERE, '04_mode3_crash_protected_consensus_leverage.csv'))
    df_m4 = pd.read_csv(os.path.join(HERE, '05_mode4_ear_momentum_consensus.csv'))
    df_m4_diag = pd.read_csv(os.path.join(HERE, '05b_ear_consensus_diagnostic.csv'))
    df_dsr = pd.read_csv(os.path.join(HERE, '06_multiple_testing_dsr.csv'))
    df_sh_diag = pd.read_csv(os.path.join(HERE, '07_shadow_industry_confirmer_diagnostic.csv'))
    df_sh_sub = pd.read_csv(os.path.join(HERE, '07b_shadow_confirmer_subperiod_split.csv'))
    df_sleeves = pd.read_csv(os.path.join(HERE, '08_standalone_sector_and_industry_sleeves.csv'))
    df_sh_bt = pd.read_csv(os.path.join(HERE, '09_shadow_confirmer_conviction_backtests.csv'))
    df_arch = pd.read_csv(os.path.join(HERE, '10_nontech_champion_vs_5leg_strawman.csv'))
    df_11a = pd.read_csv(os.path.join(HERE, '11a_expA_concentration_diagnostic.csv'))
    df_11b = pd.read_csv(os.path.join(HERE, '11b_expAB_unlevered_concentration_and_sepoff.csv'))
    df_12 = pd.read_csv(os.path.join(HERE, '12_expC_and_ABC_tiered_burst.csv'))
    df_13 = pd.read_csv(os.path.join(HERE, '13_expD_single_stock_2x_etf_backtests.csv'))
    df_13b = pd.read_csv(os.path.join(HERE, '13b_expD_single_stock_2x_etf_monthly_audit.csv'))

    lines = []
    lines.append('# Multi-Leg Consensus ("Burst Switch") & 4 Burst Modes — Clean-Room Scientific Audit Report\n')
    lines.append('**Sample Window**: `2009-01` – `2026-09` (`213` holding months, `T+1 Open` execution, `10 bp/side` single-account turnover cost, PIT `3M T-bill + 50bp` margin financing cost on levered exposure)\n')
    lines.append('---\n')

    # SECTION 1: PRIORITY #1 DIAGNOSTIC TABLE
    lines.append('## 1. Priority #1: The "Burst Switch" Diagnostic Table (`0重合 vs 2腿重合 vs 3腿重合`)\n')
    lines.append('| Strategy / Engine | Consensus State | Months ($N$) | Share | Mean 1M | Median 1M | Ann. Compounded | Ann. Vol | Excess Sharpe | Win Rate | Worst Month | Consensus Stock CAGR | Non-Consensus Stock CAGR |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')

    for _, r in df_diag.iterrows():
        lines.append(
            f"| `{r['Strategy']}` | `{r['Consensus_State']}` | `{int(r['Months_N'])}` | `{fmt_pct(r['Share_Pct'], 1)}` | "
            f"`{fmt_pct(r['Mean_Mo_Ret'], 2, True)}` | `{fmt_pct(r['Median_Mo_Ret'], 2, True)}` | "
            f"**`{fmt_pct(r['Ann_Compounded_Ret'], 2)}`** | `{fmt_pct(r['Ann_Vol'], 2)}` | "
            f"**`{fmt_num(r['Ann_Sharpe_Excess'], 2)}`** | **`{fmt_pct(r['Win_Rate'], 1)}`** | "
            f"`{fmt_pct(r['Worst_Mo_Ret'], 2, True)} ({r['Worst_Mo_YM']})` | "
            f"`{fmt_pct(r['Consensus_Stock_Ann_CAGR'], 1)}` | `{fmt_pct(r['NonConsensus_Stock_Ann_CAGR'], 1)}` |"
        )

    lines.append('\n### 1.2 Subperiod (`2009–2018` vs `2019–2026`) & Leave-One-Winner-Out (`Ex-NVDA`, `Ex-SNDK`, `Ex-2022`) Robustness\n')
    lines.append('| Strategy & Slice | Consensus State | Months ($N$) | Mean 1M | Median 1M | Ann. Compounded | Excess Sharpe | Win Rate | Worst Month | Consensus Stock CAGR |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_sub.iterrows():
        lines.append(
            f"| `{r['Strategy']}` | `{r['Consensus_State']}` | `{int(r['Months_N'])}` | "
            f"`{fmt_pct(r['Mean_Mo_Ret'], 2, True)}` | `{fmt_pct(r['Median_Mo_Ret'], 2, True)}` | "
            f"**`{fmt_pct(r['Ann_Compounded_Ret'], 2)}`** | **`{fmt_num(r['Ann_Sharpe_Excess'], 2)}`** | "
            f"`{fmt_pct(r['Win_Rate'], 1)}` | `{fmt_pct(r['Worst_Mo_Ret'], 2, True)} ({r['Worst_Mo_YM']})` | "
            f"`{fmt_pct(r['Consensus_Stock_Ann_CAGR'], 1)}` |"
        )

    # SECTION 2: BURST MODE 1
    lines.append('\n---\n## 2. Burst Mode 1 — Consensus / Overlap Conviction Sizing (`共振加仓`)\n')
    lines.append('| Variant | Avg Exp | CAGR (`09–26`) | Excess Sharpe | Sortino | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | Daily MaxDD (`O2C`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Pos Yrs | NW $t$ vs Ctrl |')
    lines.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_m1.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Avg_Gross_Exp']:.2f}x` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_num(r['Sortino'], 2)}` | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{fmt_pct(r['Daily_MaxDD_O2C'], 2)}` | "
            f"`{fmt_pct(r['CAGR_2009_2018'], 2)}` | `{fmt_pct(r['CAGR_2019_2026'], 2)}` | "
            f"`{fmt_pct(r['Ret_2022'], 1, True)}` | `{int(r['Pos_Years_18'])}/18` | `{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 3: BURST MODE 2
    lines.append('\n---\n## 3. Burst Mode 2 — `SEP` / `QQQ<SMA200` Selective `QQQ` Shutoff & Reallocation to `Tech + SPY`\n')
    lines.append('### 3.1 Sleeve Return Attribution During `SEP OFF` and `QQQ < SMA200` Regimes\n')
    lines.append('| Regime Slice | Months ($N$) | `QQQ` Sleeve Mean 1M | `QQQ` Cum Ret | `Tech` Sleeve Mean 1M | `Tech` Cum Ret | `SPY` Sleeve Mean 1M | `SPY` Cum Ret | Base `3S_G1_1k` Cum Ret |')
    lines.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_m2_attr.iterrows():
        lines.append(
            f"| `{r['Regime_Slice']}` | `{int(r['Months_N'])}` | `{fmt_pct(r['QQQ_Sleeve_Mean_Mo'], 2, True)}` | "
            f"`{fmt_pct(r['QQQ_Sleeve_Cum_Ret'], 1, True)}` | `{fmt_pct(r['Tech_Sleeve_Mean_Mo'], 2, True)}` | "
            f"`{fmt_pct(r['Tech_Sleeve_Cum_Ret'], 1, True)}` | `{fmt_pct(r['SPY_Sleeve_Mean_Mo'], 2, True)}` | "
            f"`{fmt_pct(r['SPY_Sleeve_Cum_Ret'], 1, True)}` | `{fmt_pct(r['Base_3S_G1_1k_Cum_Ret'], 1, True)}` |"
        )

    lines.append('\n### 3.2 Full Backtest & Ex-2022 Hindsight Audit of Mode 2 Variants\n')
    lines.append('| Variant | Full CAGR (`09–26`) | **Ex-2022 CAGR (`201m`)** | **`2022` Return** | **`2023–2026` CAGR** | Excess Sharpe | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | Avg Exp | NW $t$ vs Ctrl |')
    lines.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_m2.iterrows():
        lines.append(
            f"| `{r['Variant']}` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | **`{fmt_pct(r['CAGR_Ex2022'], 2)}`** | "
            f"`{fmt_pct(r['Ret_2022'], 1, True)}` | `{fmt_pct(r['CAGR_2023_2026'], 2)}` | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{r['Avg_Gross_Exp']:.2f}x` | `{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 4: BURST MODE 3
    lines.append('\n---\n## 4. Burst Mode 3 — Trend + Low Crash Risk + Consensus Controlled Leverage (Barroso–Santa-Clara / Daniel–Moskowitz)\n')
    lines.append('| Variant | Avg Exp | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Pos Yrs | NW $t$ vs Ctrl |')
    lines.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_m3.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Avg_Gross_Exp']:.2f}x` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{fmt_pct(r['CAGR_2009_2018'], 2)}` | "
            f"`{fmt_pct(r['CAGR_2019_2026'], 2)}` | `{fmt_pct(r['Ret_2022'], 1, True)}` | "
            f"`{int(r['Pos_Years_18'])}/18` | `{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 5: BURST MODE 4
    lines.append('\n---\n## 5. Burst Mode 4 — `EAR` (PIT Earnings Reaction) + Momentum Consensus\n')
    lines.append('### 5.1 Diagnostic Breakdown: Consensus State $\\times$ Trailing Earnings Reaction (`ear_sum4` & `ear_latest`)\n')
    lines.append('| Consensus $\\times$ EAR State | Months ($N$) | Share | Mean 1M | Median 1M | Ann. Compounded | Excess Sharpe | Win Rate | Worst Month |')
    lines.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_m4_diag.iterrows():
        lines.append(
            f"| `{r['Consensus_State']}` | `{int(r['Months_N'])}` | `{fmt_pct(r['Share_Pct'], 1)}` | "
            f"`{fmt_pct(r['Mean_Mo_Ret'], 2, True)}` | `{fmt_pct(r['Median_Mo_Ret'], 2, True)}` | "
            f"**`{fmt_pct(r['Ann_Compounded_Ret'], 2)}`** | **`{fmt_num(r['Ann_Sharpe_Excess'], 2)}`** | "
            f"`{fmt_pct(r['Win_Rate'], 1)}` | `{fmt_pct(r['Worst_Mo_Ret'], 2, True)} ({r['Worst_Mo_YM']})` |"
        )

    lines.append('\n### 5.2 Backtest of `EAR`-Confirmed Conviction Sizing\n')
    lines.append('| Variant | Avg Exp | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | `2022` Return | NW $t$ vs Ctrl |')
    lines.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_m4.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Avg_Gross_Exp']:.2f}x` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{fmt_pct(r['Ret_2022'], 1, True)}` | "
            f"`{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 6: DSR
    lines.append('\n---\n## 6. Cumulative Multiple-Testing Deflated Sharpe Ratio (`N = 946` Canonical Trials Across All 8 Rounds)\n')
    lines.append('| Variant | Family | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | Daily MaxDD (`5651ec2`) | $N_{\\text{cum}}$ | Expected Max $\\text{SR}_0$ (Ann.) | DSR $p$-value |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_dsr.head(30).iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Family']}` | `{fmt_pct(r['CAGR_09_26'], 2)}` | "
            f"`{fmt_num(r['Sharpe_Ann'], 3)}` | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{int(r['N_Cumulative_Canonical'])}` | "
            f"`{fmt_num(r['Expected_Max_Ann_SR0'], 3)}` | **`{fmt_num(r['DSR_p_value'], 3)}`** |"
        )

    # SECTION 7: SHADOW INDUSTRY / SECTOR CONFIRMERS
    lines.append('\n---\n## 7. Round 2 Priority #1 — Shadow Industry & Sector Confirmers (`Broad + Sector + Industry 三层确认`)\n')
    lines.append('### 7.1 Full-Sample Diagnostic Breakdown (`2009-01` – `2026-09`, `213` months)\n')
    lines.append('| Strategy | Shadow Confirmation Slice | Months ($N$) | Share | Mean 1M | Median 1M | Ann. Compounded | Excess Sharpe | Win Rate | Worst Month | Consensus Stock CAGR |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_sh_diag.iterrows():
        lines.append(
            f"| `{r['Strategy']}` | `{r['Consensus_State']}` | `{int(r['Months_N'])}` | `{fmt_pct(r['Share_Pct'], 1)}` | "
            f"`{fmt_pct(r['Mean_Mo_Ret'], 2, True)}` | `{fmt_pct(r['Median_Mo_Ret'], 2, True)}` | "
            f"**`{fmt_pct(r['Ann_Compounded_Ret'], 2)}`** | **`{fmt_num(r['Ann_Sharpe_Excess'], 2)}`** | "
            f"**`{fmt_pct(r['Win_Rate'], 1)}`** | `{fmt_pct(r['Worst_Mo_Ret'], 2, True)} ({r['Worst_Mo_YM']})` | `{fmt_pct(r['Consensus_Stock_Ann_CAGR'], 1)}` |"
        )

    lines.append('\n### 7.2 Subperiod Stability (`2009–2018` First Half vs `2019–2026` Second Half)\n')
    lines.append('| Subperiod | Shadow Confirmation Slice | Months ($N$) | Mean 1M | Median 1M | Ann. Compounded | Excess Sharpe | Win Rate | Worst Month |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_sh_sub.iterrows():
        lines.append(
            f"| `{r['Strategy']}` | `{r['Consensus_State']}` | `{int(r['Months_N'])}` | "
            f"`{fmt_pct(r['Mean_Mo_Ret'], 2, True)}` | `{fmt_pct(r['Median_Mo_Ret'], 2, True)}` | "
            f"**`{fmt_pct(r['Ann_Compounded_Ret'], 2)}`** | **`{fmt_num(r['Ann_Sharpe_Excess'], 2)}`** | "
            f"**`{fmt_pct(r['Win_Rate'], 1)}`** | `{fmt_pct(r['Worst_Mo_Ret'], 2, True)} ({r['Worst_Mo_YM']})` |"
        )

    # SECTION 8: SHADOW CONFIRMER CONVICTION BACKTESTS
    lines.append('\n---\n## 8. Shadow-Confirmed Conviction Sizing Backtests (`SOXX #1` vs `3-Layer Group #1` vs `2-Leg Shadow Upgrade`)\n')
    lines.append('| Variant | Avg Exp | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | NW $t$ vs Ctrl |')
    lines.append('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_sh_bt.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Avg_Gross_Exp']:.2f}x` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{fmt_pct(r['CAGR_2009_2018'], 2)}` | "
            f"`{fmt_pct(r['CAGR_2019_2026'], 2)}` | `{fmt_pct(r['Ret_2022'], 1, True)}` | `{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 9: STANDALONE SECTOR & INDUSTRY SLEEVES
    lines.append('\n---\n## 9. Round 2 Priority #2 — Standalone Sector & Sub-Industry Champion Sleeves (`SOXX`, `SMH`, `IGV`, `XLE`, `XLV`, `XLI`, `XLF`, `XLY`, `XLU`, `Ex-IT`)\n')
    lines.append('| Sleeve | Group | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Corr vs Tech | Corr vs QQQ | Pick Overlap vs Tech |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_sleeves.iterrows():
        lines.append(
            f"| `{r['Sleeve_Name']}` | `{r['Category']}` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"`{fmt_num(r['Sharpe'], 2)}` | `{fmt_pct(r['Monthly_MaxDD'], 1)}` | "
            f"`{fmt_pct(r['CAGR_2009_2018'], 1)}` | `{fmt_pct(r['CAGR_2019_2026'], 1)}` | "
            f"`{fmt_pct(r['Ret_2022'], 1, True)}` | `{fmt_num(r['Corr_with_Tech_Sleeve'], 2)}` | "
            f"`{fmt_num(r['Corr_with_QQQ_Sleeve'], 2)}` | `{fmt_pct(r['Pick_Overlap_with_Tech_Pct'], 1)}` |"
        )

    # SECTION 10: PORTFOLIO ARCHITECTURES (5-LEG SEMI STRAWMAN VS 4-LEG NON-TECH VS DYNAMIC ROUTING)
    lines.append('\n---\n## 10. Portfolio Architecture Comparison: 5-Leg Semiconductor Strawman vs 4-Leg Non-Tech Champion vs Dynamic Routing\n')
    lines.append('| Variant | Family | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Ex-2022 CAGR | NW $t$ vs Ctrl |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_arch.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Family']}` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{fmt_pct(r['CAGR_2009_2018'], 2)}` | "
            f"`{fmt_pct(r['CAGR_2019_2026'], 2)}` | `{fmt_pct(r['Ret_2022'], 1, True)}` | "
            f"`{fmt_pct(r['CAGR_Ex2022'], 2)}` | `{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 11: EXPERIMENT A & B (UNLEVERED CONCENTRATION + SEP OFF NON-TECH CHAMPION)
    lines.append('\n---\n## 11. Round 3 Experiments A & B — Zero-Leverage Conviction Concentration (`75/25 -> 100%`) & `SEP OFF` Non-Tech Champion Routing\n')
    lines.append('### 11.1 Stock-Level Attribution Inside `3-Leg Consensus` Months: `#1 Consensus Stock` (`100%`) vs `75/25 Blend` vs `QQQ #2 Stock`\n')
    lines.append('| Engine | Consensus Slice | Months ($N$) | `75/25` Ann. CAGR | `#1 Consensus Stock` Mean 1M | `#1 Stock` Ann. CAGR | `#1 Stock` Win Rate | `QQQ #2 Stock` Mean 1M | `QQQ #2` Ann. CAGR | `#1 vs #2` Mean Spread |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_11a.iterrows():
        lines.append(
            f"| `{r['Engine']}` | `{r['Slice']}` | `{int(r['Months_N'])}` | "
            f"`{fmt_pct(r['Standard_75_25_Ann_Compounded'], 1)}` | **`{fmt_pct(r['Consensus_Stock_Mean_1M'], 2, True)}`** | "
            f"**`{fmt_pct(r['Consensus_Stock_Ann_Compounded (100% Weight)'], 1)}`** | **`{fmt_pct(r['Consensus_Win_Rate'], 1)}`** | "
            f"`{fmt_pct(r['QQQ_2nd_Stock_Mean_1M'], 2, True)}` | `{fmt_pct(r['QQQ_2nd_Stock_Ann_Compounded'], 1)}` | "
            f"**`{fmt_pct(r['Spread_Mean_1M (Cons - QQQ2)'], 2, True)}`** |"
        )

    lines.append('\n### 11.2 Full-Portfolio Unlevered Backtests (`1.0x` Cap, Zero Margin): Experiment A, Experiment B, and `A + B`\n')
    lines.append('| Variant | Family | Avg Exp | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Ex-2022 CAGR | NW $t$ vs Ctrl |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_11b.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Family']}` | `{r['Avg_Gross_Exp']:.2f}x` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}` | `{fmt_pct(r['CAGR_2009_2018'], 2)}` | "
            f"`{fmt_pct(r['CAGR_2019_2026'], 2)}` | `{fmt_pct(r['Ret_2022'], 1, True)}` | "
            f"`{fmt_pct(r['CAGR_Ex2022'], 2)}` | `{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 12: EXPERIMENT C & A+B+C COMBINED
    lines.append('\n---\n## 12. Round 3 Experiment C & `A + B + C` Combined — Tiered Conviction Scaling (`70%–78.8%` CAGR Family)\n')
    lines.append('| Variant | Family | Avg Exp | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | Daily Calmar | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | NW $t$ vs Ctrl |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_12.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Family']}` | `{r['Avg_Gross_Exp']:.2f}x` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"**`{fmt_pct(r['Daily_MaxDD_5651ec2'], 2)}`** | `{fmt_num(r['Calmar_Daily'], 2)}` | "
            f"`{fmt_pct(r['CAGR_2009_2018'], 2)}` | `{fmt_pct(r['CAGR_2019_2026'], 2)}` | "
            f"`{fmt_pct(r['Ret_2022'], 1, True)}` | `{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    # SECTION 13: EXPERIMENT D (2X DAILY-RESET SINGLE-STOCK ETF)
    lines.append('\n---\n## 13. Round 3 Experiment D — Single-Stock `2x Daily-Reset ETF` (`Zero Margin Account`, Exact Daily Compounding + Volatility Decay + Swap/Expense Drag)\n')
    lines.append('| Variant | Family | CAGR (`09–26`) | Excess Sharpe | Monthly MaxDD | `2009–2018` CAGR | `2019–2026` CAGR | `2023–2026` CAGR | `2022` Return | NW $t$ vs Ctrl |')
    lines.append('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |')
    for _, r in df_13.iterrows():
        lines.append(
            f"| `{r['Variant']}` | `{r['Family']}` | **`{fmt_pct(r['CAGR_09_26'], 2)}`** | "
            f"**`{fmt_num(r['Sharpe'], 3)}`** | `{fmt_pct(r['Monthly_MaxDD'], 2)}` | "
            f"`{fmt_pct(r['CAGR_2009_2018'], 2)}` | `{fmt_pct(r['CAGR_2019_2026'], 2)}` | "
            f"**`{fmt_pct(r['CAGR_2023_2026'], 2)}`** | `{fmt_pct(r['Ret_2022'], 1, True)}` | "
            f"`{fmt_num(r['NW_t_vs_Ctrl'], 2, True)}` |"
        )

    out_md = os.path.join(HERE, 'CONSENSUS_BURST_MODE_AUDIT_REPORT.md')
    with open(out_md, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('Report written to:', out_md)


if __name__ == '__main__':
    main()
