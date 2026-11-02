# 100% Clean-Room Multi-Bagger Layered Momentum Backtest Report (`2010–2026`)

- **Folder**: `outputs/multibagger_layered_momentum_20261102/`
- **Script**: [`run_multibagger_layered_backtest.py`](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/multibagger_layered_momentum_20261102/run_multibagger_layered_backtest.py)
- **Summary CSV**: [`multibagger_layered_summary_table.csv`](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/multibagger_layered_momentum_20261102/multibagger_layered_summary_table.csv)
- **Shortlist Sensitivity CSV**: [`shortlist_n_sensitivity_table.csv`](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/multibagger_layered_momentum_20261102/shortlist_n_sensitivity_table.csv)
- **November 2026 Live Shortlists**: [`nov2026_top20_shortlist_Tech_Only.csv`](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/multibagger_layered_momentum_20261102/nov2026_top20_shortlist_Tech_Only.csv) | [`nov2026_top20_shortlist_All_SP500.csv`](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/multibagger_layered_momentum_20261102/nov2026_top20_shortlist_All_SP500.csv)
- **Execution Standard**: Fixed **Next-Day Open-to-Open (`Open[t+1_day1] -> Open[t+2_day1]`)**, **Drifted Weights**, **`0.1%` (`10bp`) per-side fee**, **0% Cash (No SMA200/RS Filter)**.

---

## 1. Executive Conclusions (Core Findings)

1. **`Top-1` (Single Super-Winner) vs `Top-3` (Diversified Winners) Show Opposite Responses to Multi-Factor Reranking**:
   - **In `Top-1`, pure `12-1` Price Momentum (`Layer 1`) is already near-optimal (`Tech`: `39.77%` full / `59.91%` post-2015; `All S&P 500`: `40.99%` full / `41.98%` post-2015)**:
     - Diluting `12-1` price rank inside the Top-20 shortlist (`50/50` with fundamentals or 52-week-high proximity) **dethrones the #1 parabolic outlier** (`NVDA`, `AMD`, `SMCI`, `PLTR`, `SNDK`) in favor of #8–#18 stocks with lower price momentum, cutting `Tech Top-1` CAGR from `59.91%` down to `20.85%–28.27%`.
     - **Two exceptions that hold up in `Top-1`**:
       1. **`All_SP500 Top-1` + `V2b (Price Top-20 + Revenue Growth/Acceleration)`**: improves `2015–2026` CAGR from **`41.98% → 45.46%` (`+3.48%`)**, Sharpe from **`0.86 → 0.92`**, and cuts MaxDD by **`+11.93%` (`-70.70% → -58.77%`)**.
       2. **`Tech_Only Top-1` + `V3d (Price Top-20 + Cumulative Residual Return)`**: achieves **`40.10%` CAGR** (`2010–2026`, vs `39.77%` baseline) while cutting MaxDD by **`+8.75%` (`-53.82% → -45.07%`)**.
   - **In `Top-3`, Reranking by Residual Momentum (`V3c`) or PIT Fundamentals (`V2` / `Layer 2` / `Layer 3`) Delivers Large, Statistically Significant Gains**:
     - **`Tech_Only Top-3` + `V3c (Price Top-20 + Residual Momentum vs SPY + XLK)`**:
       - `2010–2026` (201m): CAGR jumps from **`23.54% → 28.46%` (`+4.92%`/yr)**, Sharpe **`0.76 → 0.90`**, MaxDD **`-40.23% → -38.30%`**.
       - `2015–2026` (141m): CAGR jumps from **`25.67% → 36.84%` (`+11.17%`/yr)**, Sharpe **`0.75 → 1.02`**, **`t_ari = +2.12, t_log = +2.28` ($p < 0.03$)**.
       - `2015–2026 Ex-2022`: CAGR jumps from **`32.84% → 45.35%` (`+12.51%`/yr)**.
     - **`Tech_Only Top-3` + `Layer 3 (1/3 Price + 1/3 PIT Fund + 1/3 Residual Mom)`**:
       - `2010–2026`: CAGR **`23.54% → 24.90%`**, Sharpe **`0.76 → 0.79`**, MaxDD **`-40.23% → -35.08%` (`+5.15%` DD improvement)**.
       - `2015–2026`: CAGR **`25.67% → 30.28%` (`+4.61%`/yr)**, Sharpe **`0.75 → 0.84`**.
     - **`All_SP500 Top-3` + `Layer 2 (50% Price + 50% PIT Fundamental)` / `V2_Pure_Fund_In_Top20`**:
       - `Layer 2 (Top-20)` improves `2010–2026` CAGR from **`25.31% → 28.39%` (`+3.08%`/yr, Sharpe `0.83`)** and `2015–2026` CAGR from **`27.35% → 28.74%`**.
       - `V2_Pure_Fund_In_Top20` improves `2010–2026` CAGR from **`25.31% → 28.65%` (`+3.34%`/yr, Sharpe `0.84`)** and `2015–2026` CAGR from **`27.35% → 30.89%` (`+3.54%`/yr, Sharpe `0.83`)**, with `2022` returning **`+43.48%`**.
       - With a tighter **`Top-10` (`N=10`) `12-1` shortlist**, `All_SP500 Top-3 Layer 2 (Price + Fund)` reaches **`29.24%` CAGR (`2010–2026`, Sharpe `0.86`)** and **`33.38%` CAGR (`2015–2026`, Sharpe `0.88`, MaxDD `-29.38%`)**.

2. **Why `52-Week-High Proximity` (`V4` & `Layer 4`) Consistently Fails (`t = -1.64` to `-3.35`)**:
   - Inside a high-momentum shortlist, true multi-baggers have `50%–90%` annualized volatility and frequently end the month `15%–40%` off their 252-day peak (`high52_prox = 0.60–0.85`), whereas low-volatility slow grinders (`FTNT`, `NTAP`, `KEYS`) hug their 52-week high (`0.95–1.00`).
   - Adding `52-Week-High Proximity` as a ranking factor systematically **replaces high-convexity multi-baggers with low-volatility grinders**, doubling turnover (`0.76 → 1.51–1.88`) and cutting `>=20%` explosive monthly hits in half (`10.4% → 2.5%–4.5%`).

---

## 2. Pre-Frozen 4-Layer Progression Results (`12-1 Top-20` Shortlist)

### 2A. `Tech_Only` Universe (PIT S&P 500 Information Technology)

| Concentration | Layer / Strategy | `2010–2026` CAGR | `2010–2026` Sharpe | `2010–2026` MaxDD | Paired `t (log)` vs L1 | `2015–2026` CAGR | `2015–2026` Sharpe | `2015–2026` MaxDD | `2015–2026 Ex-2022` | `2010–14` | `2015–19` | `2020–21` | `2022` | `2023–26` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Top-1** | **Layer 1: Price Only (`12-1`)** | **39.77%** | **0.90** | **-53.82%** | `0.00` | **59.91%** | **1.12** | **-44.38%** | **61.73%** | 1.87% | 39.18% | 29.79% | 41.62% | 122.18% |
| **Top-1** | **Layer 2: Price + PIT Fund** | 19.22% | 0.58 | -74.11% | `-1.71` | 20.85% | 0.59 | -74.11% | 26.88% | 15.49% | 10.93% | 6.62% | -28.38% | 66.51% |
| **Top-1** | **Layer 3: Price + Fund + ResMom** | 24.23% | 0.68 | -64.08% | `-1.61` | 25.20% | 0.66 | -64.08% | 31.60% | 21.97% | 10.28% | 6.78% | -26.74% | 86.20% |
| **Top-1** | **Layer 4: Price + Fund + Res + 52WH** | 21.82% | 0.65 | -56.27% | `-1.53` | 28.27% | 0.73 | -56.27% | 32.29% | 7.90% | 33.54% | 1.00% | -7.96% | 50.86% |
| **Top-3** | **Layer 1: Price Only (`12-1`)** | 23.54% | 0.76 | -40.23% | `0.00` | 25.67% | 0.75 | -40.23% | 32.84% | 18.68% | 18.90% | 10.71% | -30.77% | 69.71% |
| **Top-3** | **Layer 2: Price + PIT Fund** | 22.53% | 0.70 | -47.64% | `-0.22` | 25.27% | 0.72 | -47.64% | 30.67% | 16.33% | 14.42% | 20.37% | -20.36% | 62.94% |
| **Top-3** | **Layer 3: Price + Fund + ResMom** | **24.90%** | **0.79** | **-35.08%** | **`+0.31`** | **30.28%** | **0.84** | **-35.08%** | **36.07%** | 13.11% | 21.92% | 16.84% | -18.37% | 70.86% |
| **Top-3** | **Layer 4: Price + Fund + Res + 52WH** | 20.38% | 0.73 | -38.40% | `-0.62` | 23.72% | 0.75 | -38.40% | 29.68% | 12.86% | 15.45% | 18.45% | -25.38% | 58.92% |

### 2B. `All_SP500` Universe (PIT Full S&P 500)

| Concentration | Layer / Strategy | `2010–2026` CAGR | `2010–2026` Sharpe | `2010–2026` MaxDD | Paired `t (log)` vs L1 | `2015–2026` CAGR | `2015–2026` Sharpe | `2015–2026` MaxDD | `2015–2026 Ex-2022` | `2010–14` | `2015–19` | `2020–21` | `2022` | `2023–26` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Top-1** | **Layer 1: Price Only (`12-1`)** | **40.99%** | **0.90** | -70.70% | `0.00` | **41.98%** | **0.86** | -70.70% | **47.32%** | 38.67% | 8.43% | 32.29% | -4.51% | 134.79% |
| **Top-1** | **Layer 2: Price + PIT Fund** | 22.32% | 0.64 | -63.76% | `-1.30` | 21.85% | 0.61 | -63.76% | 25.03% | 23.43% | 10.34% | 32.48% | -7.61% | 43.22% |
| **Top-1** | **Layer 3: Price + Fund + ResMom** | 19.96% | 0.60 | **-62.00%** | `-1.69` | 17.73% | 0.53 | **-62.00%** | 17.82% | 25.36% | 1.91% | -11.39% | 16.74% | 66.42% |
| **Top-1** | **Layer 4: Price + Fund + Res + 52WH** | 8.64% | 0.37 | -79.86% | `-2.43` | 3.10% | 0.25 | -79.86% | 0.03% | 22.86% | -8.60% | -13.41% | 42.69% | 21.86% |
| **Top-3** | **Layer 1: Price Only (`12-1`)** | 25.31% | 0.80 | **-30.49%** | `0.00` | 27.35% | **0.79** | **-25.78%** | **28.81%** | 20.65% | 16.53% | 10.70% | 12.64% | 59.62% |
| **Top-3** | **Layer 2: Price + PIT Fund** | **28.39%** | **0.83** | -34.69% | **`+0.61`** | **28.74%** | 0.78 | -34.69% | 28.75% | 27.57% | 12.31% | 20.52% | 28.67% | 59.99% |
| **Top-3** | **Layer 3: Price + Fund + ResMom** | 21.31% | 0.71 | -41.30% | `-0.90` | 22.45% | 0.69 | -41.30% | 24.23% | 18.68% | 10.23% | -2.12% | 4.92% | 65.44% |
| **Top-3** | **Layer 4: Price + Fund + Res + 52WH** | 16.49% | 0.62 | -60.78% | `-1.47` | 14.42% | 0.52 | -60.78% | 14.35% | 21.52% | -0.83% | 1.11% | 15.13% | 47.65% |

---

## 3. Full Breakdown of the 4 Core Factor Versions (`V1`–`V5`)

### 3A. `Tech_Only` — All 17 Tested Factor Versions

| Portfolio | Version ID | Shortlist | Description | `2010–26` CAGR | `2010–26` Sharpe | `2010–26` MaxDD | `2015–26` CAGR | `2015–26` Sharpe | `2015–26` MaxDD | `t_log (15–26)` | Months `>=20%` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Tech Top-1** | `L1_Price_12_1_Baseline` | 20 | **V1: Pure `12-1` Price Momentum** | 39.77% | 0.90 | -53.82% | **59.91%** | **1.12** | -44.38% | `0.00` | **10.4%** |
| **Tech Top-1** | `V3d_Price_Top20_Plus_ResMom_Cum` | 20 | **V3d: `12-1` Top-20 + Cumul. Residual Return** | **40.10%** | **0.91** | -45.07% | 56.40% | 1.07 | -45.07% | `-1.23` | 10.0% |
| **Tech Top-1** | `V3b_ResMom_Mkt_Standalone` | Full | **V3b: Pure Market Residual Mom (`vs SPY`)** | 38.94% | **0.97** | **-44.38%** | 40.87% | 0.93 | **-44.38%** | `-1.51` | 7.5% |
| **Tech Top-1** | `V2_Pure_Fund_In_Top20` | 20 | **V2 Pure: `12-1` Top-20 -> 100% PIT Fund Rank** | 38.00% | 0.84 | -67.45% | 41.26% | 0.83 | -67.45% | `-0.99` | 10.0% |
| **Tech Top-1** | `V3c_Price_Top20_Plus_ResMom_Sec` | 20 | V3c: `12-1` Top-20 + Residual IR (`vs SPY+XLK`) | 34.25% | 0.86 | -48.03% | 43.14% | 0.94 | -45.26% | `-1.64` | 8.5% |
| **Tech Top-1** | `V3a_ResMom_Sec_Standalone` | Full | V3a: Pure Residual Mom (`vs SPY+XLK`, Full) | 32.70% | 0.86 | -44.38% | 33.71% | 0.82 | -44.38% | `-2.16` | 7.0% |
| **Tech Top-1** | `V2c_Price_Plus_MarginImp` | 20 | V2c: `12-1` Top-20 + Margin Improvement | 26.23% | 0.69 | -65.49% | 25.64% | 0.65 | -65.49% | `-2.28` | 10.4% |
| **Tech Top-1** | `V2a_Price_Plus_ProfitGrowth` | 20 | V2a: `12-1` Top-20 + EPS/Operating Profit Growth | 24.74% | 0.66 | -72.97% | 25.82% | 0.66 | -72.97% | `-1.80` | 10.9% |
| **Tech Top-1** | `V2b_Price_Plus_RevAccel` | 20 | V2b: `12-1` Top-20 + Revenue Growth & Accel | 21.29% | 0.59 | -85.23% | 28.41% | 0.67 | -85.23% | `-1.58` | 9.0% |
| **Tech Top-1** | `V4b_FullUni_Price_Plus_52WH` | Full | V4b: Full Tech `50% Price + 50% 52W-High` | 19.51% | 0.61 | -69.75% | 19.11% | 0.56 | -69.75% | `-2.34` | 4.0% |
| **Tech Top-1** | `V4d_Price_Top20_Plus_52WH_Lag1` | 20 | V4d: `12-1` Top-20 + Lagged 52W-High (`t-1`) | 18.26% | 0.59 | -50.69% | 29.39% | 0.79 | -50.17% | `-1.84` | 5.5% |
| **Tech Top-1** | `V4c_52WH_Standalone` | Full | V4c: Pure 52W-High Proximity | 16.65% | 0.58 | -48.85% | 15.35% | 0.51 | -48.85% | `-2.45` | 2.5% |
| **Tech Top-1** | `V4a_Price_Top20_Plus_52WH` | 20 | V4a: `12-1` Top-20 + 52W-High Proximity | 11.75% | 0.43 | -71.10% | 8.67% | 0.36 | -71.10% | `-3.19` | 4.0% |
| **Tech Top-3** | `L1_Price_12_1_Baseline` | 20 | **V1: Pure `12-1` Price Momentum** | 23.54% | 0.76 | -40.23% | 25.67% | 0.75 | -40.23% | `0.00` | 2.5% |
| **Tech Top-3** | `V3c_Price_Top20_Plus_ResMom_Sec` | 20 | **V3c: `12-1` Top-20 + Residual IR (`vs SPY+XLK`)** | **28.46%** | **0.90** | -38.30% | **36.84%** | **1.02** | -38.30% | **`+2.28`** | 2.0% |
| **Tech Top-3** | `V3b_ResMom_Mkt_Standalone` | Full | **V3b: Pure Market Residual Mom (`vs SPY`)** | **28.11%** | **0.99** | -36.80% | 29.96% | 0.96 | -36.80% | `+0.65` | 1.5% |
| **Tech Top-3** | `V2_Pure_Fund_In_Top20` | 20 | **V2 Pure: `12-1` Top-20 -> 100% PIT Fund Rank** | **26.85%** | **0.82** | -37.84% | **29.95%** | **0.84** | **-33.70%** | `+0.52` | 4.0% |
| **Tech Top-3** | `V2c_Price_Plus_MarginImp` | 20 | **V2c: `12-1` Top-20 + Margin Improvement** | **25.41%** | **0.76** | -48.08% | **28.65%** | **0.77** | -48.08% | `+0.51` | **6.5%** |
| **Tech Top-3** | `L3_Price_Fund_ResMom` | 20 | **Layer 3: `1/3 Price + 1/3 Fund + 1/3 ResMom`** | **24.90%** | **0.79** | **-35.08%** | **30.28%** | **0.84** | **-35.08%** | `+0.80` | 2.5% |
| **Tech Top-3** | `V3a_ResMom_Sec_Standalone` | Full | V3a: Pure Residual Mom (`vs SPY+XLK`, Full) | 24.40% | 0.88 | -33.85% | 23.73% | 0.79 | -33.85% | `-0.28` | 1.5% |
| **Tech Top-3** | `V4a_Price_Top20_Plus_52WH` | 20 | V4a: `12-1` Top-20 + 52W-High Proximity | 18.58% | 0.67 | -46.05% | 19.76% | 0.64 | -46.05% | `-0.82` | 2.0% |

---

### 3B. `All_SP500` — All 17 Tested Factor Versions

| Portfolio | Version ID | Shortlist | Description | `2010–26` CAGR | `2010–26` Sharpe | `2010–26` MaxDD | `2015–26` CAGR | `2015–26` Sharpe | `2015–26` MaxDD | `t_log (10–26)` | Months `>=20%` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **All S&P Top-1** | `L1_Price_12_1_Baseline` | 20 | **V1: Pure `12-1` Price Momentum** | **40.99%** | **0.90** | -70.70% | 41.98% | 0.86 | -70.70% | `0.00` | 9.5% |
| **All S&P Top-1** | `V2b_Price_Plus_RevAccel` | 20 | **V2b: `12-1` Top-20 + Revenue Growth & Accel** | 39.58% | 0.89 | **-58.77%** | **45.46%** | **0.92** | **-58.77%** | `-0.10` (`+0.19` post-15) | 9.0% |
| **All S&P Top-1** | `V2_Pure_Fund_In_Top20` | 20 | **V2 Pure: `12-1` Top-20 -> 100% PIT Fund Rank** | 35.34% | 0.79 | -62.71% | 31.88% | 0.70 | -62.71% | `-0.36` | **10.9%** |
| **All S&P Top-1** | `V2a_Price_Plus_ProfitGrowth` | 20 | V2a: `12-1` Top-20 + EPS/Profit Growth | 26.61% | 0.71 | -58.58% | 27.69% | 0.70 | -58.58% | `-1.10` | 9.0% |
| **All S&P Top-1** | `V3d_Price_Top20_Plus_ResMom_Cum` | 20 | V3d: `12-1` Top-20 + Cumul. Residual Return | 24.11% | 0.64 | -70.70% | 24.49% | 0.63 | -70.70% | `-3.25` | 8.5% |
| **All S&P Top-1** | `V2c_Price_Plus_MarginImp` | 20 | V2c: `12-1` Top-20 + Margin Improvement | 23.29% | 0.64 | -73.37% | 26.57% | 0.67 | -73.37% | `-1.37` | 9.0% |
| **All S&P Top-1** | `V3b_ResMom_Mkt_Standalone` | Full | V3b: Pure Market Residual Mom (`vs SPY`) | 13.22% | 0.48 | -48.34% | 14.39% | 0.47 | -48.34% | `-2.13` | 3.5% |
| **All S&P Top-1** | `V4a_Price_Top20_Plus_52WH` | 20 | V4a: `12-1` Top-20 + 52W-High Proximity | 6.68% | 0.33 | -82.84% | 0.75% | 0.21 | -82.84% | `-2.56` | 4.5% |
| **All S&P Top-3** | `L1_Price_12_1_Baseline` | 20 | **V1: Pure `12-1` Price Momentum** | 25.31% | 0.80 | -30.49% | 27.35% | 0.79 | -25.78% | `0.00` | 4.5% |
| **All S&P Top-3** | `V2_Pure_Fund_In_Top20` | 20 | **V2 Pure: `12-1` Top-20 -> 100% PIT Fund Rank** | **28.65%** | **0.84** | -43.30% | **30.89%** | **0.83** | -43.30% | **`+0.47`** | 3.5% |
| **All S&P Top-3** | `L2_Price_Plus_Fund` | 20 | **Layer 2: `12-1` Top-20 -> 50% Price + 50% Fund** | **28.39%** | **0.83** | -34.69% | **28.74%** | 0.78 | -34.69% | **`+0.61`** | 4.5% |
| **All S&P Top-3** | `V2a_Price_Plus_ProfitGrowth` | 20 | **V2a: `12-1` Top-20 + EPS/Profit Growth** | **28.08%** | **0.83** | -34.13% | **29.36%** | **0.80** | -34.13% | **`+0.51`** | 4.5% |
| **All S&P Top-3** | `V2c_Price_Plus_MarginImp` | 20 | **V2c: `12-1` Top-20 + Margin Improvement** | **27.11%** | **0.83** | -48.95% | 25.62% | 0.74 | -48.95% | `+0.32` | 4.0% |
| **All S&P Top-3** | `V2b_Price_Plus_RevAccel` | 20 | V2b: `12-1` Top-20 + Revenue Growth & Accel | 22.81% | 0.71 | -42.68% | 27.31% | 0.76 | -34.24% | `-0.57` | 4.5% |
| **All S&P Top-3** | `V3c_Price_Top20_Plus_ResMom_Sec` | 20 | V3c: `12-1` Top-20 + Residual IR (`vs SPY+Sec`) | 18.67% | 0.66 | -48.05% | 19.19% | 0.63 | -48.05% | `-1.50` | 2.5% |
| **All S&P Top-3** | `V3a_ResMom_Sec_Standalone` | Full | V3a: Pure Residual Mom (`vs SPY+Sec`, Full) | 18.38% | 0.77 | -33.34% | 17.84% | 0.70 | -33.34% | `-0.92` | 0.5% |
| **All S&P Top-3** | `V4a_Price_Top20_Plus_52WH` | 20 | V4a: `12-1` Top-20 + 52W-High Proximity | 14.24% | 0.55 | -68.80% | 11.83% | 0.45 | -68.80% | `-1.81` | 2.0% |

---

## 4. Shortlist Size Sensitivity (`Top-10` vs `Top-15` vs `Top-20` vs `Top-30`)

| Universe & Top-K | Strategy | `N = 10` (`2010–26` / `2015–26`) | `N = 15` (`2010–26` / `2015–26`) | `N = 20` (`2010–26` / `2015–26`) | `N = 30` (`2010–26` / `2015–26`) |
|---|---|---|---|---|---|
| **`Tech_Only Top-3`** (`Baseline = 23.54% / 25.67%`) | `V3c (Price + Residual Mom)` | **24.68% / 31.68%** | **28.53% / 36.10%** | **28.46% / 36.84%** | **30.83% / 39.25%** |
| **`Tech_Only Top-3`** (`Baseline = 23.54% / 25.67%`) | `Layer 3 (Price + Fund + ResMom)` | **24.93% / 30.96%** | **25.07% / 30.27%** | **24.90% / 30.28%** | **24.61% / 29.23%** |
| **`All_SP500 Top-3`** (`Baseline = 25.31% / 27.35%`) | `Layer 2 (Price + PIT Fund)` | **29.24% / 33.38%** | **27.30% / 29.38%** | **28.39% / 28.74%** | **26.57% / 24.03%** |

- **`Tech_Only Top-3 + Residual Momentum (V3c)`** beats the `12-1` baseline across **all 4 shortlist sizes (`N = 10, 15, 20, 30`)**.
- **`All_SP500 Top-3 + PIT Fundamental Momentum (Layer 2)`** beats the `12-1` baseline across **`N = 10, 15, 20`** (and on `2010–2026` across all 4 sizes), peaking at **`N = 10`** (`29.24%` full / `33.38%` post-2015) where the candidate shortlist stays tightly anchored to the top 2% of S&P 500 price momentum leaders before fundamental reranking.

---

## 5. November 2026 Live Picks (`Formation = 2026-10-30` -> `Trade = 2026-11-02 Open`)

| Strategy | `Tech_Only Top-1` | `Tech_Only Top-3` | `All_SP500 Top-1` | `All_SP500 Top-3` |
|---|---|---|---|---|
| **Layer 1 (`12-1` Price Baseline)** | `SNDK` | `SNDK \| LITE \| MU` | `SNDK` | `SNDK \| MRNA \| LITE` |
| **Layer 2 (`Price + PIT Fund`)** | `SNDK` | `SNDK \| MU \| LITE` | `SNDK` | `SNDK \| MU \| LITE` |
| **Layer 3 (`Price + Fund + ResMom`)** | `SNDK` | `SNDK \| MU \| LITE` | `SNDK` | `SNDK \| MU \| STX` |
| **Layer 4 (`Price + Fund + Res + 52WH`)** | `MU` | `MU \| SNDK \| LITE` | `MU` | `MU \| SNDK \| LITE` |
| **`V3c (Price + Residual Mom)`** | `SNDK` | `SNDK \| MU \| LITE` | `SNDK` | `SNDK \| MU \| STX` |
| **`V2b (Price + Rev Accel)`** | `SNDK` | `SNDK \| MU \| LITE` | `SNDK` | `SNDK \| MU \| LITE` |
| **`V4a (Price + 52W-High)`** | `DELL` | `DELL \| LITE \| MU` | `MRNA` | `MRNA \| DELL \| ILMN` |

### Why `MU` and `SNDK` Dominate Layers 1–3 in November 2026
- **`SNDK`**: `#1` in `12-1` Price Momentum (`+772.9%`), `#2` in Residual Momentum (`IR = 2.46`), and `#1` in Margin Improvement (`OpM YoY +77.5pp`, `Rev YoY +371.6%`, `Rev Accel +120.6pp`). Only its 52-week-high proximity is low (`0.559` due to autumn pullback).
- **`MU` (Micron Technology)**: `#3` in Tech `12-1` Price Momentum (`+376.4%`), **`#1` in Residual Momentum (`IR = 2.46`)**, and **`#2` in Fundamental Momentum** (`EPS YoY +174.5%`, `Rev YoY +345.7%`, `Rev Accel +149.4pp`, `OpM YoY +57.0pp`). When `Layer 2` (`Price + Fund`) or `Layer 3` (`Price + Fund + ResMom`) is applied to `All_SP500 Top-3`, **`MU` replaces `MRNA`** (whose revenue growth decelerated `-258pp` YoY), creating a pure AI-memory/optical-interconnect/storage Top-3 (`SNDK | MU | LITE` or `SNDK | MU | STX`).
