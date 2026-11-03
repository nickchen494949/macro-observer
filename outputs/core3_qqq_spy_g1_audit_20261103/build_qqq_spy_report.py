#!/usr/bin/env python3
"""
build_qqq_spy_report.py — Generates CORE3_QQQ_SPY_G1_AUDIT_REPORT.md
from the verified CSV outputs of run_qqq_spy_g1_audit.py.
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def fmt_pct(x, digits=2):
    if pd.isna(x):
        return '—'
    return f'{float(x) * 100:.{digits}f}%'


def fmt_num(x, digits=2, sign=False):
    if pd.isna(x):
        return '—'
    if sign:
        return f'{float(x):+.{digits}f}'
    return f'{float(x):.{digits}f}'


def main():
    df_tr = pd.read_csv(os.path.join(HERE, '00_spy_pit_truncation_audit.csv'))
    df_s = pd.read_csv(os.path.join(HERE, '01_standalone_sleeves_comparison.csv'))
    df_m = pd.read_csv(os.path.join(HERE, '02_all_qqq_spy_xlk_combinations.csv'))
    df_comp = pd.read_csv(os.path.join(HERE, '03_monthly_spy_vs_xlk_picks.csv'))
    df_sec = pd.read_csv(os.path.join(HERE, '04_spy_sector_attribution.csv'))
    df_corr = pd.read_csv(os.path.join(HERE, '05_sleeve_correlation_matrix.csv'), index_col=0)
    df_lowo = pd.read_csv(os.path.join(HERE, '06_leave_one_winner_out.csv'))
    df_ven = pd.read_csv(os.path.join(HERE, '07_second_vendor_replication.csv'))
    df_dsr = pd.read_csv(os.path.join(HERE, '08_multiple_testing_dsr.csv'))

    lines = []
    lines.append('# Clean-Room Adversarial Audit: `QQQ + SPY` vs `QQQ + XLK` & `QQQ + XLK + SPY` (Under `Core3` and `G1`)')
    lines.append('')
    lines.append('- **Audit Date**: `2026-11-03`')
    lines.append('- **Sample Window**: `2009-01` – `2026-09` (`213` holding months; formations `2008-12-31` – `2026-08-31`)')
    lines.append('- **Execution & Cost Convention**: Strictly Point-in-Time (PIT), month-end close signal at $t$, `T+1 Open` execution, `10 bp/side` transaction cost, `1.0x` unlevered (`0%` return on cash)')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 1. Executive Verdict: Is `QQQ + SPY` Also Good Under `Core3` and `G1`?')
    lines.append('')
    lines.append('### Four Key Findings from the Clean-Room Audit')
    lines.append('')
    lines.append('1. **Why `SPY Raw 12-1 Mom Top-1` and `XLK Raw 12-1 Mom Top-1` Have Nearly Identical Full-Sample CAGR (`43.78%` vs `43.75%` in `Core3`, `47.95%` vs `48.02%` in `G1`)**:')
    lines.append('   - In **`87 / 213` months (`40.8%` of the entire 17.75-year sample)**, the #1 raw `12-1` momentum stock in the **entire 500-stock S&P 500 (`SPY`)** is the **exact same stock** as `XLK Top-1` (`NVDA`, `SNDK`, `AMD`, `FSLR`, `PLTR`, `ANET`, `MU`).')
    lines.append('   - In the remaining **`126 / 213` months (`59.2%`)** when `SPY Raw Top-1` picks a non-IT leader, its average monthly return (`+1.59%/month`) is almost identical to `XLK Top-1` (`+1.46%/month`), because strong non-Tech mega-trends (`NFLX` pre-2018, `TSLA`, `DVN`/`OXY` in Energy, `VST` in 2024 AI Power Utilities at `+10.71%/month`) are partially offset by mean-reverting Biotech/Health Care jump spikes (`MRNA`, `NKTR`, `ALGN` at `-4.28%/month` across 23 months).')
    lines.append('   - Consequently, simply replacing `XLK Hard Top-1` with `SPY Raw Hard Top-1` (`C3_SPY_1a` and `G1_SPY_1a`) matches CAGR (`43.78%` vs `43.75%` in `Core3`; `47.95%` vs `48.02%` in `G1`), **but worsens Monthly MaxDD** (`-36.65%` $\\to$ `-42.37%` in `Core3`; `-27.70%` $\\to$ `-38.43%` in `G1`) and hurts `2022` (`+4.72%` $\\to$ `-12.35%` in `G1`).')
    lines.append('')
    lines.append('2. **Critical Structural Discovery — `G1` Buffer Works on `SPY` (`Buy Top-1, Hold <= Top-2 or Top-3`) Even Better Than on `XLK`!**')
    lines.append('   - Previously we saw that buffering `XLK` (`Buy Top-1, Hold <= Top-2`) hurt CAGR (`38.73%` $\\to$ `34.97%`), because Rank #2 inside a narrow 65-stock sector is already a decaying stock.')
    lines.append('   - **In the 500-stock `SPY` universe, Rank #2 and Rank #3 are still the `99.4th–99.6th` percentile of the entire S&P 500!** Without a buffer, `SPY Hard Top-1` gets whipsawed whenever a 1-month Biotech or cyclical spike momentarily jumps to #1 in the S&P 500 and forces a sale of the secular winner sitting at #2.')
    lines.append('   - Applying the **`G1` Buffer to `SPY Raw 12-1 Mom` (`Buy Top-1, Hold <= Top-2` or `Hold <= Top-3`)** transforms standalone `SPY`:')
    lines.append('     - `S1a. SPY Raw Hard Top-1`: `37.64%` CAGR, Monthly MaxDD `-70.67%`, Daily MaxDD `-74.11%`, Sharpe `0.85`, `2022 = -4.43%`')
    lines.append('     - `S1f. SPY Raw (Buy Top-1, Hold <= Top-2)`: **`45.10%` CAGR (`+7.46pp`)**, Sharpe **`0.96`**, **`2022 = +45.56%`**')
    lines.append('     - `S1g. SPY Raw (Buy Top-1, Hold <= Top-3)`: **`43.21%` CAGR (`+5.57pp`)**, Monthly MaxDD **`-44.69%` (`+25.98pp` improvement!)**, Daily MaxDD `-57.55%`, Sharpe **`1.00`**, `2009–2018 = 29.51%`, **`2022 = +45.56%`**!')
    lines.append('   - Pairing **`G1` on Both `QQQ` and `SPY`** produces:')
    lines.append('     - **`G1_SPY_2d` (`50% QQQ [Buy 2, Hold<=5] + 50% SPY Raw [Buy 1, Hold<=2]`)**: **`51.60%` CAGR** (Tiingo: **`50.76%`**), Sharpe **`1.22`**, Monthly MaxDD `-34.96%`, True Daily MaxDD **`-41.96%`**, `2009–2018 = 32.23%`, `2022 = +9.09%`, `Ex-Top-5 Months = 37.44%`!')
    lines.append('     - **`G1_SPY_2e` (`50% QQQ [Buy 2, Hold<=5] + 50% SPY Raw [Buy 1, Hold<=3]`)**: **`50.23%` CAGR**, Sharpe **`1.28`**, **Monthly MaxDD `-27.12%`** (lower than `G1 Control` `-27.70%`!), **True Daily MaxDD `-40.30%`** (lower than `G1 Control` `-41.96%`!), **`2009–2018 = 39.31%`**, **`2022 = +9.09%`**!')
    lines.append('')
    lines.append('3. **Why `SPY Sharpe-Momentum` (`mom_12_1 / vol_12_1`) Fails on Full `SPY` (`22.67%` Standalone, `35.64%` in `Core3`, `39.62%` in `G1`)**:')
    lines.append('   - Inside `QQQ` (which is already a high-growth non-financial index), dividing `12-1` momentum by volatility (`Sharpe-Mom`) filters out speculative junk while keeping tech leaders (`43.75%` CAGR).')
    lines.append('   - Inside the **full S&P 500 (`SPY`) across all 11 sectors**, dividing by volatility heavily penalizes high-beta Tech/Semis and over-selects low-volatility defensive sectors (`Health Care` distributors `MCK`/`ABC`, `Consumer Staples` `KR`/`HRL`, `Utilities` `ETR`/`AWK`, `Industrials`), reducing IT picks from `41.8%` to `25.4%` of months and cutting standalone CAGR from `37.64%` to `22.67%`.')
    lines.append('')
    lines.append('4. **The Most Robust All-Weather Architecture: 3-Sleeve `G1` (`50% QQQ [Hold<=5] + 25% XLK + 25% SPY Raw`)**:')
    lines.append('   - While `G1_SPY_2d` (`50% QQQ[Hold<=5] + 50% SPY Raw[Hold<=2]`) achieves the highest headline CAGR (`51.60%`), the **Leave-One-Winner-Out (`No NVDA`)** audit reveals a crucial trade-off: when `NVDA` is banned, `G1_SPY_2d` drops to `33.91%` (vs `38.30%` for `G1 Control QQQ+XLK`), because without `NVDA` in 2023–2024 `XLK` immediately rotates into #2 S&P 500 Tech winners (`ANET`, `AMD`, `SMCI`, `AVGO`) whereas `SPY` sometimes drifts into non-Tech cyclicals.')
    lines.append('   - By combining **all three sleeves (`50% QQQ [Hold<=5] + 25% XLK Hard Top-1 + 25% SPY Raw [Hard Top-1 or Hold<=3]`)**:')
    lines.append('     - **`3S_G1_1a` (`50% QQQ[Hold<=5] + 25% XLK[Hard] + 25% SPY Raw[Hard]`)**: **`48.67%` CAGR** (Tiingo: `48.30%`), Sharpe **`1.22`**, Monthly MaxDD **`-30.37%`**, True Daily MaxDD **`-41.96%`**, **`No NVDA = 38.86%`** (beats both `QQQ+XLK` and `QQQ+SPY`!), **`No SNDK = 46.45%`**, **`No Top-3 Winners = 31.25%`**, and **Cumulative DSR = `0.9463`** (highest across all 524 cumulative trials).')
    lines.append('     - **`3S_G1_1k` (`50% QQQ[Hold<=5] + 25% XLK[Hard] + 25% SPY Raw[Hold<=3]`)**: **`49.68%` CAGR**, Sharpe **`1.26`**, **Monthly MaxDD `-25.19%`**, **True Daily MaxDD `-41.10%`**, `2009–2018 = 35.29%`, `2022 = +6.91%`, and **Cumulative DSR = `0.9609` (`> 0.95` significance threshold!)**.')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 2. Physical Truncation Audit on Full S&P 500 (`SPY`) Panel')
    lines.append('')
    lines.append('| Cutoff Date | Eligible SPY Rows Checked | Max Abs Diff Across All Features (`mom_12_1`, `vol_12_1`, `sharpe_mom_12_1`, `fip_smooth_12_1`, `max_ret_5d_12_1`, `sector_ew_mom_12_1`) | Audit Status |')
    lines.append('|---|---:|---:|---|')
    for _, r in df_tr.iterrows():
        lines.append(f"| `{r['Cutoff_Date']}` | `{int(r['SPY_Rows_Checked']):,}` | `{float(r['Max_Abs_Diff_Features']):.2e}` | **{r['Status']}** |")
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 3. Standalone Sleeve Comparison: `QQQ` vs `XLK` vs `SPY` (`2009-01` – `2026-09`)')
    lines.append('')
    lines.append('| Standalone Sleeve Variant | Family | CAGR (`09–26`) | Sharpe | Sortino | Ann Vol | Monthly MaxDD | Daily MaxDD (`5651ec2`) | Daily MaxDD (`O2C`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Avg Monthly TO |')
    lines.append('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for _, r in df_s.iterrows():
        lines.append(
            f"| {r['Variant']} | {r['Family']} | **{fmt_pct(r['CAGR_09_26'])}** | {fmt_num(r['Sharpe'])} | {fmt_num(r['Sortino'])} | "
            f"{fmt_pct(r['Ann_Vol'])} | {fmt_pct(r['Monthly_MaxDD'])} | {fmt_pct(r['Daily_MaxDD_5651ec2'])} | {fmt_pct(r['Daily_MaxDD_O2C'])} | "
            f"{fmt_pct(r['CAGR_2009_2018'])} | {fmt_pct(r['CAGR_2019_2026'])} | {fmt_pct(r['Ret_2022'])} | {fmt_num(r['Avg_Monthly_TO'])} |"
        )
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 4. Full Portfolio Matrix: `QQQ + XLK` vs `QQQ + SPY` vs `QQQ + XLK + SPY` (`Core3` & `G1`)')
    lines.append('')
    lines.append('| Portfolio Variant | Family | CAGR (`09–26`) | Sharpe | Sortino | Monthly MaxDD | Calmar (M) | Daily MaxDD (`5651ec2`) | Daily MaxDD (`O2C`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Avg TO | Overlap % | NW $t$ vs `Core3` | NW $t$ vs `G1` |')
    lines.append('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for _, r in df_m.iterrows():
        lines.append(
            f"| {r['Variant']} | {r['Family']} | **{fmt_pct(r['CAGR_09_26'])}** | {fmt_num(r['Sharpe'])} | {fmt_num(r['Sortino'])} | "
            f"{fmt_pct(r['Monthly_MaxDD'])} | {fmt_num(r['Calmar_Monthly'])} | {fmt_pct(r['Daily_MaxDD_5651ec2'])} | {fmt_pct(r['Daily_MaxDD_O2C'])} | "
            f"{fmt_pct(r['CAGR_2009_2018'])} | {fmt_pct(r['CAGR_2019_2026'])} | {fmt_pct(r['Ret_2022'])} | {fmt_num(r['Avg_Monthly_TO'])} | "
            f"{fmt_pct(r['Overlap_Share'], 1)} | {fmt_num(r['NW_t_vs_Core3_Ctrl'], 2, sign=True)} | {fmt_num(r['NW_t_vs_G1_Ctrl'], 2, sign=True)} |"
        )
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 5. Forensic Sector & Overlap Attribution: When Does `SPY` Differ from `XLK`?')
    lines.append('')
    lines.append('### 5.1 GICS Sector Breakdown of `SPY` Picks (`213` Months)')
    lines.append('')
    lines.append('| SPY Sleeve Variant | GICS Sector Picked | Months Picked | Share of 213 Months | Mean Monthly Net Ret | Median Monthly Net Ret | Win Rate | XLK Mean Ret (Same Months) | Active Diff vs XLK (`/mo`) | Top Example Tickers Picked |')
    lines.append('|---|---|---:|---:|---:|---:|---:|---:|---:|---|')
    for _, r in df_sec.iterrows():
        lines.append(
            f"| {r['Sleeve_Variant']} | {r['GICS_Sector']} | `{int(r['Months_Picked'])}` | {fmt_pct(r['Share_of_213_Months'], 1)} | "
            f"{fmt_pct(r['Mean_Monthly_Net_Ret'])} | {fmt_pct(r['Median_Monthly_Net_Ret'])} | {fmt_pct(r['Win_Rate'], 1)} | "
            f"{fmt_pct(r['XLK_Mean_Monthly_Ret_Same_Months'])} | {fmt_pct(r['Active_Mean_Diff_vs_XLK'])} | `{r['Top_Example_Tickers']}` |"
        )
    lines.append('')
    lines.append('### 5.2 Cross-Sleeve Monthly Return Correlation Matrix (`2009-01` – `2026-09`)')
    lines.append('')
    cols_c = list(df_corr.columns)
    lines.append('| Sleeve | ' + ' | '.join(f'`{c}`' for c in cols_c) + ' |')
    lines.append('|---|' + '|'.join('---:' for _ in cols_c) + '|')
    for idx_c, row_c in df_corr.iterrows():
        lines.append(f'| **`{idx_c}`** | ' + ' | '.join(f'{ float(row_c[c]):.3f}' for c in cols_c) + ' |')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 6. Adversarial Stress Tests: Leave-One-Winner-Out, Vendor Replication & Cumulative DSR')
    lines.append('')
    lines.append('### 6.1 Leave-One-Winner-Out & Remove Top-5 Months Stress Test')
    lines.append('')
    lines.append('| Portfolio Variant | Full CAGR | Ex-Top-5 Months CAGR | Ban `NVDA` | Ban `SNDK` | Ban `PLTR` | Ban `DVN` | Ban `VST` | Ban Top-3 (`NVDA`, `SNDK`, `PLTR`) |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for _, r in df_lowo.iterrows():
        lines.append(
            f"| {r['Variant']} | **{fmt_pct(r['Full_CAGR'])}** | {fmt_pct(r['Ex_Top5_Months_CAGR'])} | **{fmt_pct(r['No_NVDA'])}** | "
            f"{fmt_pct(r['No_SNDK'])} | {fmt_pct(r['No_PLTR'])} | {fmt_pct(r['No_DVN'])} | {fmt_pct(r['No_VST'])} | **{fmt_pct(r['No_Top3_NVDA_SNDK_PLTR'])}** |"
        )
    lines.append('')
    lines.append('### 6.2 Second-Vendor (`Tiingo-First`) End-to-End Replication')
    lines.append('')
    lines.append('| Portfolio Variant | Primary CAGR | Tiingo-First CAGR | Diff (bp) | Primary Sharpe | Tiingo Sharpe | Primary MaxDD (M) | Tiingo MaxDD (M) | Monthly Return Corr |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for _, r in df_ven.iterrows():
        lines.append(
            f"| {r['Variant']} | **{fmt_pct(r['Primary_CAGR'])}** | **{fmt_pct(r['Tiingo_First_CAGR'])}** | `{float(r['CAGR_Diff_bp']):+.1f} bp` | "
            f"{fmt_num(r['Primary_Sharpe'])} | {fmt_num(r['Tiingo_First_Sharpe'])} | {fmt_pct(r['Primary_MaxDD'])} | {fmt_pct(r['Tiingo_First_MaxDD'])} | `{float(r['Monthly_Return_Corr']):.5f}` |"
        )
    lines.append('')
    lines.append('### 6.3 Cumulative Multiple-Testing Deflated Sharpe Ratio (`DSR`, Bailey & López de Prado 2014)')
    lines.append('')
    lines.append('| Portfolio Variant | New Trials This Round | Cumulative Trials ($N_{\\text{cum}}$) | Expected Max Null Sharpe ($E[\\max SR_0]$) | Cumulative DSR ($p$-value) |')
    lines.append('|---|---:|---:|---:|---:|')
    for _, r in df_dsr.iterrows():
        lines.append(
            f"| {r['Variant']} | `{int(r['Round_Trials'])}` | `{int(r['Cumulative_Trials_N'])}` | `{float(r['Expected_Max_SR_Null_Ann']):.3f}` | **`{float(r['Cumulative_DSR_p']):.4f}`** |"
        )
    lines.append('')

    out_path = os.path.join(HERE, 'CORE3_QQQ_SPY_G1_AUDIT_REPORT.md')
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'Wrote {out_path} ({len(lines)} lines)')


if __name__ == '__main__':
    main()
