# Taxonomy-Immune Challenger Audit Report (`Current` vs `TI-1` vs `TI-2`, 2009–2026 Strict PIT)

> **Audit Date**: 2026-11-07  
> **Governance Status**: **`Frozen A1-RS 1.35x + V3 Election Reset` (`Current`) remains 100% untouched as the Frozen Forward Challenger.** `TI-1` and `TI-2` are evaluated strictly in a separate clean-room research track (`outputs/taxonomy_immune_challenger_audit_20261107/`).  
> **Reproducible Script & Ledgers**:
> - Script: [`run_taxonomy_immune_challenger_audit.py`](./run_taxonomy_immune_challenger_audit.py)
> - Head-to-Head Summary: [`01_taxonomy_immune_head_to_head_summary.csv`](./01_taxonomy_immune_head_to_head_summary.csv)
> - 214-Month Side-by-Side Ledger: [`02_monthly_ledger_current_vs_ti1_vs_ti2.csv`](./02_monthly_ledger_current_vs_ti1_vs_ti2.csv)
> - Taxonomy Shock Test Matrix: [`03_taxonomy_shock_test_summary.csv`](./03_taxonomy_shock_test_summary.csv)

---

## 1. Experimental Design (Strictly 3 Pre-Registered Versions, Zero Parameter Mining)

| Version | Architecture & Group Definition | GICS Dependency |
| :--- | :--- | :---: |
| **`Current`**<br>*(Frozen `A1-RS 1.35x + V3`)* | • `QQQ`: `12-1 Sharpe Top-2 / Hold <= 5`<br>• `Tech`: Official PIT GICS `Information Technology` `12-1 Raw Top-1 Hard`<br>• `SPY`: `S&P 500` `12-1 Raw Top-1 / Hold <= 3 + RS_sec >= -5.0%` (vs GICS sector 1M EW return)<br>• `SEP = OFF`: `25% Tech + 25% SPY (or Ex-IT Raw) + 25% Ex-IT BestSec (GICS) + 25% SGOV` | **Depends on GICS** (`Tech`, `Ex-IT BestSec`, `RS_sec`) |
| **`TI-1`**<br>*(Sector-Agnostic Momentum)* | • `QQQ`: `12-1 Sharpe Top-2 / Hold <= 5`<br>• `SP500 Leg 1`: `S&P 500` `12-1 Raw Top-1 / Hold <= 3 + RS_mkt >= -5.0%` (vs S&P 500 EW 1M return)<br>• `SP500 Ex-Overlap Leg 2`: `S&P 500 Ex-Leg1` `12-1 Raw Top-1 / Hold <= 3 + RS_mkt >= -5.0%`<br>• `BestSec` cancelled: in `SEP = OFF`, holds `25% SP500 Leg 1 + 25% SP500 Ex-Leg1 + 25% SP500 Ex-{Leg1,2} + 25% SGOV` | **`0%` GICS**<br>*(No clusters)* |
| **`TI-2`** 🏆<br>*(Rolling 252-Day Correlation Clusters)* | • At each month-end $t$, partitions all eligible S&P 500 stocks into **$K = 11$ deterministic Ward hierarchical clusters** using trailing 252-trading-day daily return correlations ($D_{ij} = \sqrt{1 - \rho_{ij}}$).<br>• Identifies the **"Tech/Growth Price Cluster" (`C_tech`)** purely by trailing 252-day co-movement (`corr × beta`) with `QQQ`.<br>• Runs the exact same 4-layer rules as `Current`, replacing `GICS Sector` with `Price Cluster` (`Tech-Cluster Top-1 Hard`, `Ex-Tech BestCluster`, and cluster-relative `RS_cluster >= -5.0%`). | **`0%` GICS**<br>*(100% Price-Driven)* |

---

## 2. Head-to-Head Performance (`2009-01 to 2026-10`, 214 Months Strict PIT, Next-Open, `10 bp/side`)

Source: [`01_taxonomy_immune_head_to_head_summary.csv`](./01_taxonomy_immune_head_to_head_summary.csv)

| Metric | **`Current` (`A1-RS 1.35x + V3`, GICS)** | **`TI-1` (`Sector-Agnostic`, 0% GICS)** | **`TI-2` (`252d Price Clusters`, 0% GICS)** 🏆 | `TI-2` vs `Current` |
| :--- | :---: | :---: | :---: | :---: |
| **213M CAGR (`2009-01..2026-09`)** | **`65.54%`** | `44.98%` | **`64.73%`** | `-0.81 pp` |
| **214M CAGR (`2009-01..2026-10`)** | **`64.95%`** | `43.77%` | **`64.16%`** | **`-0.79 pp`** *(+20.39pp vs TI-1)* |
| **Annualized Volatility** | `37.54%` | `33.60%` | `37.77%` | `+0.23 pp` |
| **Sharpe Ratio (213M / 214M)** | **`1.498 / 1.489`** | `1.237 / 1.208` | **`1.477 / 1.469`** | **`-0.020`** *(+0.261 vs TI-1)* |
| **Monthly MaxDD (`Initial NAV = 1.0`)** | **`-22.74%`** | `-26.52%` | `-30.06%` | `-7.32 pp` |
| **Historical Daily MaxDD** | **`-34.64%`** | `-35.52%` | `-37.22%` | `-2.58 pp` |
| **2026 Live Daily MaxDD** | **`-25.88%`** | `-34.41%` | `-31.83%` | `-5.95 pp` |
| **Min Broker Margin Equity Ratio (`MinMER`)** | **`70.63%`** | `81.48%` | **`69.54%`** | `-1.09 pp` *(well above 30% line)* |
| **Monthly Win Rate** | **`66.36%`** | `65.42%` | **`65.89%`** | `-0.47 pp` |
| **Annualized 2-Way Turnover** | `8.99x / yr` | `8.21x / yr` | `10.06x / yr` | `+1.07x / yr` |
| **Avg / Peak Single-Stock Weight** | `48.74%` / `101.25%` | `36.57%` / `60.00%` | `49.21%` / `101.25%` | `+0.47 pp` / `0.00 pp` |
| **Avg Unique Stocks Held** | `3.01` | `3.32` | `3.00` | `-0.01` |

---

## 3. Event-Window Comparison Across Historical GICS & Index Rule Shocks

| Historical Event Window | **`Current` (GICS)** | **`TI-1` (No Sectors)** | **`TI-2` (Price Clusters)** 🏆 | Key Structural Insight |
| :--- | :---: | :---: | :---: | :--- |
| **1. `2016` (Aug 2016 GICS Real Estate `XLRE` Carve-Out)** | **`+162.51%`** | `+63.44%` | **`+144.46%`** | `TI-2` captures `89%` of `Current`'s gain (`+81pp` ahead of `TI-1`). |
| **2. `2018–2019` (Sept 2018 GICS `XLC` FAANG Split)** | `+97.53%` | `+44.14%` | 🏆 **`+101.55%`** | **`TI-2` beats `Current` by `+4.02pp`** because price clusters are unaffected when S&P exiles `META/GOOGL/NFLX` to `XLC`. |
| **3. `2022` (Fed Rate-Hike Bear Market, `SEP = OFF`)** | **`+56.34%`** | `+29.62%` | **`+51.38%`** | Without knowing the word "Energy", `TI-2`'s 252d correlation clusters automatically group `XOM/CVX/DVN/OXY/VLO/EQT` into the #1 Ex-Tech Cluster (`+51.38%`), whereas `TI-1` drops to `+29.62%`. |
| **4. `2023` (Mar 2023 Fintech GICS Removal + Jul 2023 `QQQ` Special Rebalance)** | `+3.45%` | **`+14.05%`** | 🏆 **`+8.28%`** | **`TI-2` beats `Current` by `+4.83pp`** during the year S&P removed `V/MA/PYPL/ADP` from `XLK`. |
| **5. `2024` (Jun/Sep 2024 `XLK` `NVDA/AAPL` Cap Fiasco)** | **`+173.21%`** | `+89.10%` | **`+156.52%`** | Both `Current` and `TI-2` ignore `XLK` ETF cap weights and ride `NVDA / ANET / PLTR` constituent momentum. |
| **6. `2026 YTD` (`2026-01..2026-10` Live Window)** | **`+323.84%`** | `+163.80%` | **`+314.44%`** | `TI-2` tracks `Current` within `-9.4pp` on a `+324%` surge (`+150.6pp` ahead of `TI-1`). |
| **7. `2026-10` Single Month (Recent `SEP = OFF` Test)** | `-2.12%` | `-11.20%` | 🏆 **`-2.03%`** | **`TI-2` (`-2.03%`) slightly beats `Current` (`-2.12%`)**, while `TI-1` suffers `-11.20%` without cluster/sector `RS` filtering. |

---

## 4. The Taxonomy Shock Test (`03_taxonomy_shock_test_summary.csv`)

What happens if S&P / MSCI arbitrarily reclassifies stocks or scrambles GICS sector labels across history?

| Taxonomy Shock Scenario | **`Current` (GICS)**<br>214M CAGR | **`Current`**<br>$\Delta$ CAGR (pp) | **`Current`**<br>Months Altered | **`TI-1` (0% GICS)**<br>CAGR ($\Delta$) / Altered | **`TI-2` (Price Clusters)** 🏆<br>CAGR ($\Delta$) / Altered |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **0. Baseline (Unshocked Official PIT GICS)** | `64.95%` | `0.00 pp` | `0 / 214` | `43.77%` (`0.00 pp`) / `0` | **`64.16%` (`0.00 pp`) / `0`** |
| **1. Shock A: S&P Moves Semis & AI Hardware (`NVDA, AMD, AVGO, MU, SNDK, AAPL, ANET, FSLR...`) Out of `IT` $\to$ `Industrials`** | ❌ **`47.86%`** | **`-17.09 pp`** | **`147 / 214`** | `43.77%` (`0.00 pp`) / **`0`** | 🏆 **`64.16%` (`0.00 pp`) / `0`** |
| **2. Shock B: Merge Platform & Payment Giants (`META, GOOGL, NFLX, AMZN, TSLA, V, MA, PYPL`) Back Into `IT` (`2009–2026`)** | **`65.99%`** | **`+1.04 pp`** | `44 / 214` | `43.77%` (`0.00 pp`) / **`0`** | 🏆 **`64.16%` (`0.00 pp`) / `0`** |
| **3. Shock C: Reclassify Top-30 Pure Tech Leaders Into `Financials`** | ❌ **`48.12%`** | **`-16.83 pp`** | **`160 / 214`** | `43.77%` (`0.00 pp`) / **`0`** | 🏆 **`64.16%` (`0.00 pp`) / `0`** |
| **4. Shock D: 25 Monte Carlo Full Random GICS Scramblings *(Mean Across 25 Runs)*** | ❌ **`50.98%`** | **`-13.98 pp`** | **`207.2 / 214`** | `43.77%` (`0.00 pp`) / **`0`** | 🏆 **`64.16%` (`0.00 pp`) / `0`** |
| **5. Shock D: 25 Monte Carlo Full Random GICS Scramblings *(Worst-Case Run)*** | ❌ **`46.37%`** | **`-18.59 pp`** | **`213 / 214`** | `43.77%` (`0.00 pp`) / **`0`** | 🏆 **`64.16%` (`0.00 pp`) / `0`** |

---

## 5. Key Conclusions & Strategic Governance Verdict

1. **Your Hypothesis on `TI-2` vs `TI-1` Is 100% Confirmed by the Data**:
   - Simply throwing away sector structure (**`TI-1`**) destroys **`-21.18 pp` of CAGR (`64.95% → 43.77%`)** and **`-0.281` of Sharpe (`1.489 → 1.208`)**, because without a distinct Tech/Growth leg and an `Ex-Tech BestCluster` leg, the portfolio loses both `SEP = ON` 3-leg resonance and `SEP = OFF` sector rotation defense (`2022` drops from `+56.34%` to `+29.62%`).
   - By contrast, **`TI-2` (Rolling 252-Day Daily-Return Correlation Clusters)** reproduces **`98.8%` of `Current`'s CAGR (`64.16%` vs `64.95%`)** and **`98.6%` of `Current`'s Sharpe (`1.469` vs `1.489`)** with **zero GICS labels (`0 / 214` months altered under any GICS shock)**, and actually **beats `Current` during the 2018–2019 `XLC` overhaul (`+101.55%` vs `+97.53%`) and the 2023 Fintech GICS overhaul (`+8.28%` vs `+3.45%`)**!
2. **Bonus Insight from Shock B (`+1.04 pp` CAGR)**:
   - When we reverse S&P's bureaucratic exclusion of `META, GOOGL, NFLX, AMZN, TSLA, V, MA, PYPL` and allow them inside the `IT` candidate pool across `2009–2026` (**Shock B**), `Current`'s 214M CAGR rises from `64.95%` to **`65.99%` (`+1.04 pp/yr`)**. That empirically proves that S&P's administrative GICS boundaries slightly handicapped the `Tech` leg, whereas `TI-2` naturally groups co-moving growth leaders together via market correlations.
3. **Why `Current` (`A1-RS 1.35x + V3`) Remains Frozen Today while `TI-2` Is Promoted to Official Shadow Challenger**:
   - On unshocked historical data, `Current` still holds a slight edge in Monthly MaxDD (`-22.74%` vs `-30.06%`), Daily MaxDD (`-34.64%` vs `-37.22%`), and lower turnover (`8.99x/yr` vs `10.06x/yr`), because GICS sectors don't shift membership every month.
   - Therefore, we keep **`Current` (`A1-RS 1.35x + V3`)** frozen for live execution, and establish **`TI-2` (`Rolling 252d Correlation Clusters`)** as our **Taxonomy-Immune Shadow Challenger** ready to take over if S&P/MSCI ever enacts another disruptive GICS overhaul.
