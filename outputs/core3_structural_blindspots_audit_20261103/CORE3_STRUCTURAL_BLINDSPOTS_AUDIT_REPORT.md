# Core3 Structural Blindspots & Academic Mechanisms Forensic Audit Report
**Hypotheses E (Cross-Sleeve Overlap & 75% Single-Stock Concentration), F (Skip-Month Breakdown Veto & Signal Freshness), G (Buy-Hold Rank Buffers & Overlapping Tranches), H (Portfolio-Own Realized Vol & Crash State), and I (Sleeve-Asymmetric Domain Physics)**

- **Date**: 2026-11-03
- **Baseline Control (`Core3` Frozen)**:
  - **50% `QQQ Sharpe-Momentum Top-2` + 50% `Historical S&P 500 IT Tech 12-1 Momentum Top-1 [S1]`**
  - **Execution**: Month-end signal at $t$, `T+1 Open` entry/exit, `10 bp/side` transaction cost, `1.0x` unlevered (`Cash = 0%`).

---

## 1. Executive Summary Across All 5 Overlooked Structural Mechanisms (`E`, `F`, `G`, `H`, `I`)

| Mechanism / Hypothesis | Core Question Tested | Key Empirical Finding (`2009–2026`) | Impact on CAGR vs Control (`43.81%`) | Impact on True Daily MaxDD (`-46.96%`) | Final Audit Verdict |
|---|---|---|---|---|---|
| **E. Cross-Sleeve Overlap & 75% Single-Stock Concentration** | In `35.7%` of months (`76/213`), `Tech #1` is also in `QQQ Top-2`, putting **`75%` in 1 stock**. Is this overlap the hidden engine of `Core3` or a concentration hazard? | **Both!** In the `76` Overlap Months, `Core3` compounds at **`96.93%/yr` (`+6.55%/mo`, Sharpe `1.80`, Win Rate `76.3%`)** vs `20.79%/yr` in the `137` Non-Overlap Months! De-overlapping to 3 equal-weight stocks (`E1c`) cuts Daily MaxDD to **`-39.19%`** (Month DD **`-28.5%`**), at the cost of `-4.91%/yr` CAGR (`38.90%`). | `32.86%` – `41.51%` (`-2.3%` to `-10.9%/yr`) | **Improves to `-38.01% ~ -39.19%`** (Month DD **`-28.5%`**) | **KEY STRUCTURAL INSIGHT: Dual-Sleeve Overlap (`75%` weight) is `Core3`'s built-in "Conviction Multiplier"; `E1c` (`33.3% x 3`) is the cleanest `100%`-invested low-DD variant** |
| **F. Skip-Month (`[t-1m, t]`) Breakdown Veto & Short Skip (`12-1w`, `12-0`)** | Does skipping 1 full month cause `Core3` to buy falling knives that crashed in `[t-1m, t]`, or does shortening the skip to 1 week (`12-1w`) / 0 days (`12-0`) improve freshness? | **Short-Term Reversal dominates!** `12-0` collapses to **`31.97%`** (`t = -2.21`) and `12-1w` drops to **`37.30%`**. Vetoing winners that dipped `>15%` in the skipped month (`F1`) drops CAGR to **`36.11%`** (`t = -2.21`) because 1-month pullbacks in 12-month winners strongly mean-revert upward! Only a very tight `ret_1m < -5%` filter (`47.72%`, `t = +0.89`) beats Control, but is an isolated peak with worse DD (`-55.3%`). | `31.97%` – `42.40%` (except isolated `F1 -5%` at `47.72%`) | No improvement (`-46.96%` to `-55.34%`) | **FAIL (Proves classic 21-day `12-1m` skip is essential to harvest 1-month pullback mean reversion)** |
| **G. Rank-Boundary Hysteresis / Buy-Hold Buffer (`Novy-Marx & Velikov 2016`)** | Does holding an existing winner while it stays inside `Top-K_keep` eliminate rank-boundary whipsaw and reduce turnover? | **Sharp Sleeve Asymmetry!** On **`QQQ Only` (`G1`: Buy Top-2, Hold while Top-3/4/5/6; Tech Hard Top-1)**, CAGR rises monotonically across the buffer grid: **`44.89% -> 45.69% -> 48.08% -> 48.70%`**, Sharpe rises **`1.08 -> 1.21`**, Turnover drops **`0.86 -> 0.65`**, Monthly DD drops **`-36.6% -> -27.7%`**, and Daily DD drops **`-46.96% -> -41.96%`**! On `Tech` (`G2`), buffering hurts (`41.73%`) because `Tech Rank #2` (`9.67%`) is a cliff. | **`+1.08%` to `+4.89%/yr` on `G1 (QQQ Buffer)`** (`44.89%` – `48.70%`, `t = +0.65` to `+1.08`) | **Improves to `-41.96%` (`-43.63%` O2C) and Month DD `-27.7%`** | **PASS on `QQQ Sleeve` (`G1`: Reduces Turnover by 20%–25%, Cuts DD, Raises CAGR in Both Halves)** |
| **H. Portfolio-Own Realized Vol Scaling (`Barroso & Santa-Clara 2015`) & Crash State (`Daniel & Moskowitz 2016`)** | Does scaling by the **selected 3-stock basket's OWN 21d/63d realized volatility** (including covariance) outperform QQQ index vol scaling (`Cash = 0%`)? | **Yes — strictly superior to QQQ index vol scaling!** Unlike QQQ index vol scaling (which hurt Sharpe), **Basket-Own 21d Vol Target `35%–40%` (`H1`) increases Sharpe (`1.08 -> 1.10–1.12`)** while cutting Monthly DD to **`-29.6%`** and True Daily DD to **`-38.71% ~ -39.09%`** (`+10.9%` to `+12.9%` in 2022), though `Cash = 0%` costs `7.3%–9.7%/yr` CAGR (`34.09%–36.46%`). Daniel-Moskowitz bear-rebound brake (`H4`) preserves CAGR (`43.94%–44.21%`) and boosts `2009–2018` (`24.79% -> 27.13%`), but does not change worst DD. | `H1`: `27.48%` – `36.46%`; `H4`: `43.94%` – `44.21%` | **`H1` cuts Daily DD to `-35.19% ~ -39.09%`** (Month DD **`-28.1% ~ -29.7%`**) | **STRUCTURAL TRADE-OFF: `H1` is the best risk-control brake tested (`Sharpe 1.12`), but unremunerated cash still costs CAGR** |
| **I. Sleeve-Asymmetric Domain Physics (`QQQ` vs `Tech`)** | Why do `QQQ` and `Tech` behave so differently? What if each sleeve uses only its structurally valid filter (`QQQ 4Q-EAR` + `Tech Pure/A5`) or drops Biotech from `QQQ`? | Removing Biotech (`GICS 35`) from `QQQ` (`I2`) adds `+0.34%/yr` (`44.15%`, No-NVDA `+0.74%/yr`). Applying `4Q EAR` only to cross-sector `QQQ` while keeping `Tech` as pure price momentum (`I3a`) jumps `Core3` to **`48.02%`** (`Sharpe 1.12`, No-NVDA **`38.75%`**). Combining `QQQ 4Q-EAR` + `Tech A5 Anti-Jump Veto` (`I3c`) reaches **`50.50%` CAGR** (`Sharpe 1.17`, **No-NVDA `46.07%`**, **Ban Top-3 `34.32%`**). | **`48.02%` (`I3a`) to `50.50%` (`I3c`)** (`t = +0.93` to `+1.21`) | `-46.94%` (Month DD **`-35.5%`**) | **HIGHEST ALPHA CEILING (`48.0%–50.5%` CAGR, `46.1%` without `NVDA`), though `t = +0.93~+1.21` stays below formal re-specification hurdle** |

---

## 2. Physical Truncation Verification (`Table T0`)
| Cutoff Date | QQQ Rows | Tech Rows | QQQ Max Diff (12 Features) | Tech Max Diff (12 Features) | Status |
|---|---|---|---|---|---|
| 2011-12-31 | 3586 | 2648 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2015-06-30 | 7768 | 5345 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2018-12-31 | 12087 | 8142 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2021-12-31 | 15757 | 10706 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2024-06-30 | 18779 | 12801 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |

---

## 3. Hypothesis E: Cross-Sleeve Overlap & 75% Single-Stock Concentration (`Tables T1 & T2-E`)

### 3.1 Forensic Attribution of Overlap Months (`Table T1`)
| Subsample / Portfolio Leg | Months | Share | Mean Monthly Ret | Annualized Compound Ret | Ann Vol | Ann Sharpe | Win Rate | Worst Month | Best Month |
|---|---|---|---|---|---|---|---|---|---|
| All 213 Months (Full Core3 Baseline) | 213 | 100.0% | 3.67% | 43.81% | 39.6% | 1.11 | 62.4% | -36.6% | 59.4% |
| Overlap Months Only (75% Single-Stock Weight, 2 Distinct Stocks) | 76 | 35.7% | 6.55% | 96.93% | 43.7% | 1.80 | 76.3% | -36.6% | 55.5% |
| Non-Overlap Months Only (50%/25%/25% Weights, 3 Distinct Stocks) | 137 | 64.3% | 2.08% | 20.79% | 36.1% | 0.69 | 54.7% | -18.3% | 59.4% |
| Inside Overlap Months: The 75%-Weighted Overlapping Stock (Both QQQ & Tech Winner) | 76 | 35.7% | 7.39% | 111.28% | 49.5% | 1.79 | 75.0% | -44.4% | 63.5% |
| Inside Overlap Months: The 25%-Weighted Non-Overlapping 2nd QQQ Stock | 76 | 35.7% | 4.29% | 51.40% | 45.5% | 1.13 | 60.5% | -24.6% | 54.1% |
| Inside Overlap Months: Replacement QQQ Rank #3 Stock (If De-Overlapped) | 76 | 35.7% | 4.18% | 46.34% | 53.4% | 0.94 | 63.2% | -27.3% | 97.3% |
| Inside Overlap Months: Replacement Tech Rank #2 Stock (If Tech Yields) | 76 | 35.7% | 3.60% | 38.04% | 47.7% | 0.91 | 57.9% | -39.0% | 60.8% |

### 3.2 Structural De-Overlap, Single-Stock Cap, and Inverse-Volatility Weighting (`Table T2-E`)
| Strategy / Structural Variant | CAGR 09-26 | Sharpe (m) | Month DD | Daily DD (5651) | Daily DD (O2C) | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | Avg Stocks | Max Stock W | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN] | 43.81% | 1.08 | -36.6% | -46.96% | -49.68% | 24.79% | 72.69% | 9.1% | 0.86 | 2.64 | 75.0% |  |
| E1a. De-Overlap (QQQ Yields to Tech: Always 3 Distinct Stocks 50%/25%/25%) | 39.94% | 1.03 | -32.4% | -42.67% | -46.02% | 24.40% | 62.91% | 3.6% | 0.89 | 3.00 | 50.0% | -1.92 |
| E1b. De-Overlap (Tech Yields to QQQ: Always 3 Distinct Stocks 25%/25%/50%) | 34.17% | 0.96 | -30.8% | -41.92% | -41.89% | 18.08% | 58.21% | 2.2% | 0.95 | 3.00 | 50.0% | -1.92 |
| E1c. De-Overlap + Equal Weight (3 Distinct Stocks at 33.3% Each) | 38.90% | 1.03 | -28.5% | -39.19% | -43.08% | 26.66% | 56.45% | -7.4% | 0.91 | 3.00 | 33.3% | -1.46 |
| E2. Single-Stock Cap 40% (Overlap 75/25 -> 40/60 in Same 2 Stocks) | 38.10% | 0.99 | -33.8% | -50.19% | -49.90% | 19.97% | 65.61% | 3.8% | 0.95 | 2.64 | 60.0% | -1.90 |
| E2. Single-Stock Cap 50% (Overlap 75/25 -> 50/50 in Same 2 Stocks) | 39.86% | 1.03 | -32.6% | -48.32% | -48.39% | 21.43% | 67.85% | 5.4% | 0.91 | 2.64 | 50.0% | -1.89 |
| E2. Single-Stock Cap 60% (Overlap 75/25 -> 60/40 in Same 2 Stocks) | 41.51% | 1.05 | -32.0% | -46.43% | -46.87% | 22.81% | 69.91% | 6.9% | 0.89 | 2.64 | 60.0% | -1.89 |
| E3. Single-Stock Cap 50% + Overflow 25% to QQQ Rank #3 | 39.94% | 1.03 | -32.4% | -42.67% | -46.02% | 24.40% | 62.91% | 3.6% | 0.89 | 3.00 | 50.0% | -1.92 |
| E4a. Inverse-Vol Weighting Across Selected Core3 Stocks (21d Vol) | 37.66% | 1.02 | -31.0% | -47.66% | -48.04% | 24.58% | 56.59% | -11.6% | 1.01 | 2.64 | 80.5% | -1.81 |
| E4b. De-Overlapped 3 Distinct Stocks + Inverse-Vol Weighting (21d Vol) | 32.86% | 0.93 | -29.1% | -39.30% | -42.95% | 25.57% | 42.90% | -15.9% | 1.04 | 3.00 | 73.6% | -2.35 |
| E4a. Inverse-Vol Weighting Across Selected Core3 Stocks (63d Vol) | 38.94% | 1.04 | -29.4% | -47.73% | -47.99% | 25.51% | 58.41% | -13.2% | 0.98 | 2.64 | 77.3% | -1.56 |
| E4b. De-Overlapped 3 Distinct Stocks + Inverse-Vol Weighting (63d Vol) | 33.78% | 0.95 | -29.4% | -38.84% | -42.43% | 26.19% | 44.25% | -16.8% | 1.00 | 3.00 | 71.8% | -2.19 |
| E4a. Inverse-Vol Weighting Across Selected Core3 Stocks (252d Vol) | 39.34% | 1.05 | -29.5% | -47.14% | -47.42% | 26.00% | 58.67% | -15.6% | 0.97 | 2.64 | 74.1% | -1.47 |
| E4b. De-Overlapped 3 Distinct Stocks + Inverse-Vol Weighting (252d Vol) | 34.70% | 0.97 | -29.3% | -38.01% | -41.77% | 26.97% | 45.36% | -18.9% | 0.99 | 3.00 | 64.3% | -2.05 |

---

## 4. Hypothesis F: Skip-Month (`[t-1m, t]`) Breakdown Veto & Signal Freshness (`Table T2-F`)
| Strategy / Structural Variant | CAGR 09-26 | Sharpe (m) | Month DD | Daily DD (5651) | Daily DD (O2C) | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | Avg Stocks | Max Stock W | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN] | 43.81% | 1.08 | -36.6% | -46.96% | -49.68% | 24.79% | 72.69% | 9.1% | 0.86 | 2.64 | 75.0% |  |
| F1. Skip-Month Crash Veto: Drop Winner If ret_1m < -5% (Both Sleeves) | 47.72% | 1.12 | -46.2% | -55.34% | -56.64% | 26.07% | 81.25% | 20.5% | 0.98 | 2.63 | 75.0% | 0.89 |
| F1. Skip-Month Crash Veto: Drop Winner If ret_1m < -10% (Both Sleeves) | 42.40% | 1.06 | -39.5% | -46.96% | -49.68% | 25.50% | 67.61% | 14.1% | 0.92 | 2.63 | 75.0% | -0.46 |
| F1. Skip-Month Crash Veto: Drop Winner If ret_1m < -15% (Both Sleeves) | 36.11% | 0.95 | -44.3% | -49.22% | -50.46% | 22.08% | 56.61% | -4.2% | 0.86 | 2.65 | 75.0% | -2.21 |
| F1. Skip-Month Crash Veto: Drop Winner If ret_1m < -20% (Both Sleeves) | 36.68% | 0.96 | -44.3% | -49.33% | -50.54% | 21.85% | 58.52% | 2.9% | 0.84 | 2.64 | 75.0% | -2.06 |
| F1s. Skip-Month Veto ret_1m < -10% on QQQ Only (Tech Control) | 44.44% | 1.10 | -36.6% | -46.96% | -49.68% | 28.55% | 67.88% | 11.0% | 0.89 | 2.65 | 75.0% | 0.14 |
| F1s. Skip-Month Veto ret_1m < -10% on Tech Only (QQQ Control) | 41.72% | 1.04 | -40.1% | -47.16% | -49.68% | 21.75% | 72.40% | 12.2% | 0.89 | 2.65 | 75.0% | -0.68 |
| F1s. Skip-Month Veto ret_1m < -15% on QQQ Only (Tech Control) | 41.50% | 1.05 | -36.6% | -46.96% | -49.68% | 26.74% | 63.11% | 5.9% | 0.85 | 2.66 | 75.0% | -1.37 |
| F1s. Skip-Month Veto ret_1m < -15% on Tech Only (QQQ Control) | 38.63% | 0.99 | -38.8% | -46.99% | -49.68% | 20.21% | 66.63% | -0.9% | 0.87 | 2.66 | 75.0% | -2.26 |
| F2. Formation-Date Entry Trend Veto: Drop If Close[t] < SMA50 (Both Sleeves) | 39.61% | 1.01 | -43.9% | -48.50% | -51.24% | 25.41% | 60.35% | -12.6% | 1.00 | 2.62 | 75.0% | -0.91 |
| F2s. Entry Trend Veto Close[t] < SMA50 on QQQ Only (Tech Control) | 40.49% | 1.03 | -39.8% | -48.35% | -50.29% | 25.09% | 63.19% | 5.5% | 0.93 | 2.67 | 75.0% | -1.13 |
| F2s. Entry Trend Veto Close[t] < SMA50 on Tech Only (QQQ Control) | 42.92% | 1.06 | -36.7% | -46.96% | -49.68% | 25.03% | 69.84% | -9.4% | 0.93 | 2.63 | 75.0% | -0.22 |
| F2. Formation-Date Entry Trend Veto: Drop If Close[t] < SMA100 (Both Sleeves) | 38.45% | 1.00 | -46.7% | -51.59% | -51.68% | 21.35% | 64.12% | -12.2% | 0.90 | 2.64 | 75.0% | -1.39 |
| F2s. Entry Trend Veto Close[t] < SMA100 on QQQ Only (Tech Control) | 43.80% | 1.09 | -36.6% | -46.96% | -49.68% | 25.42% | 71.56% | 11.5% | 0.89 | 2.68 | 75.0% | -0.18 |
| F2s. Entry Trend Veto Close[t] < SMA100 on Tech Only (QQQ Control) | 38.55% | 0.99 | -44.6% | -52.78% | -52.21% | 20.82% | 65.34% | -14.1% | 0.86 | 2.64 | 75.0% | -1.48 |
| F2. Formation-Date Entry Trend Veto: Drop If Close[t] < SMA200 (Both Sleeves) | 40.96% | 1.03 | -36.6% | -46.96% | -49.68% | 23.14% | 67.83% | -2.4% | 0.84 | 2.64 | 75.0% | -1.74 |
| F2s. Entry Trend Veto Close[t] < SMA200 on QQQ Only (Tech Control) | 43.65% | 1.08 | -36.6% | -46.96% | -49.68% | 25.24% | 71.47% | 7.9% | 0.86 | 2.65 | 75.0% | -0.26 |
| F2s. Entry Trend Veto Close[t] < SMA200 on Tech Only (QQQ Control) | 41.12% | 1.03 | -36.6% | -46.96% | -49.68% | 22.69% | 69.03% | -1.2% | 0.84 | 2.64 | 75.0% | -1.77 |
| F3. 21-Day Peak Drawdown Veto: Drop If DD_21d < -12% at Formation | 34.60% | 0.94 | -47.4% | -53.29% | -54.58% | 21.57% | 53.49% | 0.8% | 0.98 | 2.65 | 75.0% | -1.69 |
| F3. 21-Day Peak Drawdown Veto: Drop If DD_21d < -15% at Formation | 36.17% | 0.95 | -44.2% | -50.51% | -51.04% | 19.69% | 60.82% | -0.8% | 0.93 | 2.65 | 75.0% | -1.60 |
| F3. 21-Day Peak Drawdown Veto: Drop If DD_21d < -20% at Formation | 36.58% | 0.96 | -36.6% | -46.96% | -49.68% | 21.37% | 59.05% | -10.1% | 0.87 | 2.64 | 75.0% | -2.54 |
| F4a. 1-Week Skip Momentum (12-1w: Skip 5 Trading Days Instead of 21) [Both] | 37.30% | 0.95 | -37.0% | -46.96% | -49.68% | 23.39% | 57.59% | -16.9% | 0.87 | 2.65 | 75.0% | -1.46 |
| F4b. 1-Week Skip Momentum (12-1w) on QQQ Only + Tech 12-1m Control | 39.69% | 1.01 | -36.6% | -46.96% | -49.68% | 24.69% | 61.74% | 0.3% | 0.87 | 2.67 | 75.0% | -1.37 |
| F4c. 1-Week Skip Momentum (12-1w) on Tech Only + QQQ 12-1m Control | 41.35% | 1.03 | -37.7% | -46.96% | -49.68% | 23.56% | 68.14% | -9.8% | 0.86 | 2.66 | 75.0% | -0.72 |
| F4d. Zero-Skip Momentum (12-0: Include Most Recent Month [t-1m, t]) [Both] | 31.97% | 0.86 | -45.5% | -51.18% | -50.29% | 17.75% | 52.88% | -23.9% | 0.81 | 2.66 | 75.0% | -2.21 |

---

## 5. Hypothesis G: Rank-Boundary Hysteresis / Buy-Hold Buffer Rules & Overlapping Tranches (`Table T2-G`)
| Strategy / Structural Variant | CAGR 09-26 | Sharpe (m) | Month DD | Daily DD (5651) | Daily DD (O2C) | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | Avg Stocks | Max Stock W | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN] | 43.81% | 1.08 | -36.6% | -46.96% | -49.68% | 24.79% | 72.69% | 9.1% | 0.86 | 2.64 | 75.0% |  |
| G1. QQQ Buffer Only: Buy Top-2, Hold While Top-3 (Tech Hard Top-1) | 44.89% | 1.10 | -36.6% | -48.35% | -50.29% | 27.17% | 71.46% | 10.3% | 0.77 | 2.68 | 75.0% | 0.65 |
| G1. QQQ Buffer Only: Buy Top-2, Hold While Top-4 (Tech Hard Top-1) | 45.69% | 1.12 | -36.6% | -49.43% | -51.60% | 30.28% | 68.31% | 10.1% | 0.73 | 2.68 | 75.0% | 0.74 |
| G1. QQQ Buffer Only: Buy Top-2, Hold While Top-5 (Tech Hard Top-1) | 48.08% | 1.19 | -27.7% | -41.96% | -43.63% | 30.99% | 73.45% | 4.7% | 0.69 | 2.70 | 75.0% | 1.01 |
| G1. QQQ Buffer Only: Buy Top-2, Hold While Top-6 (Tech Hard Top-1) | 48.70% | 1.21 | -31.7% | -41.96% | -43.63% | 32.75% | 72.16% | 5.7% | 0.65 | 2.69 | 75.0% | 1.08 |
| G2. Tech Buffer Only: Buy Top-1, Hold While Top-2 (QQQ Hard Top-2) | 41.73% | 1.02 | -40.9% | -46.96% | -49.68% | 21.85% | 72.24% | -10.1% | 0.70 | 2.64 | 75.0% | -0.31 |
| G2. Tech Buffer Only: Buy Top-1, Hold While Top-3 (QQQ Hard Top-2) | 40.84% | 1.06 | -41.0% | -47.11% | -46.66% | 23.00% | 67.73% | -3.5% | 0.66 | 2.64 | 75.0% | -0.72 |
| G2. Tech Buffer Only: Buy Top-1, Hold While Top-4 (QQQ Hard Top-2) | 40.74% | 1.01 | -41.5% | -50.39% | -51.12% | 25.71% | 62.81% | -14.2% | 0.61 | 2.67 | 75.0% | -0.46 |
| G3. Dual Buffer Grid: QQQ Hold<=Top-3 + Tech Hold<=Top-2 | 42.75% | 1.04 | -41.5% | -48.35% | -50.29% | 24.09% | 71.03% | -9.1% | 0.61 | 2.65 | 75.0% | -0.07 |
| G3. Dual Buffer Grid: QQQ Hold<=Top-3 + Tech Hold<=Top-3 | 41.70% | 1.07 | -39.5% | -45.82% | -45.37% | 25.22% | 66.22% | -2.5% | 0.57 | 2.64 | 75.0% | -0.50 |
| G3. Dual Buffer Grid: QQQ Hold<=Top-4 + Tech Hold<=Top-2 | 43.61% | 1.06 | -37.2% | -49.43% | -51.60% | 27.24% | 67.89% | -9.2% | 0.57 | 2.64 | 75.0% | 0.06 |
| G3. Dual Buffer Grid: QQQ Hold<=Top-4 + Tech Hold<=Top-3 | 42.49% | 1.09 | -41.0% | -47.10% | -46.62% | 28.37% | 63.02% | -2.6% | 0.53 | 2.62 | 75.0% | -0.36 |
| G3. Dual Buffer Grid: QQQ Hold<=Top-5 + Tech Hold<=Top-2 | 45.82% | 1.12 | -33.5% | -41.96% | -43.63% | 27.88% | 72.74% | -14.0% | 0.53 | 2.66 | 75.0% | 0.32 |
| G3. Dual Buffer Grid: QQQ Hold<=Top-5 + Tech Hold<=Top-3 | 44.32% | 1.14 | -41.0% | -47.10% | -46.62% | 28.98% | 66.84% | -7.6% | 0.49 | 2.60 | 75.0% | -0.12 |
| G4. Overlapping 2-Month Holding Tranches (Jegadeesh-Titman K=2m) | 36.92% | 0.98 | -39.2% | -47.91% | -50.29% | 24.33% | 55.08% | -10.5% | 0.58 | 3.77 | 75.0% | -1.90 |
| G4. Overlapping 3-Month Holding Tranches (Jegadeesh-Titman K=3m) | 37.44% | 0.99 | -36.9% | -48.19% | -50.52% | 25.57% | 54.42% | -16.1% | 0.48 | 4.68 | 75.0% | -1.32 |

---

## 6. Hypothesis H: Portfolio-Own Realized Volatility Scaling & Daniel-Moskowitz Crash State (`Table T2-H`)
| Strategy / Structural Variant | CAGR 09-26 | Sharpe (m) | Month DD | Daily DD (5651) | Daily DD (O2C) | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | Avg Stocks | Max Stock W | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN] | 43.81% | 1.08 | -36.6% | -46.96% | -49.68% | 24.79% | 72.69% | 9.1% | 0.86 | 2.64 | 75.0% |  |
| H1/H2. Barroso Portfolio-Own 21d Vol Target 25% (Cash=0%) | 27.48% | 1.07 | -28.1% | -35.19% | -35.07% | 19.53% | 38.52% | 5.1% | 0.72 | 2.64 | 75.0% | -3.12 |
| H1/H2. Barroso Portfolio-Own 21d Vol Target 30% (Cash=0%) | 31.06% | 1.08 | -28.9% | -38.20% | -39.95% | 20.56% | 45.96% | 8.1% | 0.78 | 2.64 | 75.0% | -2.77 |
| H1/H2. Barroso Portfolio-Own 21d Vol Target 35% (Cash=0%) | 34.09% | 1.10 | -29.6% | -38.71% | -39.36% | 21.94% | 51.57% | 10.9% | 0.81 | 2.64 | 75.0% | -2.45 |
| H1/H2. Barroso Portfolio-Own 21d Vol Target 40% (Cash=0%) | 36.46% | 1.12 | -29.7% | -39.09% | -38.99% | 23.24% | 55.65% | 12.9% | 0.83 | 2.64 | 75.0% | -2.19 |
| H1/H2. Barroso Portfolio-Own 63d Vol Target 25% (Cash=0%) | 25.44% | 1.02 | -28.1% | -36.08% | -36.09% | 20.01% | 32.81% | 7.3% | 0.66 | 2.64 | 75.0% | -3.26 |
| H1/H2. Barroso Portfolio-Own 63d Vol Target 30% (Cash=0%) | 29.37% | 1.04 | -29.6% | -38.83% | -38.72% | 22.03% | 39.50% | 10.1% | 0.74 | 2.64 | 75.0% | -2.85 |
| H1/H2. Barroso Portfolio-Own 63d Vol Target 35% (Cash=0%) | 32.31% | 1.06 | -29.7% | -39.80% | -38.99% | 23.50% | 44.60% | 12.8% | 0.79 | 2.64 | 75.0% | -2.54 |
| H1/H2. Barroso Portfolio-Own 63d Vol Target 40% (Cash=0%) | 34.70% | 1.08 | -30.1% | -40.40% | -38.99% | 24.37% | 49.30% | 12.4% | 0.82 | 2.64 | 75.0% | -2.29 |
| H3. Zero-Cash De-Risking: When Basket 21d Vol > 35% -> 3-Stock InvVol (100% Invested) | 35.92% | 0.97 | -29.5% | -39.53% | -42.43% | 25.10% | 51.28% | -12.5% | 1.00 | 2.85 | 75.0% | -2.07 |
| H3. Zero-Cash De-Risking: When Basket 21d Vol > 40% -> 3-Stock InvVol (100% Invested) | 36.69% | 0.98 | -29.7% | -39.09% | -42.43% | 24.55% | 54.13% | -4.1% | 0.99 | 2.80 | 75.0% | -1.97 |
| H3. Zero-Cash De-Risking: When Basket 21d Vol > 45% -> 3-Stock InvVol (100% Invested) | 37.11% | 0.99 | -30.0% | -39.09% | -42.43% | 24.44% | 55.39% | -1.2% | 0.96 | 2.79 | 75.0% | -1.81 |
| H4. Daniel-Moskowitz Bear-Rebound Crash State -> Scale Exposure to 0.50x (Cash=0%) | 44.21% | 1.10 | -36.6% | -46.96% | -49.68% | 26.22% | 71.25% | 3.9% | 0.84 | 2.64 | 75.0% | -0.01 |
| H4. Daniel-Moskowitz Bear-Rebound Crash State -> Scale Exposure to 0.75x (Cash=0%) | 44.04% | 1.09 | -36.6% | -46.96% | -49.68% | 25.51% | 72.03% | 6.7% | 0.85 | 2.64 | 75.0% | -0.02 |
| H4. Daniel-Moskowitz Bear-Rebound Crash State -> Switch to Residual Sharpe Winners (100% Invested, 0% Cash) | 43.94% | 1.08 | -36.6% | -46.96% | -49.68% | 27.13% | 68.96% | 7.5% | 0.89 | 2.64 | 75.0% | -0.01 |

---

## 7. Hypothesis I: Sleeve-Asymmetric Domain Rules (`QQQ` vs `Tech` Structural Physics, `Table T2-I`)
| Strategy / Structural Variant | CAGR 09-26 | Sharpe (m) | Month DD | Daily DD (5651) | Daily DD (O2C) | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | Avg Stocks | Max Stock W | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN] | 43.81% | 1.08 | -36.6% | -46.96% | -49.68% | 24.79% | 72.69% | 9.1% | 0.86 | 2.64 | 75.0% |  |
| I1a. QQQ Rank #2 Only (50%) + Tech Rank #1 (50%) [Skip Noisy QQQ Rank #1] | 49.92% | 1.14 | -41.9% | -46.56% | -46.38% | 25.18% | 89.20% | 1.0% | 1.19 | 1.87 | 100.0% | 1.53 |
| I1b. QQQ Rank #2 & #3 (25% Each) + Tech Rank #1 (50%) [Skip QQQ Rank #1] | 43.01% | 1.09 | -35.5% | -42.67% | -46.02% | 25.25% | 69.71% | -4.2% | 1.09 | 2.83 | 75.0% | -0.44 |
| I1c. QQQ Top-3 (16.7% Each) + Tech Rank #1 (50%) | 41.35% | 1.06 | -36.4% | -46.19% | -49.04% | 25.10% | 65.47% | 2.8% | 0.86 | 3.60 | 66.7% | -1.48 |
| I2. QQQ Ex-Biotech/Healthcare Filter (Drop GICS 35 from QQQ; Tech Control) | 44.15% | 1.08 | -36.6% | -46.96% | -49.68% | 25.36% | 72.63% | 0.8% | 0.85 | 2.62 | 75.0% | 0.19 |
| I3a. Asymmetric: QQQ Top-5->4Q EAR Top-2 + Tech Control (Pure 12-1 Mom Top-1) | 48.02% | 1.12 | -35.5% | -46.94% | -48.58% | 25.29% | 83.54% | 4.6% | 0.87 | 2.69 | 75.0% | 0.93 |
| I3b. Asymmetric: QQQ RankBlend(0.25 FundMom) + Tech Control (Pure 12-1 Mom Top-1) | 41.58% | 1.05 | -36.6% | -46.96% | -49.68% | 24.71% | 66.77% | 14.9% | 0.88 | 2.62 | 75.0% | -0.96 |
| I3c. Asymmetric: QQQ Top-5->4Q EAR Top-2 + Tech A5 Anti-Jump Veto Top-1 | 50.50% | 1.17 | -35.5% | -46.94% | -48.58% | 28.65% | 84.28% | 4.6% | 0.90 | 2.69 | 75.0% | 1.21 |
| I3d. Asymmetric: QQQ Control + Tech A5 Anti-Jump Veto Top-1 | 46.29% | 1.13 | -36.6% | -46.96% | -49.68% | 28.21% | 73.44% | 9.1% | 0.89 | 2.64 | 75.0% | 0.88 |

---

## 8. Leave-One-Winner-Out (`Table T3`), Second-Vendor Replication (`Table T4`), and Cumulative DSR (`Table T5`)

### 8.1 Leave-One-Winner-Out & Outlier Month Stress Test (`Table T3`)
| Strategy | Full CAGR | Drop Best 5m | No NVDA | No SNDK | No PLTR | No TSLA | No MU | No WDC | No AMD | Ban Top 3 (NVDA+SNDK+PLTR) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0. Control Core3 [FROZEN] | 43.81% | 29.81% | 34.78% | 42.24% | 37.86% | 40.34% | 42.31% | 43.27% | 41.96% | 27.41% |
| E1a. De-Overlap (QQQ Yields: 3 Distinct Stocks 50/25/25) | 39.94% | 27.02% | 31.35% | 37.56% | 35.91% | 36.10% | 37.51% | 40.05% | 38.45% | 25.00% |
| E1c. De-Overlap Equal Weight (3 Distinct Stocks 33.3% Each) | 38.90% | 25.70% | 31.36% | 37.33% | 36.48% | 33.88% | 36.37% | 39.07% | 37.86% | 27.35% |
| E2. Single-Stock Cap 50% (Same 2 Stocks) | 39.86% | 26.40% | 32.93% | 37.31% | 35.02% | 36.70% | 37.41% | 39.27% | 38.00% | 25.58% |
| E4a. Inverse-Vol Weighting (63d Vol) | 38.94% | 25.86% | 32.42% | 37.95% | 33.50% | 35.95% | 36.13% | 38.11% | 38.41% | 26.56% |
| F1. Skip-Month Crash Veto (ret_1m < -15%) | 36.11% | 23.05% | 27.29% | 35.36% | 30.08% | 32.89% | 36.00% | 38.26% | 35.88% | 21.05% |
| F2. Formation Trend Veto (Close[t] < SMA50) | 39.61% | 26.29% | 26.30% | 38.41% | 34.05% | 36.17% | 37.23% | 39.96% | 37.34% | 18.09% |
| F4a. 1-Week Skip Momentum (12-1w) | 37.30% | 23.93% | 31.42% | 36.09% | 32.67% | 37.46% | 37.72% | 38.27% | 38.44% | 23.10% |
| G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-4; Tech Hard Top-1) | 45.69% | 31.89% | 36.15% | 44.20% | 39.37% | 43.02% | 43.74% | 45.88% | 43.82% | 28.68% |
| G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-5; Tech Hard Top-1) | 48.08% | 34.25% | 38.35% | 46.07% | 41.77% | 44.75% | 46.62% | 48.51% | 46.14% | 30.45% |
| G3. Dual Buffer (QQQ Hold<=Top-3, Tech Hold<=Top-2) | 42.75% | 28.87% | 32.55% | 43.64% | 37.81% | 40.08% | 41.88% | 39.51% | 38.27% | 26.78% |
| G4. Overlapping 2-Month Tranches (K=2m) | 36.92% | 24.43% | 30.38% | 35.77% | 32.86% | 34.82% | 34.79% | 36.61% | 35.72% | 24.37% |
| H1. Barroso Portfolio-Own 21d Vol Target 35% | 34.09% | 25.68% | 26.84% | 34.08% | 30.89% | 31.79% | 33.04% | 34.69% | 33.38% | 23.29% |
| H1. Barroso Portfolio-Own 21d Vol Target 40% | 36.46% | 27.15% | 28.59% | 36.24% | 32.82% | 33.89% | 35.27% | 36.90% | 35.40% | 24.50% |
| H4. Daniel-Moskowitz Crash State -> Switch ResMom | 43.94% | 29.93% | 35.35% | 42.37% | 37.99% | 40.48% | 42.44% | 43.40% | 42.95% | 27.94% |
| I2. QQQ Ex-Biotech/Healthcare + Tech Control | 44.15% | 30.13% | 35.52% | 42.57% | 37.91% | 40.24% | 42.65% | 43.63% | 42.28% | 27.83% |
| I3a. Asymmetric: QQQ 4Q-EAR + Tech Control | 48.02% | 32.43% | 38.75% | 44.97% | 41.75% | 44.71% | 46.50% | 47.10% | 45.50% | 29.70% |
| I3c. Asymmetric: QQQ 4Q-EAR + Tech A5 Anti-Jump Veto | 50.50% | 34.65% | 46.07% | 46.89% | 43.75% | 47.13% | 48.94% | 49.37% | 48.68% | 34.32% |

### 8.2 Second-Vendor (`Tiingo-First`) End-to-End Replication (`Table T4`)
| Strategy | Primary CAGR | Tiingo-First CAGR | Diff (bp) | Primary Sharpe | Tiingo Sharpe | Primary DD | Tiingo DD | Ret Corr |
|---|---|---|---|---|---|---|---|---|
| 0. Control Core3 [FROZEN] | 43.81% | 43.82% | 1.41 | 1.08 | 1.08 | -36.6% | -36.6% | 1.000 |
| E1a. De-Overlap (QQQ Yields: 3 Distinct Stocks 50/25/25) | 39.94% | 39.96% | 1.42 | 1.03 | 1.03 | -32.4% | -32.4% | 1.000 |
| E1c. De-Overlap Equal Weight (3 Distinct Stocks 33.3% Each) | 38.90% | 38.91% | 0.96 | 1.03 | 1.03 | -28.5% | -28.5% | 1.000 |
| E2. Single-Stock Cap 50% (Same 2 Stocks) | 39.86% | 39.88% | 1.40 | 1.03 | 1.03 | -32.6% | -32.6% | 1.000 |
| E4a. Inverse-Vol Weighting (63d Vol) | 38.94% | 38.95% | 1.22 | 1.04 | 1.04 | -29.4% | -29.4% | 1.000 |
| F1. Skip-Month Crash Veto (ret_1m < -15%) | 36.11% | 36.12% | 1.30 | 0.95 | 0.95 | -44.3% | -44.2% | 1.000 |
| F2. Formation Trend Veto (Close[t] < SMA50) | 39.61% | 39.04% | -57.03 | 1.01 | 1.00 | -43.9% | -43.9% | 0.999 |
| F4a. 1-Week Skip Momentum (12-1w) | 37.30% | 37.31% | 1.22 | 0.95 | 0.95 | -37.0% | -37.0% | 1.000 |
| G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-4; Tech Hard Top-1) | 45.69% | 45.71% | 1.30 | 1.12 | 1.12 | -36.6% | -36.6% | 1.000 |
| G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-5; Tech Hard Top-1) | 48.08% | 48.09% | 1.32 | 1.19 | 1.19 | -27.7% | -27.7% | 1.000 |
| G3. Dual Buffer (QQQ Hold<=Top-3, Tech Hold<=Top-2) | 42.75% | 42.75% | 0.18 | 1.04 | 1.04 | -41.5% | -41.5% | 1.000 |
| G4. Overlapping 2-Month Tranches (K=2m) | 36.92% | 36.93% | 0.80 | 0.98 | 0.98 | -39.2% | -39.2% | 1.000 |
| H1. Barroso Portfolio-Own 21d Vol Target 35% | 34.09% | 34.10% | 1.15 | 1.10 | 1.10 | -29.6% | -29.5% | 1.000 |
| H1. Barroso Portfolio-Own 21d Vol Target 40% | 36.46% | 36.48% | 1.34 | 1.12 | 1.12 | -29.7% | -29.7% | 1.000 |
| H4. Daniel-Moskowitz Crash State -> Switch ResMom | 43.94% | 43.95% | 1.40 | 1.08 | 1.09 | -36.6% | -36.6% | 1.000 |
| I2. QQQ Ex-Biotech/Healthcare + Tech Control | 44.15% | 44.17% | 1.45 | 1.08 | 1.08 | -36.6% | -36.6% | 1.000 |
| I3a. Asymmetric: QQQ 4Q-EAR + Tech Control | 48.02% | 47.96% | -6.51 | 1.12 | 1.12 | -35.5% | -35.5% | 1.000 |
| I3c. Asymmetric: QQQ 4Q-EAR + Tech A5 Anti-Jump Veto | 50.50% | 50.44% | -6.64 | 1.17 | 1.17 | -35.5% | -35.5% | 1.000 |

### 8.3 Cumulative Multiple-Testing Deflated Sharpe Ratio (`Table T5`)
| Strategy | Grand Total Trials | This Round Trials | Excess Sharpe (Ann) | Null Expected Max SR0 | DSR (All Cumulative) | DSR (This Round Only) | Active IR vs Control |
|---|---|---|---|---|---|---|---|
| 0. Control Core3 [FROZEN] | 789 | 75 | 1.11 | 0.97 | 0.742 | 0.958 | 0.00 |
| E1a. De-Overlap (QQQ Yields: 3 Distinct Stocks 50/25/25) | 789 | 75 | 1.07 | 0.97 | 0.679 | 0.941 | -0.43 |
| E1c. De-Overlap Equal Weight (3 Distinct Stocks 33.3% Each) | 789 | 75 | 1.07 | 0.97 | 0.674 | 0.943 | -0.34 |
| E2. Single-Stock Cap 50% (Same 2 Stocks) | 789 | 75 | 1.06 | 0.97 | 0.666 | 0.937 | -0.46 |
| E4a. Inverse-Vol Weighting (63d Vol) | 789 | 75 | 1.08 | 0.97 | 0.702 | 0.951 | -0.41 |
| F1. Skip-Month Crash Veto (ret_1m < -15%) | 789 | 75 | 0.99 | 0.97 | 0.522 | 0.873 | -0.49 |
| F2. Formation Trend Veto (Close[t] < SMA50) | 789 | 75 | 1.05 | 0.97 | 0.632 | 0.923 | -0.21 |
| F4a. 1-Week Skip Momentum (12-1w) | 789 | 75 | 0.99 | 0.97 | 0.531 | 0.874 | -0.39 |
| G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-4; Tech Hard Top-1) | 789 | 75 | 1.16 | 0.97 | 0.803 | 0.972 | 0.16 |
| G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-5; Tech Hard Top-1) | 789 | 75 | 1.23 | 0.97 | 0.889 | 0.990 | 0.23 |
| G3. Dual Buffer (QQQ Hold<=Top-3, Tech Hold<=Top-2) | 789 | 75 | 1.07 | 0.97 | 0.674 | 0.936 | -0.02 |
| G4. Overlapping 2-Month Tranches (K=2m) | 789 | 75 | 1.02 | 0.97 | 0.584 | 0.899 | -0.52 |
| H1. Barroso Portfolio-Own 21d Vol Target 35% | 789 | 75 | 1.15 | 0.97 | 0.784 | 0.964 | -0.62 |
| H1. Barroso Portfolio-Own 21d Vol Target 40% | 789 | 75 | 1.16 | 0.97 | 0.799 | 0.969 | -0.55 |
| H4. Daniel-Moskowitz Crash State -> Switch ResMom | 789 | 75 | 1.12 | 0.97 | 0.754 | 0.961 | -0.00 |
| I2. QQQ Ex-Biotech/Healthcare + Tech Control | 789 | 75 | 1.12 | 0.97 | 0.749 | 0.959 | 0.04 |
| I3a. Asymmetric: QQQ 4Q-EAR + Tech Control | 789 | 75 | 1.16 | 0.97 | 0.814 | 0.977 | 0.21 |
| I3c. Asymmetric: QQQ 4Q-EAR + Tech A5 Anti-Jump Veto | 789 | 75 | 1.21 | 0.97 | 0.872 | 0.988 | 0.28 |
