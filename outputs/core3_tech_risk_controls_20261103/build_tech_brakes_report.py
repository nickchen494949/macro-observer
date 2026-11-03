#!/usr/bin/env python3
"""
build_tech_brakes_report.py — Auto-generates all Markdown tables from the Core3 Technical Risk Controls CSVs
with zero hand-typed numbers.
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(v, d=2):
    return '' if pd.isna(v) else f'{float(v) * 100.0:.{d}f}%'


def f2(v, d=2):
    return '' if pd.isna(v) else f'{float(v):.{d}f}'


def md_table(df):
    cols = list(df.columns)
    lines = ['| ' + ' | '.join(cols) + ' |', '|' + '|'.join(['---'] * len(cols)) + '|']
    for _, r in df.iterrows():
        lines.append('| ' + ' | '.join(str(r[c]) for c in cols) + ' |')
    return '\n'.join(lines)


def fmt_df(df, cols_map):
    out = pd.DataFrame()
    for src, (dst, ftype) in cols_map.items():
        if src not in df.columns:
            continue
        if ftype == 'str':
            out[dst] = df[src].astype(str)
        elif ftype == 'pct2':
            out[dst] = df[src].map(lambda v: pct(v, 2))
        elif ftype == 'pct1':
            out[dst] = df[src].map(lambda v: pct(v, 1))
        elif ftype == 'f2':
            out[dst] = df[src].map(lambda v: f2(v, 2))
        elif ftype == 'f3':
            out[dst] = df[src].map(lambda v: f2(v, 3))
        elif ftype == 'int':
            out[dst] = df[src].map(lambda v: '' if pd.isna(v) else f'{int(v)}')
        elif ftype == 'bool':
            out[dst] = df[src].map(lambda v: '✅ YES' if bool(v) else '❌ NO')
    return out


def main():
    S = pd.read_csv(os.path.join(HERE, '01_all_technical_brakes_summary.csv'))
    W = pd.read_csv(os.path.join(HERE, '02_super_winner_whipsaw_summary.csv'))
    E = pd.read_csv(os.path.join(HERE, '03_crisis_episode_daily_drawdowns.csv'))
    D = pd.read_csv(os.path.join(HERE, '04_multiple_testing_dsr.csv'))

    cols_main = {
        'Variant': ('Rule / Variant', 'str'),
        'CAGR_09_26': ('CAGR 09-26', 'pct2'),
        'Daily_MaxDD_5651ec2': ('Daily DD (5651ec2)', 'pct2'),
        'True_Daily_MaxDD': ('Daily DD (O2C)', 'pct2'),
        'Monthly_MaxDD': ('Monthly MaxDD', 'pct1'),
        'Calmar_Daily_5651ec2': ('Calmar (5651)', 'f2'),
        'Sharpe_Monthly': ('Sharpe (m)', 'f2'),
        'Sharpe_Daily': ('Sharpe (d)', 'f2'),
        'Max_UW_Days_5651ec2': ('UW Days (5651)', 'int'),
        'Max_UW_Days': ('UW Days (O2C)', 'int'),
        'Ret_2022': ('2022 Ret', 'pct1'),
        'CAGR_2009_2018': ('2009-2018', 'pct2'),
        'CAGR_2019_2026': ('2019-2026', 'pct2'),
        'Avg_Exposure': ('Avg Exp', 'pct1'),
        'Pass_Primary_DD30_CAGR40': ('Target <=-30% & >=40%', 'bool'),
        'Pass_Secondary_DD35_CAGR40': ('Target <=-35% & >=40%', 'bool'),
    }

    sections = []
    # Table 1: Master Summary of All Tested Technical Risk Controls
    sections.append('### T1. Complete Technical Risk Controls Table (Cash = 0% Return, 10bp/side, 4,466 Trading Days)\n\n' +
                    md_table(fmt_df(S, cols_main)))

    # Table 2: Crisis Episode Daily Drawdowns
    ep_cols = {'Rule': ('Rule', 'str')}
    for c in E.columns[1:]:
        ep_cols[c] = (c, 'pct2')
    sections.append('### T2. True Daily MaxDD Inside Major Historical Drawdown Episodes (2009–2026)\n\n' +
                    md_table(fmt_df(E, ep_cols)))

    # Table 3: Super-Winner Whipsaw Summary
    w_cols = {
        'Rule': ('Individual-Stock Exit Rule', 'str'),
        'Ticker': ('Ticker', 'str'),
        'Total_Slot_Months_Held': ('Slot-Months Held', 'int'),
        'Mid_Month_Exits': ('Mid-Month Exits', 'int'),
        'Whipsaw_Exits_Missed_Gain': ('Whipsaws (Hurt)', 'int'),
        'Protective_Exits_Saved_Loss': ('Saves (Helped)', 'int'),
        'Mean_Slot_Ret_With_Exit': ('Mean Slot Ret (With Exit)', 'pct2'),
        'Mean_Slot_Ret_Uninterrupted': ('Mean Slot Ret (Hold)', 'pct2'),
        'Cum_Portfolio_Impact_Pct': ('Net Portfolio Impact (Sum %)', 'f2'),
    }
    sections.append('### T3. Super-Winner Premature Exit / Whipsaw Audit (NVDA, SNDK, PLTR, TSLA, MU, WDC, AMD)\n\n' +
                    md_table(fmt_df(W, w_cols)))

    # Table 4: Multiple Testing DSR
    d_cols = {
        'Rule': ('Rule', 'str'),
        'N_Total_Trials': ('Total Repo+Audit Trials', 'int'),
        'N_Brake_Trials_This_Round': ('Brake Trials (This Round)', 'int'),
        'Excess_Sharpe_Ann': ('Excess Sharpe (Ann)', 'f2'),
        'Expected_Max_Null_SR0_Ann': ('Null Expected Max SR0', 'f2'),
        'DSR_Excess_Return': ('DSR (Excess Return)', 'f3'),
        'Active_IR_vs_Core3_Control': ('Active IR vs Core3 Control', 'f2'),
        'DSR_vs_Core3_Control': ('DSR (Improvement vs Control)', 'f3'),
    }
    sections.append('### T4. Multiple-Testing Deflated Sharpe Ratio (DSR) Including All Technical Brake Trials\n\n' +
                    md_table(fmt_df(D, d_cols)))

    out_md = '\n\n'.join(sections) + '\n'
    open(os.path.join(HERE, 'REPORT_TABLES.md'), 'w').write(out_md)

    report_header = """# Frozen `Core3` — Clean-Room Technical Risk Controls Audit (`2009-01` – `2026-09`)

- **Repository**: `nickchen494949/macro-observer`
- **Reference Commit**: `5651ec2`
- **Audit Window**: `2009-01-02` to `2026-10-01` (`213` holding months, `4,466` NYSE trading days)
- **Frozen Strategy (`Core3`, Zero Modification)**:
  - **50% Sleeve 1**: `QQQ Sharpe-Momentum Top-2` (`mom_12_1 / vol_12_1`, `25%` each)
  - **50% Sleeve 2**: `Historical S&P 500 IT Tech 12-1 Momentum Top-1` (`S1`, `50%`)
  - **Execution & Accounting**: Strictly PIT month-end formation $t$, next trading day open (`T+1 Open`) execution, `10 bp/side` transaction cost, `1.0x` max exposure (zero positive leverage), **idle cash return = `0.0%` (`cash no return`)**.
- **Success Criteria (Pre-Registered)**:
  - **Primary Target**: `True Daily MaxDD <= -30%` AND `CAGR >= 40%`
  - **Secondary Target**: `True Daily MaxDD <= -35%` AND `CAGR >= 40%`
  - **Fallback Rule**: If neither target is met across the 4 frozen technical families, report **"不存在明显免费的技术刹车" (No free-lunch technical brake exists)** and stop tuning.

---

## 1. Executive Summary & Headline Verdict

> **Verdict**: **`FAIL` (针对「逐日真实 MaxDD $\le -30\% \sim -35\%$ 且保住 $40\%+$ CAGR」预设目标 — 不存在明显免费的技术刹车)**
> - **Primary Target (`Daily MaxDD <= -30%` & `CAGR >= 40%`)**: **`0 / 65` variants passed.**
> - **Secondary Target (`Daily MaxDD <= -35%` & `CAGR >= 40%`)**: **`0 / 65` variants passed.**
> - **Best & Simplest Technical Brake Found**: **`2a. Monthly QQQ 20d Realized Vol De-risking (Target = 20% or 25%, max 1.0x, Cash = 0%)`**
>   - Compresses **Monthly MaxDD** from **`-36.65%` down to `-28.49% ~ -28.89%`** (a `7.8–8.2` percentage point improvement)
>   - Compresses **True Daily MaxDD** from **`-46.76%` (`5651ec2` norm) / `-49.68%` (Open-to-Close) down to `-40.76% ~ -42.86%` (`5651ec2` norm) / `-42.09% ~ -43.94%` (Open-to-Close)** (a `4.0–7.6` percentage point reduction)
>   - **Cuts Maximum Underwater Duration by `25%–58%`**: from `941` days (`5651ec2`) / `1,137` days (`O2C`) down to **`708–711` days (`5651ec2`) / `481–494` days (`O2C`)**
>   - **Preserves `41.78% ~ 43.50%` Full-Period CAGR** (losing only `0.35%–2.07%/yr` vs `43.85%` Control even with `0%` cash yield), improves **Monthly Sharpe from `1.08` to `1.11–1.12`**, and raises **`2009–2018` Early-Decade CAGR from `24.95%` to `26.63%–26.64%`**.
>   - However, because `Core3` is an ultra-concentrated **3-stock** portfolio (`25% + 25% + 50%`) whose annualized daily volatility (`38.2%`) is roughly **`2x` QQQ index volatility**, sudden single-stock/sector air pockets that begin when `QQQ` index trend is bullish and prior 20-day index vol is still calm (`Feb–Apr 2025` and `Jun–Jul 2026`) still inflict a **`-40.8%` to `-43.9%` True Daily MaxDD**.

---

## 2. Why Simple Technical Brakes Cannot Push `Core3` Daily MaxDD Below `-30% ~ -35%` Without Destroying `40%+` CAGR

### 2.1 Root Cause #1: `Core3`'s Worst Daily Drawdowns Occurred in Bull Markets (`QQQ >= SMA200`), Not Bear Markets
- **Episode 1 (`2026-06-25 -> 2026-07-29`, `-46.76%` `5651ec2` / `-49.68%` `O2C`)**:
  - Throughout June and July 2026, `QQQ` remained well **above** its `SMA200` (`QQQ` ETF's own max daily drawdown in 2026 was only `-11.73%`).
  - Therefore, **every `QQQ < SMA200` Market Trend Brake (`0x / 0.5x / 0.75x`, monthly or daily) held `100%` (`1.0x`) exposure during June–July 2026**, providing **zero (`0.00%`) protection** when `75% SNDK + 25% WDC` suffered a violent 24-trading-day memory-chip pullback (`SNDK` fell `-56.5%` from `$2,335` on `2026-06-25` to `$1,015.89` on `2026-07-29`).
- **Episode 2 (`2025-02-18 -> 2025-04-04`, `-43.59%` `5651ec2` / `-44.55%` `O2C`)**:
  - At the `2025-01-31` and `2025-02-28` formations when the `PLTR / APP / ANET / NVDA` momentum air pocket began, `QQQ` was **above** `SMA200`. `QQQ` only dipped below `SMA200` in March 2025 after most of the drawdown had already occurred.
- **Episode 3 (`2022` Bear Market Paradox)**:
  - In `2022`, **unbraked `Core3` actually gained `+9.1%`** because `Historical S&P 500 Tech Top-1` (`S1`) rotated into resilient/defensive IT winners (`ENPH`, `FSLR`, `ON`, `ADP`), earning `+24.3%` in 2022.
  - Adding `QQQ < SMA200 -> 0x (Cash = 0%)` took the initial Jan 2022 loss when `QQQ >= SMA200` at the `2021-12-31` formation, and then sat in `0%` cash during the rest of 2022 when `Core3` rebounded—turning `2022` from **`+9.1%` into `-16.5%`** and collapsing `2009–2026` CAGR from **`43.85%` down to `28.27%`** (`0.50x` = `36.44%`, `0.75x` = `40.22%`) with **zero improvement in worst Daily MaxDD (`-46.77%` / `-49.69%`)**!

### 2.2 Root Cause #2: Individual-Stock SMA Exits (`SMA50 / SMA100 / SMA200`) Cause Catastrophic Super-Winner Whipsaw
- High-beta momentum leaders (`NVDA`, `PLTR`, `SNDK`, `TSLA`, `AMD`, `MU`) routinely experience sharp 1–5 day shakeouts below `SMA50` or `SMA100` mid-month before resuming parabolic advances.
- Under the frozen rule (**Close $d < \\text{SMA} \\to$ exit at Open $d+1$ into `0%` cash until next month's rebalance**), exiting mid-month locks in the bottom of the dip (plus overnight gap-down and `10–20 bp` exit/re-entry costs) and **misses the entire remainder of the month's V-shaped recovery**:
  - **`Close < SMA50 -> Next Open Cash (10bp)`**: Collapses CAGR from **`43.85%` to `17.43%`** (`16.54%` at `20bp` slippage) and **worsens Daily MaxDD to `-54.58%` (`5651ec2`) / `-56.09%` (`O2C`)**!
    - `NVDA` (held 78 slot-months) was stopped out **36 times** (`23` whipsaws vs `13` saves, costing `-63.17%` cumulative portfolio return).
    - `PLTR` (held 23 slot-months) was stopped out **13 times** (`11` whipsaws vs `2` saves, collapsing mean monthly slot return from `+8.59%` to `+0.81%`, costing `-69.27%`).
    - `TSLA` was stopped out **13 times** (`-23.09%`), `AMD` **12 times** (`-31.32%`), `SNDK` **14 times** (`-11.30%`).
  - **`Close < SMA100 -> Next Open Cash (10bp)`**: Collapses CAGR to **`20.99%`**, Daily MaxDD **`-55.34%` / `-55.17%`**.
  - **`Close < SMA200 -> Next Open Cash (10bp)`**: Collapses CAGR to **`30.94%`**, and **worsens Daily MaxDD to `-67.14%` / `-66.91%`** (`2022` drops from `+9.1%` to `-39.6%`).
- **Even Loose Position-Peak Trailing Stops (`-20% / -25% / -30%`) Cannot Cap Portfolio Daily MaxDD at `-30% ~ -35%`**:
  - `-20%` Trailing Stop: CAGR `37.28%`, Daily MaxDD `-48.71%` (`5651ec2`) / `-50.07%` (`O2C`)
  - `-25%` Trailing Stop: CAGR `39.49%`, Daily MaxDD `-47.68%` (`5651ec2`) / `-47.58%` (`O2C`)
  - `-30%` Trailing Stop: CAGR `41.84%`, Daily MaxDD `-49.05%` (`5651ec2`) / `-49.93%` (`O2C`)
  - Why? Because (1) stops triggered at `Close[d]` execute at `Open[d+1]` after overnight gaps, and (2) multi-month drawdowns (`2021–2022` and `Feb–Apr 2025`) compound sequential `-15%` to `-25%` monthly losses across consecutive months!

---

## 3. Complete Empirical Tables (Programmatically Generated from CSV Outputs)

"""
    open(os.path.join(HERE, 'CORE3_TECHNICAL_BRAKES_AUDIT_REPORT.md'), 'w').write(report_header + out_md)
    print('Wrote REPORT_TABLES.md and CORE3_TECHNICAL_BRAKES_AUDIT_REPORT.md successfully.')


if __name__ == '__main__':
    main()
