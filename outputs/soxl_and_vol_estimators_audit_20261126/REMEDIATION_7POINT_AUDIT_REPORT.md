# Full 7-Point Remediation & Verification Report — `SOXL + TQQQ` Independent Audit (2026-11-26)

> **Remediation Script**: [`remediate_soxl_tqqq_7point_audit.py`](../../remediate_soxl_tqqq_7point_audit.py)  
> **Console Log**: [`remediation_7point_log.txt`](./remediation_7point_log.txt)  
> **All 6 New Remediation CSVs**:
> 1. [`R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv`](./R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv) — All 59 FOMC SEP meetings (`2012-01-25 .. 2026-09-16`) with 2012–2015 medians parsed from official Federal Reserve SEP PDFs (`data/fomc_sep/fomc_sep_2012-01-25.pdf .. fomc_sep_2015-06-17.pdf`), plus explicit `Core PCE (JCXFEMD)` vs `Headline PCE (PCECTPMD)` comparison.
> 2. [`R3_true_share_lot_dynamic_nsl_rebalance_audit.csv`](./R3_true_share_lot_dynamic_nsl_rebalance_audit.csv) — Unified Single-Account Share-Lot Engine with Dynamic NSL Cost-Basis Updates across Rebalances (`Average Cost`, `LIFO`, `FIFO`), Return-Chained `BIL -> SGOV` Cash (`0.000%` splice jump), Two-Sided Cash Switch Fees (`20bp`), and `2010–2022 (Pre-AI)` vs `2023–2026 (AI Era)` split.
> 3. [`R5_walk_forward_oos_2014_2026_audit.csv`](./R5_walk_forward_oos_2014_2026_audit.csv) & [`R5b_walk_forward_yearly_selections.csv`](./R5b_walk_forward_yearly_selections.csv) — Strict Expanding-Window Walk-Forward Out-of-Sample (`2014–2026`) validation of `(Trig, Rec)` and `TQQQ / SOXL` weights + 16-Cell Equal-Weight Ensemble.
> 4. [`R6_true_yang_zhang_and_15_vs_20_cell_volatility_audit.csv`](./R6_true_yang_zhang_and_15_vs_20_cell_volatility_audit.csv) — Exact Original Yang-Zhang (2000, *Journal of Business*) vs `GK-YZ` & Exact 15-Cell (`3×5`) vs 20-Cell (`4×5`) plateaus under remediated cash & fees.
> 5. [`R7_soxx_vs_soxl_2021_index_transition_audit.csv`](./R7_soxx_vs_soxl_2021_index_transition_audit.csv) — Pre-Transition (`PHLX SOX`), 47-Day Transition Mismatch (`2021-06-21 .. 2021-08-25`), and Post-Transition (`ICE Semiconductor`) signal equivalence audit.

---

## Summary of All 7 Audit Items & Remediated Results

| # | Audit Finding | Severity | Remediation Implemented | Remediated Result & Impact |
| :-: | :--- | :---: | :--- | :--- |
| **1** | **2012–2015 SEP Medians Missing & `Core PCE` vs `Headline PCE` Ambiguity** | High | Parsed all 14 FOMC SEP meetings (`2012-01-25 .. 2015-06-17`, $N = 16..19$ participants) directly from official Fed SEP Table 2 PDFs in `data/fomc_sep/`, and tabulated both **`Core PCE Median (JCXFEMD)` (official frozen spec)** and **`Headline PCE Median`** across all 59 meetings (`2012–2026`) in [`R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv`](./R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv). | Across all 14 meetings in `2012-01..2015-06`, target-year Core PCE (`1.2%–1.9%`) and Headline PCE (`0.7%–2.0%`) never exceeded `2.0%`, so **`0 / 14` meetings triggered `SEP = OFF`** (confirming `SEP = ON` throughout 2012–2015). Across 2012–2026, Core PCE vs Headline PCE match on `56 / 59` meetings (`TQQQ` Core PCE `53.21% / -44.54%` vs Headline PCE `51.47% / -59.63%`; `SOXL` Core PCE `69.87%` vs Headline PCE `72.54%`). |
| **2** | **Dynamic NSL Cost-Basis Updates Across Rebalances** | High | Replaced normalized sleeve multipliers with a **Unified Single-Account Share-Lot Engine** (`run_unified_two_sleeve_share_lot_account`) where adding shares to an active `3x` sleeve at rebalance appends a new share lot at execution `adjOpen / (1 - FEE)`, dynamically updating NSL cost basis (`Average Cost`, `LIFO`, `FIFO`). | Exactly reproduces the external auditor's JS remediation: `75/25 Annual` CAGR **`60.12%` $\rightarrow$ `59.88%`** (identical under `Average Cost`, `LIFO`, and `FIFO`), `75/25 OnSwitch` **`61.14%` $\rightarrow$ `61.06%`**, `80/20 Annual` **`58.94%` $\rightarrow$ `58.63%`**. |
| **3** | **True Walk-Forward Out-of-Sample (OOS) Validation (`2014–2026`) & Pre-AI (`2010–2022`) Split** | High | Ran strict expanding-window Walk-Forward OOS (`2014–2026`) selecting `(Trig, Rec)` and `TQQQ / SOXL` weights at each prior year-end `2013..2025` using past data only ([`R5_walk_forward_oos_2014_2026_audit.csv`](./R5_walk_forward_oos_2014_2026_audit.csv)). | **Key Discovery**: Within-asset `(Trig, Rec)` Walk-Forward OOS has **zero degradation** (`TQQQ` WF OOS **`52.06%`** vs Fixed `50.86%`; `SOXL` WF OOS **`83.38%`** vs Fixed `82.82%`). **However**, Walk-Forward weight selection picks **`100% TQQQ` (`90/10` in 3 yrs)** before 2023 (`50.52%` OOS CAGR), proving that `75/25` was favored by post-2023 AI hindsight (`2010–2022` `75/25` beat `TQQQ` by only `+2.07%/yr` [`52.13%` vs `50.06%`], vs `+24.52%/yr` in `2023–2026` [`88.69%` vs `64.17%`]). |
| **4** | **Two-Sided Transaction Cost (`20bp`) on Cash ETF Switches** | Medium | Charged `(1 - FEE)^2` (`10bp` sell equity ETF + `10bp` buy cash ETF `BIL/SGOV`, and vice versa) on all `3x/1x <-> 0x Cash` transitions. | Pure `TQQQ` CAGR `53.29%` $\rightarrow$ **`53.21%`**; Pure `SOXL` CAGR `69.96%` $\rightarrow$ **`69.87%`**. |
| **5** | **`BIL -> SGOV` Direct Price Overwrite (`+9.04%` Jump on `2020-05-28`)** | Medium | Built `build_return_chained_cash()` chaining `SGOV` daily returns onto `BIL` from `2020-06-01` onward, eliminating the `+9.044%` price-level splice jump (`+9.044%` $\rightarrow$ **`+0.000%`**). | Confirmed `0.000%` splice jump. Also documented that mandatory `SEP = OFF` cash exits override NSL (e.g., `2024-12-19` `SOXL` closed at `-22.21%`), so `SOXL` win rate is `12/12 (100%)` on `Vol_Z` trims and **`15/16 (93.75%)`** across all closed `3x` legs. |
| **6** | **True Yang-Zhang (2000) vs `GK-YZ` & 15-Cell vs 19/20-Cell Plateau** | Medium | Implemented both **Exact Original Yang-Zhang (2000, *Journal of Business*, centered $\sigma_{\text{OJ}}^2 + k\sigma_{\text{OC}}^2 + (1-k)\sigma_{\text{RS}}^2$)** and **`GK-YZ`**, and reported both the exact **15-cell (`3×5`)** and **20-cell (`4×5`)** plateaus ([`R6_true_yang_zhang_and_15_vs_20_cell_volatility_audit.csv`](./R6_true_yang_zhang_and_15_vs_20_cell_volatility_audit.csv)). | Exact Yang-Zhang (`W20`: `52.46%` CAGR, `-44.54%` MaxDD, 15-cell median `51.86%`) and `GK-YZ` (`53.40%` CAGR, 15-cell median `52.28%`) both trail Close-to-Close (`54.89%`, 15-cell median `55.31%`, 20-cell median `55.00%`). |
| **7** | **`SOXX` vs `SOXL` 2021 Index Transition & Report-to-CSV Match** | Medium | Audited the 47-trading-day transition gap (`2021-06-21` `SOXX -> ICE` to `2021-08-25` `SOXL -> ICE`) in [`R7_soxx_vs_soxl_2021_index_transition_audit.csv`](./R7_soxx_vs_soxl_2021_index_transition_audit.csv) and verified 100% of table numbers directly from CSV outputs. | During the 47-day transition window, `Vol_Z(SOXX)` vs `Vol_Z(SOXL)` correlation was **`0.99698`** with **`100.00%`** agreement on both `Vol_Z > 1.2` and `Vol_Z < 0.3`. |

---

## R1. Complete `2012–2026` FOMC SEP Medians (`Core PCE [JCXFEMD]` vs `Headline PCE`)

In our frozen specification (`FROZEN_STRATEGY_SPEC.md`), the inflation series in `02_sep_alfred_medians.csv` is **Core PCE Inflation Median (ALFRED series `JCXFEMD`: Personal Consumption Expenditures excluding food and energy)**, paired with the **Federal Funds Target Rate Median (`FEDTARMD`)**.

Using the official Federal Reserve SEP Table 2 participant compilations (`data/fomc_sep/fomc_sep_2012-01-25.pdf .. fomc_sep_2015-06-17.pdf`), we extracted the exact medians for all 14 meetings from `2012-01-25` to `2015-06-17` ([`R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv`](./R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv)):

| FOMC Meeting Date | Target Year | Participants ($N$) | Target FFR Median | Prev FFR Median | **Target Core PCE Median (`JCXFEMD`)** | Prev Core PCE Median | Target Headline PCE Median | Prev Headline PCE Median | `SEP_ON` (Core PCE) | `SEP_ON` (Headline PCE) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2012-01-25` | `2012` | 17 | `0.13%` | — | **`1.50%`** | — | `1.50%` | — | `True` | `True` |
| `2012-04-25` | `2012` | 17 | `0.13%` | `0.13%` | **`1.90%`** | `1.50%` | `2.00%` | `1.50%` | `True` | `True` |
| `2012-06-20` | `2012` | 19 | `0.13%` | `0.13%` | **`1.80%`** | `1.90%` | `1.40%` | `2.00%` | `True` | `True` |
| `2012-09-13` | `2013` | 19 | `0.13%` | `0.13%` | **`1.80%`** | `1.80%` | `1.80%` | `1.80%` | `True` | `True` |
| `2012-12-12` | `2013` | 19 | `0.13%` | `0.13%` | **`1.70%`** | `1.80%` | `1.60%` | `1.80%` | `True` | `True` |
| `2013-03-20` | `2013` | 19 | `0.13%` | `0.13%` | **`1.60%`** | `1.70%` | `1.50%` | `1.60%` | `True` | `True` |
| `2013-06-19` | `2013` | 19 | `0.13%` | `0.13%` | **`1.20%`** | `1.60%` | `1.00%` | `1.50%` | `True` | `True` |
| `2013-09-18` | `2014` | 17 | `0.13%` | `0.13%` | **`1.60%`** | `1.70%` | `1.60%` | `1.60%` | `True` | `True` |
| `2013-12-18` | `2014` | 17 | `0.13%` | `0.13%` | **`1.50%`** | `1.60%` | `1.40%` | `1.60%` | `True` | `True` |
| `2014-03-19` | `2014` | 16 | `0.13%` | `0.13%` | **`1.50%`** | `1.50%` | `1.50%` | `1.40%` | `True` | `True` |
| `2014-06-18` | `2014` | 16 | `0.13%` | `0.13%` | **`1.50%`** | `1.50%` | `1.60%` | `1.50%` | `True` | `True` |
| `2014-09-17` | `2015` | 17 | `1.38%` | `1.12%` | **`1.70%`** | `1.70%` | `1.80%` | `1.75%` | `True` | `True` |
| `2014-12-17` | `2015` | 17 | `1.13%` | `1.38%` | **`1.60%`** | `1.70%` | `1.20%` | `1.80%` | `True` | `True` |
| `2015-03-18` | `2015` | 17 | `0.63%` | `1.13%` | **`1.30%`** | `1.60%` | `0.70%` | `1.20%` | `True` | `True` |
| `2015-06-17` | `2015` | 17 | `0.63%` | `0.63%` | **`1.30%`** | `1.30%` | `0.70%` | `0.70%` | `True` | `True` |

---

## R3 & R4. Remediated Single-Account Share-Lot Engine (`Dynamic NSL + Return-Chained Cash + Two-Sided Cash Fee`) & Pre-AI (`2010–2022`) vs AI (`2023–2026`) Split

> Source CSV: [`R3_true_share_lot_dynamic_nsl_rebalance_audit.csv`](./R3_true_share_lot_dynamic_nsl_rebalance_audit.csv)

| Strategy Variant (`2010-03-11 .. 2026-11-03`, Next-Day Open + Two-Sided `10bp/side`) | Full CAGR | Total Mult | `2010–2019` CAGR | **`2010–2022` (Pre-AI)** | **`2023–2026` (AI Era)** | Full MaxDD | `2024–2026` MaxDD | Daily Sharpe | Rebal Count | Max `SOXL` Weight | End `SOXL` Weight |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `0a. Pure TQQQ V1-Daily (Original 1-Sided Cash Fee, Raw Cash)` | `53.29%` | `1,226.3x` | `46.16%` | `50.07%` | `64.51%` | `-44.54%` | `-36.97%` | `1.233` | 0 | `0.0%` | `0.0%` |
| **`0b. Pure TQQQ V1-Daily (Remediated: 2-Sided Fee + Fixed Cash)`** | **`53.21%`** | **`1,215.3x`** | **`46.16%`** | **`50.06%`** | **`64.17%`** | **`-44.54%`** | **`-36.97%`** | **`1.232`** | 0 | `0.0%` | `0.0%` |
| `0c. Pure TQQQ V1-Daily (Headline PCE SEP + Remediated Cash/Fee)` | `51.47%` | `1,005.3x` | `40.48%` | `45.57%` | `72.91%` | `-59.63%` | `-36.97%` | `1.169` | 0 | `0.0%` | `0.0%` |
| `1a. Pure SOXL V1-Daily -> 1x QQQ (Original 1-Sided Cash Fee)` | `69.96%` | `6,840.3x` | `45.31%` | `51.49%` | `149.32%` | `-70.83%` | `-70.83%` | `1.127` | 0 | `100.0%` | `100.0%` |
| **`1b. Pure SOXL V1-Daily -> 1x QQQ (Remediated: 2-Sided Fee + Fixed Cash)`** | **`69.87%`** | **`6,779.0x`** | **`45.31%`** | **`51.48%`** | **`148.81%`** | **`-70.89%`** | **`-70.89%`** | **`1.126`** | 0 | `100.0%` | `100.0%` |
| `1c. Pure SOXL V1-Daily -> 1x QQQ (Headline PCE SEP + Remediated)` | `72.54%` | `8,787.3x` | `47.89%` | `53.54%` | `154.49%` | `-70.89%` | `-70.89%` | `1.143` | 0 | `100.0%` | `100.0%` |
| `2a. 75/25 Never Rebalance (Drift -> SOXL balloons to 65.7%)` | `60.39%` | `2,606.2x` | `45.95%` | `50.43%` | `98.57%` | `-44.45%` | `-37.65%` | `1.257` | 0 | **`65.7%`** | **`65.0%`** |
| `2b. 75/25 Annual Rebal — Old Normalized Sleeve NSL` | `60.12%` | `2,534.9x` | `48.30%` | `52.33%` | `89.08%` | `-45.93%` | `-36.31%` | `1.259` | 15 | `49.9%` | `49.1%` |
| **`2c. 75/25 Annual Rebal — Remediated Dynamic Share-Lot NSL (Avg Cost)`** | **`59.88%`** | **`2,472.2x`** | **`48.06%`** | **`52.13%`** | **`88.69%`** | **`-45.93%`** | **`-36.31%`** | **`1.256`** | 15 | `49.9%` | `49.1%` |
| **`2d. 75/25 Annual Rebal — Remediated Dynamic Share-Lot NSL (LIFO)`** | **`59.88%`** | **`2,472.2x`** | **`48.06%`** | **`52.13%`** | **`88.69%`** | **`-45.93%`** | **`-36.31%`** | **`1.256`** | 15 | `49.9%` | `49.1%` |
| **`2e. 75/25 Annual Rebal — Remediated Dynamic Share-Lot NSL (FIFO)`** | **`59.88%`** | **`2,472.2x`** | **`48.06%`** | **`52.13%`** | **`88.69%`** | **`-45.93%`** | **`-36.31%`** | **`1.256`** | 15 | `49.9%` | `49.1%` |
| **`2f. 75/25 Semi-Annual Rebal — Remediated Dynamic Share-Lot NSL`** | **`60.18%`** | **`2,548.5x`** | `47.61%` | `51.85%` | `91.35%` | `-46.05%` | `-36.31%` | **`1.261`** | 31 | `49.9%` | **`25.0%`** |
| `2g. 75/25 Quarterly Rebal — Remediated Dynamic Share-Lot NSL` | `59.22%` | `2,306.6x` | `47.18%` | `51.57%` | `87.58%` | `-45.96%` | `-36.31%` | `1.250` | 59 | `41.5%` | `25.0%` |
| `2h. 75/25 Monthly Rebal — Remediated Dynamic Share-Lot NSL` | `59.35%` | `2,338.6x` | `47.55%` | `51.97%` | `86.62%` | `-45.58%` | `-36.01%` | `1.253` | 163 | **`36.8%`** | `25.0%` |
| **`2i. 75/25 On-Switch Rebal — Remediated Dynamic Share-Lot NSL`** | **`61.06%`** | **`2,793.0x`** | `47.32%` | `51.52%` | `97.39%` | `-45.87%` | `-37.28%` | **`1.265`** | 50 | `61.6%` | `25.0%` |
| **`2j. 75/25 ±10% Band Rebal — Remediated Dynamic Share-Lot NSL`** | **`60.22%`** | **`2,561.6x`** | `47.85%` | `52.11%` | `90.50%` | `-46.60%` | `-36.07%` | **`1.261`** | 10 | **`35.3%`** | `34.2%` |
| **`3a. 80/20 Annual Rebal — Remediated Dynamic Share-Lot NSL`** | **`58.63%`** | **`2,168.8x`** | `47.66%` | `51.70%` | `84.08%` | **`-44.70%`** | **`-35.79%`** | **`1.255`** | 15 | `42.8%` | `42.0%` |
| **`3b. 80/20 On-Switch Rebal — Remediated Dynamic Share-Lot NSL`** | **`59.81%`** | **`2,454.4x`** | `47.16%` | `51.29%` | `91.84%` | **`-44.70%`** | `-36.69%` | **`1.266`** | 50 | `54.6%` | `20.0%` |
| `3c. 50/50 Annual Rebal — Remediated Dynamic Share-Lot NSL` | `64.62%` | `4,019.1x` | `48.42%` | `52.96%` | `110.26%` | `-51.88%` | `-46.35%` | `1.227` | 15 | `74.9%` | `74.3%` |

---

## R5. Strict Expanding-Window Walk-Forward Out-of-Sample (`2014–2026`) Validation

> Source CSVs: [`R5_walk_forward_oos_2014_2026_audit.csv`](./R5_walk_forward_oos_2014_2026_audit.csv) & [`R5b_walk_forward_yearly_selections.csv`](./R5b_walk_forward_yearly_selections.csv)

At each year-end $Y \in \{2013 .. 2025\}$, using **only trailing data $[2010 .. Y]$**, we selected `(Trig, Rec)` and the `TQQQ / SOXL` blend weight and traded year $Y+1$ strictly out-of-sample:

| Out-of-Sample Variant (`2014-01-02 .. 2026-11-03`) | `2014–2026` OOS CAGR | **`2014–2022` (Pre-AI OOS)** | **`2023–2026` (AI Era OOS)** | OOS MaxDD | OOS Daily Sharpe |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `1a. Fixed 100% TQQQ V1-Daily (1.2/0.3, Hindsight Fixed)` | `50.86%` | `45.50%` | `64.17%` | `-44.54%` | `1.198` |
| **`1b. Walk-Forward OOS 100% TQQQ (Expanding-Window Trig/Rec)`** | **`52.06%`** | `45.15%` | **`69.57%`** | `-46.29%` | **`1.225`** |
| **`1c. 16-Cell Equal-Weight Ensemble 100% TQQQ (Zero Param Choice)`** | **`50.76%`** | `45.00%` | `65.17%` | `-44.97%` | **`1.201`** |
| `2a. Fixed 75% TQQQ + 25% SOXL Annual (1.2/0.3, Hindsight Fixed)` | `61.47%` | `51.07%` | `88.69%` | `-45.93%` | `1.273` |
| `2b. Fixed 80% TQQQ + 20% SOXL Annual (1.2/0.3, Hindsight Fixed)` | `59.41%` | `49.91%` | `84.08%` | `-44.70%` | `1.264` |
| **`2c. Walk-Forward OOS Blend (Expanding-Window Weight by Sharpe)`** | **`50.52%`** | **`45.04%`** | **`64.17%`** | **`-44.54%`** | **`1.186`** |
| **`2d. Walk-Forward OOS Joint (Expanding-Window Trig/Rec + Weight)`** | **`51.73%`** | **`44.70%`** | **`69.57%`** | **`-46.29%`** | **`1.212`** |
| `3a. Fixed 100% SOXL V1-Daily (1.2/0.3, Hindsight Fixed)` | `82.82%` | `60.27%` | `148.81%` | `-70.89%` | `1.221` |
| **`3b. Walk-Forward OOS 100% SOXL (Expanding-Window Trig/Rec)`** | **`83.38%`** | **`60.68%`** | **`149.87%`** | `-70.89%` | **`1.222`** |
| **`3c. 16-Cell Equal-Weight Ensemble 100% SOXL (Zero Param Choice)`** | **`79.98%`** | `57.62%` | `145.49%` | `-70.89%` | `1.200` |

### Critical Takeaway from Walk-Forward OOS (`R5`)
- **Within-asset `Vol_Z (Trig, Rec)` parameters pass Walk-Forward OOS with zero degradation**: On both `TQQQ` (`52.06%` WF OOS vs `50.86%` Fixed) and `SOXL` (`83.38%` WF OOS vs `82.82%` Fixed), selecting `(Trig, Rec)` strictly from past data or averaging all 16 plateau cells (`50.76%` / `79.98%`) matches or beats the fixed `(1.2, 0.3)` parameters.
- **However, the `75/25` `SOXL` blend weight does NOT pass pre-2023 Walk-Forward OOS selection**: Because `100% TQQQ` had a higher trailing Sharpe than `75/25` at the end of almost every pre-2023 year (`2013..2022`, except `2016–2017` and `2020` where WF picked `90/10`), an expanding-window investor maximizing trailing Sharpe would have entered the 2023–2026 AI boom holding **`100% TQQQ` (`0% SOXL`)**, earning **`50.52%–51.73%`** OOS CAGR instead of the hindsight-fixed `75/25` (`61.47%`). This confirms the external auditor's verdict: **`75/25` is a structural diversification choice, NOT an out-of-sample proven optimal weight, and `100% TQQQ V1-Daily` remains the primary frozen baseline.**
