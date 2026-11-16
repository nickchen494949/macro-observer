# Frozen V1 TQQQ Strategy — Complete Audit & Specification (`V1-Daily: SEP + 1Y Vol_Z + NSL`, 2026-11-16)

> **Standalone Reproducible Engine**: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)  
> **Summary Metrics CSV**: [`v1_tqqq_summary.csv`](./v1_tqqq_summary.csv)  
> **Complete Trade Ledger (`2009–2026`)**: [`v1_daily_trade_ledger_2009_2026.csv`](./v1_daily_trade_ledger_2009_2026.csv)  
> **Sweet-Spot Trade Ledger (`1.2 / 0.3`)**: [`v1_daily_sweetspot_trade_ledger_2009_2026.csv`](./v1_daily_sweetspot_trade_ledger_2009_2026.csv)  
> **Year-by-Year Returns (`2009–2026`)**: [`v1_daily_annual_returns_2009_2026.csv`](./v1_daily_annual_returns_2009_2026.csv)  
> **Parameter Plateau Grid (`30 Configs`)**: [`v1_daily_parameter_grid_2009_2026.csv`](./v1_daily_parameter_grid_2009_2026.csv)

---

## 1. Frozen V1-Daily Specification (Zero-Patch Pure Rules)

### Layer 1: Macro Gate (`FOMC SEP` $\rightarrow$ `Pure Cash 0x`)
- **Target Horizon Rule**:
  - **March & June (`month < 9`)**: Compare current-year (`YYYY`) FOMC SEP median Core PCE & Fed Funds Rate projections vs the previous SEP meeting.
  - **September & December (`month >= 9`)**: Compare next-year (`YYYY + 1`) FOMC SEP median Core PCE & Fed Funds Rate projections vs the previous SEP meeting.
- **State Transition**:
  - **`EXIT (SEP = OFF)`**: `(c_rate > p_rate) and (c_pce > p_pce) and (c_pce > 2.0%)` $\rightarrow$ Switch **`100%` to Pure Cash (`SGOV` / `DGS3MO`)**, unconditionally overriding `NSL`.
  - **`ENTER (SEP = ON)`**: `(c_rate <= p_rate)`.

### Layer 2: Daily Volatility Switch (`When SEP = ON` $\rightarrow$ `3x TQQQ` vs `1x QQQ` with `NSL`)
- **Indicator Calculation (on `QQQ` daily returns $r_{\text{QQQ}}$, strictly lagged 1 trading day)**:
  - $\text{rvol}_{20}(d) = \text{std}(r_{\text{QQQ}}, 20\text{d}) \times \sqrt{252} \times 100$
  - $\mu_{252}(d) = \text{mean}(\text{rvol}_{20}, 252\text{d})$, $\quad \sigma_{252}(d) = \text{std}(\text{rvol}_{20}, 252\text{d})$
  - $\text{Vol\_Z}(d) = \frac{\text{rvol}_{20}(d) - \mu_{252}(d)}{\sigma_{252}(d)}$
- **Execution Rules**:
  - **Trim `3x TQQQ` $\rightarrow$ `1x QQQ` (`VOL DANGER` + `NSL`)**: When holding `3x TQQQ`, if $\text{Vol\_Z}(d-1) > \text{Trig}$ **AND** $\text{Equity}(d-1) \ge \text{Entry\_Equity}$ (**`NSL`: Never Sell in Loss / 只止盈不割肉**), switch `100%` from `3x TQQQ` to **`1x QQQ`**.
  - **Re-enter `1x QQQ` $\rightarrow$ `3x TQQQ` (`VOL CALM`)**: When holding `1x QQQ`, if $\text{Vol\_Z}(d-1) < \text{Rec}$, switch `100%` from `1x QQQ` to **`3x TQQQ`** and reset $\text{Entry\_Equity} = \text{Equity}(d-1)$.
  - **Frozen Parameters**:
    - **Primary Standard**: `Window = 252d`, `Trig = 1.5`, `Rec = 0.5`
    - **Plateau Sweet-Spot**: `Window = 252d`, `Trig = 1.2`, `Rec = 0.3`

---

## 2. Headline Performance Comparison (`2009–2026` & `2010–2026`)

| Strategy Variant | `2009–2026` CAGR | `2009–2026` Daily MaxDD | `2009–2026` Sharpe | `2009–2026` Multiple | `2010–2026` CAGR | `2010–2026` Daily MaxDD | `2010–2026` Sharpe | `2010–2026` Multiple |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. `V1-Daily` Standard (`1.5 / 0.5 + NSL`) [FROZEN PRIMARY]** 🏆 | **`57.6%`** | **`-48.3%`** | **`1.21`** | **`3,369.2x`** | **`51.8%`** | **`-43.5%`** | **`1.18`** | **`1,131.9x`** |
| **2. `V1-Daily` Sweet-Spot (`1.2 / 0.3 + NSL`) [FROZEN PLATEAU]** 🏆 | **`57.8%`** | **`-48.3%`** | **`1.23`** | **`3,436.4x`** | **`52.7%`** | **`-44.5%`** | **`1.21`** | **`1,261.1x`** |
| **3. `V1-Monthly` Ratio (`(std_252/std_21)^2 + NSL`)** | `55.9%` | `-54.3%` | `1.16` | `2,744.7x` | `49.6%` | `-54.3%` | `1.10` | `876.3x` |
| **4. Pure `SEP` Baseline (`SEP=ON` 100% TQQQ, `SEP=OFF` Cash)** | `56.3%` | `-69.9%` | `1.08` | `2,900.3x` | `50.4%` | `-69.9%` | `1.04` | `974.3x` |
| **5. `3x TQQQ` Buy & Hold (No SEP, No Vol)** | `44.5%` | `-81.7%` | `0.90` | `714.7x` | `38.4%` | `-81.7%` | `0.84` | `240.1x` |
| **6. `1x QQQ` Buy & Hold** | `20.3%` | `-35.1%` | `0.95` | `27.1x` | `18.3%` | `-35.1%` | `0.91` | `17.1x` |

---

## 3. Year-by-Year Return & Drawdown Breakdown (`2009–2026`)

| Year | `1x QQQ` | `3x TQQQ` B&H | `Pure SEP` | **`V1-Daily (1.5/0.5)`** | **`V1-Daily (1.2/0.3)`** | **`V1-Daily` MaxDD** |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2009** | `+54.70%` | `+197.67%` | `+197.67%` | **`+197.67%`** | **`+197.67%`** | `-48.30%` |
| **2010** | `+19.91%` | `+52.22%` | `+52.22%` | **`+73.21%`** | **`+58.28%`** | `-32.02%` |
| **2011** | `+3.38%` | `-8.05%` | `-8.05%` | `-12.61%` | **`+4.05%`** | `-40.76%` |
| **2012** | `+18.12%` | `+52.29%` | `+52.29%` | **`+52.29%`** | **`+52.29%`** | `-31.94%` |
| **2013** | `+36.63%` | `+139.73%` | `+139.73%` | **`+139.73%`** | **`+139.73%`** | `-17.31%` |
| **2014** | `+19.18%` | `+57.09%` | `+57.09%` | `+24.30%` | `+28.13%` | `-22.49%` |
| **2015** | `+9.45%` | `+17.23%` | `+17.23%` | **`+20.22%`** | `+7.53%` | `-37.24%` |
| **2016** | `+7.10%` | `+11.38%` | `+11.38%` | **`+11.38%`** | **`+11.38%`** | `-34.12%` |
| **2017** | `+32.66%` | `+118.06%` | `+118.06%` | `+99.60%` | `+108.13%` | `-14.66%` |
| **2018** | `-0.12%` | `-19.81%` | `-19.81%` | **`+1.60%`** | **`+7.94%`** | `-37.40%` |
| **2019** | `+38.96%` | `+133.83%` | `+133.83%` | `+107.16%` | `+107.16%` | `-30.50%` |
| **2020** | `+48.62%` | `+110.05%` | `+110.05%` | **`+191.84%`** | **`+180.30%`** | **`-38.02%`** |
| **2021** | `+27.42%` | `+82.98%` | `+39.56%` | **`+39.56%`** | **`+39.56%`** | `-30.43%` |
| **2022** | `-32.58%` | `-79.08%` | `+2.10%` | **`+2.10%`** | **`+2.10%`** | **`0.00%`** |
| **2023** | `+54.85%` | `+198.26%` | `+53.52%` | **`+53.52%`** | **`+53.52%`** | `-10.19%` |
| **2024** | `+25.58%` | `+58.23%` | `+82.01%` | **`+69.80%`** | `+62.26%` | `-21.35%` |
| **2025** | `+20.77%` | `+34.37%` | `+81.55%` | **`+86.30%`** | **`+86.30%`** | `-22.97%` |
| **2026 (YTD)** | `+10.72%` | `+9.86%` | `+49.72%` | **`+45.05%`** | **`+45.05%`** | `-33.49%` |

---

## 4. Complete Trade-by-Trade Ledger (`2009–2026`, `Trig = 1.5 / Rec = 0.5`)

Every single `3x TQQQ` leg (`15 / 15 = 100%` win rate) closed with a positive gain:

| Date | Switch | Trigger Reason | `Vol_Z` | `rvol_20` | `1Y Mean` | Portfolio Multiple | Completed `3x` Leg Return |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `2010-05-11` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.80` | `30.74%` | `17.14%` | `3.24x` | **`+224.37%`** |
| `2010-07-15` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.44` | `21.50%` | `18.45%` | `3.10x` | — |
| `2011-08-05` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.69` | `24.88%` | `15.19%` | `4.84x` | **`+56.09%`** |
| `2011-11-08` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.48` | `24.38%` | `19.67%` | `5.21x` | — |
| `2014-01-31` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.54` | `15.97%` | `11.95%` | `15.51x` | **`+197.85%`** |
| `2014-03-03` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.36` | `13.39%` | `12.33%` | `16.27x` | — |
| `2014-10-13` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.76` | `18.94%` | `12.21%` | `18.20x` | **`+11.87%`** |
| `2014-11-11` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.35` | `14.26%` | `12.73%` | `19.65x` | — |
| `2015-08-28` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+4.46` | `32.53%` | `13.99%` | `20.70x` | **`+5.36%`** |
| `2015-10-07` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.49` | `19.59%` | `16.34%` | `20.63x` | — |
| `2017-07-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.56` | `17.30%` | `10.57%` | `42.05x` | **`+103.88%`** |
| `2017-07-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.49` | `11.99%` | `10.23%` | `44.02x` | — |
| `2018-02-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.90` | `19.35%` | `10.24%` | `56.51x` | **`+28.38%`** |
| `2018-05-09` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.48` | `18.44%` | `15.02%` | `59.45x` | — |
| `2018-10-26` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.36` | `32.56%` | `16.13%` | `61.39x` | **`+3.26%`** |
| `2019-01-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.20` | `23.55%` | `21.65%` | `59.44x` | — |
| `2020-02-25` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.71` | `23.23%` | `14.36%` | `127.16x` | **`+113.92%`** |
| `2020-05-06` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.37` | `32.21%` | `24.27%` | `125.29x` | — |
| `2021-10-04` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-0.48` | `14.92%` | `18.41%` | `468.42x` | **`+273.88%`** |
| `2023-04-04` | `0x -> 3x` | `SEP_ON_TO_3X` | `-1.47` | `20.29%` | `30.04%` | `484.05x` | — |
| `2023-07-05` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.30` | `16.62%` | `25.22%` | `714.43x` | **`+47.60%`** |
| `2024-01-03` | `0x -> 3x` | `SEP_ON_TO_3X` | `-1.20` | `13.49%` | `18.05%` | `734.47x` | — |
| `2024-05-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.84` | `20.15%` | `16.10%` | `868.26x` | **`+18.22%`** |
| `2024-05-17` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.44` | `17.16%` | `16.17%` | `901.16x` | — |
| `2024-07-02` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.47` | `11.77%` | `15.56%` | `1,075.95x` | **`+19.40%`** |
| `2024-10-02` | `0x -> 3x` | `SEP_ON_TO_3X` | `+0.21` | `18.10%` | `17.10%` | `1,090.32x` | — |
| `2025-01-03` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `+0.62` | `20.15%` | `17.21%` | `1,238.97x` | **`+13.63%`** |
| `2025-04-02` | `0x -> 1x` | `SEP_ON_HIGH_VOL_TO_1X` | `+1.67` | `27.27%` | `18.56%` | `1,251.83x` | — |
| `2025-05-12` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.13` | `23.84%` | `22.34%` | `1,292.27x` | — |
| `2026-06-08` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.96` | `23.46%` | `15.56%` | `3,223.80x` | **`+149.47%`** |
| `2026-07-02` | `1x -> 0x` | `SEP_OFF_TO_CASH` | `+3.31` | `34.24%` | `16.57%` | `3,319.40x` | — |

---

## 5. Parameter Plateau Audit (`Window = 252d`, No Parameter Cliff)

| `Trig` \ `Rec` | **`Rec = 0.0`** | **`Rec = 0.2`** | **`Rec = 0.3`** | **`Rec = 0.5`** | **`Rec = 0.7`** |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **`Trig = 1.0`** | `57.9%` (`-48.3%`) | `59.0%` (`-48.3%`) | **`60.0%` (`-48.3%`)** | `58.8%` (`-48.3%`) | `60.0%` (`-48.3%`) |
| **`Trig = 1.2`** | `55.6%` (`-48.3%`) | `56.8%` (`-48.3%`) | **`57.8%` (`-48.3%`)** 🏆 | **`57.6%` (`-48.3%`)** | `59.6%` (`-48.3%`) |
| **`Trig = 1.3`** | `54.9%` (`-48.3%`) | `56.1%` (`-48.3%`) | **`57.0%` (`-48.3%`)** | **`58.2%` (`-48.3%`)** | `59.2%` (`-48.3%`) |
| **`Trig = 1.5` (Standard)** | `54.3%` (`-51.3%`) | `55.5%` (`-50.2%`) | **`57.1%` (`-48.3%`)** | **`57.6%` (`-48.3%`)** 🏆 | `57.1%` (`-58.0%`) |
| **`Trig = 1.8`** | `53.7%` (`-51.3%`) | `54.8%` (`-50.2%`) | `56.5%` (`-48.3%`) | `56.9%` (`-48.3%`) | `56.6%` (`-58.0%`) |
| **`Trig = 2.0`** | `53.3%` (`-51.3%`) | `54.5%` (`-50.2%`) | `56.1%` (`-48.3%`) | `56.5%` (`-48.3%`) | `55.9%` (`-58.0%`) |

---

## 6. Live 2026-11 Status

- **Macro Gate (`SEP`)**: **`SEP = OFF`** (triggered `2026-06-17`, confirmed `2026-09-16` with Core PCE `3.4%` and 2027 dot `4.1%`) $\rightarrow$ **Current Live Holdings = `100% SGOV (Pure Cash)`**.
- **Daily `Vol_Z` Readout (`2026-11-13`)**: `Vol_Z = +2.15` (`> 1.5` $\rightarrow$ `VOL DANGER`).
