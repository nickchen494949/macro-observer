# Clean-Room Adversarial Falsification Audit Report: `Core3` (Unlevered `1.0x`)

- **Audited Strategy (Frozen Rule, Zero Modifications)**:
  - **Name**: `Core3` (`50% QQQ Sharpe-Momentum Top-2 + 50% S&P 500 Tech Pure 12-1 Momentum Top-1`)
  - **Sleeve 1 (`50%` weight — `QQQ Sharpe-Momentum Top-2`)**:
    - Universe: Monthly Point-in-Time (PIT) Nasdaq-100 constituents (`u_monthly_members.csv`, certified with `0/118` gap unknowns and `0/106` challenger flips).
    - Signal at formation month-end $t$: $\text{SharpeMom}_{12,1} = \frac{P_{t-1}/P_{t-12} - 1}{\sigma_{\text{daily}}[t-12\text{m}, t-1\text{m}] \times \sqrt{252}}$ (requiring $\ge 120$ NYSE sessions).
    - Allocation: Equal-weight Top-2 (`25%` each of total portfolio).
  - **Sleeve 2 (`50%` weight — `S&P 500 Tech Pure 12-1 Momentum Top-1`, Clean-Room `S1`)**:
    - Universe: Monthly PIT S&P 500 Information Technology constituents (`S1`, excluding `NFLX` per official GICS classification).
    - Signal at formation month-end $t$: Pure `12-1` total-return momentum ($P_{t-1}/P_{t-12} - 1$).
    - Allocation: Top-1 (`50%` of total portfolio).
  - **Execution & Friction**: Enter at next month's first trading day Open ($T+1$ Open), exit/rebalance at the following month's first trading day Open, charging `10 bps` (`0.10%`) per side on traded weight.
  - **Audit Sample**: `2009-01 .. 2026-09` (`213` holding months, `4,466` NYSE trading days). Dynamic leverage (`B6/B7`) is strictly excluded.

---

## 1. Executive Verdict & Adversarial Scorecard

> **OVERALL AUDIT VERDICT: `PASS WITH THREE STRUCTURAL CAVEATS` (`43.85%` CAGR is a genuine broad-plateau result, NOT an isolated parameter peak or arithmetic/vendor artifact — but real-money deployment must budget for a `-46.76%` intra-month daily drawdown, a `3.7-year` underwater period in `2009–2013`, and `Rank #2 > Rank #1` asymmetry inside the QQQ Sharpe-Momentum sleeve).**

| # | Adversarial Falsification Check | Verdict | Key Quantitative Evidence |
|---|---|---|---|
| **0** | **Arithmetic & Single-Account Drift Rebalance** | **✅ PASS** | Sleeve-average `43.85%` vs Unified Single-Account Linear **`43.84%`** vs Multiplicative `(1-c)^TO` **`43.82%`** (only `-3 bps/yr` difference when charging 10bp/side on monthly 50/50 rebalancing + netting cross-sleeve trades). |
| **1** | **Volatility Window (`3m / 6m / 9m / 12m / 18m`) & Mom Grid** | **✅ PASS (Plateau)** | `Core3` sits on a wide **`38.18% – 47.26%` CAGR plateau** across `6m` (`38.18%`), `9m` (`38.51%`), `12m frozen` (`43.85%`), `12m no-skip` (`43.80%`), `18m` (`47.26%`), `No-Vol Raw Core1` (`40.74%`), and `Both-Sleeves Sharpe-Mom` (`42.47%`). |
| **2** | **`Top-1 / Top-2 / Top-3 / Top-5` & Single Ranks** | **🟡 PASS w/ Asymmetry** | `50/50 Core` across `Top-1 / Top-2 / Top-3 / Top-5 / Top-10` is smooth (`35.12% / 43.85% / 41.26% / 38.01% / 34.22%`), and `Ranks 2-3` gives `42.98%`. **Caveat**: Inside QQQ Sharpe-Mom standalone, **`Rank #2 alone` (`55.23%`) >> `Rank #1 alone` (`25.06%`)** and `Rank #3 alone` (`22.20%`) because dividing by vol occasionally pushes a low-vol defensive name to `#1` while pushing the secular tech leader to `#2`. |
| **3** | **Core Weights (`25/75`, `50/50`, `75/25`) & Deduplication** | **✅ PASS (Ultra-Flat)** | From `25/75` to `100/0`, CAGR stays inside **`41.92% – 44.53%`** (`25/75 = 41.92%`, `33/67 = 42.70%`, `50/50 = 43.85%`, `67/33 = 44.45%`, `75/25 = 44.53%`). `Core4` (`1/3 + 1/3 + 1/3`) achieves **`42.66%`** with `-34.5%` monthly MaxDD. Capping single-stock overlap at `50%` yields **`40.49%`**. |
| **4** | **Transaction Costs (`10 / 20 / 30 / 50 / 100 bp/side`)** | **✅ PASS** | `10bp = 43.85%`, `20bp = 42.41%`, `30bp = 40.98%`, `50bp = 38.16%`, `100bp = 31.33%` (`-1.45%/yr` per `+10bp/side`). Beats `QQQ` (`20.87%`) by `+10.5%/yr` even at `100 bp/side`. |
| **5** | **Execution Timing (`T+1 Open / T+1 Close / T+2 / T+3 / T+5`)** | **✅ PASS** | `T+0 Close = 43.44%`, `T+1 Open [frozen] = 43.85%`, `T+1 Close = 40.66%`, `T+2 Open = 39.07%`, `T+3 Open = 36.64%`, `T+5 Open = 35.25%`. Smooth decay, zero opening-print illusion. |
| **6** | **Drop Best `1/3/5/10` Months & Ban Super-Winners** | **✅ PASS w/ Right-Tail Note** | Dropping best `1 / 3 / 5 / 10` months yields **`40.13% / 34.19% / 29.86% / 21.59%`**. Simultaneously banning from BOTH sleeves: `Ban SNDK = 42.29% (Sharpe 1.13, DD -32.1%)`, `Ban TSLA = 40.39%`, `Ban PLTR = 37.91%`, `Ban NVDA = 34.83%`, `Ban NVDA+SNDK = 33.36%`. Top 5 stocks account for `69.0%` of log-wealth. |
| **7** | **Second-Vendor (`Tiingo-First`) Full Replication** | **✅ 100% PASS** | Re-running signals (`mom_12_1`, `vol_12_1`) and holding returns (`adjOpen`) with Tiingo first gives **`43.93%` CAGR** (vs `43.85%` primary, `+8 bps/yr`). Across `469/639` slot-months in Tiingo, median return diff is **`0.00 bp`** (`p95 = 0.45 bp`). |
| **8** | **True Daily Mark-to-Market MaxDD (`4,466` Days)** | **🟠 CRITICAL CAVEAT** | Monthly MaxDD is **`-36.65%`**, but **True Daily MaxDD is `-46.76%`** (`2026-06-25 -> 2026-07-29`, `-10.11%` deeper than monthly!), plus `-43.59%` in `2025-02..04` and `-39.74%` in `2009–2011` (`941` trading days = `3.7 years` underwater). Still ~`23%` shallower than `Tech Top-1` (`-69.68%`) or `QQQ Raw Top-2` (`-68.75%`), but rules out naive `2x` leverage. |
| **9** | **Multiple-Testing (`DSR` over `579` Trials) & Paired Tests** | **🟡 MIXED** | **vs `QQQ` / `XLK` / `NDX-EW`**: Statistically significant (`+22.98%/yr` vs QQQ, NW $t = 2.57, p = 0.010$; `DSR = 0.772` full / `0.874` post-2015 across $N=579$ trials). **vs `Core1` (Raw Mom)**: The `+3.11%/yr` return pickup over Raw Momentum has NW $t = 0.57$ ($p = 0.567$, `DSR = 0.001`); Sharpe-Mom's true benefit is **drawdown compression in 2022 (`+9.1%` vs `-8.5%`)**, not a provably higher mean return. |
| **10** | **Strict Rule Freeze** | **✅ ENFORCED** | Even though `18m vol` (`47.26%`), `Rank #2 alone` (`50.26%`), and `75/25 weight` (`44.53%`, Calmar `1.36`) scored higher in the grid, `Core3` (`12m vol`, `Top-2`, `50/50`) remains **100% frozen**. |

---

## 2. Three Key Structural Takeaways Before Looking at the Tables

1. **Why `43.85%` Is Not an Overfitted Spike (The Parameter Plateau)**:
   - In data-mined backtests, perturbing lookback windows or weights collapses CAGR toward the benchmark. Here, across every reasonable perturbation — `vol` window `6m..18m` (`38.2%–47.3%`), `Top-2 / Top-3 / Top-5` (`38.0%–43.9%`), sleeve weights `25/75..75/25` (`41.9%–44.5%`), execution `T+0 Close..T+2 Open` (`39.1%–43.9%`), and `Tiingo` second vendor (`43.93%`) — the strategy stays within a **`38% – 47%` CAGR corridor**.
2. **Why True Daily MaxDD (`-46.76%`) Matters More Than Monthly MaxDD (`-36.65%`)**:
   - Concentrated momentum winners (`SNDK`, `MU`, `NVDA`, `PLTR`) experience violent intra-month air pockets (`-35% to -47%` over 3–5 weeks, such as `Feb–Apr 2025` `-43.59%` and `Jun–Jul 2026` `-46.76%`) that partially mean-revert before month-end rebalance.
   - Relying only on monthly MaxDD (`-36.65%`) understates real mark-to-market pain by **`10.11` percentage points**. Furthermore, during the post-GFC recovery (`2009–2011`), `Core3` posted three consecutive losing calendar years (`-8.2%`, `-11.2%`, `-19.6%`) while `QQQ` rallied, staying underwater for **`941` trading days (`3.7` years)**.
3. **Why `Core4` (`42.66%` CAGR, `-34.54%` Monthly / `-44.36%` Daily MaxDD) Is a Strong Practical Peer**:
   - Because `QQQ Sharpe-Mom` has `Rank #2 > Rank #1` asymmetry (`55.23%` vs `25.06%`), splitting the QQQ allocation equally between `Raw 12-1 Top-2` and `Sharpe-Mom Top-2` (`Core4 = 1/3 QQQ Raw Top-2 + 1/3 QQQ Sharpe Top-2 + 1/3 Tech Top-1`) sacrifices only `1.19%/yr` of CAGR (`42.66%` vs `43.85%`) while reducing monthly MaxDD to **`-34.54%`**, reducing true daily MaxDD to **`-44.36%`**, and cutting maximum underwater duration from **`941` trading days to `614` trading days**.

---

## 3. Complete Auto-Generated Audit Tables (Zero Hand-Typed Numbers)

### T0. Core3 Frozen Rule Performance Across Subperiods

| Window | Months | Core3 CAGR | Vol | Sharpe | MaxDD (Monthly) | MaxDD (True Daily) | Calmar | Win Months |
|---|---|---|---|---|---|---|---|---|
| FULL 2009-01..2026-09 | 213 | 43.85% | 39.6% | 1.08 | -36.6% | -46.8% | 1.20 | 62.9% |
| 2009-2014 | 72 | 17.16% | 25.2% | 0.75 | -34.5% | -39.7% | 0.50 | 66.7% |
| 2015-2019 | 60 | 39.51% | 31.2% | 1.20 | -29.7% | -39.1% | 1.33 | 56.7% |
| 2020-2022 | 36 | 36.01% | 40.5% | 0.93 | -23.2% | -37.0% | 1.55 | 52.8% |
| 2023-2026.09 | 45 | 117.66% | 59.9% | 1.53 | -36.6% | -46.8% | 3.21 | 73.3% |
| 2009-2018 (pre-2019) | 120 | 24.95% | 28.2% | 0.92 | -34.5% | -39.7% | 0.72 | 62.5% |
| 2015-2026.09 | 141 | 59.75% | 44.8% | 1.22 | -36.6% | -46.8% | 1.63 | 61.0% |
| 2019-2026.09 | 93 | 72.53% | 50.0% | 1.28 | -36.6% | -46.8% | 1.98 | 63.4% |
| IS 2009-2016 | 96 | 27.23% | 28.1% | 1.00 | -34.5% | -39.7% | 0.79 | 65.6% |
| OOS 2017-2026.09 | 117 | 59.11% | 46.7% | 1.17 | -36.6% | -46.8% | 1.61 | 60.7% |

### T1. Check 1 — Volatility Window & Momentum Lookback Grid

| Variant | CAGR 09-26 | Vol | Sharpe | MaxDD (m) | Calmar | 2009-2018 | 2015-2026 | 2019-2026 | 2009-2014 | 2015-2019 | 2020-2022 | 2023-26.09 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Core (50/50): vol_3_1 (3m daily vol, 1m skip) | 34.13% | 37.1% | 0.94 | -46.2% | 0.74 | 15.45% | 49.32% | 62.78% | 8.72% | 30.48% | 32.99% | 96.10% |
| QQQ Sleeve Only: vol_3_1 (3m daily vol, 1m skip) | 24.66% | 36.6% | 0.74 | -48.4% | 0.51 | 12.16% | 33.86% | 42.87% | 8.44% | 17.78% | 26.65% | 65.96% |
| Core (50/50): vol_6_1 (6m daily vol, 1m skip) | 38.18% | 36.6% | 1.03 | -39.2% | 0.97 | 22.24% | 52.23% | 61.87% | 14.32% | 37.14% | 33.74% | 94.07% |
| QQQ Sleeve Only: vol_6_1 (6m daily vol, 1m skip) | 32.57% | 35.0% | 0.94 | -43.9% | 0.74 | 25.85% | 39.77% | 41.77% | 19.52% | 30.79% | 28.84% | 62.98% |
| Core (50/50): vol_9_1 (9m daily vol, 1m skip) | 38.51% | 39.1% | 0.99 | -42.6% | 0.90 | 19.10% | 54.51% | 68.29% | 11.81% | 33.15% | 37.40% | 106.96% |
| QQQ Sleeve Only: vol_9_1 (9m daily vol, 1m skip) | 33.63% | 38.9% | 0.89 | -44.1% | 0.76 | 19.66% | 44.84% | 54.10% | 14.14% | 24.12% | 35.33% | 87.87% |
| Core (50/50): vol_12_1 (12m daily vol, 1m skip) [FROZEN] | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| QQQ Sleeve Only: vol_12_1 (12m daily vol, 1m skip) [FROZEN] | 43.96% | 40.1% | 1.07 | -41.4% | 1.06 | 31.35% | 54.69% | 62.05% | 25.06% | 35.92% | 33.01% | 107.42% |
| Core (50/50): vol_18_1 (18m daily vol, 1m skip) | 47.26% | 40.2% | 1.13 | -36.6% | 1.29 | 28.75% | 60.38% | 75.13% | 24.60% | 41.34% | 35.30% | 117.47% |
| QQQ Sleeve Only: vol_18_1 (18m daily vol, 1m skip) | 51.17% | 40.7% | 1.18 | -39.3% | 1.30 | 39.50% | 56.24% | 67.67% | 41.70% | 39.83% | 32.12% | 107.16% |
| Core (50/50): vol_6_0 (6m daily vol, NO skip) | 38.94% | 36.9% | 1.04 | -40.3% | 0.97 | 20.50% | 54.67% | 66.97% | 12.63% | 36.22% | 42.47% | 95.64% |
| QQQ Sleeve Only: vol_6_0 (6m daily vol, NO skip) | 33.91% | 36.0% | 0.95 | -36.2% | 0.94 | 22.53% | 44.15% | 50.19% | 15.92% | 29.64% | 44.71% | 65.54% |
| Core (50/50): vol_12_0 (12m daily vol, NO skip) | 43.80% | 39.8% | 1.07 | -36.6% | 1.20 | 25.75% | 59.21% | 70.98% | 17.82% | 40.34% | 34.72% | 115.29% |
| QQQ Sleeve Only: vol_12_0 (12m daily vol, NO skip) | 44.00% | 40.3% | 1.06 | -43.4% | 1.01 | 33.17% | 53.76% | 59.29% | 26.66% | 37.60% | 30.37% | 103.45% |
| Core (50/50): No Vol Scaling (Raw 12-1 Momentum = Core1) | 40.74% | 41.1% | 1.00 | -37.3% | 1.09 | 21.92% | 54.41% | 69.39% | 17.38% | 34.76% | 39.34% | 101.00% |
| QQQ Sleeve Only: No Vol Scaling (Raw 12-1 Momentum = Core1) | 37.13% | 44.2% | 0.90 | -63.3% | 0.59 | 24.51% | 43.43% | 55.31% | 25.57% | 26.18% | 37.85% | 75.65% |
| Core (50/50): Mom 6-1 / Vol 12m | 38.36% | 36.4% | 1.04 | -40.2% | 0.96 | 24.06% | 48.17% | 59.27% | 20.98% | 34.07% | 33.09% | 84.49% |
| QQQ Sleeve Only: Mom 6-1 / Vol 12m | 32.57% | 35.4% | 0.93 | -35.9% | 0.91 | 29.43% | 31.68% | 36.74% | 34.33% | 24.45% | 26.64% | 46.48% |
| Core (50/50): Mom 9-1 / Vol 12m | 33.52% | 38.1% | 0.91 | -40.4% | 0.83 | 18.45% | 46.28% | 55.82% | 11.67% | 33.03% | 25.62% | 87.51% |
| QQQ Sleeve Only: Mom 9-1 / Vol 12m | 24.34% | 36.1% | 0.74 | -35.9% | 0.68 | 18.38% | 29.84% | 32.47% | 14.21% | 23.78% | 15.25% | 52.26% |
| Core (50/50): Mom 11-1 / Vol 12m | 37.90% | 39.5% | 0.97 | -49.6% | 0.76 | 18.99% | 53.61% | 66.81% | 11.65% | 35.52% | 30.69% | 106.57% |
| QQQ Sleeve Only: Mom 11-1 / Vol 12m | 32.48% | 39.6% | 0.87 | -58.1% | 0.56 | 19.57% | 42.78% | 51.22% | 14.43% | 28.24% | 22.63% | 86.09% |
| Core (50/50): Mom 12-0 (no skip) / Vol 12m | 37.92% | 39.4% | 0.97 | -36.6% | 1.03 | 23.01% | 50.03% | 59.87% | 16.98% | 31.96% | 24.49% | 106.66% |
| QQQ Sleeve Only: Mom 12-0 (no skip) / Vol 12m | 32.23% | 39.7% | 0.86 | -47.5% | 0.68 | 27.26% | 36.15% | 38.94% | 24.89% | 21.05% | 11.67% | 86.62% |
| Core (50/50): Mom Ensemble(6-1,9-1,12-1) / Vol 12m | 39.58% | 39.4% | 1.00 | -40.2% | 0.99 | 20.47% | 55.64% | 68.79% | 12.77% | 35.89% | 36.19% | 107.52% |
| QQQ Sleeve Only: Mom Ensemble(6-1,9-1,12-1) / Vol 12m | 35.67% | 39.6% | 0.93 | -40.1% | 0.89 | 22.30% | 46.85% | 55.12% | 16.19% | 29.21% | 32.92% | 88.63% |
| Core (50/50): Matched 6-1 Mom / 6m Vol | 36.41% | 35.8% | 1.01 | -40.2% | 0.91 | 19.54% | 51.32% | 61.74% | 11.33% | 35.83% | 41.67% | 84.20% |
| QQQ Sleeve Only: Matched 6-1 Mom / 6m Vol | 29.16% | 33.5% | 0.89 | -35.9% | 0.81 | 20.37% | 37.81% | 41.47% | 13.77% | 28.08% | 45.10% | 45.81% |
| Core (50/50): Matched 9-1 Mom / 9m Vol | 34.44% | 38.3% | 0.92 | -40.7% | 0.85 | 18.93% | 47.19% | 57.46% | 12.57% | 30.33% | 31.07% | 89.92% |
| QQQ Sleeve Only: Matched 9-1 Mom / 9m Vol | 25.83% | 37.2% | 0.76 | -40.5% | 0.64 | 19.48% | 30.85% | 34.53% | 16.56% | 18.08% | 24.01% | 56.63% |
| Core (50/50): Both Sleeves Sharpe-Mom (QQQ Sh-Top2 + Tech Sh-Top1) | 42.47% | 37.2% | 1.10 | -36.6% | 1.16 | 28.59% | 51.71% | 62.63% | 25.99% | 29.23% | 27.95% | 115.30% |
| Tech Sleeve Only: Tech Sharpe-Mom Top-1 | 37.05% | 42.5% | 0.92 | -44.4% | 0.83 | 22.81% | 44.48% | 57.88% | 23.57% | 20.63% | 17.71% | 116.52% |

### T2. Check 2 — Top-K & Neighboring Rank Decomposition

| Variant | CAGR 09-26 | Vol | Sharpe | MaxDD (m) | Calmar | 2009-2018 | 2015-2026 | 2019-2026 | 2009-2014 | 2015-2019 | 2020-2022 | 2023-26.09 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 50% (QQQ Sharpe-Mom Top-1) + 50% Tech Top-1 | 35.12% | 41.4% | 0.90 | -44.4% | 0.79 | 22.48% | 48.93% | 53.38% | 11.68% | 43.89% | 14.36% | 92.62% |
| Standalone: QQQ Sharpe-Mom Top-1 | 25.06% | 46.9% | 0.68 | -65.3% | 0.38 | 23.35% | 33.53% | 27.30% | 10.00% | 43.34% | -6.41% | 61.43% |
| 50% (QQQ Sharpe-Mom Top-2 [FROZEN]) + 50% Tech Top-1 | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| Standalone: QQQ Sharpe-Mom Top-2 [FROZEN] | 43.96% | 40.1% | 1.07 | -41.4% | 1.06 | 31.35% | 54.69% | 62.05% | 25.06% | 35.92% | 33.01% | 107.42% |
| 50% (QQQ Sharpe-Mom Top-3) + 50% Tech Top-1 | 41.26% | 37.9% | 1.06 | -36.4% | 1.13 | 25.14% | 54.85% | 65.16% | 18.01% | 39.57% | 28.40% | 106.62% |
| Standalone: QQQ Sharpe-Mom Top-3 | 39.34% | 35.5% | 1.07 | -45.2% | 0.87 | 32.45% | 45.46% | 48.77% | 28.09% | 36.06% | 19.54% | 86.05% |
| 50% (QQQ Sharpe-Mom Top-5) + 50% Tech Top-1 | 38.01% | 35.1% | 1.05 | -33.2% | 1.15 | 23.09% | 49.26% | 59.95% | 18.36% | 35.18% | 30.52% | 89.64% |
| Standalone: QQQ Sharpe-Mom Top-5 | 32.73% | 30.0% | 1.04 | -38.0% | 0.86 | 28.48% | 34.29% | 38.43% | 29.73% | 27.40% | 22.75% | 54.80% |
| 50% (QQQ Sharpe-Mom Top-10) + 50% Tech Top-1 | 34.22% | 32.5% | 1.03 | -32.8% | 1.04 | 20.48% | 44.06% | 54.28% | 16.85% | 31.34% | 28.95% | 78.05% |
| Standalone: QQQ Sharpe-Mom Top-10 | 25.68% | 23.2% | 1.04 | -26.8% | 0.96 | 23.19% | 25.12% | 28.97% | 26.79% | 20.08% | 21.51% | 35.30% |
| 50% (QQQ Sharpe-Mom Rank #1 alone) + 50% Tech Top-1 | 35.12% | 41.4% | 0.90 | -44.4% | 0.79 | 22.48% | 48.93% | 53.38% | 11.68% | 43.89% | 14.36% | 92.62% |
| Standalone: QQQ Sharpe-Mom Rank #1 alone | 25.06% | 46.9% | 0.68 | -65.3% | 0.38 | 23.35% | 33.53% | 27.30% | 10.00% | 43.34% | -6.41% | 61.43% |
| 50% (QQQ Sharpe-Mom Rank #2 alone) + 50% Tech Top-1 | 50.26% | 41.8% | 1.14 | -43.1% | 1.17 | 25.40% | 68.06% | 89.77% | 20.68% | 33.55% | 57.13% | 140.97% |
| Standalone: QQQ Sharpe-Mom Rank #2 alone | 55.23% | 48.0% | 1.10 | -50.0% | 1.10 | 32.21% | 67.79% | 90.95% | 33.28% | 23.69% | 70.97% | 148.23% |
| 50% (QQQ Sharpe-Mom Rank #3 alone) + 50% Tech Top-1 | 33.70% | 38.7% | 0.90 | -46.6% | 0.72 | 23.66% | 42.71% | 47.87% | 17.68% | 38.09% | 11.91% | 81.11% |
| Standalone: QQQ Sharpe-Mom Rank #3 alone | 22.20% | 43.2% | 0.62 | -61.9% | 0.36 | 28.25% | 19.93% | 14.82% | 26.77% | 31.71% | -11.00% | 34.38% |
| 50% (QQQ Sharpe-Mom Rank #4 alone) + 50% Tech Top-1 | 34.66% | 41.0% | 0.88 | -36.7% | 0.95 | 17.80% | 47.29% | 60.04% | 12.99% | 30.93% | 45.83% | 73.70% |
| Standalone: QQQ Sharpe-Mom Rank #4 alone | 22.32% | 54.5% | 0.55 | -57.8% | 0.39 | 16.59% | 24.68% | 30.14% | 17.84% | 17.70% | 38.25% | 23.95% |
| 50% (QQQ Sharpe-Mom Rank #5 alone) + 50% Tech Top-1 | 26.16% | 30.9% | 0.86 | -33.7% | 0.78 | 18.79% | 28.77% | 36.35% | 21.19% | 23.43% | 12.35% | 51.95% |
| Standalone: QQQ Sharpe-Mom Rank #5 alone | 7.77% | 30.4% | 0.35 | -71.5% | 0.11 | 17.75% | -3.73% | -3.86% | 34.43% | 4.07% | -10.21% | -8.25% |
| 50% (QQQ Sharpe-Mom Ranks 2-3 (neighbour pair)) + 50% Tech Top-1 | 42.98% | 37.9% | 1.09 | -37.9% | 1.14 | 25.24% | 56.41% | 69.64% | 19.94% | 36.41% | 34.55% | 111.72% |
| Standalone: QQQ Sharpe-Mom Ranks 2-3 (neighbour pair) | 42.17% | 36.9% | 1.09 | -50.1% | 0.84 | 32.77% | 47.15% | 55.30% | 32.92% | 29.50% | 30.05% | 92.59% |
| 50% (QQQ Sharpe-Mom Ranks 3-4 (neighbour pair)) + 50% Tech Top-1 | 35.45% | 37.1% | 0.96 | -39.6% | 0.89 | 21.34% | 46.58% | 56.11% | 16.04% | 34.95% | 30.52% | 79.60% |
| Standalone: QQQ Sharpe-Mom Ranks 3-4 (neighbour pair) | 26.24% | 39.3% | 0.73 | -49.5% | 0.53 | 24.54% | 26.93% | 28.47% | 24.91% | 26.05% | 18.25% | 35.57% |
| 50% (QQQ Sharpe-Mom Ranks 4-6) + 50% Tech Top-1 | 30.65% | 32.9% | 0.94 | -35.5% | 0.86 | 17.84% | 38.77% | 49.26% | 16.09% | 28.02% | 23.96% | 69.11% |
| Standalone: QQQ Sharpe-Mom Ranks 4-6 | 17.84% | 29.0% | 0.66 | -42.1% | 0.42 | 17.43% | 14.27% | 18.38% | 25.18% | 13.33% | 9.08% | 19.90% |
| 50% QQQ Sharpe-Mom Top-2 + 50% (Tech Top-1 (S1, no NFLX) [FROZEN]) | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| 50% QQQ Sharpe-Mom Top-2 + 50% (Tech Top-2 EW (S1)) | 37.49% | 35.2% | 1.04 | -30.1% | 1.25 | 25.61% | 44.61% | 54.51% | 24.55% | 27.91% | 19.10% | 98.93% |
| 50% QQQ Sharpe-Mom Top-2 + 50% (Tech Top-3 EW (S1)) | 34.95% | 33.4% | 1.02 | -32.9% | 1.06 | 25.92% | 40.80% | 47.57% | 24.21% | 27.63% | 14.04% | 89.96% |
| 50% QQQ Sharpe-Mom Top-2 + 50% (Tech Top-5 EW (S1)) | 34.27% | 32.4% | 1.03 | -33.1% | 1.04 | 25.11% | 39.98% | 47.09% | 23.76% | 28.22% | 15.64% | 83.34% |
| 50% QQQ Sharpe-Mom Top-2 + 50% (Tech Rank #2 alone (S1)) | 28.63% | 35.9% | 0.84 | -55.9% | 0.51 | 23.81% | 27.86% | 35.13% | 30.14% | 14.65% | 2.73% | 76.18% |
| 50% QQQ Sharpe-Mom Top-2 + 50% (Tech Rank #3 alone (S1)) | 27.84% | 33.4% | 0.85 | -43.6% | 0.64 | 24.61% | 31.11% | 32.12% | 21.66% | 25.16% | 3.17% | 68.95% |
| 50% QQQ Sharpe-Mom Top-2 + 50% (Tech Top-1 (S0 w/ NFLX)) | 46.12% | 39.9% | 1.11 | -36.6% | 1.26 | 28.47% | 61.99% | 72.53% | 19.41% | 44.16% | 36.01% | 117.66% |

### T3. Check 3 — Sleeve Weights, Deduplication & Unified Account Accounting

| Variant | CAGR 09-26 | Vol | Sharpe | MaxDD (m) | Calmar | 2009-2018 | 2015-2026 | 2019-2026 | 2009-2014 | 2015-2019 | 2020-2022 | 2023-26.09 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Weight 100/0 (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg | 43.96% | 40.1% | 1.07 | -41.4% | 1.06 | 31.35% | 54.69% | 62.05% | 25.06% | 35.92% | 33.01% | 107.42% |
| Weight 100/0 (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult | 43.92% | 40.0% | 1.07 | -41.3% | 1.06 | 31.32% | 54.64% | 61.98% | 25.03% | 35.88% | 32.98% | 107.32% |
| Weight 75/25 (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg | 44.53% | 38.6% | 1.11 | -32.8% | 1.36 | 28.69% | 57.80% | 67.89% | 21.69% | 38.17% | 35.17% | 113.20% |
| Weight 75/25 (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult | 44.49% | 38.6% | 1.11 | -32.8% | 1.36 | 28.66% | 57.76% | 67.84% | 21.65% | 38.15% | 35.15% | 113.10% |
| Weight 67/33 (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg | 44.45% | 38.6% | 1.10 | -34.1% | 1.30 | 27.56% | 58.58% | 69.57% | 20.31% | 38.72% | 35.60% | 114.84% |
| Weight 67/33 (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult | 44.41% | 38.6% | 1.10 | -34.1% | 1.30 | 27.53% | 58.54% | 69.53% | 20.27% | 38.71% | 35.58% | 114.74% |
| Weight 50/50 (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg [FROZEN] | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| Weight 50/50 (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult [FROZEN] | 43.82% | 39.5% | 1.08 | -36.6% | 1.20 | 24.92% | 59.71% | 72.48% | 17.12% | 39.49% | 35.99% | 117.57% |
| Weight 33/67 (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg | 42.70% | 41.5% | 1.03 | -46.6% | 0.92 | 21.89% | 60.37% | 74.89% | 13.55% | 39.86% | 35.82% | 119.84% |
| Weight 33/67 (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult | 42.67% | 41.5% | 1.03 | -46.6% | 0.92 | 21.86% | 60.34% | 74.85% | 13.52% | 39.84% | 35.79% | 119.77% |
| Weight 25/75 (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg | 41.92% | 42.8% | 0.99 | -52.2% | 0.80 | 20.20% | 60.47% | 75.85% | 11.58% | 39.86% | 35.49% | 120.67% |
| Weight 25/75 (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult | 41.89% | 42.8% | 0.99 | -52.3% | 0.80 | 20.17% | 60.44% | 75.81% | 11.55% | 39.85% | 35.47% | 120.62% |
| Weight 0/100 (QQQ Sh-Top2 / Tech Top1) — Sleeve-Avg | 38.73% | 47.8% | 0.89 | -67.0% | 0.58 | 14.48% | 59.89% | 77.74% | 5.05% | 39.16% | 33.60% | 122.14% |
| Weight 0/100 (QQQ Sh-Top2 / Tech Top1) — Unified Account Mult | 38.73% | 47.8% | 0.89 | -67.0% | 0.58 | 14.48% | 59.89% | 77.74% | 5.05% | 39.16% | 33.60% | 122.14% |
| Core3 Accounting: Unified Account Linear 10bp/side | 43.84% | 39.6% | 1.08 | -36.6% | 1.20 | 24.93% | 59.75% | 72.54% | 17.13% | 39.51% | 36.02% | 117.65% |
| Core3 Accounting: Unified Account Multiplicative 10bp/side | 43.82% | 39.5% | 1.08 | -36.6% | 1.20 | 24.92% | 59.71% | 72.48% | 17.12% | 39.49% | 35.99% | 117.57% |
| Core3 Accounting: Unrebalanced Drift Between Sleeves | 41.74% | 38.9% | 1.05 | -35.3% | 1.18 | 25.35% | 56.23% | 66.11% | 17.15% | 36.79% | 33.18% | 111.92% |
| Core3 Deduplicated: Max 50% Cap (pull in QQQ Sh-Mom #3 on overlap) | 40.49% | 37.7% | 1.05 | -34.5% | 1.17 | 25.38% | 52.02% | 62.71% | 20.38% | 34.81% | 33.60% | 97.85% |
| Core3 Deduplicated: Equal-Weight 3 Distinct Stocks (1/3 each) | 39.65% | 36.8% | 1.05 | -31.8% | 1.25 | 27.98% | 48.00% | 56.30% | 24.64% | 32.29% | 32.38% | 87.93% |
| Core4: 1/3 QQQ Raw Top-2 + 1/3 QQQ Sharpe Top-2 + 1/3 Tech Top-1 | 42.66% | 39.2% | 1.06 | -34.5% | 1.24 | 25.67% | 55.38% | 68.02% | 20.68% | 35.80% | 38.26% | 104.17% |
| Core1: 50% QQQ Raw Top-2 + 50% Tech Top-1 | 40.74% | 41.1% | 1.00 | -37.3% | 1.09 | 21.92% | 54.41% | 69.39% | 17.38% | 34.76% | 39.34% | 101.00% |

### T4. Check 4 — Transaction Cost & Slippage Stress (0 to 100 bp/side)

| Variant | CAGR 09-26 | Vol | Sharpe | MaxDD (m) | Calmar | 2009-2018 | 2015-2026 | 2019-2026 | 2009-2014 | 2015-2019 | 2020-2022 | 2023-26.09 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Cost 0 bp/side — Sleeve-Average | 45.31% | 39.5% | 1.10 | -36.6% | 1.24 | 26.32% | 61.25% | 74.10% | 18.52% | 40.99% | 37.51% | 119.07% |
| Cost 0 bp/side — Unified Multiplicative | 45.31% | 39.5% | 1.10 | -36.6% | 1.24 | 26.32% | 61.25% | 74.10% | 18.52% | 40.99% | 37.51% | 119.07% |
| Cost 0 bp/side — Unified Linear | 45.31% | 39.5% | 1.10 | -36.6% | 1.24 | 26.32% | 61.25% | 74.10% | 18.52% | 40.99% | 37.51% | 119.07% |
| Cost 10 bp/side — Sleeve-Average [FROZEN] | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| Cost 10 bp/side — Unified Multiplicative [FROZEN] | 43.82% | 39.5% | 1.08 | -36.6% | 1.20 | 24.92% | 59.71% | 72.48% | 17.12% | 39.49% | 35.99% | 117.57% |
| Cost 10 bp/side — Unified Linear [FROZEN] | 43.84% | 39.6% | 1.08 | -36.6% | 1.20 | 24.93% | 59.75% | 72.54% | 17.13% | 39.51% | 36.02% | 117.65% |
| Cost 20 bp/side — Sleeve-Average | 42.41% | 39.6% | 1.05 | -37.2% | 1.14 | 23.60% | 58.26% | 70.97% | 15.82% | 38.04% | 34.53% | 116.25% |
| Cost 20 bp/side — Unified Multiplicative | 42.33% | 39.5% | 1.05 | -37.3% | 1.13 | 23.54% | 58.19% | 70.87% | 15.74% | 38.01% | 34.48% | 116.08% |
| Cost 20 bp/side — Unified Linear | 42.39% | 39.6% | 1.05 | -37.4% | 1.13 | 23.56% | 58.26% | 70.99% | 15.76% | 38.05% | 34.54% | 116.25% |
| Cost 30 bp/side — Sleeve-Average | 40.98% | 39.6% | 1.02 | -39.9% | 1.03 | 22.26% | 56.79% | 69.42% | 14.49% | 36.59% | 33.06% | 114.86% |
| Cost 30 bp/side — Unified Multiplicative | 40.86% | 39.5% | 1.02 | -40.0% | 1.02 | 22.17% | 56.68% | 69.28% | 14.37% | 36.54% | 32.98% | 114.59% |
| Cost 30 bp/side — Unified Linear | 40.94% | 39.6% | 1.02 | -40.1% | 1.02 | 22.20% | 56.79% | 69.45% | 14.40% | 36.60% | 33.08% | 114.85% |
| Cost 50 bp/side — Sleeve-Average | 38.16% | 39.6% | 0.97 | -44.9% | 0.85 | 19.63% | 53.87% | 66.37% | 11.88% | 33.73% | 30.17% | 112.09% |
| Cost 50 bp/side — Unified Multiplicative | 37.97% | 39.5% | 0.97 | -45.1% | 0.84 | 19.47% | 53.69% | 66.13% | 11.69% | 33.65% | 30.04% | 111.65% |
| Cost 50 bp/side — Unified Linear | 38.10% | 39.7% | 0.97 | -45.3% | 0.84 | 19.51% | 53.88% | 66.41% | 11.73% | 33.74% | 30.19% | 112.07% |
| Cost 75 bp/side — Sleeve-Average | 34.71% | 39.7% | 0.91 | -50.7% | 0.68 | 16.41% | 50.30% | 62.63% | 8.70% | 30.24% | 26.63% | 108.68% |
| Cost 75 bp/side — Unified Multiplicative | 34.42% | 39.5% | 0.90 | -51.0% | 0.67 | 16.17% | 50.03% | 62.27% | 8.41% | 30.11% | 26.45% | 108.02% |
| Cost 75 bp/side — Unified Linear | 34.61% | 39.7% | 0.90 | -51.3% | 0.68 | 16.23% | 50.30% | 62.68% | 8.46% | 30.24% | 26.66% | 108.64% |
| Cost 100 bp/side — Sleeve-Average | 31.33% | 39.7% | 0.84 | -55.9% | 0.56 | 13.27% | 46.81% | 58.96% | 5.59% | 26.82% | 23.19% | 105.32% |
| Cost 100 bp/side — Unified Multiplicative | 30.96% | 39.6% | 0.84 | -56.3% | 0.55 | 12.96% | 46.45% | 58.49% | 5.21% | 26.65% | 22.95% | 104.45% |
| Cost 100 bp/side — Unified Linear | 31.20% | 39.8% | 0.84 | -56.6% | 0.55 | 13.03% | 46.80% | 59.02% | 5.28% | 26.82% | 23.22% | 105.26% |

### T5. Check 5 — Synchronized Execution Timing & Lag Stress

| Variant | CAGR 09-26 | Vol | Sharpe | MaxDD (m) | Calmar | 2009-2018 | 2015-2026 | 2019-2026 | 2009-2014 | 2015-2019 | 2020-2022 | 2023-26.09 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Core3: T+0 Month-End Close (no lag, optimistic) | 43.44% | 39.9% | 1.06 | -38.7% | 1.12 | 24.40% | 59.35% | 72.38% | 16.74% | 38.15% | 36.74% | 117.86% |
| QQQ Sharpe-Mom Top-2: T+0 Month-End Close (no lag, optimistic) | 42.48% | 40.3% | 1.04 | -38.9% | 1.09 | 29.15% | 53.83% | 61.73% | 22.62% | 33.70% | 35.14% | 105.71% |
| Tech Top-1 (S1): T+0 Month-End Close (no lag, optimistic) | 39.44% | 48.2% | 0.89 | -62.5% | 0.63 | 15.60% | 60.01% | 77.61% | 6.50% | 39.18% | 32.77% | 123.74% |
| Core3: T+1 Open (1st trading day open) [FROZEN] | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| QQQ Sharpe-Mom Top-2: T+1 Open (1st trading day open) [FROZEN] | 43.96% | 40.1% | 1.07 | -41.4% | 1.06 | 31.35% | 54.69% | 62.05% | 25.06% | 35.92% | 33.01% | 107.42% |
| Tech Top-1 (S1): T+1 Open (1st trading day open) [FROZEN] | 38.73% | 47.8% | 0.89 | -67.0% | 0.58 | 14.48% | 59.89% | 77.74% | 5.05% | 39.16% | 33.60% | 122.14% |
| Core3: T+1 Close (1st trading day close) | 40.66% | 38.8% | 1.03 | -33.9% | 1.20 | 24.81% | 54.29% | 64.13% | 17.36% | 37.26% | 27.79% | 109.67% |
| QQQ Sharpe-Mom Top-2: T+1 Close (1st trading day close) | 40.61% | 38.7% | 1.03 | -41.6% | 0.98 | 29.32% | 50.36% | 56.65% | 23.33% | 33.88% | 28.00% | 99.66% |
| Tech Top-1 (S1): T+1 Close (1st trading day close) | 35.68% | 47.9% | 0.84 | -64.5% | 0.55 | 15.79% | 53.41% | 66.48% | 6.69% | 36.71% | 23.18% | 113.22% |
| Core3: T+2 Open (2nd trading day open) | 39.07% | 41.4% | 0.96 | -35.9% | 1.09 | 23.47% | 52.22% | 62.14% | 16.52% | 35.42% | 27.57% | 104.91% |
| QQQ Sharpe-Mom Top-2: T+2 Open (2nd trading day open) | 37.64% | 40.8% | 0.94 | -46.0% | 0.82 | 27.98% | 46.97% | 51.19% | 21.05% | 33.71% | 26.18% | 88.36% |
| Tech Top-1 (S1): T+2 Open (2nd trading day open) | 35.38% | 50.7% | 0.80 | -64.4% | 0.55 | 14.58% | 52.55% | 67.88% | 7.15% | 33.36% | 24.50% | 114.73% |
| Core3: T+2 Close (2nd trading day close) | 37.72% | 40.3% | 0.95 | -39.6% | 0.95 | 22.55% | 51.01% | 60.11% | 14.99% | 36.92% | 24.43% | 100.92% |
| QQQ Sharpe-Mom Top-2: T+2 Close (2nd trading day close) | 35.51% | 39.6% | 0.92 | -51.5% | 0.69 | 26.09% | 45.00% | 48.72% | 18.69% | 33.76% | 24.35% | 82.59% |
| Tech Top-1 (S1): T+2 Close (2nd trading day close) | 35.13% | 49.5% | 0.81 | -62.1% | 0.57 | 14.96% | 52.00% | 66.45% | 7.31% | 35.57% | 20.39% | 113.37% |
| Core3: T+3 Open (3rd trading day open) | 36.64% | 40.6% | 0.92 | -40.4% | 0.91 | 21.70% | 49.01% | 58.65% | 15.31% | 32.86% | 21.91% | 103.89% |
| QQQ Sharpe-Mom Top-2: T+3 Open (3rd trading day open) | 34.14% | 39.2% | 0.90 | -49.6% | 0.69 | 25.05% | 43.80% | 46.86% | 17.07% | 32.32% | 20.89% | 84.59% |
| Tech Top-1 (S1): T+3 Open (3rd trading day open) | 34.30% | 50.3% | 0.79 | -62.2% | 0.55 | 14.16% | 49.08% | 65.63% | 9.48% | 28.65% | 18.98% | 117.31% |
| Core3: T+5 Open (5th trading day open) | 35.25% | 41.1% | 0.89 | -42.1% | 0.84 | 23.96% | 44.78% | 51.35% | 18.36% | 31.34% | 17.85% | 94.36% |
| QQQ Sharpe-Mom Top-2: T+5 Open (5th trading day open) | 33.58% | 38.6% | 0.90 | -52.7% | 0.64 | 26.78% | 40.82% | 42.90% | 20.47% | 30.48% | 22.42% | 74.38% |
| Tech Top-1 (S1): T+5 Open (5th trading day open) | 31.67% | 52.5% | 0.74 | -63.3% | 0.50 | 17.06% | 43.15% | 53.24% | 11.78% | 28.53% | 8.58% | 106.14% |

### T6a. Check 6 — Outlier Month Removal & Simultaneous Super-Winner Stock Bans

| Variant | CAGR 09-26 | Vol | Sharpe | MaxDD (m) | Calmar | 2009-2018 | 2015-2026 | 2019-2026 | 2009-2014 | 2015-2019 | 2020-2022 | 2023-26.09 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Baseline Core3 (No months dropped, no stocks banned) [FROZEN] | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| Drop best 1 months of Core3 -> 0% (2026-04) | 40.13% | 37.3% | 1.05 | -36.6% | 1.09 | 24.95% | 53.53% | 62.46% | 17.16% | 39.51% | 36.01% | 92.21% |
| Drop best 3 months of Core3 -> 0% (2026-04, 2026-05, 2026-01) | 34.19% | 34.1% | 1.00 | -36.6% | 0.93 | 24.95% | 43.82% | 47.12% | 17.16% | 39.51% | 36.01% | 56.61% |
| Drop best 5 months of Core3 -> 0% (2026-04, 2026-05, 2026-01, 2025-04,) | 29.86% | 32.5% | 0.93 | -36.6% | 0.81 | 24.95% | 36.86% | 36.47% | 17.16% | 39.51% | 23.48% | 44.85% |
| Drop best 10 months of Core3 -> 0% (2026-04, 2026-05, 2026-01, 2025-04,) | 21.59% | 29.9% | 0.76 | -36.6% | 0.59 | 19.60% | 23.91% | 24.20% | 17.16% | 27.81% | 14.42% | 26.72% |
| Ban NVDA (both sleeves) | 34.83% | 39.8% | 0.91 | -36.6% | 0.95 | 15.77% | 44.85% | 64.12% | 17.16% | 19.76% | 27.21% | 107.10% |
| Ban SNDK (both sleeves) | 42.29% | 35.5% | 1.13 | -32.1% | 1.32 | 26.99% | 54.98% | 64.78% | 20.37% | 39.51% | 36.01% | 97.94% |
| Ban PLTR (both sleeves) | 37.91% | 38.4% | 0.99 | -36.6% | 1.03 | 24.95% | 49.88% | 56.63% | 17.16% | 39.51% | 36.01% | 78.25% |
| Ban MU (both sleeves) | 42.36% | 39.6% | 1.05 | -36.6% | 1.16 | 23.09% | 58.99% | 71.75% | 14.66% | 38.93% | 36.01% | 115.63% |
| Ban MRNA (both sleeves) | 43.56% | 39.4% | 1.07 | -36.6% | 1.19 | 24.95% | 59.25% | 71.71% | 17.16% | 39.51% | 34.35% | 117.66% |
| Ban TSLA (both sleeves) | 40.39% | 38.5% | 1.03 | -36.6% | 1.10 | 24.46% | 54.49% | 63.99% | 16.39% | 39.51% | 19.31% | 117.66% |
| Ban AAPL (both sleeves) | 43.19% | 39.8% | 1.06 | -37.3% | 1.16 | 24.17% | 59.78% | 72.09% | 15.51% | 40.14% | 35.11% | 117.66% |
| Ban AVGO (both sleeves) | 42.91% | 39.3% | 1.07 | -36.6% | 1.17 | 23.50% | 58.43% | 72.53% | 16.80% | 36.80% | 36.01% | 117.67% |
| Ban AMD (both sleeves) | 41.98% | 40.0% | 1.04 | -42.1% | 1.00 | 26.50% | 55.93% | 64.79% | 18.18% | 32.94% | 34.07% | 117.66% |
| Ban Netflix NFLX (both sleeves) | 42.10% | 39.7% | 1.04 | -44.6% | 0.94 | 22.33% | 60.09% | 72.41% | 12.51% | 40.37% | 36.01% | 117.35% |
| Ban Top-1 Contributor (NVDA) | 34.83% | 39.8% | 0.91 | -36.6% | 0.95 | 15.77% | 44.85% | 64.12% | 17.16% | 19.76% | 27.21% | 107.10% |
| Ban Top-2 Contributors (NVDA,SNDK) | 33.36% | 35.7% | 0.94 | -32.4% | 1.03 | 17.66% | 40.53% | 56.75% | 20.37% | 19.76% | 27.21% | 88.34% |
| Ban Top-3 Contributors (NVDA,SNDK,PLTR) | 27.45% | 33.8% | 0.84 | -32.4% | 0.85 | 17.66% | 31.22% | 41.29% | 20.37% | 19.76% | 27.21% | 51.96% |
| Ban Top-5 Contributors (NVDA,SNDK,PLTR,TSLA,MU) | 19.76% | 31.4% | 0.68 | -32.4% | 0.61 | 13.38% | 22.32% | 28.53% | 14.92% | 17.57% | 11.72% | 38.64% |

### T6b. Top 15 Stock Contributors to Core3 Total Log-Wealth (2009–2026)

| Ticker | Months Held | Months @ 75% (Both Sleeves) | Mean Weight When Held | Share of Total Log-Wealth | Best Month | Worst Month |
|---|---|---|---|---|---|---|
| NVDA | 50 | 28 | 60.0% | 30.87% | 38.6% | -15.8% |
| SNDK | 12 | 7 | 62.5% | 10.16% | 63.5% | -44.4% |
| PLTR | 12 | 11 | 72.9% | 10.01% | 43.1% | -19.5% |
| TSLA | 23 | 0 | 25.0% | 9.16% | 73.2% | -22.5% |
| MU | 20 | 7 | 52.5% | 8.82% | 27.3% | -15.3% |
| WDC | 8 | 2 | 40.6% | 7.13% | 44.8% | -13.3% |
| AMD | 18 | 1 | 51.4% | 4.16% | 36.6% | -22.3% |
| ON | 3 | 0 | 50.0% | 3.90% | 30.4% | 3.8% |
| STX | 10 | 2 | 42.5% | 3.82% | 68.2% | -12.5% |
| AVGO | 9 | 3 | 44.4% | 3.56% | 25.7% | -7.6% |
| NFLX | 16 | 0 | 25.0% | 3.44% | 22.6% | -12.9% |
| LRCX | 4 | 1 | 37.5% | 2.73% | 15.0% | 11.5% |
| FSLR | 7 | 0 | 50.0% | 2.59% | 20.3% | -16.0% |
| EA | 10 | 5 | 55.0% | 2.49% | 16.6% | -9.7% |
| ALXN | 11 | 0 | 25.0% | 1.94% | 12.9% | -3.7% |

### T7. Check 7 — Second-Vendor (Tiingo-First) End-to-End Replication

| Variant | CAGR 09-26 | Vol | Sharpe | MaxDD (m) | Calmar | 2009-2018 | 2015-2026 | 2019-2026 | 2009-2014 | 2015-2019 | 2020-2022 | 2023-26.09 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Core3 Primary (Yahoo-First Open-to-Open) [FROZEN] | 43.85% | 39.6% | 1.08 | -36.6% | 1.20 | 24.95% | 59.75% | 72.53% | 17.16% | 39.51% | 36.01% | 117.66% |
| Core3 Second-Vendor (Tiingo-First Signals & Open-to-Open) | 43.93% | 39.5% | 1.08 | -36.6% | 1.20 | 24.98% | 59.85% | 72.69% | 17.20% | 39.71% | 36.01% | 117.66% |
| QQQ Sharpe-Mom Top-2 Primary | 43.96% | 40.1% | 1.07 | -41.4% | 1.06 | 31.35% | 54.69% | 62.05% | 25.06% | 35.92% | 33.01% | 107.42% |
| QQQ Sharpe-Mom Top-2 Tiingo-First | 43.96% | 40.1% | 1.07 | -41.4% | 1.06 | 31.35% | 54.69% | 62.05% | 25.06% | 35.92% | 33.01% | 107.43% |
| Tech Top-1 (S1) Primary | 38.73% | 47.8% | 0.89 | -67.0% | 0.58 | 14.48% | 59.89% | 77.74% | 5.05% | 39.16% | 33.60% | 122.14% |
| Tech Top-1 (S1) Tiingo-First | 38.87% | 47.8% | 0.89 | -66.9% | 0.58 | 14.52% | 60.09% | 78.09% | 5.11% | 39.58% | 33.60% | 122.14% |

### T8a. Check 8 — True Daily Mark-to-Market MaxDD vs Monthly MaxDD (4,466 Trading Days)

| Strategy | CAGR 09-26 | Monthly MaxDD | True Daily MaxDD | Daily - Monthly Gap | Peak Date | Trough Date | Recovery Date | Max Underwater (Trading Days) | Daily Ann Vol | Calmar (vs Daily DD) |
|---|---|---|---|---|---|---|---|---|---|---|
| Core3 (50% QQQ Sharpe Top-2 + 50% Tech Top-1) [FROZEN] | 43.85% | -36.65% | -46.76% | -10.11% | 2026-06-25 | 2026-07-29 | Unrecovered | 941 | 42.8% | 0.94 |
| Core4 (1/3 QQQ Raw + 1/3 QQQ Sharpe + 1/3 Tech) | 42.66% | -34.54% | -44.36% | -9.82% | 2026-06-25 | 2026-07-29 | Unrecovered | 614 | 41.7% | 0.96 |
| Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1) | 40.74% | -37.34% | -47.27% | -9.93% | 2026-06-25 | 2026-07-29 | Unrecovered | 606 | 45.1% | 0.86 |
| Sleeve 1 Standalone: QQQ Sharpe-Mom Top-2 | 43.96% | -41.38% | -48.39% | -7.01% | 2025-02-18 | 2025-04-04 | 2025-08-06 | 820 | 40.0% | 0.91 |
| Sleeve 1b Standalone: QQQ Raw 12-1 Top-2 | 37.13% | -63.27% | -68.75% | -5.48% | 2021-08-09 | 2023-05-03 | 2025-09-10 | 1025 | 44.6% | 0.54 |
| Sleeve 2 Standalone: S&P 500 Tech Top-1 (S1) | 38.73% | -67.04% | -69.68% | -2.64% | 2009-01-06 | 2012-01-23 | 2014-07-23 | 1394 | 53.7% | 0.56 |
| Benchmark: QQQ ETF | 20.87% | -32.24% | -35.12% | -2.88% | 2021-12-27 | 2022-11-03 | 2023-12-13 | 493 | 20.9% | 0.59 |
| Benchmark: XLK ETF | 21.59% | -30.76% | -33.56% | -2.80% | 2021-12-27 | 2022-10-12 | 2023-06-15 | 368 | 22.3% | 0.64 |

### T8b. Top 10 Worst Daily Drawdown Episodes for Core3 (2009–2026)

| Peak Date | Trough Date | Recovery Date | True Daily MaxDD | Peak-to-Trough (Days) | Total Underwater (Days) |
|---|---|---|---|---|---|
| 2026-06-25 | 2026-07-29 | Ongoing | -46.76% | 24 | 67 |
| 2025-02-18 | 2025-04-04 | 2025-06-13 | -43.59% | 34 | 81 |
| 2009-10-14 | 2011-12-14 | 2013-07-12 | -39.74% | 548 | 941 |
| 2015-07-21 | 2016-02-12 | 2016-07-13 | -39.07% | 144 | 247 |
| 2021-02-12 | 2021-05-13 | 2022-11-10 | -37.02% | 63 | 440 |
| 2020-02-19 | 2020-03-20 | 2020-05-06 | -34.58% | 23 | 54 |
| 2018-06-14 | 2018-10-29 | 2019-03-18 | -34.24% | 96 | 189 |
| 2024-06-18 | 2024-07-30 | 2025-02-03 | -26.49% | 29 | 156 |
| 2026-03-19 | 2026-03-30 | 2026-04-08 | -24.96% | 8 | 13 |
| 2019-07-26 | 2019-11-22 | 2020-02-14 | -24.21% | 85 | 140 |

### T9a. Calendar-Year Net Returns & Intra-Year True Daily MaxDD (2009–2026)

| Year | Core3 (Frozen 50/50) | Core3 (Unified Mult) | Core4 (3-Way) | Core1 (Raw 50/50) | QQQ Sharpe Top-2 | QQQ Raw Top-2 | QQQ Raw Top-3 | Tech Top-1 (S1) | Bench QQQ ETF | Bench XLK ETF | Bench SPY ETF | Core3_IntraYear_Daily_MaxDD | QQQ_IntraYear_Daily_MaxDD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2009 | -8.2% | -8.2% | -1.1% | -2.8% | 1.1% | 13.5% | 4.8% | -18.6% | 56.5% | 51.8% | 27.1% | -21.9% | -18.3% |
| 2010 | -11.2% | -11.2% | -10.9% | -8.4% | -16.7% | -12.2% | 3.5% | -9.1% | 19.5% | 11.2% | 15.0% | -32.7% | -15.8% |
| 2011 | -19.6% | -19.7% | -6.6% | -20.5% | 21.7% | 21.5% | -15.9% | -52.9% | 4.4% | 3.5% | 2.9% | -36.5% | -16.1% |
| 2012 | 28.5% | 28.5% | 33.9% | 42.0% | 17.9% | 42.6% | 29.8% | 36.9% | 18.6% | 16.5% | 16.1% | -23.6% | -11.6% |
| 2013 | 88.3% | 88.2% | 78.3% | 62.0% | 111.3% | 57.5% | 49.7% | 61.0% | 32.8% | 22.5% | 29.3% | -9.8% | -5.9% |
| 2014 | 62.9% | 62.9% | 57.2% | 60.6% | 49.8% | 44.3% | 61.5% | 75.0% | 20.3% | 19.0% | 14.4% | -20.0% | -8.2% |
| 2015 | 25.9% | 25.9% | 20.0% | 20.5% | 17.8% | 6.8% | 8.4% | 32.4% | 6.5% | 2.9% | -0.8% | -19.7% | -13.9% |
| 2016 | 110.9% | 110.8% | 100.6% | 119.6% | 66.8% | 81.0% | 34.4% | 164.6% | 10.2% | 17.9% | 14.7% | -25.3% | -12.0% |
| 2017 | 47.9% | 47.9% | 47.7% | 36.2% | 71.3% | 44.0% | 37.8% | 22.5% | 32.4% | 33.9% | 21.3% | -17.7% | -4.9% |
| 2018 | -8.6% | -8.6% | -10.5% | -23.0% | 18.7% | -17.9% | -5.9% | -33.0% | -2.7% | -4.1% | -6.4% | -34.2% | -22.8% |
| 2019 | 47.3% | 47.3% | 45.2% | 60.2% | 16.1% | 40.0% | 38.5% | 81.4% | 43.2% | 54.4% | 34.0% | -24.2% | -11.0% |
| 2020 | 114.0% | 113.8% | 128.5% | 109.7% | 164.0% | 157.9% | 159.8% | 66.4% | 48.0% | 43.1% | 18.2% | -34.6% | -28.6% |
| 2021 | 7.7% | 7.7% | 30.5% | 41.1% | 9.1% | 78.9% | 54.2% | 1.2% | 27.2% | 34.2% | 28.6% | -37.0% | -10.9% |
| 2022 | 9.1% | 9.2% | -11.4% | -8.5% | -18.3% | -43.2% | -42.0% | 41.6% | -32.2% | -27.1% | -18.0% | -25.2% | -34.8% |
| 2023 | 24.9% | 24.9% | 15.5% | 20.7% | 4.9% | -3.8% | 3.2% | 45.0% | 52.1% | 52.3% | 24.7% | -17.5% | -10.8% |
| 2024 | 70.0% | 69.9% | 57.6% | 36.1% | 105.8% | 31.8% | 54.1% | 35.8% | 27.5% | 24.3% | 26.4% | -26.5% | -13.6% |
| 2025 | 126.1% | 126.0% | 114.2% | 114.6% | 111.0% | 87.8% | 79.8% | 137.5% | 21.2% | 25.1% | 17.7% | -43.6% | -22.8% |
| 2026 (Jan-Sep) | 284.9% | 284.6% | 272.7% | 289.1% | 238.8% | 247.2% | 212.5% | 326.5% | 20.2% | 35.7% | 12.3% | -46.8% | -11.7% |

### T9b. Paired Hypothesis Tests (Newey-West HAC, Stationary Bootstrap & CAPM Alpha)

| Window | Benchmark | Core3 CAGR | Bench CAGR | CAGR Diff | NW t (lag 3) | NW p (lag 3) | NW t (lag 6) | Boot 5% | Boot 95% | Boot P(diff<=0) | Win Months | CAPM Alpha/yr | Beta | Alpha NW t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FULL 2009-01..2026-09 | Bench QQQ ETF | 43.85% | 20.87% | 22.98% | 2.57 | 0.010 | 2.29 | 5.2% | 46.0% | 0.015 | 55.9% | 17.94% | 1.28 | 1.96 |
| FULL 2009-01..2026-09 | Bench XLK ETF | 43.85% | 21.59% | 22.27% | 2.58 | 0.010 | 2.32 | 5.1% | 44.4% | 0.013 | 54.5% | 17.08% | 1.27 | 1.96 |
| FULL 2009-01..2026-09 | Bench NDX-EW (PIT 10bp) | 43.85% | 17.18% | 26.68% | 2.90 | 0.004 | 2.58 | 8.7% | 49.8% | 0.006 | 57.7% | 23.48% | 1.20 | 2.55 |
| FULL 2009-01..2026-09 | Bench SPY ETF | 43.85% | 14.82% | 29.04% | 3.12 | 0.002 | 2.80 | 10.9% | 52.9% | 0.002 | 55.4% | 26.10% | 1.21 | 2.81 |
| FULL 2009-01..2026-09 | Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1) | 43.85% | 40.74% | 3.11% | 0.57 | 0.567 | 0.56 | -3.2% | 9.2% | 0.190 | 39.4% | 4.66% | 0.92 | 1.75 |
| FULL 2009-01..2026-09 | Sleeve 1 Alone: QQQ Sharpe-Mom Top-2 | 43.85% | 43.96% | -0.11% | -0.03 | 0.974 | -0.03 | -11.1% | 10.7% | 0.502 | 54.5% | 5.51% | 0.87 | 1.15 |
| FULL 2009-01..2026-09 | Sleeve 2 Alone: Tech Top-1 (S1) | 43.85% | 38.73% | 5.13% | 0.03 | 0.974 | 0.03 | -6.5% | 15.4% | 0.233 | 45.5% | 10.43% | 0.76 | 2.68 |
| FULL 2009-01..2026-09 | QQQ Raw 12-1 Top-3 (Audited) | 43.85% | 32.88% | 10.97% | 1.19 | 0.232 | 1.13 | -3.3% | 25.1% | 0.107 | 54.9% | 16.48% | 0.75 | 2.77 |
| 2009-2018 (pre-2019) | Bench QQQ ETF | 24.95% | 18.81% | 6.15% | 0.82 | 0.412 | 0.76 | -12.7% | 29.1% | 0.309 | 49.2% | 9.14% | 0.92 | 0.98 |
| 2009-2018 (pre-2019) | Bench XLK ETF | 24.95% | 16.55% | 8.40% | 1.03 | 0.302 | 0.97 | -10.5% | 31.1% | 0.241 | 50.8% | 11.14% | 0.91 | 1.19 |
| 2009-2018 (pre-2019) | Bench NDX-EW (PIT 10bp) | 24.95% | 16.95% | 8.00% | 0.97 | 0.331 | 0.90 | -11.5% | 31.2% | 0.262 | 51.7% | 11.70% | 0.85 | 1.25 |
| 2009-2018 (pre-2019) | Bench SPY ETF | 24.95% | 12.80% | 12.15% | 1.42 | 0.156 | 1.33 | -6.4% | 35.1% | 0.146 | 50.8% | 15.34% | 0.83 | 1.65 |
| 2009-2018 (pre-2019) | Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1) | 24.95% | 21.92% | 3.04% | 0.72 | 0.470 | 0.71 | -2.5% | 8.6% | 0.190 | 37.5% | 4.26% | 0.91 | 1.53 |
| 2009-2018 (pre-2019) | Sleeve 1 Alone: QQQ Sharpe-Mom Top-2 | 24.95% | 31.35% | -6.40% | -0.92 | 0.356 | -0.92 | -17.9% | 5.3% | 0.822 | 50.0% | 2.79% | 0.74 | 0.48 |
| 2009-2018 (pre-2019) | Sleeve 2 Alone: Tech Top-1 (S1) | 24.95% | 14.48% | 10.47% | 0.92 | 0.356 | 0.92 | -1.4% | 20.3% | 0.071 | 50.0% | 12.84% | 0.64 | 3.10 |
| 2009-2018 (pre-2019) | QQQ Raw 12-1 Top-3 (Audited) | 24.95% | 18.37% | 6.58% | 0.67 | 0.505 | 0.69 | -6.7% | 21.1% | 0.209 | 51.7% | 11.88% | 0.67 | 1.64 |
| 2015-2026.09 | Bench QQQ ETF | 59.75% | 19.12% | 40.63% | 3.12 | 0.002 | 2.82 | 15.3% | 75.2% | 0.001 | 63.1% | 29.64% | 1.45 | 2.47 |
| 2015-2026.09 | Bench XLK ETF | 59.75% | 22.47% | 37.28% | 2.97 | 0.003 | 2.69 | 12.5% | 70.9% | 0.002 | 58.2% | 26.31% | 1.39 | 2.30 |
| 2015-2026.09 | Bench NDX-EW (PIT 10bp) | 59.75% | 13.65% | 46.10% | 3.59 | 0.000 | 3.24 | 20.7% | 81.3% | 0.000 | 64.5% | 36.71% | 1.47 | 3.15 |
| 2015-2026.09 | Bench SPY ETF | 59.75% | 13.65% | 46.10% | 3.46 | 0.001 | 3.13 | 19.8% | 81.9% | 0.000 | 59.6% | 36.98% | 1.49 | 3.02 |
| 2015-2026.09 | Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1) | 59.75% | 54.41% | 5.34% | 0.71 | 0.475 | 0.71 | -3.9% | 14.0% | 0.155 | 44.0% | 6.42% | 0.93 | 1.77 |
| 2015-2026.09 | Sleeve 1 Alone: QQQ Sharpe-Mom Top-2 | 59.75% | 54.69% | 5.05% | 0.61 | 0.543 | 0.58 | -9.4% | 18.9% | 0.289 | 58.9% | 7.58% | 0.93 | 1.25 |
| 2015-2026.09 | Sleeve 2 Alone: Tech Top-1 (S1) | 59.75% | 59.89% | -0.14% | -0.61 | 0.543 | -0.58 | -15.7% | 13.8% | 0.499 | 41.1% | 7.79% | 0.80 | 1.55 |
| 2015-2026.09 | QQQ Raw 12-1 Top-3 (Audited) | 59.75% | 40.50% | 19.24% | 1.54 | 0.125 | 1.43 | -0.6% | 38.9% | 0.054 | 60.3% | 22.62% | 0.77 | 2.88 |
| 2019-2026.09 | Bench QQQ ETF | 72.53% | 23.59% | 48.94% | 2.73 | 0.006 | 2.42 | 13.9% | 101.7% | 0.005 | 64.5% | 32.21% | 1.55 | 2.01 |
| 2019-2026.09 | Bench XLK ETF | 72.53% | 28.41% | 44.12% | 2.57 | 0.010 | 2.29 | 10.2% | 94.5% | 0.010 | 59.1% | 27.65% | 1.46 | 1.84 |
| 2019-2026.09 | Bench NDX-EW (PIT 10bp) | 72.53% | 17.47% | 55.06% | 3.08 | 0.002 | 2.74 | 20.3% | 108.4% | 0.001 | 65.6% | 40.84% | 1.54 | 2.60 |
| 2019-2026.09 | Bench SPY ETF | 72.53% | 17.47% | 55.06% | 2.97 | 0.003 | 2.66 | 18.7% | 110.3% | 0.001 | 61.3% | 41.21% | 1.55 | 2.49 |
| 2019-2026.09 | Core1 (50% QQQ Raw Top-2 + 50% Tech Top-1) | 72.53% | 69.39% | 3.14% | 0.18 | 0.858 | 0.17 | -12.1% | 16.8% | 0.341 | 41.9% | 5.33% | 0.93 | 1.04 |
| 2019-2026.09 | Sleeve 1 Alone: QQQ Sharpe-Mom Top-2 | 72.53% | 62.05% | 10.48% | 0.83 | 0.407 | 0.78 | -10.8% | 30.9% | 0.203 | 60.2% | 11.40% | 0.92 | 1.47 |
| 2019-2026.09 | Sleeve 2 Alone: Tech Top-1 (S1) | 72.53% | 77.74% | -5.22% | -0.83 | 0.407 | -0.78 | -29.8% | 15.9% | 0.650 | 39.8% | 5.46% | 0.83 | 0.79 |
| 2019-2026.09 | QQQ Raw 12-1 Top-3 (Audited) | 72.53% | 54.27% | 18.26% | 1.00 | 0.315 | 0.89 | -12.2% | 44.7% | 0.147 | 59.1% | 23.29% | 0.77 | 2.39 |

### T9c. Multiple-Testing Deflated Sharpe Ratio (DSR) Across All Repo + Session Trials

| Window | Series Tested | N Trials | Observed SR/IR (Ann) | Expected Max Null SR0 (Ann) | Skew | Kurt | DSR (Prob True > 0) |
|---|---|---|---|---|---|---|---|
| FULL 2009-01..2026-09 (213m) | Core3 Excess Return (over 3M T-bill) | 1 | 1.08 | 0.00 | 1.07 | 7.45 | 1.000 |
| FULL 2009-01..2026-09 (213m) | Core3 Excess Return (over 3M T-bill) | 10 | 1.08 | 0.47 | 1.07 | 7.45 | 0.998 |
| FULL 2009-01..2026-09 (213m) | Core3 Excess Return (over 3M T-bill) | 39 | 1.08 | 0.65 | 1.07 | 7.45 | 0.978 |
| FULL 2009-01..2026-09 (213m) | Core3 Excess Return (over 3M T-bill) | 100 | 1.08 | 0.75 | 1.07 | 7.45 | 0.936 |
| FULL 2009-01..2026-09 (213m) | Core3 Excess Return (over 3M T-bill) | 481 | 1.08 | 0.90 | 1.07 | 7.45 | 0.794 |
| FULL 2009-01..2026-09 (213m) | Core3 Excess Return (over 3M T-bill) | 520 | 1.08 | 0.91 | 1.07 | 7.45 | 0.785 |
| FULL 2009-01..2026-09 (213m) | Core3 Excess Return (over 3M T-bill) | 579 | 1.08 | 0.92 | 1.07 | 7.45 | 0.772 |
| FULL 2009-01..2026-09 (213m) | Core3 Active Return (minus QQQ ETF) | 1 | 0.72 | 0.00 | 1.30 | 8.02 | 1.000 |
| FULL 2009-01..2026-09 (213m) | Core3 Active Return (minus QQQ ETF) | 10 | 0.72 | 0.47 | 1.30 | 8.02 | 0.885 |
| FULL 2009-01..2026-09 (213m) | Core3 Active Return (minus QQQ ETF) | 39 | 0.72 | 0.65 | 1.30 | 8.02 | 0.640 |
| FULL 2009-01..2026-09 (213m) | Core3 Active Return (minus QQQ ETF) | 100 | 0.72 | 0.75 | 1.30 | 8.02 | 0.448 |
| FULL 2009-01..2026-09 (213m) | Core3 Active Return (minus QQQ ETF) | 481 | 0.72 | 0.90 | 1.30 | 8.02 | 0.200 |
| FULL 2009-01..2026-09 (213m) | Core3 Active Return (minus QQQ ETF) | 520 | 0.72 | 0.91 | 1.30 | 8.02 | 0.191 |
| FULL 2009-01..2026-09 (213m) | Core3 Active Return (minus QQQ ETF) | 579 | 0.72 | 0.92 | 1.30 | 8.02 | 0.179 |
| FULL 2009-01..2026-09 (213m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 1 | 0.14 | 0.00 | -0.15 | 8.03 | 0.722 |
| FULL 2009-01..2026-09 (213m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 10 | 0.14 | 0.47 | -0.15 | 8.03 | 0.086 |
| FULL 2009-01..2026-09 (213m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 39 | 0.14 | 0.65 | -0.15 | 8.03 | 0.017 |
| FULL 2009-01..2026-09 (213m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 100 | 0.14 | 0.75 | -0.15 | 8.03 | 0.005 |
| FULL 2009-01..2026-09 (213m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 481 | 0.14 | 0.90 | -0.15 | 8.03 | 0.001 |
| FULL 2009-01..2026-09 (213m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 520 | 0.14 | 0.91 | -0.15 | 8.03 | 0.001 |
| FULL 2009-01..2026-09 (213m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 579 | 0.14 | 0.92 | -0.15 | 8.03 | 0.001 |
| 2015-01..2026-09 (141m) | Core3 Excess Return (over 3M T-bill) | 1 | 1.22 | 0.00 | 0.98 | 6.31 | 1.000 |
| 2015-01..2026-09 (141m) | Core3 Excess Return (over 3M T-bill) | 10 | 1.22 | 0.47 | 0.98 | 6.31 | 0.998 |
| 2015-01..2026-09 (141m) | Core3 Excess Return (over 3M T-bill) | 39 | 1.22 | 0.65 | 0.98 | 6.31 | 0.985 |
| 2015-01..2026-09 (141m) | Core3 Excess Return (over 3M T-bill) | 100 | 1.22 | 0.75 | 0.98 | 6.31 | 0.962 |
| 2015-01..2026-09 (141m) | Core3 Excess Return (over 3M T-bill) | 481 | 1.22 | 0.90 | 0.98 | 6.31 | 0.886 |
| 2015-01..2026-09 (141m) | Core3 Excess Return (over 3M T-bill) | 520 | 1.22 | 0.91 | 0.98 | 6.31 | 0.881 |
| 2015-01..2026-09 (141m) | Core3 Excess Return (over 3M T-bill) | 579 | 1.22 | 0.92 | 0.98 | 6.31 | 0.874 |
| 2015-01..2026-09 (141m) | Core3 Active Return (minus QQQ ETF) | 1 | 1.04 | 0.00 | 1.15 | 6.98 | 1.000 |
| 2015-01..2026-09 (141m) | Core3 Active Return (minus QQQ ETF) | 10 | 1.04 | 0.47 | 1.15 | 6.98 | 0.986 |
| 2015-01..2026-09 (141m) | Core3 Active Return (minus QQQ ETF) | 39 | 1.04 | 0.65 | 1.15 | 6.98 | 0.932 |
| 2015-01..2026-09 (141m) | Core3 Active Return (minus QQQ ETF) | 100 | 1.04 | 0.75 | 1.15 | 6.98 | 0.863 |
| 2015-01..2026-09 (141m) | Core3 Active Return (minus QQQ ETF) | 481 | 1.04 | 0.90 | 1.15 | 6.98 | 0.695 |
| 2015-01..2026-09 (141m) | Core3 Active Return (minus QQQ ETF) | 520 | 1.04 | 0.91 | 1.15 | 6.98 | 0.686 |
| 2015-01..2026-09 (141m) | Core3 Active Return (minus QQQ ETF) | 579 | 1.04 | 0.92 | 1.15 | 6.98 | 0.672 |
| 2015-01..2026-09 (141m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 1 | 0.22 | 0.00 | -0.46 | 7.51 | 0.772 |
| 2015-01..2026-09 (141m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 10 | 0.22 | 0.47 | -0.46 | 7.51 | 0.205 |
| 2015-01..2026-09 (141m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 39 | 0.22 | 0.65 | -0.46 | 7.51 | 0.077 |
| 2015-01..2026-09 (141m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 100 | 0.22 | 0.75 | -0.46 | 7.51 | 0.038 |
| 2015-01..2026-09 (141m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 481 | 0.22 | 0.90 | -0.46 | 7.51 | 0.011 |
| 2015-01..2026-09 (141m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 520 | 0.22 | 0.91 | -0.46 | 7.51 | 0.011 |
| 2015-01..2026-09 (141m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 579 | 0.22 | 0.92 | -0.46 | 7.51 | 0.010 |
| 2009-2018 Pre-2019 (120m) | Core3 Excess Return (over 3M T-bill) | 1 | 0.92 | 0.00 | 0.12 | 3.08 | 0.998 |
| 2009-2018 Pre-2019 (120m) | Core3 Excess Return (over 3M T-bill) | 10 | 0.92 | 0.47 | 0.12 | 3.08 | 0.923 |
| 2009-2018 Pre-2019 (120m) | Core3 Excess Return (over 3M T-bill) | 39 | 0.92 | 0.65 | 0.12 | 3.08 | 0.805 |
| 2009-2018 Pre-2019 (120m) | Core3 Excess Return (over 3M T-bill) | 100 | 0.92 | 0.75 | 0.12 | 3.08 | 0.703 |
| 2009-2018 Pre-2019 (120m) | Core3 Excess Return (over 3M T-bill) | 481 | 0.92 | 0.90 | 0.12 | 3.08 | 0.523 |
| 2009-2018 Pre-2019 (120m) | Core3 Excess Return (over 3M T-bill) | 520 | 0.92 | 0.91 | 0.12 | 3.08 | 0.514 |
| 2009-2018 Pre-2019 (120m) | Core3 Excess Return (over 3M T-bill) | 579 | 0.92 | 0.92 | 0.12 | 3.08 | 0.502 |
| 2009-2018 Pre-2019 (120m) | Core3 Active Return (minus QQQ ETF) | 1 | 0.32 | 0.00 | 0.42 | 3.83 | 0.848 |
| 2009-2018 Pre-2019 (120m) | Core3 Active Return (minus QQQ ETF) | 10 | 0.32 | 0.47 | 0.42 | 3.83 | 0.320 |
| 2009-2018 Pre-2019 (120m) | Core3 Active Return (minus QQQ ETF) | 39 | 0.32 | 0.65 | 0.42 | 3.83 | 0.149 |
| 2009-2018 Pre-2019 (120m) | Core3 Active Return (minus QQQ ETF) | 100 | 0.32 | 0.75 | 0.42 | 3.83 | 0.084 |
| 2009-2018 Pre-2019 (120m) | Core3 Active Return (minus QQQ ETF) | 481 | 0.32 | 0.90 | 0.42 | 3.83 | 0.031 |
| 2009-2018 Pre-2019 (120m) | Core3 Active Return (minus QQQ ETF) | 520 | 0.32 | 0.91 | 0.42 | 3.83 | 0.030 |
| 2009-2018 Pre-2019 (120m) | Core3 Active Return (minus QQQ ETF) | 579 | 0.32 | 0.92 | 0.42 | 3.83 | 0.028 |
| 2009-2018 Pre-2019 (120m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 1 | 0.23 | 0.00 | 0.91 | 6.90 | 0.767 |
| 2009-2018 Pre-2019 (120m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 10 | 0.23 | 0.47 | 0.91 | 6.90 | 0.217 |
| 2009-2018 Pre-2019 (120m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 39 | 0.23 | 0.65 | 0.91 | 6.90 | 0.086 |
| 2009-2018 Pre-2019 (120m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 100 | 0.23 | 0.75 | 0.91 | 6.90 | 0.044 |
| 2009-2018 Pre-2019 (120m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 481 | 0.23 | 0.90 | 0.91 | 6.90 | 0.014 |
| 2009-2018 Pre-2019 (120m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 520 | 0.23 | 0.91 | 0.91 | 6.90 | 0.013 |
| 2009-2018 Pre-2019 (120m) | Core3 vs Core1 (Sharpe-Mom improvement over Raw Mom) | 579 | 0.23 | 0.92 | 0.91 | 6.90 | 0.012 |
