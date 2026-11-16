# Frozen V1 TQQQ Strategy — Remediated Independent Audit & Specification (`2010-02-11 .. 2026-11-03` 100% Real ETFs, Next-Day Open `adjOpen` + `10bp/side`)

> **Standalone Reproducible Engine**: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)  
> **Summary Metrics CSV**: [`v1_tqqq_summary.csv`](./v1_tqqq_summary.csv)  
> **Complete Trade Ledger (`1.5/0.5`, All `3x`, `1x`, `0x` Legs)**: [`v1_daily_trade_ledger_2009_2026.csv`](./v1_daily_trade_ledger_2009_2026.csv)  
> **Sweet-Spot Trade Ledger (`1.2/0.3`, All `3x`, `1x`, `0x` Legs)**: [`v1_daily_sweetspot_trade_ledger_2009_2026.csv`](./v1_daily_sweetspot_trade_ledger_2009_2026.csv)  
> **FOMC SEP Point-in-Time Signal Table**: [`fomc_sep_signal_verification_2008_2026.csv`](./fomc_sep_signal_verification_2008_2026.csv)  
> **Parameter Plateau Grid (`30 Configs`, Next-Day Open + `10bp/side`)**: [`v1_daily_parameter_grid_2009_2026.csv`](./v1_daily_parameter_grid_2009_2026.csv)

---

## 1. 5-Point External Audit Remediation Summary

| Audit Item | Previous Commit (`a618dfa`) | Remediated Commit (Current) | Exact Quantitative Impact |
| :--- | :--- | :--- | :--- |
| **1. Next-Day Open Execution (`adjOpen`)** | Used close-to-close return on day $d$ | Signal at $d-1$ close (`adjClose[d-1]`); overnight return (`adjClose[d-1] -> adjOpen[d]`) earned on OLD asset; switch executes at $d$ Open (`adjOpen[d]`); intraday return (`adjOpen[d] -> adjClose[d]`) earned on NEW asset | In `1.5/0.5`, changes CAGR by `-0.76%/yr`; in `1.2/0.3`, Next-Day Open is `+0.27%/yr` higher (`53.02%` vs `52.75%`) |
| **2. Transaction Costs (`10bp/side`)** | `0bp` | Deducts `10bp/side` (`20bp = 0.20%` round-trip per switch) at $d$ Open | Only 31–33 switches over 16.7 years (~1.9/yr) $\rightarrow$ total cost impact is only **`-0.56%/yr`** |
| **3. 100% Real ETF History (`TQQQ` Launch `2010-02-11`)** | Included 2009 synthetic 3x splice alongside 2010–2026 | Primary benchmark strictly starts **`2010-02-11`** (actual Tiingo `TQQQ`, `QQQ`, `BIL`, `SGOV` OHLC; zero synthetic data) | `2010-02-11..2026-11-03` Real ETF CAGR: **`51.25%` (`1.5/0.5`) / `53.02%` (`1.2/0.3`)** |
| **4. FOMC SEP Signal Verification** | Referenced `v3_regime_and_cash_214m.csv` | Exported full month-end signal mapping [`fomc_sep_signal_verification_2008_2026.csv`](./fomc_sep_signal_verification_2008_2026.csv) (signal at month-end $t$ governs trading days in month $t+1$) | Zero look-ahead; month-end $t$ close executes on first trading day open of month $t+1$ |
| **5. `15/15` Leg Win Rate Accounting** | Reported `3x` legs at signal close (`15/15`) | Reports **all `3x`, `1x`, and `0x` legs** at actual **Next-Day Open (`adjOpen[d]`)** pre/post cost | Under Next-Day Open (`adjOpen`), the `2018-10-25` close signal (`+0.5%` profit) experienced an overnight gap down on `2018-10-26` Open to **`-7.98%`**, making `3x` leg win rate **`14/15 (93.3%)`** |

---

## 2. Headline Performance (`100% Real ETFs: 2010-02-11 .. 2026-11-03`, Next-Day Open `adjOpen` + `10bp/side`)

| Strategy (`2010-02-11 .. 2026-11-03` Real `TQQQ / QQQ / BIL / SGOV`) | Execution & Cost | **CAGR** | **Daily MaxDD** | **Sharpe** | **Multiple** | **Switches** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. `V1-Daily` Sweet-Spot (`1.2 / 0.3 + NSL`)** 🏆 | **Next-Day Open + `10bp/side`** | **`53.02%`** | **`-44.54%`** | **`1.23`** | **`1,230.7x`** | `33` |
| **2. `V1-Daily` Standard (`1.5 / 0.5 + NSL`)** 🏆 | **Next-Day Open + `10bp/side`** | **`51.25%`** | **`-44.59%`** | **`1.18`** | **`1,012.7x`** | `31` |
| **3. `V1-Monthly` Standard (`k=1.0`, `(std_252/std_21)^2 + NSL`)** | **Next-Day Open + `10bp/side`** | `51.39%` | `-53.89%` | `1.14` | `1,028.0x` | `201` |
| **4. `V1-Monthly` Sweet-Spot (`k=1.1`, `(1.1*std_252/std_21)^2 + NSL`)** | **Next-Day Open + `10bp/side`** | `51.59%` | `-55.71%` | `1.13` | `1,051.5x` | `201` |
| **5. Pure `SEP` Baseline (`SEP=ON` 100% TQQQ, `SEP=OFF` Cash)** | **Next-Day Open + `10bp/side`** | `52.04%` | `-69.92%` | `1.06` | `1,104.5x` | `9` |
| *6. [Reference] `V1-Daily` Sweet-Spot (`1.2 / 0.3 + NSL`)* | *Close-to-Close, `0bp`* | *`52.75%`* | *`-44.54%`* | *`1.22`* | *`1,194.4x`* | *`33`* |
| *7. [Reference] `V1-Daily` Standard (`1.5 / 0.5 + NSL`)* | *Close-to-Close, `0bp`* | *`52.57%`* | *`-43.45%`* | *`1.20`* | *`1,171.1x`* | *`31`* |

---

## 3. Complete Next-Day Open Trade Ledger (`2010-02-11 .. 2026-11-03`, `Trig = 1.5 / Rec = 0.5`, `10bp/side`)

Includes every `3x TQQQ` leg, every `1x QQQ` bridge leg, and every `0x Cash (BIL/SGOV)` leg executed at `adjOpen`:

| Signal Close (`d-1`) | Exec Open (`d`) | Switch | Reason | `Vol_Z` | `rvol_20` | `1Y Mean` | Closed Asset | Leg Start | Leg Return (Pre-Cost at `adjOpen`) | Cost (`bp`) | Equity Multiple (Post-Cost) |
| :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2010-05-10` | `2010-05-11` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.80` | `30.74%` | `17.14%` | `3x` | `2010-02-11` | **`+23.87%`** | `20.0` | `1.24x` |
| `2010-07-14` | `2010-07-15` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.44` | `21.50%` | `18.45%` | `1x` | `2010-05-11` | `-3.73%` | `20.0` | `1.19x` |
| `2011-08-04` | `2011-08-05` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.69` | `24.88%` | `15.19%` | `3x` | `2010-07-15` | **`+61.93%`** | `20.0` | `1.92x` |
| `2011-11-07` | `2011-11-08` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.48` | `24.38%` | `19.67%` | `1x` | `2011-08-05` | `+7.21%` | `20.0` | `2.05x` |
| `2014-01-30` | `2014-01-31` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.54` | `15.97%` | `11.95%` | `3x` | `2011-11-08` | **`+182.18%`** | `20.0` | `5.78x` |
| `2014-02-28` | `2014-03-03` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.36` | `13.39%` | `12.33%` | `1x` | `2014-01-31` | `+5.04%` | `20.0` | `6.06x` |
| `2014-10-10` | `2014-10-13` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.76` | `18.94%` | `12.21%` | `3x` | `2014-03-03` | **`+14.52%`** | `20.0` | `6.93x` |
| `2014-11-10` | `2014-11-11` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.35` | `14.26%` | `12.73%` | `1x` | `2014-10-13` | `+8.16%` | `20.0` | `7.48x` |
| `2015-08-27` | `2015-08-28` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+4.46` | `32.53%` | `13.99%` | `3x` | `2014-11-11` | **`+3.52%`** | `20.0` | `7.73x` |
| `2015-10-06` | `2015-10-07` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.49` | `19.59%` | `16.34%` | `1x` | `2015-08-28` | `+0.80%` | `20.0` | `7.77x` |
| `2017-07-05` | `2017-07-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.56` | `17.30%` | `10.57%` | `3x` | `2015-10-07` | **`+95.67%`** | `20.0` | `15.18x` |
| `2017-07-27` | `2017-07-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.49` | `11.99%` | `10.23%` | `1x` | `2017-07-06` | `+4.89%` | `20.0` | `15.89x` |
| `2018-02-05` | `2018-02-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.90` | `19.35%` | `10.24%` | `3x` | `2017-07-28` | **`+24.64%`** | `20.0` | `19.77x` |
| `2018-05-08` | `2018-05-09` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.48` | `18.44%` | `15.02%` | `1x` | `2018-02-06` | `+6.95%` | `20.0` | `21.10x` |
| `2018-10-25` | `2018-10-26` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.36` | `32.56%` | `16.13%` | `3x` | `2018-05-09` | **`-7.98%`** *(overnight gap)* | `20.0` | `19.38x` |
| `2019-01-25` | `2019-01-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.20` | `23.55%` | `21.65%` | `1x` | `2018-10-26` | `-1.03%` | `20.0` | `19.14x` |
| `2020-02-24` | `2020-02-25` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.71` | `23.23%` | `14.36%` | `3x` | `2019-01-28` | **`+127.86%`** | `20.0` | `43.52x` |
| `2020-05-05` | `2020-05-06` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.37` | `32.21%` | `24.27%` | `1x` | `2020-02-25` | `-1.52%` | `20.0` | `42.77x` |
| `2021-09-30` | `2021-10-01` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-0.53` | `14.58%` | `18.49%` | `3x` | `2020-05-06` | **`+260.22%`** | `20.0` | `153.77x` |
| `2023-03-31` | `2023-04-03` | `0x -> 3x` | `SEP_ON_TO_3X` | `-1.50` | `20.19%` | `30.09%` | `0x` | `2021-10-01` | `+2.73%` | `20.0` | `157.65x` |
| `2023-06-30` | `2023-07-03` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.29` | `16.73%` | `25.31%` | `3x` | `2023-04-03` | **`+49.33%`** | `20.0` | `234.96x` |
| `2023-12-29` | `2024-01-02` | `0x -> 3x` | `SEP_ON_TO_3X` | `-1.73` | `11.55%` | `18.09%` | `0x` | `2023-07-03` | `+2.67%` | `20.0` | `240.75x` |
| `2024-05-03` | `2024-05-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.84` | `20.15%` | `16.10%` | `3x` | `2024-01-02` | **`+16.76%`** | `20.0` | `280.54x` |
| `2024-05-16` | `2024-05-17` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.44` | `17.16%` | `16.17%` | `1x` | `2024-05-06` | `+3.39%` | `20.0` | `289.46x` |
| `2024-06-28` | `2024-07-01` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.44` | `11.88%` | `15.58%` | `3x` | `2024-05-17` | **`+17.99%`** | `20.0` | `340.86x` |
| `2024-09-30` | `2024-10-01` | `0x -> 3x` | `SEP_ON_TO_3X` | `+0.76` | `20.78%` | `17.08%` | `0x` | `2024-07-01` | `+1.35%` | `20.0` | `344.76x` |
| `2024-12-31` | `2025-01-02` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `+0.64` | `20.18%` | `17.18%` | `3x` | `2024-10-01` | **`+11.79%`** | `20.0` | `384.63x` |
| `2025-03-31` | `2025-04-01` | `0x -> 1x` | `SEP_ON_HIGH_VOL_TO_1X` | `+1.64` | `27.00%` | `18.51%` | `0x` | `2025-01-02` | `+1.03%` | `20.0` | `387.83x` |
| `2025-05-09` | `2025-05-12` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.13` | `23.84%` | `22.34%` | `1x` | `2025-04-01` | `+8.49%` | `20.0` | `419.93x` |
| `2026-06-05` | `2026-06-08` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.96` | `23.46%` | `15.56%` | `3x` | `2025-05-12` | **`+135.06%`** | `20.0` | `985.08x` |
| `2026-06-30` | `2026-07-01` | `1x -> 0x` | `SEP_OFF_TO_CASH` | `+3.33` | `33.88%` | `16.48%` | `1x` | `2026-06-08` | `+1.70%` | `20.0` | `999.80x` |
