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
| **1** | **2012–2015 SEP Medians Missing & `Core PCE` vs `Headline PCE` Ambiguity** | High | Parsed all 15 pre-Dec-2015 FOMC SEP meetings (`14` in `2012-01-25 .. 2015-06-17` from official Fed SEP Table 2 PDFs + `2015-09-17`, $N = 16..19$ participants) in `data/fomc_sep/`, and tabulated both **`Core PCE Median (JCXFEMD)` (official frozen spec)** and **`Headline PCE Median`** across all 59 meetings (`2012–2026`) in [`R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv`](./R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv). | Across all 14 meetings in `2012-01..2015-06` (and 15 through `2015-09`), target-year Core PCE (`1.2%–1.9%`) and Headline PCE (`0.7%–2.0%`) never exceeded `2.0%`, so **`0 / 15` meetings triggered `SEP = OFF`** (confirming `SEP = ON` throughout 2012–2015). Across 2012–2026, Core PCE vs Headline PCE match on `56 / 59` meetings (`TQQQ` Core PCE `53.21% / -44.54%` vs Headline PCE `51.47% / -59.63%`; `SOXL` Core PCE `69.87%` vs Headline PCE `72.54%`). |
| **2** | **Dynamic NSL Cost-Basis Updates Across Rebalances & Partial Trim NSL Policy** | High | Replaced normalized sleeve multipliers with a **Unified Single-Account Share-Lot Engine** (`run_unified_two_sleeve_share_lot_account`) where adding shares to an active `3x` sleeve at rebalance appends a new share lot at execution `adjOpen / (1 - FEE)`, dynamically updating NSL cost basis (`Average Cost`, `LIFO`, `FIFO`), and explicitly tested both `rebal_respects_nsl=False` (partial trim exempt) and `rebal_respects_nsl=True` (partial trim gated by NSL). | Exactly reproduces the external auditor's JS remediation: `75/25 Annual` CAGR **`60.12%` $\rightarrow$ `59.88%`** (identical under `Average Cost`, `LIFO`, and `FIFO`; **`59.45%`** with MaxDD **`-45.69%`** if partial rebalance trims are also gated by NSL), `75/25 OnSwitch` **`61.14%` $\rightarrow$ `61.06%`**, `80/20 Annual` **`58.94%` $\rightarrow$ `58.63%`**. Without rebalance, `SOXL` weight drifts to a maximum of **`65.7%`** (`65.0%` at sample end). |
| **3** | **True Stateful Continuous Walk-Forward Out-of-Sample (OOS) Validation (`2014–2026`, 16-Cell Grid) & Pre-AI (`2010–2022`) Split** | High | Ran a **Single Continuous Stateful Across-Year Share-Lot Account** (`run_stateful_wf_oos`) for Walk-Forward OOS (`2014–2026`), preserving actual held shares and NSL cost basis across every Jan 1 boundary while updating `(Trig, Rec)` (16-cell `4×4` grid) and `TQQQ / SOXL` weights at each prior year-end `2013..2025` using past data only ([`R5_walk_forward_oos_2014_2026_audit.csv`](./R5_walk_forward_oos_2014_2026_audit.csv)). | **Key Discovery**: Within-asset `(Trig, Rec)` Continuous Walk-Forward OOS has **zero degradation** (`TQQQ` WF OOS **`52.06%`**, MaxDD **`-46.29%`**, Sharpe **`1.225`** vs Fixed `50.86% / -44.54% / 1.198`; `SOXL` WF OOS **`83.38%`**, MaxDD **`-70.89%`**, Sharpe **`1.222`** vs Fixed `82.82% / -70.89% / 1.221`). **However**, Continuous Walk-Forward weight selection picks **`100% TQQQ` (`90/10` in 3 yrs)** before 2023 (**`50.47%`** OOS CAGR; **`51.68%`** joint param+weight vs `61.47%` / Sharpe `1.273` for hindsight-fixed `75/25`), confirming that `75/25` is a discretionary satellite allocation rather than an OOS-derived optimal weight. |
| **4** | **Two-Sided Transaction Cost (`20bp`) on Cash ETF Switches** | Medium | Charged `(1 - FEE)^2` (`10bp` sell equity ETF + `10bp` buy cash ETF `BIL/SGOV`, and vice versa) on all `3x/1x <-> 0x Cash` transitions. | Pure `TQQQ` CAGR `53.29%` $\rightarrow$ **`53.21%`**; Pure `SOXL` (`SOXX` signal) CAGR `69.96%` $\rightarrow$ **`69.87%`**. |
| **5** | **`BIL -> SGOV` Direct Price Overwrite (`+9.04%` Jump on `2020-05-28`)** | Medium | Built `build_return_chained_cash()` chaining `SGOV` daily returns onto `BIL` from `2020-06-01` onward, eliminating the `+9.044%` price-level splice jump (`+9.044%` $\rightarrow$ **`+0.000%`**). | Confirmed `0.000%` splice jump. Also documented that mandatory `SEP = OFF` cash exits override NSL (e.g., `2024-12-19` `SOXL` closed at `-22.21%`), so `SOXL` win rate is `12/12 (100%)` on `Vol_Z` trims and **`15/16 (93.75%)`** across all closed `3x` legs. |
| **6** | **True Yang-Zhang (2000) vs `GK-YZ` & 15-Cell vs 19/20-Cell Plateau** | Medium | Implemented both **Exact Original Yang-Zhang (2000, *Journal of Business*, centered $\sigma_{\text{OJ}}^2 + k\sigma_{\text{OC}}^2 + (1-k)\sigma_{\text{RS}}^2$)** and **`GK-YZ`**, and reported both the exact **15-cell (`3×5`)** and **20-cell (`4×5`)** plateaus ([`R6_true_yang_zhang_and_15_vs_20_cell_volatility_audit.csv`](./R6_true_yang_zhang_and_15_vs_20_cell_volatility_audit.csv)). | Exact Yang-Zhang (`W20`: `52.46%` CAGR, `-44.54%` MaxDD, 15-cell median `51.86%`) and `GK-YZ` (`53.40%` CAGR, 15-cell median `52.28%`) both trail Close-to-Close (`54.89%`, 15-cell median `55.31%`, 20-cell median `55.00%`). |
| **7** | **`SOXX` vs `SOXL` 2021 Index Transition, `SOXL` Self-Signal Backtest & Report-to-CSV Match** | Medium | Audited the 47-trading-day transition gap (`2021-06-21` `SOXX -> ICE` to `2021-08-25` `SOXL -> ICE`) in [`R7_soxx_vs_soxl_2021_index_transition_audit.csv`](./R7_soxx_vs_soxl_2021_index_transition_audit.csv), explicitly backtested `SOXL` Self-Signal (with `3x SOXX` pre-inception warmup) in [`R3`](./R3_true_share_lot_dynamic_nsl_rebalance_audit.csv) (`1d`), and synchronized 100% of report numbers with CSVs. | During the 47-day transition window, `Vol_Z(SOXX)` vs `Vol_Z(SOXL)` correlation was **`0.99698`** (`0.99831` full sample) with **`100.00%`** agreement (`0` divergence days). Over the full remediated sample (`2010-03-11..2026-11-03`), `SOXX` signal yields **`69.87%`** CAGR (`-70.89%` MaxDD) vs **`67.75%`** CAGR (`-70.89%` MaxDD) for `SOXL` self-signal with `3x SOXX` warmup. |

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
| **`1b. Pure SOXL V1-Daily -> 1x QQQ (Remediated: 2-Sided Fee + Fixed Cash, SOXX Signal)`** | **`69.87%`** | **`6,779.0x`** | **`45.31%`** | **`51.48%`** | **`148.81%`** | **`-70.89%`** | **`-70.89%`** | **`1.126`** | 0 | `100.0%` | `100.0%` |
| `1c. Pure SOXL V1-Daily -> 1x QQQ (Headline PCE SEP + Remediated)` | `72.54%` | `8,787.3x` | `47.89%` | `53.54%` | `154.49%` | `-70.89%` | `-70.89%` | `1.143` | 0 | `100.0%` | `100.0%` |
| **`1d. Pure SOXL V1-Daily -> 1x QQQ (Remediated: SOXL Self-Signal + 3x SOXX Warmup)`** | **`67.75%`** | **`5,501.5x`** | `44.22%` | `50.61%` | `140.21%` | `-70.89%` | `-70.89%` | `1.103` | 0 | `100.0%` | `100.0%` |
| `2a. 75/25 Never Rebalance (Drift -> SOXL balloons to 65.7%)` | `60.39%` | `2,606.2x` | `45.95%` | `50.43%` | `98.57%` | `-44.45%` | `-37.65%` | `1.257` | 0 | **`65.7%`** | **`65.0%`** |
| `2b. 75/25 Annual Rebal — Old Normalized Sleeve NSL` | `60.12%` | `2,534.9x` | `48.30%` | `52.33%` | `89.08%` | `-45.93%` | `-36.31%` | `1.259` | 15 | `49.9%` | `49.1%` |
| **`2c. 75/25 Annual Rebal — Remediated Dynamic Share-Lot NSL (Avg Cost, Partial Trim Exempt)`** | **`59.88%`** | **`2,472.2x`** | **`48.06%`** | **`52.13%`** | **`88.69%`** | **`-45.93%`** | **`-36.31%`** | **`1.256`** | 15 | `49.9%` | `49.1%` |
| **`2d. 75/25 Annual Rebal — Remediated Dynamic Share-Lot NSL (LIFO)`** | **`59.88%`** | **`2,472.2x`** | **`48.06%`** | **`52.13%`** | **`88.69%`** | **`-45.93%`** | **`-36.31%`** | **`1.256`** | 15 | `49.9%` | `49.1%` |
| **`2e. 75/25 Annual Rebal — Remediated Dynamic Share-Lot NSL (FIFO)`** | **`59.88%`** | **`2,472.2x`** | **`48.06%`** | **`52.13%`** | **`88.69%`** | **`-45.93%`** | **`-36.31%`** | **`1.256`** | 15 | `49.9%` | `49.1%` |
| **`2f. 75/25 Annual Rebal — Partial Trim Also Gated by NSL (rebal_respects_nsl=True)`** | **`59.45%`** | **`2,364.1x`** | `47.38%` | `51.60%` | `88.69%` | **`-45.69%`** | `-36.31%` | `1.250` | 13 | `49.9%` | `49.1%` |
| **`2g. 75/25 Semi-Annual Rebal — Remediated Dynamic Share-Lot NSL`** | **`60.18%`** | **`2,548.5x`** | `47.61%` | `51.85%` | `91.35%` | `-46.05%` | `-36.31%` | **`1.261`** | 31 | `49.9%` | **`25.0%`** |
| `2h. 75/25 Quarterly Rebal — Remediated Dynamic Share-Lot NSL` | `59.22%` | `2,306.6x` | `47.18%` | `51.57%` | `87.58%` | `-45.96%` | `-36.31%` | `1.250` | 59 | `41.5%` | `25.0%` |
| `2i. 75/25 Monthly Rebal — Remediated Dynamic Share-Lot NSL` | `59.35%` | `2,338.6x` | `47.55%` | `51.97%` | `86.62%` | `-45.58%` | `-36.01%` | `1.253` | 163 | **`36.8%`** | `25.0%` |
| **`2j. 75/25 On-Switch Rebal — Remediated Dynamic Share-Lot NSL`** | **`61.06%`** | **`2,793.0x`** | `47.32%` | `51.52%` | `97.39%` | `-45.87%` | `-37.28%` | **`1.265`** | 50 | `61.6%` | `25.0%` |
| **`2k. 75/25 ±10% Band Rebal — Remediated Dynamic Share-Lot NSL`** | **`60.22%`** | **`2,561.6x`** | `47.85%` | `52.11%` | `90.50%` | `-46.60%` | `-36.07%` | **`1.261`** | 10 | **`35.3%`** | `34.2%` |
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
| **`1b. Walk-Forward OOS 100% TQQQ (Continuous Stateful Share-Lot Account, 16-Cell Grid)`** | **`52.06%`** | `45.15%` | **`69.57%`** | **`-46.29%`** | **`1.225`** |
| **`1c. 16-Cell Equal-Weight Ensemble 100% TQQQ (Zero Param Choice)`** | **`50.76%`** | `45.00%` | `65.17%` | `-44.97%` | **`1.201`** |
| `2a. Fixed 75% TQQQ + 25% SOXL Annual (1.2/0.3, Hindsight Fixed)` | `61.47%` | `51.07%` | `88.69%` | `-45.93%` | **`1.273`** |
| `2b. Fixed 80% TQQQ + 20% SOXL Annual (1.2/0.3, Hindsight Fixed)` | `59.41%` | `49.91%` | `84.08%` | `-44.70%` | `1.264` |
| **`2c. Walk-Forward OOS Blend (Continuous Stateful Account, Expanding-Window Weight + DD50-Cap Sharpe)`** | **`50.47%`** | **`44.97%`** | **`64.17%`** | **`-44.54%`** | **`1.185`** |
| **`2d. Walk-Forward OOS Joint (Continuous Stateful Account, Expanding-Window Trig/Rec + Weight)`** | **`51.68%`** | **`44.63%`** | **`69.57%`** | **`-46.29%`** | **`1.211`** |
| **`2e. Walk-Forward OOS Blend (Continuous Stateful Account, Expanding-Window Weight by Raw Sharpe)`** | **`50.47%`** | **`44.97%`** | **`64.17%`** | **`-44.54%`** | **`1.185`** |
| `3a. Fixed 100% SOXL V1-Daily (1.2/0.3, Hindsight Fixed)` | `82.82%` | `60.27%` | `148.81%` | `-70.89%` | `1.221` |
| **`3b. Walk-Forward OOS 100% SOXL (Continuous Stateful Share-Lot Account, 16-Cell Grid)`** | **`83.38%`** | **`60.68%`** | **`149.87%`** | **`-70.89%`** | **`1.222`** |
| **`3c. 16-Cell Equal-Weight Ensemble 100% SOXL (Zero Param Choice)`** | **`79.98%`** | `57.62%` | `145.49%` | `-70.89%` | `1.200` |

### Critical Takeaway from Walk-Forward OOS (`R5`)
- **Within-asset `Vol_Z (Trig, Rec)` parameters pass Continuous Stateful Walk-Forward OOS with zero degradation**: On both `TQQQ` (`52.06%` WF OOS vs `50.86%` Fixed) and `SOXL` (`83.38%` WF OOS vs `82.82%` Fixed), selecting `(Trig, Rec)` strictly from past data across the 16-cell (`4×4`) grid in a single continuous across-year account matches or beats the fixed `(1.2, 0.3)` parameters.
- **However, the `75/25` `SOXL` blend weight does NOT pass pre-2023 Walk-Forward OOS selection**: Because `100% TQQQ` had a higher trailing Sharpe than `75/25` at the end of 10 of the 13 years (`2013..2025`, with `90/10` selected in `2017–2018` and `2021`), an expanding-window investor maximizing trailing Sharpe in a continuous across-year account earned **`50.47%–51.68%`** OOS CAGR instead of the hindsight-fixed `75/25` (`61.47%` / Sharpe `1.273`). This confirms the external auditor's verdict: **`75/25` is a discretionary high-beta semiconductor satellite allocation, NOT an out-of-sample proven optimal weight, and `100% TQQQ V1-Daily` remains the primary frozen baseline.**

---

## Round-3 Addendum: Point-in-Time Nasdaq-100 Market Breadth Divergence Audit (`B0..B5`, Falsified / Not Adopted)

> **Audit Script**: [`audit_breadth_divergence_top_escape.py`](../../audit_breadth_divergence_top_escape.py)  
> **Output Ledgers & CSVs**:
> - [`B0_daily_pit_ndx_breadth_and_coverage.csv`](./B0_daily_pit_ndx_breadth_and_coverage.csv) — All 4,189 trading days (`2010-03-11 .. 2026-11-03`) of strictly Point-in-Time Nasdaq-100 constituent coverage (`median 102 YAML members`, `101 priced`, `97.77%` mean coverage, `92.00%` min coverage, zero within-month source look-ahead, zero daily return clipping) and `% > SMA20/50/100/200` breadth series.
> - [`B1_breadth_divergence_conditional_outcomes.csv`](./B1_breadth_divergence_conditional_outcomes.csv) — Both forward 40-day drawdown definitions (`Drop from Signal Close` vs `True Rolling Peak-to-Trough MaxDD in [t, t+40]`) and **de-clustered independent 40-day episodes**.
> - [`B2_major_qqq_peaks_breadth_anatomy.csv`](./B2_major_qqq_peaks_breadth_anatomy.csv) — Programmatically detected all 19 objective `QQQ` peaks followed by a $\ge 10\%$ drawdown before making a new high (`2010–2026`).
> - [`B3_v1_tqqq_breadth_divergence_strategy_tests.csv`](./B3_v1_tqqq_breadth_divergence_strategy_tests.csv) — All 23 breadth variants tested on the **exact frozen `R3` baseline (`53.21%` CAGR, `-44.54%` MaxDD, `1.232` Sharpe, `33` switches)**.
> - [`B4_baseline_vs_A5_C5_trade_ledger.csv`](./B4_baseline_vs_A5_C5_trade_ledger.csv) — Complete trade-by-trade switch ledger comparing Baseline (`53.21%`), `A1`, `A5`, and `C5`.
> - [`B5_A5_C5_parameter_sensitivity_grid.csv`](./B5_A5_C5_parameter_sensitivity_grid.csv) — Parameter sensitivity grid across neighboring thresholds for `A5` and `C5`.

### Why Market Breadth Divergence (`A5` / `C5`) Is Falsified & Rejected Upon Round-3 Remediation
1. **De-Clustering Eliminates the Apparent `31.71%` Crash Probability in `B1`**:
   - While `31.71%` of raw signal days (`26 / 82` days) with `QQQ at 60d High + Breadth_200 < 55%` saw a $\ge 10\%$ drop from the signal price (and `40.24%` true peak-to-trough MaxDD vs `9.66% / 16.93%` for all 60d-high days), those 82 days are heavily auto-correlated within the same market tops.
   - Once de-clustered into **independent non-overlapping 40-day episodes** ([`B1`](./B1_breadth_divergence_conditional_outcomes.csv)), the 82 days collapse into **`12` independent episodes**, of which only **`2 / 12 (16.7%)`** had a $\ge 10\%$ drop from the signal day (vs **`11 / 85 (12.9%)`** baseline across all 60d-high episodes) and **`3 / 12 (25.0%)`** had a $\ge 10\%$ true MaxDD (vs **`18 / 85 (21.2%)`** baseline) — statistically indistinguishable from noise.
2. **Programmatic Objective Peak Detection (`B2`) Shows Low Sensitivity Across All 19 Historical $\ge 10\%$ Drawdown Peaks**:
   - Across all **19 objectively detected `QQQ` peaks** followed by a $\ge 10\%$ drawdown (`2010–2026`), on the peak day:
     - `Breadth_50 < 50%` occurred on **`1 / 19 (5.3%)`** peaks (`2026-10-06`);
     - `Breadth_200 < 55%` occurred on **`0 / 19 (0.0%)`** peaks;
     - `EW - CW 20d < -3%` occurred on **`6 / 19 (31.6%)`** peaks.
3. **`A5` (`Breadth_200 < 55%`) Fails the Parameter Sensitivity Plateau Test (`B5`)**:
   - Under the exact `53.21%` baseline, `Breadth_200 < 55%` yields `54.51%` CAGR / `-38.05%` MaxDD, but **every single neighboring threshold performs worse than the `53.21%` baseline**:
     - `Breadth_200 < 50%`: `52.31%` CAGR, `-44.15%` MaxDD
     - `Breadth_200 < 52%`: `52.30%` CAGR, `-44.37%` MaxDD
     - `Breadth_200 < 55%`: `54.51%` CAGR, `-38.05%` MaxDD *(isolated 1-point spike catching Nov 2015 `53.5%`)*
     - `Breadth_200 < 57%`: `50.11%` CAGR, `-44.68%` MaxDD
     - `Breadth_200 < 60%`: `51.02%` CAGR, `-43.58%` MaxDD
     - `Breadth_200 < 65%`: `46.34%` CAGR, `-56.47%` MaxDD
4. **`C5` (`EW-CW 20d < -3% -> Vol_Z > 0.8`) Relies on a Single 2011 Trade Across 17 Years (`B4`)**:
   - Trade-by-trade decomposition ([`B4_baseline_vs_A5_C5_trade_ledger.csv`](./B4_baseline_vs_A5_C5_trade_ledger.csv)) proves that `C5` (`54.41%` vs `53.21%` baseline) triggers only **2 times in 17 years** (`2011-07-20` and `2015-07-20`) and has **0 triggers in the last 11 years (`2015-08 .. 2026-11`)**.
   - On `2015-07-20`, `C5` de-levered for 13 days and then **re-levered back to `3x TQQQ` on `2015-08-06` (`Vol_Z = -0.072 < 0.3`) right before the August 24, 2015 flash crash**, so its entire `+1.20%/yr` CAGR difference comes from exiting 10 trading days earlier on a single historical event (`2011-07-20` at `Vol_Z = 1.118` vs `2011-08-03` at `Vol_Z = 1.285`).
   - **Verdict**: In accordance with our anti-overfitting standards (same reason `HYG/IEF` was rejected in Stage 12), **Market Breadth Divergence (`A5 / C5`) is rejected and NOT added to the frozen `V1-Daily` specification.**
