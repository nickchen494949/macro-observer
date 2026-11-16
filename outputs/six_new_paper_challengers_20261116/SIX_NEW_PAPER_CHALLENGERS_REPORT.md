# 6 Published Academic Paper Challengers — Full Clean-Room Evaluation & Audit Remediation Report (2026-11-16)

> **Script**: [`run_six_new_paper_challengers.py`](../../run_six_new_paper_challengers.py)  
> **V4 Summary CSV**: [`v4_challengers_p1_p2_p3_p4_summary.csv`](./v4_challengers_p1_p2_p3_p4_summary.csv)  
> **P4 Missing-Data & Ex-2020-11 Audit CSV**: [`p4_sue_missing_data_and_ex202011_audit.csv`](./p4_sue_missing_data_and_ex202011_audit.csv)  
> **TQQQ Summary CSV**: [`tqqq_challengers_p5_ebp_p6_vrp_summary.csv`](./tqqq_challengers_p5_ebp_p6_vrp_summary.csv)  
> **CBOE Nasdaq-100 Volatility Index (`VXN`) History**: [`cboe_vxn_history.csv`](./cboe_vxn_history.csv)

---

## Executive Summary & Audit Remediation Highlights

Following the external audit of commit `9f84929`, we completed all **4 audit remediations** without modifying the frozen baselines (`V4` and `V1-Daily TQQQ SEP`):

1. **Audit Remediation #1 (`P4a` & `V4` Simultaneous Exclusion of `2020-11` + Schema Fix for `filed_eps_diluted`)**:
   - **Same-Month Comparison Excluding `2020-11` (`213M`) on Old `9f84929` `P4a`**: Removing `2020-11` (`MRNA` `+161.2%` month, where portfolio return was `+106.22%` vs `V4` `+30.19%`) cuts the old `P4a` CAGR from `65.23%` to **`59.00%`** (`-6.23pp`), while `V4` changes from `59.65%` to **`57.64%`** (`-2.01pp`), confirming that **`75.6%` of the old `P4a`'s cumulative log excess return came from that single month**, and its `Ex-2020-11` Sharpe (`1.332`) still trails `V4` (`1.402`).
   - **Root-Cause Schema Discovery in `eps_quarterly_pit.parquet`**: Why did `P4a` in `9f84929` pick `MRNA` in `2020-10` in the first place? In `eps_quarterly_pit.parquet`, the columns `filed_eps_diluted` and `filed_eps_basic` have dtype `datetime64[ns]` (storing the *SEC filing date* on which `eps_diluted` was reported), whereas the actual dollar EPS numbers are stored in `eps_diluted_approx_adj` and `eps_diluted` (`float64`). Calling `pd.to_numeric(EPS_PIT["filed_eps_diluted"])` converted `datetime64[ns]` dates into nanosecond integers (`~1.5e18`), ranking stocks by filing-date intervals rather than dollar EPS surprises!
   - **True Dollar EPS Result**: Using actual dollar quarterly EPS (`eps_diluted_approx_adj` / `eps_diluted`), `MRNA` in October 2020 had a **negative** YoY earnings surprise (`-$0.59` vs Q3 2019 `-$0.37`, `eps_diff = -$0.22`, `true_SUE = -0.380`), while `ZM` (`true_SUE = +2.595`) and `TSLA` (`true_SUE = +0.266`) had the highest positive earnings surprises inside `Sharpe Top-5`. Across all 214 months, **True Dollar `SUE` (`P4a-TrueSUE-NaNLast`) achieves `56.11%` CAGR (`54.63%` Ex-`2020-11`, `46.20%` Ex-2026, Sharpe `1.375`)**, trailing `Frozen V4` (`59.65%` CAGR, Sharpe `1.426`) across every metric.

2. **Audit Remediation #2 (`P4` Missing-Data Handling & Exact 3-Trading-Day `[τ-1, τ, τ+1]` `EAR`)**:
   - Missing `SUE` and `EAR` values are now kept as `NaN` (never silently set to `0.0`, which previously ranked missing-data stocks above negative-surprise stocks `SUE < 0`).
   - Testing all 4 missing-data treatments (`NaN-Last`, `Cross-Sectional Median Impute`, `Pre-Filter Valid SUE Only`, and `Zero-Fill 0.0`) on True Dollar `SUE` produces `48.69% – 56.27%` CAGR and `1.258 – 1.379` Sharpe (all below `V4`'s `59.65%` / `1.426`). Even in the `2012–2026` mature XBRL era (`>90%` 8Q coverage), `True Dollar SUE` gets `52.36% – 56.49%` vs `V4`'s **`66.17%`**.
   - Recomputing `P4b` over **exact 3 NYSE trading days `[τ-1, τ, τ+1]`** around the SEC filing date (`59.14%` Full / `53.11%` Ex-`2020-11`, Sharpe `1.219`) and around the peak-volume announcement day in `[τ-10, τ]` (`63.07%` Full / `56.91%` Ex-`2020-11`, Sharpe `1.242`) shows that once `2020-11` (`+106.22%`) is excluded, both trail `V4` (`57.64%` Ex-`2020-11`, Sharpe `1.402`).

3. **Audit Remediation #3 (`P5` Federal Reserve `EBP` Restricted to Post-October-2016 Live Publication Era)**:
   - Because regular monthly public updates of the Federal Reserve's `EBP` started in **October 2016** (first 1M-lagged live reading available in **November 2016**), `P5a-LiveEraOnly` strictly disables `EBP` prior to `2016-11-01`.
   - **Key Finding**: **100% of the previously reported drawdown reduction (`-44.54% -> -37.24%`) came from the backfilled 2011 European Debt Crisis (`2011-08..10`), 5 years before `EBP` was publicly published!** In the actual 10-year live publication window (`2016-11-01 .. 2026-11-03`), `V1-Daily Baseline` already has a **`-37.22%`** Daily MaxDD with **`64.09%` CAGR** (Sharpe `1.434`), whereas `P5a-LiveEraOnly` has the **exact same `-37.22%` Live-Era MaxDD** (`-44.54%` Full MaxDD) while sacrificing **`-4.99pp/yr` CAGR** (`59.10%`, Sharpe `1.378`). Testing unrevised real-time daily FRED High-Yield OAS (`BAMLH0A0HYM2`, `P5c`) over `2010–2026` yields `54.42%` CAGR and `-44.54%` MaxDD (no improvement over baseline).

4. **Audit Remediation #4 (`P6` Same-Index, 21-Trading-Day Horizon-Matched `VRP`)**:
   - Using official CBOE Nasdaq-100 Volatility Index (`VXN`, `cboe_vxn_history.csv`) paired with `QQQ` 21-trading-day realized variance (`VRP_NDX = (VXN/100)^2 - RV21_QQQ^2`), the cross-index negative bias disappears (mean `VRP_NDX = +0.0077` vs old mismatched `VIX^2 - RV_QQQ^2 = -0.0138`).
   - `P6a-VRP-NDX-Matched` improves substantially over the old mismatched series (`51.82%` CAGR vs `44.09%`, switches cut from `61` to `36`), **but still trails `V1-Daily Baseline` (`54.89%` CAGR, Sharpe `1.259`, MaxDD `-44.54%`) across CAGR (`51.82%`), Sharpe (`1.172`), and MaxDD (`-44.94%`)**, because `TQQQ` volatility drag depends on the absolute level of realized volatility (`Vol_Z`), whereas `VRP` stays positive when `VXN` and `RV21_QQQ` spike together.

---

## Part 1: Dedicated `P4` Audit Table (`True Dollar EPS` vs `Old Timestamp Bug`, Missing-Data Rules & `Ex-2020-11`)

| Challenger Variant | Full 214M CAGR | **Ex-`2020-11` CAGR (`213M`)** | Ex-2026 CAGR (`09–25`) | **Mature XBRL `2012–26` CAGR** | `2020-11` Month Ret | Full Sharpe | **Ex-`2020-11` Sharpe** | Daily MaxDD | Drop-Best-10M CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen V4 Baseline (`12-1 Sharpe Top-2`)** 🏆 | **59.65%** | **57.64%** | **50.38%** | **66.17%** | +30.19% | **1.426** | **1.402** | **-37.32%** | **37.55%** |
| **P4a-TrueSUE-NaNLast** *(True Dollar EPS, `NaN` Ranked Last)* | 56.11% | 54.63% | 46.20% | 56.30% | +22.85% | 1.375 | 1.353 | -37.32% | 34.78% |
| **P4a-TrueSUE-CSMedian** *(True Dollar EPS, `NaN` = Universe Median)* | 51.30% | 49.85% | 41.76% | 52.36% | +22.85% | 1.295 | 1.272 | -37.32% | 30.94% |
| **P4a-TrueSUE-PreFilter** *(Pre-Filter Pool to Valid `SUE` Only)* | 48.69% | 47.25% | 39.37% | 52.58% | +22.85% | 1.258 | 1.235 | -37.32% | 28.51% |
| **P4a-TrueSUE-ZeroFill** *(True Dollar EPS, `NaN = 0.0` Comparison)* | 56.27% | 54.79% | 46.35% | 56.49% | +22.85% | 1.379 | 1.356 | -37.32% | 34.93% |
| **P4a-Old9f84929-BugRef** *(Old `filed_eps_diluted` Timestamp Bug)* | 65.23% | 59.00% | 57.38% | 72.31% | **+106.22%** | 1.263 | 1.332 | -37.68% | 37.03% |
| **P4b-EAR-3TD-Filing** *(Exact 3 Trading Days `[τ-1..τ+1]`, `NaN` Last)* | 59.14% | 53.11% | 51.81% | 63.60% | +106.22% | 1.219 | 1.302 | -34.18% | 33.61% |
| **P4b-EAR-3TD-PeakVol** *(Exact 3 Trading Days Peak-Vol Day, `NaN` Last)* | 63.07% | 56.91% | 55.80% | 67.97% | +106.22% | 1.242 | 1.312 | -37.03% | 35.34% |
| **P4c-TrueSUE-Blend** *(`50/50` Rank Blend: Sharpe + True Dollar SUE)* | 42.39% | 42.71% | 35.49% | 46.35% | -1.01% | 1.070 | 1.074 | -40.05% | 21.23% |
| **P4d-EAR3TD-Blend** *(`50/50` Rank Blend: Sharpe + Exact 3-TD EAR)* | 22.34% | 18.19% | 19.77% | 30.91% | +87.66% | 0.698 | 0.691 | -48.07% | 7.50% |

---

## Part 2: Complete V4 Challengers Table (`P1`–`P4`, with `Ex-2020-11` & Proper `NaN` Handling)

| Challenger Variant | Full 214M CAGR | **Ex-`2020-11` CAGR** | Ex-2026 CAGR (`09–25`) | `2012–26` CAGR | Full Sharpe | **Ex-`2020-11` Sharpe** | Daily MaxDD | Drop-Best-10M CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen V4 Baseline (`12-1 Sharpe Top-2`)** 🏆 | **59.65%** | **57.64%** | **50.38%** | **66.17%** | **1.426** | **1.402** | **-37.32%** | **37.55%** |
| **P1a-FIP-Top5Tie** (`%pos - %neg` Inside Top-5) | 45.41% | 43.68% | 38.69% | 49.43% | 1.247 | 1.221 | -38.85% | 27.67% |
| **P1b-FIP-Blend** (`50/50` Sharpe + FIP) | 28.76% | 27.07% | 21.58% | 30.68% | 0.956 | 0.924 | -46.31% | 14.27% |
| **P1c-SmoothSharpe** (Excl. Top-5 Jump Days) | 46.41% | 44.51% | 38.01% | 51.85% | 1.253 | 1.227 | -38.55% | 26.97% |
| **P2a-52WHigh-Top5Tie** (`P_t / High_252` Inside Top-5) | 35.47% | 33.66% | 27.27% | 39.14% | 1.020 | 0.991 | -37.03% | 17.87% |
| **P2b-52WHigh-Blend** (`50/50` Sharpe + 52W High) | 13.06% | 12.83% | 8.43% | 16.56% | 0.531 | 0.522 | -36.83% | 1.80% |
| **P2c-52WHigh-Pure** (Pure `P_t / High_252`) | 7.47% | 7.02% | 5.82% | 4.93% | 0.388 | 0.366 | -57.45% | 0.19% |
| **P3a-VolLow-Top5Tie** (Low `3M/12M` Volume Inside Top-5) | 40.79% | 35.38% | 33.82% | 41.17% | 1.020 | 1.131 | -30.57% | 20.37% |
| **P3b-VolHigh-Top5Tie** (High `3M/12M` Volume Inside Top-5) | 63.83% | 57.65% | 53.69% | 67.43% | 1.274 | 1.358 | -37.32% | 36.74% |
| **P3c-VolLow-Blend** (`50/50` Sharpe + Low Volume) | 20.49% | 16.75% | 17.67% | 21.10% | 0.694 | 0.683 | -41.46% | 6.16% |
| **P3d-VolHigh-Blend** (`50/50` Sharpe + High Volume) | 43.79% | 41.98% | 37.05% | 55.21% | 1.108 | 1.081 | -59.60% | 23.62% |

---

## Part 3: Remediated TQQQ SEP Challengers (`P5` Live-Era `EBP >= 2016-11` & `P6` Index-Matched `VRP_NDX / VRP_SPX`)

| TQQQ Challenger Variant | Full `2010–26` CAGR | Ex-2026 CAGR (`10–25`) | Full Daily Sharpe | **Full Daily MaxDD** | **Live EBP Era `2016-11..2026-11` CAGR** | **Live EBP Era Sharpe** | **Live EBP Era Daily MaxDD** | Switches |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Frozen V1-Daily Baseline (`Vol_Z 1.2/0.3 + NSL`)** 🏆 | **54.89%** | **54.43%** | **1.259** | **-44.54%** | **64.09%** | **1.434** | **-37.22%** | 33 |
| **P5a-LiveEraOnly** (`EBP > +0.50%` Active ONLY `>= 2016-11`) | 52.05% | 51.45% | 1.225 | -44.54% | 59.10% | 1.378 | **-37.22%** | 33 |
| **P5b-BackfilledRef** (`EBP > +0.50%` Backfilled `2010–2016` Ref) | 51.82% | 51.21% | 1.246 | -37.24% | 59.10% | 1.378 | -37.22% | 35 |
| **P5c-RealTime-HY-OAS** (Unrevised FRED `HY_OAS_Z > 1.2`) | 54.42% | 53.94% | 1.253 | -44.54% | 63.27% | 1.422 | -37.22% | 33 |
| **P6a-VRP-NDX-Matched** (`(VXN/100)^2 - RV21_QQQ^2 < -0.015`) | 51.82% | 50.82% | 1.172 | -44.94% | 59.63% | 1.323 | -44.66% | 36 |
| **P6b-VRP-NDX-ZScore** (`VRP_NDX_Z < -1.2` / `> -0.3`) | 49.84% | 48.68% | 1.047 | -67.40% | 60.54% | 1.174 | -67.40% | 51 |
| **P6c-VRP-SPX-Matched** (`(VIX/100)^2 - RV21_SPY^2 < -0.015`) | 47.41% | 46.21% | 1.040 | -69.92% | 61.98% | 1.212 | -69.92% | 37 |
| **P6d-VRP-SPX-ZScore** (`VRP_SPX_Z < -1.2` / `> -0.3`) | 50.89% | 49.69% | 1.075 | -67.40% | 60.97% | 1.170 | -67.40% | 34 |
| **P6e-VRP-NDX-Reentry** (`Vol_Z > 1.2` Exit + `VRP_NDX_Z > +1.0` Re-entry) | 55.12% | 54.67% | 1.243 | -44.54% | 64.09% | 1.434 | -37.22% | 33 |
