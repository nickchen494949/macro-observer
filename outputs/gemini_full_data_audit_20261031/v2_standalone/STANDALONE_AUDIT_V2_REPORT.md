# Clean-Room Standalone Full-Repository Data & Backtest Audit (`v2`)

- **Audit Suite Location**: `outputs/gemini_full_data_audit_20261031/v2_standalone/`
- **Clean-Room Isolation**: **`0` imports of any project module** across all 5 `v2` Python scripts (mechanically enforced via Python `ast.parse` in [`v2_00_cleanroom_ast_and_readonly_guard.py`](v2_00_cleanroom_ast_and_readonly_guard.py) → [`v2_00_cleanroom_guard_report.json`](v2_00_cleanroom_guard_report.json)).
- **Read-Only Protected Baseline**: **`10,964 / 10,964` protected repository files untouched** (`changed = 0`, `missing = 0`, `added = 0`, verified by SHA-256 fingerprint check).
- **Random Audit Sample Size**: **`300` fixed-seed random audit cards** ([`v2_300_master_random_cards.md`](v2_300_master_random_cards.md) / [`v2_300_master_random_cards.csv`](v2_300_master_random_cards.csv)), including **`120` pure unrestricted two-stage random draws across all `347` ledger CSVs** (`0` pre-filtered files), **`100` SEC raw XBRL numeric fact + live `data.sec.gov` cards** ([`v2_02_sec_xbrl_100_cards.md`](v2_02_sec_xbrl_100_cards.md)), **`40` strict full-accession SEC Form 13F raw `.zip` cards**, and **`40` Macro/FOMC SEP/S&P DJI `.xlsx`/Valuation/ETF cards**.

---

## 1. Executive Summary (Plain-Language Verdict)

1. **Why `v2` Exists**: An independent external review of our `v1` audit (`782f33b`) rightly pointed out 6 methodological weaknesses in `v1`'s audit scripts (reusing `backtest.py` / `ml2_run.py` / `fundamentals_pit.py` loaders, fallback patterns when a quote or `picks` column was missing, `LIMIT 25` in 13F line-item spot-checks, checking SEC filing metadata rather than raw XBRL numeric facts, labeling cross-store local ETF checks as primary external verification, and pre-filtering candidate ledgers before random sampling).
2. **What Changed When We Rebuilt Everything 100% Clean-Room (`v2`)**:
   - **Core S&P 500 & Codex v2 Fixed Ledgers Hold Up Under Pure Clean-Room Recomputation**: Without importing a single line of project code, [`v2_01_standalone_all_347_ledgers_auditor.py`](v2_01_standalone_all_347_ledgers_auditor.py) reconstructed daily/monthly closes, opens, segment boundaries, post-filing split factors, and first-principles portfolio turnover directly from raw JSON/Parquet/CSV files across **all `347` strategy ledgers (`63,272` strategy-months)**. **`295` ledgers (`57,705` months)** match 100% of months within CSV weight-serialization precision (`max |gross_diff| = 3.71e-5`, `max |net_diff| = 3.70e-5`, and `<= 1.11e-16` on single-stock/unrounded ledgers), including **all core S&P 500 pure-momentum ledgers (`NO_SECTOR_FILTER__top_1` `36.59%`, `SPEC` `27.36%`, `PureMom Top3 open-to-open` `27.33%`) and Codex v2 fixed `ML2 C-lgbm` ledgers (`Top1 33.39%`, `Top3 17.86%`)**.
   - **Removing Project Loaders & Fallbacks Caught 4 Brand-New Code/Ledger Bugs That `v1` Missed**:
     1. **Claude Pre-Fix NDX Basket Hardcoded `20bp/month` Cost & `XLK_regime` Unheld Gross Bug (`8` files in `research/sector_stock_momentum/results/ndx/monthly_C_*top_5*.csv`)**: Caught both in full-ledger clean-room audit (`v2_01`) and in **3 unrestricted random cards (`L007`, `L030`, `L083`)** (`FAIL_MATH_OR_FACT_MISMATCH`). Claude's `78a2d0d` NDX 5-stock basket CSVs subtracted a flat `0.002` (`20bp`) every month—even on month 1 (`2012-01-31`, where initial entry turnover is `10bp`) and when 3–4 stocks were retained—and on `CASH(regime)` months left the unheld 5-stock equity return in `gross` (`-12.33%` in `2025-03`, `+46.81%` in `2026-04`) while writing `rf` (`+0.25%`) into `net` with `0bp` liquidation/re-entry cost. (All 8 counterparts in Codex v2 `backtest_versions/2026-10-30_codex_full_audit_v2/.../ndx/` fixed this and pass `177/177` months.)
     2. **`build_fundamentals.py:344,354` Row-Level `q4_derived = max(derived)` Over-Blanking Reported Q4 `eps_diluted`**: Caught by clean-room XBRL random cards **`X007` (`ABT` `2019-12-31`, `0.59` in 10-K `0001104659-20-023904`)** and **`X051` (`ZM` `2019-01-31`, `0.01` in 10-K `0001585521-20-000095`)**. Both companies directly reported 3-month (`qtrs=1`) Q4 `EarningsPerShareDiluted` in XBRL (and `eps_diluted_approx` / `eps_diluted_approx_adj` match SEC FSDS and live `data.sec.gov` to `0.00e+00`), but aggregating `q4_derived = max(derived)` across all 5 fields on a row caused a derived `revenue` or `diluted_shares` field to blank out a genuinely reported `qtrs=1` `eps_diluted`.
     3. **`smallcap_universe.py:157` + `winners_holdout.py:101` Buying 4 Already-Delisted Stocks (`IPCM`, `HUB-B`, `HNT`, `DV`) With `NaN` Month-End Entry Price**: Caught immediately once `else led_g` was removed (`PARTIAL_UNVERIFIABLE_MISSING_RAW_INPUT` on 2 equal-weight holdout reference ledgers). `monthly()` sets `P[t, sym] = NaN` if a stock stopped trading >7 days before month-end `t`, yet `momentum(P, 12)` only checks `P[t-1]` and `P[t-12]` and `universe()` used `CL.ffill(limit=5) >= 5`, allowing 4 mid-month delisted stocks (`IPCM` `2015-11-30`, `HUB-B` `2015-12-31`, `HNT` `2016-03-31`, `DV` `2017-05-31`) into the equal-weight basket with no month-end entry quote.
     4. **15 Single-Month Intra-Month Merger/Delisting Exit Convention Discrepancies (`1` month out of `140–213` months per file)**: Clean-room open/close auditing pinpointed 15 ledgers with a single-month merger-exit convention mismatch (`CAM` `2016-03-31` and `CVC` `2016-06-30` entering at day-1 `adj_open` and exiting at final pre-merger `adj_close`; `HSP` `2015-08/09` applying `lag_days=0` `exit_resolutions.csv` vs `lag_days=1`; and 1 mid-month delisted sleeve month in 7 `hold6m` files).
3. **Final Repository Readiness Verdict (Unchanged in Substance, Upgraded in Proof)**:
   - **Ready / Verified**: S&P 500 core price/open arithmetic & Codex v2 core pure-momentum ledgers; SEC Form 13F full institutional database (`13f_full_4409f14.db`, **`40 / 40` strict raw `.zip` full-accession row-count & tuple matches**); SEC XBRL raw quarterly fundamentals & PIT `filed + 1d` timing (**`100 / 100` live `data.sec.gov` accession confirmations**, `98` `PASS_EXTERNAL_PRIMARY` + `2` conservative `q4_derived` NaN warnings).
   - **Not Ready / Structurally Defective**: `winners_holdout` small/mid-cap universe (non-PIT universe + commodity/crypto ETPs `GBTC`/`BDRY`/`UNG`/`AGQ`/`USO` + recycled CIKs `SPWR`/`BID`/`ETH` + 4 post-delisting `NaN` entries); pre-fix `78a2d0d` `ML2` (`adjclose` future-dividend valuation contamination + validation-boundary leakage) and pre-fix `78a2d0d` `NDX` 5-stock basket costs; `lseg_backtest_results_v3.csv` (`source=82221` proven to be `^GSPC`, not `QQQ`); Yardeni `curve_approx` sector EPS; pre-September-2015 FOMC SEP rows lacking official Fed medians; non-PIT revised FRED macro series when treated as real-time signals.

---

## 2. Point-by-Point Resolution of All 6 External-Review Critiques

| # | External-Review Critique of `v1` (`782f33b`) | Mechanical Fix Implemented in `v2` (`v2_standalone/`) | Reproducible Proof |
|---|---|---|---|
| **1** | `v1` imported project modules (`backtest`, `ml2_run`, `fundamentals_pit`) | **100% standalone clean-room reimplementation** ([`v2_cleanroom_lib.py`](v2_cleanroom_lib.py)). [`v2_00_cleanroom_ast_and_readonly_guard.py`](v2_00_cleanroom_ast_and_readonly_guard.py) parses every `.py` file via `ast.parse`, enforcing an explicit stdlib/scientific allowlist and banning all 24 project modules + external `sys.path` mutations. | [`v2_00_cleanroom_guard_report.json`](v2_00_cleanroom_guard_report.json): `scripts_checked=5`, `total_ast_or_pattern_violations=0` |
| **2** | False-pass fallbacks (`else led_g`, `else: ok = True`, net-only CSV pass, `gross - net` implied cost) | **All fallbacks and `gross - net` tautologies banned** in `FORBIDDEN_SUBSTRINGS` of `v2_00`. Net-only CSVs without `picks` are explicitly labeled **`UNVERIFIABLE_NET_ONLY_LEDGER`** (`27` files in `v2_01`; `12` random cards in `v2_03`). Missing raw prices return `(None, "MISSING_RAW_ENTRY_PRICE")` -> **`PARTIAL_UNVERIFIABLE_MISSING_RAW_INPUT`**. Portfolio net return is computed strictly from `capital_after_costs`, `turnover`, or first-principles weight turnover $\sum_k |w_{t,k} - w_{t-1,k}|$. | Caught **3 `FAIL_MATH_OR_FACT_MISMATCH`** random cards (`L007`, `L030`, `L083`) in Claude pre-fix NDX ledgers + **4 delisted `NaN`-entry stocks** (`IPCM`, `HUB-B`, `HNT`, `DV`) |
| **3** | 13F spot-check used `LIMIT 25` and `else: ok_13f = True` | [`v2_03_twostage_unrestricted_200_cards_auditor.py`](v2_03_twostage_unrestricted_200_cards_auditor.py) (`run_part_c_40_strict_13f_cards`, lines 486–626) scans the **entire raw SEC `.zip` `INFOTABLE.tsv`** for the drawn accession, verifies exact **total filing row count (`raw_count == db_count`)**, and requires an exact `(CUSIP, raw_value, value_usd, shares, put_call)` match across **all** rows of the filing (zero SQL row limit, zero fallback). | **`40 / 40` `PASS_EXTERNAL_PRIMARY`** across 28 official SEC `.zip` archives (`F001..F040`, filings up to `4,782` holdings/filing checked in full) |
| **4** | `v1` S5 checked SEC filing metadata (`form`, `filed+1d`) rather than raw XBRL numeric facts | [`v2_02_sec_xbrl_100_random_facts_auditor.py`](v2_02_sec_xbrl_100_random_facts_auditor.py) audits **`100` random `(CIK, period_end, metric)` facts** (`34` `eps_diluted`, `33` `revenue`, `33` `net_income` across `sp500`/`ndx`/`smallcap`) directly against **142 official SEC FSDS `sub_*.parquet` + `num_*.parquet` files** AND **live `https://data.sec.gov/api/xbrl/companyfacts/`**, including 14 Q4 `FY - 9M` derivations and 34 clean-room post-filing split adjustments from raw JSON `splits`. | [`v2_02_sec_xbrl_100_summary.json`](v2_02_sec_xbrl_100_summary.json): **`98` `PASS_EXTERNAL_PRIMARY`**, **`2` `DATA_WARNING_KNOWN_LIMITATION`** (`X007`, `X051`), **`0` `FAIL`**, **`100 / 100` live `data.sec.gov` confirmed** |
| **5** | Cross-store local ETF comparisons (`data/yahoo` vs `sector_rotation/adj_prices`) were counted as `PASS_PRIMARY_VERIFIED` | `v2` enforces **7 strictly disjoint verdict tiers**. Comparing two local caches of the same upstream vendor (Yahoo Finance) is strictly isolated as **`PASS_INTERNAL_CROSS_STORE`** (`5` cards `M036..M040`) and **never** counted inside **`PASS_EXTERNAL_PRIMARY`** (`177` cards). | [`v2_300_master_summary.json`](v2_300_master_summary.json): `PASS_EXTERNAL_PRIMARY=177`, `PASS_INTERNAL_MATH_SINGLE_VENDOR=81`, `PASS_INTERNAL_CROSS_STORE=5` |
| **6** | Stage-1 ledger pool in `v1` excluded `REF_`, `stress`, `STRICT`, and net-only files while claiming zero cherry-picking | Part A of `v2_03` (`L001..L120`) performs **pure unrestricted two-stage random sampling across ALL `347` ledger CSVs (`pre_filtered_exclusions = 0`)**: Stage 1 draws uniformly over `0..346`; Stage 2 draws uniformly over rows and constituent picks. For Part B (`X001..X100`), predefined stratum sizes $N_h$, $n_h$, and exact inclusion probabilities $n_h / N_h$ are published in `v2_02_sec_xbrl_100_summary.json`. | Stage 1 hit `103` unique ledgers across Claude (`70`), Codex v2 (`47`), and Top-3 studies (`3`), naturally hitting `12` net-only files, `stress`/`STRICT` files, and `3` pre-fix NDX cost-bug cards |

---

## 3. Full-Population Clean-Room Audit of ALL 347 Strategy Ledgers (`v2_01`)

Script: [`v2_01_standalone_all_347_ledgers_auditor.py`](v2_01_standalone_all_347_ledgers_auditor.py) (`0` project imports)  
Outputs: [`v2_01_all_347_ledgers_cleanroom_audit.csv`](v2_01_all_347_ledgers_cleanroom_audit.csv), [`v2_01_all_347_ledgers_cleanroom_summary.json`](v2_01_all_347_ledgers_cleanroom_summary.json)

### 3.1 Clean-Room Ledger Verdict Breakdown (`347` Ledgers / `63,272` Strategy-Months)

| Clean-Room Verdict | Ledgers | Share | Exact Explanation |
|---|---:|---:|---|
| **`PASS_CLEANROOM_CONSTITUENT_RECOMPUTED`** | **295** | `85.01%` | Every single month recomputed from raw constituent JSON/Parquet prices/opens + first-principles turnover (`max |gross_diff| = 3.71e-5`, `max |net_diff| = 3.70e-5`; `<= 1.11e-16` on single-stock/unrounded ledgers). Includes **all core S&P 500 pure-momentum ledgers** and **Codex v2 `ML2 C-lgbm` & `NDX` fixed ledgers**. |
| **`UNVERIFIABLE_NET_ONLY_LEDGER`** | **27** | `7.78%` | Legacy `factor_combo/monthly_*.csv` files (`24` in `research/`, `3` in `codex_v2/`) that store only `month, net` without constituent `picks`. Cannot be constituent-verified; never counted as pass. |
| **`FAIL_CLEANROOM_MATH_MISMATCH`** | **23** | `6.63%` | **`8` files**: Claude pre-fix `research/sector_stock_momentum/results/ndx/monthly_C_*top_5*.csv` hardcoded `-0.002` (`20bp/month`) cost & `XLK_regime` unheld equity `gross` bug (all 8 fixed and passing in Codex v2).<br>**`15` files**: Single-month (`1` month out of `140–213` months) intra-month cash-merger / delisting exit convention discrepancies (`CAM` `2016-03-31`, `CVC` `2016-06-30`, `HSP` `2015-08/09`, and 1 delisted-sleeve month in 7 `hold6m` files). |
| **`PARTIAL_UNVERIFIABLE_MISSING_RAW_INPUT`** | **2** | `0.58%` | `winners_holdout/monthly_REF_equal_weight_holdout_universe_base*` (`standard` & `STRICT`): `197 / 201` months match to `9.89e-17`, while **`4` months** (`2015-12`, `2016-01`, `2016-04`, `2017-06`) included already-delisted stocks (`IPCM`, `HUB-B`, `HNT`, `DV`) whose formation month-end raw entry price was `NaN`. |
| **Total** | **347** | `100.00%` | **`57,705 / 63,272` strategy-months (`91.20%`)** pass strict clean-room constituent recomputation. |

### 3.2 Orthogonal Substantive PIT / Methodology Classification Across All 347 Ledgers

Passing clean-room return arithmetic does **not** mean a strategy is free of universe/feature look-ahead bias. `v2_01` simultaneously tags every ledger for substantive PIT validity:
- **`CLEAN_OR_FIXED_LEDGER` (`230` ledgers)**: Core S&P 500 & Nasdaq-100 price/momentum ledgers and Codex v2 `4ea9a1d` fixed `ML2` / `NDX` / `factor_combo` ledgers.
- **`PIT_FAIL_SMALLCAP_UNIVERSE_AND_CIK_CONTAMINATION` (`68` ledgers)**: All `winners_holdout` small/mid-cap ledgers (arithmetic matches raw quotes, but candidate pool comes from current `company_tickers_exchange.json` and contains commodity/crypto ETPs and recycled CIKs).
- **`NET_ONLY_LEGACY_FACTOR_COMBO` (`24` ledgers)**: Pre-fix net-only `factor_combo` CSVs.
- **`PRE_FIX_ML2_VALUATION_AND_ADDITIVE_COST_BUG` (`17` ledgers)**: Claude `78a2d0d` `results/ml2/` ledgers (contaminated by dividend-adjusted `adjclose` in market-cap/valuation ratios and cross-month validation open leakage; superseded by Codex v2).
- **`PRE_FIX_NDX_HARDCODED_20BP_COST_AND_REGIME_GROSS_BUG` (`8` ledgers)**: Claude `78a2d0d` `results/ndx/monthly_C_*top_5*.csv` basket ledgers (superseded by Codex v2).

---

## 4. Clean-Room 100-Card SEC Raw XBRL Numeric Fact & Live `data.sec.gov` Audit (`v2_02`)

Script: [`v2_02_sec_xbrl_100_random_facts_auditor.py`](v2_02_sec_xbrl_100_random_facts_auditor.py) (`seed = 20261101`, `0` project imports)  
Outputs: [`v2_02_sec_xbrl_100_cards.md`](v2_02_sec_xbrl_100_cards.md), [`v2_02_sec_xbrl_100_cards.csv`](v2_02_sec_xbrl_100_cards.csv), [`v2_02_sec_xbrl_100_summary.json`](v2_02_sec_xbrl_100_summary.json)

### 4.1 Sampling Design & Predefined Stratum Weights
We drew `100` random `(CIK, period_end, metric)` facts without replacement across 9 predefined `(store × metric)` strata (`sp500`: `18` `eps_diluted`, `16` `revenue`, `16` `net_income`; `ndx`: `5` each; `smallcap`: `11` `eps_diluted`, `12` `revenue`, `12` `net_income`), spanning `95` unique SEC filers from `2008` to `2026`. Exact population counts $N_h$ (`369,248` total non-null metric cells across `204,523` quarterly rows) and inclusion probabilities $n_h / N_h$ are recorded in [`v2_02_sec_xbrl_100_summary.json`](v2_02_sec_xbrl_100_summary.json).

### 4.2 Four Independent Checks Executed on Every Card (`X001..X100`)
1. **Official SEC FSDS Raw Parquet Extraction (`sec_raw/sub_*.parquet` + `num_*.parquet`, 142 files)**: Matched exact SEC accession (`adsh`), form (`10-Q`/`10-K`), US-GAAP XBRL tag, `ddate`, `qtrs=1` (or clean-room Q4 derivation `FY [qtrs=4] - 9M [qtrs=3]` on `14` Q4 cards), and PIT `filed` date (`filed <= stored_filed`).
2. **Live SEC EDGAR `data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json` Cross-Check**: Confirmed the exact accession number and raw numeric fact live against SEC's official API on **`100 / 100` cards**.
3. **PIT `available_date == filed + 1 calendar day` & `period_end <= filed + 16 days`**: **`100 / 100` pass (`0` violations)**.
4. **Clean-Room Post-Filing Split Adjustment (`34 / 34` `eps_diluted` cards)**: Recomputed cumulative split product strictly for `split_date > filed_date` directly from raw price JSON `splits` arrays (`raw_yahoo` / `raw_ndx` / `raw_smallcap` / `raw_tiingo`) — **`34 / 34` exact (`diff = 0.00e+00`)**, including multi-split and reverse-split cases (`MMM` `1.196`, `AMCR` `0.2`, `C` `0.1`, `SPGI` `1.057`, `SIRI` `0.1`, `NCRA` `0.0333333`, `PRHI` `0.142857`).

### 4.3 Results by Store and Metric

| Store \ Metric | `eps_diluted` | `revenue` | `net_income` | Total | Live `data.sec.gov` Confirmed |
|---|---|---|---|---:|---:|
| **`sp500`** | `17` PASS + `1` WARN (`X007` ABT) | `16` PASS | `16` PASS | **50** | **`50 / 50`** |
| **`ndx`** | `4` PASS + `1` WARN (`X051` ZM) | `5` PASS | `5` PASS | **15** | **`15 / 15`** |
| **`smallcap`** | `11` PASS | `12` PASS | `12` PASS | **35** | **`35 / 35`** |
| **Total** | **`32` PASS + `2` WARN (`0` FAIL)** | **`33` PASS (`0` FAIL)** | **`33` PASS (`0` FAIL)** | **100** | **`100 / 100`** |

---

## 5. Master 300-Card Random Audit Breakdown Across Strict Disjoint Verdict Tiers (`v2_03`)

Script: [`v2_03_twostage_unrestricted_200_cards_auditor.py`](v2_03_twostage_unrestricted_200_cards_auditor.py) (`0` project imports, `0` false-pass fallbacks)  
Outputs: [`v2_300_master_random_cards.md`](v2_300_master_random_cards.md), [`v2_300_master_random_cards.csv`](v2_300_master_random_cards.csv), [`v2_300_master_summary.json`](v2_300_master_summary.json)

| Disjoint Verdict Tier | A: Unrestricted 2-Stage Ledgers (`347` Pool) | B: SEC Raw XBRL + Live `sec.gov` | C: Strict Full-Accession SEC 13F `.zip` | D: Macro / SEP / S&P DJI / LSEG / ETF | **300-Card Total** | **Share** |
|---|---:|---:|---:|---:|---:|---:|
| **`PASS_EXTERNAL_PRIMARY`** *(Verified against independent external primary source: SEC EDGAR/FSDS, SEC 13F `.zip`, Nasdaq WIKI vs Yahoo, BlackRock IVV, live FRED/ALFRED unrevised, Fed SEP PDF, S&P DJI `.xlsx`)* | 20 | 98 | **40** | 19 | **177** | **`59.00%`** |
| **`PASS_INTERNAL_MATH_SINGLE_VENDOR`** *(Clean-room raw constituent math & turnover match exactly; only 1 local price vendor covers post-2018-03 or open-to-open window)* | 81 | 0 | 0 | 0 | **81** | **`27.00%`** |
| **`PASS_INTERNAL_CROSS_STORE`** *(Two local caches of same upstream vendor agree, e.g. `data/yahoo` vs `sector_rotation/adj_prices` ETF dividends — NEVER counted as external primary)* | 0 | 0 | 0 | **5** | **5** | **`1.67%`** |
| **`DATA_WARNING_KNOWN_LIMITATION`** *(ALFRED macro vintage revisions vs today's FRED `10`, Yardeni `curve_approx` `1`, `-100%` stress bankrupt row `1`, `build_fundamentals.py` conservative Q4 EPS `NaN` `2`)* | 1 | 2 | 0 | 11 | **14** | **`4.67%`** |
| **`UNVERIFIABLE_NET_ONLY_LEDGER`** *(Unfiltered Stage-1 draw hit one of the 27 legacy `factor_combo` net-only CSVs lacking `picks`)* | **12** | 0 | 0 | 0 | **12** | **`4.00%`** |
| **`DATA_DEFECT_CONFIRMED`** *(Small-cap ETP contamination `BDRY`/`GBTC`/`UNG` `3`, pre-Sept-2015 FOMC SEP missing official Fed median `3`, LSEG `82221` = `^GSPC` not `QQQ` `2`)* | **3** | 0 | 0 | **5** | **8** | **`2.67%`** |
| **`FAIL_MATH_OR_FACT_MISMATCH`** *(Clean-room turnover formula caught Claude pre-fix `results/ndx/monthly_C_*top_5*` hardcoded `20bp/month` net-return error on `L007`, `L030`, `L083`)* | **3** | **0** | **0** | **0** | **3** | **`1.00%`** |
| **Total Cards** | **120** | **100** | **40** | **40** | **300** | **`100.00%`** |

---

## 6. One-Command Reproducibility

```bash
bash outputs/gemini_full_data_audit_20261031/v2_standalone/run_v2_standalone_audit.sh
```

This runs, in strict sequence:
1. `v2_00_cleanroom_ast_and_readonly_guard.py` (pre-flight `ast.parse` zero-project-import & anti-fallback check + `10,964`-file SHA-256 read-only baseline check)
2. `v2_01_standalone_all_347_ledgers_auditor.py` (clean-room audit of all `347` ledgers / `63,272` months)
3. `v2_02_sec_xbrl_100_random_facts_auditor.py` (`100` SEC raw XBRL numeric facts + live `data.sec.gov` API cross-checks)
4. `v2_03_twostage_unrestricted_200_cards_auditor.py` (`120` unrestricted two-stage ledger cards + `40` strict full-accession 13F `.zip` cards + `40` Macro/SEP/S&P DJI/Valuation/ETF cards -> `300`-card master tables)
5. `v2_00_cleanroom_ast_and_readonly_guard.py` (post-flight verification that `0` bytes changed across all `10,964` protected files)
