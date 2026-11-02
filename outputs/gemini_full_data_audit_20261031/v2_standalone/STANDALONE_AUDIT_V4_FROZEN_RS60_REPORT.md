# Standalone Clean-Room Audit Report (v4): Frozen Stall-Detector Rule `12-1 Momentum + RS(6-0) > Benchmark (else CASH)`

- **Audit Date**: `2026-11-02`
- **Auditor Script**: `outputs/gemini_full_data_audit_20261031/v2_standalone/v2_06_frozen_rs60_cleanroom_auditor.py`
- **Summary JSON**: `outputs/gemini_full_data_audit_20261031/v2_standalone/v2_06_frozen_rs60_cleanroom_summary.json`
- **AST & Read-Only Guard**: `outputs/gemini_full_data_audit_20261031/v2_standalone/v2_00_cleanroom_ast_and_readonly_guard.py` (`8/8` scripts checked, `total_ast_or_pattern_violations = 0`, `10,964/10,964` baseline files untouched)

---

## 1. Executive Summary & Clean-Room Verification Guarantees

1. **Zero Project Imports & Zero Derived Panel Reads (`v2_00` Mechanically Enforced)**
   - `v2_06_frozen_rs60_cleanroom_auditor.py` imports **zero** project modules (`backtest`, `ml2_run`, `winners_tracks`, `tech_only`, `sma200_overlay`, `historical_sectors`, `ticker_aliases` are all blocked by AST inspection).
   - It reads **zero** derived panels (`panel.parquet`, `panel_ml2.parquet`, `ticker_aliases_used.csv`, `cik_map.csv`) and **zero** ledger cost/cash columns (`turnover`, `capital_after_costs`, `cash_return`).
   - All `99,949` eligible S&P 500 ticker-months across `201` formation months (`2009-12-31..2026-08-31` -> holding months `2010-01..2026-09`) are reconstructed from scratch using raw JSON prices/opens (`data/raw/*.json`, `data/raw_open/*.json`, `data/raw_tiingo/*.json`, `data/raw_wiki/*.json`), raw SEC FSDS `sub_*.parquet`, raw PIT S&P 500 membership (`sp500_hist_components.csv`), and raw FRED 3M T-Bill yields (`DGS3MO.json`).

2. **Exact Parity with v3 Audited `Pure Momentum Top-3` (`27.33%` / `27.35%` Baseline)**
   - Before applying the `RS(6-0) > SPY` gate, our Clean-Room simulator (`simulate_cleanroom_rs_strategy`) reproduces the audited `monthly_BENCH_momentum_Top3.csv` ledger across all **141/141 months (`2015-01..2026-09`)** with:
     - **Pick-set exact matches**: `141 / 141` (`100.0%`)
     - **Max gross return difference**: `9.95e-17`
     - **Max net return difference**: `2.22e-16`
     - **External BlackRock iShares `IVV` S&P 500 Holdings confirmation**: `404 / 405` (`99.75%`)

3. **Both Execution Engines & Both Cash Cost Models Verified**
   - **Engine A (Close-to-Close, Fixed Equal-Weight Rebalance)**: Signal at month-end `t` close, return `Close[t+1] / Close[t] - 1`.
   - **Engine B (Next-Day Open-to-Open, Drifted-Weight Rebalance)**: Signal at month-end `t` close (`RS(6-0) = Close[t] / Close[t-6] - 1`), execution at **next trading day's Open (`Open[t+1_day1]`)**, eliminating any same-bar overlap between `Close[t]` in `RS(6-0)` and the entry price.
   - **Cash Cost Model 1 (`Cash 0bp`)**: `10bp` per side on stock buys/sells; `0bp` on T-bill cash sweep.
   - **Cash Cost Model 2 (`Cash ETF 10bp`)**: `10bp` per side on both stocks AND T-bill ETF (`Stock <-> Cash ETF = 20bp`).

---

## 2. Core Audit Results: `12-1 Momentum + RS(6-0) > Benchmark (else CASH)`

### Table 2A — Full Audited Test Window (`2015-01..2026-09`, 141 Months)

| Strategy & Execution Engine | Baseline CAGR | `+RS(6-0)` (`Cash 0bp`) | `+RS(6-0)` (`Cash ETF 10bp`) | $\Delta$ CAGR (`0bp`) | Baseline $\rightarrow$ `+RS` Sharpe | Baseline $\rightarrow$ `+RS` MaxDD | Avg Cash % |
|---|---|---|---|---|---|---|---|
| **All S&P Top-3 (`Close-to-Close`, vs `SPY`)** | `27.38%` | **`29.87%`** | `29.73%` | **`+2.49%`** | `0.78` $\rightarrow$ **`0.85`** | `-30.70%` $\rightarrow$ **`-26.02%`** | `6.6%` |
| **All S&P Top-3 (`Next-Day Open`, vs `SPY`)** | `27.35%` | **`30.19%`** | `30.06%` | **`+2.84%`** | `0.79` $\rightarrow$ **`0.87`** | `-25.78%` $\rightarrow$ **`-24.63%`** | `6.6%` |
| **All S&P Top-1 (`Close-to-Close`, vs `SPY`)** | `43.44%` | **`51.38%`** | `51.23%` | **`+7.94%`** | `0.88` $\rightarrow$ **`0.99`** | `-69.40%` $\rightarrow$ **`-57.25%`** | `5.7%` |
| **All S&P Top-1 (`Next-Day Open`, vs `SPY`)** | `41.99%` | **`48.71%`** | `48.56%` | **`+6.72%`** | `0.86` $\rightarrow$ **`0.96`** | `-70.70%` $\rightarrow$ **`-58.49%`** | `5.7%` |
| **Tech Top-1 (`Close-to-Close`, vs `XLK`)** | `60.03%` | **`60.46%`** | `60.22%` | **`+0.43%`** | `1.11` $\rightarrow$ **`1.13`** | `-46.57%` $\rightarrow$ `-46.57%` | `9.2%` |
| **All S&P Top-1 + SMA200 (`Close`, vs `SPY`)** | **`52.04%`** | `48.83%` | `48.75%` | `-3.21%` | `0.99` $\rightarrow$ `0.95` | `-62.29%` $\rightarrow$ `-62.29%` | `2.8%` |

---

## 3. The Three Reviewer Stress & Validation Tests

### Test 1: Removing 2022 Entirely (`Ex-2022` Verification)

| Strategy & Execution Engine | Window (Ex-2022) | Months | Baseline CAGR | `+RS(6-0)` (`0bp`) | `+RS(6-0)` (`10bp`) | $\Delta$ CAGR (`0bp`) | Baseline $\rightarrow$ `+RS` Sharpe | Baseline $\rightarrow$ `+RS` MaxDD |
|---|---|---|---|---|---|---|---|---|
| **All S&P Top-3 (`Close`, vs `SPY`)** | `2015–2026 ex-2022` | 129 | `28.89%` | **`29.76%`** | `29.63%` | **`+0.87%`** ✅ | `0.83` $\rightarrow$ **`0.86`** | `-30.70%` $\rightarrow$ **`-26.02%`** |
| **All S&P Top-3 (`Next-Day Open`, vs `SPY`)** | `2015–2026 ex-2022` | 129 | `28.81%` | **`29.89%`** | `29.75%` | **`+1.08%`** ✅ | `0.85` $\rightarrow$ **`0.88`** | `-25.78%` $\rightarrow$ **`-24.63%`** |
| **All S&P Top-3 (`Close`, vs `SPY`)** | `2010–2026 ex-2022` | 189 | `26.31%` | **`26.49%`** | `26.37%` | **`+0.18%`** ✅ | `0.84` $\rightarrow$ **`0.86`** | `-30.70%` $\rightarrow$ **`-28.39%`** |
| **All S&P Top-3 (`Next-Day Open`, vs `SPY`)** | `2010–2026 ex-2022` | 189 | `26.16%` | **`26.59%`** | `26.46%` | **`+0.43%`** ✅ | `0.85` $\rightarrow$ **`0.88`** | `-30.49%` $\rightarrow$ **`-28.73%`** |
| **All S&P Top-1 (`Close`, vs `SPY`)** | `2015–2026 ex-2022` | 129 | `49.79%` | **`52.95%`** | `52.81%` | **`+3.16%`** ✅ | `0.96` $\rightarrow$ **`1.00`** | `-69.40%` $\rightarrow$ **`-57.25%`** |
| **All S&P Top-1 (`Next-Day Open`, vs `SPY`)** | `2015–2026 ex-2022` | 129 | `47.33%` | **`50.05%`** | `49.91%` | **`+2.72%`** ✅ | `0.94` $\rightarrow$ **`0.98`** | `-70.70%` $\rightarrow$ **`-58.49%`** |
| **All S&P Top-1 (`Close`, vs `SPY`)** | `2010–2026 ex-2022` | 189 | `44.01%` | **`45.44%`** | `45.31%` | **`+1.43%`** ✅ | `0.94` $\rightarrow$ **`0.97`** | `-69.40%` $\rightarrow$ **`-57.25%`** |
| **Tech Top-1 (`Close`, vs `XLK`)** | `2010–2026 ex-2022` | 189 | `40.10%` | **`40.87%`** | `40.66%` | **`+0.77%`** ✅ | `0.90` $\rightarrow$ **`0.92`** | `-54.49%` $\rightarrow$ **`-47.61%`** |

---

### Test 2: Sub-Period Breakdown (`2010–2014`, `2015–2019`, `2020–2021`, `2022`, `2023–2026.09`)

#### A. All S&P Top-3 + `RS(6-0) > SPY` (Both Close-to-Close & Next-Day Open-to-Open)

| Sub-Period | Months | Close Baseline $\rightarrow$ `+RS(6-0)` | $\Delta$ CAGR (`Close`) | Next-Day Open Baseline $\rightarrow$ `+RS(6-0)` | $\Delta$ CAGR (`Open`) | Cash % |
|---|---|---|---|---|---|---|
| **2010–2014** | 60 | `20.93%` $\rightarrow$ `19.75%` | `-1.18%` | `20.65%` $\rightarrow$ `19.79%` | `-0.86%` | `4.4%` |
| **2015–2019** | 60 | `15.27%` $\rightarrow$ **`15.55%`** | **`+0.28%`** ✅ | `16.53%` $\rightarrow$ **`17.05%`** | **`+0.52%`** ✅ | `8.3%` |
| **2020–2021** | 24 | `12.76%` $\rightarrow$ **`13.28%`** | **`+0.52%`** ✅ | `10.70%` $\rightarrow$ **`11.90%`** | **`+1.20%`** ✅ | `5.6%` |
| **2022 (Single Year)** | 12 | `12.30%` $\rightarrow$ **`31.02%`** | **`+18.72%`** ✅ | `12.64%` $\rightarrow$ **`33.52%`** | **`+20.88%`** ✅ | `11.1%` |
| **2023–2026.09** | 45 | `60.63%` $\rightarrow$ **`62.84%`** | **`+2.21%`** ✅ | `59.62%` $\rightarrow$ **`61.56%`** | **`+1.94%`** ✅ | `3.7%` |

#### B. All S&P Top-1 + `RS(6-0) > SPY` (Close-to-Close)

| Sub-Period | Months | Baseline CAGR | `+RS(6-0)` CAGR | $\Delta$ CAGR | Baseline $\rightarrow$ `+RS` Sharpe | Baseline $\rightarrow$ `+RS` MaxDD | Cash % |
|---|---|---|---|---|---|---|---|
| **2010–2014** | 60 | `32.33%` | `30.54%` | `-1.79%` | `0.98` $\rightarrow$ `0.94` | `-43.49%` $\rightarrow$ **`-42.27%`** | `3.3%` |
| **2015–2019** | 60 | `8.00%` | **`14.82%`** | **`+6.82%`** ✅ | `0.39` $\rightarrow$ **`0.52`** | `-69.40%` $\rightarrow$ **`-57.25%`** | `10.0%` |
| **2020–2021** | 24 | `43.41%` | `37.66%` | `-5.75%` | `1.20` $\rightarrow$ `1.08` | `-25.84%` $\rightarrow$ `-25.91%` | `4.2%` |
| **2022 (Single Year)** | 12 | `-9.92%` | **`35.50%`** | **`+45.42%`** ✅ | `0.13` $\rightarrow$ **`0.79`** | `-25.20%` $\rightarrow$ `-25.20%` | `8.3%` |
| **2023–2026.09** | 45 | `137.12%` | **`137.12%`** | **`0.00%`** | `1.48` $\rightarrow$ `1.48` | `-46.57%` $\rightarrow$ `-46.57%` | `0.0%` |

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

## 4. Complete List of All 8 Intercepted Months in All S&P Top-1 (`2015-01..2026-09`)

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

## 5. Frozen Live Signal Verification for November 2026 (`Formation = 2026-10-30`)

- **Benchmark `RS(6-0)` (`2026-04-30` $\rightarrow$ `2026-10-30`)**:
  - **`SPY`**: **`+7.10%`**
  - **`XLK`**: **`+18.80%`**

| `12-1` Rank | Ticker | `2025-10-31` Close | `2026-04-30` Close | `2026-09-30` Close | `2026-10-30` Close | Oct 2026 Return | `Mom(12-1)` | `RS(6-0)` | vs `SPY (+7.10%)` | vs `XLK (+18.80%)` |
|---|---|---|---|---|---|---|---|---|---|---|
| **#1** | **`SNDK`** | `\$199.33` | `\$1,096.46` | `\$1,739.89` | `\$1,150.89` | `-33.85%` | `+772.87%` | **`+4.96%`** | ❌ **FAIL $\rightarrow$ `CASH`** | ❌ **FAIL $\rightarrow$ `CASH`** |
| **#2** | **`MRNA`** | `\$27.16` | `\$45.94` | `\$192.57` | `\$221.72` | `+15.14%` | `+609.02%` | **`+382.63%`** | ✅ **PASS $\rightarrow$ BUY** | N/A (Health Care) |
| **#3** | **`LITE`** | `\$201.56` | `\$902.31` | `\$971.26` | `\$840.70` | `-13.44%` | `+381.87%` | **`-6.83%`** | ❌ **FAIL $\rightarrow$ `CASH`** | ❌ **FAIL $\rightarrow$ `CASH`** |
| **#4** | **`MU`** | `\$223.56` | `\$517.00` | `\$1,064.94` | `\$884.74` | `-16.92%` | `+376.36%` | **`+71.13%`** | ✅ **PASS $\rightarrow$ BUY** | ✅ **PASS $\rightarrow$ BUY** |

- **Frozen November 2026 Allocations**:
  1. **`All S&P Top-3 + RS(6-0) > SPY`**: **`1/3 MRNA + 2/3 CASH`**
  2. **`All S&P Top-1 + RS(6-0) > SPY`**: **`100% CASH`**
  3. **`All S&P Top-1 + SMA200`**: **`100% MRNA`** (`SNDK` Close `\$1,150.89 < SMA200 \$1,259.17`)
  4. **`Tech Top-1 + RS(6-0) > XLK`**: **`100% CASH`**
