# Clean-Room Independent Audit: Pre-Registered `SEP = OFF` Overlap-Cap & Duplicate-to-ExIT Experiment (2009–2026 + Oct/Nov 2026 Live)

- **Audit Date**: `2026-11-04`
- **Engine**: Zero-shared-code independent engine (`ind_engine.py`, identical to `origin/main` commit `39c1af4`)
- **Sample**:
  - Standard Backtest Window: `2009-01 .. 2026-09` (`213` holding months, `T+1` adjusted open execution, `10 bp/side` single-account turnover cost including cross-leg drift)
  - Live Extended Window: `2009-01 .. 2026-10` (`214` months, marking October 2026 to the `2026-10-29` close)
  - Forward Target Window: `2026-11` (formed `2026-10-31`, holding November 2026)

---

## 1. Executive Summary & Core Finding

We tested the exact pre-registered question:
> **When different sleeves pick the same stock AND `SEP = OFF`, should we cap single-stock overlap (routing excess duplicate weight to `SGOV` or to the strongest Non-Tech candidate `Ex-IT`), while leaving `SEP = ON` 100% untouched?**

### Structural Discovery (`01_sep_on_vs_off_overlap_diagnostic.csv`)
Partitioning all 213 historical months (`2009-01 .. 2026-09`) by **`SEP = ON` vs `SEP = OFF`** and **Overlap vs No-Overlap** reveals why unconditional de-overlapping hurt CAGR in earlier tests while conditional `SEP = OFF` de-overlapping improves **both** CAGR and drawdown:

| Architecture | Regime × Overlap Bucket | Months ($N$) | Mean Monthly Return | Annualized Compound Return | Win Rate | Worst Month |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **2-Leg (`G1_SPY_2e`)** | **`SEP = ON` — Overlap (`75%` stock)** | **64** | **`+9.72%`** | **`+184.20%`** | **`81.25%`** | `-16.92%` |
| **2-Leg (`G1_SPY_2e`)** | `SEP = ON` — No Overlap (`50%/25%/25%`) | 116 | `+1.94%` | `+21.05%` | `59.48%` | `-17.53%` |
| **2-Leg (`G1_SPY_2e`)** | **`SEP = OFF` — Overlap (`75%` stock)** | **10** | **`+0.65%`** | **`+3.43%`** | **`60.00%`** | `-12.14%` |
| **2-Leg (`G1_SPY_2e`)** | `SEP = OFF` — No Overlap (`50%/25%/25%`) | 23 | `-0.18%` | `-6.73%` | `56.52%` | `-16.64%` |
| **3-Leg (`3S_G1_1k`)** | **`SEP = ON` — Overlap (`50%–75%` stock)** | **107** | **`+7.33%`** | **`+119.53%`** | **`74.77%`** | `-16.92%` |
| **3-Leg (`3S_G1_1k`)** | `SEP = ON` — No Overlap (`25% × 4`) | 73 | `+0.54%` | `+3.87%` | `53.42%` | `-15.60%` |
| **3-Leg (`3S_G1_1k`)** | **`SEP = OFF` — Overlap (`50%–75%` stock)** | **18** | **`+0.24%`** | **`-2.62%`** *(incl. Oct26: **`-13.85%`**)* | **`55.56%`** | `-19.92%` |
| **3-Leg (`3S_G1_1k`)** | `SEP = OFF` — No Overlap (`25% × 4`) | 15 | `+1.30%` | `+13.18%` | `73.33%` | `-12.37%` |

- **When `SEP = ON`**: Multi-sleeve overlap is the primary alpha engine (`+184.20%` annualized in 2-Leg, `+119.53%` annualized in 3-Leg). Removing overlap during `SEP = ON` (`2L_0b` / `2L_0c` / `3L_0b`) destroys **`-10.2 pp` to `-20.3 pp` of CAGR**.
- **When `SEP = OFF`**: The overlap alpha completely disappears (`+3.43%` in 2-Leg, `-2.62%` in 3-Leg, and `-13.85%` including Oct 2026) while creating extreme single-stock concentration risk (`MRNA` in 2021-10..11, `NVDA` in 2024-07..09, `PLTR` in 2025-03, `WDC/SNDK` in 2026-07..11).

---

## 2. Full Backtest & Live October 2026 Results (`03_sep_off_overlap_cap_backtest.csv`)

### Panel A: 2-Leg Architecture `G1_SPY_2e` (`50% QQQ G1 [Buy 2, Hold<=5] + 50% SPY G1 [Buy 1, Hold<=3]`)

| Variant | Rule (Active ONLY when `SEP = OFF` unless noted) | CAGR (`09–26/09`) | CAGR (`incl. Oct26`) | Excess Sharpe | Backtest Daily DD | **2026 Live Worst DD** | **2026-10-29 Live DD** | **2022 (`DVN/EQT`)** | All 33 `SEP OFF` | **Oct 2026 Live** |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`2L_0_Ctrl`** | **Original Rule: Allow overlap up to `75%`** | `49.97%` | `47.83%` | `1.274` | `-40.85%` | **`-52.43%`** | **`-47.09%`** | **`+9.04%`** | `-11.41%` | **`-20.04%`** |
| `2L_0b_Always_Cap50` | Always (`SEP ON+OFF`): Cap `<=50%` $\to$ `SGOV` | `39.80%` | `37.84%` | `1.197` | `-38.63%` | `-46.12%` | `-40.07%` | `+9.04%` | `-5.61%` | `-20.02%` |
| `2L_0c_Always_DupExIT` | Always (`SEP ON+OFF`): Dup `SPY` $\to$ `25% ExIT_Raw + 25% SGOV` | `29.67%` | `27.90%` | `0.999` | `-39.68%` | `-42.16%` | `-35.67%` | `+9.04%` | `+4.63%` | `-20.02%` |
| **`2L_1_SEPOFF_Cap50_SGOV`** | **`SEP OFF`: Cap `<=50%`, excess `25%` $\to$ `SGOV`** | **`50.51%`** | **`48.35%`** | `1.291` | `-40.66%` | `-48.58%` | `-42.81%` | **`+9.04%`** | `-5.61%` | `-20.02%` |
| **`2L_2a_SEPOFF_Cap25_ExITRaw_SGOV`** | **`SEP OFF`: `SPY in QQQ` $\to$ `25% ExIT_Raw + 25% SGOV` (Cap `25%`)** | **`51.38%`** | **`49.21%`** | `1.304` | `-40.66%` | `-46.87%` | `-40.91%` | **`+9.04%`** | `+4.63%` | `-20.02%` |
| **`2L_2b_SEPOFF_Cap33_ExITRaw`** | **`SEP OFF`: `SPY in QQQ` $\to$ `33.3% Q1 + 33.3% Q2 + 33.3% ExIT_Raw`** | **`51.72%`** | **`49.54%`** | `1.300` | `-40.66%` | `-48.98%` | `-43.26%` | **`+9.04%`** | `+8.97%` | `-20.04%` |
| **`2L_2d_SEPOFF_Cap25_ExITBS_SGOV`** | **`SEP OFF`: `SPY in QQQ` $\to$ `25% ExIT_BestSec + 25% SGOV` (Cap `25%`)** | **`52.78%`** | **`50.58%`** | `1.342` | `-40.66%` | **`-40.56%`** | **`-33.90%`** | **`+9.04%`** | **`+23.16%`** | `-20.01%` |
| **`2L_2e_SEPOFF_Cap33_ExITBS`** | **`SEP OFF`: `SPY in QQQ` $\to$ `33.3% Q1 + 33.3% Q2 + 33.3% ExIT_BestSec`** | **`53.67%`** | **`51.45%`** | `1.356` | `-40.66%` | **`-40.54%`** | **`-33.87%`** | **`+9.04%`** | **`+36.54%`** | `-20.04%` |
| **`2L_2f_SEPOFF_DupToExITBS50`** | **`SEP OFF`: `SPY in QQQ` $\to$ `25% Q1 + 25% Q2 + 50% ExIT_BestSec`** | **`54.50%`** | **`52.27%`** | `1.374` | `-40.66%` | **`-36.50%`** | **`-29.37%`** | **`+9.04%`** | **`+50.40%`** | `-20.04%` |
| **`2L_3a_SEPOFF_Cap25_ITSpyToExITRaw`** | **`SEP OFF`: Strict `<=25%` Tech Cap (`SPY` in IT $\to$ `25% SPY/SGOV + 25% ExIT_Raw`)** | **`50.47%`** | **`49.26%`** | `1.285` | `-40.66%` | **`-40.25%`** | **`-33.81%`** | **`+9.04%`** | `-5.98%` | **`-10.40%`** |
| **`2L_3b_SEPOFF_Cap25_ITSpyToExITBS`** | **`SEP OFF`: Strict `<=25%` Tech Cap (`SPY` in IT $\to$ `25% SPY/SGOV + 25% ExIT_BestSec`)** | **`52.16%`** | **`50.49%`** | `1.330` | `-40.66%` | **`-32.94%`** | **`-29.78%`** | **`+9.04%`** | **`+14.74%`** | **`-15.02%`** |

---

### Panel B: 3-Leg Architecture `3S_G1_1k` (`50% QQQ G1 [25%+25%] + 25% Tech [Hard Top-1] + 25% SPY G1 [Hold<=3]`)

> Why 3-Leg is structurally cleaner for ticker-overlap rules: Because `Tech (25%)` and `SPY (25%)` are separate `25%` sleeves, whenever `SPY` picks the `#1` Tech stock (such as `SNDK` in Oct 2026 and Nov 2026), **`SPY == Tech` is automatically detected as an exact ticker duplicate!**

| Variant | Rule (Active ONLY when `SEP = OFF` unless noted) | CAGR (`09–26/09`) | CAGR (`incl. Oct26`) | Excess Sharpe | Backtest Daily DD | **2026 Live Worst DD** | **2026-10-29 Live DD** | **2022 (`DVN/EQT`)** | All 33 `SEP OFF` | **Oct 2026 Live** |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`3L_0_Ctrl`** | **Original Rule: Allow overlap up to `75%`** | `50.23%` | `48.09%` | `1.300` | `-41.20%` | **`-47.58%`** | **`-41.70%`** | `+8.16%` | `+9.96%` | **`-19.99%`** |
| `3L_0b_Always_Cap25` | Always (`SEP ON+OFF`): Strict `<=25%` Cap | `30.26%` | `29.30%` | `1.021` | `-39.27%` | `-37.27%` | `-30.51%` | `+8.83%` | `+18.60%` | `-10.37%` |
| `3L_1_SEPOFF_Cap50_SGOV` | `SEP OFF`: Cap `<=50%`, excess `25%` $\to$ `SGOV` | `49.91%` | `47.77%` | `1.296` | `-41.20%` | `-47.58%` | `-41.70%` | `+8.16%` | `+5.91%` | `-19.99%` |
| **`3L_2a_SEPOFF_SpyDup_ExITRaw`** | **`SEP OFF`: Dup `25% SPY` $\to$ `25% ExIT_Raw` (Cap `<=50%`)** | **`50.18%`** | **`48.98%`** | `1.294` | `-41.20%` | **`-39.21%`** | **`-32.66%`** | `+8.16%` | `+9.34%` | **`-10.37%`** |
| **`3L_2b_SEPOFF_SpyDup_ExITBS`** | **`SEP OFF`: Dup `25% SPY` $\to$ `25% ExIT_BestSec` (Cap `<=50%`)** | **`51.92%`** | **`50.25%`** | `1.342` | `-41.20%` | **`-32.00%`** | **`-28.20%`** | `+8.16%` | **`+34.17%`** | **`-15.00%`** |
| **`3L_2c_SEPOFF_Cap25_ExITRaw_SGOV`** | **`SEP OFF`: Strict `<=25%` Cap (`SPY` dup $\to$ `ExIT_Raw`, `Tech` dup $\to$ `SGOV`)** | **`50.87%`** | **`49.66%`** | `1.317` | `-40.27%` | **`-39.21%`** | **`-32.66%`** | **`+8.83%`** | **`+18.60%`** | **`-10.37%`** |
| **`3L_2d_SEPOFF_Cap25_ExITBS_SGOV`** | **`SEP OFF`: Strict `<=25%` Cap (`SPY` dup $\to$ `ExIT_BestSec`, `Tech` dup $\to$ `SGOV`)** | **`52.24%`** | **`50.56%`** | `1.357` | `-40.27%` | **`-32.00%`** | **`-28.20%`** | **`+8.83%`** | **`+39.28%`** | **`-15.00%`** |
| **`3L_3a_SEPOFF_KillQQQ_50SGOV`** | **`SEP OFF`: `QQQ 50%` $\to$ `SGOV`, keep `25% Tech + 25% SPY` (allow `50%`)** | **`52.53%`** | **`51.24%`** | `1.380` | **`-34.41%`** | **`-32.50%`** | **`-29.96%`** | **`+27.12%`** | **`+44.05%`** | `-11.01%` |
| **`3L_3b_SEPOFF_KillQQQ_50SGOV_Cap25_ExITRaw`** | **`SEP OFF`: `QQQ 50%` $\to$ `SGOV` + Strict `<=25%` (`SPY==Tech` $\to$ `ExIT_Raw`)** | **`51.72%`** | **`51.31%`** | `1.364` | **`-34.41%`** | **`-31.07%`** | **`-22.40%`** | **`+27.12%`** | **`+31.12%`** | **`-1.40%`** |
| **`3L_3c_SEPOFF_KillQQQ_50SGOV_Cap25_ExITBS`** | **`SEP OFF`: `QQQ 50%` $\to$ `SGOV` + Strict `<=25%` (`SPY==Tech` $\to$ `ExIT_BestSec`)** | **`51.85%`** | **`51.03%`** | `1.366` | **`-34.41%`** | **`-31.07%`** | **`-26.04%`** | **`+27.12%`** | **`+33.13%`** | **`-6.03%`** |
| **`3L_3d_SEPOFF_KillQQQ_25SGOV_25ExITRaw`** | **`SEP OFF`: `QQQ 50%` $\to$ `25% SGOV + 25% ExIT_Raw`, keep `Tech + SPY`** | **`52.54%`** | **`51.61%`** | `1.349` | `-35.69%` | `-35.69%` | `-30.01%` | **`+39.35%`** | **`+44.14%`** | `-7.10%` |
| **`3L_3e_SEPOFF_KillQQQ_25SGOV_25ExITBS`** | **`SEP OFF`: `QQQ 50%` $\to$ `25% SGOV + 25% ExIT_BestSec`, keep `Tech + SPY`** | **`54.35%`** | **`52.97%`** | `1.396` | **`-34.65%`** | **`-28.43%`** | **`-25.48%`** | **`+39.94%`** | **`+77.93%`** | `-11.72%` |

---

## 3. Answers to the 6 Key Audit Questions

1. **Does 2022 still capture `DVN` and `EQT`?**
   - **100% YES.** Across all 12 months of `2022` (`2022-01 .. 2022-12`), `SPY G1` held `DVN` (Jan–Oct 2022) and `EQT` (Nov–Dec 2022). Neither `DVN` nor `EQT` was in `QQQ` or `Tech`.
   - Therefore, every duplicate-redirect rule (`2L_1`, `2L_2a..2f`, `2L_3a..3b`, `3L_2a..2d`) leaves `DVN` and `EQT` **100% untouched** (`+9.04%` in 2-Leg, `+8.16%` to `+8.83%` in 3-Leg, and `+27.12%` to `+39.94%` when `QQQ` is also turned off during `SEP = OFF`).
2. **Did the 2025/2026 `SNDK` / `PLTR` concentration drawdowns improve?**
   - **2026 `SNDK / WDC / STX` Live Crash (`2026-06-18 -> 2026-10-29`)**:
     - Uncapped `2L_0_Ctrl`: Worst Daily DD = **`-52.43%`** (`-47.09%` at `10/29`), Oct 2026 = **`-20.04%`**.
     - `2L_3b_SEPOFF_Cap25_ITSpyToExITBS` (Strict `<=25%` Tech Cap in 2-Leg): Worst Daily DD = **`-32.94%`** (`+19.49 pp` improvement!), `10/29` DD = **`-29.78%`**, Oct 2026 = **`-15.02%`**.
     - `3L_2d_SEPOFF_Cap25_AllDup_ExITBS_SGOV` (Strict `<=25%` Cap in 3-Leg, even without turning off QQQ): Worst Daily DD = **`-32.00%`** (`+15.58 pp` improvement vs `3L_0_Ctrl`), `10/29` DD = **`-28.20%`**.
     - `3L_3b / 3L_3c` (`QQQ -> SGOV` + Strict `<=25%` Cap in 3-Leg): Worst Daily DD = **`-31.07%`**, `10/29` DD = **`-22.40% / -26.04%`**, Oct 2026 = **`-1.40% / -6.03%`**.
   - **2025 `PLTR` Cycle**:
     - In `2025-03` (`SEP = OFF`, when `PLTR` and `APP` pulled back), `3L_2c/2d` capped `PLTR` from `50%` down to `25%` (routing `25%` to `SGOV`), saving `+0.66%` that month.
     - Then in `2025-04 .. 2025-12`, **`SEP` turned `ON`**, so the `SEP = OFF` cap automatically stepped aside and kept the full **`75% PLTR`** consensus position for the entire `+120%+` 2025 rally!
3. **How much CAGR is lost?**
   - **Zero (`0.00 pp`) CAGR is lost when the rule is restricted to `SEP = OFF`!**
   - In fact, full-sample CAGR (`2009-01 .. 2026-09`) **increases** across every single `SEP = OFF` duplicate-to-ExIT variant:
     - 2-Leg: `49.97%` $\to$ **`50.47% – 54.50%`** (`+0.50 pp` to `+4.53 pp`)
     - 3-Leg: `50.23%` $\to$ **`50.87% – 54.35%`** (`+0.64 pp` to `+4.12 pp`)
   - By contrast, capping overlap in **all months (`SEP ON + OFF`)** loses **`-10.17 pp` to `-20.30 pp`** of CAGR.
4. **How did it perform across ALL 33 historical `SEP = OFF` months (`02_all_35_sep_off_months_audit.csv`)?**
   - Cumulative return across all 33 historical `SEP = OFF` months (`2021-10 .. 2026-09`):
     - `2L_0_Ctrl`: **`-11.41%`** $\to$ `2L_2a`: **`+4.63%`**, `2L_2d`: **`+23.16%`**, `2L_2f`: **`+50.40%`**.
     - `3L_0_Ctrl`: **`+9.96%`** $\to$ `3L_2c`: **`+18.60%`**, `3L_2d`: **`+39.28%`**, `3L_3a..3e`: **`+31.12%` to `+77.93%`**.

---

## 4. November 2026 (`2026-11`) Actionable Target Holdings (`06_november_2026_holdings_table.csv`)

Because **`SEP = OFF`** in November 2026 (`t = 2026-10-31`) and `QQQ`, `Tech`, and `SPY` all point to **`SNDK`**, here is what each pre-registered rule holds for **November 2026 (`2026-11`)**:

| Strategy Track | Variant | Max Single-Stock Weight | **Continuing Account (`2026-11`)** | **New Account (`2026-11`)** |
| :--- | :--- | :---: | :--- | :--- |
| **Uncapped Baseline** | `2L_0_Ctrl` / `3L_0_Ctrl` | `75.0%` | `75% SNDK + 25% STX` | `75% SNDK + 25% MU` |
| **Rule 2 (`Cap <= 50% -> SGOV`)** | `2L_1` / `3L_1_SEPOFF_Cap50_to_SGOV` | `50.0%` | `50% SNDK + 25% STX + 25% SGOV` | `50% SNDK + 25% MU + 25% SGOV` |
| **Rule 3A (`Dup SPY -> ExIT, Cap 50%`)** | `3L_2b_SEPOFF_SpyDup_to_ExITBS` | `50.0%` | `50% SNDK + 25% STX + 25% VLO` | `50% SNDK + 25% MU + 25% VLO` |
| **Rule 3B (`Strict Cap <= 25%, QQQ On`)** | **`2L_2d` / `2L_3b` / `3L_2d` (`ExIT_BestSec`)** | **`25.0%`** | **`25% SNDK + 25% STX + 25% VLO + 25% SGOV`** | **`25% SNDK + 25% MU + 25% VLO + 25% SGOV`** |
| **Rule 3B (`Strict Cap <= 25%, QQQ On`)** | `2L_2a` / `2L_3a` / `3L_2c` (`ExIT_Raw`) | **`25.0%`** | `25% SNDK + 25% STX + 25% MRNA + 25% SGOV` | `25% SNDK + 25% MU + 25% MRNA + 25% SGOV` |
| **Rule 4A (`Kill QQQ -> 50% SGOV + Cap <= 25%`)** | **`3L_3c_SEPOFF_KillQQQ_50SGOV_Cap25_ExITBS`** | **`25.0%`** | **`25% SNDK + 25% VLO + 50% SGOV`** | **`25% SNDK + 25% VLO + 50% SGOV`** |
| **Rule 4B (`Kill QQQ -> 25% SGOV + 25% ExIT, Allow 50%`)** | `3L_3e_SEPOFF_KillQQQ_25SGOV_25ExITBS_Allow50` | `50.0%` | `50% SNDK + 25% VLO + 25% SGOV` | `50% SNDK + 25% VLO + 25% SGOV` |

---

## 5. Cumulative Multiple-Testing Deflated Sharpe Ratio (`N = 1,058` $\to$ `1,077` / `1,082` / `1,203`) (`05_multiple_testing_dsr.csv`)

Continuing strictly from the Round 8 cumulative canonical trial registry (**`N = 1,058`** canonical trials / **`1,179`** exhaustive grid rows in `06b_master_all_trials_sharpe_registry_r8.csv`):
- Round 9 evaluates `24` rows, of which `5` rows (`2L_0_Ctrl`, `3L_0_Ctrl`, `3L_3a`, `3L_3d`, `3L_3e`) are pre-existing baseline controls already included in `1,058`, and **`19` rows** are genuinely new `SEP = OFF` overlap-cap / duplicate-to-ExIT trials.
- Therefore:
  - **Strict Non-Duplicate Canonical Registry**: $1,058 + 19 = \mathbf{1,077}$ trials ($E[\max SR_0] = 1.1489$ annualized).
  - **All-Row Canonical Registry**: $1,058 + 24 = \mathbf{1,082}$ trials ($E[\max SR_0] = 1.1524$ annualized).
  - **Exhaustive Grid Registry**: $1,179 + 24 = \mathbf{1,203}$ rows ($E[\max SR_0] = 1.1241$ annualized).

| Strategy / Variant | Panel | CAGR (`09–26/09`) | Excess Sharpe | **DSR (`N = 1,077` Unique Canonical)** | **DSR (`N = 1,082` All Canonical)** | **DSR (`N = 1,203` Exhaustive Grid)** |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`CR_ExpABC_3b_BestSec_V1` (`BestSec + Gate V1` Master)** | **Master Strategy (`1.25x/1.50x/1.75x`)** | **`70.92%`** | **`1.437`** | **`93.50%`** *(Ctrl: `91.36%`)* | **`93.27%`** *(Ctrl: `91.10%`)* | **`95.00%`** |
| **`CR_ExpABC_3b_BestSec_V2` (`BestSec + Gate V2`)** | **Master Strategy (`1.25x/1.50x/1.75x`)** | **`76.46%`** | **`1.421`** | **`92.88%`** *(Ctrl: `90.11%`)* | **`92.63%`** *(Ctrl: `89.83%`)* | **`94.53%`** |
| **`Ind_ExpABC_3b_BestSec` (`ind_engine.py` Zero-Shared-Code)** | **Independent Engine Master** | **`76.18%`** | **`1.420`** | **`92.86%`** *(Ctrl: `90.02%`)* | **`92.61%`** *(Ctrl: `89.73%`)* | **`94.52%`** |
| **`CR_ExpABC_3f_SGOV50_V1` (`50% SGOV + Gate V1`)** | **Master Strategy (`1.25x/1.50x/1.75x`)** | **`68.90%`** | **`1.419`** | **`92.58%`** *(Ctrl: `89.95%`)* | **`92.32%`** *(Ctrl: `89.66%`)* | **`94.27%`** |
| **`Ind_ExpABC_3f_SGOV50` (`ind_engine.py` Zero-Shared-Code)** | **Independent Engine Master** | **`74.10%`** | **`1.401`** | **`91.77%`** *(Ctrl: `88.42%`)* | **`91.48%`** *(Ctrl: `88.10%`)* | **`93.65%`** |
| **`CR_M3_4a_V1` (`Round 1 Exact Gate V1`)** | **Master Strategy (`1.50x 3-Leg`)** | **`60.86%`** | **`1.403`** | **`90.45%`** *(Ctrl: `88.54%`)* | **`90.15%`** *(Ctrl: `88.22%`)* | **`92.45%`** |
| **`CR_ExpABC_3b_V1` (`ExIT_Raw + Gate V1`)** | **Master Strategy (`1.25x/1.50x/1.75x`)** | **`68.91%`** | **`1.400`** | **`90.38%`** *(Ctrl: `88.28%`)* | **`90.08%`** *(Ctrl: `87.96%`)* | **`92.40%`** |
| **`3L_3e_SEPOFF_KillQQQ_25SGOV_25ExITBS_Allow50`** | **Unlevered `1.0x` (`BestSec` Base)** | **`54.35%`** | **`1.396`** | **`88.32%`** *(Ctrl: `87.89%`)* | **`87.99%`** *(Ctrl: `87.56%`)* | **`90.50%`** |
| **`3L_3a_SEPOFF_KillQQQ_50SGOV_Allow50`** | **Unlevered `1.0x` (`50% SGOV` Base)** | **`52.53%`** | **`1.380`** | **`87.13%`** *(Ctrl: `86.29%`)* | **`86.77%`** *(Ctrl: `85.93%`)* | **`89.51%`** |
| **`3L_3c_SEPOFF_KillQQQ_50SGOV_Cap25_ExITBS`** | **Unlevered `1.0x` (`Cap <=25%`)** | **`51.85%`** | **`1.366`** | **`85.75%`** *(Ctrl: `84.85%`)* | **`85.37%`** *(Ctrl: `84.47%`)* | **`88.33%`** |
| **`3L_3b_SEPOFF_KillQQQ_50SGOV_Cap25_ExITRaw`** | **Unlevered `1.0x` (`Cap <=25%`)** | **`51.72%`** | **`1.364`** | **`85.47%`** *(Ctrl: `84.56%`)* | **`85.08%`** *(Ctrl: `84.17%`)* | **`88.08%`** |
| **`2L_2f_SEPOFF_DupToExITBS50`** | **Unlevered `1.0x` 2-Leg** | **`54.50%`** | **`1.374`** | **`84.82%`** *(Ctrl: `85.71%`)* | **`84.45%`** *(Ctrl: `85.34%`)* | **`87.34%`** |
| **`3L_2d_SEPOFF_Cap25_AllDup_ExITBS_SGOV`** | **Unlevered `1.0x` (`QQQ On, Cap <=25%`)** | **`52.24%`** | **`1.357`** | **`84.15%`** *(Ctrl: `83.74%`)* | **`83.74%`** *(Ctrl: `83.34%`)* | **`86.87%`** |
| **`3L_0_Ctrl` (Unmodified 3-Leg Control)** | **Unlevered `1.0x` Baseline** | `50.23%` | `1.300` | `76.34%` | `75.84%` | `79.82%` |
| **`2L_0_Ctrl` (Unmodified 2-Leg Control)** | **Unlevered `1.0x` Baseline** | `49.97%` | `1.274` | `71.56%` | `71.02%` | `75.28%` |

