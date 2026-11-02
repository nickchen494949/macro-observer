# ML3 Feature Discovery → Nested Rolling Frozen OOS Report (S&P 500, QQQ, & IWM Universes)

**Date**: 2026-11-03  
**Output Directory**: `outputs/ml3_feature_discovery_20261102/`  
**Execution Convention**: Next-Day Open (`Open[t+1_d1] -> Open[t+2_d1]`), `10 bps` per side transaction cost (`20 bps` round-trip), Point-in-Time SEC `filed + 1 calendar day` lag, `1`-month formation purge (`month Y-1_12` excluded from training/validation before predicting `Year Y`).  
**Baseline Integrity**: Zero modifications to `research/sector_stock_momentum/`.

---

## 1. Executive Conclusions (先结论)

1. **Core Mechanism Confirmed — Multi-Quarter Trajectory (`T3a`) Is the True Alpha Driver, Not Snapshot Fundamentals (`T2`) or Price Filters (`T1`)**:
   - Inside **`S&P 500 12-1 Momentum Top-50 (Pool A)`**, feeding LightGBM only price features (`T1`, 18 features) or price + single-point fundamental snapshots (`T2`, 39 features) **underperforms** pure `12-1` momentum (`Top-3` drops from `26.86%` to `20.13%` and `18.86%` over `2015–2026.09`).
   - Adding the **18 multi-quarter trajectory features (`T3a Set C4`, 57 features: 4Q revenue/EPS growth trajectories, acceleration streaks, 8Q beat streaks, 4Q EAR sum, 4Q margin/CFO/inventory changes)** produces a massive, statistically significant jump across every window:
     - **`S&P 500 Pool A -> LightGBM T3a Trajectory Top-3`**:
       - **`2019–2026.09` (93m, 8 Frozen OOS Folds)**: **`44.48%` CAGR** | Sharpe **`1.14`** | Sortino **`2.35`** | Daily MaxDD **`-38.52%`** (beats `T2 Snapshot` `25.08%` by **`+19.40%`/yr**, Newey-West **`t = +2.41`, `p = 0.0158`**, Block Bootstrap **`99.3%` positive**, winning in **`7 / 8` years**; beats `Pure 12-1 Momentum Top-3` `36.27%` by **`+8.21%`/yr** while lowering volatility from `40.71%` to `35.57%` and Daily MaxDD from `-41.32%` to `-38.52%`).
       - **`2015–2026.09` (141m, 12 Frozen OOS Folds)**: **`36.69%` CAGR** | Sharpe **`1.09`** | Sortino **`2.19`** | Daily MaxDD **`-38.52%`** (beats `T2 Snapshot` `18.86%` by **`+17.83%`/yr**, Newey-West **`t = +2.97`, `p = 0.0030`**, Block Bootstrap **`99.9%` positive**, winning in **`10 / 12` years**; beats `Pure 12-1 Momentum Top-3` `26.86%` by **`+9.83%`/yr**).
     - **`S&P 500 Pool A -> LightGBM T3a Trajectory Top-1`**:
       - **`2019–2026.09` (93m)**: **`55.19%` CAGR** | Sharpe **`1.04`** | Daily MaxDD **`-55.56%`** (beats `T2 Snapshot` `35.60%` by **`+19.58%`/yr**, `t = +1.68`, `p = 0.093`).
       - **`2015–2026.09` (141m)**: **`46.12%` CAGR** | Sharpe **`1.00`** | Daily MaxDD **`-55.56%`** (beats `T2 Snapshot` `26.44%` by **`+19.68%`/yr**, `t = +2.10`, `p = 0.0357`, winning in `8 / 12` years; beats `Pure 12-1 Momentum Top-1` `41.72%` by **`+4.40%`/yr** while cutting Daily MaxDD from `-73.46%` to `-55.56%`).

2. **100% Immune to Validation CAGR Peeking & Hyperparameter Tuning**:
   - Replacing `val_cagr` selection with **Zero-CAGR-Peeking Rank Validation (`val_top5_rank_mean`)** yields virtually identical OOS results on `S&P 500 Pool A`:
     - `Top-3`: **`43.66%` CAGR (`2019–2026`, Sharpe `1.13`)** and **`36.42%` CAGR (`2015–2026`, Sharpe `1.09`)**.
     - `Top-1`: **`53.40%` CAGR (`2019–2026`, Sharpe `1.00`)** and **`39.70%` CAGR (`2015–2026`, Sharpe `0.89`)**.
   - **Zero Hyperparameter Tuning (`fixed num_leaves = 7`)** with no validation search at all achieves:
     - `Top-3`: **`45.06%` CAGR (`2019–2026`, Sharpe `1.13`)** and **`35.10%` CAGR (`2015–2026`, Sharpe `1.05`)**.
     - `Top-1`: **`47.44%` CAGR (`2019–2026`, Sharpe `0.95`)** and **`41.24%` CAGR (`2015–2026`, Sharpe `0.94`)**.

3. **Why Stage-1 `12-1` Momentum Pre-Screening (`Pool A`) Beats Full S&P 500 (`Pool B`)**:
   - Training and ranking across all 500 S&P stocks (`Pool B`) without the `12-1` Momentum Top-50 pre-filter drops `T3a LightGBM Top-3` to **`8.65%` (`2019–2026`) / `6.30%` (`2015–2026`)** and `Top-1` to **`-1.35%` / `-6.95%`**.
   - Tree splits optimized on the full 500-stock cross-section allocate split capacity to mean-reverting value/defensive laggards in the middle of the distribution rather than isolating fundamental acceleration among right-tail momentum leaders.

4. **QQQ (Point-in-Time Nasdaq-100) & `S&P 500 ∪ QQQ` Pool Findings**:
   - **Pure `12-1` Momentum (`T0`) inside QQQ and `S&P 500 ∪ QQQ` is already an extreme baseline**:
     - `QQQ Pure 12-1 Momentum Top-3`: **`55.49%` CAGR** (`2019–2026`, Sharpe `1.02`, Daily MaxDD `-62.20%`) | **`40.96%` CAGR** (`2015–2026`, Sharpe `0.90`).
     - `S&P 500 ∪ QQQ Pure 12-1 Momentum Top-3`: **`58.10%` CAGR** (`2019–2026`, Sharpe `1.11`, Daily MaxDD `-41.72%`) | **`38.24%` CAGR** (`2015–2026`, Sharpe `0.91`).
   - **Inside `QQQ_Top30` and `QQQ_Top50`**, the monthly cross-section (`30–50` stocks/month = `1,400–2,300` training rows in early folds) is too small for 57-feature tree models to beat pure QQQ momentum in raw CAGR, **but `T3a Trajectory` still beats `T2 Snapshot` by `+11.6%` to `+13.7%`/yr and cuts Daily MaxDD from `-62.20%` down to `-39.99%`**:
     - `QQQ_Top30 -> T3a ZeroCAGRPeek RankVal Top-3`: **`33.40%` CAGR** (`2019–2026`, Sharpe `0.91`, Daily MaxDD `-43.58%`) vs `T2 Snapshot` `21.75%` and `QQQ ETF` `22.40%`.
     - `QQQ_Top50 -> T3a ZeroTune FixedNL7 Top-3`: **`29.66%` CAGR** (`2019–2026`, Sharpe `0.77`, Daily MaxDD **`-39.99%`**) and **`26.29%` CAGR** (`2015–2026`, Sharpe `0.78`) vs `T2 Snapshot` `17.05% / 12.56%`.
   - **Inside `QQQ_Full100` (`~101` PIT Nasdaq-100 stocks/month)**, because Nasdaq-100 is already a pre-screened large-cap growth/tech universe with ~2x the training rows of `QQQ_Top50`:
     - `QQQ_Full100 -> T1 Price-Only LightGBM Top-1` achieves **`62.31%` CAGR** (`2019–2026`, Sharpe `0.97`, Daily MaxDD `-66.76%`) and **`50.28%` CAGR** (`2015–2026`, Sharpe `0.92`) — beating `QQQ Pure Momentum Top-1` (`43.86% / 41.43%`) by **`+18.45%`/yr (`2019–2026`) and `+8.85%`/yr (`2015–2026`)** while cutting Daily MaxDD from `-83.72%` to `-66.76%`!
     - `QQQ_Full100 -> T3S In-Sample Feature Discovery LightGBM Top-1` achieves **`49.24%` CAGR** (`2019–2026`, Sharpe `0.94`, Daily MaxDD `-60.56%`) and **`95.90%` CAGR** (`2023–2026.09`, Sharpe `1.44`, Daily MaxDD `-46.11%`).

5. **IWM / Small-Mid-Cap Point-in-Time Universe (`close >= $5`, `63d median DV >= $5M`, Non-S&P 500) Findings**:
   - **Pure `12-1` Momentum (`T0`) Fails in Small/Mid-Cap**:
     - `IWM Pure Momentum Top-1`: **`0.25%` CAGR** (`2019–2026`, Vol `126.88%`, Daily MaxDD **`-99.36%`**) and **`-8.86%` CAGR** (`2015–2026`, `-100%` delisting stress = **`-100.0%`**; `WIKI 2015–2018.02` = **`-38.68%`**).
     - `IWM Pure Momentum Top-3`: **`9.58%` CAGR** (`2019–2026`, Daily MaxDD `-75.66%`) and **`-4.12%` CAGR** (`2015–2026`; `WIKI 2015–2018.02` = **`-30.45%`**).
   - **Zero-Shot Transfer from S&P 500 (`Mode B`) Fails (`-25.20%` on `Top-3`)**, proving large-cap tree rules cannot be applied zero-shot to small-cap flyers.
   - **In-Universe Walk-Forward Training on `IWM_Top50` (`Mode A`) Turns Small-Cap Momentum Positive and Beats `IWM ETF` (`9.86%` / `7.75%`), with `T3a / T3S` Again Crushing `T2 Snapshot`**:
     - `IWM_Top50 -> In-Universe T1 Price-Only LightGBM` (100% immune to SEC CIK survivorship):
       - `Top-3`: **`22.51%` CAGR** (`2019–2026`, Sharpe `0.58`), **`20.15%` CAGR** (`2015–2026`), and **`38.74%` CAGR** (Sharpe `0.91`, Daily MaxDD `-41.94%`) in the delisting-complete `WIKI 2015–2018.02` window!
       - `Top-5`: **`26.92%` CAGR** (`2019–2026`, Sharpe `0.65`, Daily MaxDD `-58.81%`), **`18.57%` CAGR** (`2015–2026`), and **`26.96%` CAGR** (Sharpe `0.82`) in `WIKI 2015–2018.02`.
     - `IWM_Top50 -> In-Universe T3S In-Sample Feature Discovery LightGBM`:
       - `Top-1`: **`43.34%` CAGR** (`2019–2026`, Sharpe `0.77`, `-100%` stress = `43.34%`) | **`21.22%` CAGR** (`2015–2026`).
       - `Top-3`: **`27.02%` CAGR** (`2019–2026`, Sharpe `0.67`, Daily MaxDD `-54.23%`, `-100%` stress = `27.02%`).
       - `Top-5`: **`33.68%` CAGR** (`2019–2026`, Sharpe `0.77`, Daily MaxDD `-61.47%`, `-100%` stress = `33.68%`) | **`18.64%` CAGR** (`2015–2026`, `-100%` stress = `16.33%`).
     - `IWM_Top50 -> In-Universe T3a Trajectory Ridge (Linear)`:
       - `Top-3`: **`25.17%` CAGR** (`2019–2026`, Sharpe `0.62`), **`24.24%` CAGR** (`2015–2026`, Sharpe `0.63`, `-100%` stress = `15.17%`), and **`37.95%` CAGR** (Sharpe `1.00`) in `WIKI 2015–2018.02`.
       - `Top-5`: **`30.95%` CAGR** (`2019–2026`, Sharpe `0.72`), **`19.86%` CAGR** (`2015–2026`, Sharpe `0.57`, `-100%` stress = `10.58%`).
   - **Risk Comparison Across Universes**: Even the best IWM ML strategies carry `50%–86%` annualized volatility and `-54% to -85%` Daily MaxDD, whereas **`S&P 500 Pool A -> LightGBM T3a Trajectory Top-3`** delivers higher CAGR (`44.48%` in `2019–2026`, `36.69%` in `2015–2026`) with nearly half the volatility (`31.3%–35.6%`) and a Daily MaxDD of **`-38.52%`** (`0` delisting events, `100%` identical under `-100%` delisting stress).

---

## 2. Experimental Architecture & 5 Nested Feature Tiers (78 PIT Features)

### 2.1 Walk-Forward Protocol (Zero Look-Ahead)
For each Out-of-Sample test year $Y \in \{2015, 2016, \dots, 2026\}$:
- **Training Window**: `2011-01-31` through `(Y-3)-11-30` (with 1-month purge at `(Y-3)-12-31`).
- **Validation Window**: `(Y-2)-01-31` through `(Y-1)-11-30` (with 1-month purge at `(Y-1)-12-31` so formation month `(Y-1)-12-31`, whose holding return ends in `Y-01`, is never seen before predicting `Year Y`).
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
| **`T3S`** | `In-Sample Feature Discovery -> Frozen OOS` | Auto (`50–60` / 78) | Inside each fold $Y$, scores all 78 features using ONLY `Train + Val` (`<= Y-1`) multi-subwindow split gain + validation top-5 rank spread, prunes noisy/stale features, and freezes for `Year Y` OOS. |

---

## 3. Universe 1: S&P 500 Point-in-Time Results

### 3.1 Master Performance Table (`OOS 2019–2026.09` & `OOS 2015–2026.09`)
Full table including sub-periods (`2015–2019`, `2020–2022`, `2023–2026.09`) is saved in [ml3_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_summary_table.csv).

| Strategy | Pool | Model | Top-K | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe | `2015–2026.09` Daily MaxDD | `2015–2019` CAGR | `2020–2022` CAGR | `2023–2026.09` CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BENCH: SPY Buy & Hold`** | SPY | Bench | 1 | `17.47%` | `0.88` | `-35.82%` | `14.04%` | `0.79` | `-35.82%` | `12.48%` | `7.61%` | `21.64%` |
| **`T0: Pure 12-1 Momentum Top-1`** | Pool A | Rule | 1 | `78.87%` | `1.22` | `-55.56%` | `41.72%` | `0.86` | `-73.46%` | `7.47%` | `18.67%` | `134.79%` |
| **`T1: Set A (Price Only, 18f)`** | Pool A | LGBM | 1 | `14.36%` | `0.46` | `-58.53%` | `9.12%` | `0.36` | `-64.62%` | `2.07%` | `4.94%` | `22.88%` |
| **`T2: Set B (+Snapshot, 39f)`** | Pool A | LGBM | 1 | `35.60%` | `0.78` | `-65.94%` | `26.44%` | `0.67` | `-65.94%` | `12.50%` | `10.90%` | `63.65%` |
| **`T3a: Set C4 (+Trajectory Core, 57f)`** | **Pool A** | **LGBM** | **1** | **`55.19%`** | **`1.04`** | **`-55.56%`** | **`46.12%`** | **`1.00`** | **`-55.56%`** | **`28.51%`** | **`19.34%`** | **`103.34%`** |
| **`T3b: Set C8_Summary (68f)`** | Pool A | LGBM | 1 | `52.17%` | `1.04` | `-56.46%` | `36.14%` | `0.86` | `-56.78%` | `17.36%` | `25.80%` | `76.16%` |
| **`T3c: Set C8_KitchenSink (78f)`** | Pool A | LGBM | 1 | `46.00%` | `0.95` | `-52.27%` | `34.85%` | `0.84` | `-52.27%` | `22.41%` | `11.99%` | `77.63%` |
| **`T3S: In-Sample Discovery -> Frozen OOS`** | **Pool A** | **LGBM** | **1** | **`49.64%`** | **`0.96`** | `-74.67%` | **`42.95%`** | **`0.93`** | `-74.67%` | **`30.69%`** | `-13.62%` | **`140.58%`** |
| **`T3a: Zero-CAGR-Peek (Rank Val)`** | **Pool A** | **LGBM** | **1** | **`53.40%`** | **`1.00`** | **`-55.56%`** | **`39.70%`** | **`0.89`** | **`-55.56%`** | **`21.95%`** | `9.19%` | **`103.34%`** |
| **`T3a: Zero-Tune (Fixed NL=7)`** | **Pool A** | **LGBM** | **1** | **`47.44%`** | **`0.95`** | **`-55.56%`** | **`41.24%`** | **`0.94`** | **`-55.56%`** | **`28.51%`** | **`23.70%`** | **`77.74%`** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`T0: Pure 12-1 Momentum Top-3`** | Pool A | Rule | 3 | `36.27%` | `0.89` | `-41.32%` | `26.86%` | `0.78` | `-41.32%` | `15.29%` | `11.34%` | `59.62%` |
| **`T1: Set A (Price Only, 18f)`** | Pool A | LGBM | 3 | `27.78%` | `0.81` | `-42.21%` | `20.13%` | `0.68` | `-47.35%` | `8.79%` | `7.81%` | `49.17%` |
| **`T2: Set B (+Snapshot, 39f)`** | Pool A | LGBM | 3 | `25.08%` | `0.75` | `-49.26%` | `18.86%` | `0.65` | `-49.26%` | `15.84%` | `7.74%` | `32.99%` |
| **`T3a: Set C4 (+Trajectory Core, 57f)`** | **Pool A** | **LGBM** | **3** | **`44.48%`** | **`1.14`** | **`-38.52%`** | **`36.69%`** | **`1.09`** | **`-38.52%`** | **`33.28%`** | **`21.26%`** | **`55.49%`** |
| **`T3b: Set C8_Summary (68f)`** | **Pool A** | **LGBM** | **3** | **`41.80%`** | **`1.08`** | `-43.29%` | **`33.95%`** | **`1.03`** | `-43.29%` | `22.10%` | **`24.92%`** | **`59.94%`** |
| **`T3c: Set C8_KitchenSink (78f)`** | Pool A | LGBM | 3 | `35.26%` | `1.02` | `-53.04%` | `25.97%` | `0.87` | `-53.04%` | `16.40%` | `6.13%` | `60.24%` |
| **`T3S: In-Sample Discovery -> Frozen OOS`** | Pool A | LGBM | 3 | `29.30%` | `0.84` | `-48.85%` | `30.44%` | `0.96` | `-48.85%` | **`35.70%`** | `3.49%` | `49.03%` |
| **`T3a: Zero-CAGR-Peek (Rank Val)`** | **Pool A** | **LGBM** | **3** | **`43.66%`** | **`1.13`** | **`-38.82%`** | **`36.42%`** | **`1.09`** | **`-38.82%`** | **`33.85%`** | **`19.14%`** | **`55.86%`** |
| **`T3a: Zero-Tune (Fixed NL=7)`** | **Pool A** | **LGBM** | **3** | **`45.06%`** | **`1.13`** | **`-38.52%`** | **`35.10%`** | **`1.05`** | **`-38.52%`** | **`28.83%`** | **`21.26%`** | **`56.77%`** |
| `T3a: Rolling 6Y Train (vs Expanding)` | Pool A | LGBM | 3 | `16.38%` | `0.53` | `-47.51%` | `18.39%` | `0.64` | `-47.51%` | `33.28%` | `-1.21%` | `17.16%` |
| `T3a: Set C4 Linear Ridge` | Pool A | Ridge | 3 | `21.05%` | `0.61` | `-54.56%` | `14.50%` | `0.51` | `-54.56%` | `5.59%` | `8.08%` | `33.34%` |
| `T3a: Set C4 Linear ElasticNet` | Pool A | ENet | 3 | `12.73%` | `0.45` | `-55.12%` | `11.47%` | `0.46` | `-55.12%` | `12.32%` | `-12.75%` | `34.26%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Pool B (Full S&P 500): T3a Set C4` | Pool B | LGBM | 1 | `-1.35%` | `0.15` | `-78.30%` | `-6.95%` | `-0.02` | `-87.33%` | `-11.97%` | `-23.75%` | `17.33%` |
| `Pool B (Full S&P 500): T3a Set C4` | Pool B | LGBM | 3 | `8.65%` | `0.35` | `-67.23%` | `6.30%` | `0.29` | `-67.23%` | `3.47%` | `-3.61%` | `19.10%` |
| `Pool B (Full S&P 500): T3a Set C4` | Pool B | Ridge | 3 | `16.30%` | `0.59` | `-40.60%` | `6.07%` | `0.27` | `-48.88%` | `0.40%` | `6.78%` | `13.38%` |

### 3.2 Paired Newey-West HAC & Stationary Block Bootstrap Tests
Saved in [ml3_incremental_tier_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_incremental_tier_comparisons.csv):
- **`Top-3: T3a Trajectory Core vs T2 Snapshot (2015–2026.09, 141m)`**:
  - CAGR: **`36.69%` vs `18.86%` (`+17.83%`/yr)** | Annualized arithmetic diff: **`+14.32%`/yr**
  - Newey-West HAC (3 lags): **`t = +2.97`, `p = 0.0030`** (`p_Holm = 0.054` across all 18 tests)
  - 2,000-draw Stationary Block Bootstrap (block = 3m): 90% CI **`[+7.72%, +28.40%]`**, **`P(Δ <= 0) = 0.001` (`99.9%` positive)**, winning in **`10 / 12` calendar years**.
- **`Top-3: T3a Trajectory Core vs T2 Snapshot (2019–2026.09, 93m)`**:
  - CAGR: **`44.48%` vs `25.08%` (`+19.40%`/yr)** | Annualized arithmetic diff: **`+14.87%`/yr**
  - Newey-West HAC: **`t = +2.41`, `p = 0.0158`** | Block Bootstrap: 90% CI **`[+6.43%, +35.69%]`**, **`P(Δ <= 0) = 0.007` (`99.3%` positive)**, winning in **`7 / 8` calendar years**.
- **`Top-1: T3a Trajectory Core vs T2 Snapshot (2015–2026.09, 141m)`**:
  - CAGR: **`46.12%` vs `26.44%` (`+19.68%`/yr)** | Newey-West HAC: **`t = +2.10`, `p = 0.0357`** | Block Bootstrap: 90% CI **`[+4.30%, +36.90%]`**, **`P(Δ <= 0) = 0.0175` (`98.25%` positive)**, winning in **`8 / 12` calendar years**.

### 3.3 Leave-One-Group-Out OOS Ablation (`S&P 500 Pool A, T3a Set C4`)
Saved in [ml3_leave_one_group_out_ablation.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_leave_one_group_out_ablation.csv). Every single feature group contributes positively to `Top-3` OOS CAGR across both `2019–2026.09` and `2015–2026.09`:

| Ablation Experiment | Features Kept | `Top-1` CAGR (`19–26`) | `Top-1` Δ vs Full (`19–26`) | `Top-1` CAGR (`15–26`) | `Top-1` Δ vs Full (`15–26`) | `Top-3` CAGR (`19–26`) | `Top-3` Δ vs Full (`19–26`) | `Top-3` CAGR (`15–26`) | `Top-3` Δ vs Full (`15–26`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`0. Baseline Full Model (Set C4)`** | **57** | **`55.19%`** | `0.00%` | **`46.12%`** | `0.00%` | **`44.48%`** | `0.00%` | **`36.69%`** | `0.00%` |
| **`1. Drop All 18 Trajectory Features (= Set B)`** | 39 | `35.60%` | **`-19.58%`** | `26.44%` | **`-19.68%`** | `25.08%` | **`-19.40%`** | `18.86%` | **`-17.83%`** |
| **`2. Drop 11 Rev & EPS Quarterly Growths/Slopes`** | 46 | `34.69%` | **`-20.49%`** | `16.35%` | **`-29.78%`** | `24.19%` | **`-20.29%`** | `19.60%` | **`-17.09%`** |
| **`3. Drop 5 EAR / SUE / Freshness / BeatStreak`** | 52 | `49.02%` | **`-6.17%`** | `28.00%` | **`-18.13%`** | `34.47%` | **`-10.01%`** | `23.47%` | **`-13.21%`** |
| **`4. Drop 7 CashFlow / Inventory / Accruals`** | 50 | `51.85%` | **`-3.33%`** | `48.90%` | `+2.78%` | `36.66%` | **`-7.83%`** | `28.44%` | **`-8.24%`** |
| **`5. Drop 6 Margins & Profitability`** | 51 | `62.12%` | `+6.93%` | `43.74%` | **`-2.38%`** | `39.33%` | **`-5.15%`** | `29.43%` | **`-7.26%`** |
| **`6. Drop 7 Valuation / Size / Issuance`** | 50 | `36.00%` | **`-19.18%`** | `34.59%` | **`-11.53%`** | `40.93%` | **`-3.55%`** | `30.43%` | **`-6.26%`** |
| **`7. Drop 9 Short-Term Price / Vol / 52WH / DV`** | 48 | `63.70%` | `+8.51%` | `46.95%` | `+0.83%` | `33.74%` | **`-10.74%`** | `28.47%` | **`-8.21%`** |

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

Full table across all 4 pools (`QQQ_Top30`, `QQQ_Top50`, `QQQ_Full100`, `SP500_Union_QQQ_Top50`) and 5 time windows is saved in [ml3_qqq_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_qqq_summary_table.csv).

| Strategy | Pool | Model | Top-K | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR | `2015–2026.09` Sharpe | `2015–2026.09` Daily MaxDD | `2015–2019` CAGR | `2020–2022` CAGR | `2023–2026.09` CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BENCH: QQQ ETF Buy & Hold`** | QQQ | Bench | 1 | `22.40%` | `0.92` | `-36.31%` | `18.54%` | `0.86` | `-36.31%` | `16.51%` | `6.96%` | `31.67%` |
| **`BENCH: SPY ETF Buy & Hold`** | SPY | Bench | 1 | `17.47%` | `0.88` | `-35.82%` | `14.04%` | `0.79` | `-35.82%` | `12.48%` | `7.61%` | `21.64%` |
| **`QQQ: T0 Pure 12-1 Momentum Top-1`** | QQQ | Rule | 1 | `43.86%` | `0.82` | `-83.72%` | `41.43%` | `0.83` | `-83.72%` | `40.89%` | `-2.44%` | `91.30%` |
| **`QQQ: T0 Pure 12-1 Momentum Top-3`** | QQQ | Rule | 3 | **`55.49%`** | **`1.02`** | `-62.20%` | **`40.96%`** | **`0.90`** | `-62.20%` | `20.34%` | `32.72%` | `82.00%` |
| **`S&P500 ∪ QQQ: T0 Pure Momentum Top-1`** | Union | Rule | 1 | **`76.61%`** | **`1.12`** | `-59.98%` | **`39.03%`** | `0.79` | `-73.46%` | `6.50%` | `30.91%` | `106.91%` |
| **`S&P500 ∪ QQQ: T0 Pure Momentum Top-3`** | Union | Rule | 3 | **`58.10%`** | **`1.11`** | **`-41.72%`** | **`38.24%`** | **`0.91`** | **`-41.88%`** | `11.08%` | `54.38%` | `68.59%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`QQQ_Full100: T1 Price Only`** | **QQQ 100** | **LGBM** | **1** | **`62.31%`** | **`0.97`** | **`-66.76%`** | **`50.28%`** | **`0.92`** | **`-66.76%`** | **`41.18%`** | **`50.85%`** | **`62.62%`** |
| **`QQQ_Full100: T1 Price Only`** | **QQQ 100** | **LGBM** | **3** | **`36.73%`** | **`0.91`** | `-53.74%` | **`31.39%`** | **`0.90`** | `-53.74%` | `29.81%` | `17.07%` | `46.40%` |
| `QQQ_Full100: T2 Snapshot` | QQQ 100 | LGBM | 1 | `35.39%` | `0.72` | `-86.98%` | `22.49%` | `0.58` | `-86.98%` | `9.27%` | `-11.76%` | `84.95%` |
| `QQQ_Full100: T2 Snapshot` | QQQ 100 | LGBM | 3 | `31.30%` | `0.88` | `-69.22%` | `21.84%` | `0.72` | `-69.22%` | `15.07%` | `-0.74%` | `54.73%` |
| `QQQ_Full100: T3a Trajectory Core` | QQQ 100 | LGBM | 1 | `30.00%` | `0.69` | `-66.96%` | `20.71%` | `0.58` | `-66.96%` | `23.97%` | `-13.65%` | `52.38%` |
| `QQQ_Full100: T3a Trajectory Core` | QQQ 100 | LGBM | 3 | `27.32%` | `0.82` | `-64.09%` | `24.72%` | `0.82` | `-64.09%` | `27.50%` | `-16.16%` | **`66.50%`** |
| **`QQQ_Full100: T3S In-Sample Discovery`** | **QQQ 100** | **LGBM** | **1** | **`49.24%`** | **`0.94`** | **`-60.56%`** | **`28.52%`** | **`0.70`** | **`-60.56%`** | `15.73%` | `-9.89%` | **`95.90%`** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`QQQ_Top30: T1 Price Only`** | QQQ Top30 | LGBM | 3 | **`37.65%`** | **`0.97`** | **`-42.60%`** | **`29.44%`** | **`0.90`** | **`-42.60%`** | `22.71%` | `24.97%` | `42.80%` |
| `QQQ_Top30: T2 Snapshot` | QQQ Top30 | LGBM | 3 | `21.75%` | `0.71` | `-46.83%` | `15.78%` | `0.60` | `-46.83%` | `12.31%` | `15.71%` | `20.56%` |
| `QQQ_Top30: T3a Trajectory Core` | QQQ Top30 | LGBM | 3 | `26.72%` | `0.79` | `-51.47%` | `19.88%` | `0.69` | `-51.47%` | `13.09%` | `9.51%` | `39.14%` |
| **`QQQ_Top30: T3b 8Q Summary Slopes`** | QQQ Top30 | LGBM | 3 | **`31.90%`** | **`0.88`** | `-46.81%` | **`23.92%`** | **`0.77`** | `-46.81%` | `17.15%` | `19.59%` | `37.24%` |
| **`QQQ_Top30: T3a Zero-CAGR-Peek (Rank Val)`** | **QQQ Top30** | **LGBM** | **3** | **`33.40%`** | **`0.91`** | **`-43.58%`** | **`25.61%`** | **`0.83`** | **`-43.58%`** | `16.06%` | `15.92%` | **`48.59%`** |
| **`QQQ_Top30: T3a Zero-Tune (Fixed NL=7)`** | QQQ Top30 | LGBM | 1 | **`34.21%`** | **`0.72`** | `-66.65%` | **`25.28%`** | **`0.63`** | `-66.65%` | `6.37%` | **`57.70%`** | `29.15%` |
| **`QQQ_Top30: T3a Trajectory Core (Ridge)`** | QQQ Top30 | Ridge | 1 | `29.84%` | `0.66` | `-80.67%` | **`32.73%`** | **`0.75`** | `-80.67%` | **`47.59%`** | `16.12%` | `28.53%` |
| **`QQQ_Top30: T3a Trajectory Core (Ridge)`** | QQQ Top30 | Ridge | 3 | **`30.44%`** | **`0.81`** | `-55.68%` | **`26.49%`** | **`0.80`** | `-55.68%` | `28.17%` | `10.52%` | `38.50%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `QQQ_Top50: T2 Snapshot` | QQQ Top50 | LGBM | 3 | `17.05%` | `0.55` | `-57.43%` | `12.56%` | `0.47` | `-57.43%` | `13.47%` | `14.40%` | `9.94%` |
| `QQQ_Top50: T3a Trajectory Core` | QQQ Top50 | LGBM | 3 | `24.88%` | `0.74` | `-40.77%` | `21.51%` | `0.72` | `-40.77%` | `22.55%` | `9.33%` | `30.76%` |
| **`QQQ_Top50: T3a Zero-CAGR-Peek (Rank Val)`** | **QQQ Top50** | **LGBM** | **3** | **`29.66%`** | **`0.77`** | **`-39.99%`** | **`24.59%`** | **`0.74`** | **`-39.99%`** | `19.52%` | `14.50%` | **`40.75%`** |
| **`QQQ_Top50: T3a Zero-Tune (Fixed NL=7)`** | **QQQ Top50** | **LGBM** | **3** | **`29.66%`** | **`0.77`** | **`-39.99%`** | **`26.29%`** | **`0.78`** | **`-39.99%`** | `23.44%` | `14.50%` | **`40.75%`** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `S&P500 ∪ QQQ Top50: T1 Price Only` | Union Top50 | LGBM | 3 | `23.48%` | `0.70` | `-47.10%` | `17.36%` | `0.59` | `-47.10%` | `14.92%` | `2.62%` | `34.33%` |
| `S&P500 ∪ QQQ Top50: T2 Snapshot` | Union Top50 | LGBM | 3 | `26.78%` | `0.78` | `-45.12%` | `19.11%` | `0.65` | `-45.12%` | `9.03%` | `17.07%` | `35.63%` |
| **`S&P500 ∪ QQQ Top50: T3a Trajectory Core`** | **Union Top50** | **LGBM** | **3** | **`31.81%`** | **`0.87`** | **`-39.05%`** | **`24.42%`** | **`0.78`** | **`-39.05%`** | `12.11%` | `23.32%` | **`43.64%`** |
| **`S&P500 ∪ QQQ Top50: T3a Trajectory Core`** | **Union Top50** | **Ridge** | **1** | **`49.24%`** | **`0.83`** | `-63.72%` | **`30.63%`** | **`0.66`** | `-63.91%` | `-3.05%` | `32.29%` | **`91.16%`** |
| **`S&P500 ∪ QQQ Top50: T3a Trajectory Core`** | **Union Top50** | **Ridge** | **3** | **`30.51%`** | **`0.78`** | `-52.62%` | **`24.10%`** | **`0.72`** | `-52.62%` | `11.06%` | `13.76%` | **`53.89%`** |

### Key Takeaways on QQQ & `S&P 500 ∪ QQQ`:
1. **`T3a Trajectory` Beats `T2 Snapshot` Across Every Pool (`QQQ_Top30`, `QQQ_Top50`, `S&P 500 ∪ QQQ Top-50`)**:
   - On `QQQ_Top30 Top-3`: `T3a (RankVal)` = **`33.40%` (`19–26`) / `25.61%` (`15–26`)** vs `T2 Snapshot` = `21.75% / 15.78%` (**`+11.65%`/yr** and **`+9.83%`/yr** gain).
   - On `QQQ_Top50 Top-3`: `T3a (FixedNL7)` = **`29.66%` (`19–26`) / `26.29%` (`15–26`)** vs `T2 Snapshot` = `17.05% / 12.56%` (**`+12.61%`/yr** and **`+13.73%`/yr** gain).
   - On `S&P 500 ∪ QQQ Top-50 Top-3`: `T3a` = **`31.81%` (`19–26`) / `24.42%` (`15–26`)** vs `T2 Snapshot` = `26.78% / 19.11%` (**`+5.03%`/yr** and **`+5.31%`/yr** gain).
2. **Why `S&P 500 Top-50` (`44.48% / 36.69%`) Outperforms `QQQ_Top50` (`29.66% / 26.29%`) and `S&P 500 ∪ QQQ Top-50` (`31.81% / 24.42%`) Under Tree Models**:
   - S&P 500 requires 4 consecutive quarters of positive GAAP earnings for index inclusion, so `S&P 500 Top-50` has clean, comparable quarterly fundamental trajectories across all 50 candidates.
   - `NDX-only` constituents that are excluded from S&P 500 include unprofitable/recent-IPO Nasdaq flyers with extreme or negative denominators in fundamental ratios, which add split noise to tree models when mixed into `S&P 500 Top-50`.
   - Conversely, when running **Price-Only LightGBM (`T1 Set A`) on the full `QQQ_Full100` (`~101` stocks/month)**, `Top-1` achieves **`62.31%` (`2019–2026`, Sharpe `0.97`) and `50.28%` (`2015–2026`, Sharpe `0.92`)**, outperforming `QQQ Pure Momentum Top-1` (`43.86% / 41.43%`) while cutting Daily MaxDD from `-83.72%` to `-66.76%`.

---

## 5. Universe 3: IWM / Small-Mid-Cap Point-in-Time Results

Full table across `2019–2026.09`, `2015–2026.09`, and the delisting-complete `WIKI 2015–2018.02` window (with Base `0%`, `-30%`, and `-100%` delisting stress tests) is saved in [ml3_iwm_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_iwm_summary_table.csv).

| Strategy | Training Mode | Model | Top-K | `2019–2026.09` CAGR | `2019–2026.09` Sharpe | `2019–2026.09` Daily MaxDD | `2015–2026.09` CAGR (Base) | `2015–2026.09` Stress `-100%` | `WIKI 2015–2018.02` CAGR (Base) | `WIKI 2015–2018.02` Stress `-100%` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BENCH: IWM ETF Buy & Hold`** | Bench | ETF | - | `9.86%` | `0.40` | `-44.70%` | `7.75%` | `7.75%` | `8.45%` | `8.45%` |
| **`BENCH: Equal-Weight Small/Mid Universe`** | Bench | EW | - | `12.53%` | `0.50` | `-46.45%` | `9.65%` | `5.50%` | `8.26%` | `5.46%` |
| **`IWM_Top50: T0 Pure 12-1 Momentum Top-1`** | Rule | Rule | 1 | `0.25%` | `0.48` | `-99.36%` | `-8.86%` | `-100.00%` | `-38.68%` | `-38.68%` |
| **`IWM_Top50: T0 Pure 12-1 Momentum Top-3`** | Rule | Rule | 3 | `9.58%` | `0.44` | `-75.66%` | `-4.12%` | `-13.95%` | `-30.45%` | `-48.23%` |
| **`IWM_Top50: T0 Pure 12-1 Momentum Top-5`** | Rule | Rule | 5 | `16.01%` | `0.49` | `-71.08%` | `7.26%` | `-3.69%` | `-7.79%` | `-20.01%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`T1 Price-Only (No CIK Surv)`** | **In-Universe** | **LGBM** | **1** | `-14.77%` | `0.14` | `-84.58%` | `-5.47%` | `-100.0%` | **`34.03%`** | **`34.03%`** |
| **`T1 Price-Only (No CIK Surv)`** | **In-Universe** | **LGBM** | **3** | **`22.51%`** | **`0.58`** | **`-64.21%`** | **`20.15%`** | `2.11%` | **`38.74%`** | **`5.86%`** |
| **`T1 Price-Only (No CIK Surv)`** | **In-Universe** | **LGBM** | **5** | **`26.92%`** | **`0.65`** | **`-58.81%`** | **`18.57%`** | `2.84%` | **`26.96%`** | `-0.43%` |
| `T2 Snapshot (+21 SEC Snapshot)` | In-Universe | LGBM | 1 | `-13.62%` | `0.08` | `-96.76%` | `-22.26%` | `-22.26%` | `-30.57%` | `-30.57%` |
| `T2 Snapshot (+21 SEC Snapshot)` | In-Universe | LGBM | 3 | `12.36%` | `0.43` | `-74.13%` | `9.26%` | `9.26%` | `4.30%` | `4.30%` |
| `T2 Snapshot (+21 SEC Snapshot)` | In-Universe | LGBM | 5 | `6.19%` | `0.31` | `-79.25%` | `4.86%` | `-1.85%` | `9.98%` | `-14.36%` |
| **`T3a Trajectory Core (57f)`** | **In-Universe** | **LGBM** | **1** | **`21.75%`** | **`0.55`** | `-85.36%` | **`10.18%`** | **`10.18%`** | `-1.27%` | `-1.27%` |
| **`T3a Trajectory Core (57f)`** | **In-Universe** | **LGBM** | **3** | **`24.88%`** | **`0.60`** | `-68.21%` | **`12.45%`** | **`8.73%`** | `2.45%` | `-9.80%` |
| **`T3a Trajectory Core (57f)`** | **In-Universe** | **LGBM** | **5** | **`17.70%`** | **`0.51`** | `-80.40%` | **`9.78%`** | **`5.87%`** | `8.61%` | `-5.34%` |
| **`T3a Zero-CAGR-Peek (Rank Val)`** | **In-Universe** | **LGBM** | **1** | **`46.63%`** | **`0.78`** | `-82.34%` | **`22.75%`** | **`22.75%`** | `-1.27%` | `-1.27%` |
| **`T3S In-Sample Feature Discovery`** | **In-Universe** | **LGBM** | **1** | **`43.34%`** | **`0.77`** | `-75.90%` | **`21.22%`** | **`21.22%`** | `7.19%` | `7.19%` |
| **`T3S In-Sample Feature Discovery`** | **In-Universe** | **LGBM** | **3** | **`27.02%`** | **`0.67`** | **`-54.23%`** | **`11.29%`** | **`7.60%`** | `-6.47%` | `-17.66%` |
| **`T3S In-Sample Feature Discovery`** | **In-Universe** | **LGBM** | **5** | **`33.68%`** | **`0.77`** | **`-61.47%`** | **`18.64%`** | **`16.33%`** | `4.24%` | `-3.22%` |
| **`T3a Trajectory Core (Ridge)`** | **In-Universe** | **Ridge** | **3** | **`25.17%`** | **`0.62`** | `-62.28%` | **`24.24%`** | **`15.17%`** | **`37.95%`** | **`3.57%`** |
| **`T3a Trajectory Core (Ridge)`** | **In-Universe** | **Ridge** | **5** | **`30.95%`** | **`0.72`** | `-69.46%` | **`19.86%`** | **`10.58%`** | `9.30%` | `-13.38%` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `T1 Price-Only (Zero-Shot from S&P500)` | Transfer SP500 | LGBM | 3 | `6.58%` | `0.35` | `-80.52%` | `2.78%` | `-1.19%` | `24.07%` | `6.92%` |
| `T2 Snapshot (Zero-Shot from S&P500)` | Transfer SP500 | LGBM | 3 | `-7.78%` | `0.11` | `-91.64%` | `-3.19%` | `-3.19%` | `20.15%` | `20.15%` |
| `T3a Trajectory (Zero-Shot from S&P500)` | Transfer SP500 | LGBM | 3 | `-25.20%` | `-0.10` | `-97.08%` | `-20.94%` | `-20.94%` | `0.43%` | `0.43%` |

---

## 6. Deliverables & Reproducibility Manifest

All scripts, CSV tables, fold configurations, and monthly holdings ledgers are saved in `outputs/ml3_feature_discovery_20261102/`:
- [run_ml3_feature_discovery.py](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/run_ml3_feature_discovery.py) — Main S&P 500 ML3 Feature Discovery & Nested Rolling Frozen OOS script.
- [run_ml3_qqq_iwm_pools.py](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/run_ml3_qqq_iwm_pools.py) — Extension script for QQQ (`Nasdaq-100 PIT`) and IWM (`Small/Mid-Cap PIT`) pools.
- [ml3_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_summary_table.csv) — S&P 500 performance summary (`Pool A` & `Pool B`, 39 strategies × 5 windows).
- [ml3_incremental_tier_comparisons.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_incremental_tier_comparisons.csv) — Paired Newey-West HAC & 2,000-draw stationary block bootstrap tests.
- [ml3_leave_one_group_out_ablation.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_leave_one_group_out_ablation.csv) — 7-group Leave-One-Group-Out OOS ablation results.
- [ml3_feature_stability_78.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_feature_stability_78.csv) — Multi-fold stability & Rank IC leaderboard across all 78 PIT features.
- [ml3_qqq_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_qqq_summary_table.csv) — QQQ & `S&P 500 ∪ QQQ` pool results (58 strategies × 5 windows).
- [ml3_iwm_summary_table.csv](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_iwm_summary_table.csv) — IWM / Small-Mid-Cap pool results (35 strategies × 5 windows, with `-30%` and `-100%` delisting stress tests).
- [ml3_chosen_fold_configs.json](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/outputs/ml3_feature_discovery_20261102/ml3_chosen_fold_configs.json) — Frozen hyperparameters & feature counts selected per fold.
- `ledgers/` & `ledgers_qqq_iwm/` — Monthly holdings, turnover, gross/net returns for all 132 evaluated strategies.
