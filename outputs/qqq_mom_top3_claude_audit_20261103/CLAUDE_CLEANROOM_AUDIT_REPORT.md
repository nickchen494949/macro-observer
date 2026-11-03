# Independent Clean-Room Audit Report: `QQQ Pure 12-1 Momentum Top-3`

- **Audit Date**: 2026-11-03
- **Audit Directory**: `outputs/qqq_mom_top3_claude_audit_20261103/`
- **Target Ledger Under Audit**: `outputs/ml3_feature_discovery_20261102/ledgers_qqq_iwm/QQQ__T0_Pure_Momentum_12_1__Top3.csv`
- **Reported Headline Numbers Under Audit**:
  - `2019-01 .. 2026-09` (`93` holding months): **55.49% CAGR**
  - `2015-02 .. 2026-09` (`140` holding months): **40.96% CAGR**
- **Clean-Room Rule**: Zero code or intermediate panel reuse from `research/sector_stock_momentum/*.py` or `outputs/ml3_feature_discovery_20261102/*.py`. The original ledger is read strictly once in `a4_backtest.py` / `a4b_recon_attribution.py` for month-by-month reconciliation.

---

## 1. Executive Verdict

### Overall Audit Classification: **MECHANICALLY SOUND & REPRODUCIBLE (`PASS`), WITH 4 CRITICAL ECONOMIC & RISK CAVEATS (`QUALIFIED`)**

Unlike `QQQ Price-ML Top-1` (`62.31%` CAGR), which **failed** clean-room audit due to cross-universe feature splicing (`sector_mom` and `dv_ratio` mixing S&P 500 and QQQ data), a Rank-#2 cliff (`9.48%` CAGR), and extreme random-seed instability (`40%..102%` CAGR), **`QQQ Pure 12-1 Momentum Top-3` is 100% free of look-ahead bias, free of cross-universe splicing, vendor-invariant, and structurally robust across neighboring ranks and parameters.**

However, our 18-year (`2009–2026`) clean-room reconstruction proves that **treating `54%–55%` (or even `40%`) as a stable, high-Sharpe alpha expectation over passive `QQQ` is NOT supported by the evidence**:

| Audit Dimension | Finding | Verdict |
|---|---|---|
| **1. Pick & Return Reproduction (`2015-02..2026-09`, 140m)** | Clean-room selects the **exact same 3 companies in `138 / 140` months** (`3` months `2016-01..03` are `CTRP` vs `TCOM`, same company renamed in 2019; `2` months `2018-11..12` reflect our recovery of 21st Century Fox `FOX`/`TFCF` from Tiingo where the original store had a 2018 data gap). Clean-room CAGR is **`40.95%`** (vs original **`40.96%`**) in `2015-02..2026-09` and **`54.27%`** (vs original **`55.49%`**) in `2019-01..2026-09`. | **PASS** |
| **2. Root Cause of Return Differences vs Original Ledger** | In `66` same-company months, gross returns differed by `>1 bp` because the original engine lacked Yahoo `raw_open` files for `EA` (only 1 bar in `raw_open/EA.json`) and NDX-only/delisted names (`MSTR, PDD, MELI, ZM, XLNX, ATVI, BMRN, CTRP, GMCR, SGEN`), silently falling back to **first-trading-day Close-to-Close (`close_t1`)**. Replacing those positions with `close_t1` explains **100% (`68/68` months) of differences with `0.0001 bp` max residual**. | **EXPLAINED (`0.0001 bp` residual)** |
| **3. Physical Look-Ahead / Truncation Test (`213/213` months)** | Physically cutting all YAML constituent logs and all daily price series at every formation month-end $t$ (`2008-12-31 .. 2026-08-31`) yields **`213 / 213` identical rosters, eligible sets, momentum values (`0.00e+00` diff), and Top-3 picks**. | **PASS (`100%`)** |
| **4. Independent Second-Vendor Swap (`Tiingo-First`)** | Re-running the entire 213-month signal and return pipeline using Tiingo EOD first produces the **exact same Top-3 picks in `213 / 213` months** and identical CAGR (`32.88%` vs `32.88%` full sample; `40.95%` vs `40.95%` in `2015–2026`; `54.27%` vs `54.27%` in `2019–2026`). | **PASS (`100%`)** |
| **5. Historical PIT Membership (`Wikipedia` 214 Monthly Snapshots)** | Cross-checking all 214 monthly revisions of the English Wikipedia `Nasdaq-100` article (`2008-12 .. 2026-09`) confirms `632 / 633` snapshot-covered picks (`99.84%`). Excluding the single unconfirmed pick (`CERN` at `2009-07-31`, where Wikipedia lagged Nasdaq's addition) raises `2009–2026` CAGR from `32.88%` to `33.02%`. | **PASS** |
| **6. Neighboring Ranks, Lookbacks & Execution Robustness** | Unlike ML Top-1, there is **no Rank-2 cliff**: over `2009–2026` (`2019–2026` in brackets), `Rank #1 = 26.27% [43.08%]`, **`Rank #2 = 36.61% [49.52%]`**, `Rank #3 = 13.87% [34.46%]`, `Top-2 = 37.13% [55.31%]`, `Top-3 = 32.88% [54.27%]`, `Top-5 = 30.86% [41.04%]`. Lookbacks `11-1` (`31.47%`), `9-1` (`35.92%`), `6-1` (`37.17%`), `12-0` (`36.45%`) and `T+1 Close` execution (`31.81%` / `52.47%`) all hold up. | **PASS** |
| **7. Caveat #1 — The First 10 Years (`2009–2018`, 120m) Underperformed Passive `QQQ`** | From `2009-01` to `2018-12` (`120` months), `SPEC Top-3` returned **`18.37%` CAGR** (Vol `29.2%`, Sharpe `0.72`, MaxDD `-39.9%`) vs **passive `QQQ ETF` `18.81%` CAGR** (Vol `16.0%`, Sharpe `1.14`, MaxDD `-19.0%`). Nearly all excess return over `QQQ` came in `2020` (`+159.8%`) and `2024–2026.09`. | **CRITICAL CAVEAT** |
| **8. Caveat #2 — True Max Drawdown Is `-55.2%` Monthly / `-60.6%` Daily (NOT `-27.7%`)** | An earlier summary cited `-27.71%` monthly MaxDD for QQQ Momentum Top-3; **that figure was erroneous**. Both the original ledger (`-56.56%` monthly / `-62.20%` daily) and clean-room ledger (**`-55.20%` monthly / `-60.56%` daily**) show a ~55%–61% peak-to-trough crash across the 2022 bear market (`-42.0%` in calendar year 2022). | **CRITICAL CAVEAT** |
| **9. Caveat #3 — High Beta ($\beta = 1.45\text{–}1.67$) & Insignificant CAPM Alpha vs `QQQ`** | `SPEC Top-3` runs at **`2.29x–2.56x` the volatility of `QQQ`** and **never beats `QQQ`'s Sharpe ratio** (`0.84 vs 1.06` in `2009–26`; `0.90 vs 0.92` in `2015–26`; `1.00 vs 1.00` in `2019–26`). Controlling for market beta against `QQQ`, annualized CAPM $\alpha$ is `+7.01%/yr` (**NW $t = 0.83, p = 0.41$**) in `2009–26`, `+13.45%/yr` (**NW $t = 1.24, p = 0.22$**) in `2015–26`, and `+18.65%/yr` (**NW $t = 1.19, p = 0.23$**) in `2019–26`. By contrast, vs equal-weight `NDX-EW` (`17.18%` CAGR), stock-selection excess return is statistically significant (`+15.71%/yr`, **NW $t = 2.16, p = 0.030$** in `2009–26`; `+26.85%/yr`, **NW $t = 2.56, p = 0.011$** in `2015–26`). | **CRITICAL CAVEAT** |
| **10. Caveat #4 — Right-Tail Month Dependence & Multiple Testing** | Dropping the best 5 holding months out of 213 cuts `2009–2026` CAGR from `32.88%` to `19.28%` (below `QQQ`'s `20.87%`) and `2019–2026` CAGR from `54.27%` to `20.47%` (below `QQQ`'s `23.59%`). Adjusted for `N = 481` strategy ledgers tested in the repo, the active Deflated Sharpe Ratio (`SPEC minus QQQ`) falls to `0.218` (`2015–26`) and `0.035` (`2009–26`). | **MODERATE CAVEAT** |

---

## 2. Clean-Room Pipeline Architecture

Every script in `outputs/qqq_mom_top3_claude_audit_20261103/` was written from scratch and verified to contain zero imports from existing project modules:

1. `a0_fetch_tiingo.py`: Rate-limited fetcher for Tiingo EOD (`open`, `close`, `adjOpen`, `adjClose`, `divCash`, `splitFactor`), caching **92 symbol series** across `outputs/qqq_mom_top3_claude_audit_20261103/tiingo/` and `outputs/tech_top1_independent_audit_20261103/tiingo/`.
2. `a1_universe.py`: Reconstructs monthly PIT Nasdaq-100 rosters (`2007-12-31 .. 2026-09-30`, `226` months) from `data/nasdaq100_src/n100-ticker-changes-2007..2026.yaml` using `yaml.BaseLoader` (preventing YAML 1.1 from parsing ticker `ON` as boolean `True`).
3. `a1b_fetch_wiki_ndx.py` & `a1c_compare_wiki.py`: Downloads and parses **214 historical monthly Wikipedia revisions** (`2008-12-31 .. 2026-09-30`) of the `Nasdaq-100` article (`wiki_ndx/*.json`) and cross-checks every monthly roster against the YAML chain.
4. `a2_engine.py`: Standalone price and return engine enforcing single-series ratios, 18 SEC-verified same-entity ticker renames (`RENAME`), post-delisting frozen-quote stripping (`>=5` identical closes), and the `IACI` 2008-08-21 4-spin-off + 1:2 reverse-split package adjustment (`CORP_FIX`).
5. `a3_signals.py`: Computes PIT `12-1` momentum across all `213` formation months (`2008-12-31 .. 2026-08-31`) and logs every missing constituent-month (`s_gaps_member_months.csv`).
6. `a4_backtest.py` & `a4b_recon_attribution.py`: Simulates the Top-3 open-to-open portfolio (`l_SPEC_top3.csv`), reconciles month-by-month against `QQQ__T0_Pure_Momentum_12_1__Top3.csv` (`r_recon_vs_original.csv`), and attributes all `68` return differences `>1 bp` (`r_recon_attribution.csv`).
7. `a5_stats_stress.py`: Generates subperiod metrics, paired Newey-West HAC ($lag=3, 6$) and 5,000-draw stationary block-bootstrap tests, 32 stress/falsification variants, calendar-year tables, and log-wealth attributions.
8. `a6_truncation_test.py`: Executes physical data truncation at every formation month-end $t$ (`213/213` months).
9. `a7_crosscheck.py` & `a7b_jump_scan.py`: Cross-checks all `639` held positions against independent Tiingo EOD `adjOpen`, audits all `32` extreme monthly returns (`|r| > 30%`), checks `169` cross-store overlap pairs, and scans for daily corporate-action jumps (`|r_1d| > 35%`).
10. `a8_gaps_mt_vendor.py` & `a8b_membership_doubt.py`: Evaluates missing-data gap thresholds, Deflated Sharpe Ratio across `481` repo strategy ledgers, volatility/beta-matched levered `QQQ` benchmarks, full Tiingo-first vendor swap, and Wikipedia-confirmed-only constituent filtering.
11. `a9_report_tables.py` & `run_all.sh`: Renders all report tables (`REPORT_TABLES.md`) directly from CSV outputs.

---

## 3. Point-in-Time Universe & Data Integrity Findings

### 3.1 YAML Constituent Chain & Wikipedia Historical Revision Cross-Check
- **YAML Chain Integrity (`u_yaml_chain_check.csv`)**: All `19` year-to-year transitions (`2007->2008` through `2025->2026`) reconcile with **`0` inconsistencies**. Monthly constituent counts (`u_monthly_members.csv`) span `100` to `107` (median `101` due to dual-class shares such as `GOOG/GOOGL`, `FOXA/FOX`, `DISCA/DISCK`, `LBTYA/LBTYK`), with `0` discrepancies against `ndx_monthly_members.csv` across all `226` common months (`u_diff_vs_project.csv`).
- **Contemporaneous Wikipedia Snapshots (`u_wiki_vs_yaml_monthly.csv`, `u_pick_membership_check.csv`)**:
  - Out of `214` monthly MediaWiki revisions (`2008-12-31 .. 2026-09-30`), `211` contain parseable constituent lists/tables (`2026-07..09` omitted inline constituent tables in Wikipedia).
  - Median disagreement vs the YAML roster on the revision date is **`0.0` tickers** (mean `0.65`, primarily dual-class share lines such as `LVNTA/CMCSK/LILAK` or 1–2 week Wikipedia editor lag around December annual rebalances).
  - Across all `633` Top-3 stock-month picks covered by a contemporaneous Wikipedia snapshot, **`632 / 633` (`99.84%`) are explicitly confirmed in the contemporaneous Wikipedia revision**.
  - The single exception is `CERN` at formation date `2009-07-31` (holding month `2009-08-31`), where Nasdaq added Cerner (`CERN`) in July 2009 (`n100-ticker-changes-2009.yaml`) but Wikipedia editors updated the article in August 2009. Excluding `CERN` in `2009-08` increases full-sample `2009–2026` CAGR from **`32.88%` to `33.02%`** and leaves `2015–2026` (`40.95%`) and `2019–2026` (`54.27%`) completely unchanged (`x_membership_doubt_variant.csv`).

### 3.2 Coverage Funnel & Missing-Data Gap Audit (`s_coverage_by_month.csv`, `g_gap_impact.csv`)
- Across `213` formation months (`21,697` total constituent-months), **`21,402` (`98.64%`)** have valid PIT `12-1` momentum.
- Of the `295` ineligible constituent-months:
  - **`177`** are genuine recent IPOs / spin-offs with `<12` months of trading history (`ABNB, ARM, CEG, CRWD,DASH, DDOG, DOCU, FB,FTNT, GEHC, GFS, HCAC, KHC, LCID, LMCA, META, MRNA, NXPI, PLTR, PDD, PYPL, PTON, RIVN, SNDK, SOLS, TEAM, TSLA, ZM`, plus post-spin New Fox `FOX/FOXA` in `2019-03 .. 2020-02`).
  - **`118`** are non-new-listing vendor gaps across `17` tickers (`BATRA, BATRK, BMC, CA, CEG, FMCN, FOX, FOXA, KHC, LIFE, LILA, LILAK, LMCK, PPDI, PYPL, QVCA, SPCX`).
  - Notably, our Tiingo EOD fetch (`a0_fetch_tiingo.py`) recovered `TFCF` and `TFCFA` (`2007-01-03 .. 2019-03-20`), filling `22` constituent-months (`11` months each for `FOX` and `FOXA` from `2018-04-30` to `2019-02-28`) that were missing in the original backtest! As a result, Twenty-First Century Fox (`FOX` via `TFCF`) legitimately entered the Top-3 in `2018-11` (`#2`, `+81.65%` 12-1 momentum during the Disney/Comcast acquisition bidding war) and `2018-12` (`#3`, `+46.34%`).

### 3.3 Execution Price Coverage & Corporate-Action Audit (`l_SPEC_top3.csv`, `v_position_crosscheck.csv`, `v_extreme_positions.csv`)
- Out of `639` total position-months (`213` months $\times$ `3` stocks):
  - **`634 / 639` (`99.22%`)** are executed using genuine `open_to_open` prices (`Open[t+1, d1] -> Open[t+2, d1]`).
  - **`3 / 639` (`0.47%`)** are mid-month M&A delistings (`GENZ` in `2011-04`, `ESRX` in `2018-12`, `SGEN` in `2023-12`) exited at their last traded adjusted close (`delist_last_close`).
  - **`2 / 639` (`0.31%`)** (`GENZ` in `2009-02` and `2009-03`, stored only in `raw_archive` close format) use `no_open_close_proxy`. Penalizing fallback-priced positions by `min(open, close_proxy) - 200 bp` changes full-sample CAGR by just `-0.26%/yr` (`32.88% -> 32.62%`).
- **Independent Second-Vendor Cross-Check (`v_position_crosscheck.csv`)**:
  - For `353` positions where the primary store was Yahoo/WIKI and Tiingo EOD also had `adjOpen` (plus `128` positions priced directly from Tiingo = `481 / 639` covered by Tiingo `adjOpen`), the median absolute difference between primary and Tiingo open-to-open return is **`0.00 bp`** (`p90 = 0.18 bp`, `max = 4.5 bp`, **`0` positions `> 25 bp`**).
- **Extreme Return Audit (`v_extreme_positions.csv`)**:
  - All `32` position-months with `|ret| > 30%` (including `MRNA +161.2%` in `2020-11`, `MU +97.3%` in `2026-05`, `TSLA +73.2%` in `2020-08`, `STX +68.2%` in `2026-04`, `SNDK +63.5%` in `2026-05`, `MRNA +61.4%` in `2021-01`, `APP +54.1%` in `2025-09`, `NFLX -50.9%` in `2011-09`, `SNDK -44.4%` in `2026-07`) were cross-checked against Tiingo `adjOpen` and `adjClose`. Every post-2010 extreme return (`31 / 32`) matches Tiingo `adjOpen` to within `0.00–0.03 bp` (`2009-11 PCLN +36.61%` is verified via `wikibulk` and Yahoo `BKNG`).

---

## 4. Complete Auto-Generated Audit Tables (`REPORT_TABLES.md`)

All tables below are generated directly from the CSV outputs by `a9_report_tables.py` with zero manual transcription.

### T1. Performance by window (net of 10 bp/side; QQQ = same open-to-open dates)

| Window | Months | Top-3 CAGR | QQQ CAGR | NDX-EW CAGR | Top-1 CAGR | Top-3 Sharpe | QQQ Sharpe | Top-3 vol | Top-3 MaxDD (monthly) | Top-3 MaxDD (daily) | QQQ MaxDD (monthly) | QQQ levered to same vol | QQQ levered to same beta | beta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FULL 2009-01..2026-09 | 213 | 32.88% | 20.87% | 17.18% | 26.27% | 0.84 | 1.06 | 41.6% | -55.2% | -60.6% | -32.2% | 43.95% | 29.36% | 1.45 |
| 2009-2014 | 72 | 19.14% | 24.38% | 24.41% | 4.96% | 0.74 | 1.43 | 29.5% | -39.9% | -43.8% | -13.2% | 45.48% | 24.93% | 1.02 |
| 2015-2019 | 60 | 21.21% | 16.72% | 12.59% | 37.14% | 0.76 | 0.97 | 30.1% | -30.2% | -32.6% | -19.0% | 29.03% | 22.91% | 1.42 |
| 2020-2022 | 36 | 32.49% | 8.50% | 7.92% | -4.30% | 0.72 | 0.41 | 58.4% | -47.3% | -52.1% | -32.2% | 8.48% | 10.00% | 1.57 |
| 2023-2026.09 | 45 | 79.32% | 31.88% | 19.93% | 89.73% | 1.25 | 1.46 | 53.3% | -24.6% | -41.5% | -9.0% | 95.84% | 59.82% | 1.95 |
| 2009-2018 (pre-2019) | 120 | 18.37% | 18.81% | 16.95% | 14.60% | 0.72 | 1.14 | 29.2% | -39.9% | -43.8% | -19.0% | 33.79% | 21.70% | 1.16 |
| ORIG 2015-02..2026-09 | 140 | 40.95% | 19.51% | 14.10% | 40.44% | 0.90 | 0.92 | 46.6% | -55.2% | -60.6% | -32.2% | 40.02% | 29.29% | 1.62 |
| ORIG 2019-01..2026-09 | 93 | 54.27% | 23.59% | 17.47% | 43.08% | 1.00 | 1.00 | 53.1% | -55.2% | -60.6% | -32.2% | 50.77% | 36.41% | 1.67 |

### T2. Paired tests (SPEC Top-3 minus benchmark)

| Window | vs | CAGR diff | NW t (lag 3) | p | Bootstrap 90% CI of CAGR diff | P(diff<=0) | monthly win | alpha/yr vs QQQ | alpha NW t |
|---|---|---|---|---|---|---|---|---|---|
| FULL 2009-01..2026-09 | BENCH QQQ ETF | 12.01% | 1.81 | 0.070 | [-3.49%, 31.21%] | 0.105 | 54% | 7.01% | 0.83 |
| FULL 2009-01..2026-09 | BENCH NDX equal-weight (PIT, 10bp) | 15.71% | 2.16 | 0.030 | [-0.02%, 35.39%] | 0.051 | 53% |  |  |
| FULL 2009-01..2026-09 | Top-1 | 6.62% | -0.20 | 0.845 | [-9.01%, 20.97%] | 0.240 | 49% |  |  |
| FULL 2009-01..2026-09 | Ranks 4-6 (neighbour Top-3) | 13.59% | 1.69 | 0.090 | [-2.72%, 33.26%] | 0.096 | 47% |  |  |
| 2009-2014 | BENCH QQQ ETF | -5.24% | -0.11 | 0.913 | [-25.11%, 15.90%] | 0.653 | 50% | -1.74% | -0.15 |
| 2009-2014 | BENCH NDX equal-weight (PIT, 10bp) | -5.27% | -0.13 | 0.898 | [-26.01%, 16.16%] | 0.651 | 47% |  |  |
| 2009-2014 | Top-1 | 14.17% | 0.67 | 0.505 | [-3.96%, 28.92%] | 0.091 | 56% |  |  |
| 2009-2014 | Ranks 4-6 (neighbour Top-3) | -16.23% | -1.03 | 0.305 | [-35.06%, 4.45%] | 0.904 | 39% |  |  |
| 2015-2019 | BENCH QQQ ETF | 4.50% | 0.82 | 0.412 | [-9.48%, 21.34%] | 0.303 | 58% | 0.41% | 0.05 |
| 2015-2019 | BENCH NDX equal-weight (PIT, 10bp) | 8.62% | 1.27 | 0.205 | [-5.54%, 25.37%] | 0.160 | 57% |  |  |
| 2015-2019 | Top-1 | -15.93% | -1.51 | 0.131 | [-48.32%, 5.33%] | 0.869 | 45% |  |  |
| 2015-2019 | Ranks 4-6 (neighbour Top-3) | 0.16% | 0.27 | 0.789 | [-12.31%, 14.31%] | 0.483 | 48% |  |  |
| 2020-2022 | BENCH QQQ ETF | 23.99% | 1.31 | 0.189 | [-10.06%, 95.60%] | 0.161 | 53% | 25.33% | 1.29 |
| 2020-2022 | BENCH NDX equal-weight (PIT, 10bp) | 24.57% | 1.35 | 0.178 | [-11.20%, 99.11%] | 0.167 | 50% |  |  |
| 2020-2022 | Top-1 | 36.79% | 1.04 | 0.300 | [2.25%, 93.91%] | 0.038 | 61% |  |  |
| 2020-2022 | Ranks 4-6 (neighbour Top-3) | 45.58% | 2.39 | 0.017 | [8.59%, 115.50%] | 0.009 | 56% |  |  |
| 2023-2026.09 | BENCH QQQ ETF | 47.44% | 1.58 | 0.114 | [-3.01%, 126.13%] | 0.066 | 56% | 18.52% | 0.69 |
| 2023-2026.09 | BENCH NDX equal-weight (PIT, 10bp) | 59.39% | 2.02 | 0.043 | [11.22%, 136.73%] | 0.019 | 58% |  |  |
| 2023-2026.09 | Top-1 | -10.41% | -0.85 | 0.395 | [-67.52%, 30.07%] | 0.652 | 36% |  |  |
| 2023-2026.09 | Ranks 4-6 (neighbour Top-3) | 56.22% | 1.71 | 0.087 | [7.43%, 123.79%] | 0.027 | 53% |  |  |
| ORIG 2015-02..2026-09 | BENCH QQQ ETF | 21.44% | 2.12 | 0.034 | [-0.19%, 50.50%] | 0.052 | 56% | 13.45% | 1.24 |
| ORIG 2015-02..2026-09 | BENCH NDX equal-weight (PIT, 10bp) | 26.85% | 2.56 | 0.011 | [4.62%, 56.19%] | 0.020 | 55% |  |  |
| ORIG 2015-02..2026-09 | Top-1 | 0.51% | -0.70 | 0.486 | [-23.75%, 22.54%] | 0.499 | 46% |  |  |
| ORIG 2015-02..2026-09 | Ranks 4-6 (neighbour Top-3) | 29.37% | 2.52 | 0.012 | [7.90%, 56.79%] | 0.009 | 52% |  |  |
| ORIG 2019-01..2026-09 | BENCH QQQ ETF | 30.68% | 1.95 | 0.051 | [-2.18%, 79.28%] | 0.069 | 53% | 18.65% | 1.19 |
| ORIG 2019-01..2026-09 | BENCH NDX equal-weight (PIT, 10bp) | 36.80% | 2.30 | 0.021 | [3.33%, 86.00%] | 0.033 | 53% |  |  |
| ORIG 2019-01..2026-09 | Top-1 | 11.19% | -0.05 | 0.958 | [-21.82%, 40.68%] | 0.281 | 47% |  |  |
| ORIG 2019-01..2026-09 | Ranks 4-6 (neighbour Top-3) | 44.51% | 2.57 | 0.010 | [12.18%, 88.44%] | 0.007 | 52% |  |  |
| 2009-2018 (pre-2019) | BENCH QQQ ETF | -0.43% | 0.36 | 0.722 | [-14.48%, 14.67%] | 0.506 | 55% | -0.15% | -0.02 |
| 2009-2018 (pre-2019) | BENCH NDX equal-weight (PIT, 10bp) | 1.42% | 0.53 | 0.595 | [-13.30%, 16.79%] | 0.424 | 52% |  |  |
| 2009-2018 (pre-2019) | Top-1 | 3.77% | -0.23 | 0.814 | [-14.46%, 17.66%] | 0.350 | 51% |  |  |
| 2009-2018 (pre-2019) | Ranks 4-6 (neighbour Top-3) | -8.88% | -0.75 | 0.453 | [-23.06%, 6.06%] | 0.834 | 44% |  |  |

### T3. Benchmarks, neighbours and stress variants (CAGR)

| Variant | FULL 2009-26 | 2009-2018 | 2015-02..2026-09 | 2019-01..2026-09 | Sharpe FULL | MaxDD FULL (monthly) |
|---|---|---|---|---|---|---|
| SPEC Top-3 (10bp) | 32.88% | 18.37% | 40.95% | 54.27% | 0.84 | -55.2% |
| BENCH QQQ ETF | 20.87% | 18.81% | 19.51% | 23.59% | 1.06 | -32.2% |
| BENCH NDX equal-weight (PIT, 10bp) | 17.18% | 16.95% | 14.10% | 17.47% | 0.91 | -28.5% |
| Top-1 | 26.27% | 14.60% | 40.44% | 43.08% | 0.66 | -80.1% |
| Top-2 | 37.13% | 24.51% | 43.45% | 55.31% | 0.90 | -63.3% |
| Top-5 | 30.86% | 23.47% | 33.12% | 41.04% | 0.94 | -48.8% |
| Top-10 | 24.92% | 22.24% | 23.83% | 28.47% | 0.91 | -42.4% |
| Rank #1 alone | 26.27% | 14.60% | 40.44% | 43.08% | 0.66 | -80.1% |
| Rank #2 alone | 36.61% | 27.38% | 33.12% | 49.52% | 0.82 | -76.2% |
| Rank #3 alone | 13.87% | 0.11% | 22.89% | 34.46% | 0.42 | -67.4% |
| Rank #4 alone | 13.12% | 24.19% | 4.67% | 0.29% | 0.46 | -85.7% |
| Rank #5 alone | 24.16% | 25.14% | 20.73% | 22.90% | 0.75 | -46.5% |
| Rank #6 alone | 7.31% | 21.61% | -3.52% | -8.68% | 0.34 | -87.3% |
| Ranks 4-6 (neighbour Top-3) | 19.29% | 27.25% | 11.57% | 9.76% | 0.72 | -56.6% |
| Ranks 2-4 | 27.57% | 20.45% | 27.62% | 37.38% | 0.79 | -50.4% |
| Cost 20bp/side | 31.74% | 17.30% | 39.82% | 53.04% | 0.82 | -55.9% |
| Cost 30bp/side | 30.61% | 16.24% | 38.71% | 51.82% | 0.80 | -56.7% |
| Cost 50bp/side | 28.38% | 14.14% | 36.49% | 49.40% | 0.76 | -58.1% |
| Cost 100bp/side | 22.93% | 9.04% | 31.10% | 43.51% | 0.65 | -62.1% |
| Exec T+1 close (first trading day close) | 31.81% | 17.74% | 39.80% | 52.47% | 0.86 | -55.8% |
| Exec month-end close (no lag, optimistic) | 32.22% | 17.67% | 40.03% | 53.66% | 0.85 | -56.6% |
| Exec open of trading day 2 (timing luck) | 31.83% | 17.85% | 39.99% | 52.34% | 0.84 | -58.4% |
| Exec open of trading day 3 (timing luck) | 31.45% | 18.51% | 38.73% | 50.25% | 0.84 | -60.2% |
| Exec open of trading day 5 (timing luck) | 32.08% | 18.74% | 39.45% | 51.53% | 0.86 | -58.5% |
| Exec open of trading day 10 (timing luck) | 29.39% | 17.89% | 35.77% | 45.90% | 0.82 | -64.4% |
| Signal 11-1 momentum | 31.47% | 21.51% | 39.00% | 45.53% | 0.82 | -61.4% |
| Signal 12-2 momentum | 28.10% | 25.41% | 27.61% | 31.65% | 0.75 | -67.6% |
| Signal 9-1 momentum | 35.92% | 24.58% | 39.71% | 52.08% | 0.89 | -63.0% |
| Signal 6-1 momentum | 37.17% | 25.03% | 45.61% | 54.60% | 1.05 | -37.5% |
| Signal 12-0 momentum | 36.45% | 24.73% | 44.03% | 53.23% | 0.92 | -61.3% |
| Drop best 1 months (set to 0%) | 29.02% | 18.37% | 34.75% | 44.17% | 0.81 | -55.2% |
| Drop best 3 months (set to 0%) | 22.48% | 18.37% | 24.51% | 27.99% | 0.73 | -55.2% |
| Drop best 5 months (set to 0%) | 19.28% | 18.37% | 19.60% | 20.47% | 0.67 | -55.2% |
| Drop best 10 months (set to 0%) | 12.41% | 18.37% | 9.27% | 5.16% | 0.49 | -55.2% |
| Ban top-1 contributors (MRNA) | 27.89% | 18.37% | 32.97% | 41.32% | 0.78 | -59.3% |
| Ban top-3 contributors (MRNA,TSLA,MU) | 20.72% | 13.43% | 25.58% | 30.82% | 0.68 | -59.9% |
| Ban top-6 contributors (MRNA,TSLA,MU,NFLX,SNDK,NVDA) | 12.99% | 8.78% | 14.65% | 18.67% | 0.49 | -65.5% |
| Ban SNDK | 33.37% | 19.93% | 40.15% | 52.96% | 0.87 | -55.2% |
| Ban NVDA | 26.87% | 13.97% | 31.36% | 45.70% | 0.73 | -57.9% |
| Ban TSLA | 28.80% | 18.22% | 34.56% | 43.86% | 0.79 | -56.0% |
| Worst-case: fallback-priced positions = min(open,close proxy) - 2% | 32.62% | 18.03% | 40.78% | 54.14% | 0.84 | -55.2% |
| Worst-case combo: 30bp/side + T+1 close + fallback worst | 29.28% | 15.26% | 37.37% | 49.91% | 0.81 | -57.2% |

### T4. Calendar-year net returns (2026 = Jan–Sep)

| Year | SPEC Top-3 (10bp) | Top-1 | BENCH QQQ ETF | BENCH NDX equal-weight (PIT, 10bp) |
|---|---|---|---|---|
| 2009 | 4.8% | -0.6% | 56.5% | 63.6% |
| 2010 | 3.5% | -44.2% | 19.5% | 21.5% |
| 2011 | -15.9% | -10.8% | 4.4% | -1.0% |
| 2012 | 29.8% | 48.6% | 18.6% | 14.7% |
| 2013 | 49.7% | 11.6% | 32.8% | 37.6% |
| 2014 | 61.5% | 63.1% | 20.3% | 19.3% |
| 2015 | 8.4% | -11.1% | 6.5% | 0.3% |
| 2016 | 34.4% | 121.8% | 10.2% | 9.5% |
| 2017 | 37.8% | 64.1% | 32.4% | 26.4% |
| 2018 | -5.9% | -9.7% | -2.7% | -7.1% |
| 2019 | 38.5% | 66.0% | 43.2% | 40.2% |
| 2020 | 159.8% | 56.8% | 48.0% | 38.7% |
| 2021 | 54.2% | -19.1% | 27.2% | 18.5% |
| 2022 | -42.0% | -30.9% | -32.2% | -23.5% |
| 2023 | 3.2% | -10.1% | 52.1% | 33.3% |
| 2024 | 54.1% | 155.2% | 27.5% | 8.9% |
| 2025 | 79.8% | 28.4% | 21.2% | 16.1% |
| 2026 | 212.5% | 274.8% | 20.2% | 17.3% |

### T5. Top-10 contributors, 2009-01..2026-09

| Ticker | Months held | Share of total log wealth | Best month | Worst month |
|---|---|---|---|---|
| MRNA | 18 | 6.2% | 161.2% | -39.6% |
| TSLA | 30 | 4.8% | 73.2% | -29.1% |
| MU | 32 | 4.1% | 97.3% | -13.1% |
| NFLX | 37 | 3.5% | 22.6% | -50.9% |
| SNDK | 11 | 3.1% | 63.5% | -44.4% |
| NVDA | 47 | 3.0% | 38.6% | -15.8% |
| WDC | 12 | 2.2% | 44.8% | -15.5% |
| STX | 16 | 2.2% | 68.2% | -12.5% |
| ALGN | 13 | 1.5% | 17.5% | -43.5% |
| APP | 12 | 1.4% | 54.1% | -24.6% |

### T5b. Top-10 contributors, 2019-01..2026-09

| Ticker | Months held | Share of total log wealth | Best month | Worst month |
|---|---|---|---|---|
| MRNA | 18 | 9.4% | 161.2% | -39.6% |
| TSLA | 19 | 5.7% | 73.2% | -29.1% |
| MU | 7 | 4.7% | 97.3% | -13.1% |
| SNDK | 5 | 4.2% | 63.5% | -44.4% |
| WDC | 9 | 3.3% | 44.8% | -15.5% |
| STX | 4 | 2.6% | 68.2% | -2.2% |
| NVDA | 23 | 2.5% | 33.6% | -15.8% |
| APP | 12 | 2.1% | 54.1% | -24.6% |
| PLTR | 12 | 1.5% | 43.1% | -19.5% |
| AMD | 12 | 1.5% | 36.6% | -6.8% |

### T5c. Top-10 contributors, 2009-01..2018-12

| Ticker | Months held | Share of total log wealth | Best month | Worst month |
|---|---|---|---|---|
| NFLX | 32 | 10.1% | 22.6% | -50.9% |
| ALGN | 11 | 4.5% | 17.5% | -43.5% |
| NVDA | 24 | 3.9% | 38.6% | -6.0% |
| PCLN | 8 | 3.1% | 36.6% | -27.8% |
| TSLA | 11 | 3.0% | 29.7% | -22.5% |
| MU | 25 | 2.8% | 29.0% | -6.8% |
| LINTA | 8 | 2.6% | 22.0% | -19.4% |
| GMCR | 13 | 2.5% | 19.6% | -30.5% |
| AMZN | 12 | 2.4% | 9.0% | -19.7% |
| SIRI | 1 | 1.7% | -18.8% | -18.8% |

### T6. Deflated Sharpe ratio (N = number of strategies tried)

| window | series | n_trials | sr_ann | sr0_ann (expected max of N null trials) | DSR |
|---|---|---|---|---|---|
| ORIG 2015-02..2026-09 | SPEC Top-3 excess of rf | 1 | 0.90 | 0.00 | 1.000 |
| ORIG 2015-02..2026-09 | SPEC Top-3 excess of rf | 10 | 0.90 | 0.44 | 0.970 |
| ORIG 2015-02..2026-09 | SPEC Top-3 excess of rf | 50 | 0.90 | 0.64 | 0.860 |
| ORIG 2015-02..2026-09 | SPEC Top-3 excess of rf | 100 | 0.90 | 0.71 | 0.784 |
| ORIG 2015-02..2026-09 | SPEC Top-3 excess of rf | 481 | 0.90 | 0.85 | 0.579 |
| ORIG 2015-02..2026-09 | SPEC minus QQQ (active) | 1 | 0.67 | 0.00 | 0.997 |
| ORIG 2015-02..2026-09 | SPEC minus QQQ (active) | 10 | 0.67 | 0.44 | 0.821 |
| ORIG 2015-02..2026-09 | SPEC minus QQQ (active) | 50 | 0.67 | 0.64 | 0.542 |
| ORIG 2015-02..2026-09 | SPEC minus QQQ (active) | 100 | 0.67 | 0.71 | 0.426 |
| ORIG 2015-02..2026-09 | SPEC minus QQQ (active) | 481 | 0.67 | 0.85 | 0.218 |
| FULL 2009-01..2026-09 | SPEC Top-3 excess of rf | 1 | 0.84 | 0.00 | 1.000 |
| FULL 2009-01..2026-09 | SPEC Top-3 excess of rf | 10 | 0.84 | 0.44 | 0.975 |
| FULL 2009-01..2026-09 | SPEC Top-3 excess of rf | 50 | 0.84 | 0.64 | 0.840 |
| FULL 2009-01..2026-09 | SPEC Top-3 excess of rf | 100 | 0.84 | 0.71 | 0.741 |
| FULL 2009-01..2026-09 | SPEC Top-3 excess of rf | 481 | 0.84 | 0.85 | 0.479 |
| FULL 2009-01..2026-09 | SPEC minus QQQ (active) | 1 | 0.48 | 0.00 | 0.988 |
| FULL 2009-01..2026-09 | SPEC minus QQQ (active) | 10 | 0.48 | 0.44 | 0.562 |
| FULL 2009-01..2026-09 | SPEC minus QQQ (active) | 50 | 0.48 | 0.64 | 0.217 |
| FULL 2009-01..2026-09 | SPEC minus QQQ (active) | 100 | 0.48 | 0.71 | 0.131 |
| FULL 2009-01..2026-09 | SPEC minus QQQ (active) | 481 | 0.48 | 0.85 | 0.035 |

### T7. Integrity summary

- Original ledger months: 140; exact ticker-string match: 135/140; same-company match: 138/140 (3 months `2016-01..03` are `CTRP` vs `TCOM` = same entity renamed in 2019; 2 months `2018-11..12` are `FOX` (`TFCF`, 21st Century Fox) recovered via Tiingo EOD where the original store had a 2018 data gap).
- Months with |gross diff| > 1 bp: 68; all 68/68 attributed in `r_recon_attribution.csv` with max unexplained residual `0.0001 bp`.
- Truncation test: roster/eligible/ranking identical in 213/213 months; max |momentum diff| 0.00e+00; Top-3 identical 213/213.
- Positions: 639; independent Tiingo adjOpen comparison available for 353 (+128 priced from Tiingo directly).
- Vendor swap (Tiingo-first for signals and returns): same Top-3 set 213/213 months.

---

## 5. Output File Manifest (`outputs/qqq_mom_top3_claude_audit_20261103/`)

| File | Description |
|---|---|
| `run_all.sh` | One-command deterministic reproduction script (`zsh run_all.sh`) |
| `a0_fetch_tiingo.py`, `tiingo/*.json` | Rate-limited Tiingo EOD fetcher + 43 new Tiingo symbol files (+ 49 shared in `tech_top1_independent_audit_20261103/tiingo/`) |
| `a1_universe.py`, `u_monthly_members.csv`, `u_yaml_chain_check.csv`, `u_diff_vs_project.csv` | PIT Nasdaq-100 monthly rosters (`226` months) and chain verification |
| `a1b_fetch_wiki_ndx.py`, `a1c_compare_wiki.py`, `wiki_ndx/*.json`, `u_wiki_vs_yaml_monthly.csv`, `u_wiki_vs_yaml_disagreements.csv` | 214 historical monthly Wikipedia revisions and cross-check vs YAML rosters |
| `a2_engine.py`, `a2b_identity.py` | Clean-room price/return engine, rename table, `IACI` spin-off fix, frozen-quote cleaner |
| `a3_signals.py`, `s_panel.parquet`, `s_panel.csv`, `s_coverage_by_month.csv`, `s_gaps_member_months.csv` | Full 213-month PIT 12-1 momentum panel and missing-data funnel |
| `a4_backtest.py`, `a4b_recon_attribution.py`, `l_SPEC_top3.csv`, `r_recon_vs_original.csv`, `r_recon_attribution.csv` | Clean-room Top-3 ledger and 100% attributed reconciliation vs original ledger |
| `a5_stats_stress.py`, `x_stress.csv`, `x_paired_tests.csv`, `x_calendar_years.csv`, `x_contribution.csv` | Subperiod metrics, Newey-West / bootstrap hypothesis tests, 32 stress variants, and log-wealth attribution |
| `a6_truncation_test.py`, `t_truncation_test.csv` | Physical truncation test across all `213` formation months (`213/213` pass) |
| `a7_crosscheck.py`, `a7b_jump_scan.py`, `v_position_crosscheck.csv`, `v_extreme_positions.csv`, `v_identity_overlap.csv`, `v_jump_scan.csv` | Position-by-position Tiingo `adjOpen` cross-check, extreme return verification, and daily jump scan |
| `a8_gaps_mt_vendor.py`, `a8b_membership_doubt.py`, `g_gap_impact.csv`, `m_multiple_testing.csv`, `m_repo_trials.csv`, `x_risk_matched.csv`, `x_vendor_swap.csv`, `u_pick_membership_check.csv`, `x_membership_doubt_variant.csv` | Gap analysis, DSR across 481 trials, levered QQQ benchmarks, full Tiingo-first swap, and Wikipedia-confirmed-only filter |
| `a9_report_tables.py`, `REPORT_TABLES.md` | Automated Markdown table generator |
