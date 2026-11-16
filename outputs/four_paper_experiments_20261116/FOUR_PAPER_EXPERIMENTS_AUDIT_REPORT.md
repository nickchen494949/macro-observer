# Complete Independent Audit Response: 4 Academic Paper Experiments (`T1`, `T2`, `V1`, `V2`), Stateful Walk-Forward, and Raw-Data Verification (2026-11-16)

> **Standalone Reproducible Scripts (Committed on `main`)**:
> - Four Paper Experiments (`T1`, `T2`, `V1` FF3-12M/36M, `V2`) & Stateful Walk-Forward Audit: [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py)
> - Committed Daily FF3 Factor Series (`MKT`, `SMB`, `HML` for Clean Clone Reproducibility): [`ff3_daily_factors_2007_2026.csv`](./ff3_daily_factors_2007_2026.csv)
> - From-Scratch Raw-Data V4 Rebuild (Both Default `No-ER` & `+ER`, Cross-Vendor `Open-to-Open` & `Max-Diff`): [`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py)
> - Stateful Walk-Forward V4 & Pre-Registered 12-Sleeve Ensemble (`V4.1`): [`v4_robust_upgrade_research.py`](../../v4_robust_upgrade_research.py)
> - Self-Contained V1-Daily TQQQ Engine: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)
> - V4 Independent Engine (Hard Error on Missing `hold_ret`): [`independent_v4_symmetric_sharpe_top2_audit.py`](../../independent_v4_symmetric_sharpe_top2_audit.py)

---

## 1. Point-by-Point Remediation of All 6 Follow-Up Audit Items

### Item 1: Full Reproducible `FF3` (`12-1M` & `36M` Blitz 2011) Code & CSV in `run_four_paper_experiments.py`
- **Fix Applied**: Embedded the complete per-stock daily OLS regression (`add_ff3_residual`) for **1-Factor CAPM**, **3-Factor Fama-French (`MKT + SMB + HML`, `12-1M` window)**, **3-Factor 36-Month Rolling Regression (`V1c-FF3-36M`, Blitz, Huij & Martens 2011)**, and **50/50 Blends (`V1d`, `V1e`)** directly inside [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py), exported the factor series [`ff3_daily_factors_2007_2026.csv`](./ff3_daily_factors_2007_2026.csv), and regenerated [`exp_V1_residual_momentum.csv`](./exp_V1_residual_momentum.csv).

### Item 2: True Stateful Single-Account Walk-Forward for `V1-Daily TQQQ` (`run_four_paper_experiments.py`)
- **Fix Applied**: Replaced spliced annual return slices with a **true stateful single-account simulation** (`sim_stateful` inside `run_walk_forward_volz()`) that maintains one continuous live account state `(pos, eq, entry_eq)` across all day and year boundaries (`2012-01-03 .. 2026-11-03`) and charges the full `10bp/side` (`20bp` round-trip) Open switch cost whenever the newly selected year's `(trig, rec)` triggers a position switch:
  - **True Stateful Walk-Forward (`2012–2026`, Continuous Account from 2010 Warmup)**: **CAGR = `56.38%`, Daily MaxDD = `-46.29%`, Sharpe = `1.293`** (`2.5` switches/yr).
  - **True Stateful Walk-Forward (`2012–2026`, Fresh Account Start at `2012-01-03`)**: **CAGR = `56.38%`, Daily MaxDD = `-46.29%`, Sharpe = `1.293`** (`2.2` switches/yr).
  - **Spliced Approximation (Reference)**: CAGR = `56.97%`, Daily MaxDD = `-46.29%`, Sharpe = `1.301` (`-0.59pp/yr` difference from true stateful execution).

### Item 3: True Stateful Single-Account Walk-Forward for `V4` (`v4_robust_upgrade_research.py`)
- **Fix Applied**: Added `simulate_stateful_wf()` in [`v4_robust_upgrade_research.py`](../../v4_robust_upgrade_research.py) (exported to [`walk_forward_stateful_sep_ledger.csv`](../v4_robust_upgrade_20261115/walk_forward_stateful_sep_ledger.csv)), which maintains a single continuous live portfolio's drifted weights `prev_w` and buffers `(hq, hb)` across all month and year boundaries (`2012-01 .. 2026-10`) and charges the full `10bp/side` turnover cost when parameters change each January:
  - **With `SEP` Overlay (`2012-01 .. 2026-10`, 178 Months)**:
    - **Stateful Walk-Forward (Continuous Live Buffers + Switch Turnover Cost)**: **CAGR = `49.17%`, Sharpe = `1.269`, Monthly MaxDD = `-27.39%`**.
    - **Stateful Walk-Forward (Adopt Target Sleeve + Full Switch Turnover Cost)**: **CAGR = `50.16%`, Sharpe = `1.296`, Monthly MaxDD = `-27.39%`**.
    - **Spliced Approximation (Reference)**: CAGR = `50.21%`, Sharpe = `1.297`, Monthly MaxDD = `-27.39%`.
  - **Without `SEP` Overlay (`regime=none`, `2012-01 .. 2026-10`, 178 Months)**:
    - **Stateful Walk-Forward (Continuous Live Buffers)**: **CAGR = `40.98%`, Sharpe = `1.053`, Monthly MaxDD = `-40.70%`**.
    - **Stateful Walk-Forward (Adopt Target Sleeve + Switch Cost)**: **CAGR = `41.91%`, Sharpe = `1.076`, Monthly MaxDD = `-40.70%`**.

### Item 4: Explicit Separation of True M&A Delistings (`3`) vs `2026-10-29` Sample-End Cutoff (`2`) in `audit_v4_from_scratch.py`
- **Fix Applied**: Updated `hold_return()` and Part D in [`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py) (exported to [`D_invested_positions.csv`](../v4_from_scratch_audit_20261114/D_invested_positions.csv)) so that the `2026-10` positions (`MPC` and `VLO`, which are active S&P 500 constituents whose Oct 2026 holding period ended at the `2026-10-29` sample cutoff date `LAST_D1`) are explicitly flagged as `sample_end_cutoff_20261029`, separate from the `3` historical M&A/reorganization exits (`delist_mna_last_close`):

| Holding Month | Ticker | Leg | Audited Flag | Holding Return | Verified Corporate Action / Cutoff Reason |
| :---: | :---: | :---: | :---: | :---: | :--- |
| `2013-06` | `VMED` | `QQQ` | `delist_mna_last_close` | `+2.72%` | Virgin Media acquired by Liberty Global (cash+stock merger completed `2013-06-07`; exited at last pre-merger close) |
| `2019-03` | `FOX` | `QQQ` | `delist_mna_last_close` | `-1.49%` | 21st Century Fox acquired by Disney / Fox Corp spin-off (completed `2019-03-19`; exited at last pre-close session) |
| `2019-03` | `FOXA` | `QQQ` | `delist_mna_last_close` | `-1.86%` | 21st Century Fox Class A acquired by Disney / Fox Corp spin-off (completed `2019-03-19`; exited at last pre-close session) |
| `2026-10` | `MPC` | `BestSec` | `sample_end_cutoff_20261029` | `+7.81%` | Active S&P 500 constituent; holding period truncated at `2026-10-29` sample cutoff (`NOT delisted`) |
| `2026-10` | `VLO` | `BestSec` | `sample_end_cutoff_20261029` | `-2.32%` | Active S&P 500 constituent; holding period truncated at `2026-10-29` sample cutoff (`NOT delisted`) |

### Item 5: Cross-Vendor `Open-to-Open` & `Max-Diff` Check + Default `V4 (No-ER)` in `audit_v4_from_scratch.py`
- **Default `V4 (No Election Reset)` vs `V4 + ER` in Part C of [`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py)**:
  - **Default `V4 (No ER)` on Panel Features**: **CAGR = `59.6538%`, Sharpe = `1.426`, Monthly MaxDD = `-27.99%`** (`0` pick mismatches, max `|net diff| = 1.40e-06` vs [`v4_symmetric_sharpe_top2_h5_v0_214m_ledger.csv`](../v4_symmetric_sharpe_top2_20261113/v4_symmetric_sharpe_top2_h5_v0_214m_ledger.csv)).
  - **Default `V4 (No ER)` on Raw Recomputed Features**: **CAGR = `59.5551%`, Sharpe = `1.423`, Monthly MaxDD = `-27.99%`** (exported to [`C_my_ledger_v0_raw_features.csv`](../v4_from_scratch_audit_20261114/C_my_ledger_v0_raw_features.csv)).
  - **`V4 + ER` on Panel / Raw Features**: **CAGR = `60.7764%` (panel) / `60.6770%` (raw), Sharpe = `1.444` / `1.441`**.
- **Cross-Vendor `Open-to-Open` & Worst-Case `Max-Diff` Check ([`D_cross_vendor_check.csv`](../v4_from_scratch_audit_20261114/D_cross_vendor_check.csv))**:
  - **Open-to-Open (`288 / 422` positions with $\ge 1$ alternative vendor having Open prices)**: `min_absdiff_oo > 1%`: **`0`**; **`max_absdiff_oo` (worst-case across ALL alternative vendors) `> 1%`**: **`0`** (`> 5%`: **`0`**).
  - **Close-to-Close (`297 / 422` positions with $\ge 1$ alternative vendor)**: `min_absdiff > 1%`: **`0`**; **`max_absdiff_cc` (worst-case across ALL alternative vendors) `> 1%`**: **`0`** (`> 5%`: **`0`**).

### Item 6: Removal of All Remaining `0.0` Fallbacks in `audit_v4_from_scratch.py` and `v4_robust_upgrade_research.py`
- In [`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py), changed `run_v4(..., nan_ret=None)` default so any missing `hold_ret` immediately raises `ValueError`.
- In [`v4_robust_upgrade_research.py`](../../v4_robust_upgrade_research.py), replaced `RET.get((t, k_), 0.0)` with a strict check that raises `ValueError` if `(t, k_) not in RET`. Both scripts execute with **`0` missing returns across all variants**.

---

## 2. Updated Summary Tables for All 4 Paper Experiments (`T1`, `T2`, `V1`, `V2`) & Sub-Periods

### Experiment `T1`: Horizon-Matched `SEP Surprise` ([`exp_T1_horizon_matched_sep_surprise.csv`](./exp_T1_horizon_matched_sep_surprise.csv))

| `T1` Variant (`2010-02-11 .. 2026-11-03` Real ETF, Next-Day Open + `10bp/side`) | Full `2010–2026` CAGR | Ex-2026 (`2010–2025`) CAGR | Daily MaxDD | Sharpe | Switches |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen Baseline `SEP` (Same-Target-Year Dot & Core PCE Revision)** 🏆 | **`54.89%`** | **`54.43%`** | **`-44.54%`** | **`1.259`** | `33` |
| **`T1a`. Horizon-Matched Dot vs Implied Rate (`DGS1` / `1Y1Y Fwd 2*DGS2-DGS1`)** | `42.50%` | `43.42%` | `-62.46%` | `1.021` | `28` |
| **`T1b`. Baseline `SEP` + Positive Horizon-Matched Forward Rate Shock** | `54.20%` | `53.71%` | `-44.54%` | `1.243` | `33` |

### Experiment `T2`: Volatility Control, Equal Risk-Budget Scaling & Stateful Walk-Forward `Vol_Z` ([`exp_T2_volatility_managed_tqqq.csv`](./exp_T2_volatility_managed_tqqq.csv))

| `T2` Variant (`Next-Day Open + 10bp/side`) | CAGR | Daily MaxDD | Sharpe | Annual Switches / Turnover |
| :--- | :---: | :---: | :---: | :---: |
| **0. Frozen `V1-Daily` (`Discrete Vol_Z 1.2/0.3 + Open NSL`, `2010–2026`)** 🏆 | **`54.89%`** | **`-44.54%`** | **`1.259`** | `2.0 / yr` |
| **0b. Conservative Ref (`Discrete Vol_Z 1.5/0.5 + Open NSL`, `2010–2026`)** | **`53.74%`** | **`-44.59%`** | **`1.221`** | `1.9 / yr` |
| **0c. Pure `SEP` (`3x TQQQ` in `SEP=ON` / Cash in `SEP=OFF`, `2010–2026`)** | `53.74%` | `-69.92%` | `1.084` | `0.5 / yr` |
| **`T2-WF1`. TRUE STATEFUL Walk-Forward `Vol_Z` (`2012–2026` Continuous Account)** | **`56.38%`** | **`-46.29%`** | **`1.293`** | `2.5 / yr` |
| **`T2-WF2`. TRUE STATEFUL Walk-Forward `Vol_Z` (`2012–2026` Fresh 2012 Start)** | **`56.38%`** | **`-46.29%`** | **`1.293`** | `2.2 / yr` |
| **`T2-WF3`. Spliced Approx Walk-Forward `Vol_Z` (`2012–2026` Reference)** | `56.97%` | `-46.29%` | `1.301` | — |
| **`T2a`. Moreira & Muir (2017) Continuous Inv-Var (`c=20%`, Monthly Rebal)** | `30.76%` | `-39.08%` | `1.022` | `4.1x / yr` |
| **`T2b`. Moreira & Muir (2017) Continuous Inv-Var (`c=20%`, Daily Rebal)** | `28.50%` | `-34.00%` | `1.026` | `8.3x / yr` |
| **`T2c`. Moreira & Muir (2017) Continuous Inv-Vol (`c=20%`, Monthly Rebal)** | `26.83%` | `-32.45%` | `1.110` | `2.8x / yr` |
| **`T2d`. Equal Risk-Budget Matched Inv-Var (`c=38%`, Monthly Rebal)** | `52.39%` | `-54.86%` | `1.164` | `1.8x / yr` |
| **`T2e`. Equal Risk-Budget Matched Inv-Var (`c=38%`, Daily Rebal, MDD Matched `-43.96%`)** | `50.85%` | `-43.96%` | `1.180` | `3.1x / yr` |

### Experiment `V1`: Robeco 3-Factor Fama-French (`MKT + SMB + HML`, `12-1M` & `36M` Blitz 2011) Residual Momentum ([`exp_V1_residual_momentum.csv`](./exp_V1_residual_momentum.csv))

| `V1` Ranking Factor (`V4` Architecture Fixed: `Top-2 / Hold <= 5`, `SEP`, Open + `10bp/side`) | Full `2009–2026` CAGR | **Ex-2026 (`2009–2025`) CAGR** | **Full Sharpe (`09–25` Sharpe)** | **Monthly MaxDD** | **Drop-Best-5M CAGR** | **Trade Win Rate** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline (`12-1 Total Return Sharpe`)** 🏆 | **`59.65%`** | **`50.38%`** | **`1.426` (`1.354`)** | **`-27.99%`** | **`46.43%`** | `70.16%` |
| **`V1a`. 1-Factor CAPM Residual Sharpe (`12-1M` Daily OLS)** | `51.25%` | `42.52%` | `1.309` (`1.204`) | `-35.59%` | `38.82%` | `74.02%` |
| **`V1b-FF3-12M`. 3-Factor (`MKT+SMB+HML`) `12-1M` Residual Sharpe** | `53.78%` | `44.39%` | `1.135` (`1.046`) | `-28.48%` | `36.69%` | `70.87%` |
| **`V1c-FF3-36M`. 3-Factor (`MKT+SMB+HML`) `36M` Beta + `12-1M` Residual Sharpe (Blitz 2011)** | **`52.96%`** | **`43.78%`** | **`1.322` (`1.239`)** | **`-29.91%`** | **`40.35%`** | `68.99%` |
| **`V1d`. 50/50 Blend (`Total Sharpe + FF3-12M Residual Sharpe`)** | `52.72%` | `43.04%` | `1.257` (`1.189`) | `-34.31%` | `39.10%` | `68.99%` |
| **`V1e`. 50/50 Blend (`Total Sharpe + FF3-36M Residual Sharpe`)** | `60.79%` | `51.50%` | `1.407` (`1.330`) | `-27.99%` | `47.41%` | `70.63%` |

### Experiment `V2`: Crash & Volatility Overlays on `V4` ([`exp_V2_crash_overlay.csv`](./exp_V2_crash_overlay.csv))

| `V2` Variant (`2009-01 .. 2026-10`, Open + `10bp/side`) | Full `2009–2026` CAGR | Ex-2026 (`2009–2025`) CAGR | Sharpe | Monthly MaxDD |
| :--- | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline (`SEP` Routing Only, Zero Patch)** 🏆 | **`59.65%`** | **`50.38%`** | **`1.426`** | **`-27.99%`** |
| **`V2a`. Daniel & Moskowitz (2016) Panic Overlay (`50%` Cash in Bear Rebound)** | `60.11%` | `50.83%` | `1.441` | `-27.99%` |
| **`V2b`. Barroso & Santa-Clara (2015) Vol-Targeted Momentum (`c=25%` in `SEP=ON`)** | `55.98%` | `46.75%` | `1.425` | `-27.99%` |
| **`V2c`. Combined DM Panic + Barroso Vol Target** | `56.58%` | `47.35%` | `1.442` | `-27.99%` |
