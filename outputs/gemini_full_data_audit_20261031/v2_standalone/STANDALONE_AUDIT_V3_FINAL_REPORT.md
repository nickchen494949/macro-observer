# Clean-Room Standalone Full-Repository Data & Backtest Audit — Final Sign-Off Edition (`v3`)

- **Audit Suite Location**: `outputs/gemini_full_data_audit_20261031/v2_standalone/`
- **Mechanical Clean-Room Isolation**: **`0` imports of any audited project module**, **`0` reads of ledger cost/cash columns (`turnover`, `capital_after_costs`, `cash_return`)**, and **`0` reads of project-generated monthly RF CSVs** across all **7** Python scripts — mechanically enforced via Python `ast.parse` and source scanning in [`v2_00_cleanroom_ast_and_readonly_guard.py`](v2_00_cleanroom_ast_and_readonly_guard.py) → [`v2_00_cleanroom_guard_report.json`](v2_00_cleanroom_guard_report.json) (`scripts_checked = 7`, `total_ast_or_pattern_violations = 0`).
- **Read-Only Protected Baseline**: **`10,964 / 10,964` protected repository files untouched** (`changed = 0`, `missing = 0`, `added = 0`, verified pre-flight and post-flight by SHA-256 fingerprint check).
- **End-to-End Full-Chain PIT Strategy Reconstruction (`v2_05`)**: **`10` core headline strategy ledgers** reconstructed from raw membership CSVs + raw price/open/volume JSONs + 142 raw SEC FSDS `sub_*.parquet` / `num_*.parquet` + `earnings_dates.csv` + raw `data/fred/DGS3MO.json` (`0` reads of `panel_ml2.parquet` or `eps_quarterly_pit.parquet` during reconstruction) → [`v2_05_full_chain_pit_reconstruction_summary.json`](v2_05_full_chain_pit_reconstruction_summary.json), [`v2_05_full_chain_picks_comparison.csv`](v2_05_full_chain_picks_comparison.csv).
- **Random Spot-Check Sample Size (`400` Fixed-Seed Audit Cards Total)**:
  - **`300` Master Disjoint-Tier Random Audit Cards** ([`v2_300_master_random_cards.md`](v2_300_master_random_cards.md) / [`v2_300_master_summary.json`](v2_300_master_summary.json)): `120` unrestricted two-stage draws across all `347` ledgers (`pre_filtered_exclusions = 0`) + `100` SEC raw XBRL non-null numeric facts (`100/100` live `data.sec.gov`) + `40` strict full-accession SEC Form 13F `100%` sorted multiset comparisons (`18,099` holding tuples) + `40` Macro/ALFRED/coordinate-parsed FOMC SEP PDF/S&P DJI `.xlsx`/Valuation/ETF cards.
  - **`100` SEC Fundamental `NULL` / Missing Completeness Random Audit Cards (`N001..N100`)** ([`v2_04_sec_xbrl_100_null_cards.md`](v2_04_sec_xbrl_100_null_cards.md) / [`v2_04_sec_xbrl_100_null_summary.json`](v2_04_sec_xbrl_100_null_summary.json)): auditing missingness/completeness bias across all 142 raw SEC FSDS parquets + live `data.sec.gov` (`100/100` live-confirmed) with Horvitz-Thompson population-weighted root-cause shares.

---

## 1. Plain-Language Final Sign-Off Verdict

1. **What Is 100% Verified End-to-End From Raw Primary Inputs (`PASS`)**:
   - **All 8 Core S&P 500 Pure-Momentum & Sector-Momentum (`SPEC`) Headline Ledgers (`2009–2026` Close-to-Close & `2015–2026` Open-to-Open)**: Reconstructed **100% end-to-end** in [`v2_05_full_chain_pit_strategy_reconstructor.py`](v2_05_full_chain_pit_strategy_reconstructor.py) from raw membership intervals, raw ticker/CIK aliases (`41/41` exact), raw GICS historical sector mappings, raw prices/opens, and first-principles self-financing/additive transaction costs. **Every single monthly pick (`213/213` and `141/141`), top GICS sector (`213/213`), eligible member count (`213/213`), gross return, and net return matches to machine precision (`max |net_diff| <= 2.22e-16`)**:
     - `Pure Momentum Top1 (Close-to-Close, 2009–2026, 213m)`: **`36.59%` net CAGR** (`36.594%` additive / `36.585%` self-financing; **`135 / 135 = 100.0%`** picks confirmed inside official BlackRock `IVV` institutional monthly holdings snapshots `2014-12..2026-08`).
     - `SPEC Top Sector -> Top 1 Stock (Close-to-Close, 2009–2026, 213m)`: **`27.37%` / `27.36%` net CAGR** (**`135 / 135 = 100.0%`** picks confirmed inside official BlackRock `IVV` snapshots).
     - `Pure Momentum Top1 (Open-to-Open, 2015–2026, 141m)`: **`41.97%` net CAGR** (**`135 / 135 = 100.0%`** picks confirmed in official BlackRock `IVV`).
     - `Pure Momentum Top3 (Open-to-Open, 2015–2026, 141m — ML2 Bench / Skip-Latest / QQQ Rebalance)`: **`27.33%` net CAGR** (**`404 / 405 = 99.75%`** stock-months confirmed in official BlackRock `IVV`; sole unmatched ticker is `2018-05-31 CPRI`, held by BlackRock under its pre-2019 ticker `KORS`).
   - **Smart Money SEC Form 13F Full Database (`13f_full_4409f14.db`, `397,833` filings / `120.18M` rows)**: **`40 / 40` (`100.0%`)** randomly drawn accessions match the official SEC `.zip` `INFOTABLE.tsv` via **100% full-accession sorted multiset equality** (`raw_multiset == db_multiset` across all `18,099` holding tuples on `(cusip, raw_value, value_usd, shares, put_call)`).
   - **SEC Raw XBRL As-First-Reported Fundamentals & 57-Feature Panel Math**: Rebuilding all 57 `ML2` features from 142 raw SEC FSDS `sub_*.parquet` / `num_*.parquet` files reproduces **`94,010 / 94,010` universe rows**, **`0` NaN mismatches across `5,358,570` feature cells**, and **`max_abs_diff = 2.075e-14`**. Across `100` random non-null XBRL cards (`v2_02`), **`100 / 100`** accessions match live `data.sec.gov` (`98 PASS_EXTERNAL_PRIMARY`, `2` conservative `q4_derived` warnings, `0 FAIL`). Across `100` random `NULL` cells (`v2_04`), **`65.40%`** (Horvitz-Thompson population-weighted) are genuinely absent in SEC XBRL, **`32.24%`** report an alternative sector-specific US-GAAP tag omitted by the parser's tag list, and **`2.36%`** are conservatively blanked when no unambiguous 3-month USD quarter can be formed.

2. **Major New Audit Breakthrough Caught by `v3` Full-Chain Reconstruction & First-Principles Costing (Not Caught in `v1` or `v2`)**:
   - **Finding E — `Codex v2` `ML2` Off-by-One `<` WIKI Open Cutoff (`CAM` `2016-04-01`) + Remaining `adjclose` Future-Dividend Valuation Sensitivity (`C-lgbm Top1: 33.39% -> 16.33% / 23.51%`)**:
     1. *Why return-only ledger checks (`v2_01`) couldn't see it on `C-lgbm`*: `Codex v2` (`backtest.py:222` + `ml2_run.py:89`) used strict `<` (`wiki<2016-04-01|yahoo`) instead of `<=` when slicing WIKI adjusted opens, wiping `CAM`'s final valid pre-acquisition open `O['2016-04-01', 'CAM'] = 66.18` to `NaN`. Return-only auditing (`v2_01`) caught the **`200.1 bp` holding-return error** on the **5 `Codex v2` Ridge ledgers** that *bought* `CAM` on `2016-03-31`, whereas `C-lgbm Top1` and `Top3` never held `CAM` on `2016-03-31`.
     2. *What full-chain reconstruction (`v2_05`) uncovered*: `CAM` WAS inside `ML2`'s Top-50 momentum training pool on **both `2016-02-29` (`mom_rank = 9`, exit open `d1 = 2016-04-01`) and `2016-03-31` (`mom_rank = 10`, entry open `d0 = 2016-04-01`)**! Wiping `O['2016-04-01', 'CAM']` corrupted `CAM`'s open-to-open training labels `ret_oo` on those **2 training rows** (`+200.081 bp` on `2016-02-29`, `-25.688 bp` on `2016-03-31`).
        - Emulating **only** that 1-day `<` bug in `v2_05` reproduces `Codex v2`'s stored `monthly_C_lgbm_Top1.csv` (**`33.39%`**, `141/141` picks, `12/12` annual `chosen_params`, `max_net_diff = 1.67e-16`) and `monthly_C_lgbm_Top3.csv` (**`17.86%`**, `141/141` picks, `12/12` annual `chosen_params`, `max_net_diff = 2.22e-16`) bit-for-bit.
        - **Fixing just that 1-day `<` vs `<=` bug (`2` training rows out of `9,450`)** shifts `LGBMRegressor` tree splits and `[Y-2, Y-1]` `num_leaves` selection from 2017 onward, **dropping `C-lgbm Top1` net CAGR from `33.39%` to `16.33%` (`-17.06 pp`, `104/141` picks)** and moving `C-lgbm Top3` from **`17.86%` to `18.69%` (`+0.83 pp`, `68/141` exact 3-stock sets)**!
     3. *100% Dividend-Free Unadjusted-Price × Split-Only Valuation Sensitivity (`Step 5` of `v2_05`)*: In `Codex v2` `ml_features.py` (`lines 21–22 & 220–226`), the 6 valuation features (`ep`, `deps_p`, `log_mcap`, `sp`, `bm`, `cfo_yield`) still divide split-adjusted fundamentals by `adjclose[t]` (which carries backward future cash-dividend adjustments after `t`). Replacing `adjclose[t]` with **100% PIT dividend-free `raw_close[t] / split_factor_after(t)`** (under bug-free `<=` opens) yields **`23.51%` net CAGR on `C-lgbm Top1`** (`-9.88 pp` vs stored `33.39%`, `+7.18 pp` vs bug-free `<=` `16.33%`) and **`14.08%` net CAGR on `C-lgbm Top3`** (`-3.78 pp` vs stored `17.86%`, `-4.61 pp` vs bug-free `<=` `18.69%`). Under **every** clean-room specification, `ML2 C-lgbm` remains far below **Pure Momentum (`41.97%` Top1 / `27.33%` Top3)** and exhibits extreme Top-1 tree-split fragility.
   - **Finding C — Complete 74-Row Official Fed FOMC SEP Coordinate Table 1 Census (`v2_03`)**: Coordinate-based cell parsing (`(x0, y0)` Table 1 `Median × target_year` intersection for **both** `Core PCE inflation` and `Federal funds rate`) across all `74` rows of `data/sep_revisions.json` proves: **`31` pre-`2015-09` rows** had no `Median` column in official Fed Table 1; **`11` rows in `2015-09..2018-12`** contain cell-extraction errors (pulling headline PCE, an adjacent year column, or `1.4` Fed funds rate into `pce`); and **`32 / 43` post-`2015-09` rows** match official Fed Table 1 on both cells to `0.0000` (including **`29 / 29 = 100.0%` from `2019-03` through `2026-06`**).

---

## 2. Point-by-Point Verification of All 6 Final Sign-Off Upgrades

| # | External Auditor Requirement for Final Sign-Off | Mechanical Implementation in `v2_standalone/` | Executed Verification Proof |
|---|---|---|---|
| **1** | **Zero reads of ledger `turnover`, `capital_after_costs`, `cash_return`, or `rf_monthly.csv`** (`100%` first-principles costs & cash carry) | `FORBIDDEN_LEDGER_COST_PATTERNS` in [`v2_00_cleanroom_ast_and_readonly_guard.py`](v2_00_cleanroom_ast_and_readonly_guard.py) bans all literal/subscript/`.get()` access to `turnover`, `capital_after_costs`, `cash_return`, and `rf_monthly.csv`. [`v2_cleanroom_lib.py`](v2_cleanroom_lib.py) (`simulate_cleanroom_ledger_rows`) reconstructs drifted pre-trade weights `w_prev`, quarterly non-rebalance drift, 6-sleeve overlapping `hold6m` tranche accounting, self-financing bisection, additive `turn × 10bp`, and monthly cash carry directly from raw `data/fred/DGS3MO.json`. | [`v2_00_cleanroom_guard_report.json`](v2_00_cleanroom_guard_report.json): `scripts_checked = 7`, `violations = 0`. Caught **5 `Codex v2` Ridge `CAM` `200.1 bp` ledgers** + **8 Claude pre-fix `NDX` `20bp`/regime ledgers** + **6 Claude pre-fix `ML2` ledgers** + **1 `next_day_close` ledger** (`20` failed ledgers total in `v2_01`). |
| **2** | **End-to-end clean-room PIT signal, feature, model & pick reconstruction (`0` project imports, `0` project parquet reads)** + honest scope labels on all `347` ledgers | [`v2_05_full_chain_pit_strategy_reconstructor.py`](v2_05_full_chain_pit_strategy_reconstructor.py) rebuilds aliases (`41/41`), SEC CIK map (`842/842`), PIT S&P 500 membership, historical GICS sectors, all `57` SEC XBRL/price/volume/8-K features (`94,010 × 57`), purged annual walk-forward `LGBMRegressor`, picks, BlackRock `IVV` cross-checks, and dividend-free split-only valuation sensitivity across **10 core headline ledgers**. `v2_01` assigns **9 explicit scope labels** across all `347` ledgers (`211` `RETURN_AND_FIRST_PRINCIPLES_COST_VERIFIED_ONLY` never overstated as full-chain). | **`8 / 8` Pure Momentum & SPEC headline ledgers `PASS` (`213/213` and `141/141` picks, `max_net_diff <= 2.22e-16`)**; **`2 / 2` `Codex v2` `C-lgbm` ledgers flagged for `CAM` `<` training cascade (`33.39% -> 16.33%` Top1) AND `141/141` bit-for-bit reproduced (`<= 2.22e-16`) under `<` emulation**. |
| **3** | **SEC Form 13F full-accession 100% sorted multiset equality** (no `set()` deduplication of identical-CUSIP multi-manager rows) | `run_part_c_40_strict_13f_cards` in [`v2_03_twostage_unrestricted_200_cards_auditor.py`](v2_03_twostage_unrestricted_200_cards_auditor.py) compares `sorted(raw_rows) == sorted(db_rows)` across **100% of rows** in each filing on `(cusip, raw_value, value_usd, shares, put_call)`. | [`v2_300_master_summary.json`](v2_300_master_summary.json): **`40 / 40` filings `PASS_EXTERNAL_PRIMARY`** (`18,099` total holding tuples `100%` multiset-equal across `28` SEC `.zip` archives). |
| **4** | **Downgrade FRED `ALFRED_initial = None` observations out of `PASS_EXTERNAL_PRIMARY`** | When `ALFRED` returns no initial-release vintage (`alf_first is None`) while live latest `api.stlouisfed.org` matches `0.00e+00`, `v2_03` assigns the distinct tier **`PASS_EXTERNAL_LATEST_ONLY`** (`5` cards), reserving `PASS_EXTERNAL_PRIMARY` strictly for ALFRED-confirmed unrevised real-time observations. | [`v2_300_master_summary.json`](v2_300_master_summary.json): `PASS_EXTERNAL_LATEST_ONLY = 5` (strictly separated from `PASS_EXTERNAL_PRIMARY = 199`). |
| **5** | **Coordinate-based Table 1 `(row × column)` cell parser for official Fed FOMC SEP PDFs** (`Core PCE` + `Fed funds rate` at `Median × target_year`) | `extract_fomc_sep_table1_medians` in [`v2_cleanroom_lib.py`](v2_cleanroom_lib.py) extracts PyMuPDF `(x0, y0)` word coordinates on official Table 1 pages, locates the `Median` header span and `target_year` column x-center, and parses **both** `Core PCE inflation` and `Federal funds rate` across all `74` rows of `data/sep_revisions.json`. | Complete 74-row census: `31` pre-`2015-09` no official Median, **`11` `2015-09..2018-12` extraction mismatches caught**, **`32` exact 2-cell matches** (including **`29 / 29 = 100.0%`** from `2019-03..2026-06`). |
| **6** | **100 Random `NULL` / Missing SEC Fundamental Completeness Cards (`N001..N100`)** | [`v2_04_sec_xbrl_100_null_completeness_auditor.py`](v2_04_sec_xbrl_100_null_completeness_auditor.py) draws `100` stratified random `NULL` cells (`sp500` `50`, `ndx` `15`, `smallcap` `35`), scans all 142 raw SEC FSDS parquets unfiltered plus live `data.sec.gov` (`100/100`), classifies every `NULL`, and computes Horvitz-Thompson population-weighted shares + a store-wide zero-row CIK census. | [`v2_04_sec_xbrl_100_null_summary.json`](v2_04_sec_xbrl_100_null_summary.json): Raw `38` True Absent / `54` Alternative Tag / `8` Conservative Blank; Population-weighted **`65.40%` True Absent / `32.24%` Alternative Tag / `2.36%` Conservative Blank**. |

---

## 3. End-to-End Clean-Room PIT Strategy Reconstruction Results (`v2_05`)

Script: [`v2_05_full_chain_pit_strategy_reconstructor.py`](v2_05_full_chain_pit_strategy_reconstructor.py) (`0` project imports, `0` ledger cost/cash reads, `0` project parquet reads during reconstruction)  
Outputs: [`v2_05_full_chain_pit_reconstruction_summary.json`](v2_05_full_chain_pit_reconstruction_summary.json), [`v2_05_full_chain_picks_comparison.csv`](v2_05_full_chain_picks_comparison.csv)

### 3.1 Intermediate Pipeline Parity (Rebuilt From Raw Files vs `Codex v2` Stored Artifacts)
- **Ticker Aliases Rebuilt From Raw Membership + Price Coverage**: **`41 / 41` (`100.0%` exact match)**.
- **SEC CIK Map Rebuilt From 142 Raw `sec_raw/sub_*.parquet` + Overrides**: **`842 / 842` (`100.0%` exact match)**.
- **57-Feature SEC XBRL + Price/Volume/8-K Panel (`94,010 rows × 57 features = 5,358,570 cells`)**:
  - Universe `(t, ticker)` rows: **`94,010 / 94,010` (`100.0%`)**
  - `mom_rank` mismatches: **`0`**
  - Feature `NaN` mismatches across `5,358,570` cells: **`0`**
  - Maximum feature absolute difference across `5,358,570` cells: **`2.075e-14`**
  - Open-to-open label `ret_oo` differences (`Clean-Room <=` vs `Codex v2 <`): **exactly `2` rows out of `94,010`** — `(2016-02-29, CAM)` (`+0.303%` vs `-1.698%`, `+200.081 bp`) and `(2016-03-31, CAM)` (`-0.257%` vs `0.000%`, `-25.688 bp`); **`0` rows** when emulating `Codex v2`'s `<` boundary.

### 3.2 All 10 Core Headline Strategy Ledgers — End-to-End Clean-Room Verdict

| # | Strategy & Execution Mode | Window (Months) | Clean-Room Verdict (`<=` Bug-Free Opens) | Pick Match | Clean-Room Net CAGR | Stored Ledger Net CAGR | Max `\|net_diff\|` | External BlackRock `IVV` Holdings Confirmation |
|---:|---|---:|---|---:|---:|---:|---:|---|
| **1** | `Pure Momentum Top1` (Close, Additive, `78a2d0d`) | `2009-01..2026-09` (`213`) | **`PASS`** | **`213 / 213`** | **`36.59%`** | `36.59%` | `9.71e-17` | **`135 / 135` (`100.0%`)** |
| **2** | `Pure Momentum Top1` (Close, Self-Financing, `Codex v2`) | `2009-01..2026-09` (`213`) | **`PASS`** | **`213 / 213`** | **`36.59%`** | `36.59%` | `1.67e-16` | **`135 / 135` (`100.0%`)** |
| **3** | `SPEC Top Sector -> Top1` (Close, Additive, `78a2d0d`) | `2009-01..2026-09` (`213`) | **`PASS`** (`213/213` sectors) | **`213 / 213`** | **`27.37%`** | `27.37%` | `9.97e-17` | **`135 / 135` (`100.0%`)** |
| **4** | `SPEC Top Sector -> Top1` (Close, Self-Financing, `Codex v2`) | `2009-01..2026-09` (`213`) | **`PASS`** (`213/213` sectors) | **`213 / 213`** | **`27.36%`** | `27.36%` | `1.63e-16` | **`135 / 135` (`100.0%`)** |
| **5** | `Pure Momentum Top1` (Open-to-Open, Self-Financing, `ML2 Bench`) | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`41.97%`** | `41.97%` | `9.71e-17` | **`135 / 135` (`100.0%`)** |
| **6** | `Pure Momentum Top3` (Open-to-Open, Self-Financing, `ML2 Bench`) | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`27.33%`** | `27.33%` | `2.22e-16` | **`404 / 405` (`99.75%`)** |
| **7** | `Pure Momentum Top3` (Open-to-Open, `Top3_skip_monthly`) | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`27.33%`** | `27.33%` | `2.22e-16` | **`404 / 405` (`99.75%`)** |
| **8** | `Pure Momentum Top3` (Open-to-Open, `Top3_qqq_rebalance`) | `2015-01..2026-09` (`141`) | **`PASS`** | **`141 / 141`** | **`27.33%`** | `27.33%` | `2.22e-16` | **`404 / 405` (`99.75%`)** |
| **9** | `Codex v2 ML2 C-lgbm Top1` (Open-to-Open, Walk-Forward) | `2015-01..2026-09` (`141`) | **`FLAGGED_CAM_TRAINING_OPEN_CUTOFF_CASCADE`** *(Diagnostic `<` emulation: **`141/141` PASS**, `1.67e-16`)* | `104 / 141` *(emul: `141/141`)* | **`16.33%`** *(nodiv: **`23.51%`**)* | `33.39%` | `2.81e-01` *(emul: `1.67e-16`)* | Training-label `<` bug (`-17.06 pp`) + `adjclose` dividend sensitivity |
| **10** | `Codex v2 ML2 C-lgbm Top3` (Open-to-Open, Walk-Forward) | `2015-01..2026-09` (`141`) | **`FLAGGED_CAM_TRAINING_OPEN_CUTOFF_CASCADE`** *(Diagnostic `<` emulation: **`141/141` PASS**, `2.22e-16`)* | `68 / 141` *(emul: `141/141`)* | **`18.69%`** *(nodiv: **`14.08%`**)* | `17.86%` | `1.34e-01` *(emul: `2.22e-16`)* | Training-label `<` bug (`+0.83 pp`) + `adjclose` dividend sensitivity (`-3.78 pp`) |

---

## 4. Full-Population 100% First-Principles Audit of ALL 347 Strategy Ledgers (`v2_01`)

Script: [`v2_01_standalone_all_347_ledgers_auditor.py`](v2_01_standalone_all_347_ledgers_auditor.py) (`0` project imports, `0` reads of ledger cost/cash columns, `rf` from raw `data/fred/DGS3MO.json`)  
Outputs: [`v2_01_all_347_ledgers_cleanroom_audit.csv`](v2_01_all_347_ledgers_cleanroom_audit.csv), [`v2_01_all_347_ledgers_cleanroom_summary.json`](v2_01_all_347_ledgers_cleanroom_summary.json)

### 4.1 First-Principles Return & Transaction-Cost Verdict Breakdown (`347` Ledgers / `63,272` Months)

| Clean-Room First-Principles Verdict | Ledgers | Share | Exact Explanation |
|---|---:|---:|---|
| **`PASS_CLEANROOM_FIRST_PRINCIPLES_RECOMPUTED`** | **298** | `85.88%` | Every month's gross AND net return (including drifted `w_prev`, quarterly non-rebalance drift, 6-sleeve overlapping `hold6m` tranche costs, self-financing bisection, additive `turn × 10bp`, and `DGS3MO` cash carry) matches from raw quotes (`max_gross_diff = 4.98e-6`, `max_net_diff = 5.00e-6`; `<= 2.22e-16` on single-stock/unrounded ledgers). |
| **`UNVERIFIABLE_NET_ONLY_LEDGER`** | **27** | `7.78%` | Legacy `factor_combo/monthly_*.csv` files (`24` in `research/`, `3` in `codex_v2/`) storing only `month, net` without constituent `picks`. Never counted as pass. |
| **`FAIL_CLEANROOM_FIRST_PRINCIPLES_MISMATCH`** | **20** | `5.76%` | **`8` files**: Claude pre-fix `results/ndx/monthly_C_*top_5*.csv` hardcoded `-0.002` (`20bp/month`) cost & `XLK_regime` stale equity `gross` bug;<br>**`6` files**: Claude pre-fix `results/ml2/` merger-exit / additive-cost discrepancies;<br>**`5` files**: **`Codex v2` `ML2` Ridge ledgers (`A_ridge_Top3`, `B_ridge_Top1/Top3`, `C_ridge_Top1/Top3`) holding `CAM` on `2016-03-31` (`200.1 bp` error from `< 2016-04-01` WIKI open cutoff)**;<br>**`1` file**: Claude pre-fix `monthly_SPEC___next_day_close_execution.csv` exit-denominator bug. |
| **`PARTIAL_UNVERIFIABLE_MISSING_RAW_INPUT`** | **2** | `0.58%` | `winners_holdout/monthly_REF_equal_weight_holdout_universe_base*` (`standard` & `STRICT`): `197 / 201` months match to `9.89e-17`, while **`4` months** (`2015-12`, `2016-01`, `2016-04`, `2017-06`) bought already-delisted stocks (`IPCM`, `HUB-B`, `HNT`, `DV`) with `NaN` month-end entry prices (`CL.ffill(limit=5)` vs `7`-calendar-day holiday gap). |
| **Total** | **347** | `100.00%` | **`57,700 / 63,272` strategy-months (`91.19%`)** pass strict first-principles constituent + cost/cash recomputation. |

### 4.2 Honest Audit Scope & Substantive PIT Classification Across All 347 Ledgers
- `RETURN_AND_FIRST_PRINCIPLES_COST_VERIFIED_ONLY`: **`211`** ledgers (constituent returns, cash carry, and first-principles turnover verified; upstream grid/variant picks not re-generated in `v2_05`).
- `PIT_FAIL_SMALLCAP_UNIVERSE_AND_CIK_CONTAMINATION`: **`68`** ledgers (`winners_holdout` small/mid-cap).
- `NET_ONLY_LEGACY_FACTOR_COMBO_NO_PICKS`: **`27`** ledgers.
- `PRE_FIX_ML2_VALUATION_EXIT_AND_ADDITIVE_COST_BUG`: **`17`** ledgers.
- `FULL_CHAIN_PIT_SIGNAL_PICK_AND_COST_VERIFIED_PASS_V2_05`: **`8`** core Pure Momentum & SPEC headline ledgers (`100%` end-to-end verified `PASS`).
- `PRE_FIX_NDX_HARDCODED_20BP_COST_AND_REGIME_GROSS_BUG`: **`8`** ledgers.
- `CODEX_V2_ML2_RIDGE_CAM_OPEN_BOUNDARY_OFF_BY_ONE_BUG`: **`5`** ledgers.
- `FULL_CHAIN_RECONSTRUCTED_V2_05_FLAGGED_CAM_TRAINING_OPEN_CUTOFF_AND_ADJCLOSE_DIVIDEND_SENSITIVITY`: **`2`** `Codex v2` `C-lgbm` headline ledgers.
- `PRE_FIX_NEXT_DAY_CLOSE_EXIT_DENOM_BUG`: **`1`** ledger.

---

## 5. Master 300-Card Disjoint-Tier Audit (`v2_03`) + 100-Card SEC XBRL Non-Null (`v2_02`) & 100-Card SEC NULL Completeness (`v2_04`)

### 5.1 Master 300-Card Random Audit Across 9 Strictly Disjoint Verdict Tiers (`v2_03`)

Outputs: [`v2_300_master_random_cards.md`](v2_300_master_random_cards.md), [`v2_300_master_random_cards.csv`](v2_300_master_random_cards.csv), [`v2_300_master_summary.json`](v2_300_master_summary.json)

| Disjoint Verdict Tier | A: Unrestricted 2-Stage Ledgers (`347` Pool) | B: SEC Raw XBRL + Live `sec.gov` | C: Strict 100% Multiset SEC 13F `.zip` | D: Macro / Coordinate SEP / S&P DJI / ETF | **300-Card Total** | **Share** |
|---|---:|---:|---:|---:|---:|---:|
| **`PASS_EXTERNAL_PRIMARY`** *(Verified against independent external primary source: SEC EDGAR/FSDS, 100%-multiset SEC 13F `.zip`, official BlackRock `IVV` snapshots, Nasdaq WIKI/Tiingo second vendor, ALFRED unrevised vintage, coordinate-parsed Fed SEP Table 1, S&P DJI `.xlsx`)* | **48** | **98** | **40** | **13** | **199** | **`66.33%`** |
| **`PASS_INTERNAL_MATH_SINGLE_VENDOR`** *(Clean-room raw constituent math & first-principles turnover match exactly; single local price/open vendor covers post-2018 open or non-IVV ticker)* | 51 | 0 | 0 | 0 | **51** | **`17.00%`** |
| **`UNVERIFIABLE_NET_ONLY_LEDGER`** *(Unfiltered Stage-1 draw hit one of the 27 legacy `factor_combo` net-only CSVs lacking `picks`)* | **12** | 0 | 0 | 0 | **12** | **`4.00%`** |
| **`DATA_WARNING_KNOWN_LIMITATION`** *(ALFRED macro vintage revisions vs today's FRED, Yardeni `curve_approx`, `-100%` stress bankrupt row, `ANDV`/`SCG` stock-merger dividend omission, `q4_derived` conservative Q4 EPS `NaN`)* | 3 | 2 | 0 | 6 | **11** | **`3.67%`** |
| **`DATA_DEFECT_CONFIRMED`** *(Small-cap ETP contamination `BDRY`/`GBTC`/`UNG` `3`, FOMC SEP 2015–2018 Table 1 cell-extraction errors `3`, LSEG `82221 = ^GSPC` not `QQQ` `2`)* | **3** | 0 | 0 | **5** | **8** | **`2.67%`** |
| **`UNVERIFIABLE_MISSING_RAW_INPUT`** *(Pre-Sept-2015 FOMC SEP rows where official Fed Table 1 had no `Median` column, or missing raw vintage file)* | 0 | 0 | 0 | **6** | **6** | **`2.00%`** |
| **`PASS_EXTERNAL_LATEST_ONLY`** *(Live `api.stlouisfed.org` latest observation matches `0.00e+00`, but ALFRED initial-release vintage was unavailable/empty — strictly downgraded out of `PASS_EXTERNAL_PRIMARY`)* | 0 | 0 | 0 | **5** | **5** | **`1.67%`** |
| **`PASS_INTERNAL_CROSS_STORE`** *(Two local caches of same upstream vendor agree, e.g. `data/yahoo` vs `sector_rotation/adj_prices` ETF dividends — never counted as external primary)* | 0 | 0 | 0 | **5** | **5** | **`1.67%`** |
| **`FAIL_MATH_OR_FACT_MISMATCH`** *(First-principles turnover caught Claude pre-fix `results/ndx/monthly_C_*top_5*` hardcoded `20bp/month` cost bug on `L007`, `L030`, `L083`)* | **3** | **0** | **0** | **0** | **3** | **`1.00%`** |
| **Total Cards** | **120** | **100** | **40** | **40** | **300** | **`100.00%`** |

### 5.2 100-Card SEC Fundamental `NULL` / Missing Completeness Audit (`v2_04`, `N001..N100`)

Script: [`v2_04_sec_xbrl_100_null_completeness_auditor.py`](v2_04_sec_xbrl_100_null_completeness_auditor.py) (`seed = 20261104`, `100 / 100` live `data.sec.gov` confirmed)  
Outputs: [`v2_04_sec_xbrl_100_null_cards.md`](v2_04_sec_xbrl_100_null_cards.md), [`v2_04_sec_xbrl_100_null_cards.csv`](v2_04_sec_xbrl_100_null_cards.csv), [`v2_04_sec_xbrl_100_null_summary.json`](v2_04_sec_xbrl_100_null_summary.json)

| Root-Cause Class of `NULL` Cell | Stratified Sample Count (`100` Cards) | Horvitz-Thompson Population-Weighted Share (`43,321` NULL Cells) | Concrete Findings From Raw SEC FSDS + Live `data.sec.gov` |
|---|---:|---:|---|
| **`TRUE_ABSENT_IN_SEC_XBRL`** | **38** | **`65.40%`** | Neither primary nor any alternative US-GAAP XBRL tag was filed for that quarter in SEC FSDS or live EDGAR (e.g., pre-IPO comparative stubs, pre-revenue biotech `revenue`, or early XBRL phase-in filings). |
| **`PARSER_OMITTED_ALTERNATIVE_TAG_IN_SEC`** | **54** | **`32.24%`** | Company filed a valid `qtrs=1` (or derivable Q4) USD fact under an alternative/industry-specific US-GAAP tag not included in `build_fundamentals.py`'s `WANT` list — principally `NetIncomeLossAvailableToCommonStockholdersBasic` (`23` cards), `IncomeLossFromContinuingOperationsPerBasicShare` (`8` cards), `IncomeLossFromContinuingOperations` (`5` cards), utility `RegulatedAndUnregulatedOperatingRevenue` (`4` cards), bank `InterestIncomeExpenseNet` (`3` cards), `OilAndGasRevenue` (`2` cards), and REIT `RealEstateRevenueNet` (`2` cards). Quantifies exact sector-tag coverage opportunity if fundamental models are rebuilt. |
| **`CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE`** | **8** | **`2.36%`** | Fact existed only as cumulative `FY` (`qtrs=4`) without a matching `9M` (`qtrs=3`) filing (`4` cards), only `qtrs in {2, 3}` YTD (`2` cards), or non-USD reporting currency (`GBP`, `CAD`, `2` cards) — conservatively left `NaN` rather than guessed. |

---

## 6. One-Command Reproducibility (Complete 7-Stage Pipeline)

```bash
bash outputs/gemini_full_data_audit_20261031/v2_standalone/run_v2_standalone_audit.sh
```

Executes in strict sequence:
1. `v2_00_cleanroom_ast_and_readonly_guard.py` (pre-flight `ast.parse` zero-project-import, zero-ledger-cost-read & `10,964`-file SHA-256 read-only baseline check)
2. `v2_01_standalone_all_347_ledgers_auditor.py` (`100%` first-principles constituent + cost + raw `DGS3MO` cash audit of all `347` ledgers / `63,272` months)
3. `v2_02_sec_xbrl_100_random_facts_auditor.py` (`100` SEC raw XBRL non-null numeric facts + `100/100` live `data.sec.gov` API checks)
4. `v2_03_twostage_unrestricted_200_cards_auditor.py` (`120` unrestricted two-stage ledger cards + `40` `100%`-multiset SEC 13F `.zip` cards + `40` Macro/ALFRED/coordinate-parsed FOMC SEP/S&P DJI/Valuation/ETF cards -> `300`-card master tables + 74-row SEP census)
5. `v2_04_sec_xbrl_100_null_completeness_auditor.py` (`100` random SEC `NULL` completeness cards + `100/100` live `data.sec.gov` checks + store-wide zero-row CIK census)
6. `v2_05_full_chain_pit_strategy_reconstructor.py` (end-to-end raw-to-net clean-room PIT reconstruction of `10` core headline ledgers + BlackRock `IVV` verification + dividend-free split-only valuation sensitivity)
7. `v2_00_cleanroom_ast_and_readonly_guard.py` (post-flight verification that `0` bytes changed across all `10,964` protected files)
