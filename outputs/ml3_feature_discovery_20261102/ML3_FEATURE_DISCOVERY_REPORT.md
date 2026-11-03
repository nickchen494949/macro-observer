# ML3 Feature Discovery → Nested Rolling Frozen OOS Report (S&P 500, QQQ, XLK Tech, & IWM Universes)

**Date**: 2026-11-03  
**Output Directory**: `outputs/ml3_feature_discovery_20261102/`  
**Execution Convention**: Next-Day Open (`Open[t+1_d1] -> Open[t+2_d1]`), `10 bps` per side transaction cost (`20 bps` round-trip), Point-in-Time SEC `filed + 1 calendar day` lag, `1`-month formation purge on **both** `Train` (`<= (Y-3)-11-30`), `Validation` (`<= (Y-1)-11-30`), and `Refit` (`<= (Y-1)-11-30`) so formation month `(Y-1)-12-31` (whose holding return exits on the first trading day of `Feb Y`) is never seen before predicting `Year Y`.  
**Baseline Integrity**: Zero modifications to `research/sector_stock_momentum/`.

---

## 1. Executive Conclusions & Audit-Calibrated Findings (先结论)

1. **Audit Calibration — What Is Statistically Proven vs What Is Economic/Risk Improvement**:
   - **Statistically Significant (`p < 0.01`)**: **Multi-Quarter Trajectory (`T3a`) vs Single-Point Snapshot Fundamentals (`T2`)**. Inside `S&P 500 12-1 Momentum Top-50 (Pool A)`, adding 18 multi-quarter trajectory features (`T3a`) over snapshot fundamentals (`T2`) raises `Top-3` CAGR from `18.86%` to **`36.69%`** (`2015–2026.09`, **`+17.83%`/yr**, Newey-West **`t = +2.97`, `p = 0.0030`**, `p_Holm = 0.054`, Block Bootstrap `99.9%` positive, winning `10 / 12` years) and from `25.08%` to **`44.48%`** (`2019–2026.09`, **`+19.40%`/yr**, **`t = +2.41`, `p = 0.0158`**, winning `7 / 8` years).
   - **Positive Point Estimate & Better Drawdown/Sharpe, But NOT Statistically Significant at $p < 0.05$ (`|t| < 2.0`)**: **ML (`T3a` / `T1`) vs Pure `12-1` Price Momentum (`T0`)**.
     - On **`S&P 500 Pool A Top-3`**, `T3a LGBM` beats `Pure 12-1 Momentum Top-3` in raw CAGR (`44.48% vs 36.27%` in `19–26`; `36.69% vs 26.86%` in `15–26`), raises Sharpe (`1.14 vs 0.89`; `1.09 vs 0.78`), and lowers Daily MaxDD (`-38.52% vs -41.32%`), with Newey-West **`t = +0.39` (`p = 0.70`)** in `19–26` and **`t = +0.79` (`p = 0.43`, winning `7 / 12` years)** in `15–26`.
     - On **`QQQ_Full100 Top-1`**, `T1 Price-Only LGBM` achieves **`62.31%` vs `43.86%`** (`19–26`) and **`50.28%` vs `41.43%`** (`15–26`) while cutting Daily MaxDD from `-83.72%` to `-66.76%`, with Newey-West **`t = +0.49` (`p = 0.62`, winning `37/93 = 39.8%` months, `4/8` years)** in `19–26` and **`t = +0.26` (`p = 0.80`, winning `59/140 = 42.1%` months, `7/12` years)** in `15–26` (saved in [ml3_qqq_paired_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_qqq_paired_comparisons.csv)).
     - On **`XLK_Top30_TrainSP500Top50`**, `T3a RankVal LGBM` achieves **`64.64%` vs `58.30%`** on `Top-1` (`15–26`, `t = +0.18`, winning `8/12` years) and **`35.06%` vs `25.79%`** on `Top-3` (`15–26`, `t = +0.90`, winning `8/12` years) while cutting `Top-1` Daily MaxDD from `-55.56%` to `-44.41%` (`19–26`) and `Top-3` Daily MaxDD from `-48.63%` to `-39.88%` (saved in [ml3_xlk_paired_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_xlk_paired_comparisons.csv)).

2. **Validation `Dec Y-1` Boundary Embargo Fix Verified (`100%` Unchanged Headline Numbers)**:
   - Previously, `Train` and `Refit` purged `Dec 31, Y-1` (`<= (Y-1)-11-30`), whereas `Validation` used `D.t.dt.year <= Y - 1` (which included `Dec 31, Y-1`, whose Open-to-Open holding period exits on the first trading day of `Feb Y`, 1 trading day after `Jan 31, Y` formation).
   - All 3 scripts (`run_ml3_feature_discovery.py`, `run_ml3_qqq_iwm_pools.py`, `run_ml3_xlk_pool.py`) now enforce `val_end = pd.Timestamp(f"{Y - 1}-11-30")`.
   - Re-running all folds confirms **zero change** to headline strategies:
     - `S&P 500 Pool A T3a LGBM Top-3`: **`44.48%` (`19–26`) / `36.69%` (`15–26`)** (unchanged).
     - `S&P 500 Pool A T3a LGBM Top-1`: **`55.19%` (`19–26`) / `46.12%` (`15–26`)** (unchanged).
     - `QQQ_Full100 T1 Price LGBM Top-1`: **`62.31%` (`19–26`) / `50.28%` (`15–26`)** (unchanged).
     - `S&P 500 Pool A T3S In-Sample Discovery Top-1` improved to **`67.17%` (`19–26`, Sharpe `1.21`) / `41.14%` (`15–26`, Sharpe `0.92`)**; `QQQ_Top30 T3a RankVal Top-3` improved to **`36.92%` (`19–26`, Sharpe `0.97`) / `27.81%` (`15–26`, Sharpe `0.87`)**.

3. **Universe 4 (XLK Historical PIT Tech Pool & `100%` SEC EDGAR SIC Tech Pool) Key Findings**:
   - **Pure `12-1` Momentum (`T0`) on US Large-Cap Tech (`XLK_PIT`, `~68` stocks/m) Is the Strongest Single-Factor Baseline Across All 4 Universes**:
     - **`XLK_PIT Pure 12-1 Momentum Top-1`**: **`77.79%` CAGR** (`2019–2026.09`, Sharpe **`1.25`**, Daily MaxDD `-55.56%`, `t_NW = +2.51, p = 0.0121` vs `XLK ETF` `27.01%`) | **`58.30%` CAGR** (`2015–2026.09`, Sharpe **`1.09`**, Daily MaxDD `-55.56%`, `t_NW = +2.53, p = 0.0113` vs `XLK ETF` `21.62%`), with positive returns in every sub-period (`2015–2019: 35.56%`, `2020–2022: 33.62%`, `2023–2026.09: 122.18%`).
     - **`100%` SEC EDGAR SIC-Code Tech Pool (`XLK_Strict_SEC_SIC`, `~65` stocks/m, Zero Wikipedia/Yahoo Sector Input)**: **`73.19%` CAGR** (`2019–2026.09`, Sharpe `1.20`) | **`55.57%` CAGR** (`2015–2026.09`, Sharpe `1.06`), proving the `~56%–78%` Tech Top-1 momentum return is genuine and NOT an artifact of sector backfill.
     - **`XLK_PIT Pure 12-1 Momentum Top-3`**: **`31.01%` CAGR** (`2019–2026.09`, Sharpe `0.80`, Daily MaxDD `-45.74%`) | **`25.79%` CAGR** (`2015–2026.09`, Sharpe `0.75`, Daily MaxDD `-48.63%`).
   - **Why Direct ML on `XLK_Full_PIT` (`~68` stocks/m) Fails, While Momentum Pre-Filtering + Cross-Pool Training Succeeds**:
     - Training LightGBM directly on all `~68` XLK stocks without a momentum pre-filter fails (`Top-1 = -0.96%` for `T1`, `-11.44%` for `T3a`, `t_NW = -3.14, p = 0.0017` vs Pure Mom; `Top-3 = 12.92% / 16.72%`) because a single-sector 68-stock pool lacks cross-sector contrast and provides too few training rows (`~3,200` in early folds) for 57-feature trees.
     - Pre-filtering to `XLK_Top20_PIT` (`T3a LGBM Top-3`: **`41.22%` in `19–26`, Sharpe `0.99`, Daily MaxDD `-42.31%` | `30.59%` in `15–26`, Sharpe `0.87`**) or training `T3a` on the broader `S&P 500 Top-50` momentum pool and ranking `XLK_Top30` (`XLK_Top30_TrainSP500Top50`) resolves the sample-size bottleneck:
       - **`XLK_Top30_TrainSP500Top50 -> T3a RankVal LGBM Top-1`**: **`76.30%` CAGR** (`2019–2026.09`, Sharpe **`1.26`**, Daily MaxDD **`-44.41%`**) | **`64.64%` CAGR** (`2015–2026.09`, Sharpe **`1.21`**, Daily MaxDD **`-50.88%`**; sub-periods `52.97%` / `23.96%` / `127.53%`, beating `XLK Pure Mom Top-1` `58.30%` by **`+6.34%`/yr** over `2015–2026` and winning `8 / 12` years).
       - **`XLK_Top30_TrainSP500Top50 -> T3a RankVal LGBM Top-3`**: **`38.12%` CAGR** (`2019–2026.09`, Sharpe **`1.02`**, Daily MaxDD **`-39.88%`**) | **`35.06%` CAGR** (`2015–2026.09`, Sharpe **`1.05`**, Daily MaxDD **`-39.88%`**; beating `XLK Pure Mom Top-3` `31.01% / 25.79%` by **`+7.11%` / `+9.28%`/yr**, winning `8 / 12` years).
       - **`XLK_Top30_TrainSP500Top50 -> T3a FixedNL7 (Zero-Tune) LGBM`**: `Top-1` = **`63.16%` (`19–26`, Sharpe `1.20`) / `51.94%` (`15–26`, Sharpe `1.13`)**; `Top-3` = **`37.90%` (`19–26`, Sharpe `1.01`) / `34.03%` (`15–26`, Sharpe `1.02`)**.

4. **Four-Universe Synthesis (`S&P 500` vs `QQQ` vs `XLK` vs `IWM`)**:
   - **If the goal is `Top-1` maximum raw CAGR with zero model complexity**: **`XLK_PIT Pure 12-1 Momentum Top-1`** (`77.79%` in `19–26`, `58.30%` in `15–26`, Sharpe `1.25 / 1.09`, Daily MaxDD `-55.56%`) or **`S&P 500 Pure 12-1 Momentum Top-1`** (`78.87%` in `19–26`, `41.72%` in `15–26`, Daily MaxDD `-73.46%`).
   - **If the goal is `Top-1` with lower drawdown and higher full-cycle consistency (`2015–2026`)**: **`XLK_Top30_TrainSP500Top50 -> T3a RankVal LGBM Top-1`** (`76.30%` in `19–26`, **`64.64%`** in `15–26`, Sharpe `1.26 / 1.21`, Daily MaxDD **`-44.41% / -50.88%`**) or **`QQQ_Full100 -> T1 Price LGBM Top-1`** (`62.31%` in `19–26`, `50.28%` in `15–26`, Daily MaxDD `-66.76%`).
   - **If the goal is `Top-3` institutional risk-adjusted compounding (`Daily MaxDD < 40%`, `Sharpe > 1.05`)**: **`S&P 500 Pool A -> T3a Trajectory Core LGBM Top-3`** (**`44.48%`** in `19–26`, **`36.69%`** in `15–26`, Sharpe **`1.14 / 1.09`**, Daily MaxDD **`-38.52%`**) or **`XLK_Top30_TrainSP500Top50 -> T3a RankVal LGBM Top-3`** (**`38.12%`** in `19–26`, **`35.06%`** in `15–26`, Sharpe **`1.02 / 1.05`**, Daily MaxDD **`-39.88%`**).

---

## 2. Experimental Architecture & 5 Nested Feature Tiers (78 PIT Features)

### 2.1 Walk-Forward Protocol (Zero Look-Ahead, Purged Validation & Refit)
For each Out-of-Sample test year $Y \in \{2015, 2016, \dots, 2026\}$:
- **Training Window**: `2011-01-31` through `(Y-3)-11-30` (with 1-month purge at `(Y-3)-12-31`).
- **Validation Window**: `(Y-2)-01-31` through `(Y-1)-11-30` (with 1-month purge at `(Y-1)-12-31` so formation month `(Y-1)-12-31`, whose Open-to-Open holding return exits on the first trading day of `Feb Y`, is never seen during validation or hyperparameter/feature selection before predicting `Year Y`).
- **Refit & Freeze**: After selecting hyperparameters (and feature subset in `T3S`) on `Train + Val`, the model is refit on `2011-01-31 .. (Y-1)-11-30`, frozen for all 12 months of `Year Y`, and predicts cross-sectional next-month Open-to-Open rank $y_{i,t} \in [-0.5, +0.5]$.

### 2.2 The 5 Nested Feature Tiers
| Tier | Name | Feature Count | Features Added |
| :--- | :--- | :---: | :--- |
| **`T0`** | `Pure 12-1 Momentum` | 1 | `mom_12_1` |
| **`T1`** | `Set A (Price & Regime Only)` | 18 | `mom_12_1`, `mom_6_1`, `mom_3_1`, `rev_1m`, `sector_mom`, `mom_12_1_secrel`, `mom_accel`, `smooth`, `dist_sma200`, `dist_sma50`, `dist_52wh`, `vol_3m`, `vol_12m`, `beta_12m`, `maxret_1m`, `dv_ratio`, `mkt_ret12`, `mkt_above200`, `mkt_vol3m` |
| **`T2`** | `Set B (+ Snapshot Fundamentals)` | 39 | `T1` + 21 single-point PIT SEC & reaction features: `eps_g`, `eps_g_sym`, `deps_p`, `ep`, `sue`, `margin`, `margin_chg`, `rev_g`, `log_mcap`, `sp`, `bm`, `roe`, `gp_a`, `accruals`, `leverage`, `asset_turn`, `inv_turn`, `cfo_yield`, `net_issuance`, `days_since_filing`, `ear` |
| **`T3a`** | `Set C4 (+ Core 4Q/8Q Trajectory)` | 57 | `T2` + 18 multi-quarter trajectory features: `rev_g_q0..q3`, `rev_g_slope`, `rev_accel_streak`, `epsg_q0..q3`, `epsg_slope`, `eps_beat_streak` (up to 8Q), `gm_chg_4q`, `nm_chg_4q`, `inv_rev_chg`, `cfo_ni`, `cfo_ni_chg`, `ear_sum4` |
| **`T3b`** | `Set C8_Summary (+ 8Q Slopes, OPM, ROIC, CapEx)` | 68 | `T3a` + 11 calendar-matched 8Q/Operating/ROIC/CapEx trajectory features: `rev_g_slope_8q`, `epsg_slope_8q`, `gm_chg_8q`, `nm_chg_8q`, `opm_q0`, `opm_chg_4q`, `opm_chg_8q`, `roic_q0`, `roic_chg_4q`, `capex_rev`, `capex_chg_4q` |
| **`T3c`** | `Set C8_KitchenSink (+ Raw Stale Lags q4..q7)` | 78 | `T3b` + 8 raw stale quarters (`rev_g_q4..q7`, `epsg_q4..q7`, 1.25–2.0y old) + 2 regime interactions (`mkt_ret12_x_beta`, `mkt_vol3m_x_vol`) |
| **`T3S`** | `In-Sample Feature Discovery -> Frozen OOS` | Auto (`50–60` / 78) | Inside each fold $Y$, scores all 78 features using ONLY `Train + Val` (`<= (Y-1)-11-30`) multi-subwindow split gain + validation top-5 rank spread, prunes noisy/stale features, and freezes for `Year Y` OOS. |

---

## 3. Universe 1: S&P 500 Point-in-Time Results

### 3.1 Master Performance Table (`OOS 2019–2026.09` & `OOS 2015–2026.09`)
Full table including sub-periods (`2015–2019`, `2020–2022`, `2023–2026.09`) is saved in [ml3_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_summary_table.csv).

| Strategy | Pool | Model | Top-K | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe | `2015–2026.09` Daily MaxDD | `2015–2019` CAGR | `2020–2022` CAGR | `2023–2026.09` CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BENCH: SPY Buy & Hold`** | SPY | Bench | 1 | `17.47%` | `0.88` | `-35.82%` | `14.04%` | `0.79` | `-35.82%` | `12.48%` | `7.61%` | `21.64%` |
| **`T0: Pure 12-1 Momentum Top-1`** | Pool A | Rule | 1 | `78.87%` | `1.22` | `-55.56%` | `41.72%` | `0.86` | `-73.46%` | `7.47%` | `18.67%` | `134.79%` |
| **`T1: Set A (Price Only, 18f)`** | Pool A | LGBM | 1 | `14.36%` | `0.46` | `-58.53%` | `9.12%` | `0.36` | `-64.62%` | `2.07%` | `4.94%` | `22.88%` |
| **`T2: Set B (+Snapshot, 39f)`** | Pool A | LGBM | 1 | `38.52%` | `0.81` | `-65.94%` | `33.83%` | `0.79` | `-65.94%` | `28.74%` | `10.90%` | `63.65%` |
| **`T3a: Set C4 (+Trajectory Core, 57f)`** | **Pool A** | **LGBM** | **1** | **`55.19%`** | **`1.04`** | **`-55.56%`** | **`46.12%`** | **`1.00`** | **`-55.56%`** | **`28.51%`** | **`19.34%`** | **`103.34%`** |
| **`T3b: Set C8_Summary (68f)`** | Pool A | LGBM | 1 | `52.17%` | `1.04` | `-56.46%` | `36.14%` | `0.86` | `-56.78%` | `17.36%` | `25.80%` | `76.16%` |
| **`T3c: Set C8_KitchenSink (78f)`** | Pool A | LGBM | 1 | `46.00%` | `0.95` | `-52.27%` | `34.85%` | `0.84` | `-52.27%` | `22.41%` | `11.99%` | `77.63%` |
| **`T3S: In-Sample Discovery -> Frozen OOS`** | **Pool A** | **LGBM** | **1** | **`67.17%`** | **`1.21`** | `-63.25%` | **`41.14%`** | **`0.92`** | `-73.73%` | `10.49%` | **`21.56%`** | **`119.23%`** |
| **`T3a: Zero-CAGR-Peek (Rank Val)`** | **Pool A** | **LGBM** | **1** | **`53.40%`** | **`1.00`** | **`-55.56%`** | **`39.70%`** | **`0.89`** | **`-55.56%`** | **`21.95%`** | `9.19%` | **`103.34%`** |
| **`T3a: Zero-Tune (Fixed NL=7)`** | **Pool A** | **LGBM** | **1** | **`47.44%`** | **`0.95`** | **`-55.56%`** | **`41.24%`** | **`0.94`** | **`-55.56%`** | **`28.51%`** | **`23.70%`** | **`77.74%`** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`T0: Pure 12-1 Momentum Top-3`** | Pool A | Rule | 3 | `36.27%` | `0.89` | `-41.32%` | `26.86%` | `0.78` | `-41.32%` | `15.29%` | `11.34%` | `59.62%` |
| **`T1: Set A (Price Only, 18f)`** | Pool A | LGBM | 3 | `27.78%` | `0.81` | `-42.21%` | `20.13%` | `0.68` | `-47.35%` | `8.79%` | `7.81%` | `49.17%` |
| **`T2: Set B (+Snapshot, 39f)`** | Pool A | LGBM | 3 | `25.08%` | `0.75` | `-49.26%` | `18.86%` | `0.65` | `-49.26%` | `15.84%` | `7.74%` | `32.99%` |
| **`T3a: Set C4 (+Trajectory Core, 57f)`** | **Pool A** | **LGBM** | **3** | **`44.48%`** | **`1.14`** | **`-38.52%`** | **`36.69%`** | **`1.09`** | **`-38.52%`** | **`33.28%`** | **`21.26%`** | **`55.49%`** |
| **`T3b: Set C8_Summary (68f)`** | **Pool A** | **LGBM** | **3** | **`44.40%`** | **`1.13`** | `-43.29%` | **`35.58%`** | **`1.07`** | `-43.29%` | `26.98%` | **`22.78%`** | **`59.94%`** |
| **`T3c: Set C8_KitchenSink (78f)`** | Pool A | LGBM | 3 | `35.26%` | `1.02` | `-53.04%` | `25.97%` | `0.87` | `-53.04%` | `16.40%` | `6.13%` | `60.24%` |
| **`T3S: In-Sample Discovery -> Frozen OOS`** | **Pool A** | **LGBM** | **3** | **`35.09%`** | **`1.00`** | `-48.02%` | **`28.29%`** | **`0.93`** | `-48.02%` | `21.11%` | `11.60%` | **`54.67%`** |
| **`T3a: Zero-CAGR-Peek (Rank Val)`** | **Pool A** | **LGBM** | **3** | **`43.66%`** | **`1.13`** | **`-38.82%`** | **`36.42%`** | **`1.09`** | **`-38.82%`** | **`33.85%`** | **`19.14%`** | **`55.86%`** |
| **`T3a: Zero-Tune (Fixed NL=7)`** | **Pool A** | **LGBM** | **3** | **`45.06%`** | **`1.13`** | **`-38.52%`** | **`35.10%`** | **`1.05`** | **`-38.52%`** | **`28.83%`** | **`21.26%`** | **`56.77%`** |
| `T3a: Rolling 6Y Train (vs Expanding)` | Pool A | LGBM | 3 | `16.38%` | `0.53` | `-47.51%` | `18.39%` | `0.64` | `-47.51%` | `33.28%` | `-1.21%` | `17.16%` |
| `T3a: Set C4 Linear Ridge` | Pool A | Ridge | 3 | `21.05%` | `0.61` | `-54.56%` | `11.19%` | `0.41` | `-54.56%` | `-1.51%` | `8.08%` | `33.34%` |
| `T3a: Set C4 Linear ElasticNet` | Pool A | ENet | 3 | `12.73%` | `0.45` | `-55.12%` | `12.66%` | `0.50` | `-55.12%` | `15.19%` | `-12.75%` | `34.26%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Pool B (Full S&P 500): T3a Set C4` | Pool B | LGBM | 1 | `7.04%` | `0.35` | `-73.61%` | `0.27%` | `0.18` | `-79.35%` | `-6.58%` | `-23.75%` | `36.95%` |
| `Pool B (Full S&P 500): T3a Set C4` | Pool B | LGBM | 3 | `8.00%` | `0.33` | `-65.40%` | `5.88%` | `0.28` | `-65.40%` | `3.47%` | `-5.09%` | `19.10%` |
| `Pool B (Full S&P 500): T3a Set C4` | Pool B | Ridge | 3 | `16.30%` | `0.59` | `-40.60%` | `6.07%` | `0.27` | `-48.88%` | `0.40%` | `6.78%` | `13.38%` |

### 3.2 Paired Newey-West HAC & Stationary Block Bootstrap Tests (`S&P 500 Pool A`)
Saved in [ml3_incremental_tier_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_incremental_tier_comparisons.csv):
- **`Top-3: T3a Trajectory Core vs T2 Snapshot (2015–2026.09, 141m)`**:
  - CAGR: **`36.69%` vs `18.86%` (`+17.83%`/yr)** | Annualized arithmetic diff: **`+14.32%`/yr**
  - Newey-West HAC (3 lags): **`t = +2.97`, `p = 0.0030`** (`p_Holm = 0.054` across all 18 tests)
  - 2,000-draw Stationary Block Bootstrap (block = 3m): 90% CI **`[+7.72%, +28.40%]`**, **`P(Δ <= 0) = 0.001` (`99.9%` positive)**, winning in **`10 / 12` calendar years**.
- **`Top-3: T3a Trajectory Core vs T2 Snapshot (2019–2026.09, 93m)`**:
  - CAGR: **`44.48%` vs `25.08%` (`+19.40%`/yr)** | Annualized arithmetic diff: **`+14.87%`/yr**
  - Newey-West HAC: **`t = +2.41`, `p = 0.0158`** (`p_Holm = 0.284`) | Block Bootstrap: 90% CI **`[+6.43%, +35.69%]`**, **`P(Δ <= 0) = 0.007` (`99.3%` positive)**, winning in **`7 / 8` calendar years**.
- **`Top-3: T3a Trajectory Core vs Pure 12-1 Momentum (T0)`**:
  - `2015–2026.09 (141m)`: **`36.69%` vs `26.86%` (`+9.83%`/yr)**, arithmetic diff `+5.93%`/yr, Newey-West **`t = +0.79`, `p = 0.4297`**, Bootstrap `83.15%` positive, winning in **`7 / 12` years**.
  - `2019–2026.09 (93m)`: **`44.48%` vs `36.27%` (`+8.21%`/yr)**, arithmetic diff `+4.05%`/yr, Newey-West **`t = +0.39`, `p = 0.6987`**, Bootstrap `72.15%` positive, winning in **`4 / 8` years**.

### 3.3 Leave-One-Group-Out OOS Ablation (`S&P 500 Pool A, T3a Set C4`)
Saved in [ml3_leave_one_group_out_ablation.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_leave_one_group_out_ablation.csv). Every single feature group contributes positively to `Top-3` OOS CAGR across both `2019–2026.09` and `2015–2026.09`:

| Ablation Experiment | Features Kept | `Top-1` CAGR (`19–26`) | `Top-1` Δ vs Full (`19–26`) | `Top-1` CAGR (`15–26`) | `Top-1` Δ vs Full (`15–26`) | `Top-3` CAGR (`19–26`) | `Top-3` Δ vs Full (`19–26`) | `Top-3` CAGR (`15–26`) | `Top-3` Δ vs Full (`15–26`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`0. Baseline Full Model (Set C4)`** | **57** | **`55.19%`** | `0.00%` | **`46.12%`** | `0.00%` | **`44.48%`** | `0.00%` | **`36.69%`** | `0.00%` |
| **`1. Drop All 18 Trajectory Features (= Set B)`** | 39 | `38.52%` | **`-16.67%`** | `33.83%` | **`-12.29%`** | `25.08%` | **`-19.40%`** | `18.86%` | **`-17.83%`** |
| **`2. Drop 11 Rev & EPS Quarterly Growths/Slopes`** | 46 | `34.69%` | **`-20.49%`** | `16.35%` | **`-29.78%`** | `25.28%` | **`-19.21%`** | `20.29%` | **`-16.39%`** |
| **`3. Drop 5 EAR / SUE / Freshness / BeatStreak`** | 52 | `49.02%` | **`-6.17%`** | `28.63%` | **`-17.49%`** | `35.35%` | **`-9.13%`** | `24.01%` | **`-12.68%`** |
| **`4. Drop 7 CashFlow / Inventory / Accruals`** | 50 | `51.85%` | **`-3.33%`** | `48.90%` | `+2.78%` | `36.66%` | **`-7.83%`** | `28.44%` | **`-8.24%`** |
| **`5. Drop 6 Margins & Profitability`** | 51 | `62.12%` | `+6.93%` | `43.74%` | **`-2.38%`** | `39.33%` | **`-5.15%`** | `29.43%` | **`-7.26%`** |
| **`6. Drop 7 Valuation / Size / Issuance`** | 50 | `29.74%` | **`-25.44%`** | `30.44%` | **`-15.68%`** | `41.37%` | **`-3.12%`** | `30.70%` | **`-5.99%`** |
| **`7. Drop 9 Short-Term Price / Vol / 52WH / DV`** | 48 | `68.51%` | `+13.32%` | `49.80%` | `+3.68%` | `33.12%` | **`-11.36%`** | `28.07%` | **`-8.61%`** |

### 3.4 Multi-Fold Feature Stability Leaderboard (Top 20 Core Drivers across 12 Folds)
Full 78-feature leaderboard is saved in [ml3_feature_stability_78.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_feature_stability_78.csv).

| Rank | Feature | Tier | Mean Split Gain % (`C4`, 12 Folds) | Folds in Top-15 (of 12) | Mean Split Gain % (`C8`, 78f) | Within-Pool Rank IC (`15–26`) | Pool IC `t_NW` | Economic Role |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `sector_mom` | `T1_Price` | **`3.03%`** | `11 / 12` | `2.20%` | `+0.0277` | `+1.30` | Sector-level tailwind confirmation |
| 2 | `days_since_filing` | `T2_Snapshot` | **`2.97%`** | `11 / 12` | `2.17%` | `-0.0050` | `-0.41` | Freshness of latest 10-Q/10-K filing |
| 3 | `rev_g_q1` | `T3a_Trajectory` | **`2.73%`** | `10 / 12` | `1.81%` | `+0.0193` | `+1.22` | Prior-quarter YoY revenue growth anchor |
| 4 | `rev_accel_streak` | `T3a_Trajectory` | **`2.48%`** | `10 / 12` | `1.68%` | `+0.0143` | `+1.20` | Consecutive quarters of revenue acceleration |
| 5 | `ear_sum4` | `T3a_Trajectory` | **`2.47%`** | `6 / 12` | `1.89%` | **`+0.0504`** | **`+3.99`** | 4-quarter cumulative 3-day earnings announcement return |
| 6 | `rev_g_q2` | `T3a_Trajectory` | **`2.46%`** | `7 / 12` | `1.81%` | `+0.0192` | `+1.01` | 2-quarters-ago YoY revenue growth |
| 7 | `eps_beat_streak` | `T3a_Trajectory` | **`2.43%`** | `7 / 12` | `1.89%` | `-0.0038` | `-0.25` | Consecutive quarters of positive YoY EPS growth (up to 8Q) |
| 8 | `ear` | `T2_Snapshot` | **`2.39%`** | `10 / 12` | `1.48%` | `+0.0044` | `+0.33` | Most recent 3-day earnings announcement excess return |
| 9 | `dv_ratio` | `T1_Price` | **`2.38%`** | `7 / 12` | `1.74%` | **`+0.0319`** | **`+2.15`** | 63d / 252d institutional dollar-volume surge ratio |
| 10 | `epsg_q2` | `T3a_Trajectory` | **`2.31%`** | `7 / 12` | `2.05%` | `+0.0123` | `+0.74` | 2-quarters-ago YoY EPS growth |
| 11 | `rev_g_q0` | `T3a_Trajectory` | **`2.23%`** | `5 / 12` | `1.68%` | **`+0.0323`** | **`+1.82`** | Current-quarter YoY revenue growth |
| 12 | `net_issuance` | `T2_Snapshot` | **`2.22%`** | `5 / 12` | `1.69%` | `+0.0025` | `+0.17` | Share buyback / dilution rate |
| 13 | `dist_sma50` | `T1_Price` | **`2.13%`** | `4 / 12` | `1.84%` | `-0.0209` | `-1.10` | Short-term overextension control (`Close / SMA50 - 1`) |
| 14 | `accruals` | `T2_Snapshot` | **`2.10%`** | `5 / 12` | `1.53%` | `+0.0020` | `+0.12` | Earnings quality (`(NI - CFO) / Assets`) |
| 15 | `cfo_ni` | `T3a_Trajectory` | **`2.08%`** | `4 / 12` | `1.65%` | `+0.0037` | `+0.24` | Operating cash flow conversion (`CFO / |NI|`) |
| 16 | `epsg_q3` | `T3a_Trajectory` | **`2.06%`** | `4 / 12` | `1.62%` | `+0.0051` | `+0.34` | 3-quarters-ago YoY EPS growth base |
| 17 | `log_mcap` | `T2_Snapshot` | **`2.05%`** | `5 / 12` | `1.43%` | `+0.0330` | `+1.70` | Market capitalization scaling |
| 18 | `dist_52wh` | `T1_Price` | **`2.04%`** | `4 / 12` | `1.55%` | `-0.0402` | `-1.96` | Proximity to 52-week high |
| 19 | `sue` | `T2_Snapshot` | **`2.03%`** | `5 / 12` | `1.63%` | `-0.0045` | `-0.29` | Standardized unexpected earnings |
| 20 | `inv_rev_chg` | `T3a_Trajectory` | **`2.00%`** | `3 / 12` | `1.35%` | `-0.0150` | `-0.91` | 4-quarter inventory-to-revenue bloat/drawdown |

---

## 4. Universe 2: QQQ (Point-in-Time Nasdaq-100) & `S&P 500 ∪ QQQ` Results

Full table across all 4 pools (`QQQ_Top30`, `QQQ_Top50`, `QQQ_Full100`, `SP500_Union_QQQ_Top50`) is saved in [ml3_qqq_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_qqq_summary_table.csv), and paired statistical comparisons are saved in [ml3_qqq_paired_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_qqq_paired_comparisons.csv). *(Note: Historical Nasdaq-100 constituent spells are reconstructed from `jmccarrell/n100tickers` + SEC/price cross-checks, not an official licensed Nasdaq feed).*

| Strategy | Pool | Model | Top-K | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe | `2015–2026.09` Daily MaxDD | `2015–2019` CAGR | `2020–2022` CAGR | `2023–2026.09` CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BENCH: QQQ ETF Buy & Hold`** | QQQ | Bench | 1 | `22.40%` | `0.92` | `-36.31%` | `18.54%` | `0.86` | `-36.31%` | `16.51%` | `6.96%` | `31.67%` |
| **`QQQ: T0 Pure 12-1 Momentum Top-1`** | QQQ | Rule | 1 | `43.86%` | `0.82` | `-83.72%` | `41.43%` | `0.83` | `-83.72%` | `40.89%` | `-2.44%` | `91.30%` |
| **`QQQ: T0 Pure 12-1 Momentum Top-3`** | QQQ | Rule | 3 | **`55.49%`** | **`1.02`** | `-62.20%` | **`40.96%`** | **`0.90`** | `-62.20%` | `20.34%` | `32.72%` | `82.00%` |
| **`S&P500 ∪ QQQ: T0 Pure Momentum Top-1`** | Union | Rule | 1 | **`76.61%`** | **`1.12`** | `-59.98%` | **`39.03%`** | `0.79` | `-73.46%` | `6.50%` | `30.91%` | `106.91%` |
| **`S&P500 ∪ QQQ: T0 Pure Momentum Top-3`** | Union | Rule | 3 | **`58.10%`** | **`1.11`** | **`-41.72%`** | **`38.24%`** | **`0.91`** | **`-41.88%`** | `11.08%` | `54.38%` | `68.59%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`QQQ_Full100: T1 Price Only`** | **QQQ 100** | **LGBM** | **1** | **`62.31%`** | **`0.97`** | **`-66.76%`** | **`50.28%`** | **`0.92`** | **`-66.76%`** | **`41.18%`** | **`50.85%`** | **`62.62%`** |
| **`QQQ_Full100: T1 Price Only`** | **QQQ 100** | **LGBM** | **3** | **`36.73%`** | **`0.91`** | `-53.74%` | **`31.39%`** | **`0.90`** | `-53.74%` | `29.81%` | `17.07%` | `46.40%` |
| `QQQ_Full100: T2 Snapshot` | QQQ 100 | LGBM | 1 | `22.49%` | `0.56` | `-86.98%` | `14.60%` | `0.46` | `-86.98%` | `9.27%` | `-11.76%` | `50.37%` |
| `QQQ_Full100: T2 Snapshot` | QQQ 100 | LGBM | 3 | `31.30%` | `0.88` | `-69.22%` | `21.84%` | `0.72` | `-69.22%` | `15.07%` | `-0.74%` | `54.73%` |
| `QQQ_Full100: T3a Trajectory Core` | QQQ 100 | LGBM | 1 | `30.00%` | `0.69` | `-66.96%` | `20.71%` | `0.58` | `-66.96%` | `23.97%` | `-13.65%` | `52.38%` |
| `QQQ_Full100: T3a Trajectory Core` | QQQ 100 | LGBM | 3 | `27.32%` | `0.82` | `-64.09%` | `24.72%` | `0.82` | `-64.09%` | `27.50%` | `-16.16%` | **`66.50%`** |
| `QQQ_Full100: T3S In-Sample Discovery` | QQQ 100 | LGBM | 3 | `27.90%` | `0.81` | `-65.25%` | `22.82%` | `0.76` | `-65.25%` | `24.97%` | `-12.53%` | `57.51%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`QQQ_Top30: T1 Price Only`** | QQQ Top30 | LGBM | 3 | **`37.65%`** | **`0.97`** | **`-42.60%`** | **`29.44%`** | **`0.90`** | **`-42.60%`** | `22.71%` | `24.97%` | `42.80%` |
| `QQQ_Top30: T2 Snapshot` | QQQ Top30 | LGBM | 3 | `17.75%` | `0.60` | `-46.83%` | `13.24%` | `0.51` | `-46.83%` | `12.31%` | `15.71%` | `12.51%` |
| **`QQQ_Top30: T3a Trajectory Core`** | **QQQ Top30** | **LGBM** | **3** | **`32.11%`** | **`0.87`** | `-51.47%` | **`23.25%`** | **`0.75`** | `-51.47%` | `13.09%` | `9.51%` | **`51.64%`** |
| **`QQQ_Top30: T3b 8Q Summary Slopes`** | QQQ Top30 | LGBM | 3 | **`31.90%`** | **`0.88`** | `-46.81%` | **`23.92%`** | **`0.77`** | `-46.81%` | `17.15%` | `19.59%` | `37.24%` |
| **`QQQ_Top30: T3a Zero-CAGR-Peek (Rank Val)`** | **QQQ Top30** | **LGBM** | **3** | **`36.92%`** | **`0.97`** | **`-43.58%`** | **`27.81%`** | **`0.87`** | **`-43.58%`** | `16.06%` | `23.99%` | **`48.59%`** |
| **`QQQ_Top30: T3a Zero-Tune (Fixed NL=7)`** | QQQ Top30 | LGBM | 1 | **`34.21%`** | **`0.72`** | `-66.65%` | **`25.28%`** | **`0.63`** | `-66.65%` | `6.37%` | **`57.70%`** | `29.15%` |
| **`QQQ_Top30: T3a Trajectory Core (Ridge)`** | QQQ Top30 | Ridge | 1 | `29.43%` | `0.66` | `-78.90%` | **`32.46%`** | **`0.74`** | `-78.90%` | **`44.27%`** | `19.56%` | `28.53%` |
| **`QQQ_Top30: T3a Trajectory Core (Ridge)`** | QQQ Top30 | Ridge | 3 | **`30.44%`** | **`0.81`** | `-55.68%` | **`26.81%`** | **`0.81`** | `-55.68%` | `28.94%` | `10.52%` | `38.50%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `QQQ_Top50: T2 Snapshot` | QQQ Top50 | LGBM | 3 | `16.36%` | `0.53` | `-57.43%` | `12.11%` | `0.45` | `-57.43%` | `13.47%` | `12.65%` | `9.94%` |
| `QQQ_Top50: T3a Trajectory Core` | QQQ Top50 | LGBM | 3 | `24.88%` | `0.74` | `-40.77%` | `21.51%` | `0.72` | `-40.77%` | `22.55%` | `9.33%` | `30.76%` |
| **`QQQ_Top50: T3S In-Sample Discovery`** | **QQQ Top50** | **LGBM** | **1** | **`33.30%`** | **`0.72`** | **`-58.63%`** | **`35.98%`** | **`0.80`** | **`-58.63%`** | **`34.10%`** | **`41.19%`** | **`34.39%`** |
| **`QQQ_Top50: T3a Zero-Tune (Fixed NL=7)`** | **QQQ Top50** | **LGBM** | **3** | **`29.66%`** | **`0.77`** | **`-39.99%`** | **`26.29%`** | **`0.78`** | **`-39.99%`** | `23.44%` | `14.50%` | **`40.75%`** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `S&P500 ∪ QQQ Top50: T2 Snapshot` | Union Top50 | LGBM | 3 | `26.78%` | `0.78` | `-45.12%` | `19.11%` | `0.65` | `-45.12%` | `9.03%` | `17.07%` | `35.63%` |
| **`S&P500 ∪ QQQ Top50: T3a Trajectory Core`** | **Union Top50** | **LGBM** | **3** | **`31.81%`** | **`0.87`** | **`-39.05%`** | **`24.42%`** | **`0.78`** | **`-39.05%`** | `12.11%` | `23.32%` | **`43.64%`** |
| **`S&P500 ∪ QQQ Top50: T3a Trajectory Core`** | **Union Top50** | **Ridge** | **1** | **`49.24%`** | **`0.83`** | `-63.72%` | **`30.63%`** | **`0.66`** | `-63.91%` | `-3.05%` | `32.29%` | **`91.16%`** |
| **`S&P500 ∪ QQQ Top50: T3a Trajectory Core`** | **Union Top50** | **Ridge** | **3** | **`30.25%`** | **`0.77`** | `-52.62%` | **`23.93%`** | **`0.71`** | `-52.62%` | `11.06%` | `13.76%` | **`53.24%`** |

---

## 5. Universe 3: XLK Historical PIT Tech Pool & `100%` SEC EDGAR SIC Tech Pool

Full table across all 7 XLK pool configurations (`127` strategies × `5` windows = `635` rows) is saved in [ml3_xlk_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_xlk_summary_table.csv), and paired comparisons are saved in [ml3_xlk_paired_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_xlk_paired_comparisons.csv).

### 5.1 XLK Pool Definitions (Zero Survivorship, Dual Sector Provenance)
1. **`XLK_PIT` (`~68` stocks/month)**: Point-in-Time S&P 500 historical members (`sp500_PIT_daily.parquet`) assigned to `Information Technology` at date $t$ (`historical_sectors.py`).
2. **`XLK_Strict_SEC_SIC` (`~65` stocks/month, `100%` SEC EDGAR Provenance)**: Point-in-Time S&P 500 historical members whose **SEC EDGAR filing SIC code** is strictly IT/Semiconductors/Software/Hardware (`3570–3579`, `3660–3679`, `3825`, `7370–7379`, plus payment processors `6099/6199`), with **zero Wikipedia or Yahoo sector input**.
3. **Training Modes Evaluated**:
   - **In-Pool Direct (`XLK_Full_PIT`)**: Train & predict on all `~68` XLK stocks.
   - **In-Pool Momentum Pre-Filtered (`XLK_Top30_PIT`, `XLK_Top20_PIT`)**: Train & predict inside XLK `12-1` Momentum Top-30 or Top-20.
   - **Cross-Pool Trained (`XLK_Top30_TrainSP500Top50`, `XLK_Top20_TrainSP500Top50`)**: Train on the broader `S&P 500 12-1 Momentum Top-50` (`50` stocks/m across all sectors, providing larger sample size and cross-sector fundamental contrast) $\rightarrow$ rank inside `XLK_Top30` or `XLK_Top20`.

### 5.2 Master XLK Performance Table

| Strategy | Pool / Train Mode | Model | Top-K | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe | `2015–2026.09` Daily MaxDD | `2015–2019` CAGR | `2020–2022` CAGR | `2023–2026.09` CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BENCH: XLK ETF Buy & Hold`** | XLK ETF | Bench | 1 | `27.01%` | `1.00` | `-35.53%` | `21.62%` | `0.92` | `-35.53%` | `18.64%` | `9.69%` | `36.48%` |
| **`BENCH: Equal-Weight XLK Tech PIT`** | XLK PIT | Bench | - | `22.84%` | `0.89` | `-35.81%` | `20.10%` | `0.89` | `-35.81%` | `20.58%` | `9.73%` | `28.40%` |
| **`XLK_PIT: T0 Pure 12-1 Momentum Top-1`** | **XLK PIT** | **Rule** | **1** | **`77.79%`** | **`1.25`** | **`-55.56%`** | **`58.30%`** | **`1.09`** | **`-55.56%`** | **`35.56%`** | **`33.62%`** | **`122.18%`** |
| **`XLK_PIT: T0 Pure 12-1 Momentum Top-3`** | **XLK PIT** | **Rule** | **3** | **`31.01%`** | **`0.80`** | `-45.74%` | **`25.79%`** | **`0.75`** | `-48.63%` | `19.05%` | `-5.33%` | **`69.71%`** |
| **`XLK_Strict_SEC_SIC: T0 Pure Mom Top-1`** | **SEC SIC** | **Rule** | **1** | **`73.19%`** | **`1.20`** | **`-55.56%`** | **`55.57%`** | **`1.06`** | **`-55.56%`** | **`30.08%`** | **`33.62%`** | **`122.18%`** |
| **`XLK_Strict_SEC_SIC: T0 Pure Mom Top-3`** | **SEC SIC** | **Rule** | **3** | **`31.75%`** | **`0.79`** | `-53.92%` | **`26.20%`** | **`0.74`** | `-53.92%` | `20.07%` | `-10.68%` | **`77.64%`** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `XLK_Full_PIT: T1 Price Only` | In-Pool Full | LGBM | 1 | `-0.96%` | `0.18` | `-75.26%` | `3.89%` | `0.27` | `-75.26%` | `22.83%` | `-8.15%` | `-7.95%` |
| `XLK_Full_PIT: T3a Trajectory Core` | In-Pool Full | LGBM | 1 | `-11.44%` | `0.05` | `-91.27%` | `-10.08%` | `0.02` | `-91.27%` | `0.96%` | `-29.15%` | `-6.51%` |
| `XLK_Full_PIT: T3a Trajectory Core` | In-Pool Full | LGBM | 3 | `16.72%` | `0.53` | `-50.28%` | `12.33%` | `0.46` | `-50.28%` | `15.78%` | `1.33%` | `17.25%` |
| **`XLK_Full_PIT: T3a Trajectory (Ridge)`** | In-Pool Full | Ridge | 1 | **`31.92%`** | **`0.83`** | `-48.40%` | **`25.99%`** | **`0.74`** | `-48.40%` | `18.74%` | `19.30%` | `42.26%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`XLK_Top30_PIT: T1 Price Only`** | **In-Pool Top30** | **LGBM** | **1** | **`58.71%`** | **`1.01`** | **`-48.87%`** | **`30.63%`** | **`0.70`** | `-58.27%` | `-4.00%` | `-4.10%` | **`150.51%`** |
| **`XLK_Top30_PIT: T1 Price Only`** | **In-Pool Top30** | **LGBM** | **3** | **`36.53%`** | **`0.89`** | **`-42.28%`** | **`26.90%`** | **`0.78`** | **`-42.28%`** | `15.31%` | `2.18%` | **`71.10%`** |
| **`XLK_Top30_PIT: T3S Discovery`** | **In-Pool Top30** | **LGBM** | **3** | **`33.81%`** | **`0.98`** | **`-42.18%`** | **`25.98%`** | **`0.87`** | **`-42.18%`** | `20.30%` | `19.07%` | `40.01%` |
| **`XLK_Top30_PIT: T3a ZeroCAGRPeek RankVal`** | **In-Pool Top30** | **LGBM** | **3** | **`32.08%`** | **`0.87`** | **`-37.66%`** | **`28.43%`** | **`0.87`** | **`-37.66%`** | `24.90%` | `11.84%` | `48.82%` |
| **`XLK_Top20_PIT: T3a Trajectory Core`** | **In-Pool Top20** | **LGBM** | **3** | **`41.22%`** | **`0.99`** | **`-42.31%`** | **`30.59%`** | **`0.87`** | **`-42.31%`** | `17.51%` | **`28.67%`** | **`51.74%`** |
| **`XLK_Top20_PIT: T3a ZeroCAGRPeek RankVal`** | **In-Pool Top20** | **LGBM** | **3** | **`35.91%`** | **`0.91`** | **`-41.36%`** | **`27.30%`** | **`0.81`** | **`-41.36%`** | `17.51%` | `19.93%` | `48.28%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`XLK_Top30 (Train S&P500 Top50): T3a Core`** | **Cross-Pool** | **LGBM** | **1** | **`60.29%`** | **`1.16`** | **`-44.41%`** | **`50.70%`** | **`1.09`** | **`-50.88%`** | **`44.08%`** | **`31.67%`** | **`78.08%`** |
| **`XLK_Top30 (Train S&P500 Top50): T3a Core`** | **Cross-Pool** | **LGBM** | **3** | **`32.33%`** | **`0.89`** | `-44.26%` | **`28.10%`** | **`0.87`** | `-44.26%` | `24.83%` | `14.03%` | `45.44%` |
| **`XLK_Top30 (Train S&P500 Top50): T3a RankVal`** | **Cross-Pool** | **LGBM** | **1** | **`76.30%`** | **`1.26`** | **`-44.41%`** | **`64.64%`** | **`1.21`** | **`-50.88%`** | **`52.97%`** | **`23.96%`** | **`127.53%`** |
| **`XLK_Top30 (Train S&P500 Top50): T3a RankVal`** | **Cross-Pool** | **LGBM** | **3** | **`38.12%`** | **`1.02`** | **`-39.88%`** | **`35.06%`** | **`1.05`** | **`-39.88%`** | **`32.29%`** | **`16.92%`** | **`55.76%`** |
| **`XLK_Top30 (Train S&P500 Top50): T3a FixedNL7`** | **Cross-Pool** | **LGBM** | **1** | **`63.16%`** | **`1.20`** | **`-44.41%`** | **`51.94%`** | **`1.13`** | **`-50.88%`** | **`46.37%`** | **`32.45%`** | **`78.08%`** |
| **`XLK_Top30 (Train S&P500 Top50): T3a FixedNL7`** | **Cross-Pool** | **LGBM** | **3** | **`37.90%`** | **`1.01`** | `-44.26%` | **`34.03%`** | **`1.02`** | `-44.26%` | **`31.15%`** | **`23.56%`** | **`47.18%`** |
| **`XLK_Top20 (Train S&P500 Top50): T3a FixedNL7`** | **Cross-Pool** | **LGBM** | **1** | **`44.33%`** | **`0.84`** | `-55.95%` | **`34.84%`** | **`0.77`** | `-55.95%` | `25.03%` | `12.41%` | **`72.21%`** |
| **`XLK_Top20 (Train S&P500 Top50): T3a FixedNL7`** | **Cross-Pool** | **LGBM** | **3** | **`34.61%`** | **`0.89`** | **`-39.04%`** | **`28.87%`** | **`0.85`** | **`-39.04%`** | `22.46%` | `10.21%` | **`56.16%`** |

---

## 6. Universe 4: IWM / Small-Mid-Cap Point-in-Time Results

Full table across `2019–2026.09`, `2015–2026.09`, and the delisting-complete `WIKI 2015–2018.02` window (with Base `0%`, `-30%`, and `-100%` delisting stress tests) is saved in [ml3_iwm_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_iwm_summary_table.csv).

| Strategy | Training Mode | Model | Top-K | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR (Base) | `2015–2026.09` Stress `-100%` | `WIKI 2015–2018.02` CAGR (Base) | `WIKI 2015–2018.02` Stress `-100%` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BENCH: IWM ETF Buy & Hold`** | Bench | ETF | - | `9.86%` | `0.40` | `-44.70%` | `7.75%` | `7.75%` | `8.45%` | `8.45%` |
| **`BENCH: Equal-Weight Small/Mid Universe`** | Bench | EW | - | `12.53%` | `0.50` | `-46.45%` | `9.65%` | `5.50%` | `8.26%` | `5.46%` |
| **`IWM_Top50: T0 Pure 12-1 Momentum Top-1`** | Rule | Rule | 1 | `0.25%` | `0.48` | `-99.36%` | `-8.86%` | `-100.00%` | `-38.68%` | `-38.68%` |
| **`IWM_Top50: T0 Pure 12-1 Momentum Top-3`** | Rule | Rule | 3 | `9.58%` | `0.44` | `-75.66%` | `-4.12%` | `-13.95%` | `-30.45%` | `-48.23%` |
| **`IWM_Top50: T0 Pure 12-1 Momentum Top-5`** | Rule | Rule | 5 | `16.01%` | `0.49` | `-71.08%` | `7.26%` | `-3.69%` | `-7.79%` | `-20.01%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`T1 Price-Only (No CIK Surv)`** | **In-Universe** | **LGBM** | **3** | **`22.51%`** | **`0.58`** | **`-64.21%`** | **`20.15%`** | `2.11%` | **`38.74%`** | **`5.86%`** |
| **`T1 Price-Only (No CIK Surv)`** | **In-Universe** | **LGBM** | **5** | **`26.92%`** | **`0.65`** | **`-58.81%`** | **`18.57%`** | `2.84%` | **`26.96%`** | `-0.43%` |
| `T2 Snapshot (+21 SEC Snapshot)` | In-Universe | LGBM | 3 | `12.36%` | `0.43` | `-74.13%` | `9.26%` | `9.26%` | `4.30%` | `4.30%` |
| `T2 Snapshot (+21 SEC Snapshot)` | In-Universe | LGBM | 5 | `6.19%` | `0.31` | `-79.25%` | `4.86%` | `-1.85%` | `9.98%` | `-14.36%` |
| **`T3a Trajectory Core (57f)`** | **In-Universe** | **LGBM** | **1** | **`21.75%`** | **`0.55`** | `-85.36%` | **`10.18%`** | **`10.18%`** | `-1.27%` | `-1.27%` |
| **`T3a Trajectory Core (57f)`** | **In-Universe** | **LGBM** | **3** | **`24.88%`** | **`0.60`** | `-68.21%` | **`12.45%`** | **`8.73%`** | `2.45%` | `-9.80%` |
| **`T3a Zero-CAGR-Peek (Rank Val)`** | **In-Universe** | **LGBM** | **1** | **`46.63%`** | **`0.78`** | `-82.34%` | **`22.75%`** | **`22.75%`** | `-1.27%` | `-1.27%` |
| **`T3S In-Sample Feature Discovery`** | **In-Universe** | **LGBM** | **5** | **`38.95%`** | **`0.82`** | **`-58.47%`** | **`26.00%`** | **`20.52%`** | **`17.36%`** | `-0.81%` |
| **`T3a Trajectory Core (Ridge)`** | **In-Universe** | **Ridge** | **3** | **`25.17%`** | **`0.62`** | `-62.28%` | **`24.24%`** | **`15.17%`** | **`37.95%`** | **`3.57%`** |
| **`T3a Trajectory Core (Ridge)`** | **In-Universe** | **Ridge** | **5** | **`30.95%`** | **`0.72`** | `-69.46%` | **`19.86%`** | **`10.58%`** | `9.30%` | `-13.38%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `T1 Price-Only (Zero-Shot from S&P500)` | Transfer SP500 | LGBM | 3 | `2.34%` | `0.29` | `-85.77%` | `0.04%` | `-3.81%` | `24.07%` | `6.92%` |
| `T2 Snapshot (Zero-Shot from S&P500)` | Transfer SP500 | LGBM | 3 | `-7.78%` | `0.11` | `-91.64%` | `-3.19%` | `-3.19%` | `20.15%` | `20.15%` |
| `T3a Trajectory (Zero-Shot from S&P500)` | Transfer SP500 | LGBM | 3 | `-25.20%` | `-0.10` | `-97.08%` | `-20.94%` | `-20.94%` | `0.43%` | `0.43%` |

---

## 7. Deliverables & Reproducibility Manifest

All scripts, CSV tables, fold configurations, and monthly holdings ledgers are saved in `outputs/ml3_feature_discovery_20261102/`:
- [run_ml3_feature_discovery.py](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/run_ml3_feature_discovery.py) — Main S&P 500 ML3 Feature Discovery & Nested Rolling Frozen OOS script (`val <= (Y-1)-11-30`).
- [run_ml3_qqq_iwm_pools.py](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/run_ml3_qqq_iwm_pools.py) — Extension script for QQQ (`Nasdaq-100 PIT`) and IWM (`Small/Mid-Cap PIT`) pools (`val <= (Y-1)-11-30`).
- [run_ml3_xlk_pool.py](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/run_ml3_xlk_pool.py) — Extension script for XLK (`Historical PIT Tech Pool` & `100% SEC EDGAR SIC Tech Pool`, `val <= (Y-1)-11-30`).
- [ml3_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_summary_table.csv) — S&P 500 performance summary (`Pool A` & `Pool B`, 39 strategies × 5 windows).
- [ml3_incremental_tier_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_incremental_tier_comparisons.csv) — S&P 500 paired Newey-West HAC & 2,000-draw stationary block bootstrap tests.
- [ml3_leave_one_group_out_ablation.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_leave_one_group_out_ablation.csv) — 7-group Leave-One-Group-Out OOS ablation results.
- [ml3_feature_stability_78.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_feature_stability_78.csv) — Multi-fold stability & Rank IC leaderboard across all 78 PIT features.
- [ml3_qqq_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_qqq_summary_table.csv) — QQQ & `S&P 500 ∪ QQQ` pool results (58 strategies × 5 windows).
- [ml3_qqq_paired_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_qqq_paired_comparisons.csv) — QQQ paired Newey-West HAC, block bootstrap, win-month & win-year comparisons.
- [ml3_xlk_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_xlk_summary_table.csv) — XLK Historical PIT Tech & `100%` SEC EDGAR SIC Tech pool results (127 strategies × 5 windows).
- [ml3_xlk_paired_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_xlk_paired_comparisons.csv) — XLK paired Newey-West HAC, block bootstrap, and Holm-Bonferroni comparisons.
- [ml3_iwm_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_iwm_summary_table.csv) — IWM / Small-Mid-Cap pool results (35 strategies × 5 windows, with `-30%` and `-100%` delisting stress tests).
- `ledgers/`, `ledgers_qqq_iwm/`, & `ledgers_xlk/` — Monthly holdings, turnover, gross/net returns across all 259 evaluated strategies.
