# Standalone Clean-Room Audit Report (v5): Frozen Stall-Detector Rule `12-1 Momentum + RS(6-0) > Benchmark` & Full `Top-1 + SMA200` Next-Day Open Audit

- **Audit Date**: `2026-11-02`
- **Audit Version**: `v5_zero_alias_csv_and_full_sma200_open_audit`
- **Auditor Script**: `outputs/gemini_full_data_audit_20261031/v2_standalone/v2_06_frozen_rs60_cleanroom_auditor.py`
- **Clean-Room Library**: `outputs/gemini_full_data_audit_20261031/v2_standalone/v2_cleanroom_lib.py`
- **Summary JSON**: `outputs/gemini_full_data_audit_20261031/v2_standalone/v2_06_frozen_rs60_cleanroom_summary.json`
- **AST & Read-Only Guard**: `outputs/gemini_full_data_audit_20261031/v2_standalone/v2_00_cleanroom_ast_and_readonly_guard.py` (`8/8` scripts checked, `total_ast_or_pattern_violations = 0`, `10,964/10,964` baseline files untouched)

---

## 1. Executive Summary & Clean-Room Verification Guarantees (Upgraded in v5)

1. **Zero Project Imports & Zero Derived File Reads — Including `ticker_aliases_used.csv` (`v2_00` Mechanically Enforced)**
   - In `v5`, `v2_cleanroom_lib.py`'s `CleanRoomEquityStore._read_aliases()` was completely rewritten to **eliminate any read of `results/ticker_aliases_used.csv`**, and both `"ticker_aliases_used.csv"` and `"panel.parquet"` were added to `FORBIDDEN_SUBSTRINGS` in `v2_00_cleanroom_ast_and_readonly_guard.py` (`total_ast_or_pattern_violations = 0`).
   - All `41` ticker aliases (corporate renames/reorgs) are reconstructed **100% from scratch** using raw SEC FSDS `sub_*.parquet` submissions, `sp500_ticker_start_end.csv`, `wiki_changes.csv`, `wiki_current_constituents.csv`, `sec_company_tickers.csv`, `sec_successor_aliases.csv`, and raw first-price dates (`data/raw/*.json`, `data/raw_tiingo/*.json`).
   - All `99,949` eligible S&P 500 ticker-months across `201` formation months (`2009-12-31..2026-08-31` $\rightarrow$ holding months `2010-01..2026-09`) are reconstructed from scratch using raw JSON prices/opens (`data/raw/*.json`, `data/raw_open/*.json`, `data/raw_tiingo/*.json`, `data/raw_wiki/*.json`), raw SEC FSDS `sub_*.parquet`, raw PIT S&P 500 membership (`sp500_hist_components.csv`), and raw FRED 3M T-Bill yields (`DGS3MO.json`).

2. **Three Full-Chain Month-by-Month Parity Checks Passed (`100.0%` Pick Match & Machine-Epsilon Return Parity)**
   - **Parity Check 1 — `BENCH_momentum_Top3` (`Next-Day Open`, `141` months `2015-01..2026-09`)**:
     - Ledger compared: `backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_BENCH_momentum_Top3.csv`
     - **Pick-set exact matches**: `141 / 141` (`100.0%`)
     - **Max gross return diff**: `9.95e-17` | **Max net return diff**: `2.22e-16`
     - **External BlackRock iShares `IVV` Holdings confirmation**: `404 / 405` (`99.75%`)
   - **Parity Check 2 — `Top-1 + SMA200` (`Close-to-Close`, `201` months `2010-01..2026-09` & `141` months `2015-01..2026-09`)**:
     - Ledger compared: `research/sector_stock_momentum/results/ml/sma200_pure_momentum_top_1___SMA200.csv`
     - **`2010–2026` (`201` months) exact pick matches**: `201 / 201` (`100.0%`), **max net return diff**: `9.54e-17`
     - **`2015–2026` (`141` months) exact pick matches**: `141 / 141` (`100.0%`), **max net return diff**: `9.19e-17`
     - **External BlackRock iShares `IVV` Holdings confirmation (`2015–2026`)**: `135 / 135` (`100.0%`)
   - **Parity Check 3 — `Top-1 Pure Momentum` (`Close-to-Close`, `201` months `2010-01..2026-09`)**:
     - Ledger compared: `research/sector_stock_momentum/results/ml/sma200_pure_momentum_top_1.csv`
     - **`2010–2026` (`201` months) exact pick matches**: `201 / 201` (`100.0%`), **max net return diff**: `9.54e-17`

3. **Both Execution Engines, Both Turnover Cost Equations (`Additive` vs `Self-Financing`), & Both Cash Cost Models (`0bp` vs `10bp`) Verified**
   - **Engine A (`Close-to-Close`, Fixed Equal-Weight Rebalance)**: Signal at month-end `t` close, return `Close[t+1] / Close[t] - 1`.
   - **Engine B (`Next-Day Open-to-Open`, Drifted-Weight Rebalance)**: Signal at month-end `t` close (`RS(6-0) = Close[t] / Close[t-6] - 1`, `SMA200` at `t` close), execution at **next trading day's Open (`Open[t+1_day1]`)**.
   - **Turnover Cost Equation 1 (`Additive`)**: `net = gross - turnover * 0.0010` (matches `ml2_run.py` ledger format).
   - **Turnover Cost Equation 2 (`Self-Financing`)**: `solve_self_financing_capital(w_drift, w_target, cost_bps=10.0)` where transaction fees are deducted from invested capital before buying the next month's portfolio.
   - **Cash Cost Model 1 (`Cash 0bp`)**: `10bp` per side on stock buys/sells; `0bp` on T-bill cash sweep.
   - **Cash Cost Model 2 (`Cash ETF 10bp`)**: `10bp` per side on both stocks AND T-bill ETF (`Stock <-> Cash ETF = 20bp`).

---

## 2. Dedicated Audit of `All S&P Top-1 + SMA200` (`Close-to-Close` vs `Next-Day Open-to-Open` & `Pass-Down` vs `Gate-to-Cash`)

### 2.1 Strategy Definitions Audited
1. **`Pass-Down (< SMA200 顺延下一名)`**: At month-end `t`, remove all S&P 500 stocks with `Close[t] < SMA200[t]`, then buy the `#1` highest `12-1` momentum stock among the remaining `>= SMA200` stocks (e.g., in `2026-11`, `#1 SNDK` is below `SMA200`, so it passes down to `#2 MRNA`).
2. **`Gate-to-Cash (#1 < SMA200 转 Cash)`**: At month-end `t`, select the `#1` `12-1` momentum stock first; if its `Close[t] < SMA200[t]`, hold `100% CASH` (3M T-Bill) for that month instead of passing down to `#2`.

### 2.2 Full Performance Table Across All Windows (`2010–2026`, `2015–2026`, `Ex-2022`, & 5 Sub-Periods)

| Variant & Execution Engine | `2010–2026` (201m) CAGR / Sharpe / MaxDD | `2015–2026` (141m) CAGR / Sharpe / MaxDD | `2015–2026 Ex-2022` (129m) CAGR | `2010–2014` (60m) | `2015–2019` (60m) | `2020–2021` (24m) | `2022` (12m) | `2023–2026` (45m) | Cash % (201m) |
|---|---|---|---|---|---|---|---|---|---|
| **`Top-1 + SMA200` (`Pass-Down`, `Close-to-Close`, Fixed Wt)** | **`45.47%`** / `0.97` / `-62.29%` | **`52.04%`** / `0.99` / `-62.29%` | **`51.69%`** | `31.14%` | `7.85%` | `43.41%` | **`+55.84%`** | `146.30%` | `0.0%` |
| **`Top-1 + SMA200` (`Pass-Down`, `Next-Day Open`, Drifted Wt, `Additive`)** | **`45.82%`** / `0.98` / `-61.00%` | **`50.18%`** / `0.98` / `-61.00%` | **`49.82%`** | **`36.07%`** | **`9.53%`** | `32.29%` | **`+54.11%`** | `143.09%` | `0.0%` |
| **`Top-1 + SMA200` (`Pass-Down`, `Next-Day Open`, Drifted Wt, `Self-Financing`)** | **`45.80%`** / `0.98` / `-60.96%` | **`50.15%`** / `0.98` / `-60.96%` | **`49.78%`** | **`36.05%`** | **`9.52%`** | `32.24%` | **`+54.18%`** | `143.02%` | `0.0%` |
| **`Top-1 + SMA200` (`Gate-to-Cash`, `Close-to-Close`, Fixed Wt)** | `44.40%` / `0.96` / `-57.25%` | `50.73%` / `0.98` / `-57.25%` | `52.23%` | `30.54%` | `12.38%` | `43.41%` | `+35.50%` | `135.57%` | `4.0%` |
| **`Top-1 + SMA200` (`Gate-to-Cash`, `Next-Day Open`, Drifted Wt, `Additive`)** | `44.08%` / `0.96` / `-58.49%` | `47.98%` / `0.96` / `-58.49%` | `49.25%` | `35.30%` | `12.11%` | `32.29%` | `+35.05%` | `133.08%` | `4.0%` |
| *Reference: Pure `Top-1` (`Next-Day Open`, No Filter)* | `40.99%` / `0.90` / `-70.70%` | `41.98%` / `0.86` / `-70.70%` | `47.32%` | `38.67%` | `8.43%` | `32.29%` | `-4.51%` | `134.79%` | `0.0%` |

- **Key Takeaways on `Top-1 + SMA200`**:
  1. Switching from `Close-to-Close` to **realistic `Next-Day Open-to-Open` (`Drifted Wt`, `0.1%` per-side cost, zero alias CSV read)** preserves the strategy's full strength:
     - **`2010–2026` (`201` months)**: `Close` `45.47%` $\rightarrow$ **`Next-Day Open` `45.82%` (`Additive`) / `45.80%` (`Self-Financing`)**, while MaxDD improves slightly from `-62.29%` to **`-61.00%`** (`-60.96%`).
     - **`2015–2026` (`141` months)**: `Close` `52.04%` $\rightarrow$ **`Next-Day Open` `50.18%` (`Additive`) / `50.15%` (`Self-Financing`)**, Sharpe `0.98`, beating un-filtered `Next-Day Open Top-1` (`41.98%`) by **`+8.20%/yr`** and reducing MaxDD by **`+9.70%`** (`-70.70%` $\rightarrow$ `-61.00%`).
  2. **`Pass-Down` (`< SMA200` 顺延下一名) outperforms `Gate-to-Cash` (`#1 < SMA200` 转 Cash)** in both `Close` (`45.47%` vs `44.40%`) and `Next-Day Open` (`45.82%` vs `44.08%`), especially in `2022` (`+54.11%` vs `+35.05%`), because rotating from broken tech/biotech leaders (`MRNA` in `2022-01`) into #2 energy leaders (`DVN` above `SMA200`) captured the 2022 energy bull trend.

---

## 3. Core Audit Results: `12-1 Momentum + RS(6-0) > Benchmark (else CASH)` (`Additive` vs `Self-Financing` Side-by-Side)

### Table 3A — Full Audited Test Window (`2015-01..2026-09`, 141 Months)

| Strategy & Execution Engine | Baseline CAGR | `+RS(6-0)` (`Cash 0bp`) | `+RS(6-0)` (`Cash ETF 10bp`) | $\Delta$ CAGR (`0bp`) | Baseline $\rightarrow$ `+RS` Sharpe | Baseline $\rightarrow$ `+RS` MaxDD | Avg Cash % |
|---|---|---|---|---|---|---|---|
| **All S&P Top-3 (`Close-to-Close`, Fixed Wt)** | `27.38%` | **`29.87%`** | `29.73%` | **`+2.49%`** | `0.78` $\rightarrow$ **`0.85`** | `-30.70%` $\rightarrow$ **`-26.02%`** | `6.6%` |
| **All S&P Top-3 (`Next-Day Open`, Drifted Wt, `Additive`)** | `27.35%` | **`30.19%`** | `30.06%` | **`+2.84%`** | `0.79` $\rightarrow$ **`0.87`** | `-25.78%` $\rightarrow$ **`-24.63%`** | `6.6%` |
| **All S&P Top-3 (`Next-Day Open`, Drifted Wt, `Self-Financing`)** | `27.32%` | **`30.17%`** | `30.06%` | **`+2.85%`** | `0.79` $\rightarrow$ **`0.87`** | `-25.76%` $\rightarrow$ **`-24.63%`** | `6.6%` |
| **All S&P Top-1 (`Close-to-Close`, Fixed Wt)** | `43.44%` | **`51.38%`** | `51.23%` | **`+7.94%`** | `0.88` $\rightarrow$ **`0.99`** | `-69.40%` $\rightarrow$ **`-57.25%`** | `5.7%` |
| **All S&P Top-1 (`Next-Day Open`, Drifted Wt, `Additive`)** | `41.98%` | **`48.70%`** | `48.55%` | **`+6.72%`** | `0.86` $\rightarrow$ **`0.96`** | `-70.70%` $\rightarrow$ **`-58.49%`** | `5.7%` |
| **All S&P Top-1 (`Next-Day Open`, Drifted Wt, `Self-Financing`)** | `41.96%` | **`48.68%`** | `48.55%` | **`+6.72%`** | `0.86` $\rightarrow$ **`0.96`** | `-70.67%` $\rightarrow$ **`-58.46%`** | `5.7%` |
| **Tech Top-1 (`Close-to-Close`, vs `XLK`)** | `60.03%` | **`60.46%`** | `60.22%` | **`+0.43%`** | `1.11` $\rightarrow$ **`1.13`** | `-46.57%` $\rightarrow$ `-46.57%` | `9.2%` |
| **All S&P Top-1 + SMA200 (`Close`, vs `SPY`)** | **`52.04%`** | `48.83%` | `48.76%` | `-3.21%` | `0.99` $\rightarrow$ `0.95` | `-62.29%` $\rightarrow$ `-62.29%` | `2.8%` |
| **All S&P Top-1 + SMA200 (`Next-Day Open`, vs `SPY`)** | **`50.18%`** | `46.59%` | `46.52%` | `-3.59%` | `0.98` $\rightarrow$ `0.93` | `-61.00%` $\rightarrow$ `-61.00%` | `2.8%` |

---

## 4. The Three Reviewer Stress & Validation Tests

### Test 1: Removing 2022 Entirely (`Ex-2022` Verification)

| Strategy & Execution Engine | Window (Ex-2022) | Months | Baseline CAGR | `+RS(6-0)` (`0bp`) | `+RS(6-0)` (`10bp`) | $\Delta$ CAGR (`0bp`) | Baseline $\rightarrow$ `+RS` Sharpe | Baseline $\rightarrow$ `+RS` MaxDD |
|---|---|---|---|---|---|---|---|---|
| **All S&P Top-3 (`Close`, vs `SPY`)** | `2015–2026 ex-2022` | 129 | `28.89%` | **`29.76%`** | `29.63%` | **`+0.87%`** ✅ | `0.83` $\rightarrow$ **`0.86`** | `-30.70%` $\rightarrow$ **`-26.02%`** |
| **All S&P Top-3 (`Next-Day Open`, `Additive`)** | `2015–2026 ex-2022` | 129 | `28.81%` | **`29.89%`** | `29.75%` | **`+1.08%`** ✅ | `0.85` $\rightarrow$ **`0.88`** | `-25.78%` $\rightarrow$ **`-24.63%`** |
| **All S&P Top-3 (`Next-Day Open`, `Self-Fin`)** | `2015–2026 ex-2022` | 129 | `28.78%` | **`29.86%`** | `29.75%` | **`+1.08%`** ✅ | `0.85` $\rightarrow$ **`0.88`** | `-25.76%` $\rightarrow$ **`-24.63%`** |
| **All S&P Top-3 (`Close`, vs `SPY`)** | `2010–2026 ex-2022` | 189 | `26.31%` | **`26.50%`** | `26.37%` | **`+0.19%`** ✅ | `0.84` $\rightarrow$ **`0.86`** | `-30.70%` $\rightarrow$ **`-28.39%`** |
| **All S&P Top-3 (`Next-Day Open`, `Additive`)** | `2010–2026 ex-2022` | 189 | `26.16%` | **`26.59%`** | `26.46%` | **`+0.43%`** ✅ | `0.85` $\rightarrow$ **`0.88`** | `-30.49%` $\rightarrow$ **`-28.73%`** |
| **All S&P Top-3 (`Next-Day Open`, `Self-Fin`)** | `2010–2026 ex-2022` | 189 | `26.14%` | **`26.57%`** | `26.46%` | **`+0.43%`** ✅ | `0.85` $\rightarrow$ **`0.88`** | `-30.47%` $\rightarrow$ **`-28.71%`** |
| **All S&P Top-1 (`Close`, vs `SPY`)** | `2015–2026 ex-2022` | 129 | `49.79%` | **`52.95%`** | `52.81%` | **`+3.16%`** ✅ | `0.96` $\rightarrow$ **`1.00`** | `-69.40%` $\rightarrow$ **`-57.25%`** |
| **All S&P Top-1 (`Next-Day Open`, `Additive`)** | `2015–2026 ex-2022` | 129 | `47.32%` | **`50.04%`** | `49.90%` | **`+2.72%`** ✅ | `0.93` $\rightarrow$ **`0.97`** | `-70.70%` $\rightarrow$ **`-58.49%`** |
| **All S&P Top-1 (`Next-Day Open`, `Self-Fin`)** | `2015–2026 ex-2022` | 129 | `47.28%` | **`50.01%`** | `49.90%` | **`+2.73%`** ✅ | `0.93` $\rightarrow$ **`0.97`** | `-70.67%` $\rightarrow$ **`-58.46%`** |
| **All S&P Top-1 (`Close`, vs `SPY`)** | `2010–2026 ex-2022` | 189 | `44.01%` | **`45.44%`** | `45.31%` | **`+1.43%`** ✅ | `0.94` $\rightarrow$ **`0.97`** | `-69.40%` $\rightarrow$ **`-57.25%`** |
| **Tech Top-1 (`Close`, vs `XLK`)** | `2010–2026 ex-2022` | 189 | `40.10%` | **`40.87%`** | `40.66%` | **`+0.77%`** ✅ | `0.90` $\rightarrow$ **`0.92`** | `-54.49%` $\rightarrow$ **`-47.61%`** |

---

### Test 2: Sub-Period Breakdown (`2010–2014`, `2015–2019`, `2020–2021`, `2022`, `2023–2026.09`)

#### A. All S&P Top-3 + `RS(6-0) > SPY` (`Close`, `Next-Day Open Additive`, & `Next-Day Open Self-Financing`)

| Sub-Period | Months | Close Baseline $\rightarrow$ `+RS(6-0)` | $\Delta$ (`Close`) | Open (`Additive`) Baseline $\rightarrow$ `+RS(6-0)` | $\Delta$ (`Open Add`) | Open (`Self-Fin`) Baseline $\rightarrow$ `+RS(6-0)` | $\Delta$ (`Open SF`) | Cash % |
|---|---|---|---|---|---|---|---|---|
| **2010–2014** | 60 | `20.94%` $\rightarrow$ `19.76%` | `-1.18%` | `20.65%` $\rightarrow$ `19.79%` | `-0.86%` | `20.63%` $\rightarrow$ `19.76%` | `-0.87%` | `4.4%` |
| **2015–2019** | 60 | `15.27%` $\rightarrow$ **`15.55%`** | **`+0.28%`** ✅ | `16.53%` $\rightarrow$ **`17.05%`** | **`+0.52%`** ✅ | `16.51%` $\rightarrow$ **`17.04%`** | **`+0.53%`** ✅ | `8.3%` |
| **2020–2021** | 24 | `12.76%` $\rightarrow$ **`13.28%`** | **`+0.52%`** ✅ | `10.70%` $\rightarrow$ **`11.90%`** | **`+1.20%`** ✅ | `10.68%` $\rightarrow$ **`11.89%`** | **`+1.21%`** ✅ | `5.6%` |
| **2022 (Single Year)** | 12 | `12.30%` $\rightarrow$ **`31.02%`** | **`+18.72%`** ✅ | `12.64%` $\rightarrow$ **`33.52%`** | **`+20.88%`** ✅ | `12.63%` $\rightarrow$ **`33.49%`** | **`+20.86%`** ✅ | `11.1%` |
| **2023–2026.09** | 45 | `60.63%` $\rightarrow$ **`62.84%`** | **`+2.21%`** ✅ | `59.62%` $\rightarrow$ **`61.56%`** | **`+1.94%`** ✅ | `59.57%` $\rightarrow$ **`61.51%`** | **`+1.94%`** ✅ | `3.7%` |

#### B. All S&P Top-1 + `RS(6-0) > SPY` (`Close-to-Close` & `Next-Day Open-to-Open`)

| Sub-Period | Months | Close Baseline $\rightarrow$ `+RS` | $\Delta$ (`Close`) | Open (`Additive`) Baseline $\rightarrow$ `+RS` | $\Delta$ (`Open Add`) | Open (`Self-Fin`) Baseline $\rightarrow$ `+RS` | $\Delta$ (`Open SF`) | Cash % |
|---|---|---|---|---|---|---|---|---|
| **2010–2014** | 60 | `32.33%` $\rightarrow$ `30.54%` | `-1.79%` | `38.67%` $\rightarrow$ `35.30%` | `-3.37%` | `38.65%` $\rightarrow$ `35.28%` | `-3.37%` | `3.3%` |
| **2015–2019** | 60 | `8.00%` $\rightarrow$ **`14.82%`** | **`+6.82%`** ✅ | `8.43%` $\rightarrow$ **`14.68%`** | **`+6.25%`** ✅ | `8.41%` $\rightarrow$ **`14.67%`** | **`+6.26%`** ✅ | `10.0%` |
| **2020–2021** | 24 | `43.41%` $\rightarrow$ `37.66%` | `-5.75%` | `32.29%` $\rightarrow$ `26.85%` | `-5.44%` | `32.24%` $\rightarrow$ `26.82%` | `-5.42%` | `4.2%` |
| **2022 (Single Year)** | 12 | `-9.92%` $\rightarrow$ **`35.50%`** | **`+45.42%`** ✅ | `-4.51%` $\rightarrow$ **`35.05%`** | **`+39.56%`** ✅ | `-4.43%` $\rightarrow$ **`35.08%`** | **`+39.51%`** ✅ | `8.3%` |
| **2023–2026.09** | 45 | `137.12%` $\rightarrow$ **`137.12%`** | **`0.00%`** | `134.79%` $\rightarrow$ **`134.79%`** | **`0.00%`** | `134.73%` $\rightarrow$ **`134.73%`** | **`0.00%`** | `0.0%` |

---

### Test 3: Untouched Cross-Universe & Cross-Sector OOS Verification

1. **Untouched OOS Test A — Non-Tech S&P 500 Universe (`sector != Information Technology`, vs `SPY`)**:
   - **Non-Tech S&P Top-3 + `RS(6-0) > SPY`**:
     - `2015–2026` (141m): CAGR `+1.00%` $\rightarrow$ **`+4.43%`** (**`+3.43%/yr`**), Sharpe `0.14` $\rightarrow$ **`0.23`**, MaxDD `-59.79%` $\rightarrow$ **`-57.30%`**.
     - `2015–2026 ex-2022` (129m): CAGR `-0.62%` $\rightarrow$ **`+1.62%`** (**`+2.24%/yr`**).
     - `2010–2026 ex-2022` (189m): CAGR `+3.74%` $\rightarrow$ **`+5.16%`** (**`+1.42%/yr`**).
   - **Non-Tech S&P Top-1 + `RS(6-0) > SPY`**:
     - `2015–2026` (141m): CAGR `-13.58%` $\rightarrow$ **`-8.10%`** (**`+5.48%/yr`**), MaxDD `-87.40%` $\rightarrow$ **`-83.79%`**.
     - `2015–2026 ex-2022` (129m): CAGR `-13.92%` $\rightarrow$ **`-11.36%`** (**`+2.56%/yr`**).

2. **Untouched OOS Test B — All 10 Non-Tech GICS Sectors Individually (`Top-1 + RS(6-0) > Own GICS Sector ETF`, `2015–2026`)**:
   - **8 / 10 (`80%`) non-tech sectors improved in CAGR; 7 / 10 (`70%`) improved or held flat in MaxDD**:

| GICS Sector | Sector ETF | Baseline Top-1 CAGR | `+RS(6-0)` CAGR | $\Delta$ CAGR | Baseline MaxDD $\rightarrow$ `+RS` MaxDD | $\Delta$ MaxDD | Cash % |
|---|---|---|---|---|---|---|---|
| **Health Care** | `XLV` | `-4.14%` | **`+4.61%`** | **`+8.75%`** ✅ | `-89.91%` $\rightarrow$ **`-63.94%`** | **`+25.97%`** | `9.2%` |
| **Financials** | `XLF` | `-10.23%` | **`-5.25%`** | **`+4.98%`** ✅ | `-80.64%` $\rightarrow$ **`-61.43%`** | **`+19.21%`** | `11.3%` |
| **Real Estate** | `XLRE` | `+13.36%` | **`+16.03%`** | **`+2.67%`** ✅ | `-30.75%` $\rightarrow$ **`-24.23%`** | **`+6.52%`** | `23.4%` |
| **Consumer Staples** | `XLP` | `+0.67%` | **`+2.72%`** | **`+2.05%`** ✅ | `-42.79%` $\rightarrow$ `-42.79%` | `0.00%` | `9.2%` |
| **Energy** | `XLE` | `+5.93%` | **`+7.45%`** | **`+1.52%`** ✅ | `-82.09%` $\rightarrow$ **`-77.02%`** | **`+5.07%`** | `16.3%` |
| **Industrials** | `XLI` | `+12.37%` | **`+13.41%`** | **`+1.04%`** ✅ | `-43.58%` $\rightarrow$ **`-41.31%`** | **`+2.27%`** | `5.7%` |
| **Materials** | `XLB` | `+9.27%` | **`+9.91%`** | **`+0.64%`** ✅ | `-48.77%` $\rightarrow$ **`-43.61%`** | **`+5.16%`** | `12.8%` |
| **Consumer Discretionary** | `XLY` | `-8.95%` | **`-8.74%`** | **`+0.21%`** ✅ | `-83.95%` $\rightarrow$ **`-83.43%`** | **`+0.52%`** | `8.5%` |
| **Utilities** | `XLU` | `+10.84%` | `+8.32%` | `-2.52%` | `-44.61%` $\rightarrow$ `-51.83%` | `-7.22%` | `14.9%` |
| **Communication Services** | `XLC` | `+4.82%` | `-6.92%` | `-11.74%` | `-66.84%` $\rightarrow$ `-75.87%` | `-9.03%` | `44.0%` |

---

## 5. Complete List of All 8 Intercepted Months in All S&P Top-1 (`2015-01..2026-09`)

| Holding Month | Formation Date | Intercepted Stock | Sector | `Mom(12-1)` | Stock `RS(6-0)` | `SPY RS(6-0)` | Avoided Next-Month Return (`Close`) | Avoided Next-Month Return (`Open`) |
|---|---|---|---|---|---|---|---|---|
| `2016-04` | `2016-03-31` | `CVC` | Consumer Discretionary | `+79.88%` | `+1.63%` | `+8.44%` | `+1.18%` | `+1.26%` |
| `2018-07` | `2018-06-30` | `NKTR` | Health Care | `+310.61%` | `-18.24%` | `+2.52%` | `+7.72%` | `+8.17%` |
| `2018-09` | `2018-08-31` | `NKTR` | Health Care | `+150.11%` | `-23.19%` | `+7.78%` | **`-8.32%`** | **`-6.64%`** |
| `2018-10` | `2018-09-30` | `NKTR` | Health Care | `+176.96%` | `-42.63%` | `+11.48%` | **`-36.55%`** | **`-36.93%`** |
| `2019-03` | `2019-02-28` | `AMD` | Information Technology | `+101.64%` | `-6.52%` | `-3.01%` | `+8.46%` | `+6.29%` |
| `2019-04` | `2019-03-31` | `AMD` | Information Technology | `+134.06%` | `-17.38%` | `-1.84%` | `+8.27%` | `+4.82%` |
| `2021-06` | `2021-05-31` | `TSLA` | Consumer Discretionary | `+324.80%` | `+10.15%` | `+16.89%` | `+8.71%` | `+7.77%` |
| `2022-01` | `2021-12-31` | `MRNA` | Health Care | `+237.44%` | `+8.09%` | `+11.70%` | **`-33.33%`** | **`-32.33%`** |

---

## 6. Frozen Live Signal Verification for November 2026 (`Formation = 2026-10-30`)

- **Benchmark `RS(6-0)` (`2026-04-30` $\rightarrow$ `2026-10-30`)**:
  - **`SPY`**: **`+7.10%`**
  - **`XLK`**: **`+18.80%`**

| `12-1` Rank | Ticker | `2025-10-31` Close | `2026-04-30` Close | `2026-09-30` Close | `2026-10-30` Close | Oct 2026 Return | `Mom(12-1)` | `RS(6-0)` | `SMA200` (`2026-10-30`) | vs `SPY (+7.10%)` | vs `SMA200` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **#1** | **`SNDK`** | `\$199.33` | `\$1,096.46` | `\$1,739.89` | `\$1,150.89` | `-33.85%` | `+772.87%` | **`+4.96%`** | `\$1,259.17` | ❌ **FAIL $\rightarrow$ `CASH`** | ❌ **Below $\rightarrow$ Pass-Down** |
| **#2** | **`MRNA`** | `\$27.16` | `\$45.94` | `\$192.57` | `\$221.72` | `+15.14%` | `+609.02%` | **`+382.63%`** | `\$104.22` | ✅ **PASS $\rightarrow$ BUY** | ✅ **Above $\rightarrow$ BUY** |
| **#3** | **`LITE`** | `\$201.56` | `\$902.31` | `\$971.26` | `\$840.70` | `-13.44%` | `+381.87%` | **`-6.83%`** | `\$827.57` | ❌ **FAIL $\rightarrow$ `CASH`** | ✅ Above |
| **#4** | **`MU`** | `\$223.56` | `\$517.00` | `\$1,064.94` | `\$884.74` | `-16.92%` | `+376.36%` | **`+71.13%`** | `\$774.29` | ✅ **PASS $\rightarrow$ BUY** | ✅ Above |

- **Frozen November 2026 Allocations**:
  1. **`All S&P Top-3 + RS(6-0) > SPY`**: **`1/3 MRNA + 2/3 CASH`**
  2. **`All S&P Top-1 + RS(6-0) > SPY`**: **`100% CASH`**
  3. **`All S&P Top-1 + SMA200 (Pass-Down)`**: **`100% MRNA`** (`SNDK` Close `\$1,150.89 < SMA200 \$1,259.17`)
  4. **`Tech Top-1 + RS(6-0) > XLK`**: **`100% CASH`**
