# Frozen V1.1-Daily `75% TQQQ + 25% SOXL` On-Switch Dynamic Rebalance & V1-Daily `100% TQQQ` SEP Strategy — Official Specification & Independent Audit Package (`Trig = 1.2 / Rec = 0.3`, `2010-02-11 .. 2026-11-03` 100% Real ETFs, Next-Day Open `adjOpen` + Two-Sided `10bp/side` + Dynamic Share-Lot NSL)

> **100% Self-Contained Reproducible Engines (Zero Local Cache Dependencies)**:
> - **V1.1 Dual-Sleeve `75% TQQQ + 25% SOXL` On-Switch Dynamic Rebalance Engine (3-Round External Audit Verified)**: [`remediate_soxl_tqqq_7point_audit.py`](../../remediate_soxl_tqqq_7point_audit.py) & [`REMEDIATION_7POINT_AUDIT_REPORT.md`](../soxl_and_vol_estimators_audit_20261126/REMEDIATION_7POINT_AUDIT_REPORT.md)
> - **V1 Single-Asset `100% TQQQ` Engine**: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)  
> **Summary Metrics CSVs**: [`R3_true_share_lot_dynamic_nsl_rebalance_audit.csv`](../soxl_and_vol_estimators_audit_20261126/R3_true_share_lot_dynamic_nsl_rebalance_audit.csv) & [`v1_tqqq_summary.csv`](./v1_tqqq_summary.csv)  
> **Primary Frozen Trade Ledger (`1.2/0.3`, `16/16 = 100%` Profitable `3x` Legs)**: [`v1_daily_trade_ledger_2009_2026.csv`](./v1_daily_trade_ledger_2009_2026.csv)  
> **Complete 2012–2026 FOMC SEP Meeting & Transition Table (`59 Meetings`)**: [`R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv`](../soxl_and_vol_estimators_audit_20261126/R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv) & [`fomc_sep_signal_verification_2008_2026.csv`](./fomc_sep_signal_verification_2008_2026.csv)  
> **30-Cell Parameter Plateau Grid**: [`v1_daily_parameter_grid_2009_2026.csv`](./v1_daily_parameter_grid_2009_2026.csv)

---

## 0. V1.1-Daily Primary Frozen Dual-Sleeve Specification (`75% TQQQ + 25% SOXL On-Switch Dynamic Rebalance`, 2026-11-26)

1. **Dual-Sleeve Target Allocation & Asset Mapping (`75% TQQQ Core Sleeve + 25% SOXL Satellite Sleeve`)**:
   - **`TQQQ` Core Sleeve (`75%` target weight)**: Trades `3x TQQQ <-> 1x QQQ <-> 0x SGOV/BIL`, driven by **`Vol_Z(QQQ)`** (`Trig = 1.2 / Rec = 0.3`, 20-day Close-to-Close volatility Z-score over 252-day window).
   - **`SOXL` Satellite Sleeve (`25%` target weight)**: Trades `3x SOXL <-> 1x QQQ <-> 0x SGOV/BIL`, driven by **`Vol_Z(SOXX)`** (`Trig = 1.2 / Rec = 0.3`, 20-day Close-to-Close volatility Z-score over 252-day window). When de-leveraging in `SEP = ON`, `SOXL` **always rotates into `1x QQQ` (NOT `1x SOXX`)**.
2. **Event-Driven On-Switch Dynamic Rebalance (`75% / 25%`) + Dynamic Share-Lot NSL Cost-Basis Update**:
   - Whenever **either sleeve executes a state switch (`3x <-> 1x QQQ` or `SEP` transition)** at day $d$ Open (`adjOpen`), simultaneously rebalance total account equity back to the fixed **`75% TQQQ Sleeve / 25% SOXL Sleeve`** target weights at day $d$ Open (charging two-sided `20bp` transaction cost on the rebalanced dollar delta unless both sleeves hold the identical `1x QQQ` or `0x Cash` asset).
   - When a rebalance purchases additional shares for an active `3x` sleeve (`TQQQ` or `SOXL`), append a new share lot at execution price `adjOpen / (1 - FEE)`, dynamically updating that sleeve's weighted-average `Open Limit NSL` cost basis.
3. **Audited Performance (`2010-03-11 .. 2026-11-03`, 4,189 Trading Days, Next-Day Open + Two-Sided `10bp/side` + Return-Chained `BIL->SGOV` Cash)**:
   - **`75/25 On-Switch Dynamic Rebalance (V1.1 Primary Frozen)`**: Full CAGR **`61.06%`** (`2,793.0x`), Daily MaxDD **`-45.87%`**, Daily Sharpe **`1.265`**, Pre-AI (`2010–2022`) CAGR **`51.52%`**, AI Era (`2023–2026`) CAGR **`97.39%`**, `2024–2026` MaxDD **`-37.28%`** (`50` switch-rebalances).
   - **`75/25 Annual Calendar Rebalance (Calendar Ref)`**: Full CAGR **`59.88%`** (`2,472.2x`, identical across `Average Cost`, `LIFO`, `FIFO`), Daily MaxDD **`-45.93%`**, Daily Sharpe **`1.256`**.
   - **`80/20 On-Switch / Annual Rebalance (Conservative Satellite Ref)`**: Full CAGR **`59.81% / 58.63%`**, Daily MaxDD **`-44.70%`**, Daily Sharpe **`1.266 / 1.255`**.
   - **`100% Pure TQQQ V1-Daily (Single-Asset Baseline)`**: `2010-03-11..2026-11-03` CAGR **`53.21%`** (`1,215.3x`; `2010-02-11..2026-11-03` **`54.89%`** / `1,506.8x`), Daily MaxDD **`-44.54%`**, Sharpe **`1.232`** (`1.259` from Feb 2010), Stateful Continuous Walk-Forward OOS (`2014–2026`) **`52.06%`** (`SOXL` WF OOS **`83.38%`**).

---

## 1. Complete Strategy Rules (`Frozen V1-Daily TQQQ SEP Strategy`)

Only trades 3 ETFs (`TQQQ`, `QQQ`, `SGOV`/`BIL`), with signals evaluated at day $d-1$ close (`adjClose[d-1]`) and executed at day $d$ open (`adjOpen[d]`):

1. **Layer 1 — Macro Gate (`FOMC SEP` $\rightarrow$ `100% Pure Cash SGOV`)**:
   - **Target Horizon**:
     - **March & June (`month < 9`)**: Compare current-year (`YYYY`) FOMC SEP median Core PCE & Fed Funds Rate projections vs that same `target_year` in the previous SEP meeting.
     - **September & December (`month >= 9`)**: Compare next-year (`YYYY + 1`) FOMC SEP median Core PCE & Fed Funds Rate projections vs that same `target_year` in the previous SEP meeting.
   - **`EXIT (SEP = OFF)`**: `(c_rate > p_rate) and (c_pce > p_pce) and (c_pce > 2.0%)` $\rightarrow$ Next trading day open (`adjOpen`), switch **`100%` to Pure Cash (`SGOV`/`BIL`)** (unconditionally overrides `NSL`).
   - **`ENTER (SEP = ON)`**: `(c_rate <= p_rate)` $\rightarrow$ Next trading day open (`adjOpen`), re-enter equity (`3x TQQQ` if `Vol_Z <= 1.2`, else `1x QQQ`).

2. **Layer 2 — Daily Volatility Switch (`When SEP = ON` $\rightarrow$ `3x TQQQ` vs `1x QQQ`)**:
   - On `QQQ` daily returns $r_{\text{QQQ}}$, compute 20-day annualized volatility $\text{rvol}_{20}(d)$ and its 252-day rolling mean $\mu_{252}(d)$ and std $\sigma_{252}(d)$:
     $$\text{Vol\_Z}(d) = \frac{\text{rvol}_{20}(d) - \mu_{252}(d)}{\sigma_{252}(d)}$$
   - **De-lever (`3x TQQQ` $\rightarrow$ `1x QQQ`, Profit-Only `Open Limit NSL`)**:
     - When holding `3x TQQQ`, if $\text{Vol\_Z}(d-1) > \mathbf{1.2}$ **AND** the position is in net profit after transaction fees both at $d-1$ close and at $d$ open ($\text{Equity\_Open\_Post\_Fee}(d) \ge \text{Entry\_Equity}$), switch `100%` from `3x TQQQ` to **`1x QQQ`** at day $d$ Open.
     - If underwater, hold `3x TQQQ` (never lock in a leveraged loss).
   - **Re-lever (`1x QQQ` $\rightarrow$ `3x TQQQ`, Unconditional on Signal)**:
     - When holding `1x QQQ`, as soon as $\text{Vol\_Z}(d-1) < \mathbf{0.3}$, switch `100%` from `1x QQQ` back to **`3x TQQQ`** at day $d$ Open (regardless of `1x QQQ` gain/loss, to re-lever at the bottom) and record new $\text{Entry\_Equity}$.

---

## 2. Headline Performance (`2010-02-11 .. 2026-11-03` 100% Real Tiingo ETFs, Next-Day Open `adjOpen` + `10bp/side`)

| Strategy Configuration (`2010-02-11 .. 2026-11-03` Real `TQQQ / QQQ / BIL / SGOV`) | **CAGR** | **Daily MaxDD** | **Sharpe** | **Multiple** | **Switches** | **Closed `3x` Legs Win Rate (Post-Cost)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. `V1-Daily` Primary Frozen (`1.2 / 0.3`) [Exact FOMC + Open Limit NSL + `10bp`]** 🏆 | **`54.89%`** | **`-44.54%`** | **`1.259`** | **`1,506.8x`** | `33` | **`16 / 16` (`100.0%`)** |
| **2. `V1-Daily` Conservative Ref (`1.5 / 0.5`) [Exact FOMC + Open Limit NSL + `10bp`]** | **`53.74%`** | **`-44.59%`** | **`1.221`** | **`1,331.1x`** | `31` | **`15 / 15` (`100.0%`)** |
| **3. `V1-Daily` Primary Frozen (`1.2 / 0.3`) — Month-End SEP Delay + Open Limit NSL** | `53.02%` | `-44.54%` | `1.228` | `1,230.7x` | `33` | **`16 / 16` (`100.0%`)** |
| **4. `V1-Monthly` Equal-Footed `Vol_Z` (`1.2 / 0.3`) — Month-End SEP + Open Limit NSL** | `48.57%` | `-58.08%` | `1.104` | `750.7x` | `28` | `14 / 14` (`100.0%`) |
| *5. [Ref] `V1-Daily` Primary (`1.2 / 0.3`) — Blind Market-on-Open (No Open Limit NSL)* | *`54.94%`* | *`-44.54%`* | *`1.261`* | *`1,516.1x`* | *`35`* | *`16 / 17` (`94.1%`)* |
| **6. Pure `SEP` Only (No `Vol_Z`) — Exact FOMC Open + `10bp/side`** | `53.74%` | `-69.92%` | `1.084` | `1,330.8x` | `9` | `5 / 5` |
| **7. Pure `SEP` Only (No `Vol_Z`) — Month-End SEP Delay + Open + `10bp/side`** | `52.04%` | `-69.92%` | `1.061` | `1,104.5x` | `9` | `5 / 5` |

---

## 3. Parameter Plateau Proof: Why `Trig = 1.2 / Rec = 0.3` Has Zero Parameter Cliff

Across the entire `Trig ∈ [1.0, 1.3]` × `Rec ∈ [0.0, 0.7]` region (15 contiguous grid cells surrounding `1.2 / 0.3`), Daily MaxDD stays locked between **`-44.54%` and `-46.29%`** (eliminating the `-58.08%` cliff that occurred at `Trig >= 1.5, Rec = 0.7`):

| `Trig` \ `Rec` | **`Rec = 0.0`** | **`Rec = 0.2`** | **`Rec = 0.3`** | **`Rec = 0.5`** | **`Rec = 0.7`** |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **`Trig = 1.0`** | `55.56%` (`-46.29%`) | `55.61%` (`-46.29%`) | **`57.14%` (`-46.29%`)** | `55.88%` (`-45.38%`) | `58.12%` (`-45.38%`) |
| **`Trig = 1.2` (Primary)** 🏆 | `53.32%` (**`-44.54%`**) | `53.29%` (**`-44.54%`**) | 🏆 **`54.89%` (`-44.54%`)** | **`54.75%` (`-44.54%`)** | **`57.73%` (`-44.59%`)** |
| **`Trig = 1.3`** | `52.61%` (**`-44.54%`**) | `52.58%` (**`-44.54%`**) | **`54.17%` (`-44.54%`)** | **`55.19%` (`-44.59%`)** | **`57.21%` (`-44.59%`)** |
| **`Trig = 1.5`** | `51.13%` (`-51.53%`) | `51.51%` (`-50.90%`) | `53.69%` (`-47.55%`) | `53.74%` (`-44.59%`) | `54.13%` (`-58.08%`) |

---

## 4. Complete Trade Ledger (`2010-02-11 .. 2026-11-03`, Primary Frozen `1.2 / 0.3`, Next-Day Open `adjOpen` + `10bp/side`)

All 16 completed `3x TQQQ` legs (`16 / 16 = 100.0%`) closed in net profit after `20bp` (`10bp/side`) transaction costs:

| Signal Close (`d-1`) | Exec Open (`d`) | Switch | Reason | `Vol_Z` | `rvol_20` | `1Y Mean` | Closed Asset | Leg Start | Leg Return Pre-Cost (`%`) | **Leg Return Post-Cost (`%`)** | Equity Multiple (Post-Cost) |
| :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2010-05-07` | `2010-05-10` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.34` | `23.53%` | `17.11%` | `3x` | `2010-02-11` | `+24.92%` | **`+24.67%`** | `1.25x` |
| `2010-07-29` | `2010-07-30` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.29` | `20.48%` | `18.51%` | `1x` | `2010-05-10` | `-4.16%` | `-4.35%` | `1.19x` |
| `2011-08-02` | `2011-08-03` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.29` | `19.72%` | `15.16%` | `3x` | `2010-07-30` | `+80.25%` | **`+79.89%`** | `2.15x` |
| `2011-12-27` | `2011-12-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.15` | `22.85%` | `21.41%` | `1x` | `2011-08-03` | `+0.12%` | `-0.08%` | `2.14x` |
| `2014-01-30` | `2014-01-31` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.54` | `15.97%` | `11.95%` | `3x` | `2011-12-28` | `+226.81%` | **`+226.16%`** | `6.99x` |
| `2014-03-04` | `2014-03-05` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `-0.60` | `10.54%` | `12.31%` | `1x` | `2014-01-31` | `+6.79%` | `+6.57%` | `7.45x` |
| `2014-10-09` | `2014-10-10` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.27` | `17.01%` | `12.19%` | `3x` | `2014-03-05` | `+16.23%` | **`+15.99%`** | `8.64x` |
| `2014-11-12` | `2014-11-13` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.19` | `13.59%` | `12.75%` | `1x` | `2014-10-10` | `+6.61%` | `+6.39%` | `9.19x` |
| `2015-01-08` | `2015-01-09` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.39` | `19.38%` | `13.01%` | `3x` | `2014-11-13` | `+2.76%` | **`+2.55%`** | `9.43x` |
| `2015-02-20` | `2015-02-23` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.28` | `14.55%` | `13.25%` | `1x` | `2015-01-09` | `+4.56%` | `+4.36%` | `9.84x` |
| `2017-06-28` | `2017-06-29` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.23` | `16.15%` | `10.65%` | `3x` | `2015-02-23` | `+83.36%` | **`+82.99%`** | `18.01x` |
| `2017-07-28` | `2017-07-31` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `-0.13` | `9.79%` | `10.24%` | `1x` | `2017-06-29` | `+3.46%` | `+3.25%` | `18.59x` |
| `2017-08-31` | `2017-09-01` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.21` | `14.88%` | `10.62%` | `3x` | `2017-07-31` | `+3.62%` | **`+3.41%`** | `19.22x` |
| `2017-09-15` | `2017-09-18` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `-0.07` | `10.56%` | `10.81%` | `1x` | `2017-09-01` | `-0.11%` | `-0.31%` | `19.17x` |
| `2018-02-05` | `2018-02-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.90` | `19.35%` | `10.24%` | `3x` | `2017-09-18` | `+18.35%` | **`+18.11%`** | `22.64x` |
| `2018-05-15` | `2018-05-16` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.28` | `17.20%` | `15.25%` | `1x` | `2018-02-06` | `+8.06%` | `+7.84%` | `24.41x` |
| `2018-10-16` | `2018-10-17` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.34` | `24.78%` | `15.56%` | `3x` | `2018-05-16` | `+14.08%` | **`+13.85%`** | `27.79x` |
| `2019-01-25` | `2019-01-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.20` | `23.55%` | `21.65%` | `1x` | `2018-10-17` | `-8.19%` | `-8.37%` | `25.47x` |
| `2020-02-24` | `2020-02-25` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.71` | `23.23%` | `14.36%` | `3x` | `2019-01-28` | `+127.86%` | **`+127.40%`** | `57.91x` |
| `2020-05-12` | `2020-05-13` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.24` | `29.83%` | `24.64%` | `1x` | `2020-02-25` | `-0.05%` | `-0.25%` | `57.76x` |
| `2021-09-22` | `2021-09-23` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-0.91` | `11.92%` | `19.03%` | `3x` | `2020-05-13` | `+282.73%` | **`+281.96%`** | `220.64x` |
| `2023-03-22` | `2023-03-23` | `0x -> 3x` | `SEP_ON_TO_3X` | `-1.49` | `20.86%` | `30.48%` | `0x` | `2021-09-23` | `+2.64%` | `+2.43%` | `226.00x` |
| `2023-06-14` | `2023-06-15` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.21` | `17.82%` | `26.23%` | `3x` | `2023-03-23` | `+55.26%` | **`+54.95%`** | `350.20x` |
| `2023-12-13` | `2023-12-14` | `0x -> 3x` | `SEP_ON_TO_3X` | `-2.29` | `10.00%` | `18.76%` | `0x` | `2023-06-15` | `+2.65%` | `+2.44%` | `358.76x` |
| `2024-04-30` | `2024-05-01` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.41` | `19.13%` | `16.06%` | `3x` | `2023-12-14` | `+6.75%` | **`+6.53%`** | `382.19x` |
| `2024-05-17` | `2024-05-20` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `-0.63` | `14.74%` | `16.16%` | `1x` | `2024-05-01` | `+6.81%` | `+6.60%` | `407.42x` |
| `2024-06-12` | `2024-06-13` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.55` | `11.97%` | `15.83%` | `3x` | `2024-05-20` | `+16.74%` | **`+16.51%`** | `474.67x` |
| `2024-09-18` | `2024-09-19` | `0x -> 3x` | `SEP_ON_TO_3X` | `+0.82` | `20.85%` | `16.91%` | `0x` | `2024-06-13` | `+1.44%` | `+1.24%` | `480.53x` |
| `2024-12-18` | `2024-12-19` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `+0.30` | `18.36%` | `16.92%` | `3x` | `2024-09-19` | `+20.26%` | **`+20.02%`** | `576.72x` |
| `2025-03-19` | `2025-03-20` | `0x -> 1x` | `SEP_ON_HIGH_VOL_TO_1X` | `+1.88` | `27.43%` | `18.16%` | `0x` | `2024-12-19` | `+1.07%` | `+0.87%` | `581.71x` |
| `2025-05-09` | `2025-05-12` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.13` | `23.84%` | `22.34%` | `1x` | `2025-03-20` | `+6.47%` | `+6.26%` | `618.10x` |
| `2026-06-05` | `2026-06-08` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.96` | `23.46%` | `15.56%` | `3x` | `2025-05-12` | `+135.06%` | **`+134.59%`** | `1,449.98x` |
| `2026-06-17` | `2026-06-18` | `1x -> 0x` | `SEP_OFF_TO_CASH` | `+3.00` | `29.22%` | `15.90%` | `1x` | `2026-06-08` | `+2.70%` | `+2.50%` | `1,486.17x` |
