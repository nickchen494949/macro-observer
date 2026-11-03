# Core3 Stock-Selection Layer Forensic Audit Report
**Hypotheses A (Momentum Consistency / FIP), B (Residual Momentum), C (Price + Fundamental / Earnings Momentum), and D (52-Week-High Proximity)**

- **Date**: 2026-11-03
- **Reference Commit**: `fe1df50` / `5651ec2`
- **Baseline Control (`Core3` Frozen)**:
  - **50% `QQQ Sharpe-Momentum Top-2`** (`12-1 momentum / 12m daily vol`, Historical PIT Nasdaq-100)
  - **50% `Historical S&P 500 IT Tech 12-1 Momentum Top-1 [S1]`**
  - **Execution**: Month-end signal at $t$, `T+1 Open` entry/exit, `10 bp/side` transaction cost, `1.0x` unlevered (`Cash = 0%`).
- **Audit Protocol**:
  - **Strict Hypothesis Isolation**: Every hypothesis (`A`, `B`, `C`, `D`) is tested independently against the frozen `Core3` Control (`00`) without mixing or multi-factor soup.
  - **7-Step Verification per Hypothesis**:
    1. Control vs Single Isolated Hypothesis (`Sleeve 1 Only`, `Sleeve 2 Only`, `Both Sleeves`)
    2. Parameter Neighborhood Grid (`Pool size N`, `Lookback window`, `Weight w`, `Veto threshold`)
    3. Subperiod Decomposition (`2009–2018`, `2019–2026`, `2022 Bear Market`)
    4. Single-Rank Monotonicity Diagnostic (`Rank #1` vs `Rank #2` vs `Rank #3`)
    5. Leave-One-Winner-Out (`Ban NVDA`, `SNDK`, `PLTR`, `TSLA`, `MU`, `WDC`, `AMD`, `Ban Top-3`, and `Drop Best 5 Months`)
    6. Second-Vendor (`Tiingo-First`) End-to-End Replication
    7. Physical Truncation Look-Ahead Test (`5 Cutoffs x 15 Features`) + True Daily MaxDD + Multiple-Testing DSR (`N = 714` cumulative trials)

---

## 1. Executive Summary & Headline Verdict

| Hypothesis Family | Academic Basis | Core3 CAGR (09–26) Across Variants | Best Variant vs Control (`43.75%`) | Solves Rank #1 vs #2 Anomaly? | Reduces True Daily MaxDD (`-46.76%`)? | Final Audit Verdict |
|---|---|---|---|---|---|---|
| **0. Frozen `Core3` Control** | Sharpe-Mom (`QQQ Top-2`) + Raw Mom (`Tech Top-1`) | **`43.75%`** (`43.85%` exact bridge) | Baseline (`Sharpe 1.08`) | Baseline (`QQQ R1 25.4% vs R2 54.5%`; `Tech R1 38.7% vs R2 9.7%`) | Baseline (`-46.76%` / `-49.68%` O2C) | **KEEP FROZEN AS PRIMARY BASELINE** |
| **A. Momentum Consistency / FIP (Pool Re-Rank `A1–A3`, `A6–A7`)** | Da, Gurun, Warachka (2014, *RFS*) — continuous daily gains | `15.44%` – `38.06%` | `-5.69%` to `-28.31%/yr` (`t = -1.31` to `-3.41`) | **NO** — demotes high-elasticity secular winners (`NVDA`, `PLTR`, `TSLA`) in favor of low-vol grinders (`AAPL`, `PAYX`, `ADP`) | No (`-41.7%` to `-55.7%`) | **FAIL (Pool Re-Ranking Destroys Alpha)** |
| **A5. FIP Extreme-Jump Veto (`Anti-Jump Veto`)** | Da et al. (2014) — veto only extreme lottery/spike winners (`FIP < 0` or `Top 5 days > 60%–65% of 12-1 gain`) | **`44.01%` – `47.06%`** (`30/31` grid cells beat Control; canonical `A5 = 46.79%`) | **`+3.04%/yr`** (`Sharpe 1.14`, `t = +1.07`; **No-NVDA `42.61%` vs `34.73%`**) | Partially in **Tech** (`Tech R1` rises `38.73% -> 44.03%`, DD `-67.0% -> -59.6%`); in **QQQ**, `R2` rises `54.45% -> 60.22%` | No (`-46.76%`) | **CONDITIONAL PASS (Only Surviving Filter; Statistically Insignificant `t = +1.07`)** |
| **B. Residual Momentum (`B1–B4`)** | Blitz, Huij, Martens (2011, *JEMP*) — OLS market/sector-hedged residuals | `30.92%` – `40.41%` | `-3.34%` to `-12.83%/yr` (`t = -0.98` to `-2.13`) | **YES in Tech (`R1 31.6% / R2 26.6% / R3 19.8%`, DD `-54.6%`)**, but at the cost of sacrificing `7.1%/yr` in `Tech R1` | No (`-46.76%` to `-57.6%`) | **FAIL for Top-1/Top-2 (Strips Out Sector-Wave Beta Amplification)** |
| **C. Price + Fundamental / Earnings Momentum (`C1–C5`)** | Novy-Marx (2015) & Chan et al. (1996) — PIT 8-K `EAR` + 10-Q/10-K `Rev/EPS` YoY & Accel | `19.52%` – `41.84%` (`QQQ Sleeve` reaches **`50.04%`** on `4Q EAR`!) | `-1.91%/yr` on `Core3` (`+6.29%/yr` on `QQQ Sleeve`, but `-10.65%/yr` on `Tech Sleeve`) | Helps `QQQ` (`4Q EAR` & `RankBlend 0.25`), **destroys `Tech Top-1`** (`38.73% -> 11.7%–28.1%`) | Worse (`-48.5%` to `-61.9%`) | **SPLIT: Works on `QQQ Top-2` (`4Q EAR`), FAILS on `Tech Top-1` (Lags Cyclical Semi Inflections)** |
| **D. 52-Week-High Proximity (`D1–D2`)** | George & Hwang (2004, *JF*) — `Close / High_252d` | `9.56%` – `40.71%` | `-3.04%` to `-34.19%/yr` (`t = -0.51` to `-3.85`) | **NO** — flips `Tech R1` (`4.89%`) below `Tech R2` (`38.39%`) | Worse (`-49.7%` to `-57.0%`) | **FAIL (Penalizes Normal High-Beta Pullbacks)** |

---

## 2. Structural Discovery: Why "Two-Stage Pool Re-Ranking" Fails While "Extreme Veto" Survives

Before examining individual hypotheses, Table `T2` (`Single-Rank Monotonicity Diagnostic`) reveals the **fundamental mathematical reason** why every standard two-stage pool re-ranking rule (`Take Top-5 in QQQ / Top-3 in Tech, then pick the best by Factor X`) degrades `Core3`:

1. **In `S&P 500 IT Tech` (`Sleeve 2`), Pure `12-1` Momentum Has an Extreme Winner-Take-All Cliff at Rank #1**:
   - `Tech Rank #1` net CAGR = **`38.73%`** (gross `40.06%`)
   - `Tech Rank #2` net CAGR = **`9.67%`**
   - `Tech Rank #3` net CAGR = **`8.84%`**
   - Because `Rank #1` outperforms `Rank #2` and `Rank #3` by **`+29.06%/yr`**, *any* secondary sort (`FIP_Smooth`, `Residual Momentum`, `Fundamental Momentum`, or `52W-High Proximity`) that overrides `Rank #1` in `50%–70%` of months and replaces it with `Rank #2` or `Rank #3` suffers an immediate **`10%–25%/yr` structural drag** unless the secondary factor has near-perfect foresight!
2. **In `QQQ` (`Sleeve 1`), `Sharpe-Momentum` (`mom_12_1 / vol_12_1`) Already Penalizes Volatility**:
   - In `Core3`, `Sleeve 1` does not use raw `12-1` return—it *already* divides `12-1` return by realized daily volatility (`vol_12_1`).
   - Adding a second smoothness or low-beta sort on top of `Sharpe-Momentum` **double-penalizes high-elasticity secular winners** (`NVDA`, `TSLA`, `AMD`, `NFLX`, `MRNA`) and forces the portfolio into slow, low-volatility defensive stocks (`ORCL`, `ADP`, `PAYX`, `AAPL`, `CSCO`).

---

## 3. Detailed Forensic Analysis by Hypothesis

### 3.1 Hypothesis A: Momentum Consistency / Frog in the Pan (Da, Gurun, Warachka 2014)
- **What Fails (`A1–A3`, `A6–A7`: Pool Re-Ranking by `FIP_Smooth`)**:
  - When we take the `Top-N` momentum candidates and select the ones with the highest `fip_smooth_12_1 = sign(mom_12_1) * (%pos - %neg)`, `Core3` CAGR collapses monotonically as the candidate pool widens:
    - Control (`Top-2 QQQ / Top-1 Tech`): **`43.75%`**
    - Pool `(3, 2)`: **`34.18%`** (`t = -1.31`)
    - Pool `(4, 2)`: **`30.39%`** (`t = -1.62`)
    - Pool `(5, 3)` (`A1c`): **`25.09%`** (`t = -2.23`)
    - Pool `(6, 3)`: **`21.57%`** (`t = -2.59`)
    - Pool `(8, 4)`: **`17.19%`** (`t = -3.14`)
    - Pool `(10, 5)`: **`15.44%`** (`t = -3.41`)
  - Similarly, `A4b (Non-Jump Momentum: 12-1 return excluding the 5 largest daily jumps)` drops `Core3` CAGR to **`32.67%`** (`t = -2.47`). Why? Because in concentrated large-cap Tech (`NDX` / `S&P 500 IT`), the biggest multi-year winners (`NVDA` in 2023–2024, `PLTR` in 2024, `AMD` in 2018–2020, `NFLX` in 2013–2015) experience massive **single-day post-earnings gap-ups** (`+15%` to `+25%` on 8-K release days). Removing the top 5 jump days treats genuine earnings-driven re-ratings as "bad jumps"!
- **What Works (`A5`: Anti-Jump / Extreme Discreteness Veto)**:
  - If instead of re-ranking slow stocks above fast stocks, we **keep the exact `Core3` ranking and ONLY veto a candidate when its `12-1` momentum is pathologically discrete**—specifically, when `fip_smooth_12_1 < 0` (it rose over 12 months despite having *more negative days than positive days*) OR `max_ret_5d_12_1 / mom_12_1 > 0.65` (more than `65%` of its entire 12-month gain came from just 5 trading days):
    - **`Core3` CAGR rises from `43.75%` to `46.79%` (`+3.04%/yr`)**, Monthly Sharpe rises from `1.08` to **`1.14`**, `QQQ Sleeve` rises from `43.75%` to **`44.77%`**, and `Tech Sleeve` rises from `38.73%` to **`44.03%`**.
    - Both subperiods improve: `2009–2018` rises from `24.79%` to **`28.13%`** (`+3.34%/yr`), and `2019–2026` rises from `72.53%` to **`74.95%`** (`+2.42%/yr`).
    - **Leave-One-Winner-Out Proof (`Table T3`)**: When `NVDA` is completely banned from the universe, Control drops to `34.73%`, whereas `A5 (Anti-Jump Veto)` achieves **`42.61%` (`+7.88%/yr` ahead of Control!)**. When `NVDA + SNDK + PLTR` are all banned simultaneously, `A5` achieves **`32.65%`** vs Control's `27.35%` (`+5.30%/yr`).
    - **2D Parameter Sensitivity Grid (`Table T6`)**: Across all `31` parameter combinations of `fip_th in {-0.02, 0.0, +0.02, None} x jump_th in {0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, None}`, **`30 / 31` parameter cells beat Control (`44.01%` to `47.06%` CAGR)**.
    - **Why `A5` is still NOT a miracle**: It only triggers in ~12% of months (vetoing episodic spike traps like `TWTR` in `2018-06` before its `-29.1%` crash, `SMCI` in `2024-08`, and `EA` in `2011-11`), so its Newey-West $t$-stat vs Control is **`+1.07`** ($p pprox 0.28$), and it **does not reduce worst-case Daily MaxDD (`-46.76%`)**.

| Strategy / Hypothesis Variant | Core3 CAGR 09-26 | Sharpe (m) | Month MaxDD | Daily DD (5651) | Daily DD (O2C) | QQQ Sleeve CAGR | Tech Sleeve CAGR | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN] | 43.75% | 1.08 | -36.6% | -46.76% | -49.68% | 43.75% | 38.73% | 24.79% | 72.53% | 9.1% | 0.86 |  |
| 00b. Core1 Control (50% QQQ Raw 12-1 Mom Top-2 + 50% Tech Mom Top-1) | 40.74% | 1.00 | -37.3% | -47.27% | -50.30% | 37.12% | 38.73% | 21.91% | 69.39% | -8.5% | 0.78 | -0.54 |

| Strategy / Hypothesis Variant | Core3 CAGR 09-26 | Sharpe (m) | Month MaxDD | Daily DD (5651) | Daily DD (O2C) | QQQ Sleeve CAGR | Tech Sleeve CAGR | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1a. FIP on QQQ Only (QQQ Sharpe Top-5 -> FIP Top-2; Tech Control) | 34.36% | 0.97 | -36.6% | -47.46% | -50.39% | 24.98% | 38.73% | 22.90% | 50.74% | 10.0% | 0.95 | -2.30 |
| A1b. FIP on Tech Only (QQQ Control; Tech Mom Top-3 -> FIP Top-1) | 34.72% | 0.98 | -35.8% | -45.12% | -43.12% | 43.75% | 21.20% | 29.56% | 41.68% | -14.9% | 0.98 | -1.62 |
| A1c. FIP on Both Sleeves (QQQ Top-5->FIP Top-2 + Tech Top-3->FIP Top-1) | 25.09% | 0.81 | -35.0% | -43.26% | -41.72% | 24.98% | 21.20% | 27.23% | 22.39% | -14.3% | 1.08 | -2.23 |
| A2. FIP Pool Grid: QQQ Top-3->FIP Top-2 + Tech Top-2->FIP Top-1 | 34.18% | 1.01 | -38.0% | -47.57% | -52.40% | 37.62% | 26.42% | 30.98% | 38.42% | 4.6% | 0.98 | -1.31 |
| A2. FIP Pool Grid: QQQ Top-4->FIP Top-2 + Tech Top-2->FIP Top-1 | 30.39% | 0.93 | -36.7% | -47.57% | -52.40% | 29.95% | 26.42% | 29.34% | 31.75% | 3.9% | 1.02 | -1.62 |
| A2. FIP Pool Grid: QQQ Top-4->FIP Top-2 + Tech Top-3->FIP Top-1 | 27.56% | 0.86 | -34.6% | -43.64% | -42.07% | 29.95% | 21.20% | 28.95% | 25.78% | -18.2% | 1.08 | -2.04 |
| A2. FIP Pool Grid: QQQ Top-5->FIP Top-2 + Tech Top-2->FIP Top-1 | 27.93% | 0.88 | -36.7% | -47.57% | -52.40% | 24.98% | 26.42% | 27.73% | 28.18% | 8.8% | 1.02 | -1.84 |
| A2. FIP Pool Grid: QQQ Top-6->FIP Top-2 + Tech Top-3->FIP Top-1 | 21.57% | 0.73 | -40.4% | -51.26% | -49.87% | 17.86% | 21.20% | 21.86% | 21.20% | -15.2% | 1.03 | -2.59 |
| A2. FIP Pool Grid: QQQ Top-8->FIP Top-2 + Tech Top-4->FIP Top-1 | 17.19% | 0.62 | -39.7% | -49.53% | -48.19% | 16.07% | 14.41% | 14.89% | 20.22% | -19.1% | 1.01 | -3.14 |
| A2. FIP Pool Grid: QQQ Top-10->FIP Top-2 + Tech Top-5->FIP Top-1 | 15.44% | 0.57 | -41.4% | -52.90% | -49.70% | 19.20% | 8.68% | 11.59% | 20.61% | -19.4% | 1.02 | -3.41 |
| A3. FIP on Raw Mom Pool: QQQ Raw Top-4->FIP Top-2 + Tech Top-2->FIP Top-1 | 28.77% | 0.85 | -48.1% | -51.24% | -52.89% | 27.25% | 26.42% | 26.20% | 32.17% | 1.9% | 0.94 | -1.69 |
| A3. FIP on Raw Mom Pool: QQQ Raw Top-5->FIP Top-2 + Tech Top-3->FIP Top-1 | 27.28% | 0.83 | -39.7% | -48.54% | -46.92% | 29.66% | 21.20% | 26.97% | 27.68% | -20.1% | 1.02 | -1.89 |
| A3. FIP on Raw Mom Pool: QQQ Raw Top-6->FIP Top-2 + Tech Top-3->FIP Top-1 | 25.62% | 0.81 | -39.1% | -48.02% | -46.42% | 26.15% | 21.20% | 27.23% | 23.58% | -16.4% | 1.02 | -2.06 |
| A4a. Zero-Param Multiplicative: Score = BaseMom * (1 + FIP_Smooth) | 43.12% | 1.07 | -36.6% | -46.76% | -49.68% | 41.81% | 39.89% | 28.39% | 64.66% | 2.3% | 0.87 | -0.40 |
| A4b. Zero-Param Non-Jump Mom (12-1 Return Excluding 5 Biggest Jump Days) | 32.67% | 0.93 | -36.6% | -46.76% | -49.68% | 29.08% | 32.83% | 21.49% | 48.62% | -20.6% | 0.92 | -2.47 |
| A5. Anti-Jump Veto (Drop Winner Only If FIP<0 or Top5Days > 65% of Gain) | 46.79% | 1.14 | -36.6% | -46.76% | -49.68% | 44.77% | 44.03% | 28.13% | 74.95% | 9.1% | 0.90 | 1.07 |
| A6a. Neighbor Window: 6-1 FIP Smooth (QQQ Top-5 / Tech Top-3) | 23.71% | 0.77 | -53.5% | -55.69% | -56.20% | 26.85% | 15.89% | 18.36% | 30.97% | -19.7% | 1.14 | -2.15 |
| A6b. Neighbor Definition: Monthly Win-Rate Across 11 Formation Months | 34.55% | 0.99 | -42.1% | -50.03% | -49.07% | 33.42% | 31.59% | 29.74% | 41.02% | -19.1% | 1.01 | -1.53 |
| A7. Rank Blend (Top-10 Pool): Rank(Mom) + 0.25 * Rank(FIP) | 38.06% | 1.03 | -42.1% | -48.48% | -49.68% | 37.99% | 32.48% | 22.82% | 60.56% | 8.1% | 0.89 | -1.51 |
| A7. Rank Blend (Top-10 Pool): Rank(Mom) + 0.50 * Rank(FIP) | 34.38% | 0.98 | -41.6% | -45.93% | -50.91% | 36.02% | 28.01% | 30.63% | 39.37% | -1.6% | 0.94 | -1.35 |
| A7. Rank Blend (Top-10 Pool): Rank(Mom) + 0.75 * Rank(FIP) | 30.94% | 0.92 | -42.6% | -47.62% | -52.40% | 31.72% | 25.89% | 27.40% | 35.66% | -12.0% | 1.01 | -1.79 |
| A7. Rank Blend (Top-10 Pool): Rank(Mom) + 1.00 * Rank(FIP) | 28.96% | 0.89 | -36.7% | -47.62% | -52.40% | 32.54% | 21.71% | 27.03% | 31.49% | -18.1% | 1.01 | -1.87 |

---

### 3.2 Hypothesis B: Residual Momentum (Blitz, Huij, Martens 2011)
- **Empirical Result (`B1–B4`)**:
  - Every single Residual Momentum variant (`B1a` through `B4b`) underperforms the frozen `Core3` Control (`30.92%` to `40.41%` vs `43.75%`, with Newey-West $t$-stats between `-0.98` and `-2.13`).
- **Economic & Mathematical Diagnosis**:
  - Look at `Table T2` (`Single-Rank Monotonicity Diagnostic`) for `B1e (Residual Sharpe vs XLK)`:
    - In `Tech`, single-rank CAGRs become much more uniform: `Rank #1 = 31.58%`, `Rank #2 = 26.63%`, `Rank #3 = 19.82%`, and `Tech Rank #1` Monthly MaxDD improves from `-67.0%` to **`-54.6%`**!
    - So Blitz, Huij & Martens (2011) are **academically right** about cross-sectional smoothness: stripping out market/sector beta dramatically improves `Rank #2` (`9.67% -> 26.63%`) and `Rank #3` (`8.84% -> 19.82%`) and lowers single-stock drawdown.
    - **Why does it lose in `Core3`?** Because `Core3` is a **1.0x long-only Top-1 / Top-2** strategy, not a 50-stock dollar-neutral decile spread! During major technology/semiconductor bull waves (`2019–2026`), total-return momentum naturally selects high-beta secular leaders (`eta_{XLK} pprox 1.4–1.8`, such as `NVDA`, `AMD`, `SNDK`, `MU`) that capture **both** idiosyncratic alpha **and** sector-wave beta amplification. Stripping out `QQQ / XLK` beta cuts `2019–2026` CAGR from **`72.53%` down to `50.93%–53.06%`**.

| Strategy / Hypothesis Variant | Core3 CAGR 09-26 | Sharpe (m) | Month MaxDD | Daily DD (5651) | Daily DD (O2C) | QQQ Sleeve CAGR | Tech Sleeve CAGR | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1a. Residual Mom on QQQ Only (QQQ ResSharpe vs QQQ; Tech Control) | 40.41% | 1.02 | -42.6% | -46.76% | -49.68% | 37.07% | 38.73% | 19.65% | 72.60% | 11.4% | 0.91 | -1.17 |
| B1b. Residual Mom on Tech Only (QQQ Control; Tech ResRet vs XLK) | 37.25% | 0.96 | -44.4% | -49.94% | -49.68% | 43.75% | 26.28% | 27.50% | 50.94% | -8.5% | 0.91 | -1.70 |
| B1c. Residual Mom on Tech Only (QQQ Control; Tech ResSharpe vs XLK) | 39.49% | 1.05 | -37.3% | -46.76% | -49.68% | 43.75% | 31.58% | 29.91% | 52.91% | -6.0% | 0.98 | -1.01 |
| B1d. Residual Mom on Both: QQQ ResSharpe(QQQ) + Tech ResRet(XLK) | 34.01% | 0.91 | -36.6% | -46.76% | -49.68% | 37.07% | 26.28% | 22.21% | 50.93% | -6.6% | 0.96 | -2.09 |
| B1e. Residual Mom on Both: QQQ ResSharpe(QQQ) + Tech ResSharpe(XLK) | 36.28% | 1.00 | -37.0% | -46.76% | -49.68% | 37.07% | 31.58% | 24.55% | 53.06% | -4.1% | 1.03 | -1.49 |
| B1f. Residual Mom on Both: QQQ ResRet(QQQ) + Tech ResRet(XLK) | 33.00% | 0.87 | -51.9% | -57.57% | -55.72% | 34.49% | 26.28% | 21.21% | 49.93% | -24.2% | 0.89 | -1.90 |
| B1g. Residual Mom on Both: QQQ ResSharpe(QQQ) + Tech ResRet(SPY) | 36.59% | 0.96 | -36.8% | -46.76% | -49.68% | 37.07% | 31.23% | 19.63% | 62.08% | -8.7% | 0.95 | -1.95 |
| B1h. 2-Factor Residual (SPY+XLK): QQQ ResSharpe(2F) + Tech ResRet(2F) | 33.36% | 0.91 | -36.6% | -46.76% | -49.68% | 35.42% | 26.80% | 25.35% | 44.47% | -3.5% | 0.97 | -2.07 |
| B1i. 2-Factor Residual (SPY+XLK): QQQ ResSharpe(2F) + Tech ResSharpe(2F) | 32.63% | 0.92 | -36.6% | -46.76% | -49.68% | 35.42% | 26.16% | 23.73% | 45.07% | 3.9% | 1.08 | -1.96 |
| B2. Exact Blitz-Huij-Martens Standardized Residual Sum (QQQ + XLK) | 37.94% | 1.05 | -36.6% | -48.31% | -50.29% | 37.39% | 35.05% | 27.74% | 52.33% | -16.6% | 1.08 | -1.23 |
| B3. Top-N Pool -> Best Residual Mom (QQQ Top-3, Tech Top-2) | 35.62% | 0.91 | -40.6% | -47.60% | -49.68% | 36.01% | 30.60% | 21.42% | 56.44% | -5.1% | 0.94 | -1.86 |
| B3. Top-N Pool -> Best Residual Mom (QQQ Top-4, Tech Top-2) | 35.59% | 0.91 | -36.7% | -46.76% | -49.68% | 35.65% | 30.60% | 19.90% | 58.89% | -4.2% | 0.93 | -1.82 |
| B3. Top-N Pool -> Best Residual Mom (QQQ Top-5, Tech Top-3) | 34.44% | 0.91 | -36.6% | -46.76% | -49.68% | 35.91% | 28.26% | 22.48% | 51.61% | -10.1% | 0.95 | -2.13 |
| B3. Top-N Pool -> Best Residual Mom (QQQ Top-8, Tech Top-4) | 34.88% | 0.92 | -36.6% | -46.76% | -49.68% | 36.42% | 28.45% | 21.92% | 53.65% | -9.2% | 0.94 | -2.04 |
| B4a. Neighbor Window: 6-1 Residual Momentum (QQQ ResSharpe + Tech ResRet) | 30.92% | 0.92 | -37.0% | -46.80% | -48.33% | 31.23% | 25.27% | 23.36% | 41.36% | -7.0% | 1.24 | -1.56 |
| B4b. Neighbor Window: 18-1 Beta Estimation Applied to 12-1 Return | 39.29% | 1.00 | -36.6% | -46.76% | -49.68% | 41.40% | 32.46% | 24.32% | 61.32% | -10.1% | 0.96 | -0.98 |

---

### 3.3 Hypothesis C: Price + Fundamental / Earnings Momentum (Novy-Marx 2015 / PEAD)
- **Strict Point-in-Time Construction Verified by Physical Truncation (`Table T0 = 0.00e+00`)**:
  - `ear_latest` and `ear_sum4` use strictly PIT SEC Form 8-K Item 2.02 release timestamps (`public_date = session[R+1] <= t`, age $\le 100$ days).
  - Quarterly revenue and diluted EPS growth (`rev_yoy_q`, `rev_accel_q`, `eps_yoy_sym_q`, `eps_accel_q`, `eps_ttm_yoy_sym`) use strictly PIT SEC 10-Q/10-K XBRL filing dates (`max(filed_curr, filed_prior) + 1 calendar day <= t`, age $\le 200$ days, `cik_valid(ticker, t)`).
- **Sharp Divergence Between `QQQ Sleeve (Top-2)` and `Tech Sleeve (Top-1)`**:
  1. **In `QQQ Sleeve (Top-2)`, `4-Quarter Cumulative EAR` (`ear_sum4`) and `RankBlend(w=0.25)` Add `+5.2%` to `+6.3%/yr`**:
     - Selecting the Top-2 stocks by `ear_sum4` inside the Top-5 `QQQ Sharpe-Momentum` pool (`C1: 4-Quarter Cumulative EAR`) boosts standalone **`QQQ Sleeve` CAGR from `43.75%` to `50.04%`**!
     - Blending `Rank(SharpeMom) + 0.25 * Rank(FundMom)` inside the Top-10 QQQ pool (`C5 w=0.25`) boosts **`QQQ Sleeve` CAGR from `43.75%` to `48.93%`**.
     - Vetoing QQQ winners in the bottom 40% of `FundMom` (`C4b`) raises **`QQQ Sleeve` CAGR from `43.75%` to `44.68%`**.
     - *Why?* Because `Nasdaq-100` is a cross-sector index containing Biotech (`MRNA`, `BIIB`, `VRTX`), Retail, and Telecom alongside Tech. Requiring repeated positive earnings announcement drift (`ear_sum4`) filters out speculative non-earnings bubbles in `QQQ`.
  2. **In `Tech Sleeve (Top-1)`, Every Fundamental Filter Hurts (`38.73% -> 11.68%–34.47%`)**:
     - Even the best fundamental metric in Tech (`4Q EAR`, `28.08%`) loses `-10.65%/yr` vs pure price momentum (`38.73%`), while GAAP EPS acceleration (`eps_accel_q`, `11.68%`) loses `-27.05%/yr`!
     - *Why?* Because `S&P 500 IT` is heavily driven by **semiconductor and hardware cycles (`MU`, `SNDK`, `WDC`, `LRCX`, `KLAC`, `AMAT`, `AMD`, `NVDA`)**. At cyclical inflection points, semiconductor stocks break out into Top-1 price momentum **1 to 2 quarters before** their trailing 10-Q YoY GAAP revenue/EPS growth turns positive! Filtering `Tech Top-1` by trailing 10-Q GAAP numbers systematically misses the most explosive early-cycle rallies.

| Strategy / Hypothesis Variant | Core3 CAGR 09-26 | Sharpe (m) | Month MaxDD | Daily DD (5651) | Daily DD (O2C) | QQQ Sleeve CAGR | Tech Sleeve CAGR | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> 3-Day Earnings Announcement Return (EAR, 8-K Item 2.02) | 34.46% | 0.90 | -51.4% | -58.46% | -57.89% | 38.54% | 25.65% | 25.51% | 46.97% | -26.7% | 1.08 | -1.02 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> 4-Quarter Cumulative EAR | 41.78% | 0.99 | -54.4% | -60.72% | -60.27% | 50.04% | 28.08% | 24.45% | 67.75% | -20.2% | 0.83 | -0.02 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> Quarterly Revenue YoY Growth | 30.14% | 0.85 | -53.6% | -59.27% | -57.57% | 37.50% | 18.09% | 20.48% | 43.77% | -29.1% | 0.87 | -1.44 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> Quarterly Revenue Growth Acceleration (Delta Rev YoY) | 35.62% | 0.92 | -40.1% | -49.65% | -52.14% | 40.27% | 24.98% | 22.99% | 53.84% | -20.3% | 1.06 | -1.15 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> Quarterly Diluted EPS Symmetric YoY Growth | 27.74% | 0.80 | -50.2% | -55.14% | -54.90% | 34.51% | 16.23% | 18.12% | 41.33% | -23.0% | 0.96 | -2.16 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> Quarterly Diluted EPS Growth Acceleration (Delta EPS YoY) | 19.52% | 0.62 | -52.9% | -56.93% | -57.83% | 23.05% | 11.68% | 11.06% | 31.38% | -38.1% | 1.12 | -3.22 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> TTM Diluted EPS Symmetric YoY Growth | 30.63% | 0.86 | -45.3% | -50.82% | -51.05% | 37.17% | 19.64% | 18.64% | 47.91% | -30.4% | 0.94 | -1.51 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> Operating Acceleration Composite (Rev + EPS YoY & Accel) | 23.27% | 0.68 | -46.1% | -50.03% | -52.14% | 29.05% | 13.21% | 15.34% | 34.32% | -31.8% | 1.02 | -2.84 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> PEAD Composite (EAR + 4Q EAR + Quarterly EPS YoY) | 28.59% | 0.83 | -48.3% | -53.13% | -53.68% | 36.07% | 16.92% | 18.32% | 43.17% | -15.0% | 1.02 | -1.81 |
| C1. Price Pool (QQQ Top-5 / Tech Top-3) -> All-In Fundamental Momentum Composite (EAR + Rev + EPS) | 30.15% | 0.84 | -46.8% | -54.90% | -54.62% | 39.20% | 16.57% | 18.53% | 46.83% | -28.6% | 0.99 | -1.52 |
| C2a. FundMom Composite on QQQ Only (QQQ Top-5->FundMom; Tech Control) | 41.66% | 1.03 | -40.2% | -49.68% | -52.36% | 39.20% | 38.73% | 22.27% | 71.29% | 4.7% | 0.90 | -0.41 |
| C2b. FundMom Composite on Tech Only (QQQ Control; Tech Top-3->FundMom) | 32.35% | 0.89 | -48.6% | -56.20% | -56.85% | 43.75% | 16.57% | 21.04% | 48.51% | -24.7% | 0.95 | -1.48 |
| C2c. EAR (8-K Drift) on QQQ Only (QQQ Top-5->EAR; Tech Control) | 41.67% | 1.06 | -35.5% | -46.74% | -48.58% | 38.54% | 38.73% | 25.64% | 65.41% | 1.7% | 0.94 | -0.63 |
| C2d. EAR (8-K Drift) on Tech Only (QQQ Control; Tech Top-3->EAR) | 36.84% | 0.94 | -51.6% | -56.61% | -57.23% | 43.75% | 25.65% | 24.75% | 54.18% | -21.0% | 1.00 | -0.88 |
| C3. FundMom Pool Grid: QQQ Top-3->FundMom + Tech Top-2->FundMom | 31.90% | 0.87 | -52.7% | -60.33% | -59.89% | 39.37% | 19.22% | 22.22% | 45.53% | -15.5% | 0.94 | -1.60 |
| C3. FundMom Pool Grid: QQQ Top-4->FundMom + Tech Top-2->FundMom | 30.62% | 0.84 | -53.7% | -61.86% | -61.22% | 36.62% | 19.22% | 19.52% | 46.47% | -17.8% | 0.96 | -1.56 |
| C3. FundMom Pool Grid: QQQ Top-4->FundMom + Tech Top-3->FundMom | 28.96% | 0.81 | -48.3% | -56.51% | -56.24% | 36.62% | 16.57% | 17.17% | 45.93% | -27.7% | 1.01 | -1.72 |
| C3. FundMom Pool Grid: QQQ Top-6->FundMom + Tech Top-3->FundMom | 29.45% | 0.83 | -47.7% | -54.82% | -54.54% | 37.74% | 16.57% | 17.59% | 46.52% | -31.5% | 1.00 | -1.60 |
| C3. FundMom Pool Grid: QQQ Top-8->FundMom + Tech Top-4->FundMom | 25.85% | 0.76 | -51.5% | -56.83% | -58.13% | 32.94% | 14.07% | 16.05% | 39.72% | -32.7% | 0.98 | -1.86 |
| C3. FundMom Pool Grid: QQQ Top-10->FundMom + Tech Top-5->FundMom | 24.40% | 0.74 | -53.3% | -60.88% | -61.23% | 30.43% | 13.60% | 13.93% | 39.33% | -29.2% | 1.00 | -1.92 |
| C4a. Earnings Veto: Drop Winner Only If Latest 8-K EAR < -1% | 34.89% | 0.92 | -45.5% | -52.59% | -52.89% | 32.44% | 32.63% | 19.18% | 58.27% | -9.3% | 1.05 | -1.34 |
| C4b. Fundamental Veto: Drop Winner Only If FundMom Rank < 40th Pct | 41.84% | 1.04 | -44.6% | -48.50% | -49.81% | 44.68% | 34.47% | 23.49% | 69.59% | 12.7% | 0.86 | -0.92 |
| C5. Rank Blend (Top-10 Pool): Rank(PriceMom) + 0.25 * Rank(FundMom) | 40.23% | 0.98 | -44.1% | -50.28% | -50.27% | 48.93% | 26.56% | 22.38% | 67.16% | -4.0% | 0.89 | -0.58 |
| C5. Rank Blend (Top-10 Pool): Rank(PriceMom) + 0.50 * Rank(FundMom) | 31.30% | 0.84 | -54.1% | -61.27% | -61.14% | 39.56% | 19.22% | 16.27% | 53.60% | -3.9% | 0.95 | -1.89 |
| C5. Rank Blend (Top-10 Pool): Rank(PriceMom) + 0.75 * Rank(FundMom) | 29.98% | 0.83 | -50.4% | -58.33% | -58.50% | 40.29% | 15.16% | 18.86% | 45.86% | -13.0% | 0.93 | -2.05 |
| C5. Rank Blend (Top-10 Pool): Rank(PriceMom) + 1.00 * Rank(FundMom) | 32.85% | 0.90 | -50.7% | -59.22% | -59.24% | 45.18% | 16.27% | 22.11% | 48.12% | -18.7% | 0.99 | -1.52 |

---

### 3.4 Hypothesis D (2nd Tier): 52-Week-High Proximity (George & Hwang 2004)
- **Empirical Result (`D1–D2`)**:
  - Re-ranking `Top-5 QQQ / Top-3 Tech` by proximity to 52-week high (`Close[t] / High_252d[t]`) collapses `Core3` CAGR from `43.75%` to **`12.12%`** (`t = -3.53`), and `Tech Rank #1` collapses to **`4.89%`** while `Tech Rank #2` is `38.39%` (`Table T2`)!
  - Even zero-parameter multiplicative weighting (`BaseMom * (Close / High252)`, `D2`) reduces `Core3` CAGR to **`37.24%`** (`t = -2.46`).
  - *Why?* Because high-beta momentum winners (`\sigma pprox 45\%–65\%`) routinely sit `5%–12%` below their 252-day high at month-end during normal consolidation, whereas low-beta defensive stocks (`\sigma pprox 18\%`) sit at `98%–100%` of their 52-week high.

| Strategy / Hypothesis Variant | Core3 CAGR 09-26 | Sharpe (m) | Month MaxDD | Daily DD (5651) | Daily DD (O2C) | QQQ Sleeve CAGR | Tech Sleeve CAGR | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1. 52W-High Pool Grid: QQQ Top-3->52WH + Tech Top-2->52WH | 40.71% | 1.07 | -40.2% | -49.68% | -52.12% | 41.11% | 35.87% | 25.69% | 62.77% | -23.8% | 1.12 | -0.51 |
| D1. 52W-High Pool Grid: QQQ Top-5->52WH + Tech Top-3->52WH | 12.12% | 0.47 | -47.4% | -53.28% | -54.58% | 16.60% | 4.89% | 16.37% | 6.86% | -34.0% | 1.35 | -3.53 |
| D1. 52W-High Pool Grid: QQQ Top-8->52WH + Tech Top-4->52WH | 9.56% | 0.39 | -51.5% | -56.96% | -55.00% | 14.67% | 1.74% | 6.19% | 14.08% | -44.1% | 1.51 | -3.85 |
| D2. Zero-Param Multiplicative: Score = BaseMom * (Close / High252) | 37.24% | 0.97 | -40.2% | -49.68% | -52.12% | 36.09% | 34.37% | 20.26% | 62.74% | -9.7% | 0.84 | -2.46 |

---

## 4. Mandatory Verification Tables (`T0`, `T2`, `T3`, `T4`, `T5`, `T6`)

### 4.1 Physical Truncation Look-Ahead Audit (`Table T0`)
All 15 newly engineered features across Hypotheses A, B, C, and D were recomputed from scratch after physically truncating all price, 8-K, and 10-Q/10-K datasets at 5 historical cutoff dates. Maximum absolute difference across all `21,402` QQQ rows and `14,605` Tech rows is **`0.00e+00`**.

| Cutoff Date | QQQ Rows | Tech Rows | QQQ Max Diff (15 Factors) | Tech Max Diff (15 Factors) | Status |
|---|---|---|---|---|---|
| 2011-12-31 | 3586 | 2648 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2015-06-30 | 7768 | 5345 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2018-12-31 | 12087 | 8142 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2021-12-31 | 15757 | 10706 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2024-06-30 | 18779 | 12801 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |

### 4.2 Single-Rank Monotonicity Diagnostic (`Table T2`)
| Hypothesis / Selection Method | QQQ Rank #1 CAGR | QQQ Rank #2 CAGR | QQQ Rank #3 CAGR | QQQ R#1 DD | QQQ R#2 DD | Tech Rank #1 CAGR | Tech Rank #2 CAGR | Tech Rank #3 CAGR | Tech R#1 DD |
|---|---|---|---|---|---|---|---|---|---|
| 0. Control (QQQ Sharpe-Mom / Tech Raw Mom) | 25.41% | 54.45% | 22.75% | -65.3% | -47.5% | 38.73% | 9.67% | 8.84% | -67.0% |
| A1. FIP Pool (QQQ Top-5->FIP / Tech Top-3->FIP) | 22.47% | 20.02% | 38.80% | -49.9% | -65.7% | 21.20% | 15.25% | 18.90% | -69.8% |
| A4a. FIP Multiplicative (BaseMom * (1+FIP)) | 29.80% | 45.75% | 14.82% | -55.4% | -56.6% | 39.89% | 6.27% | 5.31% | -62.1% |
| A5. Anti-Jump Veto | 22.76% | 60.22% | 23.83% | -71.3% | -47.5% | 44.03% | 13.29% | 1.35% | -59.6% |
| B1. Residual Momentum (QQQ ResSharpe / Tech ResRet XLK) | 21.70% | 43.59% | 21.75% | -55.7% | -38.6% | 26.28% | 21.68% | 12.77% | -60.6% |
| B1e. Residual Sharpe Both (QQQ ResSharpe / Tech ResSharpe XLK) | 21.70% | 43.59% | 21.75% | -55.7% | -38.6% | 31.58% | 26.63% | 19.82% | -54.6% |
| C1. Price Pool -> FundMom Composite (Top-5 / Top-3) | 18.27% | 51.90% | 37.83% | -60.5% | -31.8% | 16.57% | 23.30% | 15.42% | -78.6% |
| C4b. Fundamental Veto (Drop if FundMom < 40th Pct) | 26.74% | 54.67% | 24.78% | -59.3% | -47.1% | 34.47% | 12.02% | 10.14% | -75.5% |
| D1. 52W-High Pool (Top-5 / Top-3) | 19.75% | 8.18% | 42.65% | -45.0% | -66.0% | 4.89% | 38.39% | 13.57% | -79.5% |

### 4.3 Leave-One-Winner-Out & Outlier Month Stress Audit (`Table T3`)
| Strategy | Full CAGR | Drop Best 5m | No NVDA | No SNDK | No PLTR | No TSLA | No MU | No WDC | No AMD | Ban Top 3 (NVDA+SNDK+PLTR) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0. Control Core3 [FROZEN] | 43.75% | 29.76% | 34.73% | 42.18% | 37.81% | 40.29% | 42.25% | 43.21% | 41.88% | 27.35% |
| A1c. FIP Pool (QQQ Top-5->FIP, Tech Top-3->FIP) | 25.09% | 15.73% | 20.99% | 22.88% | 24.44% | 21.68% | 20.14% | 22.29% | 24.98% | 19.33% |
| A4a. FIP Multiplicative (BaseMom * (1+FIP)) | 43.12% | 29.20% | 35.51% | 40.68% | 36.79% | 39.65% | 39.67% | 41.29% | 40.12% | 25.75% |
| A5. Anti-Jump Veto | 46.79% | 32.51% | 42.61% | 44.68% | 40.41% | 43.25% | 45.25% | 46.05% | 45.82% | 32.65% |
| B1d. Residual Mom (QQQ ResSharpe + Tech ResRet XLK) | 34.01% | 21.23% | 27.77% | 29.84% | 27.93% | 34.06% | 31.36% | 32.44% | 33.09% | 16.73% |
| B3. Residual Pool (QQQ Top-5->Res, Tech Top-3->Res) | 34.44% | 21.62% | 27.85% | 30.26% | 28.17% | 34.33% | 32.86% | 32.87% | 33.29% | 16.68% |
| C1. FundMom Composite Pool (QQQ Top-5, Tech Top-3) | 30.15% | 18.70% | 23.45% | 30.17% | 24.25% | 28.98% | 26.49% | 28.90% | 31.62% | 17.66% |
| C4b. Fundamental Veto (FundMom >= 40th Pct) | 41.84% | 28.04% | 32.77% | 41.93% | 34.97% | 38.57% | 40.20% | 41.11% | 40.24% | 26.02% |
| D1. 52W-High Pool (QQQ Top-5, Tech Top-3) | 12.12% | 3.62% | 9.35% | 9.45% | 10.82% | 10.67% | 11.17% | 13.07% | 13.07% | 5.35% |

### 4.4 Second-Vendor (`Tiingo-First`) End-to-End Replication (`Table T4`)
| Strategy | Primary CAGR | Tiingo-First CAGR | Diff (bp) | Primary Sharpe | Tiingo Sharpe | Primary DD | Tiingo DD | Ret Corr | QQQ Pick Match | Tech Pick Match |
|---|---|---|---|---|---|---|---|---|---|---|
| 0. Control Core3 [FROZEN] | 43.75% | 43.82% | 7.16 | 1.08 | 1.08 | -36.6% | -36.6% | 1.000 | 100.0% | 100.0% |
| A1c. FIP Pool (QQQ Top-5->FIP, Tech Top-3->FIP) | 25.09% | 25.22% | 12.69 | 0.81 | 0.81 | -35.0% | -35.0% | 1.000 | 99.5% | 100.0% |
| A4a. FIP Multiplicative (BaseMom * (1+FIP)) | 43.12% | 43.20% | 7.16 | 1.07 | 1.07 | -36.6% | -36.6% | 1.000 | 100.0% | 100.0% |
| A5. Anti-Jump Veto | 46.79% | 46.81% | 1.43 | 1.14 | 1.14 | -36.6% | -36.6% | 1.000 | 100.0% | 100.0% |
| B1d. Residual Mom (QQQ ResSharpe + Tech ResRet XLK) | 34.01% | 34.04% | 3.55 | 0.91 | 0.91 | -36.6% | -36.6% | 1.000 | 99.5% | 100.0% |
| B3. Residual Pool (QQQ Top-5->Res, Tech Top-3->Res) | 34.44% | 34.47% | 3.61 | 0.91 | 0.91 | -36.6% | -36.6% | 1.000 | 99.5% | 100.0% |
| C1. FundMom Composite Pool (QQQ Top-5, Tech Top-3) | 30.15% | 30.12% | -2.21 | 0.84 | 0.84 | -46.8% | -46.8% | 1.000 | 99.5% | 100.0% |
| C4b. Fundamental Veto (FundMom >= 40th Pct) | 41.84% | 41.89% | 5.17 | 1.04 | 1.04 | -44.6% | -44.5% | 1.000 | 100.0% | 100.0% |
| D1. 52W-High Pool (QQQ Top-5, Tech Top-3) | 12.12% | 12.11% | -0.83 | 0.47 | 0.47 | -47.4% | -47.4% | 1.000 | 99.5% | 100.0% |

### 4.5 Cumulative Multiple-Testing Deflated Sharpe Ratio (`Table T5`)
| Strategy | Grand Total Trials | This Round Trials | Excess Sharpe (Ann) | Null Expected Max SR0 | DSR (All Cumulative) | DSR (This Round Only) | Active IR vs Control |
|---|---|---|---|---|---|---|---|
| 0. Control Core3 [FROZEN] | 714 | 70 | 1.08 | 0.90 | 0.791 | 0.965 | 0.00 |
| A1c. FIP Pool (QQQ Top-5->FIP, Tech Top-3->FIP) | 714 | 70 | 0.81 | 0.90 | 0.341 | 0.696 | -0.61 |
| A4a. FIP Multiplicative (BaseMom * (1+FIP)) | 714 | 70 | 1.08 | 0.90 | 0.790 | 0.965 | -0.10 |
| A5. Anti-Jump Veto | 714 | 70 | 1.14 | 0.90 | 0.869 | 0.983 | 0.25 |
| B1d. Residual Mom (QQQ ResSharpe + Tech ResRet XLK) | 714 | 70 | 0.91 | 0.90 | 0.510 | 0.847 | -0.57 |
| B3. Residual Pool (QQQ Top-5->Res, Tech Top-3->Res) | 714 | 70 | 0.91 | 0.90 | 0.513 | 0.849 | -0.55 |
| C1. FundMom Composite Pool (QQQ Top-5, Tech Top-3) | 714 | 70 | 0.84 | 0.90 | 0.397 | 0.742 | -0.37 |
| C4b. Fundamental Veto (FundMom >= 40th Pct) | 714 | 70 | 1.05 | 0.90 | 0.746 | 0.952 | -0.20 |
| D1. 52W-High Pool (QQQ Top-5, Tech Top-3) | 714 | 70 | 0.47 | 0.90 | 0.031 | 0.175 | -1.00 |

### 4.6 2D Parameter Sensitivity Grid for `A5` Anti-Jump Veto (`Table T6`)
| FIP Smooth Veto (<) | 5-Day Jump Share Veto (>) | Core3 CAGR 09-26 | Sharpe (m) | Month MaxDD | QQQ Sleeve CAGR | Tech Sleeve CAGR | 2009-2018 | 2019-2026 | NW t vs Ctrl | Beats Control? |
|---|---|---|---|---|---|---|---|---|---|---|
| -0.02 | 0.5 | 44.97% | 1.11 | -36.6% | 43.41% | 41.62% | 30.46% | 66.10% | 0.27 | True |
| -0.02 | 0.55 | 46.29% | 1.14 | -36.6% | 45.12% | 42.58% | 29.43% | 71.32% | 0.77 | True |
| -0.02 | 0.6 | 46.90% | 1.14 | -36.6% | 44.88% | 44.07% | 29.21% | 73.36% | 1.15 | True |
| -0.02 | 0.65 | 46.92% | 1.15 | -36.6% | 44.77% | 44.28% | 28.33% | 74.95% | 1.15 | True |
| -0.02 | 0.7 | 44.90% | 1.11 | -36.6% | 43.54% | 41.26% | 25.42% | 74.57% | 0.43 | True |
| -0.02 | 0.75 | 45.23% | 1.11 | -36.6% | 43.91% | 41.53% | 25.64% | 75.08% | 0.58 | True |
| -0.02 | 0.8 | 45.48% | 1.11 | -36.6% | 44.58% | 41.32% | 26.54% | 74.15% | 0.91 | True |
| -0.02 | nan | 45.42% | 1.11 | -36.6% | 44.21% | 41.47% | 27.38% | 72.53% | 1.56 | True |
| 0.0 | 0.5 | 44.97% | 1.11 | -36.6% | 43.41% | 41.62% | 30.46% | 66.10% | 0.27 | True |
| 0.0 | 0.55 | 46.29% | 1.14 | -36.6% | 45.12% | 42.58% | 29.43% | 71.32% | 0.77 | True |
| 0.0 | 0.6 | 47.06% | 1.14 | -36.6% | 45.45% | 43.82% | 29.45% | 73.36% | 1.18 | True |
| 0.0 | 0.65 | 46.79% | 1.14 | -36.6% | 44.77% | 44.03% | 28.13% | 74.95% | 1.07 | True |
| 0.0 | 0.7 | 44.78% | 1.10 | -36.6% | 43.54% | 41.01% | 25.23% | 74.57% | 0.36 | True |
| 0.0 | 0.75 | 45.10% | 1.11 | -36.6% | 43.91% | 41.29% | 25.45% | 75.08% | 0.51 | True |
| 0.0 | 0.8 | 45.35% | 1.11 | -36.6% | 44.58% | 41.08% | 26.35% | 74.15% | 0.80 | True |
| 0.0 | nan | 46.31% | 1.12 | -36.6% | 44.74% | 42.63% | 28.41% | 73.14% | 1.70 | True |
| 0.02 | 0.5 | 44.74% | 1.11 | -36.6% | 44.80% | 40.03% | 30.18% | 65.96% | 0.19 | True |
| 0.02 | 0.55 | 45.44% | 1.12 | -36.6% | 46.53% | 39.79% | 29.15% | 69.55% | 0.44 | True |
| 0.02 | 0.6 | 46.31% | 1.13 | -36.6% | 45.79% | 42.20% | 29.16% | 71.85% | 0.88 | True |
| 0.02 | 0.65 | 46.02% | 1.13 | -36.6% | 45.05% | 42.41% | 27.85% | 73.34% | 0.75 | True |
| 0.02 | 0.7 | 44.55% | 1.10 | -36.6% | 44.92% | 39.43% | 24.96% | 74.43% | 0.24 | True |
| 0.02 | 0.75 | 44.87% | 1.11 | -36.6% | 45.30% | 39.70% | 25.18% | 74.93% | 0.38 | True |
| 0.02 | 0.8 | 45.46% | 1.11 | -36.6% | 45.98% | 40.14% | 26.07% | 74.93% | 0.81 | True |
| 0.02 | nan | 45.03% | 1.10 | -36.6% | 45.94% | 39.22% | 27.83% | 70.70% | 0.70 | True |
| nan | 0.5 | 44.01% | 1.10 | -36.6% | 43.41% | 39.81% | 28.93% | 66.10% | -0.07 | True |
| nan | 0.55 | 45.32% | 1.12 | -36.6% | 45.12% | 40.75% | 27.91% | 71.32% | 0.46 | True |
| nan | 0.6 | 45.93% | 1.12 | -36.6% | 44.88% | 42.23% | 27.69% | 73.36% | 0.86 | True |
| nan | 0.65 | 45.70% | 1.12 | -36.6% | 44.29% | 42.43% | 26.44% | 74.95% | 0.76 | True |
| nan | 0.7 | 43.49% | 1.08 | -36.6% | 43.06% | 39.05% | 23.26% | 74.57% | -0.32 | False |
| nan | 0.75 | 43.81% | 1.09 | -36.6% | 43.43% | 39.32% | 23.48% | 75.08% | -0.13 | True |
| nan | 0.8 | 44.06% | 1.09 | -36.6% | 44.10% | 39.12% | 24.36% | 74.15% | 0.12 | True |

---

## 5. Final Governance Decision & Practical Conclusion

1. **Should We Unfreeze and Modify `Core3`?**
   - **No — keep `Core3` frozen as the primary baseline (`43.75% / 43.85%` CAGR, Sharpe `1.08`, Daily MaxDD `-46.76%`).**
   - While **`A5 (Anti-Jump Veto)`** is a clean, economically grounded improvement (`46.79%` CAGR, Sharpe `1.14`, `30/31` parameter grid cells beating Control, and **`42.61%` vs `34.73%` when `NVDA` is banned**), its Newey-West $t$-statistic against Control is **`+1.07`** ($p pprox 0.28$). Under our strict anti-overfitting governance (`N = 714` cumulative trials across the repository), a `+1.07` $t$-stat is **not** strong enough to justify replacing the frozen baseline rule ex-post.
   - Instead, `A5` should be documented as a **verified robustness confirmation**: it proves that `Core3`'s return is driven by **continuous secular compounders (`FIP >= 0`, moderate 5-day jump share)** rather than 5-day lottery spikes, and provides an optional conservative sanity veto if a future Rank #1 pick is a pure 1-week buyout/meme spike.
2. **Does Stock-Selection Refinement Provide a Path to `70% CAGR` (2009–2026) or `-25%` Daily MaxDD?**
   - **No.** Across all 70 isolated specifications of `FIP Consistency`, `Residual Momentum`, `PIT SEC 8-K / 10-Q Fundamental & Earnings Momentum`, and `52-Week-High Proximity`:
     - Full-period `2009–2026` unlevered `Core3` CAGR tops out at **`46.79%–47.06%`** (`A5` grid), because `2009–2018` was a lower-dispersion macro regime (`24.8%–28.1%` CAGR) while `2019–2026` already compounds at **`72.53%–74.95%` CAGR** unlevered.
     - True Daily MaxDD remains anchored around **`-43%` to `-49%`** because concentrated 3-stock long-only Tech/NDX equity exposure cannot avoid `2020 COVID` or `2022 Rate-Shock` drawdowns through stock-picking alone.
