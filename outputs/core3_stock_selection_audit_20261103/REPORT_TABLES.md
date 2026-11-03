### T0. Physical Truncation Audit Across All 15 New Stock-Selection Features

| Cutoff Date | QQQ Rows | Tech Rows | QQQ Max Diff (15 Factors) | Tech Max Diff (15 Factors) | Status |
|---|---|---|---|---|---|
| 2011-12-31 | 3586 | 2648 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2015-06-30 | 7768 | 5345 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2018-12-31 | 12087 | 8142 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2021-12-31 | 15757 | 10706 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |
| 2024-06-30 | 18779 | 12801 | 0.00e+00 | 0.00e+00 | PASS (0.00e+00) |

### T1. Complete Master Summary of Isolated Stock-Selection Hypotheses (A, B, C, D vs Control)

| Strategy / Hypothesis Variant | Core3 CAGR 09-26 | Sharpe (m) | Month MaxDD | Daily DD (5651) | Daily DD (O2C) | QQQ Sleeve CAGR | Tech Sleeve CAGR | 2009-2018 | 2019-2026 | 2022 Ret | Avg TO | NW t vs Ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN] | 43.75% | 1.08 | -36.6% | -46.76% | -49.68% | 43.75% | 38.73% | 24.79% | 72.53% | 9.1% | 0.86 |  |
| 00b. Core1 Control (50% QQQ Raw 12-1 Mom Top-2 + 50% Tech Mom Top-1) | 40.74% | 1.00 | -37.3% | -47.27% | -50.30% | 37.12% | 38.73% | 21.91% | 69.39% | -8.5% | 0.78 | -0.54 |
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
| D1. 52W-High Pool Grid: QQQ Top-3->52WH + Tech Top-2->52WH | 40.71% | 1.07 | -40.2% | -49.68% | -52.12% | 41.11% | 35.87% | 25.69% | 62.77% | -23.8% | 1.12 | -0.51 |
| D1. 52W-High Pool Grid: QQQ Top-5->52WH + Tech Top-3->52WH | 12.12% | 0.47 | -47.4% | -53.28% | -54.58% | 16.60% | 4.89% | 16.37% | 6.86% | -34.0% | 1.35 | -3.53 |
| D1. 52W-High Pool Grid: QQQ Top-8->52WH + Tech Top-4->52WH | 9.56% | 0.39 | -51.5% | -56.96% | -55.00% | 14.67% | 1.74% | 6.19% | 14.08% | -44.1% | 1.51 | -3.85 |
| D2. Zero-Param Multiplicative: Score = BaseMom * (Close / High252) | 37.24% | 0.97 | -40.2% | -49.68% | -52.12% | 36.09% | 34.37% | 20.26% | 62.74% | -9.7% | 0.84 | -2.46 |

### T2. Single-Rank Monotonicity Diagnostic (Rank #1 vs Rank #2 vs Rank #3)

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

### T3. Leave-One-Winner-Out & Best-5-Months Removal Stress Table

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

### T4. Second-Vendor (Tiingo-First) End-to-End Replication

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

### T5. Multiple-Testing Deflated Sharpe Ratio (DSR) Audit

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

### T6. 2D Parameter Sensitivity Grid for A5 Anti-Jump Veto (31 Parameter Cells)

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
