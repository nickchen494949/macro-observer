# Clean-Room Adversarial Audit: `QQQ + SPY` vs `QQQ + XLK` & `QQQ + XLK + SPY` (Under `Core3` and `G1`)

- **Audit Date**: `2026-11-03`
- **Sample Window**: `2009-01` – `2026-09` (`213` holding months; formations `2008-12-31` – `2026-08-31`)
- **Execution & Cost Convention**: Strictly Point-in-Time (PIT), month-end close signal at $t$, `T+1 Open` execution, `10 bp/side` transaction cost, `1.0x` unlevered (`0%` return on cash)

---

## 1. Executive Verdict: Is `QQQ + SPY` Also Good Under `Core3` and `G1`?

### Four Key Findings from the Clean-Room Audit

1. **Why `SPY Raw 12-1 Mom Top-1` and `XLK Raw 12-1 Mom Top-1` Have Nearly Identical Full-Sample CAGR (`43.78%` vs `43.75%` in `Core3`, `47.95%` vs `48.02%` in `G1`)**:
   - In **`87 / 213` months (`40.8%` of the entire 17.75-year sample)**, the #1 raw `12-1` momentum stock in the **entire 500-stock S&P 500 (`SPY`)** is the **exact same stock** as `XLK Top-1` (`NVDA`, `SNDK`, `AMD`, `FSLR`, `PLTR`, `ANET`, `MU`).
   - In the remaining **`126 / 213` months (`59.2%`)** when `SPY Raw Top-1` picks a non-IT leader, its average monthly return (`+1.59%/month`) is almost identical to `XLK Top-1` (`+1.46%/month`), because strong non-Tech mega-trends (`NFLX` pre-2018, `TSLA`, `DVN`/`OXY` in Energy, `VST` in 2024 AI Power Utilities at `+10.71%/month`) are partially offset by mean-reverting Biotech/Health Care jump spikes (`MRNA`, `NKTR`, `ALGN` at `-4.28%/month` across 23 months).
   - Consequently, simply replacing `XLK Hard Top-1` with `SPY Raw Hard Top-1` (`C3_SPY_1a` and `G1_SPY_1a`) matches CAGR (`43.78%` vs `43.75%` in `Core3`; `47.95%` vs `48.02%` in `G1`), **but worsens Monthly MaxDD** (`-36.65%` $\to$ `-42.37%` in `Core3`; `-27.70%` $\to$ `-38.43%` in `G1`) and hurts `2022` (`+4.72%` $\to$ `-12.35%` in `G1`).

2. **Critical Structural Discovery — `G1` Buffer Works on `SPY` (`Buy Top-1, Hold <= Top-2 or Top-3`) Even Better Than on `XLK`!**
   - Previously we saw that buffering `XLK` (`Buy Top-1, Hold <= Top-2`) hurt CAGR (`38.73%` $\to$ `34.97%`), because Rank #2 inside a narrow 65-stock sector is already a decaying stock.
   - **In the 500-stock `SPY` universe, Rank #2 and Rank #3 are still the `99.4th–99.6th` percentile of the entire S&P 500!** Without a buffer, `SPY Hard Top-1` gets whipsawed whenever a 1-month Biotech or cyclical spike momentarily jumps to #1 in the S&P 500 and forces a sale of the secular winner sitting at #2.
   - Applying the **`G1` Buffer to `SPY Raw 12-1 Mom` (`Buy Top-1, Hold <= Top-2` or `Hold <= Top-3`)** transforms standalone `SPY`:
     - `S1a. SPY Raw Hard Top-1`: `37.64%` CAGR, Monthly MaxDD `-70.67%`, Daily MaxDD `-74.11%`, Sharpe `0.85`, `2022 = -4.43%`
     - `S1f. SPY Raw (Buy Top-1, Hold <= Top-2)`: **`45.10%` CAGR (`+7.46pp`)**, Sharpe **`0.96`**, **`2022 = +45.56%`**
     - `S1g. SPY Raw (Buy Top-1, Hold <= Top-3)`: **`43.21%` CAGR (`+5.57pp`)**, Monthly MaxDD **`-44.69%` (`+25.98pp` improvement!)**, Daily MaxDD `-57.55%`, Sharpe **`1.00`**, `2009–2018 = 29.51%`, **`2022 = +45.56%`**!
   - Pairing **`G1` on Both `QQQ` and `SPY`** produces:
     - **`G1_SPY_2d` (`50% QQQ [Buy 2, Hold<=5] + 50% SPY Raw [Buy 1, Hold<=2]`)**: **`51.60%` CAGR** (Tiingo: **`50.76%`**), Sharpe **`1.22`**, Monthly MaxDD `-34.96%`, True Daily MaxDD **`-41.96%`**, `2009–2018 = 32.23%`, `2022 = +9.09%`, `Ex-Top-5 Months = 37.44%`!
     - **`G1_SPY_2e` (`50% QQQ [Buy 2, Hold<=5] + 50% SPY Raw [Buy 1, Hold<=3]`)**: **`50.23%` CAGR**, Sharpe **`1.28`**, **Monthly MaxDD `-27.12%`** (lower than `G1 Control` `-27.70%`!), **True Daily MaxDD `-40.30%`** (lower than `G1 Control` `-41.96%`!), **`2009–2018 = 39.31%`**, **`2022 = +9.09%`**!

3. **Why `SPY Sharpe-Momentum` (`mom_12_1 / vol_12_1`) Fails on Full `SPY` (`22.67%` Standalone, `35.64%` in `Core3`, `39.62%` in `G1`)**:
   - Inside `QQQ` (which is already a high-growth non-financial index), dividing `12-1` momentum by volatility (`Sharpe-Mom`) filters out speculative junk while keeping tech leaders (`43.75%` CAGR).
   - Inside the **full S&P 500 (`SPY`) across all 11 sectors**, dividing by volatility heavily penalizes high-beta Tech/Semis and over-selects low-volatility defensive sectors (`Health Care` distributors `MCK`/`ABC`, `Consumer Staples` `KR`/`HRL`, `Utilities` `ETR`/`AWK`, `Industrials`), reducing IT picks from `41.8%` to `25.4%` of months and cutting standalone CAGR from `37.64%` to `22.67%`.

4. **The Most Robust All-Weather Architecture: 3-Sleeve `G1` (`50% QQQ [Hold<=5] + 25% XLK + 25% SPY Raw`)**:
   - While `G1_SPY_2d` (`50% QQQ[Hold<=5] + 50% SPY Raw[Hold<=2]`) and `G1_SPY_2e` (`50% QQQ[Hold<=5] + 50% SPY Raw[Hold<=3]`) achieve the highest 2-sleeve CAGRs (`51.60%` and `50.23%`), the **Leave-One-Winner-Out (`No NVDA`)** audit reveals a crucial trade-off: when `NVDA` is banned, `G1_SPY_2d`/`2e` drop to `33.91%`/`34.44%` (vs `38.30%` for `G1 Control QQQ+XLK`), because without `NVDA` in 2023–2024 `XLK` immediately rotates into #2 S&P 500 Tech winners (`ANET`, `AMD`, `SMCI`, `AVGO`) whereas `SPY` sometimes drifts into non-Tech cyclicals.
   - By combining **all three sleeves (`50% QQQ [Hold<=5] + 25% XLK Hard Top-1 + 25% SPY Raw [Hard Top-1 or Hold<=3]`)**:
     - **`3S_G1_1a` (`50% QQQ[Hold<=5] + 25% XLK[Hard] + 25% SPY Raw[Hard]`)**: **`48.67%` CAGR** (Tiingo: `48.30%`), Excess Sharpe **`1.225`**, Monthly MaxDD **`-30.37%`**, True Daily MaxDD **`-41.96%`**, **`No NVDA = 38.86%`** (beats both `QQQ+XLK` and `QQQ+SPY`!), **`No SNDK = 46.45%`**, **`No Top-3 Winners = 31.25%`**.
     - **`3S_G1_1k` (`50% QQQ[Hold<=5] + 25% XLK[Hard] + 25% SPY Raw[Hold<=3]`)**: **`49.96%` CAGR** (Tiingo: `49.58%`), Excess Sharpe **`1.294`** (`Raw Sharpe = 1.334`), **Monthly MaxDD `-22.61%`**, **True Daily MaxDD `-40.19%`**, `2009–2018 = 35.82%`, `2022 = +8.13%`.

### Official 3-Tier Strategy Hierarchy & Honest Statistical Assessment

| Tier | Role | Strategy Specification | `2009–2026` CAGR | `2009–2018` CAGR | Monthly MaxDD | True Daily MaxDD (`5651ec2`) | Excess Sharpe | NW $t$ vs `Core3` | NW $t$ vs `G1` | Pooled `DSR` ($N=878$ Ex / Raw) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| **1** | **Official Frozen Benchmark** | **`Core3`** (`50% QQQ Sharpe Top-2 Hard + 50% Tech Raw Top-1 Hard`) | `43.75%` | `24.79%` | `-36.65%` | `-46.96%` | `1.077` | `+0.00` | `-1.00` | `0.7078` / `0.7489` |
| **2** | **First Challenger** | **`G1 Control`** (`50% QQQ Sharpe [Buy 2, Hold<=5] + 50% Tech Hard Top-1`) | `48.02%` | `30.99%` | `-27.70%` | `-41.96%` | `1.194` | `+1.00` | `+0.00` | `0.8657` / `0.8932` |
| **3A** | **Strongest 3-Sleeve Challenger** | **`3S_G1_1k`** (`50% QQQ [Hold<=5] + 25% Tech [Hard] + 25% SPY Raw [Buy 1, Hold<=3]`) | **`49.96%`** | **`35.82%`** | **`-22.61%`** | **`-40.19%`** | **`1.294`** | `+0.69` | **`+0.21`** | **`0.9434`** / `0.9588` |
| **3B** | **Strongest 2-Sleeve `QQQ+SPY` Challenger** | **`G1_SPY_2e`** (`50% QQQ [Hold<=5] + 50% SPY Raw [Buy 1, Hold<=3]`) | **`50.23%`** | **`39.31%`** | `-27.12%` | **`-40.30%`** | `1.280` | `+0.52` | **`+0.21`** | **`0.9284`** / `0.9461` |

> [!IMPORTANT]
> **Three Mandatory Statistical & Risk Guardrails (Why We Do Not Claim a Formal 95% Statistical Pass Over `G1`)**:
> 1. **Corrected Cumulative DSR (`N = 878` Canonical / `N = 999` Exhaustive Grid Rows)**: After fixing the prior-trial counter (`789 + 89 = 878` canonical trials across all 7 audit rounds, or `999` including all sensitivity grid rows) and pooling the **actual realized monthly Sharpe ratios of all `878`/`999` historical trials** (`08b_master_all_trials_sharpe_registry.csv`), the expected maximum null Excess Sharpe is $E[\max SR_0] = 0.959$ (`0.964` for $N=999$). Under consistent Excess Sharpe, `G1_SPY_2e` achieves **`DSR = 0.9284`** (`0.9251` at $N=999$) and `3S_G1_1k` achieves **`DSR = 0.9434`** (`0.9406` at $N=999$) — both **below the strict `0.95` threshold** (only `3S_G1_1k` under unadjusted Raw Sharpe reaches `0.9588`).
> 2. **Insignificant Paired $t$-Statistic Relative to `G1 Control`**: Relative to `G1 Control` (`48.02%` CAGR), the paired Newey-West $t$-statistic (`lag=6`) is only **`+0.21`** for both `G1_SPY_2e` and `3S_G1_1k` (`+0.60` for `G1_SPY_2d` and `3S_G1_1j`). Thus, while adding the `SPY Raw [Buy 1, Hold<=3]` sleeve improves `2009–2018` CAGR (`30.99%` $\to$ `35.82%`–`39.31%`) and reduces Monthly MaxDD (`-27.70%` $\to$ `-22.61%`–`-27.12%`), **the ~2pp full-sample CAGR gain over `G1` is not statistically distinguishable from sample noise on its own**.
> 3. **True Daily MaxDD Remains `~ -40.2%`**: Although month-end MaxDD drops to `-22.61%` (`3S_G1_1k`) and `-27.12%` (`G1_SPY_2e`), **True Daily MaxDD (`5651ec2` daily path) is still `-40.19%` and `-40.30%`** (compared to `-46.96%` for `Core3` and `-41.96%` for `G1`). It has not solved the `-25%` to `-30%` daily drawdown problem.

---

## 2. Physical Truncation Audit on Full S&P 500 (`SPY`) Panel

| Cutoff Date | Eligible SPY Rows Checked | Max Abs Diff Across All Features (`mom_12_1`, `vol_12_1`, `sharpe_mom_12_1`, `fip_smooth_12_1`, `max_ret_5d_12_1`, `sector_ew_mom_12_1`) | Audit Status |
|---|---:|---:|---|
| `2012-12-31` | `24,152` | `0.00e+00` | **PASS (0.00e+00)** |
| `2016-06-30` | `44,894` | `0.00e+00` | **PASS (0.00e+00)** |
| `2020-12-31` | `71,841` | `0.00e+00` | **PASS (0.00e+00)** |
| `2024-06-30` | `92,836` | `0.00e+00` | **PASS (0.00e+00)** |

---

## 3. Standalone Sleeve Comparison: `QQQ` vs `XLK` vs `SPY` (`2009-01` – `2026-09`)

| Standalone Sleeve Variant | Family | CAGR (`09–26`) | Sharpe | Sortino | Ann Vol | Monthly MaxDD | Daily MaxDD (`5651ec2`) | Daily MaxDD (`O2C`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Avg Monthly TO |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S0a. QQQ Sharpe-Mom Top-2 [Hard Control] | 1. Standalone Control | **43.75%** | 1.06 | 2.38 | 40.11% | -41.38% | -48.35% | -48.39% | 31.00% | 62.05% | -18.30% | 0.92 |
| S0b. QQQ Sharpe-Mom (Buy Top-2, Hold<=Top-5) [G1 Sleeve] | 1. Standalone Control | **51.21%** | 1.24 | 3.02 | 38.22% | -40.82% | -51.34% | -49.82% | 43.99% | 61.06% | -25.05% | 0.58 |
| S0c. XLK Raw 12-1 Mom Top-1 [Hard Control] | 1. Standalone Control | **38.73%** | 0.89 | 1.63 | 47.83% | -67.04% | -68.77% | -69.68% | 14.48% | 77.74% | 41.59% | 0.80 |
| S0d. XLK Raw 12-1 Mom (Buy Top-1, Hold<=Top-2) | 1. Standalone Control | **34.97%** | 0.82 | 1.49 | 49.74% | -72.84% | -77.98% | -75.90% | 9.48% | 76.83% | -6.12% | 0.48 |
| S0e. XLK Sharpe-Mom Top-1 [Hard] | 1. Standalone Control | **36.65%** | 0.91 | 1.65 | 42.49% | -44.38% | -54.58% | -56.49% | 22.18% | 57.88% | 33.99% | 1.00 |
| S1a. SPY Raw 12-1 Mom Top-1 [Hard] | 1A. SPY Raw Mom | **37.64%** | 0.85 | 1.47 | 50.70% | -70.67% | -74.11% | -73.41% | 12.36% | 78.82% | -4.43% | 0.92 |
| S1b. SPY Raw 12-1 Mom Top-2 [Hard] | 1A. SPY Raw Mom | **23.59%** | 0.74 | 1.25 | 34.95% | -42.67% | -51.80% | -52.37% | 5.03% | 52.46% | 14.70% | 0.88 |
| S1c. SPY Raw 12-1 Mom Top-3 [Hard] | 1A. SPY Raw Mom | **23.83%** | 0.77 | 1.32 | 32.65% | -30.47% | -39.76% | -41.49% | 15.00% | 36.23% | 12.63% | 0.83 |
| S1d. SPY Raw 12-1 Mom Rank #2 Alone | 1A. SPY Raw Mom | **1.53%** | 0.20 | 0.32 | 38.99% | -76.48% | -79.21% | -79.23% | -9.83% | 18.31% | 26.56% | 1.48 |
| S1e. SPY Raw 12-1 Mom Rank #3 Alone | 1A. SPY Raw Mom | **15.94%** | 0.51 | 0.95 | 44.56% | -74.20% | -76.52% | -78.15% | 29.80% | 0.22% | 5.53% | 1.63 |
| S1f. SPY Raw 12-1 Mom (Buy Top-1, Hold<=Top-2) [G1 Buffer] | 1A. SPY Raw Mom | **45.10%** | 0.96 | 1.67 | 51.01% | -64.16% | -70.19% | -68.42% | 16.62% | 92.36% | 45.56% | 0.68 |
| S1g. SPY Raw 12-1 Mom (Buy Top-1, Hold<=Top-3) [G1 Buffer] | 1A. SPY Raw Mom | **43.21%** | 1.00 | 1.81 | 44.64% | -44.69% | -57.55% | -51.50% | 29.51% | 63.05% | 45.56% | 0.54 |
| S1h. SPY Raw 12-1 Mom (Buy Top-2, Hold<=Top-5) [G1 Buffer] | 1A. SPY Raw Mom | **26.78%** | 0.78 | 1.30 | 37.03% | -37.97% | -44.50% | -45.55% | 19.34% | 37.08% | 32.74% | 0.54 |
| S2a. SPY Sharpe-Mom Top-1 [Hard] | 1B. SPY Sharpe-Mom | **22.67%** | 0.66 | 1.11 | 42.78% | -66.18% | -75.51% | -74.60% | 15.27% | 32.93% | 36.86% | 1.20 |
| S2b. SPY Sharpe-Mom Top-2 [Hard] | 1B. SPY Sharpe-Mom | **16.50%** | 0.58 | 1.01 | 33.30% | -61.01% | -65.79% | -65.71% | 5.69% | 32.10% | 33.85% | 1.04 |
| S2c. SPY Sharpe-Mom Top-3 [Hard] | 1B. SPY Sharpe-Mom | **17.43%** | 0.64 | 1.10 | 29.50% | -37.61% | -45.38% | -44.47% | 4.20% | 37.01% | 25.61% | 1.03 |
| S2d. SPY Sharpe-Mom Rank #2 Alone | 1B. SPY Sharpe-Mom | **3.40%** | 0.24 | 0.43 | 39.99% | -82.57% | -83.88% | -84.47% | -9.47% | 22.76% | 26.31% | 1.64 |
| S2e. SPY Sharpe-Mom Rank #3 Alone | 1B. SPY Sharpe-Mom | **13.06%** | 0.47 | 0.81 | 36.34% | -67.76% | -71.85% | -71.05% | -3.28% | 38.28% | 6.44% | 1.81 |
| S2f. SPY Sharpe-Mom (Buy Top-1, Hold<=Top-2) [G1 Buffer] | 1B. SPY Sharpe-Mom | **14.36%** | 0.50 | 0.80 | 40.40% | -74.35% | -81.05% | -81.09% | 7.18% | 24.35% | 56.32% | 0.86 |
| S2g. SPY Sharpe-Mom (Buy Top-1, Hold<=Top-3) [G1 Buffer] | 1B. SPY Sharpe-Mom | **18.02%** | 0.57 | 1.00 | 40.36% | -61.57% | -71.66% | -73.35% | 13.68% | 23.86% | 28.49% | 0.75 |
| S2h. SPY Sharpe-Mom (Buy Top-2, Hold<=Top-5) [G1 Buffer] | 1B. SPY Sharpe-Mom | **17.59%** | 0.64 | 1.09 | 30.61% | -46.26% | -53.69% | -52.51% | 12.86% | 23.99% | 16.55% | 0.71 |
| S3a. SPY Best-Sector (EW Mom) -> Top-1 Stock [SPEC, Hard] | 1C. SPY Sector/Veto | **29.44%** | 0.78 | 1.37 | 42.03% | -50.92% | -54.58% | -56.49% | 16.77% | 47.84% | 54.18% | 1.23 |
| S3b. SPY Best-Sector -> Top-1 Stock (Hold<=Top-2) | 1C. SPY Sector/Veto | **25.63%** | 0.70 | 1.17 | 44.20% | -61.62% | -66.71% | -66.31% | 13.18% | 43.73% | 45.56% | 1.09 |
| S3c. SPY Best-Sector (EW Sharpe) -> Top-1 Sharpe Stock | 1C. SPY Sector/Veto | **3.00%** | 0.22 | 0.33 | 33.96% | -63.89% | -68.84% | -69.67% | -1.48% | 9.10% | 4.50% | 1.40 |
| S3d. SPY Top-2 Sectors -> Top-1 Stock Each | 1C. SPY Sector/Veto | **22.12%** | 0.74 | 1.36 | 31.98% | -40.82% | -50.34% | -47.93% | 9.90% | 39.93% | 15.67% | 1.13 |
| S3e. SPY Ex-IT (10 Non-Tech Sectors) Raw Mom Top-1 | 1C. SPY Sector/Veto | **-0.95%** | 0.15 | 0.25 | 41.92% | -87.81% | -89.57% | -90.17% | -2.94% | 1.68% | -4.43% | 0.92 |
| S3f. SPY Ex-IT (10 Non-Tech Sectors) Sharpe-Mom Top-1 | 1C. SPY Sector/Veto | **3.36%** | 0.24 | 0.36 | 37.66% | -78.91% | -84.98% | -84.86% | -0.98% | 9.24% | 46.06% | 1.21 |
| S3g. SPY Raw Mom Top-1 + A5 Anti-Jump Veto (5d<35%) | 1C. SPY Sector/Veto | **7.05%** | 0.33 | 0.59 | 41.12% | -64.71% | -68.36% | -66.47% | -9.80% | 33.53% | -4.59% | 1.29 |
| S3h. SPY Sharpe-Mom Top-1 + A5 Anti-Jump Veto (5d<35%) | 1C. SPY Sector/Veto | **4.73%** | 0.26 | 0.42 | 35.45% | -64.42% | -66.30% | -66.54% | -7.15% | 22.34% | -0.00% | 1.18 |
| S3i. SPY Raw Mom Top-5 -> FIP Smooth Top-1 | 1C. SPY Sector/Veto | **0.85%** | 0.19 | 0.34 | 41.76% | -85.19% | -85.63% | -87.29% | -0.78% | 3.01% | -7.30% | 1.21 |
| S3j. SPY Sharpe-Mom Top-5 -> FIP Smooth Top-1 | 1C. SPY Sector/Veto | **6.05%** | 0.29 | 0.52 | 32.23% | -58.69% | -60.07% | -59.89% | 1.16% | 12.70% | -1.54% | 1.22 |

---

## 4. Full Portfolio Matrix: `QQQ + XLK` vs `QQQ + SPY` vs `QQQ + XLK + SPY` (`Core3` & `G1`)

| Portfolio Variant | Family | CAGR (`09–26`) | Sharpe | Sortino | Monthly MaxDD | Calmar (M) | Daily MaxDD (`5651ec2`) | Daily MaxDD (`O2C`) | `2009–2018` CAGR | `2019–2026` CAGR | `2022` Return | Avg TO | Overlap % | NW $t$ vs `Core3` | NW $t$ vs `G1` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 00a. Core3 Control: 50% QQQ Sharpe Top-2 [Hard] + 50% XLK Raw Top-1 [Hard] | 0. QQQ+XLK Control | **43.75%** | 1.08 | 2.21 | -36.65% | 1.19 | -46.96% | -49.68% | 24.79% | 72.53% | 9.14% | 0.86 | 35.7% | +0.00 | -1.00 |
| 00b. G1 Control: 50% QQQ (Buy 2, Hold<=5) + 50% XLK Raw Top-1 [Hard] | 0. QQQ+XLK Control | **48.02%** | 1.19 | 2.59 | -27.70% | 1.73 | -41.96% | -43.63% | 30.99% | 73.30% | 4.72% | 0.69 | 30.0% | +1.00 | +0.00 |
| 00c. G1 (QQQ Hold<=3) + XLK Hard Top-1 | 0. QQQ+XLK Control | **44.84%** | 1.10 | 2.20 | -36.60% | 1.23 | -48.35% | -50.29% | 27.17% | 71.31% | 10.26% | 0.77 | 31.9% | +0.72 | -0.74 |
| 00d. G1 (QQQ Hold<=4) + XLK Hard Top-1 | 0. QQQ+XLK Control | **45.64%** | 1.12 | 2.19 | -36.65% | 1.25 | -49.43% | -51.60% | 30.28% | 68.16% | 10.14% | 0.73 | 31.9% | +0.74 | -0.74 |
| 00e. G1 (QQQ Hold<=6) + XLK Hard Top-1 | 0. QQQ+XLK Control | **48.65%** | 1.20 | 2.55 | -31.69% | 1.53 | -41.96% | -43.63% | 32.75% | 72.01% | 5.74% | 0.65 | 31.0% | +1.04 | +0.43 |
| 00f. G1-Both: 50% QQQ (Buy 2, Hold<=5) + 50% XLK (Buy 1, Hold<=2) | 0. QQQ+XLK Control | **45.82%** | 1.12 | 2.43 | -33.54% | 1.37 | -41.96% | -43.63% | 27.88% | 72.74% | -14.02% | 0.53 | 34.3% | +0.33 | -0.30 |
| C3_SPY_1a. Core3 + SPY Raw Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Raw Top-1) | 2A. Core3 QQQ+SPY | **43.78%** | 1.06 | 2.06 | -42.37% | 1.03 | -48.91% | -49.68% | 23.96% | 74.11% | -8.84% | 0.92 | 31.5% | +0.09 | -0.36 |
| C3_SPY_1b. Core3 + SPY Raw Mom Top-2 (50% QQQ Hard Top-2 + 50% SPY Raw Top-2) | 2A. Core3 QQQ+SPY | **35.08%** | 1.02 | 1.95 | -30.31% | 1.16 | -44.35% | -45.35% | 18.86% | 59.33% | -0.77% | 0.90 | 51.2% | -1.77 | -2.32 |
| C3_SPY_1c. Core3 + SPY Sharpe-Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Sharpe Top-1) | 2A. Core3 QQQ+SPY | **35.64%** | 0.99 | 1.76 | -39.38% | 0.91 | -47.25% | -49.68% | 25.52% | 49.91% | 7.76% | 1.06 | 31.0% | -1.38 | -1.86 |
| C3_SPY_1d. Core3 + SPY Sharpe-Mom Top-2 (50% QQQ Hard Top-2 + 50% SPY Sharpe Top-2) | 2A. Core3 QQQ+SPY | **31.22%** | 0.95 | 1.87 | -32.49% | 0.96 | -43.48% | -42.71% | 19.25% | 48.45% | 5.64% | 0.98 | 46.5% | -2.19 | -2.76 |
| C3_SPY_1e. Core3 + SPY Best-Sector->Top-1 Stock [SPEC] (50/50) | 2A. Core3 QQQ+SPY | **38.93%** | 1.05 | 2.02 | -36.65% | 1.06 | -46.96% | -49.68% | 25.62% | 58.19% | 16.86% | 1.07 | 14.1% | -0.79 | -1.16 |
| C3_SPY_1f. Core3 + SPY Best-Sector(Sharpe)->Top-1 Sharpe Stock (50/50) | 2A. Core3 QQQ+SPY | **24.49%** | 0.84 | 1.29 | -38.01% | 0.64 | -47.07% | -49.60% | 15.60% | 36.97% | -4.90% | 1.16 | 8.5% | -2.47 | -2.98 |
| C3_SPY_1g. Core3 + SPY Top-2 Sectors->Top-1 Stock Each (50/50) | 2A. Core3 QQQ+SPY | **34.15%** | 1.02 | 2.13 | -28.29% | 1.21 | -42.42% | -43.33% | 21.28% | 52.78% | -1.34% | 1.02 | 25.8% | -1.87 | -2.33 |
| C3_SPY_1h. Core3 + SPY Raw Mom Top-1 + A5 Jump Veto (50/50) | 2A. Core3 QQQ+SPY | **26.41%** | 0.79 | 1.51 | -37.53% | 0.70 | -46.96% | -49.68% | 10.65% | 50.11% | -10.43% | 1.10 | 16.4% | -2.67 | -3.08 |
| C3_SPY_1i. Core3 + SPY Sharpe-Mom Top-1 + A5 Jump Veto (50/50) | 2A. Core3 QQQ+SPY | **24.99%** | 0.80 | 1.35 | -36.65% | 0.68 | -46.96% | -49.68% | 12.19% | 43.68% | -8.98% | 1.05 | 17.8% | -3.03 | -3.53 |
| C3_SPY_1j. Core3 + SPY Raw Top-5->FIP Smooth Top-1 (50/50) | 2A. Core3 QQQ+SPY | **23.26%** | 0.73 | 1.43 | -48.80% | 0.48 | -54.57% | -56.37% | 16.52% | 32.53% | -11.66% | 1.06 | 18.3% | -2.96 | -3.55 |
| C3_SPY_1k. Core3 + SPY Sharpe Top-5->FIP Smooth Top-1 (50/50) | 2A. Core3 QQQ+SPY | **25.76%** | 0.85 | 1.57 | -36.42% | 0.71 | -41.49% | -42.17% | 16.89% | 38.21% | -9.63% | 1.07 | 14.6% | -2.86 | -3.55 |
| C3_SPY_1l. Core3 + SPY Ex-IT (Non-Tech) Raw Mom Top-1 (50/50) | 2A. Core3 QQQ+SPY | **22.81%** | 0.75 | 1.31 | -43.58% | 0.52 | -54.13% | -52.10% | 15.47% | 32.99% | -8.84% | 0.92 | 16.4% | -2.21 | -2.54 |
| C3_SPY_1m. Core3 + SPY Ex-IT (Non-Tech) Sharpe-Mom Top-1 (50/50) | 2A. Core3 QQQ+SPY | **25.26%** | 0.84 | 1.51 | -35.65% | 0.71 | -47.25% | -48.20% | 16.78% | 37.11% | 11.35% | 1.06 | 18.3% | -2.10 | -2.53 |
| G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Mom Hard Top-1 (50/50) | 2B. G1 QQQ+SPY | **47.95%** | 1.17 | 2.35 | -38.43% | 1.25 | -45.87% | -45.68% | 30.28% | 74.33% | -12.35% | 0.75 | 28.6% | +0.50 | +0.09 |
| G1_SPY_1b. G1 QQQ(Hold<=5) + SPY Raw Mom Hard Top-2 (50/50) | 2B. G1 QQQ+SPY | **38.74%** | 1.14 | 2.29 | -25.36% | 1.53 | -41.54% | -42.25% | 24.71% | 59.20% | -4.97% | 0.73 | 45.5% | -1.04 | -1.77 |
| G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe-Mom Hard Top-1 (50/50) | 2B. G1 QQQ+SPY | **39.62%** | 1.12 | 1.99 | -32.31% | 1.23 | -43.16% | -43.63% | 31.82% | 50.37% | 3.43% | 0.89 | 24.9% | -0.79 | -1.38 |
| G1_SPY_1d. G1 QQQ(Hold<=5) + SPY Sharpe-Mom Hard Top-2 (50/50) | 2B. G1 QQQ+SPY | **34.76%** | 1.07 | 2.16 | -28.00% | 1.24 | -40.07% | -37.81% | 25.14% | 48.28% | 1.32% | 0.81 | 41.8% | -1.45 | -2.19 |
| G1_SPY_1e. G1 QQQ(Hold<=5) + SPY Best-Sector->Top-1 Stock [SPEC] (50/50) | 2B. G1 QQQ+SPY | **42.84%** | 1.17 | 2.27 | -27.70% | 1.55 | -41.96% | -43.63% | 31.79% | 58.49% | 11.48% | 0.90 | 8.9% | -0.36 | -0.79 |
| G1_SPY_1f. G1 QQQ(Hold<=5) + SPY Best-Sector(Sharpe)->Top-1 Sharpe Stock (50/50) | 2B. G1 QQQ+SPY | **27.87%** | 0.96 | 1.57 | -30.20% | 0.92 | -41.74% | -43.06% | 21.16% | 37.07% | -8.84% | 0.99 | 7.0% | -1.86 | -2.47 |
| G1_SPY_1g. G1 QQQ(Hold<=5) + SPY Raw Top-1 + A5 Jump Veto (50/50) | 2B. G1 QQQ+SPY | **30.11%** | 0.90 | 1.84 | -28.14% | 1.07 | -41.96% | -43.63% | 16.17% | 50.61% | -14.07% | 0.93 | 13.6% | -1.94 | -2.67 |
| G1_SPY_1h. G1 QQQ(Hold<=5) + SPY Sharpe Top-1 + A5 Jump Veto (50/50) | 2B. G1 QQQ+SPY | **28.70%** | 0.94 | 1.61 | -32.31% | 0.89 | -43.16% | -43.63% | 17.71% | 44.42% | -12.66% | 0.88 | 13.6% | -2.21 | -3.03 |
| G1_SPY_1i. G1 QQQ(Hold<=5) + SPY Raw Top-5->FIP Smooth Top-1 (50/50) | 2B. G1 QQQ+SPY | **26.48%** | 0.82 | 1.63 | -46.15% | 0.57 | -52.22% | -54.09% | 22.27% | 32.13% | -15.20% | 0.89 | 17.4% | -2.16 | -2.96 |
| G1_SPY_1j. G1 QQQ(Hold<=5) + SPY Sharpe Top-5->FIP Smooth Top-1 (50/50) | 2B. G1 QQQ+SPY | **28.83%** | 0.95 | 1.81 | -27.70% | 1.04 | -43.27% | -43.79% | 22.50% | 37.47% | -13.28% | 0.90 | 14.6% | -2.03 | -2.86 |
| G1_SPY_2a. G1 Grid: QQQ(Hold<=3) + SPY Raw Hard Top-1 | 2C. G1 QQQ+SPY Grid | **44.82%** | 1.08 | 2.07 | -41.03% | 1.09 | -48.35% | -50.29% | 26.28% | 72.80% | -7.89% | 0.83 | 33.8% | +0.24 | -0.23 |
| G1_SPY_2b. G1 Grid: QQQ(Hold<=4) + SPY Raw Hard Top-1 | 2C. G1 QQQ+SPY Grid | **45.55%** | 1.11 | 2.06 | -40.04% | 1.14 | -49.43% | -51.60% | 29.33% | 69.53% | -8.03% | 0.80 | 31.9% | +0.33 | -0.14 |
| G1_SPY_2c. G1 Grid: QQQ(Hold<=6) + SPY Raw Hard Top-1 | 2C. G1 QQQ+SPY Grid | **48.42%** | 1.18 | 2.25 | -43.13% | 1.12 | -50.00% | -49.49% | 31.76% | 73.06% | -11.42% | 0.71 | 28.2% | +0.57 | +0.18 |
| G1_SPY_2d. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=2) | 2C. G1 QQQ+SPY Grid | **51.60%** | 1.22 | 2.49 | -34.96% | 1.48 | -41.96% | -43.63% | 32.23% | 80.84% | 9.09% | 0.63 | 31.9% | +0.87 | +0.60 |
| G1_SPY_2e. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=3) | 2C. G1 QQQ+SPY Grid | **50.23%** | 1.28 | 2.88 | -27.12% | 1.85 | -40.30% | -40.85% | 39.31% | 65.59% | 9.09% | 0.56 | 34.7% | +0.52 | +0.21 |
| G1_SPY_2f. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 2, Hold<=5) | 2C. G1 QQQ+SPY Grid | **40.65%** | 1.16 | 2.29 | -26.44% | 1.54 | -41.57% | -42.25% | 32.83% | 51.41% | 4.00% | 0.56 | 48.4% | -0.71 | -1.31 |
| G1_SPY_2g. G1-Both: QQQ(Hold<=5) + SPY Sharpe (Buy 1, Hold<=2) | 2C. G1 QQQ+SPY Grid | **34.71%** | 1.04 | 1.82 | -35.83% | 0.97 | -44.00% | -45.92% | 26.95% | 45.43% | 10.27% | 0.72 | 26.3% | -1.20 | -1.75 |
| G1_SPY_2h. G1-Both: QQQ(Hold<=5) + SPY Sharpe (Buy 1, Hold<=3) | 2C. G1 QQQ+SPY Grid | **36.44%** | 1.06 | 2.05 | -32.31% | 1.13 | -43.16% | -40.85% | 30.64% | 44.31% | 1.05% | 0.66 | 28.2% | -1.11 | -1.75 |
| G1_SPY_2i. G1-Both: QQQ(Hold<=5) + SPY Sharpe (Buy 2, Hold<=5) | 2C. G1 QQQ+SPY Grid | **35.40%** | 1.13 | 2.24 | -28.00% | 1.26 | -40.07% | -37.33% | 29.25% | 43.76% | -4.51% | 0.64 | 43.2% | -1.34 | -2.01 |
| G1_SPY_2j. G1-Both: QQQ(Hold<=5) + SPY Best-Sector->Stock (Hold<=2) | 2C. G1 QQQ+SPY Grid | **40.89%** | 1.10 | 2.15 | -32.74% | 1.25 | -47.43% | -46.04% | 29.65% | 56.85% | 9.09% | 0.84 | 10.3% | -0.50 | -0.94 |
| G1_SPY_3a. Weight 75/25: 75% QQQ(Hold<=5) + 25% SPY Raw Top-1 | 2D. QQQ+SPY Weights | **50.48%** | 1.26 | 2.78 | -34.43% | 1.47 | -43.32% | -42.95% | 37.75% | 68.67% | -18.23% | 0.66 | 28.6% | +0.65 | +0.31 |
| G1_SPY_3b. Weight 25/75: 25% QQQ(Hold<=5) + 75% SPY Raw Top-1 | 2D. QQQ+SPY Weights | **43.65%** | 1.01 | 1.86 | -56.47% | 0.77 | -61.83% | -61.26% | 21.77% | 77.80% | -7.67% | 0.84 | 28.6% | +0.27 | -0.09 |
| G1_SPY_3c. Weight 75/25: 75% QQQ(Hold<=5) + 25% SPY Sharpe Top-1 | 2D. QQQ+SPY Weights | **46.16%** | 1.24 | 2.52 | -30.17% | 1.53 | -41.63% | -41.88% | 38.53% | 56.63% | -11.44% | 0.73 | 24.9% | -0.02 | -0.51 |
| 3S_C3_1a. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Raw Top-1) | 3A. 3-Sleeve Core3 | **44.43%** | 1.10 | 2.23 | -36.65% | 1.21 | -46.96% | -49.68% | 25.02% | 73.99% | 0.54% | 0.89 | 65.7% | +0.09 | -0.65 |
| 3S_C3_1b. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Sharpe Top-1) | 3A. 3-Sleeve Core3 | **40.39%** | 1.08 | 2.06 | -36.65% | 1.10 | -46.96% | -49.68% | 25.83% | 61.69% | 9.22% | 0.96 | 55.4% | -1.38 | -1.98 |
| 3S_C3_1c. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Best-Sector->Stock) | 3A. 3-Sleeve Core3 | **42.01%** | 1.10 | 2.17 | -36.65% | 1.15 | -46.96% | -49.68% | 25.83% | 66.00% | 14.12% | 0.96 | 53.5% | -0.79 | -1.35 |
| 3S_C3_1d. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Ex-IT Raw Top-1) | 3A. 3-Sleeve Core3 | **34.00%** | 1.00 | 1.87 | -32.48% | 1.05 | -44.35% | -45.34% | 20.90% | 53.04% | 0.54% | 0.89 | 47.4% | -2.21 | -2.67 |
| 3S_C3_1e. Core3 3-Sleeve Equal (33.3% QQQ + 33.3% XLK + 33.3% SPY Raw Top-1) | 3A. 3-Sleeve Core3 | **43.71%** | 1.07 | 2.03 | -40.63% | 1.08 | -49.56% | -51.98% | 22.32% | 76.92% | 6.98% | 0.88 | 65.7% | +0.09 | -0.58 |
| 3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw Top-1) | 3B. 3-Sleeve G1 | **48.67%** | 1.22 | 2.61 | -30.37% | 1.60 | -41.96% | -43.63% | 31.32% | 74.47% | -3.44% | 0.72 | 62.0% | +0.73 | +0.09 |
| 3S_G1_1b. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Sharpe Top-1) | 3B. 3-Sleeve G1 | **44.53%** | 1.22 | 2.38 | -27.70% | 1.61 | -41.96% | -43.63% | 32.11% | 62.30% | 4.82% | 0.79 | 53.1% | -0.34 | -1.38 |
| 3S_G1_1c. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Best-Sector->Stock) | 3B. 3-Sleeve G1 | **46.12%** | 1.23 | 2.57 | -27.70% | 1.66 | -41.96% | -43.63% | 32.04% | 66.52% | 9.16% | 0.80 | 47.4% | -0.03 | -0.79 |
| 3S_G1_1d. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Ex-IT Raw Top-1) | 3B. 3-Sleeve G1 | **37.74%** | 1.12 | 2.18 | -30.37% | 1.24 | -41.54% | -42.24% | 26.98% | 53.00% | -3.44% | 0.72 | 41.8% | -1.32 | -2.21 |
| 3S_G1_1e. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw+A5 Veto) | 3B. 3-Sleeve G1 | **39.58%** | 1.11 | 2.26 | -27.70% | 1.43 | -41.96% | -43.63% | 24.10% | 62.46% | -4.60% | 0.81 | 50.2% | -1.28 | -2.67 |
| 3S_G1_1f. G1 3-Sleeve Equal (33.3% QQQ[Hold<=5] + 33.3% XLK + 33.3% SPY Raw Top-1) | 3B. 3-Sleeve G1 | **46.63%** | 1.15 | 2.26 | -37.93% | 1.23 | -45.69% | -47.36% | 26.45% | 77.50% | 4.21% | 0.77 | 62.0% | +0.56 | -0.19 |
| 3S_G1_1g. G1 3-Sleeve Equal (33.3% QQQ[Hold<=5] + 33.3% XLK + 33.3% SPY Sharpe Top-1) | 3B. 3-Sleeve G1 | **41.29%** | 1.13 | 2.10 | -33.26% | 1.24 | -45.61% | -47.36% | 27.50% | 61.30% | 16.55% | 0.86 | 53.1% | -0.86 | -1.86 |
| 3S_G1_1h. G1 3-Sleeve (40% QQQ[Hold<=5] + 40% XLK + 20% SPY Raw Top-1) | 3B. 3-Sleeve G1 | **47.44%** | 1.18 | 2.45 | -32.64% | 1.45 | -44.13% | -45.85% | 28.48% | 76.09% | 4.74% | 0.74 | 62.0% | +0.79 | -0.19 |
| 3S_G1_1i. G1 3-Sleeve (40% QQQ[Hold<=5] + 40% XLK + 20% SPY Best-Sector->Stock) | 3B. 3-Sleeve G1 | **45.48%** | 1.19 | 2.42 | -31.04% | 1.47 | -44.13% | -45.85% | 29.10% | 69.72% | 15.65% | 0.80 | 47.4% | -0.04 | -1.17 |
| 3S_G1_1j. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=2]) | 3B. 3-Sleeve G1 | **50.60%** | 1.26 | 2.75 | -30.37% | 1.67 | -41.96% | -43.63% | 32.37% | 77.89% | 8.13% | 0.66 | 61.5% | +0.99 | +0.60 |
| 3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3]) | 3B. 3-Sleeve G1 | **49.96%** | 1.29 | 3.04 | -22.61% | 2.21 | -40.19% | -41.21% | 35.82% | 70.40% | 8.13% | 0.62 | 58.7% | +0.69 | +0.21 |

---

## 5. Forensic Sector & Overlap Attribution: When Does `SPY` Differ from `XLK`?

### 5.1 GICS Sector Breakdown of `SPY` Picks (`213` Months)

| SPY Sleeve Variant | GICS Sector Picked | Months Picked | Share of 213 Months | Mean Monthly Net Ret | Median Monthly Net Ret | Win Rate | XLK Mean Ret (Same Months) | Active Diff vs XLK (`/mo`) | Top Example Tickers Picked |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| SPY Best-Sector -> Top-1 Stock | Information Technology | `50` | 23.5% | 5.98% | 4.42% | 58.0% | 6.04% | -0.06% | `NVDA, SNDK, AMD, MU` |
| SPY Best-Sector -> Top-1 Stock | Utilities | `37` | 17.4% | -1.13% | -0.16% | 48.6% | 5.26% | -6.39% | `AWK, VST, SO, NI` |
| SPY Best-Sector -> Top-1 Stock | Energy | `35` | 16.4% | 3.10% | 1.42% | 57.1% | 0.88% | 2.22% | `DVN, OXY, COG, ANDV` |
| SPY Best-Sector -> Top-1 Stock | Consumer Discretionary | `25` | 11.7% | 3.21% | 6.01% | 68.0% | 2.24% | 0.97% | `NFLX, TGNA, F, PENN` |
| SPY Best-Sector -> Top-1 Stock | Telecommunication Services | `20` | 9.4% | 4.76% | 3.56% | 75.0% | 2.64% | 2.12% | `S, TMUS, FTR, DTV` |
| SPY Best-Sector -> Top-1 Stock | Health Care | `15` | 7.0% | 2.29% | 0.25% | 53.3% | 5.64% | -3.35% | `HSP, DXCM, CI, AGN` |
| SPY Best-Sector -> Top-1 Stock | Consumer Staples | `12` | 5.6% | 1.42% | 1.56% | 58.3% | -2.38% | 3.80% | `RAI, PBG, HRL, GIS` |
| SPY Best-Sector -> Top-1 Stock | Financials | `10` | 4.7% | 1.88% | 1.91% | 50.0% | 2.13% | -0.25% | `GNW, KKR, DFS, RF` |
| SPY Best-Sector -> Top-1 Stock | Communication Services | `6` | 2.8% | 1.51% | 5.22% | 66.7% | 8.11% | -6.60% | `FOX, NFLX, DISCA, META` |
| SPY Best-Sector -> Top-1 Stock | Industrials | `2` | 0.9% | -3.59% | -3.59% | 0.0% | 6.77% | -10.36% | `DAL` |
| SPY Best-Sector -> Top-1 Stock | Materials | `1` | 0.5% | -3.63% | -3.63% | 0.0% | 4.23% | -7.86% | `NEM` |
| SPY Raw 12-1 Mom Top-1 | Information Technology | `89` | 41.8% | 6.59% | 5.61% | 67.4% | 6.74% | -0.15% | `NVDA, AMD, FSLR, PLTR` |
| SPY Raw 12-1 Mom Top-1 | Consumer Discretionary | `50` | 23.5% | 3.25% | 2.97% | 58.0% | 0.26% | 2.98% | `NFLX, PHM, FDO, TSLA` |
| SPY Raw 12-1 Mom Top-1 | Health Care | `23` | 10.8% | -4.28% | -1.57% | 39.1% | 0.29% | -4.57% | `NKTR, ALGN, MRNA, DXCM` |
| SPY Raw 12-1 Mom Top-1 | Energy | `20` | 9.4% | 3.69% | 2.66% | 65.0% | 3.66% | 0.03% | `DVN, COG, OXY, ANDV` |
| SPY Raw 12-1 Mom Top-1 | Financials | `12` | 5.6% | -0.37% | -0.67% | 50.0% | 1.38% | -1.75% | `GNW, HOOD, XL, FHN` |
| SPY Raw 12-1 Mom Top-1 | Utilities | `6` | 2.8% | 10.71% | 9.87% | 66.7% | -2.31% | 13.03% | `VST` |
| SPY Raw 12-1 Mom Top-1 | Industrials | `4` | 1.9% | 1.98% | 3.32% | 75.0% | 10.31% | -8.33% | `LUV` |
| SPY Raw 12-1 Mom Top-1 | Materials | `4` | 1.9% | 3.49% | 4.65% | 75.0% | 3.10% | 0.39% | `TIE, NEM, BLL` |
| SPY Raw 12-1 Mom Top-1 | Consumer Staples | `3` | 1.4% | -7.31% | -6.26% | 0.0% | 9.28% | -16.59% | `GMCR, MNST, TSN` |
| SPY Raw 12-1 Mom Top-1 | Communication Services | `1` | 0.5% | 7.72% | 7.72% | 100.0% | 5.85% | 1.87% | `META` |
| SPY Raw 12-1 Mom Top-1 | Telecommunication Services | `1` | 0.5% | 2.63% | 2.63% | 100.0% | -3.23% | 5.86% | `S` |
| SPY Sharpe-Mom Top-1 | Information Technology | `54` | 25.4% | 5.34% | 5.57% | 64.8% | 7.25% | -1.92% | `NVDA, SNDK, PLTR, FTNT` |
| SPY Sharpe-Mom Top-1 | Consumer Discretionary | `42` | 19.7% | 1.05% | 1.39% | 54.8% | -0.36% | 1.41% | `NFLX, DLTR, FDO, ORLY` |
| SPY Sharpe-Mom Top-1 | Health Care | `32` | 15.0% | -0.99% | -1.41% | 40.6% | 4.09% | -5.08% | `MCK, LLY, ABC, DXCM` |
| SPY Sharpe-Mom Top-1 | Industrials | `19` | 8.9% | 2.98% | 3.47% | 84.2% | 4.94% | -1.96% | `LUV, BA, CPRT, NOC` |
| SPY Sharpe-Mom Top-1 | Energy | `16` | 7.5% | 4.19% | 6.96% | 56.2% | -1.45% | 5.64% | `COG, MPC, DVN, OKE` |
| SPY Sharpe-Mom Top-1 | Financials | `12` | 5.6% | -0.44% | -1.82% | 50.0% | 1.60% | -2.04% | `GNW, HOOD, CBOE, ETFC` |
| SPY Sharpe-Mom Top-1 | Materials | `10` | 4.7% | 3.93% | 5.39% | 80.0% | 2.41% | 1.52% | `SHW, BLL, TIE, FCX` |
| SPY Sharpe-Mom Top-1 | Utilities | `10` | 4.7% | 2.53% | 0.31% | 50.0% | 0.05% | 2.49% | `VST, ETR, TEG, AWK` |
| SPY Sharpe-Mom Top-1 | Consumer Staples | `8` | 3.8% | 0.71% | 3.31% | 62.5% | 4.92% | -4.21% | `KR, CCE, TSN, HRL` |
| SPY Sharpe-Mom Top-1 | Communication Services | `7` | 3.3% | 4.69% | 7.61% | 57.1% | 15.53% | -10.84% | `META, FOX` |
| SPY Sharpe-Mom Top-1 | Telecommunication Services | `2` | 0.9% | 3.66% | 3.66% | 100.0% | -2.87% | 6.53% | `TMUS, S` |
| SPY Sharpe-Mom Top-1 | Real Estate | `1` | 0.5% | -4.33% | -4.33% | 0.0% | 15.95% | -20.28% | `EXR` |

### 5.2 Cross-Sleeve Monthly Return Correlation Matrix (`2009-01` – `2026-09`)

| Sleeve | `QQQ_Sharpe_Top2_Hard` | `QQQ_Sharpe_G1_Hold5` | `XLK_Raw_Top1` | `SPY_Raw_Top1` | `SPY_Sharpe_Top1` | `SPY_Sector_Top1` | `SPY_ExIT_Raw_Top1` |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`QQQ_Sharpe_Top2_Hard`** | 1.000 | 0.871 | 0.618 | 0.576 | 0.474 | 0.534 | 0.282 |
| **`QQQ_Sharpe_G1_Hold5`** | 0.871 | 1.000 | 0.524 | 0.504 | 0.369 | 0.454 | 0.259 |
| **`XLK_Raw_Top1`** | 0.618 | 0.524 | 1.000 | 0.676 | 0.539 | 0.588 | 0.248 |
| **`SPY_Raw_Top1`** | 0.576 | 0.504 | 0.676 | 1.000 | 0.705 | 0.645 | 0.670 |
| **`SPY_Sharpe_Top1`** | 0.474 | 0.369 | 0.539 | 0.705 | 1.000 | 0.602 | 0.509 |
| **`SPY_Sector_Top1`** | 0.534 | 0.454 | 0.588 | 0.645 | 0.602 | 1.000 | 0.408 |
| **`SPY_ExIT_Raw_Top1`** | 0.282 | 0.259 | 0.248 | 0.670 | 0.509 | 0.408 | 1.000 |

---

## 6. Adversarial Stress Tests: Leave-One-Winner-Out, Vendor Replication & Cumulative DSR

### 6.1 Leave-One-Winner-Out & Remove Top-5 Months Stress Test

| Portfolio Variant | Full CAGR | Ex-Top-5 Months CAGR | Ban `NVDA` | Ban `SNDK` | Ban `PLTR` | Ban `DVN` | Ban `VST` | Ban Top-3 (`NVDA`, `SNDK`, `PLTR`) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 00a. Core3 Control (QQQ Hard + XLK Hard) | **43.75%** | 29.76% | **34.73%** | 42.18% | 37.81% | 43.75% | 43.75% | **27.35%** |
| 00b. G1 Control (QQQ Hold<=5 + XLK Hard) | **48.02%** | 34.19% | **38.30%** | 46.01% | 41.71% | 48.02% | 48.02% | **30.40%** |
| C3_SPY_1a. Core3 + SPY Raw Top-1 | **43.78%** | 30.07% | **34.26%** | 41.84% | 38.35% | 43.79% | 40.95% | **27.45%** |
| C3_SPY_1c. Core3 + SPY Sharpe Top-1 | **35.64%** | 23.90% | **27.84%** | 34.49% | 32.15% | 34.36% | 35.34% | **23.50%** |
| G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Top-1 | **47.95%** | 34.11% | **37.87%** | 45.58% | 42.22% | 47.96% | 45.15% | **30.48%** |
| G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe Top-1 | **39.62%** | 28.05% | **31.29%** | 38.04% | 35.89% | 38.29% | 39.32% | **26.45%** |
| G1_SPY_2d. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=2) | **51.60%** | 37.44% | **33.91%** | 50.05% | 43.74% | 49.21% | 51.53% | **25.78%** |
| G1_SPY_2e. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=3) | **50.23%** | 37.57% | **34.44%** | 51.21% | 40.99% | 47.51% | 50.37% | **28.17%** |
| 3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw) | **48.67%** | 34.88% | **38.86%** | 46.45% | 42.68% | 48.66% | 47.20% | **31.25%** |
| 3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3]) | **49.96%** | 36.69% | **37.17%** | 49.37% | 42.23% | 48.57% | 50.02% | **30.13%** |

### 6.2 Second-Vendor (`Tiingo-First`) End-to-End Replication

| Portfolio Variant | Primary CAGR | Tiingo-First CAGR | Diff (bp) | Primary Sharpe | Tiingo Sharpe | Primary MaxDD (M) | Tiingo MaxDD (M) | Monthly Return Corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 00a. Core3 Control (QQQ Hard + XLK Hard) | **43.75%** | **43.82%** | `+7.2 bp` | 1.08 | 1.08 | -36.65% | -36.65% | `0.99999` |
| 00b. G1 Control (QQQ Hold<=5 + XLK Hard) | **48.02%** | **48.09%** | `+7.0 bp` | 1.19 | 1.19 | -27.70% | -27.70% | `0.99999` |
| C3_SPY_1a. Core3 + SPY Raw Top-1 | **43.78%** | **42.98%** | `-79.4 bp` | 1.06 | 1.05 | -42.37% | -42.37% | `0.99843` |
| C3_SPY_1c. Core3 + SPY Sharpe Top-1 | **35.64%** | **35.63%** | `-0.9 bp` | 0.99 | 0.99 | -39.38% | -39.38% | `1.00000` |
| G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Top-1 | **47.95%** | **47.13%** | `-82.2 bp` | 1.17 | 1.15 | -38.43% | -38.43% | `0.99829` |
| G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe Top-1 | **39.62%** | **39.61%** | `-0.9 bp` | 1.12 | 1.12 | -32.31% | -32.31% | `1.00000` |
| G1_SPY_1e. G1 QQQ(Hold<=5) + SPY Best-Sector->Stock | **42.84%** | **42.84%** | `-0.1 bp` | 1.17 | 1.17 | -27.70% | -27.70% | `1.00000` |
| G1_SPY_2d. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=2) | **51.60%** | **50.76%** | `-84.2 bp` | 1.22 | 1.20 | -34.96% | -34.96% | `0.99834` |
| G1_SPY_2e. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=3) | **50.23%** | **49.39%** | `-83.4 bp` | 1.28 | 1.26 | -27.12% | -27.12% | `0.99801` |
| 3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw) | **48.67%** | **48.30%** | `-37.0 bp` | 1.22 | 1.21 | -30.37% | -30.37% | `0.99952` |
| 3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3]) | **49.96%** | **49.58%** | `-37.3 bp` | 1.29 | 1.28 | -22.61% | -22.60% | `0.99947` |

### 6.3 Cumulative Multiple-Testing Deflated Sharpe Ratio (`DSR`, Bailey & López de Prado 2014)

#### 6.3.1 Master Historical Trial Registry (`08b_master_all_trials_sharpe_registry.csv`)

| Audit Round | Description | Exhaustive Grid Rows | Canonical Cumulative Trials ($N_{\text{cum}}$) | Mean Excess SR (Ann) | Std Excess SR (Ann) | Mean Raw SR (Ann) |
|---:|---|---:|---:|---:|---:|---:|
| `1` | Round 1 (`m_repo_trials.csv` pre-Core3 repo ledgers) | `481` (cum `481`) | **`481`** (cum **`481`**) | `0.572` | `0.266` | `0.627` |
| `2` | Round 2 (`alpha_core_regime_experiment_20261103` A/B/C) | `39` (cum `520`) | **`39`** (cum **`520`**) | `0.951` | `0.085` | `0.984` |
| `3` | Round 3 (`core3_adversarial_audit_20261103` grid/stress) | `147` (cum `667`) | **`59`** (cum **`579`**) | `0.938` | `0.155` | `0.977` |
| `4` | Round 4 (`core3_tech_risk_controls_20261103` technical brakes) | `67` (cum `734`) | **`65`** (cum **`644`**) | `0.945` | `0.145` | `0.983` |
| `5` | Round 5 (`core3_stock_selection_audit_20261103` A/B/C/D + A5 grid) | `101` (cum `835`) | **`70`** (cum **`714`**) | `0.891` | `0.138` | `0.931` |
| `6` | Round 6 (`core3_structural_blindspots_audit_20261103` E/F/G/H/I) | `75` (cum `910`) | **`75`** (cum **`789`**) | `1.044` | `0.065` | `1.084` |
| `7` | Round 7 (`core3_qqq_spy_g1_audit_20261103` QQQ+SPY+XLK) | `89` (cum `999`) | **`89`** (cum **`878`**) | `0.910` | `0.301` | `0.951` |
| **All 1–7** | **Pooled All-History Empirical Distribution** | **`999`** | **`878`** | **`0.741`** | **`0.2981`** | **`0.789`** |

#### 6.3.2 Corrected Cumulative DSR & Paired Significance Table (`08_multiple_testing_dsr.csv`)

| Portfolio Variant | Excess SR | Raw SR | $E[\max SR_0]$ ($N=878$ Ex) | **DSR ($N=878$ Excess)** | **DSR ($N=999$ All-Grid Ex)** | DSR ($N=878$ Raw) | DSR ($N=397$ Post-Core3) | DSR ($N=89$ Round 7) | NW $t$ vs `Core3` | NW $t$ vs `G1` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 00a. Core3 Control: 50% QQQ Sharpe Top-2 [Hard] + 50% XLK Raw Top-1 [Hard] | `1.077` | `1.112` | `0.959` | **`0.7078`** | **`0.6997`** | `0.7489` | `0.9923` | `0.9359` | `+0.00` | **`-1.00`** |
| 00b. G1 Control: 50% QQQ (Buy 2, Hold<=5) + 50% XLK Raw Top-1 [Hard] | `1.194` | `1.230` | `0.959` | **`0.8657`** | **`0.8604`** | `0.8932` | `0.9987` | `0.9821` | `+1.00` | **`+0.00`** |
| C3_SPY_1a. Core3 + SPY Raw Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Raw Top-1) | `1.066` | `1.100` | `0.959` | **`0.6845`** | **`0.6763`** | `0.7251` | `0.9894` | `0.9232` | `+0.09` | **`-0.36`** |
| C3_SPY_1c. Core3 + SPY Sharpe-Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Sharpe Top-1) | `0.996` | `1.035` | `0.959` | **`0.5638`** | **`0.5549`** | `0.6171` | `0.9745` | `0.8621` | `-1.38` | **`-1.86`** |
| G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Mom Hard Top-1 (50/50) | `1.172` | `1.208` | `0.959` | **`0.8332`** | **`0.8273`** | `0.8633` | `0.9975` | `0.9728` | `+0.50` | **`+0.09`** |
| G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe-Mom Hard Top-1 (50/50) | `1.125` | `1.167` | `0.959` | **`0.7680`** | **`0.7611`** | `0.8114` | `0.9942` | `0.9518` | `-0.79` | **`-1.38`** |
| G1_SPY_2d. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=2) | `1.221` | `1.256` | `0.959` | **`0.8847`** | **`0.8801`** | `0.9075` | `0.9989` | `0.9847` | `+0.87` | **`+0.60`** |
| G1_SPY_2e. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=3) | `1.280` | `1.319` | `0.959` | **`0.9284`** | **`0.9251`** | `0.9461` | `0.9995` | `0.9923` | `+0.52` | **`+0.21`** |
| 3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw Top-1) | `1.225` | `1.262` | `0.959` | **`0.8924`** | **`0.8879`** | `0.9161` | `0.9991` | `0.9868` | `+0.73` | **`+0.09`** |
| 3S_G1_1j. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=2]) | `1.257` | `1.295` | `0.959` | **`0.9187`** | **`0.9150`** | `0.9378` | `0.9995` | `0.9914` | `+0.99` | **`+0.60`** |
| 3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3]) | `1.294` | `1.334` | `0.959` | **`0.9434`** | **`0.9406`** | `0.9588` | `0.9998` | `0.9950` | `+0.69` | **`+0.21`** |
| 3S_G1_1d. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Ex-IT Raw Top-1) | `1.122` | `1.166` | `0.959` | **`0.7606`** | **`0.7537`** | `0.8066` | `0.9933` | `0.9478` | `-1.32` | **`-2.21`** |

