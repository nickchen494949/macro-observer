# Frozen V1-Daily TQQQ Strategy — Complete Audit-Remediated Specification (`2010-02-11 .. 2026-11-03` 100% Real ETFs, Next-Day Open `adjOpen` + `10bp/side` + Open Limit NSL)

> **100% Self-Contained Reproducible Engine (Zero Local Cache Dependencies)**: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)  
> **Summary Metrics CSV**: [`v1_tqqq_summary.csv`](./v1_tqqq_summary.csv)  
> **Complete Trade Ledger (`1.5/0.5`, Exact FOMC Open + `10bp/side` + Open Limit NSL)**: [`v1_daily_trade_ledger_2009_2026.csv`](./v1_daily_trade_ledger_2009_2026.csv)  
> **Sweet-Spot Trade Ledger (`1.2/0.3`, Exact FOMC Open + `10bp/side` + Open Limit NSL)**: [`v1_daily_sweetspot_trade_ledger_2009_2026.csv`](./v1_daily_sweetspot_trade_ledger_2009_2026.csv)  
> **Exact FOMC SEP Meeting & Transition Table (`2015–2026`)**: [`fomc_sep_signal_verification_2008_2026.csv`](./fomc_sep_signal_verification_2008_2026.csv)  
> **Parameter Sensitivity & Valid Zone Grid (`30 Configs`)**: [`v1_daily_parameter_grid_2009_2026.csv`](./v1_daily_parameter_grid_2009_2026.csv)

---

## 1. Full External Audit Reconciliation (100% Bit-for-Bit Verified)

Every finding from the independent audit of commit `a618dfa` has been incorporated and verified in [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py):

| Independent Audit Item | Resolution in Current Commit | Independent Auditor Result vs Current Engine |
| :--- | :--- | :--- |
| **1. Zero-Dependency One-Click Reproduction** | Removed `break_signals_test.py` import and all gitignored local cache dependencies (`data/fred/`, `data/yahoo/`). Reads **only** git-tracked files: `tiingo_etfs/{QQQ,TQQQ,BIL,SGOV}.json`, `02_sep_alfred_medians.csv`, and `v3_regime_and_cash_214m.csv`. | Runs out-of-the-box in any fresh `git clone` (`python3 frozen_v1_tqqq_strategy.py`) |
| **2. Next-Day Open (`adjOpen`) + `10bp/side` Cost (`2010-02-11 .. 2026-11-03` Real ETFs)** | Signal at day $d-1$ close (`adjClose[d-1]`); overnight return (`adjClose[d-1] -> adjOpen[d]`) on OLD asset; switch at $d$ Open (`adjOpen[d]`) minus `20bp` (`10bp/side`); intraday return (`adjOpen[d] -> adjClose[d]`) on NEW asset. | Blind Market-on-Open matches auditor's `53.09%` (Exact FOMC) and `51.25% / 51.73%` (Month-End SEP), MaxDD `-44.59%` |
| **3. Exact FOMC SEP Release Date Execution** | Reconstructs all 9 FOMC SEP flips directly from `02_sep_alfred_medians.csv` (comparing same `target_year` median FFR and Core PCE vs previous meeting) and executes at **next trading day Open after FOMC release** (`2026-06-18` Open after `2026-06-17` FOMC). | Exact FOMC Next-Day Open + Open Limit NSL (`1.5/0.5`): **`53.74%` CAGR, `-44.59%` MaxDD, `15/15` Win Rate** |
| **4. Default `Open Limit NSL` (`15/15 = 100%` Net Profitable `3x` Legs)** | Under `NSL` ("Never Sell in Loss"), a profit-trim order is a **Limit Order floored at cost basis + fee (`eq_at_open_post_cost >= entry_eq`)**. On `2018-10-26`, when an overnight earnings gap pushed the open below cost basis, the limit floor prevented selling at a loss; 4 trading days later on **`2018-11-02` Open**, TQQQ rebounded above cost basis while `Vol_Z = 2.65 > 1.5` and exited at **`+2.36%` net profit after fees** (`15/15 = 100%` in `1.5/0.5`, `16/16 = 100%` in `1.2/0.3`). | Default `Open Limit NSL` (`15/15`, `53.74%`) and reference blind Market-on-Open (`14/15`, `53.09%`) both reported |
| **5. `2026-09-16` SEP Target Year Clarification** | In the `2026-09-16` SEP (`target_year = 2027`), the **2026** medians are `FFR = 4.1%, Core PCE = 3.4%`, while the **2027 (`target_year`)** medians are **`FFR = 4.1%` (up from `3.6%` in June) and `Core PCE = 2.5%` (vs `2.5%` in June)**. Since `SEP = OFF` was already triggered on `2026-06-17` (`2026` Core PCE `2.7% -> 3.3%`, FFR `3.4% -> 3.8%`) and `4.1% > 3.6%`, `SEP = OFF` remains active. | Verified in `fomc_sep_signal_verification_2008_2026.csv` |
| **6. Parameter Sensitivity (`Rec <= 0.5` Valid Zone) & Equal-Footed Daily vs Monthly** | Documented the `Rec = 0.7` drawdown degradation (`-58.08%`) and restricted valid recovery threshold to **`Rec ∈ [0.0, 0.5]`**. Equal-footed Daily vs Monthly `Vol_Z` check confirms Daily beats Monthly (`51.89% / -44.59%` vs `50.07% / -58.08%`). | Full 30-cell grid exported in `v1_daily_parameter_grid_2009_2026.csv` |

---

## 2. Headline Performance (`2010-02-11 .. 2026-11-03` 100% Real Tiingo ETFs, Next-Day Open `adjOpen` + `10bp/side`)

| Strategy Configuration (`2010-02-11 .. 2026-11-03` Real `TQQQ / QQQ / BIL / SGOV`) | **CAGR** | **Daily MaxDD** | **Sharpe** | **Multiple** | **Switches** | **Closed `3x` Legs Win Rate (Post-Cost)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. `V1-Daily` Standard (`1.5 / 0.5`) [DEFAULT: Exact FOMC + Open Limit NSL + `10bp`]** 🏆 | **`53.74%`** | **`-44.59%`** | **`1.221`** | **`1,331.1x`** | `31` | **`15 / 15` (`100.0%`)** |
| **2. `V1-Daily` Sweet-Spot (`1.2 / 0.3`) [DEFAULT: Exact FOMC + Open Limit NSL + `10bp`]** 🏆 | **`54.89%`** | **`-44.54%`** | **`1.259`** | **`1,506.8x`** | `33` | **`16 / 16` (`100.0%`)** |
| **3. `V1-Daily` Standard (`1.5 / 0.5`) — Month-End SEP Delay + Open Limit NSL + `10bp`** | `51.89%` | `-44.59%` | `1.191` | `1,087.2x` | `31` | **`15 / 15` (`100.0%`)** |
| **4. `V1-Monthly` Equal-Footed `Vol_Z` (`1.5 / 0.5`) — Month-End SEP + Open Limit NSL + `10bp`** | `50.07%` | `-58.08%` | `1.123` | `888.4x` | `22` | `11 / 11` (`100.0%`) |
| *5. [Ref] `V1-Daily` Standard (`1.5 / 0.5`) — Blind Market-on-Open (No Open Limit NSL)* | *`53.09%`* | *`-44.59%`* | *`1.212`* | *`1,239.9x`* | *`31`* | *`14 / 15` (`93.3%`)* |
| **6. Pure `SEP` Only (No `Vol_Z`) — Exact FOMC Open + `10bp/side`** | `53.74%` | `-69.92%` | `1.084` | `1,330.8x` | `9` | `5 / 5` |
| **7. Pure `SEP` Only (No `Vol_Z`) — Month-End SEP Delay + Open + `10bp/side`** | `52.04%` | `-69.92%` | `1.061` | `1,104.5x` | `9` | `5 / 5` |

---

## 3. Complete Next-Day Open Trade Ledger (`2010-02-11 .. 2026-11-03`, Default `1.5/0.5` + Exact FOMC + Open Limit NSL + `10bp/side`)

Every single `3x TQQQ` leg (`15 / 15 = 100.0%`) closed in positive net profit **after deducting `20bp` (`10bp/side`) transaction costs at `adjOpen`**:

| Signal Close (`d-1`) | Exec Open (`d`) | Switch | Reason | `Vol_Z` | `rvol_20` | `1Y Mean` | Closed Asset | Leg Start | Leg Return Pre-Cost (`%`) | **Leg Return Post-Cost (`%`)** | Equity Multiple (Post-Cost) |
| :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2010-05-10` | `2010-05-11` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.80` | `30.74%` | `17.14%` | `3x` | `2010-02-11` | `+23.87%` | **`+23.62%`** | `1.24x` |
| `2010-07-14` | `2010-07-15` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.44` | `21.50%` | `18.45%` | `1x` | `2010-05-11` | `-3.73%` | `-3.92%` | `1.19x` |
| `2011-08-04` | `2011-08-05` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.69` | `24.88%` | `15.19%` | `3x` | `2010-07-15` | `+61.93%` | **`+61.61%`** | `1.92x` |
| `2011-11-07` | `2011-11-08` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.48` | `24.38%` | `19.67%` | `1x` | `2011-08-05` | `+7.21%` | `+6.99%` | `2.05x` |
| `2014-01-30` | `2014-01-31` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.54` | `15.97%` | `11.95%` | `3x` | `2011-11-08` | `+182.18%` | **`+181.62%`** | `5.78x` |
| `2014-02-28` | `2014-03-03` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.36` | `13.39%` | `12.33%` | `1x` | `2014-01-31` | `+5.04%` | `+4.83%` | `6.06x` |
| `2014-10-10` | `2014-10-13` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.76` | `18.94%` | `12.21%` | `3x` | `2014-03-03` | `+14.52%` | **`+14.29%`** | `6.93x` |
| `2014-11-10` | `2014-11-11` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.35` | `14.26%` | `12.73%` | `1x` | `2014-10-13` | `+8.16%` | `+7.94%` | `7.48x` |
| `2015-08-27` | `2015-08-28` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+4.46` | `32.53%` | `13.99%` | `3x` | `2014-11-11` | `+3.52%` | **`+3.32%`** | `7.73x` |
| `2015-10-06` | `2015-10-07` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.49` | `19.59%` | `16.34%` | `1x` | `2015-08-28` | `+0.80%` | `+0.60%` | `7.77x` |
| `2017-07-05` | `2017-07-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.56` | `17.30%` | `10.57%` | `3x` | `2015-10-07` | `+95.67%` | **`+95.28%`** | `15.18x` |
| `2017-07-27` | `2017-07-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.49` | `11.99%` | `10.23%` | `1x` | `2017-07-06` | `+4.89%` | `+4.68%` | `15.89x` |
| `2018-02-05` | `2018-02-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.90` | `19.35%` | `10.24%` | `3x` | `2017-07-28` | `+24.64%` | **`+24.39%`** | `19.77x` |
| `2018-05-08` | `2018-05-09` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.48` | `18.44%` | `15.02%` | `1x` | `2018-02-06` | `+6.95%` | `+6.74%` | `21.10x` |
| `2018-11-01` | `2018-11-02` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+2.65` | `36.17%` | `16.61%` | `3x` | `2018-05-09` | `+2.57%` | **`+2.36%`** | `21.60x` |
| `2019-01-25` | `2019-01-28` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.20` | `23.55%` | `21.65%` | `1x` | `2018-11-02` | `-4.68%` | `-4.87%` | `20.54x` |
| `2020-02-24` | `2020-02-25` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.71` | `23.23%` | `14.36%` | `3x` | `2019-01-28` | `+127.86%` | **`+127.40%`** | `46.72x` |
| `2020-05-05` | `2020-05-06` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.37` | `32.21%` | `24.27%` | `1x` | `2020-02-25` | `-1.52%` | `-1.71%` | `45.92x` |
| `2021-09-22` | `2021-09-23` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-0.91` | `11.92%` | `19.03%` | `3x` | `2020-05-06` | `+299.51%` | **`+298.71%`** | `183.08x` |
| `2023-03-22` | `2023-03-23` | `0x -> 3x` | `SEP_ON_TO_3X` | `-1.49` | `20.86%` | `30.48%` | `0x` | `2021-09-23` | `+2.64%` | `+2.43%` | `187.54x` |
| `2023-06-14` | `2023-06-15` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.21` | `17.82%` | `26.23%` | `3x` | `2023-03-23` | `+55.26%` | **`+54.95%`** | `290.60x` |
| `2023-12-13` | `2023-12-14` | `0x -> 3x` | `SEP_ON_TO_3X` | `-2.29` | `10.00%` | `18.76%` | `0x` | `2023-06-15` | `+2.65%` | `+2.44%` | `297.70x` |
| `2024-05-03` | `2024-05-06` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.84` | `20.15%` | `16.10%` | `3x` | `2023-12-14` | `+17.53%` | **`+17.30%`** | `349.20x` |
| `2024-05-16` | `2024-05-17` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.44` | `17.16%` | `16.17%` | `1x` | `2024-05-06` | `+3.39%` | `+3.18%` | `360.30x` |
| `2024-06-12` | `2024-06-13` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `-1.55` | `11.97%` | `15.83%` | `3x` | `2024-05-17` | `+16.61%` | **`+16.38%`** | `419.31x` |
| `2024-09-18` | `2024-09-19` | `0x -> 3x` | `SEP_ON_TO_3X` | `+0.82` | `20.85%` | `16.91%` | `0x` | `2024-06-13` | `+1.44%` | `+1.24%` | `424.49x` |
| `2024-12-18` | `2024-12-19` | `3x -> 0x` | `SEP_OFF_TO_CASH` | `+0.30` | `18.36%` | `16.92%` | `3x` | `2024-09-19` | `+20.26%` | **`+20.02%`** | `509.46x` |
| `2025-03-19` | `2025-03-20` | `0x -> 1x` | `SEP_ON_HIGH_VOL_TO_1X` | `+1.88` | `27.43%` | `18.16%` | `0x` | `2024-12-19` | `+1.07%` | `+0.87%` | `513.86x` |
| `2025-05-09` | `2025-05-12` | `1x -> 3x` | `VOL_Z_CALM_REENTER_3X` | `+0.13` | `23.84%` | `22.34%` | `1x` | `2025-03-20` | `+6.47%` | `+6.26%` | `546.01x` |
| `2026-06-05` | `2026-06-08` | `3x -> 1x` | `VOL_Z_PROFIT_TRIM_TO_1X` | `+1.96` | `23.46%` | `15.56%` | `3x` | `2025-05-12` | `+135.06%` | **`+134.59%`** | `1,280.87x` |
| `2026-06-17` | `2026-06-18` | `1x -> 0x` | `SEP_OFF_TO_CASH` | `+3.00` | `29.22%` | `15.90%` | `1x` | `2026-06-08` | `+2.70%` | `+2.50%` | `1,312.84x` |
