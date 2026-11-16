# Complete Independent Audit Response: 4 Academic Paper Experiments (`T1`, `T2`, `V1`, `V2`) & Out-of-Sample / Outlier-Removal Verification (2026-11-16)

> **Standalone Scripts (Live on `main`)**:
> - Four Paper Experiments & Sub-Period / Walk-Forward Audit: [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py)
> - From-Scratch Raw-Data V4 Rebuild (Zero Shared Panel Code): [`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py)
> - Walk-Forward V4 & Pre-Registered 12-Sleeve Ensemble (`V4.1`): [`v4_robust_upgrade_research.py`](../../v4_robust_upgrade_research.py)
> - Self-Contained V1-Daily TQQQ Engine: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)
> - V4 Independent Engine (Hard Error on Missing `hold_ret`): [`independent_v4_symmetric_sharpe_top2_audit.py`](../../independent_v4_symmetric_sharpe_top2_audit.py)

---

## 1. Point-by-Point Remediation of the 5 Audit Findings

### Finding 1: Official FOMC SEP Timeline (`2012-01-25` Dots, `2015-09-17` Medians)
- **Correction Applied**: Added the official **`2015-09-17`** FOMC SEP median projections (`2016` target year: `FFR = 1.4%`, `Core PCE = 1.7%`) to [`02_sep_alfred_medians.csv`](../expabc_independent_audit_20261104/02_sep_alfred_medians.csv).
- **Verification**: Because Core PCE in both `2015-09-17` (`1.7%`) and `2015-12-16` (`1.6%`) was below `2.0%`, `SEP = ON` remained unchanged. All 9 historical `SEP` state transitions (`2021-09-22` to `2026-06-17`) rely strictly on real-time 2:00 PM ET FOMC SEP releases.

### Finding 2: Removal of Silent `0.0` Fallback in `independent_v4_symmetric_sharpe_top2_audit.py` & Raw-Data Rebuild
- **Code Fix**: Replaced `0.0 if pd.isna(r.hold_ret) else float(r.hold_ret)` in [`independent_v4_symmetric_sharpe_top2_audit.py`](../../independent_v4_symmetric_sharpe_top2_audit.py) with `get_verified_ret(t, tk)`, which **immediately raises a `ValueError` if any invested stock has a missing `hold_ret`**.
- **From-Scratch Raw-Data Verification ([`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py))**: Rebuilt NDX/SPX membership from raw `nasdaq100_src/*.yaml` and `sp500_hist_components.csv` and recomputed `12-1` momentum, volatility, Sharpe, and open-to-open holding returns directly from raw vendor JSON/parquet files:
  - Total invested stock-months (`2009-01 .. 2026-10`): **`422`** (`82` unique tickers).
  - Missing `hold_ret` count among invested positions: **`0 / 422`** (`415` `open_open`, `5` `delist_last_close`, `1` `open_open_via_wiki:SRCL`, `1` `close_proxy`).
  - Cross-vendor verification (`297 / 422` positions with $\ge 2$ independent data vendors): **`0` positions differ by `> 1%`**.

### Finding 3: V4 Concentration Analysis — Excluding 2026, Excluding 2020, and Dropping Best 5 / 10 Months
Exported in [`v4_subperiod_and_outlier_removal_audit.csv`](./v4_subperiod_and_outlier_removal_audit.csv):

| Evaluation Window / Stress Test (`V4 Default: Hold <= 5, No Election Reset`) | Months | **CAGR** | **Sharpe** | **Monthly MaxDD** |
| :--- | :---: | :---: | :---: | :---: |
| **1. Full 214 Months (`2009-01 .. 2026-10`)** | `214` | **`59.65%`** | `1.466` *(rf=0)* / `1.426` *(ex-rf)* | `-27.99%` |
| **2. Ex-2026: 17 Full Calendar Years (`2009-01 .. 2025-12`)** | `204` | **`50.38%`** | `1.394` | `-27.99%` |
| **3. Pre-2021: First 12 Full Years (`2009-01 .. 2020-12`)** | `144` | **`50.55%`** | `1.408` | `-27.99%` |
| **4. Post-2020 Ex-2026: 5 Full Years (`2021-01 .. 2025-12`)** | `60` | **`49.98%`** | `1.352` | **`-14.32%`** |
| **5. Ex-2020 & Ex-2026 (16 Years, Dropping Both Best Years)** | `192` | **`44.89%`** | `1.387` | **`-19.43%`** |
| **6. Drop Best 5 Months (Remaining 209 Months in Chronological Order)** | `209` | **`46.43%`** | `1.392` | `-27.99%` |
| **7. Drop Best 10 Months (Remaining 204 Months in Chronological Order)** | `204` | **`37.55%`** | `1.270` | `-27.99%` |
| **8. Walk-Forward Expanding-Window Parameter Selection (`2012-01 .. 2026-10`, 42 Configs)** | `178` | **`50.21%`** | `1.297` | `-27.39%` |

> **Key Takeaway on Realistic V4 Expectations**:  
> Excluding 2026 (`+308.5%` YTD driven by `WDC`/`STX`), `V4` delivered a remarkably consistent **`50.55%` CAGR in `2009–2020`** and **`49.98%` CAGR in `2021–2025`** (**`50.38%` across `2009–2025`**), and **`50.21%` under expanding-window walk-forward selection (`2012–2026`)**. Therefore, **`~45%–50%` (not `60%`)** is the realistic historical baseline before the 2026 outlier run.

---

## 2. Remediated 4 Paper Experiments (`T1`, `T2`, `V1`, `V2`)

### Experiment `T1`: Horizon-Matched `SEP Surprise` (`1Y Treasury DGS1` for Current-Year Dot, `1Y1Y Forward Rate 2*DGS2 - DGS1` for Next-Year Dot)
Exported in [`exp_T1_horizon_matched_sep_surprise.csv`](./exp_T1_horizon_matched_sep_surprise.csv):

| `T1` Variant (`2010-02-11 .. 2026-11-03` Real ETF, Next-Day Open + `10bp/side`) | Full `2010–2026` CAGR | Ex-2026 (`2010–2025`) CAGR | Daily MaxDD | Sharpe | Switches |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen Baseline `SEP` (Same-Target-Year Dot & Core PCE Revision)** 🏆 | **`54.89%`** | **`54.43%`** | **`-44.54%`** | **`1.259`** | `33` |
| **`T1a`. Horizon-Matched Dot vs Implied Rate (`DGS1` / `1Y1Y Fwd 2*DGS2-DGS1`)** | `42.50%` | `43.42%` | `-62.46%` | `1.021` | `28` |
| **`T1b`. Baseline `SEP` + Positive Horizon-Matched Forward Rate Shock** | `54.20%` | `53.71%` | `-44.54%` | `1.243` | `33` |

### Experiment `T2`: Out-of-Sample Walk-Forward `Vol_Z` Parameter Selection (`2012–2026`)
- To eliminate hindsight bias in choosing `(1.2, 0.3)` vs `(1.5, 0.5)`, `run_walk_forward_volz()` re-selects `(Trig, Rec)` from the 24-cell grid (`Trig ∈ [1.0..2.0], Rec ∈ [0.0..0.5]`) at each December close (`2011–2025`) using **only expanding-window past Sharpe**, and holds that parameter pair for the following calendar year (`2012–2026`):
  - **Out-of-Sample Walk-Forward `Vol_Z` (`2012–2026`)**: **CAGR = `56.97%`, Daily MaxDD = `-46.29%`, Sharpe = `1.301`** (confirming that `Vol_Z + NSL`'s drawdown reduction is not an artifact of picking `1.2/0.3` ex-post).

### Experiment `V1`: Robeco 3-Factor Fama-French (`MKT + SMB + HML`, `12-1M` & `36M` Rolling Regression) Residual Momentum
Exported in [`exp_V1_residual_momentum.csv`](./exp_V1_residual_momentum.csv):

| `V1` Ranking Factor (`V4` Architecture Fixed: `Top-2 / Hold <= 5`, `SEP`, Open + `10bp/side`) | Full `2009–2026` CAGR | **Ex-2026 (`2009–2025`) CAGR** | **Full Sharpe (`09–25` Sharpe)** | **Monthly MaxDD** | **Drop-Best-5M CAGR** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline (`12-1 Sharpe = mom / vol`)** 🏆 | **`59.65%`** | **`50.38%`** | **`1.426` (`1.350`)** | **`-27.99%`** | **`46.43%`** |
| **`V1-CAPM` (`12-1M` Single-Factor Market-Residual Sharpe)** | `45.99%` | `39.12%` | `1.070` (`1.010`) | `-29.40%` | `35.10%` |
| **`V1-FF3` (`12-1M` 3-Factor `MKT+SMB+HML` Residual Sharpe)** | `53.78%` | `44.39%` | `1.140` (`1.050`) | `-28.48%` | `36.69%` |
| **`V1-FF3-36M` (`36M` 3-Factor Beta + `12-1M` Residual Sharpe, Blitz 2011)** | `52.96%` | `43.78%` | `1.320` (`1.240`) | `-29.91%` | `40.35%` |
| **`V1-Blend-FF3` (`50% Standard 12-1 Sharpe + 50% FF3 Residual Sharpe`)** | `52.72%` | `43.03%` | `1.260` (`1.190`) | `-34.31%` | `39.10%` |
| **`V1-Blend-CAPM` (`50% Standard 12-1 Sharpe + 50% CAPM Residual Sharpe`)** | `61.30%` | `48.15%` | `1.250` (`1.140`) | `-27.99%` | `44.12%` |

> **Why `V1-FF3-36M` (Exact Blitz, Huij & Martens 2011 3-Factor 36M Regression) Beats 1-Factor CAPM (`52.96%` / Sharpe `1.32` vs `45.99%` / Sharpe `1.07`), Yet Still Trails `12-1 Sharpe` (`59.65%` / Sharpe `1.43`, or `50.38%` vs `43.78%` Ex-2026)**:  
> Adding `SMB` and `HML` with a 36-month estimation window (`V1-FF3-36M`) significantly improves Residual Momentum compared to 1-factor CAPM (`Sharpe` rises from `1.07` to `1.32`), confirming the auditor's point that multi-factor specification matters! However, in a concentrated **Long-Only Top-2** portfolio during `SEP = ON` bull markets, stripping out Market and Growth factor returns still penalizes secular mega-cap compounders (`NVDA`, `TSLA`, `AVGO`), trailing standard `12-1 Sharpe` by `-6.6pp/yr` both in `2009–2025` (`43.78%` vs `50.38%`) and `2009–2026` (`52.96%` vs `59.65%`). Even `V1-Blend-CAPM` (`61.30%` full period) trails `V4` in `2009–2025` (`48.15%` vs `50.38%`) with lower Sharpe (`1.25` vs `1.43`).
