# Complete Independent Audit Response: Official Kenneth French FF3, Open-Executed Drifted T2/V2, and Cold-Start Walk-Forward Verification (2026-11-16)

> **Standalone Reproducible Scripts & Official Datasets (Committed on `main`)**:
> - Four Paper Experiments (`T1`, `T2`, `V1` Official Ken French FF3 + ETF Proxy, `V2`) & Walk-Forward Audit: [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py)
> - Official Kenneth French Daily FF3 Factors (`2004-01-02 .. 2026-09-30`, `MKT_RF`, `SMB`, `HML`, `RF`): [`ken_french_ff3_daily.csv`](./ken_french_ff3_daily.csv)
> - Official Kenneth French Monthly FF3 Factors (`2004-01 .. 2026-09`, `MKT_RF`, `SMB`, `HML`, `RF`): [`ken_french_ff3_monthly.csv`](./ken_french_ff3_monthly.csv)
> - Regression Sample Length & Fallback Audit Table: [`exp_V1_ff3_sample_length_audit.csv`](./exp_V1_ff3_sample_length_audit.csv)
> - From-Scratch Raw-Data V4 Rebuild (214M, Complete 213M, Ex-2026 204M, M&A Deal Audit): [`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py)
> - Cold-Start & Strict PIT Walk-Forward V4 + 12-Sleeve Ensemble (`V4.1`): [`v4_robust_upgrade_research.py`](../../v4_robust_upgrade_research.py)

---

## 1. Point-by-Point Remediation of the 5 Remaining Audit Items

### Item 1: True Official Kenneth French Fama-French 3 Factors (`MKT-RF`, `SMB`, `HML`, `RF`) + Full Sample-Length & Fallback Audit
- **Official Data Committed**: Downloaded and parsed the official **Kenneth French Data Library** daily and monthly 3-factor files from Dartmouth (`F-F_Research_Data_Factors_daily_CSV.zip` and `F-F_Research_Data_Factors_CSV.zip`), committed at [`ken_french_ff3_daily.csv`](./ken_french_ff3_daily.csv) (`5,722` trading days, `2004-01-02 .. 2026-09-30`) and [`ken_french_ff3_monthly.csv`](./ken_french_ff3_monthly.csv) (`273` months, `2004-01 .. 2026-09`). Because the last formation date in the 214-month backtest is `2026-09-30` (whose `12-1` window ends `2026-08-31`), official Kenneth French data covers **100% of all 214 formation dates**.
- **Regression Sample Length & Fallback Accounting ([`exp_V1_ff3_sample_length_audit.csv`](./exp_V1_ff3_sample_length_audit.csv))**:
  - Note on raw stock price start date: the project's raw Yahoo/Tiingo constituent stock files start on **`2007-01-03`**. Thus for the earliest formation date `2008-12-31` (`ym = 2009-01`, `t-1 = 2008-11-30`), `2007-01-03 .. 2008-11-30` contains `481` trading days (`22` monthly returns), growing to the full `36` months (`~734` trading days) by early `2010`.

| Pool | Total Valid Stock-Months | `12-1M` Daily Obs (`Min / Med / Max`) | **`12-1M` Fallback (`<120d`)** | `36-1M` Daily Obs (`Min / 10% / Med / Max`) | **`36-1M` Fallback (`<200d`)** | **`36-1M` Excluded in Strict (`<450d`)** | `36-1M` Monthly Obs (`Min / Med / Max`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`NDX_100`** | `21,196` | `223 / 230 / 233` | **`0 (0.0%)`** | `236 / 730 / 734 / 736` | **`0 (0.0%)`** | `190 (0.90%)` | `11 / 36 / 36` |
| **`SPX_BestSec_NonIT`** | `8,676` | `227 / 230 / 233` | **`0 (0.0%)`** | `240 / 730 / 733 / 736` | **`0 (0.0%)`** | `47 (0.54%)` | `11 / 36 / 36` |

- **Official Kenneth French FF3 vs ETF-Proxy Results ([`exp_V1_residual_momentum.csv`](./exp_V1_residual_momentum.csv))**:

| `V1` Ranking Factor (`V4` Architecture Fixed: `Top-2 / Hold <= 5`, `SEP`, Open + `10bp/side`) | Full `2009–2026` CAGR | **Ex-2026 (`2009–2025`) CAGR** | **Full Sharpe (`09–25` Sharpe)** | **Monthly MaxDD** | **Drop-Best-5M CAGR** | **Trade Win Rate** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline (`12-1 Total Return Sharpe`)** 🏆 | **`59.65%`** | **`50.38%`** | **`1.426` (`1.354`)** | **`-27.99%`** | **`46.43%`** | `70.16%` |
| **`V1a-KF`. Official Ken French 1-Factor CAPM (`12-1M` Daily OLS)** | `51.18%` | `42.45%` | `1.304` (`1.198`) | `-28.74%` | `38.76%` | `70.45%` |
| **`V1b-KF`. Official Ken French FF3 (`MKT-RF+SMB+HML`, `12-1M` Daily OLS)** | `51.60%` | `42.87%` | `1.112` (`0.997`) | `-39.60%` | `36.20%` | `68.29%` |
| **`V1c-KF-Strict`. Official Ken French FF3 `36M` Daily Beta + `12-1M` Residual (Strict Zero Fallback)** | **`56.06%`** | **`49.46%`** | **`1.383` (`1.289`)** | `-37.43%` | **`44.74%`** | `66.10%` |
| **`V1c-KF-FB`. Official Ken French FF3 `36M` Daily Beta + `12-1M` Residual (With `<200d` Fallback)** | `56.33%` | `48.89%` | `1.231` (`1.124`) | `-37.43%` | `41.99%` | `66.94%` |
| **`V1c-KF-Monthly-Blitz`. Official Ken French FF3 `36M` Monthly OLS (Blitz 2011 Eq.2 Pure $\sum \hat{\epsilon}/\sigma_{\hat{\epsilon}}$)** | `31.22%` | `24.00%` | `0.990` (`0.884`) | `-35.22%` | `21.30%` | `60.29%` |
| **`V1c-KF-Monthly-Alpha`. Official Ken French FF3 `36M` Monthly OLS ($\hat{\alpha} + \hat{\epsilon}$ Sharpe)** | `47.54%` | `42.36%` | `1.280` (`1.257`) | `-27.28%` | `35.52%` | `66.67%` |
| **`V1d-KF`. 50/50 Blend (`Total Sharpe` + Official Ken French `FF3-12M` Residual Sharpe)** | `51.80%` | `43.06%` | `1.291` (`1.184`) | `-35.18%` | `39.96%` | `66.93%` |
| **`V1e-KF`. 50/50 Blend (`Total Sharpe` + Official Ken French `FF3-36M` Strict Residual Sharpe)** | **`56.78%`** | **`50.18%`** | **`1.466` (`1.376`)** | **`-27.99%`** | **`45.85%`** | **`71.67%`** |
| **`V1f-ETF-Proxy`. ETF-Proxy 3-Factor (`SPY / IWM-SPY / XLF+XLE-XLK`) `36M` Residual Sharpe** | `52.96%` | `43.78%` | `1.322` (`1.239`) | `-29.91%` | `40.35%` | `68.99%` |
| **`V1g-ETF-Proxy`. 50/50 Blend (`Total Sharpe` + ETF-Proxy 3-Factor `36M` Residual Sharpe)** | `60.79%` | `51.50%` | `1.407` (`1.330`) | `-27.99%` | `47.41%` | `70.63%` |

> **Key Takeaway on Official Ken French FF3**:  
> 1. Under **true Official Kenneth French FF3**, `V1c-KF-Strict` (`56.06%` Full / `49.46%` Ex-2026, Sharpe `1.383`) and the 50/50 Blend `V1e-KF` (`56.78%` Full / `50.18%` Ex-2026, Sharpe `1.466`) **do not beat V4's CAGR (`59.65%` Full / `50.38%` Ex-2026)**, confirming the auditor's point that the `60.79%` figure (`V1g-ETF-Proxy`) was driven by the ETF sector proxy (`0.5*(XLF+XLE) - XLK`) rather than true Fama-French book-to-market (`HML`) and size (`SMB`) factors.
> 2. Textbook monthly Blitz (2011) Eq. 2 (`V1c-KF-Monthly-Blitz`, `31.22%` CAGR) strips out the 36-month regression intercept $\hat{\alpha}_i$ in addition to $\hat{\beta}_i F_m$, which severely penalizes multi-year secular compounders in a Long-Only Top-2 strategy; retaining $\hat{\alpha}_i$ (`V1c-KF-Monthly-Alpha`) restores CAGR to `47.54%` (Sharpe `1.280`).

---

### Item 2: Strict Next-Day `adjOpen` Execution + True Daily Weight Drift for `T2` (`eval_moreira_muir_continuous`)
- **Fix Applied**: Rewrote `eval_moreira_muir_continuous()` in [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py) so that:
  1. Signals (`sep_on` and `rvol_20`) are observed strictly at `prev_dt` Close and executed at **Next-Day Open (`adjOpen[i]`)**;
  2. Between rebalance dates, portfolio weights **drift daily with asset prices** (`adjOpen[i]/adjClose[i-1]` overnight and `adjClose[i]/adjOpen[i]` intraday) with zero implicit free rebalancing;
  3. On rebalance dates, exact `10bp/side` turnover cost is deducted at `adjOpen` against the pre-trade drifted weights `w_open_pre`.

| `T2` Variant (`2010-02-11 .. 2026-11-03`, Next-Day `adjOpen` + `10bp/side`) | CAGR | Daily MaxDD | Sharpe | Annual Switches / One-Way Turnover |
| :--- | :---: | :---: | :---: | :---: |
| **0. Frozen `V1-Daily` (`Discrete Vol_Z 1.2/0.3 + Open NSL`, `2010–2026`)** 🏆 | **`54.89%`** | **`-44.54%`** | **`1.259`** | `2.0 switches/yr` |
| **0b. Conservative Ref (`Discrete Vol_Z 1.5/0.5 + Open NSL`, `2010–2026`)** | **`53.74%`** | **`-44.59%`** | **`1.221`** | `1.9 switches/yr` |
| **0c. Pure `SEP` (`3x TQQQ` in `SEP=ON` / Cash in `SEP=OFF`, `2010–2026`)** | `53.74%` | `-69.92%` | `1.084` | `0.5 switches/yr` |
| **`T2-WF1`. TRUE STATEFUL Walk-Forward `Vol_Z` (`2012–2026` Cold-Cash Start at `2012-01-03` Open)** | **`56.37%`** | **`-46.29%`** | **`1.293`** | `2.2 switches/yr` |
| **`T2-WF2`. TRUE STATEFUL Walk-Forward `Vol_Z` (`2012–2026` Strict PIT `2010–2011` Warmup)** | **`56.38%`** | **`-46.29%`** | **`1.293`** | `2.2 switches/yr` |
| **`T2-WF3`. Spliced Approx Walk-Forward `Vol_Z` (`2012–2026` Reference)** | `56.97%` | `-46.29%` | `1.301` | — |
| **`T2a`. Moreira & Muir (2017) Continuous Inv-Var (`c=20%`, Monthly Open Rebal + Daily Drift)** | `30.19%` | `-38.40%` | `1.008` | `4.1x / yr` |
| **`T2b`. Moreira & Muir (2017) Continuous Inv-Var (`c=20%`, Daily Open Rebal)** | `28.61%` | `-34.86%` | `1.024` | `8.3x / yr` |
| **`T2c`. Moreira & Muir (2017) Continuous Inv-Vol (`c=20%`, Monthly Open Rebal + Daily Drift)** | `26.51%` | `-32.42%` | `1.102` | `2.8x / yr` |
| **`T2d`. Equal Risk-Budget Inv-Var (`c=38%`, Monthly Open Rebal + Daily Drift)** | `51.55%` | `-53.93%` | `1.155` | `1.7x / yr` |
| **`T2e`. Equal Risk-Budget Inv-Var (`c=38%`, Daily Open Rebal, MDD Matched `-45.27%`)** | `50.10%` | `-45.27%` | `1.168` | `3.1x / yr` |

---

### Item 3: Zero Look-Ahead Walk-Forward Initialization (`2012 Cold-Cash Start` & `Strict PIT Warmup`)
- **`V4` Stateful Walk-Forward (`2012-01 .. 2026-10`, 178 Months, [`v4_robust_upgrade_research.py`](../../v4_robust_upgrade_research.py) & [`walk_forward_stateful_sep_ledger.csv`](../v4_robust_upgrade_20261115/walk_forward_stateful_sep_ledger.csv))**:
  1. **2012 Cold-Cash Start (`init_mode="cold_cash_2012"`)**: Account starts from **100% Cash (`hq=[], hb=[], prev_w={}`)** at `2012-01` Open, buys fresh Top-`n` picks under `chosen["2012"]` (`sharpe_top1_hold6`, where `ALXN` is Rank #1 in NDX at `2011-12-30`), and **pays the full `10bp` initial buy cost (`to = 1.0000`)** in `2012-01`:
     - With `SEP`: **CAGR = `49.16%`, Sharpe = `1.269`, Monthly MaxDD = `-27.39%`**.
     - Without `SEP`: **CAGR = `40.97%`, Sharpe = `1.053`, Monthly MaxDD = `-40.70%`**.
  2. **Strict PIT 2009–2011 Warmup (`init_mode="strict_pit_warmup"`)**: Account starts from Cash at `2009-01` with prior `("sharpe", 2, 5)`, selects `2010` config at `2009-12-31` from `2009` returns, selects `2011` config at `2010-12-31` from `2009–2010` returns, and selects `2012` config at `2011-12-31` from `2009–2011` returns:
     - With `SEP`: **CAGR = `49.17%`, Sharpe = `1.269`, Monthly MaxDD = `-27.39%`**.
     - Without `SEP`: **CAGR = `40.98%`, Sharpe = `1.053`, Monthly MaxDD = `-40.70%`**.
- **`TQQQ` Stateful Walk-Forward (`2012-01-03 .. 2026-11-03`, [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py))**:
  - **Cold-Cash Start at `2012-01-03` Open (`eq = 1.0 - 0.001`)**: **CAGR = `56.37%`, Daily MaxDD = `-46.29%`, Sharpe = `1.293`**.
  - **Strict PIT `2010–2011` Warmup**: **CAGR = `56.38%`, Daily MaxDD = `-46.29%`, Sharpe = `1.293`**.

---

### Item 4: Full Drifted-Weight Portfolio Simulation with `10bp/side` Turnover Cost for `V2` ([`exp_V2_crash_overlay.csv`](./exp_V2_crash_overlay.csv))
- **Fix Applied**: Replaced linear return blending (`0.5 * r_net + 0.5 * r_cash`) with `sim_v2_stateful()` in [`run_four_paper_experiments.py`](../../run_four_paper_experiments.py), which constructs exact monthly target weights (`{q1: 0.5*scale, q2: 0.5*scale, "SGOV": 1.0 - scale}`) and computes the exact two-way turnover against `prev_drifted_w`, charging `10bp/side` on every scale-down and scale-up trade:

| `V2` Variant (`2009-01 .. 2026-10`, Open Execution + Full Drifted Turnover Cost) | Full `2009–2026` CAGR | Ex-2026 (`2009–2025`) CAGR | Sharpe | Monthly MaxDD | Two-Way Turnover |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen `V4` Baseline (`SEP` Routing Only, Zero Patch)** 🏆 | **`59.65%`** | **`50.38%`** | **`1.426`** | **`-27.99%`** | `7.00x / yr` |
| **`V2a`. Daniel & Moskowitz (2016) Panic Overlay (`50%` Cash in Bear Rebound, Full Turnover Cost)** | `60.05%` | `50.77%` | `1.440` | `-27.99%` | `7.27x / yr` |
| **`V2b`. Barroso & Santa-Clara (2015) Vol-Targeted Momentum (`c=25%` in `SEP=ON`, Full Turnover Cost)** | `55.94%` | `46.71%` | `1.424` | `-27.99%` | `7.03x / yr` |
| **`V2c`. Combined DM Panic + Barroso Vol Target (Full Turnover Cost)** | `56.51%` | `47.27%` | `1.441` | `-27.99%` | `7.17x / yr` |

---

### Item 5: Complete 213 Open-to-Open Months (`2009-01 .. 2026-09`), M&A Deal Consideration Verification, & Vendor Coverage ([`audit_v4_from_scratch.py`](../../audit_v4_from_scratch.py))
1. **Complete 213 Open-to-Open Months (`2009-01 .. 2026-09`, Excluding Oct 2026 Partial Cutoff Month)**:
   - **Default `V4 (No ER)` on Panel Features**: `214M` CAGR = **`59.65%`**, **Complete `213M` (`2009-01 .. 2026-09`) CAGR = `59.87%`** (`Sharpe = 1.427` ex-rf / `1.467` rf=0), **Ex-2026 `204M` (`2009-01 .. 2025-12`) CAGR = `50.38%`** (`Sharpe = 1.354` ex-rf / `1.394` rf=0).
   - **Default `V4 (No ER)` on Raw Recomputed Features**: `214M` CAGR = **`59.56%`**, **Complete `213M` CAGR = `59.77%`** (`Sharpe = 1.425`), **Ex-2026 `204M` CAGR = `50.28%`** (`Sharpe = 1.351`).
2. **M&A Deal Consideration Verification (`3` Historical Exits in [`D_invested_positions.csv`](../v4_from_scratch_audit_20261114/D_invested_positions.csv))**:
   - **`2013-06 VMED` (`+2.72%`)**: Virgin Media acquisition by Liberty Global completed `2013-06-07` paid `$17.50` cash + `0.2582` LBTYA + `0.1928` LBTYK per VMED share (`~$51.00/sh` closing consideration vs `$49.65` entry Open on `2013-06-03` = `+2.72%`).
   - **`2019-03 FOX` (`-1.49%`) & `2019-03 FOXA` (`-1.86%`)**: 21st Century Fox (`TFCF` / `TFCFA`) distributed `1/3` share of spin-off Fox Corp (`~$12.92` per 21CF share) on `2019-03-19` plus `$38.00/sh` Disney merger consideration on `2019-03-20` (`~$50.92/sh` combined package = `+1.11%` / `+0.57%` vs `$50.36` / `$50.63` entry Open on `2019-03-01`). The ledger conservatively uses the last pre-close price `$49.61` / `$49.69` (`-1.49%` / `-1.86%`).
3. **Accounting for the `134 / 422` Single-Open-Vendor Positions in [`D_cross_vendor_check.csv`](../v4_from_scratch_audit_20261114/D_cross_vendor_check.csv)**:
   - `288 / 422` positions have $\ge 2$ independent Open-to-Open vendors (`max_absdiff_oo > 1%: 0`);
   - `9` additional positions (`297 / 422` total) have a verified 2nd Close-to-Close vendor (`max_absdiff_cc <= 0.05%`);
   - Of the remaining `125` single-vendor (`yahoo`) positions, **`120 / 125` (`96%`) occur in `2018-04 .. 2026-10`**, after the Quandl WIKI dataset ended in `2018-03`.
