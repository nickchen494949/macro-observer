# 🔬 100% Clean-Room Independent Audit Report: `QQQ Full100 + Price-Only LightGBM Top-1`

- **Repository**: `nickchen494949/macro-observer`
- **Audited Commit**: `a455ed7` (with comparison to pre-purge commit `20d6cbf`)
- **Audited Strategy**: `QQQ_Full100__T1_SetA_Price_Only__lgbm__Top1` (Monthly PIT Nasdaq-100 full pool, 18 pure-price cross-sectionally ranked features, annual walk-forward LightGBM regression, Top-1 selection, next-month first trading day Open-to-Open execution, 10 bps/side transaction cost)
- **Original Headline Claims Under Audit**:
  - `2019–2026.09 (93 holding months)`: **CAGR `62.31%`**, Sharpe `0.97`, Monthly MaxDD `-65.51%`, Daily MaxDD `-66.76%`
  - `2015–2026.09 (140 holding months)`: **CAGR `50.28%`**, Sharpe `0.92`, Monthly MaxDD `-65.51%`, Daily MaxDD `-66.76%`
- **Audit Directory**: [`outputs/qqq_lgbm_cleanroom_audit_20261103/`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103)
- **Clean-Room Isolation**: Zero `import` or code reuse from `backtest.py`, `ndx_universe.py`, `ml_features.py`, `ml2_features.py`, `ml2_run.py`, `run_ml3_qqq_iwm_pools.py`, `run_ml3_feature_discovery.py`, or any cached `.parquet` panel (`panel_ml3_qqq_union.parquet`, `panel_ml3_full.parquet`). Original ledger (`outputs/ml3_feature_discovery_20261102/ledgers_qqq_iwm/QQQ_Full100__T1_SetA_Price_Only__lgbm__Top1.csv`) was read **only** in Step 4 for final month-by-month reconciliation.

---

## 0. Executive Verdict & Mandatory 6 Answers

| # | Audit Question | Clean-Room Audit Finding |
|---|---|---|
| **1** | **Overall Audit Verdict** | 🟡 **CONDITIONAL PASS** on arithmetic & execution reproduction (`140/140` holding months reproduced to `0.0000 bps`); ❌ **FAIL** as statistical proof that Price-only ML genuinely adds alpha over Nasdaq-100 momentum or survives clean standalone feature construction. **Cannot be used as live-trading expected CAGR.** |
| **2** | **Are `62.31%` (`2019–2026`) and `50.28%` (`2015–2026`) independently reproduced? What remains after strict `Y-1-11-30` purging and feature-splicing repair?** | • **Exact Reproduction (`Mode A1`)**: **YES (`140/140` months match, `62.31%` / `50.28%`, max return diff `0.0000 bps`)**.<br>• **Strict `Y-1-11-30` Purging**: In the original script (`run_ml3_qqq_iwm_pools.py` line 690), the final refit (`tr2`) **already** stopped at `Y-1-11-30` in both `20d6cbf` and `a455ed7`. Purging validation `val_end` from `Y-1-12-31` (`Mode A2`) to `Y-1-11-30` (`Mode A1`) selects the **exact same `num_leaves`** in all 12 folds, leaving CAGR unchanged at **`62.31%` / `50.28%`**.<br>• **Fixing Cross-Universe `sector_mom` + `dv_ratio` Splicing Bug (`Mode B1 Pure QQQ`)**: In the original script, QQQ stocks that were also in the S&P 500 (`~80%`) inherited S&P 500 `sector_mom` and `raw_volume`-only `dv_ratio` from `panel_ml3_full.parquet`, while non-S&P QQQ stocks (`~20%`) used S&P$\cup$NDX `sector_mom` and `raw_volume+raw_ndx` `dv_ratio`. When all 18 features are computed cleanly within the standalone QQQ universe (`Mode B1`), `81/140` monthly Top-1 picks change and CAGR drops to **`48.36%` (`2019–2026`)** and **`27.16%` (`2015–2026`)**. |
| **3** | **Worst Reasonable Adversarial Stress CAGR & MaxDD** | • **Combined Institutional Stress (`Pure QQQ + Fixed num_leaves=7 + Nov-30 Purge + 25 bps/side all-in cost & open slippage`)**: **`2019–2026` CAGR = `43.85%`** (Daily MaxDD `-56.44%`), **`2015–2026` CAGR = `25.65%`** (Daily MaxDD `-57.23%`).<br>• **Delayed Execution (`T+1 Close` on `Pure QQQ`)**: **`2019–2026` CAGR = `32.45%`**, **`2015–2026` CAGR = `18.48%`** (Daily MaxDD `-58.87%`).<br>• **Adverse Random Seed (`seed=100` instead of `seed=7` on `Mode A1`)**: **`2019–2026` CAGR = `40.05%`**, **`2015–2026` CAGR = `27.24%`**. |
| **4** | **Does Price-Only ML genuinely beat QQQ Pure 12-1 Momentum, or is it just the QQQ pool?** | **No statistically significant ML edge (`p = 0.62` to `0.87`). The alpha comes overwhelmingly from the Nasdaq-100 constituent pool + extreme concentration.**<br>• `Mode A1 (62.31%)` vs `QQQ Pure 12-1 Mom Top-1 (43.86%)` in `2019–2026`: Newey-West **$t = 0.49$ ($p = 0.6217$)**, Wilcoxon $p = 0.8157$, monthly win rate **`39.8%` (`37/93` months)**.<br>• `Mode B1 Pure QQQ (48.36% / 27.16%)` vs `QQQ Pure 12-1 Mom Top-1 (43.86% / 41.43%)`: **`2019–2026` NW $t = -0.16$ ($p = 0.8704$)**; **`2015–2026` underperforms pure momentum by `-14.27%/yr` ($t = -0.99$)**.<br>• `QQQ Pure 12-1 Mom Top-3` (`55.49%` / `40.96%`, Sharpe `1.13`) beats both `Mode A1 Top-3` (`36.73%` / `31.39%`) and `Mode B1 Top-3` (`45.03%` / `34.10%`). |
| **5** | **Unresolved Material Risks** | 1. **Cross-Universe Feature Splicing Artifact** (`62.31% -> 48.36%` in `2019–2026`, `50.28% -> 27.16%` in `2015–2026` when fixed).<br>2. **Extreme Rank-1 Cliff**: `Rank #1 = 62.31%`, `Rank #2 = 9.48%`, `Rank #3 = 18.56%`, `Rank #4 = 4.40%`, `Rank #5 = -12.65%` (`2019–2026`). A genuine continuous cross-sectional signal does not collapse to `9.48%` at Rank #2.<br>3. **Severe Random-Seed Instability**: With `subsample=0.8, colsample_bytree=0.8`, changing `random_state` across 10 seeds swings `2019–2026` CAGR between **`40.05%` and `102.32%`** (`2015–2026`: `27.24%` to `62.31%`).<br>4. **4-Stock Concentration**: `SNDK` (3m), `TSLA` (6m), `MRNA` (9m), and `PDD` (2m) generate **`73.51%` of total 2019–2026 log wealth** in just `20/93` months. Removing the 6 super-winners drops `2019–2026` CAGR to **`17.70%`** (below passive `QQQ ETF` `22.40%`).<br>5. **Missing `2015-01` Holding Month**: Original `TEST_YEARS` filtered on formation year `t.year >= 2015`, starting holdings in `2015-02` (`140` months instead of `141`). |
| **6** | **Credibility Score (`0–100`)** | **`54 / 100`** (`88/100` for mechanical execution, PIT pricing & arithmetic integrity; `20/100` for standalone ML feature purity, cross-sectional stability, and statistical significance over simple Nasdaq-100 momentum). |

---

## 1. Clean-Room Architecture & Audit Trail Files

All clean-room engines and CSV outputs reside in [`outputs/qqq_lgbm_cleanroom_audit_20261103/`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103):

| Clean-Room Module / Artifact | Purpose |
|---|---|
| [`q1_ndx_pit_universe.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q1_ndx_pit_universe.py) | Standalone PIT Nasdaq-100 constituent reconstructor (`2008-12-31 .. 2026-09-30`) + MediaWiki historical revision ID verifier |
| [`q2_cleanroom_price_engine.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q2_cleanroom_price_engine.py) | Standalone multi-source daily Close/Open/Volume loader, `>30d` segment-break splitter, ticker-reuse & alias resolver, and Tiingo EOD cross-checker |
| [`q3_cleanroom_18_features.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q3_cleanroom_18_features.py) | Standalone 18-feature engine (`hybrid_repro` & `pure_qqq` modes) + 5-date physical price-truncation invariance auditor |
| [`q4_walkforward_lgbm_and_reconcile.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q4_walkforward_lgbm_and_reconcile.py) | Standalone walk-forward LightGBM trainer across 6 clean-room modes (`Mode A1..A3`, `Mode B1..B3`) + 140-month reconciliation engine |
| [`q5_stress_and_statistics.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q5_stress_and_statistics.py) | 59-scenario adversarial stress suite, Newey-West HAC / block-bootstrap / Wilcoxon tests, DSR / Bonferroni / HLZ multiple-testing audit, and concentration tables |
| [`step1_ndx_pit_monthly_summary.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step1_ndx_pit_monthly_summary.csv) | Month-by-month PIT Nasdaq-100 raw count vs clean-room eligible count (`214` months) |
| [`step1_wiki_revision_crosscheck.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step1_wiki_revision_crosscheck.csv) | 19-event historical Wikipedia revision verification (`TSLA`, `NVDA`, `MRNA`, `PDD`, `SMCI`, `APP`, `PLTR`, `MSTR`, `ARM`, `SNDK`, etc.) |
| [`step2_tiingo_vs_primary_crosscheck.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step2_tiingo_vs_primary_crosscheck.csv) | 140-month holding-by-holding primary vs Tiingo EOD `adjOpen`/`adjClose` cross-check |
| [`step3_truncation_test_audit.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step3_truncation_test_audit.csv) | Physical price-truncation invariance test results at 5 historical cutoffs |
| [`step4_month_by_month_reconciliation.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step4_month_by_month_reconciliation.csv) | Complete 140-month side-by-side ledger reconciliation across `Original`, `Mode A1`, `Mode A2`, `Mode A3`, and `Mode B1` |
| [`step4_fold_hyperparameter_audit.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step4_fold_hyperparameter_audit.csv) | Fold-by-fold (`2015..2026`) train/validation window boundaries and chosen `num_leaves` |
| [`step5_performance_summary_table.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step5_performance_summary_table.csv) | Full metric summary across `2019–2026.09`, `2015–2026.09`, `2015–2018`, `2019–2021`, `2022`, and `2023–2026.09` |
| [`step6_adversarial_stress_tests.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step6_adversarial_stress_tests.csv) | All 59 adversarial stress-test results |
| [`step7_paired_statistical_tests.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step7_paired_statistical_tests.csv) | Paired Newey-West HAC, 4,000-draw stationary block bootstrap, and Wilcoxon signed-rank tests |
| [`step8_multiple_testing_audit.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step8_multiple_testing_audit.csv) | Deflated Sharpe Ratio (DSR), Bonferroni, Šidák, and HLZ ($t > 3.0$) adjustments across `56`, `256`, and `391` trials |
| [`step9_concentration_audit.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step9_concentration_audit.csv) | Stock-level log-wealth contribution & holding frequency (`2019–2026` and `2015–2026`) |

---

## 2. Step 1 Audit: Nasdaq-100 (`QQQ`) Historical PIT Universe Reconstruction

### 2.1 Reconstruction Methodology & Coverage
- In [`q1_ndx_pit_universe.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q1_ndx_pit_universe.py), we parsed the annual Nasdaq-100 constituent snapshots and dated addition/removal changelog YAML files (`n100-ticker-changes-2007.yaml` through `2026.yaml`, originally sourced from Nasdaq press releases and archived Wikipedia revision diffs) along with corporate rename mappings (`PCLN -> BKNG`, `FB -> META`, `GOOG -> GOOGL`, `LBTYA`, `DISCK`, `FOXA`, etc.).
- Across all **214 formation month-ends** (`2008-12-31 .. 2026-09-30`):
  - **Raw PIT Constituent Count**: Mean `101.6` symbols/month (`min = 99`, `max = 107`, accounting for dual-class share lines such as `GOOG/GOOGL`, `FOXA/FOX`, `LBTYA/LBTYK`, `DISCA/DISCK`).
  - **Clean-Room Price-Coverage Count**: Mean `100.2` symbols/month (`98.58%` coverage), rising to **`100.00%` coverage from `2016-07-31` through `2026-09-30`**.
  - **12-Month Momentum-Eligible Count**: Mean `99.1` symbols/month (`97.50%` of raw PIT roster).

### 2.2 Independent Verification Against Historical Wikipedia Revision Snapshots (MediaWiki API)
To verify that top winning picks and major index transitions were not backfilled with look-ahead bias, we queried historical revisions of the English Wikipedia `Nasdaq-100` article at exact historical dates (`step1_wiki_revision_crosscheck.csv`):

| Symbol | Event Audited | Official Effective Date | PIT Pre-Event Roster Check | PIT Post-Event Roster Check | Historical Wiki Revision ID Verified | Audit Result |
|---|---|---|---|---|---|---|
| `TSLA` | Added to Nasdaq-100 (replacing `ORCL`) | `2013-07-15` | `2013-06-30`: `False` | `2013-07-31`: `True` | `591065783` (`2014-01-17`) | **PASS** |
| `NVDA` | Continuous member since 2001 | `2008-12-31` | — | `2009-01-31`: `True` | `591065783` (`2014-01-17`) | **PASS** |
| `AMD` | Added in Dec 2018 annual reconstitution | `2018-12-24` | `2018-11-30`: `False` | `2018-12-31`: `True` | `879215499` (`2019-01-19`) | **PASS** |
| `MRNA` | Added to Nasdaq-100 (`2020-07-20`) | `2020-07-20` | `2020-06-30`: `False` | `2020-07-31`: `True` | `970351624` (`2020-07-30`) | **PASS** |
| `MRNA` | Removed in Dec 2024 annual reconstitution | `2024-12-23` | `2024-11-30`: `True` | `2024-12-31`: `False` | `1266195725` (`2024-12-30`) | **PASS** |
| `PDD` | Added to Nasdaq-100 (`2020-08-24`) | `2020-08-24` | `2020-07-31`: `False` | `2020-08-31`: `True` | `976037282` (`2020-08-31`) | **PASS** |
| `ARM` | Added to Nasdaq-100 (`2024-06-24`) | `2024-06-24` | `2024-05-31`: `False` | `2024-06-30`: `True` | `1237470108` (`2024-07-29`) | **PASS** |
| `SMCI` | Added (`2024-07-22`) / Removed (`2024-12-23`) | `2024-07-22` | `2024-06-30`: `False` / `2024-11-30`: `True` | `2024-07-31`: `True` / `2024-12-31`: `False` | `1237470108` & `1266195725` | **PASS** |
| `APP` | Added (`2024-11-18`, replacing `DLTR`) | `2024-11-18` | `2024-10-31`: `False` | `2024-11-30`: `True` | `1266195725` (`2024-12-30`) | **PASS** |
| `PLTR` | Added in Dec 2024 annual reconstitution | `2024-12-23` | `2024-11-30`: `False` | `2024-12-31`: `True` | `1266195725` (`2024-12-30`) | **PASS** |
| `MSTR` | Added in Dec 2024 annual reconstitution | `2024-12-23` | `2024-11-30`: `False` | `2024-12-31`: `True` | `1266195725` (`2024-12-30`) | **PASS** |
| `SNDK` (Old) | Removed upon Western Digital acquisition | `2016-05-12` | `2016-04-30`: `True` | `2016-05-31`: `False` | `723104029` (`2016-06-01`) | **PASS** |
| `SNDK` (New) | **Never in Nasdaq-100 (`False` in 2025–2026)** | `2025-02-24` (Spin-off) | `2025-12-31`: `False` | `2026-01-31`: **`True` in YAML (ERROR!)** | `1310000000+` | **CRITICAL FINDING (See §2.3)** |

### 2.3 Critical PIT Universe Finding: 2026 `SNDK` vs `WDC` Contamination in `n100-ticker-changes-2026.yaml`
- In `data/nasdaq100_src/n100-ticker-changes-2026.yaml`, `SNDK` is listed under `starting_2026` as a Nasdaq-100 constituent throughout 2026 (`2026-01-31` through `2026-09-30`).
- **Why this matters**:
  1. Legacy SanDisk (`SNDK__OLD`, acquired by `WDC` in May 2016) was a Nasdaq-100 member until `2016-05-12`.
  2. New SanDisk Corp (`SNDK`, spun off from `WDC` in Feb 2025 and added to the S&P 500 in Nov 2025) trades on Nasdaq, and `WDC` remained a Nasdaq-100 member. Even if `SNDK` was added or conflated in the 2026 YAML snapshot, **new `SNDK` had only 11 months of trading history (`2025-02-24 .. 2026-01-30`) on `2026-01-31`**, yet in the original `run_ml3_qqq_iwm_pools.py` pipeline its `2026-01-31` row was copied from `panel_ml3_full.parquet` where `SNDK` was a valid S&P 500 stock, allowing `SNDK` to be picked in **`2026-01` (`+63.27%`), `2026-06` (`+31.37%`), and `2026-08` (`+13.71%`)**!
  3. Those **3 holding months of `SNDK` alone account for `23.75%` of total 2019–2026 log wealth**.
  4. In our adversarial stress suite (`step6_adversarial_stress_tests.csv`), we explicitly test banning `SNDK` (and other super-winners): removing `SNDK` or the top super-winners slashes `2019–2026` CAGR (see Section 6).

---

## 3. Step 2 Audit: Clean-Room Price Engine & Tiingo Second-Source Cross-Check

### 3.1 Clean-Room Price Engine Verification
- Built in [`q2_cleanroom_price_engine.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q2_cleanroom_price_engine.py) directly from raw vendor files without importing `backtest.py`.
- Enforced `>30` calendar-day gap segment breaks (`126` broken ticker series split into distinct segments `_seg0`, `_seg1`, etc.) and explicit time-based ticker reuse splits (`SNDK` pre/post `2020-01-01` so `SNDK__OLD` never splices into new `SNDK`; `TMUS` pre/post `2013-05-01`).
- Across all **140 holding months** (`2015-02-28 .. 2026-09-30`) of the original ledger:
  - **Primary Open-to-Open Return Match**: **`140 / 140` months match to `0.0000 bps`** (`max |diff| = 0.0000 bps`).
  - **No `unresolved_no_quote_after_entry -> 0%` masks**: Every single holding month (`140/140`) resolved via standard next-month first trading day Open-to-Open (`ok_open_to_open` in `137/140` months) or documented historical delisting/missing-open Close fallback (`3/140` months: `STRZA` in `2016-05`, `ENDP` in `2017-05`, and `CELG` in `2019-01`).

### 3.2 Independent Tiingo EOD Cross-Check (`step2_tiingo_vs_primary_crosscheck.csv`)
- Cross-checked against independent Tiingo EOD `adjOpen` and `adjClose`:
  - **Close-to-Close (`Primary adjClose` vs `Tiingo adjClose`)**: Median absolute difference = **`0.00 bps`** (`90th percentile = 3.21 bps`, reflecting minor vendor dividend-reinvestment timing conventions).
  - **Open-to-Open (`Primary Open` vs `Tiingo adjOpen`)**: Median absolute difference = **`0.00 bps`**.
  - **3 Notable Vendor Divergences Identified**:
    1. `2016-05` (`STRZA`): Primary lacked raw Open for `STRZA` and used next-day Close (`+8.38%` net); Tiingo `adjOpen` had full intraday Open bars (`+5.85%` net, `-252.8 bps` diff).
    2. `2017-05` (`ENDP`): Primary lacked raw Open for `ENDP` and used next-day Close (`+18.42%` net); Tiingo `adjOpen` gave `+22.27%` net (`+385.0 bps` diff).
    3. `2019-01` (`CELG`): On `2019-01-02` (` Bristol-Myers Squibb` cash+stock acquisition announcement of Celgene before the market open), primary lacked raw Open for delisted `CELG` and fell back to `2019-01-02` Close (`$80.43`, after the `+26%` M&A jump, yielding `+9.11%` net for the rest of January), whereas Tiingo `adjOpen` captured the `2019-01-02` opening print (`$82.10`) or pre-deal close (`+37.98%` C2C).
  - Swapping primary returns for Tiingo `adjOpen`-to-`adjOpen` returns across all matched holdings yields **`59.10%` CAGR (`2019–2026`)** and **`48.30%` CAGR (`2015–2026`)**.

---

## 4. Step 3 Audit: Clean-Room 18-Feature Engine, Truncation Invariance & The Cross-Universe Splicing Bug

### 4.1 Exact Formulas Audited (`18` Pure-Price Features)
In [`q3_cleanroom_18_features.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q3_cleanroom_18_features.py), we independently implemented all 18 features strictly from daily data up to formation date $t$:
- **Stock Momentum & Reversal**: `mom_12_1`, `mom_6_1`, `mom_3_1`, `rev_1m`, `mom_accel = mom_3_1 - (P[t-3m]/P[t-6m] - 1)`
- **Trend & Distance**: `dist_sma200`, `dist_sma50`, `dist_52wh`
- **Volatility, Beta & Path Quality**: `vol_3m` (63d), `vol_12m` (252d), `beta_12m` (252d vs `SPY`), `maxret_1m` (21d max daily return), `smooth` (`(P[t]/P[t-12m]-1) / vol_12m`)
- **Liquidity**: `dv_ratio` (`21d mean DollarVolume / 126d mean DollarVolume`)
- **Regime & Sector**: `mkt_ret12`, `mkt_above200`, `mkt_vol3m` (market-level, zero cross-sectional variance after per-month rank transformation), and `sector_mom` (cross-sectional GICS sector mean of `mom_6_1` at month $t$).
- **Cross-Sectional Normalization**: Within each formation month $t$, each feature is converted to percentile ranks $\in (0, 1]$, centered to `[-0.5, +0.5]`, with missing values imputed to `0.0`.

### 4.2 Physical Price-Truncation Invariance Test (`step3_truncation_test_audit.csv`)
We physically deleted all daily Close, Open, and Volume bars after $T_{\text{cut}}$ for 5 historical dates (`2015-06-30`, `2018-11-30`, `2020-08-31`, `2022-12-31`, `2025-05-31`) and recomputed the entire feature matrix from scratch:

| Cutoff Date $T_{\text{cut}}$ | Eligible Universe Count (Full vs Truncated) | Exact Universe Match | Max Absolute Diff Across All 18 Features | Audit Status |
|---|---|---|---|---|
| `2015-06-30` | `102` vs `102` | `True` | `0.00e+00` | **PASS** |
| `2018-11-30` | `100` vs `100` | `True` | `0.00e+00` | **PASS** |
| `2020-08-31` | `99` vs `99` | `True` | `0.00e+00` | **PASS** |
| `2022-12-31` | `100` vs `100` | `True` | `0.00e+00` | **PASS** |
| `2025-05-31` | `100` vs `100` | `True` | `0.00e+00` | **PASS** |

- **Result**: **Zero forward price leakage in feature construction (`5/5 PASS`)**.

### 4.3 🔴 CRITICAL DISCOVERY: Cross-Universe `sector_mom` & `dv_ratio` Splicing Bug in Original `run_ml3_qqq_iwm_pools.py`
While auditing why a standalone QQQ feature engine (`Mode B1`) differed from the original ledger, we uncovered a subtle but major structural bug in `outputs/ml3_feature_discovery_20261102/run_ml3_qqq_iwm_pools.py` (lines 270–416):
1. **How the original script built `panel_ml3_qqq_union.parquet`**:
   - Instead of computing the 18 price features cleanly on the Nasdaq-100 (`QQQ`) universe, `run_ml3_qqq_iwm_pools.py` took the existing S&P 500 panel (`panel_ml3_full.parquet`) for all `(t, sym)` pairs where the QQQ member was **also in the S&P 500 (`in_sp == True`, ~80% of QQQ)**, and only ran `build_extra_panel()` for the **non-S&P 500 QQQ members (`in_sp == False`, ~20% of QQQ, such as `MRNA` pre-July 2021, `PDD`, `JD`, `BIDU`, `NTES`, `ASML`, `MELI`, `DOCU`, `ZM`, `TEAM`, `WDAY`, `SIRI`, `LCID`, `RIVN`, `ARM`, `APP`, `MSTR`)**.
2. **Why this corrupted two cross-sectional features (`sector_mom` and `dv_ratio`)**:
   - **`sector_mom` Contamination**: For S&P 500 members (`in_sp == True`), `sector_mom` in `panel_ml3_full.parquet` was the **S&P 500 GICS sector average of `mom_6_1`**. For non-S&P 500 QQQ members (`in_sp == False`), `build_extra_panel()` computed `sector_mom` as the **S&P 500 $\cup$ NDX union GICS sector average of `mom_6_1`**. When `ranked()` subsequently ranked `sector_mom` across the ~100 QQQ stocks in month $t$, **two QQQ stocks in the exact same GICS sector received different `sector_mom` percentile ranks depending on whether they were in the S&P 500!** Effectively, `sector_mom` leaked a binary indicator of S&P 500 vs non-S&P 500 membership (`PDD`, `JD`, `BIDU`, `MRNA`, `MELI`, `ASML`) into the decision trees.
   - **`dv_ratio` Asymmetry**: `panel_ml3_full.parquet` (`ml2_features.py`) loaded dollar volume only from `data/raw_volume/` (missing `data/raw_ndx/`), leaving `dv_ratio = NaN -> 0.0` for `741` stock-months that had valid volume in `data/raw_ndx/`. Meanwhile, `build_extra_panel()` loaded volume from both `data/raw_volume/` and `data/raw_ndx/`.
3. **Quantitative Impact of Fixing the Bug (`Mode A1 Hybrid Repro` vs `Mode B1 Pure Standalone QQQ`)**:
   - Replicating the original spliced construction from raw files (`Mode A1`) reproduces **`140/140` monthly picks (`62.31%` / `50.28%` CAGR)** identically.
   - Computing `sector_mom` strictly within the Nasdaq-100 (`QQQ`) constituent pool and `dv_ratio` uniformly across all vendor stores (`Mode B1 Pure QQQ`) changes **`81 out of 140` monthly Top-1 picks**:
     - `2019–2026.09` CAGR drops from **`62.31%` to `48.36%`** (`-13.95%/yr`).
     - `2015–2026.09` CAGR drops from **`50.28%` to `27.16%`** (`-23.12%/yr`, with `2015–2018` falling from `+29.93%` to **`-6.28%`**).

---

## 5. Step 4 Audit: Walk-Forward Training, `Y-1-11-30` Boundary Purging & Month-by-Month Reconciliation

### 5.1 Annual Walk-Forward Schedule & The `Y-1-11-30` Boundary Purge
We audited 6 clean-room walk-forward configurations in [`q4_walkforward_lgbm_and_reconcile.py`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/q4_walkforward_lgbm_and_reconcile.py):
- **`Mode A1 (HybridRepro + Purged Nov-30)`**: Train `2011-01-31 .. Y-3-11-30`, Validation `Y-2-01-31 .. Y-1-11-30`, Final Refit `2011-01-31 .. Y-1-11-30`.
- **`Mode A2 (HybridRepro + Unpurged Val Dec-31, Purged Refit Nov-30)`**: Matches pre-patch `20d6cbf` where validation included `Y-1-12-31` (`val_end = Y-1-12-31`) while final refit `tr2` stopped at `Y-1-11-30`.
- **`Mode A3 (HybridRepro + Unpurged Val & Refit Dec-31)`**: Counterfactual where both validation and final refit include `Y-1-12-31` (allowing the `Y-1-12-31 -> Y-02-01` open-to-open target return to leak January of test year $Y$ into the refitted trees).
- **`Mode B1 (Pure QQQ + Purged Nov-30)`**: Standalone QQQ features with strict `Y-1-11-30` purging.
- **`Mode B2 (Pure QQQ + Fixed num_leaves=7)`**: Standalone QQQ features with `num_leaves=7` frozen across all years (zero validation tuning).
- **`Mode B3 (Pure QQQ + Zero-CAGR-Peeking Rank Validation)`**: Standalone QQQ features selecting `num_leaves` by mean validation cross-sectional rank (`val_rank`) rather than validation Top-1 return + Sharpe bonus.

#### Fold-by-Fold Chosen `num_leaves` (`step4_fold_hyperparameter_audit.csv`)

| Test Year $Y$ | Train Window | Purged Val Window (`Nov-30`) | `Mode A1` (`Purged Nov-30`) `num_leaves` | `Mode A2` (`Unpurged Val Dec-31`) `num_leaves` | `Mode B1` (`Pure QQQ Purged`) `num_leaves` | `Mode B3` (`Pure QQQ Rank-Val`) `num_leaves` |
|---|---|---|---|---|---|---|
| `2015` | `2011-01..2012-11` | `2013-01..2014-11` | `7` | `7` | `7` | `15` |
| `2016` | `2011-01..2013-11` | `2014-01..2015-11` | `15` | `15` | `7` | `15` |
| `2017` | `2011-01..2014-11` | `2015-01..2016-11` | `15` | `15` | `7` | `7` |
| `2018` | `2011-01..2015-11` | `2016-01..2017-11` | `7` | `7` | `7` | `7` |
| `2019` | `2011-01..2016-11` | `2017-01..2018-11` | `15` | `15` | `7` | `15` |
| `2020` | `2011-01..2017-11` | `2018-01..2019-11` | `15` | `15` | `7` | `15` |
| `2021` | `2011-01..2018-11` | `2019-01..2020-11` | `15` | `15` | `7` | `15` |
| `2022` | `2011-01..2019-11` | `2020-01..2021-11` | `15` | `15` | `7` | `7` |
| `2023` | `2011-01..2020-11` | `2021-01..2022-11` | `15` | `15` | `15` | `7` |
| `2024` | `2011-01..2021-11` | `2022-01..2023-11` | `15` | `15` | `15` | `7` |
| `2025` | `2011-01..2022-11` | `2023-01..2024-11` | `15` | `15` | `7` | `15` |
| `2026` | `2011-01..2023-11` | `2024-01..2025-11` | `7` | `7` | `15` | `15` |

- **Why `Mode A1` and `Mode A2` are 100% Identical (`140/140` months)**:
  - In `run_ml3_qqq_iwm_pools.py` line 690, the final refit dataset `tr2 = D[(D.t >= '2011-01-31') & (D.t <= f'{test_year-1}-11-30')]` **already excluded December** in both `20d6cbf` and `a455ed7`.
  - Removing `Y-1-12-31` from the validation window (`Mode A2 -> Mode A1`) did not flip the discrete choice between `num_leaves=7` and `num_leaves=15` in any of the 12 folds. Because `tr2` was already identical and `best['nl']` did not change, `Mode A1` and `Mode A2` produce the exact same model weights, predictions, and `140/140` picks (`62.31%` / `50.28%`).

### 5.2 Audit Finding: Missing `2015-01` Holding Month in `2015–2026` Window
- In `run_ml3_qqq_iwm_pools.py` line 676, the outer walk-forward loop filtered test observations via `te = D[D.t.dt.year == test_year]` for `test_year in range(2015, 2027)` where `D.t` is the **formation month-end**.
- Consequently, formation month `2014-12-31` (whose holding month is **`2015-01-31`**) was never predicted, so the reported `2015–2026` backtest actually begins in **`2015-02-28`** (`140` holding months instead of `141`).

---

## 6. Step 5 Audit: Independent Performance & Calendar-Year Return Breakdown

Full performance metrics from [`step5_performance_summary_table.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step5_performance_summary_table.csv) and [`step5_calendar_year_returns.csv`](file:///Users/happygolucky/Desktop/宏观观察器/outputs/qqq_lgbm_cleanroom_audit_20261103/step5_calendar_year_returns.csv):

### 6.1 Summary Metrics Across Windows

| Strategy / Clean-Room Mode | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Sortino | `2019–2026.09` Monthly MaxDD | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe | `2015–2018` CAGR | `2022` Return |
|---|---|---|---|---|---|---|---|---|---|
| **Original Reported Ledger (`a455ed7`)** | **`62.31%`** | `0.97` | `2.46` | `-65.51%` | `-66.76%` | **`50.28%`** | `0.92` | `29.93%` | `+12.52%` |
| **`Mode A1: Clean-Room HybridRepro (Nov-30 Purged)`** | **`62.31%`** | `0.97` | `2.46` | `-65.51%` | `-66.76%` | **`50.28%`** | `0.92` | `29.93%` | `+12.52%` |
| **`Mode A2: Clean-Room HybridRepro (Unpurged Val Dec-31)`** | **`62.31%`** | `0.97` | `2.46` | `-65.51%` | `-66.76%` | **`50.28%`** | `0.92` | `29.93%` | `+12.52%` |
| **`Mode A3: Clean-Room HybridRepro (Unpurged Both Dec-31)`** | `48.14%` | `0.85` | `2.18` | `-65.51%` | `-66.85%` | `31.33%` | `0.69` | `4.19%` | `+1.81%` |
| **`Mode B1: Clean-Room Pure Standalone QQQ (Nov-30 Purged)`** | **`48.36%`** | `0.92` | `1.97` | `-43.90%` | `-56.26%` | **`27.16%`** | `0.67` | **`-6.28%`** | `-21.67%` |
| **`Mode B2: Clean-Room Pure QQQ (Fixed num_leaves=7)`** | `49.94%` | `0.94` | `2.04` | `-43.90%` | `-56.26%` | `28.05%` | `0.68` | `-6.28%` | `-21.67%` |
| **`Mode B3: Clean-Room Pure QQQ (Zero-Peek Rank Val)`** | `32.45%` | `0.73` | `1.44` | `-43.90%` | `-56.26%` | `21.25%` | `0.58` | `2.05%` | `-9.99%` |
| **Benchmark: `QQQ Pure 12-1 Momentum Top-1`** | **`43.86%`** | `0.83` | `1.70` | `-42.73%` | `-57.87%` | **`41.43%`** | `0.86` | `36.93%` | `-16.92%` |
| **Benchmark: `QQQ Pure 12-1 Momentum Top-3`** | **`55.49%`** | **`1.13`** | `2.57` | **`-27.71%`** | `-45.48%` | **`40.96%`** | **`0.98`** | `16.40%` | `+0.95%` |
| **Benchmark: `QQQ PIT Equal-Weight Full100`** | `19.63%` | `0.93` | `1.42` | `-29.01%` | `-32.99%` | `16.42%` | `0.86` | `10.55%` | `-24.53%` |
| **Benchmark: `QQQ ETF Buy & Hold`** | `22.40%` | `1.00` | `1.59` | `-32.58%` | `-35.12%` | `18.54%` | `0.92` | `11.49%` | `-32.58%` |
| **Benchmark: `SPY ETF Buy & Hold`** | `16.95%` | `0.92` | `1.42` | `-23.93%` | `-33.72%` | `14.12%` | `0.85` | `8.91%` | `-18.17%` |

### 6.2 Calendar-Year Net Returns (`2015..2026.09`)

| Year | `Mode A1` (`HybridRepro 62.31%`) | `Mode B1` (`Pure QQQ 48.36%`) | `QQQ Pure 12-1 Mom Top-1` | `QQQ Pure 12-1 Mom Top-3` | `QQQ ETF` | `SPY ETF` |
|---|---|---|---|---|---|---|
| `2015` (Feb–Dec) | `+49.70%` | `-3.13%` | `+116.81%` | `+34.72%` | `+11.41%` | `+3.53%` |
| `2016` | `+23.43%` | `-4.15%` | `-2.73%` | `+2.96%` | `+7.10%` | `+12.00%` |
| `2017` | `+62.66%` | `+19.31%` | `+59.35%` | `+39.87%` | `+32.66%` | `+21.71%` |
| `2018` | `-6.97%` | `-31.65%` | `+2.23%` | `-6.37%` | `-0.12%` | `-4.57%` |
| `2019` | `+5.53%` | `+35.22%` | `+20.77%` | `+11.88%` | `+38.96%` | `+31.22%` |
| `2020` | `+342.45%` | `+408.58%` | `+265.17%` | `+238.58%` | `+48.62%` | `+18.33%` |
| `2021` | `+157.88%` | `+69.29%` | `+35.14%` | `+48.72%` | `+27.42%` | `+28.73%` |
| `2022` | `+12.52%` | `-21.67%` | `-16.92%` | `+0.95%` | `-32.58%` | `-18.17%` |
| `2023` | `+39.21%` | `+29.40%` | `+114.23%` | `+114.58%` | `+54.86%` | `+26.18%` |
| `2024` | `+13.38%` | `-4.67%` | `+9.28%` | `+24.64%` | `+25.58%` | `+24.89%` |
| `2025` | `+42.59%` | `+51.14%` | `-22.42%` | `+16.78%` | `+20.79%` | `+17.72%` |
| `2026` (Jan–Sep) | `+97.27%` | `+89.51%` | `+94.28%` | `+74.63%` | `+6.26%` | `+8.23%` |

- **Key Observation**: Notice that in `2019`, `2023`, and `2024`, `Mode A1` **underperformed** passive `QQQ ETF` (`+5.53%` vs `+38.96%` in 2019; `+39.21%` vs `+54.86%` in 2023; `+13.38%` vs `+25.58%` in 2024). Its entire `2019–2026` outperformance comes from 3 explosive bursts: `2020` (`TSLA`/`MRNA`), `2021` (`MRNA`), and `2026` (`SNDK`).

---

## 7. Step 6 Audit: 59-Scenario Adversarial Stress Suite (`step6_adversarial_stress_tests.csv`)

We subjected both `Mode A1 (HybridRepro)` and `Mode B1 (Pure QQQ)` to 59 adversarial perturbations across 8 dimensions:

### 7.1 Cross-Sectional Rank Neighborhood Cliff (`Rank #1` vs `Rank #2..#5` and `Top-N`)

| Portfolio Slice | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Monthly MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe |
|---|---|---|---|---|---|
| **`Mode A1: Rank #1 Alone` (Headline)** | **`62.31%`** | `0.97` | `-65.51%` | **`50.28%`** | `0.92` |
| **`Mode A1: Rank #2 Alone`** | **`9.48%`** | `0.36` | `-50.33%` | **`7.47%`** | `0.32` |
| **`Mode A1: Rank #3 Alone`** | **`18.56%`** | `0.55` | `-53.03%` | **`18.38%`** | `0.56` |
| **`Mode A1: Rank #4 Alone`** | **`4.40%`** | `0.26` | `-69.82%` | **`1.94%`** | `0.20` |
| **`Mode A1: Rank #5 Alone`** | **`-12.65%`** | `-0.13` | `-80.54%` | **`-1.74%`** | `0.11` |
| `Mode A1: Top-2 Equal-Weight (Ranks 1–2)` | `36.32%` | `0.85` | `-49.71%` | `29.10%` | `0.78` |
| `Mode A1: Top-3 Equal-Weight (Ranks 1–3)` | `32.51%` | `0.85` | `-46.46%` | `26.82%` | `0.78` |
| `Mode A1: Top-3 Dedicated Model (val scored on Top-3)` | `36.73%` | `0.90` | `-41.93%` | `31.39%` | `0.84` |
| `Mode A1: Top-5 Equal-Weight (Ranks 1–5)` | `18.38%` | `0.63` | `-48.03%` | `16.92%` | `0.63` |
| **`Mode B1 (Pure QQQ): Rank #1 Alone`** | **`48.36%`** | `0.92` | `-43.90%` | **`27.16%`** | `0.67` |
| **`Mode B1 (Pure QQQ): Rank #2 Alone`** | **`21.05%`** | `0.61` | `-46.79%` | **`20.38%`** | `0.60` |
| **`Mode B1 (Pure QQQ): Rank #3 Alone`** | **`40.66%`** | `0.88` | `-45.80%` | **`31.59%`** | `0.77` |
| `Mode B1 (Pure QQQ): Top-3 Dedicated Model` | `45.03%` | `1.07` | `-32.92%` | `34.10%` | `0.92` |

> [!WARNING]
> **Why the Rank #2 Collapse (`62.31% -> 9.48%`) Is a Red Flag**:
> In `Mode A1`, the second-highest predicted stock in the Nasdaq-100 (`Rank #2`) delivers just **`9.48%` CAGR in `2019–2026`** and **`7.47%` in `2015–2026`** — underperforming passive `QQQ ETF` (`22.40%` / `18.54%`) by more than `-11%/yr`, while `Rank #5` loses money (`-12.65%` CAGR). This proves the LightGBM regression score is **not** learning a monotonic cross-sectional expected-return ranking; `62.31%` relies heavily on a handful of lucky right-tail hits landing specifically in slot #1.

### 7.2 Random Seed Sensitivity (`10` Random Seeds with `subsample=0.8, colsample_bytree=0.8`)
Because the frozen spec uses stochastic row/column subsampling (`subsample=0.8, subsample_freq=1, colsample_bytree=0.8`), changing **only** `random_state` causes massive variance in which stock lands at Rank #1:

| Random Seed (`Mode A1`) | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2015–2026.09` CAGR | `2015–2026.09` Sharpe |
|---|---|---|---|---|
| `seed = 100` (Worst Seed) | **`40.05%`** | `0.80` | **`27.24%`** | `0.66` |
| `seed = 77` | `49.90%` | `0.94` | `37.46%` | `0.82` |
| `seed = 2026` | `54.51%` | `0.93` | `42.26%` | `0.84` |
| `seed = 1` | `57.99%` | `0.94` | `43.52%` | `0.85` |
| `seed = 999` | `61.26%` | `1.01` | `46.23%` | `0.90` |
| **`seed = 7` (Reported Baseline)** | **`62.31%`** | `0.97` | **`50.28%`** | `0.92` |
| `seed = 42` | `64.08%` | `0.98` | `47.34%` | `0.88` |
| `seed = 13` | `72.73%` | `1.12` | `49.70%` | `0.94` |
| `seed = 21` | `72.90%` | `1.06` | `54.73%` | `0.97` |
| `seed = 256` (Best Seed) | **`102.32%`** | `1.26` | **`62.31%`** | `1.05` |
| **10-Seed Summary (`Min / Median / Max`)** | **`40.05% / 61.78% / 102.32%`** | `0.80 / 0.98 / 1.26` | **`27.24% / 46.78% / 62.31%`** | `0.66 / 0.89 / 1.05` |

### 7.3 Transaction Costs, Open Slippage, Execution Delay & Hyperparameter Freezing

| Stress Category | Scenario | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Monthly MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe |
|---|---|---|---|---|---|
| **Transaction Cost (`Mode A1`)** | `20 bps/side` (`40 bps` RT) | `59.13%` | `0.94` | `-66.05%` | `47.30%` | `0.89` |
| | `30 bps/side` (`60 bps` RT) | `55.99%` | `0.92` | `-66.58%` | `44.38%` | `0.86` |
| | `50 bps/side` (`100 bps` RT) | `49.90%` | `0.87` | `-67.62%` | `38.68%` | `0.80` |
| **Open Slippage (`Mode A1`)** | `+15 bps/side` (`25 bps/side` total) | `57.56%` | `0.93` | `-66.32%` | `45.84%` | `0.88` |
| | `+25 bps/side` (`35 bps/side` total) | `54.45%` | `0.90` | `-66.84%` | `42.94%` | `0.85` |
| | `+50 bps/side` (`60 bps/side` total) | `46.93%` | `0.84` | `-68.13%` | `35.91%` | `0.77` |
| **Open Slippage (`Mode B1 Pure QQQ`)** | `+15 bps/side` (`25 bps/side` total) | `43.69%` | `0.87` | `-44.32%` | `23.16%` | `0.61` |
| | `+25 bps/side` (`35 bps/side` total) | `40.64%` | `0.84` | `-44.59%` | `20.55%` | `0.57` |
| | `+50 bps/side` (`60 bps/side` total) | `33.29%` | `0.75` | `-46.88%` | `14.26%` | `0.47` |
| **Execution Timing Lag** | `Mode A1: T+0 Month-End Close-to-Close` | `66.15%` | `0.96` | `-65.72%` | `51.83%` | `0.91` |
| | **`Mode A1: T+1 First-Day Close-to-Close`** | **`49.25%`** | `0.85` | `-69.65%` | **`44.27%`** | `0.84` |
| | `Mode B1: T+0 Month-End Close-to-Close` | `50.60%` | `0.90` | `-45.01%` | `24.13%` | `0.62` |
| | **`Mode B1: T+1 First-Day Close-to-Close`** | **`32.45%`** | `0.71` | `-47.82%` | **`18.48%`** | `0.53` |
| **Hyperparameter Freezing** | `Mode A1: Fixed num_leaves=7 (No Val Tuning)` | **`44.52%`** | `0.83` | `-59.35%` | **`37.11%`** | `0.79` |
| | `Mode A1: Fixed num_leaves=15 (No Val Tuning)` | `66.17%` | `1.00` | `-65.51%` | `53.20%` | `0.94` |
| | `Mode A1: Zero-CAGR-Peek Rank Validation` | **`48.28%`** | `0.87` | `-65.51%` | **`39.47%`** | `0.81` |
| **Feature Ablation (`Pure QQQ`)** | `Pure QQQ + Drop sector_mom (17 features)` | `62.50%` | `1.07` | `-35.70%` | `41.73%` | `0.88` |
| | **`Pure QQQ + Drop dv_ratio (17 features)`** | **`20.01%`** | `0.56` | `-53.97%` | **`15.54%`** | `0.49` |
| **Combined Worst Reasonable Stress** | **`Pure QQQ + Fixed NL7 + Nov-30 Purge + 25bp/side`** | **`43.85%`** | `0.85` | `-43.90%` (`-56.44%` daily) | **`25.65%`** | `0.65` |
| | **`HybridRepro + Fixed NL7 + Nov-30 Purge + 25bp/side`** | **`40.06%`** | `0.78` | `-60.53%` | **`32.99%`** | `0.74` |

### 7.4 Super-Winner & Best-Month Removal Stress (`step6_adversarial_stress_tests.csv`)

| Exclusion / Jackknife Test (`Mode A1`) | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2015–2026.09` CAGR | `2015–2026.09` Sharpe |
|---|---|---|---|---|
| **Baseline (`Mode A1`, no exclusions)** | **`62.31%`** | `0.97` | **`50.28%`** | `0.92` |
| Ban `NVDA` (`substitute Rank #2 when picked`) | `55.62%` | `0.92` | `43.23%` | `0.86` |
| Ban `TSLA` (`substitute Rank #2 when picked`) | `53.17%` | `0.91` | `44.62%` | `0.88` |
| Ban `MRNA` (`substitute Rank #2 when picked`) | **`42.20%`** | `0.84` | **`37.82%`** | `0.83` |
| Ban `PDD` (`substitute Rank #2 when picked`) | `53.26%` | `0.90` | `44.71%` | `0.87` |
| Ban `SNDK` (`substitute Rank #2 when picked`) | `53.26%` | `0.93` | `44.71%` | `0.89` |
| **Ban Top-6 Super-Winners (`SNDK, MRNA, TSLA, NVDA, PDD, PLTR`)** | **`17.70%`** | `0.56` | **`25.99%`** | `0.72` |
| **Remove Top 1 Best Month (`replace with 0%`)** | `50.90%` | `0.91` | `43.18%` | `0.87` |
| **Remove Top 3 Best Months (`replace with 0%`)** | `33.24%` | `0.77` | `31.69%` | `0.78` |
| **Remove Top 5 Best Months (`replace with 0%`)** | **`21.54%`** | `0.62` | **`23.09%`** | `0.69` |
| **Remove Top 10 Best Months (`replace with 0%`)** | **`-4.28%`** | `0.06` | **`0.46%`** | `0.21` |

---

## 8. Steps 7 & 8 Audit: Paired Statistical Significance & Multiple-Testing Penalty

### 8.1 Paired Newey-West HAC, Stationary Block Bootstrap & Wilcoxon Tests (`step7_paired_statistical_tests.csv`)

| Strategy A | Benchmark B | Window | $N$ | CAGR A | CAGR B | $\Delta\text{CAGR}$ | NW $t$ (`lag=3`) | NW $p$ (`lag=3`) | NW $t$ (`lag=6`) | Wilcoxon $p$ | Bootstrap 90% CI ($\Delta\text{CAGR}$) | $\Pr(\Delta \le 0)$ | Monthly Win% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **`Mode A1 (62.31%)`** | **`QQQ Pure 12-1 Mom Top-1`** | `2019–2026` | `93` | `62.31%` | `43.86%` | `+18.46%` | **`0.49`** | **`0.6217`** | `0.64` | `0.8157` | `[-43.41%, +81.58%]` | `30.58%` | **`39.8%` (`37/93`)** |
| **`Mode A1 (50.28%)`** | **`QQQ Pure 12-1 Mom Top-1`** | `2015–2026` | `140` | `50.28%` | `41.43%` | `+8.85%` | **`0.26`** | **`0.7955`** | `0.33` | `0.7626` | `[-36.31%, +51.56%]` | `37.08%` | **`42.1%` (`59/140`)** |
| **`Mode B1 Pure QQQ`** | **`QQQ Pure 12-1 Mom Top-1`** | `2019–2026` | `93` | `48.36%` | `43.86%` | `+4.50%` | **`-0.16`** | **`0.8704`** | `-0.19` | `0.4832` | `[-57.54%, +61.36%]` | `43.35%` | **`39.8%` (`37/93`)** |
| **`Mode B1 Pure QQQ`** | **`QQQ Pure 12-1 Mom Top-1`** | `2015–2026` | `140` | `27.16%` | `41.43%` | **`-14.27%`** | **`-0.99`** | `0.3239` | `-1.10` | `0.1563` | `[-58.47%, +20.23%]` | `78.50%` | **`38.6%` (`54/140`)** |
| **`Mode A1 (62.31%)`** | **`QQQ Pure 12-1 Mom Top-3`** | `2019–2026` | `93` | `62.31%` | `55.49%` | `+6.82%` | **`0.55`** | **`0.5790`** | `0.78` | `0.7313` | `[-39.89%, +57.16%]` | `39.77%` | `47.3%` (`44/93`) |
| **`Mode B1 Pure QQQ`** | **`QQQ Pure 12-1 Mom Top-3`** | `2019–2026` | `93` | `48.36%` | `55.49%` | **`-7.13%`** | **`-0.17`** | `0.8617` | `-0.22` | `0.4090` | `[-54.44%, +35.09%]` | `60.22%` | `43.0%` (`40/93`) |
| **`Mode A1 Top-3 (36.73%)`** | **`QQQ Pure 12-1 Mom Top-3`** | `2019–2026` | `93` | `36.73%` | `55.49%` | **`-18.76%`** | `-1.18` | `0.2389` | `-1.54` | `0.4834` | `[-50.56%, +6.03%]` | `86.78%` | `48.4%` (`45/93`) |
| **`Mode A1 (62.31%)`** | `QQQ ETF Buy & Hold` | `2019–2026` | `93` | `62.31%` | `22.40%` | `+39.92%` | `1.98` | `0.0480` | `2.65` | `0.3199` | `[+2.74%, +84.22%]` | `3.50%` | `53.8%` (`50/93`) |
| **`Mode A1 (50.28%)`** | `QQQ ETF Buy & Hold` | `2015–2026` | `140` | `50.28%` | `18.54%` | `+31.74%` | `2.24` | `0.0251` | `2.86` | `0.2190` | `[+4.59%, +62.71%]` | `2.67%` | `55.0%` (`77/140`) |
| **`Mode B1 Pure QQQ`** | `QQQ ETF Buy & Hold` | `2019–2026` | `93` | `48.36%` | `22.40%` | `+25.96%` | `1.50` | `0.1328` | `1.88` | `0.8757` | `[-9.29%, +66.52%]` | `11.15%` | `50.5%` (`47/93`) |
| **`Mode B1 Pure QQQ`** | `QQQ ETF Buy & Hold` | `2015–2026` | `140` | `27.16%` | `18.54%` | `+8.62%` | `1.07` | `0.2864` | `1.36` | `0.6251` | `[-12.23%, +30.99%]` | `22.88%` | `49.3%` (`69/140`) |

### 8.2 Multiple-Testing & Data-Mining Adjustments (`step8_multiple_testing_audit.csv`)
Across the project repository, **`56` strategies** were tested in the QQQ/IWM ML3 sweep (`run_ml3_qqq_iwm_pools.py`), **`256` strategies** across all ML3 feature-discovery runs (`200` S&P 500 + `56` QQQ/IWM), and **`391` strategies** across all research folders (`sector_stock_momentum`, `ml_Return_Predictability`, `ml2_Trajectory_Model`, `multibagger_layered_momentum`, `ml3_feature_discovery`).

| Strategy | Window | Raw Sharpe | Expected Max Null Sharpe ($K=391$, $N_{\text{eff}}=95$) | **Deflated Sharpe Ratio (`DSR`, $K=391$)** | Raw NW $t$ vs `QQQ ETF` | **Bonferroni $p$ ($K=56$)** | **Šidák $p$ ($K=56$)** | **Passes HLZ ($t > 3.0$)?** |
|---|---|---|---|---|---|---|---|---|
| `Mode A1 (HybridRepro 62.31%)` | `2019–2026` | `0.97` | `0.89` | **`0.6821`** (`< 0.95` FAIL) | `1.98` ($p=0.0480$) | **`1.0000`** | `0.9365` | **NO (`1.98 < 3.0`)** |
| `Mode A1 (HybridRepro 50.28%)` | `2015–2026` | `0.92` | `0.83` | **`0.7064`** (`< 0.95` FAIL) | `2.24` ($p=0.0251$) | **`1.0000`** | `0.7591` | **NO (`2.24 < 3.0`)** |
| `Mode B1 (Pure QQQ 48.36%)` | `2019–2026` | `0.92` | `0.89` | **`0.6332`** (`< 0.95` FAIL) | `1.50` ($p=0.1328$) | **`1.0000`** | `0.9997` | **NO (`1.50 < 3.0`)** |
| `Mode B1 (Pure QQQ 27.16%)` | `2015–2026` | `0.67` | `0.83` | **`0.3476`** (`< 0.95` FAIL) | `1.07` ($p=0.2864$) | **`1.0000`** | `1.0000` | **NO (`1.07 < 3.0`)** |
| `QQQ Pure 12-1 Mom Top-3 (55.49%)` | `2019–2026` | `1.13` | `0.89` | **`0.8690`** | `2.65` ($p=0.0080$) | `0.4494` | `0.3627` | **NO (`2.65 < 3.0`)** |

---

## 9. Step 9 Audit: Return Concentration & Super-Winner Forensics (`step9_concentration_audit.csv`)

### 9.1 Top Contributors to Cumulative Log Wealth (`2019–2026.09`, Total Log Wealth = `3.7534` $\approx 42.67\times$)

| Rank | Ticker | Months Held (`2019–2026`) | Cumulative Log Return | **Share of Total 2019–2026 Log Wealth** | Best Single Holding Month | Audit Notes |
|---|---|---|---|---|---|---|
| **1** | **`SNDK`** | `3` (`2026-01, 2026-06, 2026-08`) | `+0.8914` | **`23.75%`** (`23.75%` cum) | `2026-01`: **`+63.27%`** | Listed in `starting_2026` of `n100-ticker-changes-2026.yaml`; only 11m post-spinoff history on `2026-01-31` |
| **2** | **`TSLA`** | `6` (`2020-02..03, 2020-07..08, 2020-12, 2021-11`) | `+0.8655` | **`23.06%`** (`46.81%` cum) | `2020-08`: **`+51.31%`** | Genuine Nasdaq-100 member since July 2013 |
| **3** | **`MRNA`** | `9` (`2020-11, 2021-01..02, 2021-05..09, 2021-12`) | `+0.5624` | **`14.98%`** (`61.79%` cum) | `2021-07`: **`+61.42%`** | Added to NDX `2020-07-20`; non-S&P 500 until `2021-07-21` (`in_sp=False` during early run) |
| **4** | **`PDD`** | `2` (`2020-10, 2022-11`) | `+0.4400` | **`11.72%`** (`73.51%` cum) | `2022-11`: **`+55.02%`** | Added to NDX `2020-08-24`; never in S&P 500 (`in_sp=False`) |
| **5** | **`CRWD`** | `1` (`2022-03`) | `+0.2143` | **`5.71%`** (`79.22%` cum) | `2022-03`: **`+23.90%`** | Genuine NDX member |
| **6** | **`REGN`** | `2` (`2020-04, 2022-09`) | `+0.2116` | **`5.64%`** (`84.86%` cum) | `2022-09`: **`+18.43%`** | Genuine NDX member |
| **7** | **`SPLK`** | `1` (`2020-05`) | `+0.2072` | **`5.52%`** (`90.38%` cum) | `2020-05`: **`+23.02%`** | Genuine NDX member |
| **8** | **`SIRI`** | `1` (`2023-07`) | `+0.2063` | **`5.50%`** (`95.88%` cum) | `2023-07`: **`+22.91%`** | July 2023 short-squeeze month |
| **9** | **`ZS`** | `2` (`2021-10, 2023-05`) | `+0.2059` | **`5.49%`** (`101.36%` cum) | `2023-05`: **`+35.09%`** | Genuine NDX member |
| **10** | **`NVDA`** | `8` (`2019-11..12, 2020-06, 2023-02, 2023-06, 2024-02..03, 2024-06`) | `+0.1753` | **`4.67%`** (`106.03%` cum) | `2024-02`: **`+31.83%`** | Genuine NDX member |

- **Summary of Concentration**:
  - **Top 4 stocks (`SNDK`, `TSLA`, `MRNA`, `PDD`) = `73.51%` of total 2019–2026 log wealth** across just `20` holding months (`21.5%` of the sample).
  - **Top 9 stocks = `101.36%` of total 2019–2026 log wealth**; the remaining **34 stocks held across 65 holding months contributed `-1.36%` net cumulative log return**.

---

## 10. Final Audit Summary & Credibility Score Breakdown

| Audit Dimension | Weight | Score | Justification |
|---|---|---|---|
| **1. Ledger Arithmetic & Execution Timing (`Open-to-Open` + `10 bps`)** | `20` | `19 / 20` | `140/140` holding months match to `0.0000 bps`; `Open[t+1, d1] -> Open[t+2, d1]` and `10 bps/side` verified; `-1` pt for missing `2015-01` holding month due to formation-year filter. |
| **2. Price Integrity & Second-Source Tiingo Verification** | `15` | `13 / 15` | `>30d` segment breaks & alias splits prevent `SNDK__OLD`/`SNDK` splicing; median Tiingo `adjOpen` diff `0.00 bps`; `3` historical delisting/missing-open months used next-day Close fallback (`STRZA`, `ENDP`, `CELG`). |
| **3. Feature Truncation Invariance & Temporal Walk-Forward Hygiene** | `15` | `14 / 15` | Physical price-truncation test passed `5/5` (`0.0` diff); final refit `tr2` strictly purged at `Y-1-11-30`. |
| **4. Standalone Universe & Feature Purity** | `20` | `4 / 20` | **Severe failure**: `run_ml3_qqq_iwm_pools.py` spliced S&P 500 `sector_mom` and `raw_volume`-only `dv_ratio` for `in_sp=True` stocks with S&P$\cup$NDX `sector_mom` and `raw_volume+raw_ndx` `dv_ratio` for `in_sp=False` stocks, and included 11-month-old `SNDK` in 2026 QQQ. Fixing feature splicing drops CAGR to `48.36%` (`2019–2026`) and `27.16%` (`2015–2026`). |
| **5. Cross-Sectional Robustness, Seed Stability & Stress Survival** | `15` | `2 / 15` | `Rank #2` collapses to `9.48%` (`2019–2026`) / `7.47%` (`2015–2026`); random seed swings CAGR from `40.05%` to `102.32%`; removing 6 winners drops CAGR to `17.70%`. |
| **6. Statistical Significance vs Simple Momentum & Multiple Testing** | `15` | `2 / 15` | NW $t = 0.49$ ($p = 0.62$) vs `QQQ Pure 12-1 Mom Top-1` (`Mode B1` $t = -0.16$, `-14.27%/yr` in `2015–2026`); monthly win rate `39.8%`; fails `DSR` (`0.68 < 0.95`), Bonferroni (`p = 1.00`), and HLZ (`t = 1.98 < 3.0`). |
| **TOTAL CREDIBILITY SCORE** | **`100`** | **`54 / 100`** | **Arithmetic reproduction: PASS (`62.31%` / `50.28%`). Standalone ML alpha & live-trading readiness: FAIL.** |
