# Independent From-Scratch Audit — High-Low/OHLC Volatility Estimators, `SOXL` V1-Daily & `TQQQ + SOXL` Rebalanced Blend (2026-11-26)

> **Zero-Shared-Code Audit Script**: [`audit_soxl_and_vol_estimators.py`](../../audit_soxl_and_vol_estimators.py)  
> **Full Console Log**: [`audit_log.txt`](./audit_log.txt)  
> **All 9 CSV Result & Ledger Files**:
> - [`T1_volatility_estimators_and_window_sweep.csv`](./T1_volatility_estimators_and_window_sweep.csv)
> - [`T1b_jan_feb_2020_c2c_vs_hl_tr_diagnostic.csv`](./T1b_jan_feb_2020_c2c_vs_hl_tr_diagnostic.csv)
> - [`T2_1x_vs_3x_vol_z_source_comparison.csv`](./T2_1x_vs_3x_vol_z_source_comparison.csv)
> - [`T3_soxl_standalone_variants_vs_tqqq.csv`](./T3_soxl_standalone_variants_vs_tqqq.csv)
> - [`T4_soxl_standalone_2d_trig_rec_plateau.csv`](./T4_soxl_standalone_2d_trig_rec_plateau.csv)
> - [`T5_blend_weight_x_rebalance_frequency_plateau.csv`](./T5_blend_weight_x_rebalance_frequency_plateau.csv)
> - [`T6_blend_75_25_annual_x_soxl_trig_rec_64cell_plateau.csv`](./T6_blend_75_25_annual_x_soxl_trig_rec_64cell_plateau.csv)
> - [`T7_soxl_v1_to_qqq_trade_ledger.csv`](./T7_soxl_v1_to_qqq_trade_ledger.csv)
> - [`T7_blend_75_25_daily_nav_and_weights.csv`](./T7_blend_75_25_daily_nav_and_weights.csv)

---

## Executive Summary & Key Findings

1. **`T1` — Close-to-Close vs High-Low / OHLC Volatility Estimators (`2010-02-11 .. 2026-11-03`)**:
   - **At the standard 20-day window (`W20`)**: The frozen **Close-to-Close (`C2C`)** estimator achieves the highest CAGR (**`54.97%`**, MaxDD **`-44.54%`**, Sharpe **`1.261`**, 15-cell plateau median **`54.97%`**), outperforming all 6 High-Low / OHLC range estimators by `+1.49%` to `+4.55%/yr` because wide intraday ranges on big green V-rebound days keep range estimators elevated longer before falling below `Rec = 0.3`.
   - **At short windows (`W8`–`W12`, 8–12 days)**: **`Parkinson High-Low`** (`W10`: **`55.19%` CAGR / `-44.54%` MaxDD**) and **`True Range RMS` (High-Low + Overnight Gap)** (`W10`: **`54.86%` CAGR / `-44.54%` MaxDD**) completely eliminate the `10-day` Close-to-Close `-69.92%` COVID cliff **without any "20-day non-ratchet NSL" patch**.
   - **Mechanism (`T1b`)**: On `2020-02-04`, `QQQ` rallied `+2.29%` to a new all-time high after a `-1.59%` dip on `2020-01-31`. The 10-day Close-to-Close standard deviation confused upward breakout dispersion with risk (`VZ10_C2C = +1.27 > 1.2`), triggering a false exit on `2020-02-05` and a fatal re-entry at the `2020-02-14/18` market top (`VZ10_C2C = -0.11 < 0.3`). By contrast, 10-day `Parkinson High-Low` (`+0.70`) and 10-day `True Range RMS` (`+0.97`) did not false-trigger on `2020-02-04`, and instead triggered cleanly on Day 1 of the COVID crash (`2020-02-24`, `VZ10_TR = +1.34 > 1.2`).

2. **`T2` — Computing `Vol_Z` from 1x Underlying (`QQQ` / `SOXX`) vs 3x ETF Itself (`TQQQ` / `SOXL`)**:
   - Because $r_{3\times,t} \approx 3 r_{1\times,t}$, the factor of `3` cancels out in the Z-score numerator and denominator: $\text{Corr}(\text{Vol\_Z}_{\text{QQQ}}, \text{Vol\_Z}_{\text{TQQQ}}) = \mathbf{0.99960}$ and $\text{Corr}(\text{Vol\_Z}_{\text{SOXX}}, \text{Vol\_Z}_{\text{SOXL}}) = \mathbf{0.99831}$.
   - Using the 1x underlying (`QQQ` / `SOXX`) is superior because `1x QQQ` (launched 1999) and `1x SOXX` (launched 2001) already have a full 252-day trailing window on Day 1 of `TQQQ`/`SOXL` inception in Feb/Mar 2010 (avoiding missing the May 2010 Flash Crash exit) and are free of variable leveraged-ETF financing drag.

3. **`T3` & `T4` — Applying Frozen `V1-Daily (SEP + Vol_Z 1.2/0.3 + Open Limit NSL)` Directly to `SOXL` (`2010-03-11 .. 2026-11-03`, Zero Retuning)**:
   - **`SOXL Buy & Hold`**: `33.42%` CAGR (`121.6x`), MaxDD **`-90.46%`**, 2022 return **`-85.66%`**, Sharpe `0.779` (underperformed `TQQQ Buy & Hold` `38.74%` due to extreme cyclical volatility decay).
   - **`SOXL Pure FOMC SEP Only`**: `61.37%` CAGR (`2,882.8x`), MaxDD `-80.38%`, 2022 return **`+1.58%`**, Sharpe `1.008`.
   - **`SOXL Frozen V1-Daily (Vol_Z on SOXX -> De-lever to 1x SOXX)`**: **`69.62%` CAGR (`6,616.1x`)**, MaxDD **`-70.83%`**, Sharpe **`1.119`**, closed `3x` win rate **`15 / 16 (93.8%)`**.
   - **`SOXL Frozen V1-Daily (Vol_Z on SOXX -> De-lever to 1x QQQ)`**: **`69.96%` CAGR (`6,840.3x`)**, `2010–2019` CAGR **`45.31%`** (vs `44.39%` de-levering to `SOXX`), MaxDD **`-70.83%`**, Sharpe **`1.127`**, requiring zero trades in `SOXX`.
   - **2D Parameter Plateau (`T4`)**: `TQQQ`'s frozen plateau (`Trig ∈ [1.0..1.3] × Rec ∈ [-0.2..+0.7]`, 36 cells) is also the exact top plateau on `SOXL` (all 36 cells achieve `63.4% .. 74.4%` CAGR with identical `-70.83%` MaxDD; `Trig = 1.2` is the #1 row out of all 10 trigger levels).
   - **Caveat on `100% SOXL`**: In `2010–2019` (pre-AI era), `100% SOXL V1-Daily` (`44.39%–45.31%`) trailed `100% TQQQ V1-Daily` (`46.16%`), and `100% SOXL` suffered a **`-70.83%`** drawdown from `2024-10-14` to `2025-04-08` (after `SEP` flipped `ON` on `2025-03-19` right before the April 2025 tariff selloff). Hence `SOXL` should **not** replace `TQQQ` 100%, but rather serve as a `15%–25%` rebalanced satellite sleeve.

4. **`T5` & `T6` — `TQQQ + SOXL` Rebalanced Blend (`Both De-levering to 1x QQQ`, Exact Next-Day Open Rebalance + `10bp/side`)**:
   - **Never Rebalancing (`75/25` Drift)** allows the `SOXL` sleeve to balloon from `25.0%` to **`64.3%`** of the portfolio by 2026 and underperforms `100% TQQQ` during `2010–2019` (`45.74%` vs `46.16%`).
   - **Periodic or Event Rebalancing (`Annual`, `Semi-Annual`, or `OnSwitch`) at `80/20` or `75/25`** harvests semiconductor cyclical volatility into the `TQQQ` core ("Shannon's Demon"), outperforming **both** standalone strategies in `2010–2019` (`48.30%` at `75/25 Annual` vs `46.16%` `TQQQ` and `45.31%` `SOXL`) while achieving **`60.12%`–`61.14%` full-period CAGR**, **`-45.87%`–`-45.93%` MaxDD** (`2024–2026` MaxDD **`-36.31%`**, smaller than `100% TQQQ`'s `-36.97%`!), and **`1.259`–`1.266` Sharpe**.
   - Across all **64 cells** of `SOXL (Trig ∈ [0.8..1.5] × Rec ∈ [-0.2..+0.7])` inside `75/25 Annual Rebalance` (`T6`), 100% of cells achieve `57.56% .. 61.22%` CAGR and `-45.59% .. -46.10%` MaxDD (total drawdown spread of only `0.51%`).

---

## T1. Volatility Estimators on V1-Daily TQQQ SEP (`2010-02-11 .. 2026-11-03`)

| Estimator (`Trig=1.2, Rec=0.3`, Next-Day Open + `10bp/side`) | `W20` CAGR | `W20` MaxDD | `W20` Sharpe | 15-Cell Median CAGR | 15-Cell Worst DD | `W8` CAGR / DD | `W10` CAGR / DD | `W12` CAGR / DD | `W15` CAGR / DD | `W25` CAGR / DD | `W30` CAGR / DD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`1. Close-to-Close` *(Current Frozen Baseline)*** | **`54.97%`** | **`-44.54%`** | **`1.261`** | **`54.97%`** | `-46.29%` | `52.8% / -69.9%` | `50.5% / -69.9%` ❌ | `56.2% / -43.5%` | `58.5% / -43.5%` | `53.0% / -44.5%` | `53.4% / -46.6%` |
| `2. Open-to-Close` *(Intraday Body Only)* | `52.87%` | `-44.54%` | `1.210` | `52.26%` | `-58.56%` | `50.3% / -69.9%` | `50.3% / -69.9%` ❌ | `50.7% / -69.9%` | `54.7% / -44.5%` | `49.7% / -44.5%` | `50.3% / -51.5%` |
| **`3. Parkinson High-Low` *(Intraday H/L Range)*** | `52.56%` | `-44.54%` | `1.211` | `52.20%` | **`-44.54%`** | **`54.5% / -45.1%`** ✅ | **`55.2% / -44.5%`** ✅ | **`55.4% / -44.5%`** ✅ | `54.3% / -44.5%` | `50.9% / -44.5%` | `51.0% / -44.5%` |
| **`4. True Range RMS` *(High-Low + Overnight Gap)*** | `52.72%` | `-44.54%` | `1.221` | `52.32%` | **`-44.54%`** | `51.1% / -69.9%` | **`54.9% / -44.5%`** ✅ | **`55.6% / -44.5%`** ✅ | `53.4% / -44.5%` | `51.3% / -44.5%` | `51.1% / -44.5%` |
| **`5. Classic ATR%` *(Avg True Range / Close)*** | `52.03%` | `-44.54%` | `1.211` | `52.33%` | **`-44.54%`** | `53.1% / -69.9%` | **`56.4% / -44.5%`** ✅ | **`55.9% / -44.5%`** ✅ | `54.1% / -44.5%` | `51.4% / -44.5%` | `48.2% / -58.1%` |
| `6. Garman-Klass` *(Intraday OHLC)* | `50.42%` | `-44.54%` | `1.180` | `50.42%` | `-44.85%` | `56.7% / -43.6%` | `54.6% / -44.9%` ✅ | `53.2% / -44.9%` | `53.9% / -44.5%` | `48.0% / -44.5%` | `49.7% / -50.7%` |
| `7. Yang-Zhang / GK-YZ` *(Full OHLC + Gap)* | `53.48%` | `-44.54%` | `1.230` | `52.33%` | **`-44.54%`** | `52.4% / -69.9%` | `50.1% / -69.9%` ❌ | `53.7% / -43.5%` | `53.0% / -44.5%` | `49.8% / -44.5%` | `51.4% / -44.5%` |

---

## T2. 1x Underlying `Vol_Z` (`QQQ` / `SOXX`) vs 3x ETF Own `Vol_Z` (`TQQQ` / `SOXL`)

| Variant | Corr vs `1x Vol_Z` | Full CAGR | Total Mult | `2010–2019` CAGR | `2020–2026` CAGR | MaxDD | Daily Sharpe | Switches | Closed `3x` Wins |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`TQQQ` — `Vol_Z` from `1x QQQ` *(Frozen Standard)*** | `1.00000` | **`54.97%`** | `1,520.5x` | `48.94%` | `64.11%` | **`-44.54%`** | `1.261` | 33 | `16 / 16` |
| `TQQQ` — `Vol_Z` from `3x TQQQ` *(with 2009 3x Warm-up)* | **`0.99960`** | `55.74%` | `1,652.3x` | `50.20%` | `64.11%` | `-44.54%` | `1.274` | 33 | `16 / 16` |
| `TQQQ` — `Vol_Z` from `3x TQQQ` *(Raw Post-Inception Only)* | **`0.99960`** | `54.55%` | `1,452.9x` | `48.26%` | `64.11%` | `-44.54%` | `1.241` | 31 | `15 / 15` |
| **`SOXL` — `Vol_Z` from `1x SOXX` *(Standard, -> `1x SOXX`)*** | `1.00000` | **`69.62%`** | **`6,616.1x`** | **`44.39%`** | **`113.66%`** | **`-70.83%`** | **`1.119`** | 32 | `15 / 16` |
| `SOXL` — `Vol_Z` from `3x SOXL` *(with 2009 3x Warm-up)* | **`0.99831`** | `68.08%` | `5,682.4x` | `43.71%` | `110.38%` | `-70.83%` | `1.102` | 34 | `16 / 17` |
| `SOXL` — `Vol_Z` from `3x SOXL` *(Raw Post-Inception Only)* | **`0.99831`** | `63.89%` | `3,734.8x` | `37.69%` | `110.38%` | `-72.61%` | `1.050` | 30 | `14 / 15` |

---

## T3. `SOXL` Standalone `V1-Daily` Variants & De-levering Target Matrix (`2010-03-11 .. 2026-11-03`)

| Strategy (`2010-03-11 .. 2026-11-03`, Next-Day Open + `10bp/side`) | Full CAGR | Total Mult | `2010–2019` CAGR | `2020–2026` CAGR | MaxDD | MaxDD Window | `2024–2026` DD | `2022` Ret | Daily Sharpe | Switches | Closed `3x` Wins |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `0a. SOXX (1x Semiconductor) Buy & Hold` | `23.71%` | `34.5x` | `17.56%` | `33.24%` | `-45.75%` | `2021-12-27->2022-10-14` | `-39.77%` | `-35.09%` | `0.843` | 0 | — |
| `0b. SOXL (3x Semiconductor) Buy & Hold` | `33.42%` | `121.6x` | `25.81%` | `45.36%` | `-90.46%` | `2021-12-27->2022-10-14` | `-78.41%` | `-85.66%` | `0.779` | 0 | — |
| `1. SOXL Pure FOMC SEP Only (SEP=ON -> SOXL, OFF -> Cash)` | `61.37%` | `2,882.8x` | `37.69%` | `103.52%` | `-80.38%` | `2020-02-12->2020-03-20` | `-70.83%` | `+1.58%` | `1.008` | 9 | `4 / 5` |
| `2. SOXL + SEP + SOXX Vol_Z(1.2/0.3) NO NSL (Accept Loss)` | `57.28%` | `1,880.2x` | `39.17%` | `88.24%` | `-66.50%` | `2024-07-10->2025-04-08` | `-66.50%` | `+1.58%` | `1.038` | 48 | `14 / 24` |
| **`3a. SOXL V1-Daily (Vol_Z on SOXX -> De-lever to 1x SOXX)`** | **`69.62%`** | **`6,616.1x`** | `44.39%` | **`113.66%`** | `-70.83%` | `2024-10-14->2025-04-08` | `-70.83%` | `+1.58%` | `1.119` | 32 | **`15 / 16`** |
| **`3b. SOXL V1-Daily (Vol_Z on SOXX -> De-lever to 1x QQQ)`** 🏆 | **`69.96%`** | **`6,840.3x`** | **`45.31%`** | **`112.77%`** | `-70.83%` | `2024-10-14->2025-04-08` | `-70.83%` | `+1.58%` | **`1.127`** | 32 | **`15 / 16`** |
| `3c. SOXL V1-Daily (Vol_Z on QQQ -> De-lever to 1x SOXX)` | `64.34%` | `3,908.5x` | `46.51%` | `94.25%` | `-67.50%` | `2018-03-12->2018-12-24` | `-62.90%` | `+1.58%` | `1.086` | 33 | `15 / 16` |
| `3d. SOXL V1-Daily (Vol_Z on QQQ -> De-lever to 1x QQQ)` | `63.86%` | `3,723.2x` | `46.08%` | `93.69%` | `-68.23%` | `2018-03-12->2018-12-24` | `-62.90%` | `+1.58%` | `1.087` | 33 | `15 / 16` |
| `3e. SOXL V1-Daily (Vol_Z on SOXX -> De-lever to 0x Cash)` | `61.93%` | `3,053.6x` | `38.68%` | `103.11%` | `-80.87%` | `2020-02-12->2020-03-20` | `-70.83%` | `+1.58%` | `1.021` | 32 | `15 / 16` |
| `3f. SOXL -> 3x TQQQ (if QQQ calm) -> 1x QQQ Ladder` | `63.35%` | `3,533.2x` | `40.48%` | `103.55%` | `-72.95%` | `2024-07-10->2025-04-08` | `-72.95%` | `+1.58%` | `1.066` | 45 | — |
| `4a. SOXL V1-Daily + Parkinson High-Low Vol_Z (20d)` | `61.58%` | `2,947.1x` | `42.25%` | `94.46%` | `-72.61%` | `2011-02-17->2011-10-03` | `-70.83%` | `+1.58%` | `1.047` | 32 | `14 / 15` |
| `4b. SOXL V1-Daily + Parkinson High-Low Vol_Z (10d)` | `60.97%` | `2,766.8x` | `39.77%` | `97.70%` | `-70.83%` | `2024-10-14->2025-04-08` | `-70.83%` | `+1.58%` | `1.032` | 40 | `19 / 20` |
| `5. SOXL V1-Daily + HYG/IEF SMA200 Gate` | `67.79%` | `5,520.1x` | `41.15%` | `115.01%` | `-70.83%` | `2024-10-14->2025-04-08` | `-70.83%` | `+1.58%` | `1.094` | 21 | `10 / 11` |
| *`Ref-2. TQQQ (3x Nasdaq-100) Buy & Hold (Same Dates)`* | *`38.74%`* | *`233.2x`* | *`43.09%`* | *`32.68%`* | *`-81.65%`* | *`2021-11-19->2022-12-28`* | *`-47.92%`* | *`-79.08%`* | *`0.845`* | *0* | *—* |
| *`Ref-4. TQQQ Frozen V1-Daily (Same Dates)`* | ***`53.29%`*** | ***`1,226.3x`*** | ***`46.16%`*** | ***`64.35%`*** | ***`-44.54%`*** | *`2015-07-20->2016-02-09`* | ***`-36.97%`*** | *`+1.58%`* | ***`1.233`*** | *33* | ***`16 / 16`*** |

---

## T4. `SOXL` Standalone 2D `(Trig × Rec)` Parameter Plateau (`Vol_Z` on `SOXX` $\rightarrow$ `1x QQQ`)

| `Trig \ Rec` | `-0.4` | `-0.2` | `-0.1` | `+0.0` | `+0.1` | `+0.2` | **`+0.3` *(Frozen)*** | `+0.4` | `+0.5` | `+0.7` |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `0.6` | `59.0% / -67.3%` | `59.2% / -63.9%` | `59.4% / -63.9%` | `58.9% / -65.2%` | `61.4% / -67.4%` | `60.8% / -67.4%` | `63.2% / -66.6%` | `64.2% / -66.9%` | `65.2% / -66.9%` | — |
| `0.8` | `61.5% / -67.7%` | `61.6% / -63.9%` | `62.3% / -63.9%` | `62.2% / -66.9%` | `62.9% / -69.0%` | `63.5% / -69.0%` | `65.4% / -68.3%` | `66.0% / -68.3%` | `67.6% / -68.3%` | `70.1% / -68.3%` |
| `0.9` | `59.7% / -70.8%` | `62.2% / -70.8%` | `63.1% / -70.8%` | `61.6% / -70.8%` | `62.3% / -70.8%` | `62.5% / -70.8%` | `63.9% / -70.8%` | `65.5% / -70.8%` | `66.7% / -70.8%` | `70.1% / -70.8%` |
| **`1.0`** | `62.9% / -70.8%` | `65.5% / -70.8%` | `66.4% / -70.8%` | **`64.8% / -70.8%`** | **`65.5% / -70.8%`** | **`65.8% / -70.8%`** | **`67.3% / -70.8%`** | **`69.5% / -70.8%`** | **`69.9% / -70.8%`** | **`71.2% / -70.8%`** |
| **`1.1`** | `63.4% / -70.8%` | `65.9% / -70.8%` | `66.8% / -70.8%` | **`65.3% / -70.8%`** | **`66.0% / -70.8%`** | **`66.2% / -70.8%`** | **`67.8% / -70.8%`** | **`70.0% / -70.8%`** | **`70.4% / -70.8%`** | **`72.3% / -70.8%`** |
| **`1.2` *(Frozen)*** | `64.9% / -70.8%` | `67.7% / -70.8%` | `68.6% / -70.8%` | **`67.1% / -70.8%`** | **`67.7% / -70.8%`** | **`69.0% / -70.8%`** | **`70.0% / -70.8%`** 🏆 | **`72.0% / -70.8%`** | **`72.4% / -70.8%`** | **`74.4% / -70.8%`** |
| **`1.3`** | `62.7% / -70.8%` | `64.6% / -70.8%` | `65.4% / -70.8%` | **`63.7% / -70.8%`** | **`63.4% / -70.8%`** | **`65.6% / -70.8%`** | **`66.3% / -70.8%`** | **`67.1% / -70.8%`** | **`68.3% / -70.8%`** | **`68.8% / -70.8%`** |
| `1.4` | `62.0% / -74.7%` | `64.0% / -72.6%` | `64.9% / -72.6%` | `63.2% / -72.6%` | `62.7% / -72.6%` | `63.0% / -72.6%` | `63.7% / -72.6%` | `63.5% / -72.6%` | `67.7% / -70.8%` | `68.3% / -70.8%` |
| `1.5` | `60.3% / -74.7%` | `62.1% / -72.6%` | `63.1% / -72.6%` | `61.4% / -72.6%` | `60.8% / -72.6%` | `61.7% / -72.6%` | `61.9% / -72.6%` | `63.2% / -72.6%` | `65.8% / -70.8%` | `66.3% / -70.8%` |
| `1.6` | `61.0% / -74.7%` | `61.6% / -72.6%` | `62.5% / -72.6%` | `60.9% / -72.6%` | `60.3% / -72.6%` | `60.4% / -72.6%` | `60.6% / -72.6%` | `61.9% / -72.6%` | `64.4% / -70.8%` | `64.9% / -70.8%` |

---

## T5. `TQQQ + SOXL` Rebalanced Blend: Weight × Rebalance Frequency 2D Plateau (`Both De-lever to 1x QQQ`)

> Full 74-row table with `2010–2019` CAGR, `2020–2026` CAGR, `2024–2026` MaxDD, rebalance counts, and max `SOXL` weight drift: [`T5_blend_weight_x_rebalance_frequency_plateau.csv`](./T5_blend_weight_x_rebalance_frequency_plateau.csv)

| `TQQQ / SOXL` Weight | `Monthly` | `Quarterly` | **`Semi-Annual`** | **`Annual`** | **`OnSwitch`** 🏆 | `Band ±5%` | `Band ±10%` | `Band ±15%` |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| *`100 / 0` (Pure TQQQ)* | *`53.3% / -44.5% (1.23)`* | *`53.3% / -44.5% (1.23)`* | *`53.3% / -44.5% (1.23)`* | *`53.3% / -44.5% (1.23)`* | *`53.3% / -44.5% (1.23)`* | *`53.3% / -44.5% (1.23)`* | *`53.3% / -44.5% (1.23)`* | *`53.3% / -44.5% (1.23)`* |
| **`90 / 10`** | `56.0% / -44.4% (1.25)` | `56.0% / -44.5% (1.25)` | `56.4% / -44.5% (1.26)` | `56.3% / -44.5% (1.25)` | `57.0% / -44.5% (1.26)` | `56.4% / -44.5% (1.26)` | `55.6% / -44.5% (1.25)` | `55.8% / -44.5% (1.25)` |
| **`85 / 15`** | `57.3% / -44.4% (1.26)` | `57.2% / -44.5% (1.25)` | `57.9% / -44.5% (1.26)` | `57.7% / -44.5% (1.26)` | **`58.5% / -44.5% (1.27)`** | `57.4% / -44.4% (1.25)` | `56.4% / -44.5% (1.25)` | `56.8% / -44.5% (1.25)` |
| **`80 / 20`** 🏆 | `58.5% / -44.4% (1.26)` | `58.4% / -44.7% (1.25)` | **`59.2% / -44.8% (1.26)`** | **`58.9% / -44.7% (1.26)`** | **`59.9% / -44.7% (1.27)`** | `58.6% / -44.6% (1.26)` | **`59.9% / -44.4% (1.27)`** | `57.6% / -44.5% (1.25)` |
| **`75 / 25`** 🏆 | `59.7% / -45.6% (1.26)` | `59.5% / -46.0% (1.25)` | **`60.4% / -46.0% (1.26)`** | **`60.1% / -45.9% (1.26)`** | **`61.1% / -45.9% (1.27)`** | `59.6% / -45.8% (1.25)` | `60.3% / -46.6% (1.26)` | `58.4% / -44.4% (1.25)` |
| `70 / 30` | `60.8% / -46.8% (1.26)` | `60.6% / -47.2% (1.25)` | `61.5% / -47.3% (1.26)` | `61.2% / -47.1% (1.26)` | `62.3% / -47.1% (1.26)` | `60.7% / -46.4% (1.25)` | `60.5% / -47.4% (1.26)` | `60.6% / -49.2% (1.25)` |
| `65 / 35` | `61.9% / -47.9% (1.25)` | `61.6% / -48.4% (1.25)` | `62.6% / -48.5% (1.26)` | `62.3% / -48.3% (1.25)` | `63.3% / -48.3% (1.26)` | `62.7% / -48.1% (1.26)` | `62.4% / -48.5% (1.26)` | `62.8% / -49.9% (1.25)` |
| `60 / 40` | `62.8% / -49.1% (1.25)` | `62.6% / -49.6% (1.24)` | `63.6% / -49.7% (1.25)` | `63.2% / -49.5% (1.25)` | `64.2% / -49.4% (1.25)` | `63.3% / -48.7% (1.25)` | `63.4% / -49.3% (1.25)` | `63.1% / -50.7% (1.24)` |
| `50 / 50` | `64.7% / -51.5% (1.23)` | `64.3% / -51.9% (1.23)` | `65.3% / -52.0% (1.24)` | `65.0% / -51.9% (1.23)` | `65.9% / -51.8% (1.24)` | `64.7% / -51.8% (1.23)` | `65.5% / -51.3% (1.23)` | `66.1% / -52.6% (1.24)` |

---

## T6. `75% TQQQ + 25% SOXL` (Annual Rebalance, Both De-lever to `1x QQQ`) × `SOXL (Trig, Rec)` 64-Cell Plateau

> Full CSV: [`T6_blend_75_25_annual_x_soxl_trig_rec_64cell_plateau.csv`](./T6_blend_75_25_annual_x_soxl_trig_rec_64cell_plateau.csv)

| `SOXL Trig \ Rec` | `-0.2` | `+0.0` | `+0.1` | `+0.2` | **`+0.3` *(Frozen)*** | `+0.4` | `+0.5` | `+0.7` |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `0.8` | `57.6% / -45.7%` | `58.1% / -45.7%` | `58.4% / -45.6%` | `58.3% / -45.9%` | `58.9% / -45.9%` | `59.2% / -45.6%` | `59.5% / -45.6%` | `60.1% / -45.6%` |
| `0.9` | `57.6% / -46.1%` | `57.6% / -46.1%` | `57.9% / -45.9%` | `57.9% / -45.9%` | `58.3% / -45.9%` | `58.8% / -45.9%` | `59.0% / -45.9%` | `59.8% / -45.9%` |
| **`1.0`** | `58.5% / -46.1%` | `58.5% / -46.1%` | `58.9% / -45.9%` | `58.8% / -45.9%` | `59.2% / -45.9%` | `59.9% / -45.9%` | `60.0% / -45.9%` | `60.2% / -45.9%` |
| **`1.1`** | `58.6% / -46.1%` | `58.7% / -46.1%` | `59.0% / -45.9%` | `59.0% / -45.9%` | `59.4% / -45.9%` | `60.1% / -45.9%` | `60.1% / -45.9%` | `60.5% / -45.9%` |
| **`1.2` *(Frozen)*** | `59.2% / -46.1%` | `59.3% / -46.1%` | `59.6% / -45.9%` | `59.9% / -45.9%` | **`60.1% / -45.9%`** 🏆 | **`60.8% / -45.9%`** | **`60.8% / -45.9%`** | **`61.2% / -45.9%`** |
| **`1.3`** | `58.4% / -45.9%` | `58.4% / -45.9%` | `58.4% / -45.9%` | `59.0% / -45.9%` | `59.1% / -45.9%` | `59.4% / -45.9%` | `59.6% / -45.9%` | `59.7% / -45.9%` |
| `1.4` | `58.5% / -45.9%` | `58.5% / -45.9%` | `58.4% / -45.9%` | `58.6% / -45.9%` | `58.7% / -45.9%` | `58.6% / -45.9%` | `59.6% / -45.9%` | `59.7% / -45.9%` |
| `1.5` | `58.1% / -45.9%` | `58.1% / -45.9%` | `58.0% / -45.9%` | `58.2% / -45.9%` | `58.3% / -45.9%` | `58.7% / -45.9%` | `59.1% / -45.9%` | `59.2% / -45.9%` |
