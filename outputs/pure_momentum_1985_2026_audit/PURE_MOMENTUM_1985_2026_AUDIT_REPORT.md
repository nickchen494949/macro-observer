# 1985–2026 (41.8-Year) Pure Momentum, Rebalance Frequency (`1M / 3M / 6M`), & Frozen `A1-RS 1.35x + V3 Election Reset` Clean-Room Audit Report (Full Raw-Data Clean-Room Edition)

> **Audit Date**: 2026-11-07  
> **Scope**: 1985-01 to 2026-10 (502 months / 41.8 years) long-term momentum verification + Monthly (`1M`) vs Quarterly (`3M`) vs Bi-Annual (`6M`) Rebalancing Audit + `2009-01 to 2026-10` (214 months) Full Raw-Data Clean-Room & Canonical Ledger Reconciliation of Frozen `A1-RS 1.35x + V3 Election Reset`  
> **Reproducible Scripts**:
> - [`build_portable_inputs_from_raw.py`](./build_portable_inputs_from_raw.py) *(100% zero-shared-code raw-data builder: reconstructs all `inputs/*` directly from raw membership YAML/CSV logs, raw Yahoo/Tiingo/WIKI/Archive daily JSONs, raw ALFRED SEP medians, and raw GICS mappings with `< 1e-12` assertions)*
> - [`run_pure_momentum_1985_2026_audit.py`](./run_pure_momentum_1985_2026_audit.py) *(100% standalone, imports only `os, json, numpy, pandas`)*
> - [`zero_shared_code_v3_cleanroom_audit.py`](./zero_shared_code_v3_cleanroom_audit.py) / [`independent_a1_rs_election_reset_audit.py`](./independent_a1_rs_election_reset_audit.py) *(100% zero-shared-code V3 clean-room engine with 214-month row-by-row canonical ledger reconciliation assertions)*
> - [`run_rebalance_frequency_audit.py`](./run_rebalance_frequency_audit.py) *(tests Monthly `1M`, Quarterly `3M` across all 3 calendar phase offsets, and Bi-Annual `6M` across all 6 calendar phase offsets)*
> - **Portable Self-Contained Inputs**: [`inputs/`](./inputs/) *(all stock panels, canonical ledgers, total-return ETFs, and macro/cash tables included in bundle & repo)*

---

## 0. Executive Summary of the External-Audit Remediations (Round 1: Fixes #1–#6 + Round 2: Fixes #7–#9)

Following the external auditor's Round 1 review (`65/100`) and Round 2 review (`86/100 — CONDITIONAL PASS`), all **9 mandatory items** have been implemented and verified via hard `assert` checks:

| Fix # | External Auditor Finding | Remediation Implemented & Verified | Impact on Numbers & Conclusions |
| :--- | :--- | :--- | :--- |
| **Fix #1**<br>*(ETF Total Return)* | `fetch_yahoo.py` extracted `quote[0]['close']` (raw price close without dividends) instead of `adjclose` for `DIA`, `SPY`, `QQQ`, and `XLB..XLY`. | Fetched full 35-year daily **dividend-reinvested `adj_close`** (`inputs/etfs_daily_total_return_adjclose.parquet`) and re-ran all ETF rotation (`03_spy_dia_qqq_rotation_audit.csv`) and 9-SPDR sector lookback grids (`04_sector_lookback_grid_audit.csv`). | `SPY` (`2000-04..2026-10`) rises from `6.26%` (price) to **`8.14%`** (Total Return); `DIA` rises from `6.00%` to **`8.29%`**; `Equal-Weight 9 SPDR` rises from `6.41%` to **`8.92%`**. `12-1m Top-1 H3` (`11.13%` CAGR) and `9m Top-1 H3` (`10.96%`) remain the top sector lookbacks, while `1m–4m` (`2.94%–7.08%`) still lose to EW (`8.92%`). |
| **Fix #2**<br>*(2009–2026 Repaired PIT GICS & Dynamic Assertions)* | `2009–2026` pure-momentum script used raw `sector` instead of repaired PIT GICS `clean_sector`, and `01_era_pit_certification_summary.csv` was hardcoded. | `inputs/panel_1985_2026_monthly.parquet` uses `clean_sector` (from the 8-point remediation). Scripts run dynamic `assert` checks (`868 = 503 active + 365 exited/delisted`, `580/857 = 67.7%` pre-2009) before generating `01_era_pit_certification_summary.csv`. Pre-2009 `-30%/-55%` penalty is explicitly labeled as a **delisting stress approximation** rather than exact Shumway exchange/reason classification. | `BestSec_Stock_Top1_H3` (`2009–2026`) improves from `11.74%` (raw `sector`) to **`15.71%` CAGR** with repaired PIT GICS `clean_sector`. |
| **Fix #3**<br>*(Unified Drifted `10 bp/side` Turnover Cost)* | `EW_Universe`, `EW_Sectors`, `Sec_12_1_*`, and ETF cash switches in `+Avoid SEP&Elec` did not deduct `10 bp/side` turnover cost. | Every single strategy (`EW_Universe`, `EW_Sectors`, `Sec_12_1_Top1_Hard`, `Sec_12_1_Top1_H3`, `Sec_12_1_Top2`, stock strategies, and ETF/cash switches) runs through `eval_weights_drifted(..., cost_bp=0.0010)`. `SP500_Index_0bp` is explicitly labeled as a `0bp` index benchmark. | `2009–2026` `EW_Universe` adjusts from `14.65%` to **`14.57%`**, `Sec_12_1_Top1_Hard` from `16.44%` to **`16.13%`**, `Pure_3Leg_Core_1x` (`1985–2026`) from `28.65%` to **`28.55%`**. |
| **Fix #4**<br>*(`MaxDD` Initial `NAV = 1.0`)* | `eval_series()` computed `eq = (1+r).cumprod()` without prepending initial `1.0`, understating drawdown when a strategy lost money from month 1. | Prepended `1.0` (`np.concatenate([[1.0], np.cumprod(1.0 + r)])`) in all scripts, verified by `assert abs(mdd_tech_09_26 - (-0.594080)) < 1e-4`. | `Tech_Top1_Hard` (`2009–2026`) `MaxDD` is accurately reported as **`-59.41%`** (was `-55.29%`), matching the external auditor's calculation to the basis point. |
| **Fix #5**<br>*(Full Stateful `V3` on `1994 & 2006` + Separate Reporting + Retract OOS Claim)* | Earlier script never used `ELECTION_RESET_JAN` on `1994/2006`, mixed `1994/2006` with `2010/2018/2022`, and falsely claimed `"pre-2009 OOS proves V3"`. | Implemented full stateful `V3` (`Dec 100% Cash + Dec-End Hold-Buffer Clear -> Jan fresh Rank-1 entry` with `10bp/side` cost) and reported **Pre-2009 OOS (`1994, 2006`, $N=2$)** strictly separately from **Post-2009 In-Sample (`2010, 2018, 2022`, $N=3$)** in [`05_v3_election_pre2009_oos_vs_post2009_is_audit.csv`](./05_v3_election_pre2009_oos_vs_post2009_is_audit.csv). **Retracted the claim that pre-2009 OOS validates V3.** | On `1994 & 2006` (`Pre-2009 OOS`), `Pure_3Leg_Core_1x` was positive in both Decembers (`1994-12 +3.56%`, `2006-12 +0.80%`), so `V2` (Dec cash only) changes CAGR by **`-0.12pp`** (`28.55% → 28.43%`) and full `V3` changes CAGR by **`-0.11pp`** (`28.55% → 28.44%`). Thus **`V3 Election Reset` is strictly an $N=3$ Post-2009 In-Sample Forward Challenger (`Frozen Forward Challenger`), NOT a long-history OOS-certified rule.** |
| **Fix #6**<br>*(True Zero-Shared-Code Clean-Room V3 Engine & Portable Inputs)* | `independent_a1_rs_election_reset_audit.py` imported `ind_engine` and `run_full_8point_remediation_audit`, lacked `assert` checks and monthly CSV output, and `ind_engine.py` had a hardcoded local path. | Wrote [`zero_shared_code_v3_cleanroom_audit.py`](./zero_shared_code_v3_cleanroom_audit.py) (and replaced root `independent_a1_rs_election_reset_audit.py`) with **zero project imports**, 100% relative paths, strict `assert` checks, portable [`inputs/`](./inputs/), and exported [`06_v3_214m_cleanroom_reconciliation.csv`](./06_v3_214m_cleanroom_reconciliation.csv) & [`07_v3_variants_v0_to_v8_cleanroom_summary.csv`](./07_v3_variants_v0_to_v8_cleanroom_summary.csv). Fixed relative `ROOT` in `ind_engine.py`. | Reproduces all 214 months (`2009-01..2026-10`) standalone: Production `1.35x` = **`60.96%`**, `A1-RS V0` = **`62.28%`**, Frozen `A1-RS V3` = **`64.95%`** (Sharpe **`1.489`**, Monthly MaxDD **`-22.74%`**). |
| **Fix #7**<br>*(Round 2 Item #1: Full Raw-Data Clean-Room Builder `build_portable_inputs_from_raw.py`)* | Clean-room engine consumed pre-built `v3_spx_panel_214m.parquet`, `v3_ndx_panel_214m.parquet`, and `panel_1985_2026_monthly.parquet` without committing the standalone raw-to-parquet builder script. | Created and committed [`build_portable_inputs_from_raw.py`](./build_portable_inputs_from_raw.py) (**zero imports** of `ind_engine` or `run_full_8point_remediation_audit`), which rebuilds all `inputs/*` directly from raw membership logs (`nasdaq100_src/*.yaml`, `sp500_hist_components.csv`), raw daily price files (`raw/`, `raw_open/`, `raw_tiingo/`, `raw_archive/`, `wiki_bulk/`), raw ALFRED SEP medians (`02_sep_alfred_medians.csv`), and raw GICS files. | Hard `assert` checks verify bit-for-bit equality (`< 1e-12` max difference) across all `107,903` SPX rows, `21,899` NDX rows, `214` regime/cash rows, and `209,894` long-term panel rows. |
| **Fix #8**<br>*(Round 2 Item #2: True 214M Canonical vs Clean-Room Reconciliation)* | `06_v3_214m_cleanroom_reconciliation.csv` generated `Prod / V0 / V3` inside the same clean-room engine rather than comparing `canonical_return - cleanroom_return` row-by-row against the canonical ledger. | Exported [`inputs/canonical_214m_ledgers_prod_v0_v3.csv`](./inputs/canonical_214m_ledgers_prod_v0_v3.csv) from the original canonical pipeline (`run_full_8point_remediation_audit.py` / `step_6902_audit.py`) and updated [`zero_shared_code_v3_cleanroom_audit.py`](./zero_shared_code_v3_cleanroom_audit.py) to compare all 214 months side-by-side (`pick_mismatch`, `max_weight_diff`, `ret_diff_bp`) with hard `assert` checks, outputting [`06b_canonical_vs_cleanroom_reconciliation_summary.csv`](./06b_canonical_vs_cleanroom_reconciliation_summary.csv). | Across all 214 months for `Production 1.35x`, `A1-RS V0`, and `Frozen A1-RS V3`: **`0` pick mismatches**, **`0.0` weight difference**, and **`3.05e-12 bp` (`0.0000 bp`) max return difference**. |
| **Fix #9**<br>*(Round 2 Item #3: Exact `10/14` vs `11/14` Count in `05...csv`)* | Report text stated that under Full `V3` on `1994/2006`, `11/14` strategies were $\le 0$, whereas `05...csv` has `11/14 <= 0` for `V2` (Dec cash only) and **`10/14 <= 0` (`4/14 > 0`) for Full `V3`**. | Corrected Section 0 & Section 5 to report both exact counts: **`11 / 14` $\le 0$ under `V2` (Dec Cash Only)** and **`10 / 14` $\le 0$ (`4 / 14 > 0`: `Stock_12_1_Top2_H5 +0.02pp`, `Tech_Top1_Hard +0.04pp`, `Sec_12_1_Top1_H3 +0.04pp`, `BestSec_Stock_Top1_H3 +0.30pp`) under Full `V3`**. | Text now matches `05_v3_election_pre2009_oos_vs_post2009_is_audit.csv` with 100% precision. |

---

## 1. Strict Point-in-Time (PIT) Certification by Era (`01_era_pit_certification_summary.csv`)

We partition the 502-month backtest (`1985-01` to `2026-10`) into three distinct data-integrity eras generated dynamically from code assertions:

| Era | Period & Months | PIT Certification Verdict | Universe & Membership Source | Delisting & Corporate Action Treatment | Sector Classification | Execution & Cost |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Era 1** | `1985-01 .. 1996-12`<br>*(144 months)* | ❌ **FAIL / NOT PIT-CERTIFIED**<br>*(Illustrative Only)* | `1,030` unique Nasdaq WIKI tickers (avg `385.8/mo`, `close >= $5` Top-500 dollar volume). Pre-1997 S&P 500 membership lists are not on disk. | **Incomplete**: Companies delisted/bankrupt before ~2010 are largely absent from WIKI. Observed terminal exits receive a `-30%` (`close >= $5`) / `-55%` (`close < $5`) **delisting stress approximation**. | **Look-ahead biased**: Static back-mapped GICS (GICS was created by MSCI/S&P in 1999). | Monthly Close-to-Close + unified drifted `10 bp/side` turnover cost |
| **Era 2** | `1997-01 .. 2008-12`<br>*(144 months)* | ⚠️ **FAIL FOR CERTIFICATION / PARTIAL PIT**<br>*(67.7% Price Coverage)* | `sp500_hist_components.csv` has `857` historical S&P 500 tickers in `1997–2008`, of which **`580 / 857 (67.7%)`** have local price series (avg `343.1/mo`); `277` pre-2008 delisted/merged members lack local price files. | **Partial**: `580` covered members include `-30% / -55%` **delisting stress approximation** on terminal mid-spell exits; `277` missing tickers create survivorship uplift in single-stock tails. | Static / Historical GICS Hybrid | Monthly Close-to-Close + unified drifted `10 bp/side` turnover cost |
| **Era 3** | **`2009-01 .. 2026-10`**<br>*(214 months)* | ✅ **PASS / 100.0% STRICT PIT CERTIFIED**<br>*(Verified via Dynamic Assertions)* | `sp500_hist_components.csv`: **`868 / 868 (100.0%)`** unique S&P 500 members (`503` active at `2026-10` + **`365` exited/delisted/acquired**; `841` with $\ge 12\text{m}$ momentum). | **100.0% Complete**: All `365` exited/delisted stocks (`LEH, BSC, WM,WB, MER, SNDK_old,TWX, CELG, MON, ALXN,FRC, SIVB`, etc.) verified via Tiingo/WIKI/Archive + `exit_resolutions.csv`. | **100% Repaired PIT GICS** (`clean_sector` verified via 8-point remediation). | **Next-Month First Trading Day Open-to-Open** ($d_0$ Open $\to d_1$ Open) + unified drifted `10 bp/side` cost |

---

## 2. Pure Momentum Results Across the Three Eras (All Strategies With Unified Drifted `10 bp/side` Turnover Cost & `Initial NAV = 1.0` MaxDD)

### 2.1 Era 3 (`2009-01 to 2026-10`, 214 Months — **100.0% Strict PIT Certified + Repaired PIT GICS**)
Source: [`summary_2009_2026_strict_pit.csv`](./summary_2009_2026_strict_pit.csv)

| Strategy | Months | Net CAGR | Ann. Vol | Sharpe | Monthly MaxDD<br>*(Initial NAV = 1.0)* | Win Rate | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`SP500_Index_0bp`** *(Index Benchmark)* | 214 | 12.67% | 14.83% | 0.88 | -24.77% | 65.4% | Raw S&P 500 price index (`0bp` fee) |
| **`EW_Universe`** *(10bp/side)* | 214 | 14.57% | 17.44% | 0.87 | -30.63% | 66.4% | Equal-weight all PIT S&P 500 stocks |
| **`EW_Sectors`** *(10bp/side)* | 214 | 13.73% | 16.71% | 0.86 | -30.89% | 66.8% | Equal-weight across 11 Repaired PIT GICS sectors |
| **`Sec_12_1_Top1_Hard`** *(10bp/side)* | 214 | 16.13% | 21.41% | 0.81 | -29.27% | 61.7% | Top-1 PIT GICS sector (`+2.40pp` over `EW_Sectors`) |
| **`Sec_12_1_Top2`** *(10bp/side)* | 214 | 13.17% | 17.14% | 0.81 | -24.70% | 62.1% | Top-2 PIT GICS sectors equal-weighted |
| **`Sec_12_1_Top1_H3`** *(10bp/side)* | 214 | 14.33% | 21.31% | 0.74 | -35.20% | 60.7% | Top-1 sector with `Hold <= 3` buffer |
| **`Stock_12_1_Top1_Hard`** *(10bp/side)* | 214 | 31.12% | 51.97% | 0.78 | -70.70% | 60.3% | Single stock `12-1` Top-1 (`Hold <= 1`) |
| **`Stock_12_1_Top1_H3`** *(10bp/side)* 🏆 | 214 | **37.74%** | 45.19% | **0.94** | -44.69% | 60.7% | Single stock `12-1` Top-1 with `Hold <= 3` buffer |
| **`Stock_12_1_Top2_H5`** *(10bp/side)* | 214 | 24.89% | 36.98% | 0.78 | -37.96% | 60.7% | Top-2 stocks with `Hold <= 5` buffer |
| **`Stock_12_1_Top5`** *(10bp/side)* | 214 | 17.58% | 29.89% | 0.69 | -31.86% | 61.2% | Top-5 stocks (`Hold <= 5`) |
| **`Stock_12_1_Top10`** *(10bp/side)* | 214 | 14.20% | 26.25% | 0.64 | -34.62% | 61.2% | Top-10 stocks (`Hold <= 10`) |
| **`Stock_Sharpe_Top2_H5`** *(10bp/side)* | 214 | 13.42% | 31.19% | 0.56 | -48.72% | 59.3% | S&P 500 `12-1 Sharpe` Top-2 (`Hold <= 5`) |
| **`Tech_Top1_Hard`** *(10bp/side)* | 214 | **38.30%** | 47.50% | 0.91 | **-59.41%** | 59.3% | Repaired PIT GICS IT `12-1` Hard Top-1 (`MaxDD` fixed w/ Initial `NAV=1.0`) |
| **`BestSec_Stock_Top1_H3`** *(10bp/side)* | 214 | **15.71%** | 40.96% | 0.56 | -63.75% | 55.6% | Top-1 stock inside Top-1 Repaired PIT GICS sector (`Hold <= 3`) |
| **`Pure_3Leg_Core_1x`** *(10bp/side)* 🏆 | 214 | **28.17%** | **32.34%** | **0.93** | **-39.02%** | **64.0%** | `50% Sharpe Top-2 H5 + 25% Tech Top-1 + 25% SPY Top-1 H3` |

### 2.2 Era 2 + Era 3 (`1997-01 to 2026-10`, 358 Months) & Full 41.8-Year (`1985-01 to 2026-10`, 502 Months)
Sources: [`summary_1997_2026_pit_sp500.csv`](./summary_1997_2026_pit_sp500.csv) & [`summary_1985_2026.csv`](./summary_1985_2026.csv)

| Strategy (All 10bp/side except Index) | `1997–2026` (358m)<br>Net CAGR | `1997–2026`<br>Sharpe | `1997–2026`<br>MaxDD | `1985–2026` (502m)<br>Net CAGR | `1985–2026`<br>Sharpe | `1985–2026`<br>MaxDD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`SP500_Index_0bp`** | 8.11% | 0.59 | -52.56% | 9.55% | 0.68 | -52.56% |
| **`EW_Universe`** | 11.30% | 0.71 | -55.74% | 13.20% | 0.83 | -55.74% |
| **`EW_Sectors`** | 11.59% | 0.75 | -50.65% | 13.90% | 0.90 | -50.65% |
| **`Sec_12_1_Top1_Hard`** | 15.03% | 0.70 | -57.40% | 17.78% | 0.81 | -57.40% |
| **`Sec_12_1_Top2`** | 12.37% | 0.72 | -54.60% | 15.94% | 0.88 | -54.60% |
| **`Sec_12_1_Top1_H3`** | 12.87% | 0.63 | -59.74% | 17.87% | 0.83 | -59.74% |
| **`Stock_12_1_Top1_Hard`** | 19.03% | 0.58 | -98.41% | 25.05% | 0.67 | -98.41% |
| **`Stock_12_1_Top1_H3`** | 18.61% | 0.58 | -97.70% | 28.42% | 0.73 | -97.70% |
| **`Stock_12_1_Top2_H5`** | 13.26% | 0.51 | -90.65% | 18.52% | 0.62 | -90.65% |
| **`Stock_12_1_Top5`** | 14.35% | 0.56 | -77.15% | 19.37% | 0.70 | -77.15% |
| **`Stock_12_1_Top10`** | 12.40% | 0.55 | -74.09% | 17.42% | 0.71 | -74.09% |
| **`Stock_Sharpe_Top2_H5`** | 10.98% | 0.47 | -83.41% | 15.90% | 0.60 | -83.41% |
| **`Tech_Top1_Hard`** | 30.73% | 0.76 | -93.47% | 39.90% | 0.90 | -93.47% |
| **`BestSec_Stock_Top1_H3`** | 14.00% | 0.51 | -90.10% | 29.05% | 0.76 | -90.10% |
| **`Pure_3Leg_Core_1x`** | **21.04%** | **0.69** | **-84.83%** | **28.55%** | **0.87** | **-84.83%** |

> **Critical Takeaway**: While `Pure_3Leg_Core_1x` delivers `28.55%` CAGR over 1985–2026 (`21.04%` over 1997–2026, `28.17%` over strict-PIT 2009–2026), an unhedged `100%` equity momentum portfolio suffered an **`-84.83%` maximum drawdown during the 2000–2002 dot-com/rate-cycle crash**. That is why the `FOMC SEP = OFF` macro regime router (`Stage 3` of our frozen architecture) is indispensable for survival.

---

## 3. Broad Index Rotation (`SPY, DIA, QQQ`) — Repaired With Dividend-Reinvested Total-Return `AdjClose` (`03_spy_dia_qqq_rotation_audit.csv`)

Using **Total-Return `adj_close`** (which properly includes dividends on `DIA` and `SPY`) and deducting drifted `10 bp/side` turnover cost on all rotations and cash switches (`2000-04 to 2026-10`, 319 months):

| Strategy (`Panel A: Real Total-Return ETFs {SPY, DIA, QQQ}`, `2000-04..2026-10`, 319m, `10bp/side`) | Pure Net CAGR | Pure Sharpe | Pure MaxDD | `+Avoid SEP&Elec`<br>Hedged CAGR | Hedged Sharpe | Hedged MaxDD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Buy & Hold SPY`** *(Total Return)* | 8.14% | 0.60 | -50.78% | 7.90% | 0.63 | -50.78% |
| **`Buy & Hold DIA`** *(Total Return)* | 8.29% | 0.62 | -47.03% | 7.88% | 0.65 | -47.03% |
| **`Buy & Hold QQQ`** *(Total Return)* | 7.86% | 0.45 | -81.10% | 9.81% | 0.56 | -79.61% |
| **`Equal-Weight [SPY, DIA, QQQ]`** *(10bp/side)* | **8.34%** | 0.57 | -56.19% | 8.72% | 0.63 | -55.96% |
| **`Best-1 1m`** *(10bp/side)* | 7.33% | 0.49 | -61.17% | 7.87% | 0.55 | -60.43% |
| **`Best-1 3m`** *(10bp/side)* | 7.29% | 0.49 | -62.09% | 9.75% | 0.68 | -53.15% |
| **`Best-1 6m (6-0m)`** *(10bp/side)* | 8.54% | 0.56 | -58.27% | 9.97% | 0.69 | -58.27% |
| **`Best-1 6-1m`** *(10bp/side)* | 8.40% | 0.55 | -59.61% | **10.05%** | **0.70** | -59.61% |
| **`Best-1 12-0m`** *(10bp/side)* | **8.59%** | 0.54 | -58.87% | 9.97% | 0.65 | -59.60% |
| **`Best-1 12-1m`** *(10bp/side)* | 7.48% | 0.48 | -68.61% | 9.11% | 0.60 | -67.40% |

**Conclusion**: Even with dividend-reinvested `adj_close`, rotating among `{SPY, DIA, QQQ}` yields at best **`8.59%` Pure (`+0.25pp` over Equal-Weight `8.34%`)** and **`10.05%` Hedged**, because the three broad US indices have pairwise correlations of `0.85–0.95`. Cross-sectional momentum requires constituent-level dispersion (`QQQ + Tech + SPY` stocks), not broad index ETF switching.

---

## 4. Sector ETF Lookback Grid (`1m` to `12-1m`) — Repaired With Dividend-Reinvested Total-Return `AdjClose` (`04_sector_lookback_grid_audit.csv`)

Using **Total-Return `adj_close`** across all 9 SPDR Sector ETFs (`XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY`, `2000-01 to 2026-10`, 322 months) with drifted `10 bp/side` turnover cost on all portfolios:

| Lookback Window (`2000-01..2026-10`, 322m, Total-Return `AdjClose`, `10bp/side`) | `Top-1 Hard` CAGR | `Top-1 Hard` Sharpe | `Top-1 Hard` MaxDD | `Top-1 (Hold<=3)` CAGR | `Top-1 (Hold<=3)` Sharpe | `Top-1 (Hold<=3)` MaxDD | `Top-2 EW` CAGR | `Top-2 EW` Sharpe | `Top-2 EW` MaxDD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Equal-Weight 9 SPDR Sectors`** *(Baseline)* | **8.92%** | **0.66** | -49.16% | **8.92%** | **0.66** | -49.16% | **8.92%** | **0.66** | -49.16% |
| **`1m (1-0m)`** | 4.58% | 0.32 | -62.22% | 6.84% | 0.44 | -56.22% | 4.43% | 0.35 | -64.72% |
| **`2m (2-0m)`** | 4.17% | 0.31 | -47.78% | 2.94% | 0.25 | -55.06% | 5.80% | 0.44 | -43.47% |
| **`3m (3-0m)`** | 4.12% | 0.31 | -67.84% | 7.08% | 0.46 | -61.20% | 6.37% | 0.46 | -53.46% |
| **`4m (4-0m)`** | 4.90% | 0.35 | -55.69% | 5.09% | 0.36 | -49.56% | 5.94% | 0.45 | -44.83% |
| **`6m (6-0m)`** | 7.44% | 0.47 | -48.37% | 9.88% | 0.58 | -39.38% | 8.05% | 0.57 | -42.92% |
| **`6-1m (Skip 1m)`** | 8.57% | 0.52 | -43.77% | 8.65% | 0.52 | -42.48% | **9.22%** | **0.65** | **-38.42%** |
| **`9m (9-0m)`** | 8.14% | 0.50 | -48.37% | **10.96%** | **0.62** | -46.73% | 7.13% | 0.51 | -43.49% |
| **`12-0m (Raw)`** | 7.17% | 0.44 | -49.22% | 8.56% | 0.51 | -43.71% | 9.00% | 0.62 | -41.20% |
| **`12-1m (Standard)`** 🏆 | 8.18% | 0.48 | -58.15% | **11.13%** | **0.62** | **-43.71%** | 8.40% | 0.56 | -45.32% |

**Conclusion**:
1. Including dividends (`adj_close`) lifts the Equal-Weight 9-SPDR benchmark from `6.41%` (price) to **`8.92%` CAGR** (Total Return, Sharpe `0.66`).
2. **Short lookbacks (`1m, 2m, 3m, 4m`) fail decisively (`2.94%–7.08%` CAGR)**, underperforming Equal-Weight (`8.92%`) by `-1.8pp` to `-6.0pp` due to monthly/quarterly sector mean reversion and turnover drag.
3. **`12-1m Top-1 (Hold <= 3)` (`11.13%` CAGR, `+2.21pp` over EW)** and **`9m Top-1 (Hold <= 3)` (`10.96%` CAGR)** are the only lookbacks that generate meaningful outperformance over Equal-Weight, confirming that our `12-1m` + `Hold <= 3` design in `Ex-IT BestSec` is structurally sound.

---

## 5. Honest Audit of `V3 Election Reset`: Pre-2009 OOS (`1994, 2006`) vs Post-2009 In-Sample (`2010, 2018, 2022`) (`05_v3_election_pre2009_oos_vs_post2009_is_audit.csv`)

In Fix #5, we implemented the **complete stateful `V3` rule** (`December 100% Cash + December-End Hold-Buffer Clear -> January fresh Rank-1 entry`, deducting drifted `10 bp/side` turnover cost on cash entry and January re-entry) across all `Unified → Divided` midterm flips (`1994, 2006, 2010, 2018, 2022`) and separated **Pre-2009 OOS (`1994, 2006`, $N=2$)** from **Post-2009 In-Sample Discovery (`2010, 2018, 2022`, $N=3$)**:

| Strategy (`1985–2026`, 502m, `10bp/side`) | Base CAGR | **Pre-2009 OOS (`1994, 2006`)**<br>`V2` (Dec Cash Only) $\Delta$ | **Pre-2009 OOS (`1994, 2006`)**<br>**Full `V3` (Dec Cash + Jan Reset) $\Delta$** | **Post-2009 IS (`2010, 2018, 2022`)**<br>**Full `V3` $\Delta$** | `1994-12`<br>Base Ret | `1995-01`<br>Base $\to$ V3 | `2006-12`<br>Base Ret | `2007-01`<br>Base $\to$ V3 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`EW_Universe`** | 13.20% | -0.05 pp | **-0.05 pp** | +0.29 pp | +1.62% | `+1.06% → +0.90%` | +0.53% | `+2.50% → +2.30%` |
| **`EW_Sectors`** | 13.90% | -0.03 pp | **-0.03 pp** | +0.29 pp | +0.85% | `+2.24% → +2.06%` | +0.50% | `+2.30% → +2.11%` |
| **`Sec_12_1_Top1_Hard`** | 17.78% | -0.05 pp | **-0.05 pp** | +0.33 pp | +1.30% | `-1.63% → -1.81%` | +0.77% | `+1.58% → +1.58%` |
| **`Sec_12_1_Top1_H3`** | 17.87% | -0.05 pp | **+0.04 pp** | +0.20 pp | +1.30% | `-1.63% → -1.81%` | +0.77% | `+3.41% → +1.58%` |
| **`Stock_12_1_Top1_Hard`** | 25.05% | -0.35 pp | **-0.35 pp** | +1.01 pp | +11.41% | `-21.53% → -21.53%` | +1.30% | `-0.23% → -0.23%` |
| **`Stock_12_1_Top1_H3`** | 28.42% | -0.23 pp | **-0.17 pp** | **+1.66 pp** | +6.84% | `-21.53% → -21.53%` | +1.30% | `+14.13% → -0.23%` |
| **`Stock_12_1_Top2_H5`** | 18.52% | +0.02 pp | **+0.02 pp** | **+1.23 pp** | +2.99% | `-10.72% → -10.72%` | -3.20% | `+6.95% → +6.85%` |
| **`Stock_12_1_Top5`** | 19.37% | -0.06 pp | **-0.06 pp** | +0.84 pp | +2.70% | `-3.41% → -3.45%` | -0.12% | `-0.45% → -0.57%` |
| **`Stock_12_1_Top10`** | 17.42% | -0.03 pp | **-0.03 pp** | +0.65 pp | +3.62% | `-5.03% → -5.09%` | -2.10% | `+3.04% → +2.90%` |
| **`Stock_Sharpe_Top2_H5`** | 15.90% | -0.13 pp | **-0.13 pp** | +0.39 pp | +4.20% | `-15.45% → -15.54%` | +0.94% | `+2.58% → +2.58%` |
| **`Tech_Top1_Hard`** | 39.90% | +0.04 pp | **+0.04 pp** | +0.97 pp | -1.01% | `+0.09% → +0.09%` | +0.05% | `-17.18% → -17.38%` |
| **`BestSec_Stock_Top1_H3`** | 29.05% | +0.30 pp | **+0.30 pp** | +0.58 pp | -1.21% | `+0.09% → +0.09%` | -7.69% | `-2.41% → -2.41%` |
| **`Pure_3Leg_Core_1x`** | **28.55%** | **-0.12 pp** | **-0.11 pp** | **+0.83 pp** | **+3.56%** | `-13.08% → -13.13%` | **+0.80%** | `+0.53% → -3.11%` |

### Why Pre-2009 OOS Does NOT Validate `V3` (And Why `V3` Remains Strictly a `Frozen Forward Challenger`)
1. **Honest Empirical Verdict**:
   - In the two pre-2009 `Unified → Divided` midterm flips (`1994-12` and `2006-12`), `Pure_3Leg_Core_1x` earned **`+3.56%`** (`1994-12`) and **`+0.80%`** (`2006-12`). Exiting to cash in December (`V2`) cost `-0.12pp` CAGR (`28.55% → 28.43%`), and running full `V3` (`Dec Cash + Jan Hold-Buffer Clear`) cost **`-0.11pp` CAGR (`28.55% → 28.44%`)**.
   - Across all 14 strategies in `05_v3_election_pre2009_oos_vs_post2009_is_audit.csv` (which also includes `Sec_12_1_Top2` with Base `15.94%`, `V2 = -0.02pp`, `Full V3 = -0.02pp`):
     - Under **`V2` (Dec Cash Only)**: **`11 / 14` strategies are $\le 0$** (`3 / 14 > 0`: `Stock_12_1_Top2_H5 +0.02pp`, `Tech_Top1_Hard +0.04pp`, `BestSec_Stock_Top1_H3 +0.30pp`).
     - Under **Full `V3` (Dec Cash + Jan Hold-Buffer Clear)**: **`10 / 14` strategies are $\le 0$ (`-0.35pp` to `-0.02pp`), and `4 / 14` are $> 0$** (`Stock_12_1_Top2_H5 +0.02pp`, `Tech_Top1_Hard +0.04pp`, `Sec_12_1_Top1_H3 +0.04pp`, `BestSec_Stock_Top1_H3 +0.30pp`).
   - By contrast, on the three post-2009 `Unified → Divided` flips (`2010-12`, `2018-12`, `2022-12`), `14 / 14` strategies improve (`+0.20pp` to `+1.66pp`, and `+2.70pp` on `A1-RS 1.35x`).
2. **Governance Classification**:
   - We **explicitly retract** any claim that pre-2009 data out-of-sample validates `V3 Election Reset`.
   - `A1-RS 1.35x + V3 Election Reset` is classified strictly as an **$N = 3$ Post-2009 In-Sample Forward Challenger (`Frozen Forward Challenger`)**, while `BestSec_ModBurst_135_75_25_GateV1` (`60.96%` CAGR) remains the **Production Baseline**.
   - December 2026 (if the November 2026 midterm flips `Unified → Divided`) will serve as the first true forward out-of-sample test ($N = 1$ live forward test).

---

## 6. True Zero-Shared-Code Clean-Room & Canonical Reconciliation Audit of `A1-RS 1.35x + V3 Election Reset` (`2009-01 to 2026-10`, 214 Months)

Scripts:
- Raw-to-portable builder: [`build_portable_inputs_from_raw.py`](./build_portable_inputs_from_raw.py) *(zero shared code; rebuilds `v3_spx_panel_214m.parquet`, `v3_ndx_panel_214m.parquet`, `v3_regime_and_cash_214m.csv`, and `panel_1985_2026_monthly.parquet` directly from raw membership logs and raw price JSONs)*
- Clean-room engine & canonical reconciler: [`zero_shared_code_v3_cleanroom_audit.py`](./zero_shared_code_v3_cleanroom_audit.py) (mirrored at [`independent_a1_rs_election_reset_audit.py`](./independent_a1_rs_election_reset_audit.py))

Outputs:
- Row-by-row 214-month Canonical vs Clean-Room reconciliation ledger: [`06_v3_214m_cleanroom_reconciliation.csv`](./06_v3_214m_cleanroom_reconciliation.csv)
- Canonical vs Clean-Room reconciliation summary: [`06b_canonical_vs_cleanroom_reconciliation_summary.csv`](./06b_canonical_vs_cleanroom_reconciliation_summary.csv)
- Full `V0..V8` variant matrix: [`07_v3_variants_v0_to_v8_cleanroom_summary.csv`](./07_v3_variants_v0_to_v8_cleanroom_summary.csv)

### 6.1 214-Month Row-by-Row Canonical vs Clean-Room Reconciliation (`06b_canonical_vs_cleanroom_reconciliation_summary.csv`)

| Strategy | Months Compared | Canonical 214M CAGR | Clean-Room 214M CAGR | Pick Mismatches (214m) | Max Weight Diff | Max Abs Return Diff (bp) | Mean Abs Return Diff (bp) | Audit Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Production Baseline `1.35x`**<br>(`BestSec_ModBurst_135_75_25_GateV1`) | 214 | `60.9619%` | `60.9619%` | **`0 / 214`** | `0.0000` | `3.05e-12 bp` (`0.0000 bp`) | `4.91e-13 bp` | ✅ **PASS** |
| **2. `A1-RS V0 1.35x`**<br>(`A1-RS_ModBurst_135_75_25_GateV1`) | 214 | `62.2753%` | `62.2753%` | **`0 / 214`** | `0.0000` | `3.05e-12 bp` (`0.0000 bp`) | `5.06e-13 bp` | ✅ **PASS** |
| **3. Frozen Challenger: `A1-RS 1.35x + V3`** 🏆<br>(`A1-RS_ModBurst_135_75_25_GateV1_ElectionResetV3`) | 214 | `64.9550%` | `64.9550%` | **`0 / 214`** | `0.0000` | `3.05e-12 bp` (`0.0000 bp`) | `4.97e-13 bp` | ✅ **PASS** |

### 6.2 Clean-Room `V0..V8` Variant Matrix (`07_v3_variants_v0_to_v8_cleanroom_summary.csv`)

| Panel & Variant (`2009-01..2026-10`, 214m, Next-Open Execution, `10bp/side` Drifted Cost) | 213M CAGR<br>*(to 26-09)* | **214M CAGR**<br>*(to 26-10)* | Sharpe<br>*(213M / **214M**)* | Monthly MaxDD<br>*(Initial NAV=1)* | Three Flip Decembers<br>`[2010 / 2018 / 2022]` | Three Flip Januaries<br>`[2011 / 2019 / 2023]` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Production Baseline: `Original 1.35x (V0)`** | 62.46% | **60.96%** | 1.443 / **1.414** | -22.42% | `[-7.38%, -8.48%, -10.47%]` | `[+7.92%, +19.98%, +4.72%]` |
| **2. `A1-RS (-5.0%) 1.35x` (`V0`, No Election Reset)** | 62.84% | **62.28%** | 1.444 / **1.435** | -22.74% | `[-7.38%, -8.48%, -10.47%]` | `[+7.92%, +19.98%, +5.92%]` |
| **3. `A1-RS (-5.0%) 1.35x + V1` (Jan Buffer Reset Only)** | 63.01% | **62.44%** | 1.445 / **1.436** | -22.74% | `[-7.38%, -8.48%, -10.47%]` | `[+13.75%, +19.98%, +5.92%]` |
| **4. `A1-RS (-5.0%) 1.35x + V2` (Dec `100% SGOV` Only)** | 65.37% | **64.78%** | 1.497 / **1.488** | -22.74% | `[-0.24%, -0.00%, +0.20%]` | `[+7.83%, +19.89%, +5.87%]` |
| **5. Frozen Challenger: `A1-RS 1.35x + V3 Election Reset`** 🏆 | **65.54%** | **64.95%** | **1.498 / 1.489** | **-22.74%** | **`[-0.24%, -0.00%, +0.20%]`** | **`[+13.71%, +19.89%, +5.87%]`** |
| **6. `A1-RS (-5.0%) 1.35x + V4` (Half `50% SGOV` + Jan Reset)** | 64.43% | **63.85%** | 1.475 / **1.467** | -22.74% | `[-3.20%, -3.52%, -5.14%]` | `[+13.73%, +19.95%, +5.89%]` |
| **7. `A1-RS (-5.0%) 1.35x + V7` (Dodge 2 Months Dec+Jan)** | 61.93% | **61.37%** | 1.442 / **1.434** | -22.74% | `[-0.24%, -0.00%, +0.20%]` | `[+0.00%, +0.19%, +0.34%]` |
| **8. `A1-RS (-5.0%) 1.35x + V8` (Dodge 3 Months Dec+Jan+Feb)** | 62.22% | **61.66%** | 1.448 / **1.439** | -22.74% | `[-0.24%, -0.00%, +0.20%]` | `[+0.00%, +0.19%, +0.34%]` |

---

## 7. Rebalance Frequency Audit: Monthly (`1M`) vs Quarterly (`3M`) vs Bi-Annual (`6M`) (`08_rebalance_frequency_monthly_quarterly_biannual_audit.csv`)

Script: [`run_rebalance_frequency_audit.py`](./run_rebalance_frequency_audit.py)  
Output Ledger: [`08_rebalance_frequency_monthly_quarterly_biannual_audit.csv`](./08_rebalance_frequency_monthly_quarterly_biannual_audit.csv) (`90` rows across all calendar phase offsets: `Jan/Apr/Jul/Oct`, `Feb/May/Aug/Nov`, `Mar/Jun/Sep/Dec` for `3M`; all 6 phase offsets for `6M`).  
In non-rebalance months, positions **drift naturally with realized returns (`0` turnover cost)** unless a stock delists/exits the universe mid-quarter/half-year.

### 7.1 Panel A: `2009–2026` (214M Strict PIT) Mainline Multi-Leg Strategies (`1M` vs `3M` vs `6M`)

| Strategy (`2009-01..2026-10`, 214m, Next-Open Execution, `10bp/side`) | Rebalance Frequency & Phase Offset | Net CAGR | Ann. Vol | Sharpe | Monthly MaxDD<br>*(Initial NAV=1)* | Win Rate | Ann. 2-Way Turnover |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Frozen: A1-RS 1.35x + V3`** 🏆 | **`1M (Monthly — Frozen Standard)`** | **`64.95%`** | `35.09%` | **`1.489`** | **`-22.74%`** | **`66.4%`** | `8.99x / yr` |
| *(Stock Picks `3M/6M` + Macro `SEP/V3` `1M`)* | `3M (Quarterly — Mean of 3 Offsets)` | `45.84%` | `33.90%` | `1.155` | `-37.19%` | `64.3%` | `6.11x / yr` |
| | `  ├─ 3M Offset 0 (Jan/Apr/Jul/Oct)` | `47.86%` | `34.10%` | `1.188` | `-33.89%` | `64.5%` | `5.65x / yr` |
| | `  ├─ 3M Offset 1 (Feb/May/Aug/Nov)` | `44.19%` | `32.78%` | `1.150` | `-36.46%` | `63.6%` | `6.24x / yr` |
| | `  └─ 3M Offset 2 (Mar/Jun/Sep/Dec)` | `45.47%` | `34.81%` | `1.126` | `-41.22%` | `65.0%` | `6.45x / yr` |
| | `6M (Bi-Annual — Mean of 6 Offsets)` | `40.68%` | `34.18%` | `1.042` | `-42.39%` | `63.6%` | `4.95x / yr` |
| **`Frozen: A1-RS 1.35x + V3`**<br>*(Full Portfolio Frozen Between Rebalances)* | `3M (Quarterly — Mean of 3 Offsets)` | `42.31%` | `34.23%` | `1.087` | `-40.99%` | `63.6%` | `5.43x / yr` |
| | `6M (Bi-Annual — Mean of 6 Offsets)` | `35.35%` | `34.67%` | `0.928` | `-46.92%` | `62.2%` | `3.76x / yr` |
| **`A1-RS 1.35x (V0, No Election Reset)`** | **`1M (Monthly)`** | **`62.28%`** | `35.29%` | **`1.435`** | **`-22.74%`** | **`65.9%`** | `8.59x / yr` |
| | `3M (Quarterly — Mean of 3 Offsets)` | `39.31%` | `34.68%` | `1.021` | `-40.38%` | `62.8%` | `5.10x / yr` |
| | `6M (Bi-Annual — Mean of 6 Offsets)` | `32.71%` | `35.09%` | `0.872` | `-44.59%` | `61.3%` | `3.46x / yr` |
| **`Production Baseline 1.35x`** | **`1M (Monthly)`** | **`60.96%`** | `35.15%` | **`1.414`** | **`-22.42%`** | **`65.4%`** | `8.50x / yr` |
| | `3M (Quarterly — Mean of 3 Offsets)` | `38.91%` | `34.72%` | `1.010` | `-40.38%` | `62.3%` | `5.05x / yr` |
| | `6M (Bi-Annual — Mean of 6 Offsets)` | `32.76%` | `35.12%` | `0.873` | `-45.24%` | `61.1%` | `3.45x / yr` |
| **`Unlevered Pure 3-Leg Core 1.0x`**<br>(`50% QQQ + 25% Tech + 25% SPY`) | **`1M (Monthly)`** | **`48.05%`** | `33.24%` | **`1.248`** | **`-31.16%`** | **`65.4%`** | `6.66x / yr` |
| | `3M (Quarterly — Mean of 3 Offsets)` | `32.78%` | `33.63%` | `0.913` | `-40.05%` | `62.3%` | `3.86x / yr` |
| | `6M (Bi-Annual — Mean of 6 Offsets)` | `28.21%` | `34.09%` | `0.807` | `-46.86%` | `62.1%` | `2.65x / yr` |

### 7.2 Panel B & Panel C: Pure Momentum Stocks (`2009–2026` & `1985–2026`) vs Total-Return SPDR Sector ETFs (`2000–2026`)

| Era & Universe | Strategy (`10bp/side` Drifted Cost) | **`1M (Monthly)`**<br>CAGR / Sharpe / MaxDD | **`3M (Quarterly Mean)`**<br>CAGR / Sharpe / MaxDD | **`6M (Bi-Annual Mean)`**<br>CAGR / Sharpe / MaxDD | Structural Verdict |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Panel B1: `2009–2026`**<br>*(214m Strict PIT Stocks)* | `Stock_12_1_Top1_H3` | **`37.70%` / `0.94` / `-44.69%`** | `20.78%` / `0.62` / `-65.94%` | `11.41%` / `0.42` / `-74.26%` | **`1M` wins by `+16.9pp` over `3M`** (`+26.3pp` over `6M`) |
| | `Stock_12_1_Top1_Hard` | **`31.11%` / `0.78` / `-70.70%`** | `18.30%` / `0.56` / `-70.44%` | `10.17%` / `0.39` / `-76.68%` | **`1M` wins by `+12.8pp` over `3M`** |
| | `Tech_Top1_Hard` | **`38.30%` / `0.91` / `-59.41%`** | `32.40%` / `0.82` / `-61.26%` | `25.42%` / `0.70` / `-62.87%` | **`1M` wins by `+5.9pp` over `3M`** (`+12.9pp` over `6M`) |
| | `Pure_3Leg_Core_1x` *(SPX)* | **`28.14%` / `0.93` / `-39.02%`** | `22.90%` / `0.81` / `-47.55%` | `16.41%` / `0.64` / `-57.13%` | **`1M` wins by `+5.2pp` over `3M`** (`+11.7pp` over `6M`) |
| | `Stock_12_1_Top5` | `17.57%` / `0.69` / `-31.86%` | **`19.65%` / `0.74` / `-40.48%`** | `15.53%` / `0.63` / `-48.03%` | Diversified `Top-5` benefits slightly from `3M`, but deeper DD |
| | `Sec_12_1_Top1_Hard` *(PIT GICS)* | `16.12%` / `0.81` / **`-29.27%`** | **`16.51%` / `0.83`** / `-33.42%` | `15.49%` / `0.79` / `-34.50%` | Unbuffered Sector Top-1 slightly higher CAGR at `3M` |
| **Panel B2: `1985–2026`**<br>*(502m Long-Term Stocks)* | `Pure_3Leg_Core_1x` | **`28.53%` / `0.87`** / `-84.83%` | `25.42%` / `0.81` / `-85.08%` | `20.34%` / `0.70` / `-85.81%` | **`1M` wins by `+3.1pp` over `3M`** (`+8.2pp` over `6M`) |
| | `Tech_Top1_Hard` | **`39.90%` / `0.90`** / `-93.47%` | `33.24%` / `0.81` / `-92.04%` | `26.86%` / `0.71` / `-92.05%` | **`1M` wins by `+6.7pp` over `3M`** (`+13.0pp` over `6M`) |
| | `Stock_12_1_Top1_H3` | **`28.40%` / `0.73`** / `-97.70%` | `20.99%` / `0.62` / `-94.75%` | `13.48%` / `0.48` / `-94.74%` | **`1M` wins by `+7.4pp` over `3M`** (`+14.9pp` over `6M`) |
| **Panel C: `2000–2026`**<br>*(322m 9-SPDR ETFs `AdjClose`)* | `SPDR_12_1_Top1_Hard` | `8.19%` / `0.48` / `-58.11%` | **`11.06%` / `0.62` / `-55.81%`** | `10.66%` / `0.60` / `-53.03%` | On **unbuffered** Sector ETFs, `3M` cuts monthly rank-1 whipsaw (`+2.87pp`) |
| | `SPDR_12_1_Top1_H3` *(Buffered)* | **`11.13%` / `0.62` / `-43.70%`** | `10.17%` / `0.58` / `-51.14%` | `9.79%` / `0.57` / `-51.40%` | **`1M + Hold<=3 Buffer` (`11.13%`, DD `-43.70%`) beats `3M Hard` (`11.06%`, DD `-55.81%`)!** |
| | `SPDR_6_1_Top2_EW` | `9.22%` / `0.65` / **`-38.42%`** | `9.19%` / `0.65` / `-41.00%` | **`9.59%` / `0.67`** / `-42.19%` | Broadly flat (`9.19%–9.59%`) across `1M / 3M / 6M` |

### 7.3 Key Mechanism Takeaway: Why `1M + Hold Buffer + RS_sec` Dominates `3M` and `6M`
1. **Why Quarterly (`3M`) and Bi-Annual (`6M`) Crush Single-Stock Momentum (`-19.1pp` to `-29.6pp` CAGR on `A1-RS + V3`)**:
   - In concentrated single-stock momentum (`Top-1 / Top-2`), monthly rebalancing with our **`Hold <= 3 / Hold <= 5 + RS_sec >= -5.0%` buffer** already holds multi-month winners (`NVDA`, `ANET`, `AVGO`, `PLTR`, `NFLX`) for 3–9+ consecutive months with zero turnover whenever they remain healthy in the top ranks.
   - Slowing the check frequency to `3M` or `6M` saves only **`~28–40 bp/yr`** in transaction costs (`8.99x/yr → 6.11x/yr`), but **delays exiting broken momentum leaders and macro regime transitions by 1–5 months** (e.g., staying trapped in post-peak stocks during 2011, 2015, 2018Q4, 2022, and 2026-10), expanding Monthly MaxDD from **`-22.74%` (`1M`)** to **`-37.19%` (`3M`)** and **`-42.39%` (`6M`)** while introducing massive calendar-month luck (`30.09%` to `51.35%` across `6M` offsets).
2. **Why `1M + Hold <= 3` Also Beats `3M` on Sector ETFs (`Panel C`)**:
   - If one trades **unbuffered** `9-SPDR 12-1m Top-1 Hard`, `1M` suffers monthly rank-1 whipsaws (`8.19%` CAGR), so slowing to `3M Quarterly` improves CAGR to `11.06%`.
   - However, **`1M Monthly with Hold <= 3 Buffer` (`11.13%` CAGR, MaxDD `-43.70%`)** captures the exact same whipsaw reduction while retaining the ability to exit a crashing sector at the end of any month if it drops below Rank 3 — achieving higher CAGR (`11.13%` vs `11.06%`) and **`-12.11pp` shallower MaxDD (`-43.70%` vs `-55.81%`)** than `3M Quarterly`!

---

## 8. Complete Manifest of the Self-Contained Audit Bundle (`PURE_MOMENTUM_AND_FROZEN_V3_AUDIT_BUNDLE.zip`)

Every file required to rebuild the portable inputs from raw data and run all three audit engines from scratch is packaged inside the bundle and committed to the repository:

1. **Documentation & Specs**:
   - `PURE_MOMENTUM_1985_2026_AUDIT_REPORT.md` *(this report)*
   - `FROZEN_STRATEGY_SPEC.md` *(master 4-layer frozen strategy specification)*
2. **Standalone Zero-Shared-Code Scripts**:
   - `build_portable_inputs_from_raw.py` *(rebuilds all `inputs/*` directly from raw membership YAML/CSV logs, raw Yahoo/Tiingo/WIKI/Archive daily JSONs, raw ALFRED SEP medians, and raw GICS mappings with `< 1e-12` assertions)*
   - `run_pure_momentum_1985_2026_audit.py` *(runs all 1985–2026 stock/sector/ETF/V3 OOS vs IS audits and assertions)*
   - `zero_shared_code_v3_cleanroom_audit.py` / `independent_a1_rs_election_reset_audit.py` *(runs the 214-month zero-shared-code V3 clean-room engine and row-by-row canonical ledger reconciliation assertions)*
   - `run_rebalance_frequency_audit.py` *(runs the Monthly `1M` vs Quarterly `3M` vs Bi-Annual `6M` rebalancing audit across all calendar phase offsets)*
3. **Output Audit CSV Ledgers (`01` through `08` + Era Summaries)**:
   - `01_era_pit_certification_summary.csv`
   - `summary_2009_2026_strict_pit.csv`
   - `summary_1997_2026_pit_sp500.csv`
   - `summary_1985_2026.csv`
   - `monthly_returns_1985_2026_shumway.csv`
   - `03_spy_dia_qqq_rotation_audit.csv`
   - `04_sector_lookback_grid_audit.csv`
   - `05_v3_election_pre2009_oos_vs_post2009_is_audit.csv`
   - `06_v3_214m_cleanroom_reconciliation.csv`
   - `06b_canonical_vs_cleanroom_reconciliation_summary.csv`
   - `07_v3_variants_v0_to_v8_cleanroom_summary.csv`
   - `08_rebalance_frequency_monthly_quarterly_biannual_audit.csv`
4. **Portable Self-Contained Inputs (`inputs/`)**:
   - `inputs/canonical_214m_ledgers_prod_v0_v3.csv` *(canonical 214-month ledgers for `Production 1.35x`, `A1-RS V0`, and `Frozen A1-RS V3` exported from the original pipeline for row-by-row reconciliation)*
   - `inputs/panel_1985_2026_monthly.parquet` *(502-month stock panel with Repaired PIT GICS `clean_sector` in 2009–2026)*
   - `inputs/etfs_daily_total_return_adjclose.parquet` *(35-year daily dividend-reinvested `adj_close` for `SPY, DIA, QQQ, XLB..XLY`)*
   - `inputs/macro_and_cash_indices_monthly_1983_2026.csv` *(monthly macro/T-bill/cash indices)*
   - `inputs/pre2009_coverage_stats.json` *(exact `sp500_hist_components.csv` coverage counts)*
   - `inputs/v3_spx_panel_214m.parquet` *(214-month strict PIT S&P 500 panel, 868 tickers)*
   - `inputs/v3_ndx_panel_214m.parquet` *(214-month strict PIT Nasdaq-100 panel)*
   - `inputs/v3_regime_and_cash_214m.csv` & `.parquet` *(214-month `SEP`, `qqq_vol21`, `dm_panic`, and Tiingo `SGOV/BIL` open-to-open cash returns)*
