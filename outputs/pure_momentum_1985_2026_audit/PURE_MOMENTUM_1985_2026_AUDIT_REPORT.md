# 1985–2026 Pure Momentum, Delisted Stocks, `{SPY, DIA, QQQ}` & Sector Lookback Audit Report

**Audit Date**: 2026-11-07  
**Audit Folder**: `outputs/pure_momentum_1985_2026_audit/`  
**Included Files in Bundle**:
- [`PURE_MOMENTUM_1985_2026_AUDIT_REPORT.md`](./PURE_MOMENTUM_1985_2026_AUDIT_REPORT.md) (This Report)
- [`run_pure_momentum_1985_2026_audit.py`](./run_pure_momentum_1985_2026_audit.py) (Standalone Reproducible Script)
- [`01_era_pit_certification_summary.csv`](./01_era_pit_certification_summary.csv) (3-Era PIT Certification Grading Table)
- [`summary_2009_2026_strict_pit.csv`](./summary_2009_2026_strict_pit.csv) (Era 3: 214m `100.0%` Strict PIT Certified Summary)
- [`summary_1997_2026_pit_sp500.csv`](./summary_1997_2026_pit_sp500.csv) (Era 2+3: 358m Historical S&P 500 Membership Summary)
- [`summary_1985_2026.csv`](./summary_1985_2026.csv) (Era 1+2+3: 502m Long-Horizon Illustrative Extension Summary)
- [`monthly_returns_1985_2026_shumway.csv`](./monthly_returns_1985_2026_shumway.csv) (502-Month Return Ledger across all 15 strategies)
- [`03_spy_dia_qqq_rotation_audit.csv`](./03_spy_dia_qqq_rotation_audit.csv) (`{SPY, DIA, QQQ}` Real ETF `2000-04..2026-10` vs Cash Index `1993-02..2026-10` Audit)
- [`04_sector_lookback_grid_audit.csv`](./04_sector_lookback_grid_audit.csv) (All 9 Select Sector SPDR ETFs `XLB..XLY` `2000-01..2026-10` Complete `322m` Lookback Grid)
- [`FROZEN_STRATEGY_SPEC.md`](../../FROZEN_STRATEGY_SPEC.md) & [`independent_a1_rs_election_reset_audit.py`](../../independent_a1_rs_election_reset_audit.py) (Frozen `A1-RS 1.35x + V3 Election Reset` Spec & Zero-Shared-Code Engine)

---

## 0. Direct Response to the 8 External Audit Checklist Items

To prevent any overstatement of pre-2009 backtest results, we explicitly grade our own dataset across the 8 audit criteria (`01_era_pit_certification_summary.csv`):

| Audit Item | Era 1: `1985-01..1996-12` (144m) | Era 2: `1997-01..2008-12` (144m) | Era 3: `2009-01..2026-10` (214m — Frozen V3 Window) |
| :--- | :--- | :--- | :--- |
| **1. Prices, Splits, Dividends & Delistings** | **Incomplete Delistings**: Single-source `WIKI_PRICES` (`adj_close`), Shumway `-30%/-50%` penalty on observed terminal exits, but pre-2010 delistings prior to WIKI creation are missing. | **Partial Delistings (`68.4%`)**: `587 / 858` historical S&P 500 tickers present on disk (`WIKI` + `Tiingo` + `Archive`); `271` pre-2008 delisted/merged tickers missing. | **PASS (`100.0%` Complete)**: All `868` historical S&P 500 tickers (`503` active + `365` delisted/acquired/removed) verified via `Yahoo` + `Tiingo` + `WIKI` + `Archive` + `exit_resolutions.csv`. |
| **2. `1985–1996` Membership** | **FAIL / NOT PIT-CERTIFIED**: `sp500_hist_components.csv` begins `1996-01-02`. Uses `WIKI` `close >= $5` Top-500 dollar volume at formation `t` (subject to pre-2010 WIKI survivorship bias). | N/A | N/A |
| **3. `1997–2026` PIT S&P 500 Membership** | N/A | **PARTIAL PIT**: True historical S&P 500 membership (`sp500_hist_components.csv`), `68.4%` (`587/858`) price coverage (`~365` stocks/month). | **PASS (`100.0%` Strict PIT)**: `868 / 868` S&P 500 tickers + PIT Nasdaq-100 (`~495` eligible S&P 500 stocks/month). |
| **4. `SPY / DIA / QQQ` Pre-Launch Integrity** | **PASS**: Real ETF rotation (`03_spy_dia_qqq_rotation_audit.csv` Panel A) strictly starts **`2000-04` (`319m`)**, after `QQQ` (`1999-03-10`) completes 12m history. Cash index panel (`Panel B`) strictly starts **`1993-02` (`405m`)** after `^DJI` (`1992-01-02`) completes 12m history. Zero pre-launch backfilling or splicing. | **PASS** | **PASS** |
| **5. Historical Sector Classification** | **FAIL (Static Back-Mapping)**: GICS was created in 1999; mapping modern GICS labels to `1985–1998` has static classification look-ahead. | **HYBRID**: Static/historical GICS on stock panels; **PASS (`0%` look-ahead)** on actual traded Select Sector SPDR ETFs (`XLB..XLY`, launched `1998-12-22`, `322m` `2000-01..2026-10`). | **PASS (`100%` Repaired PIT GICS)**: Uses `historical_sectors.py` + `build_repaired_pit_gics_tables()` (all 8 external audit items remediated). |
| **6. Execution & `10 bp/side` Drifted Cost** | Monthly `Close-to-Close` + single-account drifted turnover (`10 bp/side` = `0.10%` one-way). | Monthly `Close-to-Close` + single-account drifted turnover (`10 bp/side`). | **PASS**: Strictly Next-Month First Trading Day **`Open-to-Open` (`d0 Open -> d1 Open`)** + single-account drifted turnover (`10 bp/side`). |
| **7. `Election V3` (`2010, 2018, 2022`)** | Out-of-sample pre-2009 `Unified -> Divided` Midterm flips (`1994-12`, `2006-12`) tested below (`+0.77%/yr` to `+1.95%/yr` full-period improvement). | Out-of-sample `2006-12` included. | Structural political science rule (`Unified -> Divided` Midterm flip: `2010, 2018, 2022` vs non-flip `2014` placebo). **Frozen V3 remains unchanged.** |
| **8. Independent Code & Monthly Reconciliation** | Reproducible via `run_pure_momentum_1985_2026_audit.py` and `monthly_returns_1985_2026_shumway.csv`. | Same. | Zero-shared-code engine (`independent_a1_rs_election_reset_audit.py`) matches month-by-month across all 214 months. |

---

## 1. Era-by-Era Pure Momentum Results (With Drifted `10 bp/side` Turnover Cost)

| Strategy | **Era 3: `2009–2026` (214m)**<br>**100.0% Strict PIT Certified**<br>*(CAGR / Sharpe / MaxDD)* | **Era 2+3: `1997–2026` (358m)**<br>**Partial PIT 97–08 + Strict PIT 09–26**<br>*(CAGR / Sharpe / MaxDD)* | **Era 1+2+3: `1985–2026` (502m)**<br>**Illustrative Non-PIT Pre-1997**<br>*(CAGR / Sharpe / MaxDD)* |
| :--- | :---: | :---: | :---: |
| `SP500_Index` (`^GSPC`) | `12.67%` / `0.88` / `-24.77%` | `8.11%` / `0.59` / `-52.56%` | `9.55%` / `0.68` / `-52.56%` |
| `EW_Universe` | `14.65%` / `0.88` / `-30.61%` | `11.38%` / `0.71` / `-55.65%` | `13.35%` / `0.83` / `-55.65%` |
| `EW_Sectors` | `13.89%` / `0.86` / `-30.77%` | `11.73%` / `0.76` / `-50.91%` | `14.06%` / `0.90` / `-50.91%` |
| `Sec_12_1_Top1_Hard` | `16.11%` / `0.81` / `-28.99%` | `15.47%` / `0.72` / `-57.60%` | `18.79%` / `0.85` / `-57.60%` |
| `Sec_12_1_Top1_H3` | `16.29%` / `0.82` / `-35.32%` | `14.15%` / `0.68` / `-58.86%` | `17.84%` / `0.82` / `-58.86%` |
| `Sec_12_1_Top2` | `14.29%` / `0.87` / `-23.94%` | `13.46%` / `0.78` / `-52.76%` | `16.98%` / `0.93` / `-52.76%` |
| `Stock_12_1_Top10` | `14.20%` / `0.64` / `-34.62%` | `12.40%` / `0.55` / `-74.06%` | `17.42%` / `0.71` / `-74.06%` |
| `Stock_12_1_Top5` | `17.58%` / `0.69` / `-31.86%` | `14.37%` / `0.57` / `-77.01%` | `19.38%` / `0.71` / `-77.01%` |
| `Stock_12_1_Top2_H5` | `24.89%` / `0.78` / `-37.96%` | `13.29%` / `0.51` / `-90.60%` | `18.54%` / `0.63` / `-90.60%` |
| `Stock_12_1_Top1_Hard` | `31.12%` / `0.78` / `-70.70%` | `19.03%` / `0.58` / `-98.41%` | `25.04%` / `0.67` / `-98.41%` |
| `Stock_12_1_Top1_H3` | **`37.74%`** / **`0.94`** / `-44.69%` | `18.61%` / `0.58` / `-97.70%` | `28.41%` / `0.73` / `-97.70%` |
| `Stock_Sharpe_Top2_H5` | `13.42%` / `0.56` / `-48.72%` | `10.99%` / `0.47` / `-83.40%` | `15.92%` / `0.60` / `-83.40%` |
| `Tech_Top1_Hard` | **`38.30%`** / **`0.91`** / `-55.29%` | **`30.83%`** / `0.76` / `-93.33%` | **`40.35%`** / `0.90` / `-93.33%` |
| `BestSec_Stock_Top1_H3` | `11.74%` / `0.47` / `-59.03%` | `12.85%` / `0.49` / `-89.18%` | `27.15%` / `0.73` / `-89.18%` |
| `Pure_3Leg_Core_1x` | **`28.17%`** / **`0.93`** / `-39.02%` | **`21.08%`** / **`0.69`** / `-84.69%` | **`28.68%`** / **`0.87`** / `-84.69%` |

---

## 2. Quantifying Delisted Stock & Survivorship Bias on the 100% PIT `2009–2026` Panel (`868` Total vs `503` Surviving)

| Strategy (`2009-01` to `2026-10`, 214m) | **100.0% PIT (`868` Tickers, Incl. `365` Delisted/Exited)** | **Survivors-Only (`503` Tickers Alive in `2026-10`)** | **True Delisting / Exit Impact** |
| :--- | :---: | :---: | :---: |
| `Equal-Weight S&P 500` | **14.65%** | 16.71% | **-2.06% / yr** (Survivorship inflates EW by +2.06%/yr) |
| `Stock 12-1m Top-10 EW` | **14.20%** (Sharpe `0.64`) | 21.00% (Sharpe `0.88`) | **-6.80% / yr** (`Top-10` underperforms EW once delisted/removed stocks are included!) |
| `Stock 12-1m Top-5 EW` | **17.58%** (Sharpe `0.69`) | 21.90% (Sharpe `0.80`) | **-4.32% / yr** |
| `Stock 12-1m Top-1 Hard` | **31.12%** (Sharpe `0.78`) | 37.61% (Sharpe `0.90`) | **-6.49% / yr** |
| `Stock 12-1m Top-1 (Hold<=3)` | **37.74%–40.62%** (Sharpe `0.94–0.99`) | 30.03% (Sharpe `0.82`) | **+7.71% to +10.59% / yr** (Acquired M&A winners like `GMCR`, `ENDP`, `SWY` were true Rank-1 leaders before buyout) |

---

## 3. `{SPY, DIA, QQQ}` Rotation Audit (`03_spy_dia_qqq_rotation_audit.csv` — Zero Pre-Launch Backfill)

### Panel A: 100% Real Tradable ETFs `{SPY, DIA, QQQ}` (`2000-04` to `2026-10`, `319` Months)
*(Starts `2000-04`, the exact first month after `QQQ` [launched `1999-03-10`] has a complete 12-month formation window)*

| Strategy | Months | Pure CAGR | Pure Sharpe | Pure MaxDD | `+Avoid SEP&Elec` CAGR | `+Avoid SEP&Elec` Sharpe | `+Avoid SEP&Elec` MaxDD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `Buy&Hold SPY` | 319 | 6.26% | 0.48 | -52.20% | 6.60% | 0.54 | -55.04% |
| `Buy&Hold DIA` | 319 | 6.02% | 0.48 | **-49.08%** | 6.23% | 0.53 | **-49.08%** |
| `Buy&Hold QQQ` | 319 | **7.17%** | 0.42 | -79.61% | **9.50%** | 0.55 | -79.61% |
| `Equal-Weight {SPY, DIA, QQQ}` | 319 | 6.77% | **0.49** | -56.29% | 7.67% | 0.57 | -58.02% |
| `Best-1 1m` | 319 | 6.29% | 0.43 | -67.97% | 6.68% | 0.48 | -61.50% |
| `Best-1 3m` | 319 | 6.81% | 0.46 | -59.65% | 9.03% | 0.63 | -54.73% |
| `Best-1 6m (6-0m)` | 319 | 7.36% | 0.49 | -59.40% | 9.58% | 0.66 | -59.40% |
| `Best-1 6-1m` | 319 | 7.51% | 0.50 | -60.59% | 9.67% | 0.67 | -60.59% |
| `Best-1 12-0m` | 319 | 7.65% | 0.49 | -56.04% | 9.71% | 0.64 | -56.18% |
| `Best-1 12-1m` | 319 | 6.90% | 0.45 | -66.84% | 9.26% | 0.61 | -65.28% |

### Panel B: Cash Indices `{^GSPC, ^DJI, ^IXIC}` (`1993-02` to `2026-10`, `405` Months — Zero Splicing)
*(Starts `1993-02`, the first month after `_DJI.json` [`1992-01-02`] has a complete 12-month formation window)*

| Strategy | Months | Pure CAGR | Pure Sharpe | Pure MaxDD | `+Avoid SEP&Elec` CAGR | `+Avoid SEP&Elec` Sharpe | `+Avoid SEP&Elec` MaxDD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `Buy&Hold ^GSPC` | 405 | 8.81% | 0.65 | -52.56% | 8.91% | 0.71 | -55.66% |
| `Buy&Hold ^DJI` | 405 | 8.49% | 0.63 | **-49.30%** | 8.55% | 0.70 | **-49.30%** |
| `Buy&Hold ^IXIC` | 405 | **11.25%** | 0.61 | -75.05% | **12.10%** | 0.70 | -72.14% |
| `Equal-Weight {^GSPC, ^DJI, ^IXIC}` | 405 | 9.74% | **0.66** | -52.88% | 10.01% | **0.74** | -54.81% |
| `Best-1 1m` | 405 | 8.99% | 0.57 | -64.06% | 8.51% | 0.60 | -61.03% |
| `Best-1 3m` | 405 | 9.92% | 0.63 | -59.48% | 10.80% | 0.76 | -55.22% |
| `Best-1 6m (6-0m)` | 405 | 7.99% | 0.52 | -65.81% | 8.54% | 0.61 | -58.40% |
| `Best-1 6-1m` | 405 | 8.67% | 0.55 | -62.29% | 9.43% | 0.66 | -61.94% |
| `Best-1 12-0m` | 405 | 10.19% | 0.61 | -62.76% | 10.81% | 0.71 | -60.56% |
| `Best-1 12-1m` | 405 | 9.01% | 0.55 | -67.75% | 9.52% | 0.64 | -65.18% |

---

## 4. Complete 9-ETF Select Sector SPDR Lookback Grid (`2000-01` to `2026-10`, `322/322` Months, `04_sector_lookback_grid_audit.csv`)
*(All 9 original SPDR Sector ETFs `XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY` have complete daily history from `1998-12-22` to `2026-10-30`; 0% GICS look-ahead)*

| Lookback Horizon | Months | `Top-1 Hard` CAGR | `Top-1 Hard` Sharpe | `Top-1 Hard` MaxDD | `Top-1 Hold<=3` CAGR | `Top-1 Hold<=3` Sharpe | `Top-1 Hold<=3` MaxDD | `Top-2 EW` CAGR | `Top-2 EW` Sharpe | `Top-2 EW` MaxDD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Equal-Weight 9 SPDR ETFs`** | 322 | **6.78%** | **0.52** | -50.61% | **6.78%** | **0.52** | -50.61% | **6.78%** | **0.52** | -50.61% |
| `1m (1-0m)` | 322 | 2.92% | 0.24 | -63.95% | 4.27% | 0.31 | -57.73% | 2.53% | 0.23 | -67.53% |
| `2m (2-0m)` | 322 | 2.75% | 0.24 | -54.81% | 2.45% | 0.22 | -53.47% | 3.85% | 0.32 | -46.49% |
| `3m (3-0m)` | 322 | 2.68% | 0.23 | -71.80% | 3.93% | 0.30 | -66.74% | 5.26% | 0.40 | -53.74% |
| `4m (4-0m)` | 322 | 3.89% | 0.30 | -60.84% | 3.68% | 0.29 | -48.71% | 4.74% | 0.38 | -46.59% |
| **`6m (6-0m)`** 🏆 | 322 | 6.76% | 0.44 | -48.34% | **8.53%** | **0.51** | **-42.65%** | 6.46% | 0.47 | -44.13% |
| **`6-1m (Skip 1m)`** 🏆 | 322 | **7.02%** | **0.45** | **-44.74%** | 6.82% | 0.43 | -43.33% | **6.81%** | **0.50** | **-39.68%** |
| `9m (9-0m)` | 322 | 4.63% | 0.32 | -55.75% | 7.42% | 0.45 | -47.35% | 5.08% | 0.39 | -47.71% |
| `12-0m (Raw)` | 322 | 5.66% | 0.37 | -54.84% | 7.97% | 0.46 | -51.06% | 5.96% | 0.44 | -41.21% |
| `12-1m (Standard)` | 322 | **7.38%** | 0.44 | -54.23% | 6.44% | 0.40 | -55.12% | 6.16% | 0.44 | -46.15% |
