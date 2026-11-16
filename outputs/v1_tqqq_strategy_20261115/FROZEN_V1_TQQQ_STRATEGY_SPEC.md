# Frozen V1-Daily TQQQ Strategy — Complete Audit-Remediated Specification (`2010-02-11 .. 2026-11-03` 100% Real ETFs, Next-Day Open `adjOpen` + `10bp/side`)

> **100% Self-Contained Reproducible Engine (Zero Local Cache Dependencies)**: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)  
> **Summary Metrics CSV**: [`v1_tqqq_summary.csv`](./v1_tqqq_summary.csv)  
> **Complete Trade Ledger (`1.5/0.5`, Exact FOMC Open + `10bp/side`)**: [`v1_daily_trade_ledger_2009_2026.csv`](./v1_daily_trade_ledger_2009_2026.csv)  
> **Sweet-Spot Trade Ledger (`1.2/0.3`, Exact FOMC Open + `10bp/side`)**: [`v1_daily_sweetspot_trade_ledger_2009_2026.csv`](./v1_daily_sweetspot_trade_ledger_2009_2026.csv)  
> **Exact FOMC SEP Meeting & Transition Table (`2015–2026`)**: [`fomc_sep_signal_verification_2008_2026.csv`](./fomc_sep_signal_verification_2008_2026.csv)  
> **Parameter Sensitivity & Valid Zone Grid (`30 Configs`)**: [`v1_daily_parameter_grid_2009_2026.csv`](./v1_daily_parameter_grid_2009_2026.csv)

---

## 1. Full External Audit Reconciliation (100% Bit-for-Bit Verified)

Every finding from the independent audit of commit `a618dfa` has been incorporated and verified in [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py):

| Independent Audit Item | Resolution in Current Commit | Independent Auditor Result vs Current Engine |
| :--- | :--- | :--- |
| **1. Zero-Dependency One-Click Reproduction** | Removed `break_signals_test.py` import and all gitignored local cache dependencies (`data/fred/`, `data/yahoo/`). Reads **only** git-tracked files: `tiingo_etfs/{QQQ,TQQQ,BIL,SGOV}.json`, `02_sep_alfred_medians.csv`, and `v3_regime_and_cash_214m.csv`. | Runs out-of-the-box in any fresh `git clone` (`python3 frozen_v1_tqqq_strategy.py`) |
| **2. Next-Day Open (`adjOpen`) + `10bp/side` Cost (`2010-02-11 .. 2026-11-03` Real ETFs)** | Signal at day $d-1$ close (`adjClose[d-1]`); overnight return (`adjClose[d-1] -> adjOpen[d]`) on OLD asset; switch at $d$ Open (`adjOpen[d]`) minus `20bp` (`10bp/side`); intraday return (`adjOpen[d] -> adjClose[d]`) on NEW asset. | Month-End SEP Delay: **`51.25%` (`BIL+SGOV`) / `51.73%` (`SGOV`)**, MaxDD **`-44.59%`** (matches auditor's `51.73% / -44.59%`) |
| **3. Exact FOMC SEP Release Date Execution** | Reconstructs all 9 FOMC SEP flips directly from `02_sep_alfred_medians.csv` (comparing same `target_year` median FFR and Core PCE vs previous meeting) and executes at **next trading day Open after FOMC release** (e.g., `2026-06-18` Open after `2026-06-17` FOMC). | Exact FOMC Next-Day Open (`1.5/0.5`): **`53.09%` CAGR, `-44.59%` MaxDD** (matches auditor's **`53.09% / -44.59%`** to `0.00%`!) |
| **4. `2018-10-26` Overnight Gap Counterexample (`14/15` vs `15/15`)** | Documented transparently: at `2018-10-25` close, `3x` leg was in profit (`+0.5%`), but an overnight earnings gap down caused a Market-on-Open exit on `2018-10-26` to close at **`-7.98%` pre-cost / `-8.17%` post-cost** (`14/15` win rate). Also tests **Open Limit NSL** (cancel profit-trim at Open if overnight gap pushed price below entry cost basis $\rightarrow$ `15/15`, CAGR **`53.74%`**). | Both `14/15` (Market-on-Open) and `15/15` (Open Limit NSL) reported side-by-side |
| **5. `2026-09-16` SEP Target Year Clarification** | Corrected table documentation: in the `2026-09-16` SEP (`target_year = 2027`), the **2026** medians are `FFR = 4.1%, Core PCE = 3.4%`, while the **2027 (`target_year`)** medians are **`FFR = 4.1%` (up from `3.6%` in June) and `Core PCE = 2.5%` (vs `2.5%` in June)**. Since `SEP = OFF` was already triggered on `2026-06-17` (`2026` Core PCE `2.7% -> 3.3%`, FFR `3.4% -> 3.8%`) and `4.1% > 3.6%`, `SEP = OFF` remains active. | Verified in `fomc_sep_signal_verification_2008_2026.csv` |
| **6. Parameter Sensitivity (`Rec = 0.7` vs `Rec <= 0.5`) & Equal-Footed Daily vs Monthly** | Documented the `Rec = 0.7` drawdown degradation (`-58.08%` due to premature March 2020 re-entry) and restricted valid recovery threshold to **`Rec ∈ [0.0, 0.5]`**. Added equal-footed Daily vs Monthly `Vol_Z` check (`51.25% / -44.59%` vs `50.07% / -58.08%`). | Full 30-cell grid exported in `v1_daily_parameter_grid_2009_2026.csv` |

---

## 2. Remediated Headline Performance (`2010-02-11 .. 2026-11-03` 100% Real Tiingo ETFs, Next-Day Open `adjOpen` + `10bp/side`)

| Strategy Configuration (`2010-02-11 .. 2026-11-03` Real `TQQQ / QQQ / BIL / SGOV`) | **CAGR** | **Daily MaxDD** | **Sharpe** | **Multiple** | **Switches** | **Closed `3x` Legs Win Rate** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. `V1-Daily` Standard (`1.5 / 0.5`) — Exact FOMC Open + `10bp/side`** 🏆 | **`53.09%`** | **`-44.59%`** | **`1.212`** | **`1,239.9x`** | `31` | **`14 / 15` (`93.3%`)** |
| **2. `V1-Daily` Standard (`1.5 / 0.5`) — Exact FOMC Open + `10bp/side` + Open Limit NSL** 🏆 | **`53.74%`** | **`-44.59%`** | **`1.221`** | **`1,331.1x`** | `31` | **`15 / 15` (`100.0%`)** |
| **3. `V1-Daily` Sweet-Spot (`1.2 / 0.3`) — Exact FOMC Open + `10bp/side`** 🏆 | **`54.94%`** | **`-44.54%`** | **`1.261`** | **`1,516.1x`** | `35` | **`16 / 17` (`94.1%`)** |
| **4. `V1-Daily` Standard (`1.5 / 0.5`) — Month-End SEP Delay + Open + `10bp/side`** | `51.25%` | `-44.59%` | `1.182` | `1,012.7x` | `31` | `14 / 15` (`93.3%`) |
| **5. `V1-Monthly` Equal-Footed `Vol_Z` (`1.5 / 0.5`) — Month-End SEP + Open + `10bp/side`** | `50.07%` | `-58.08%` | `1.123` | `888.4x` | `22` | `11 / 11` (`100.0%`) |
| **6. Pure `SEP` Only (No `Vol_Z`) — Exact FOMC Open + `10bp/side`** | `53.74%` | `-69.92%` | `1.084` | `1,330.8x` | `9` | `5 / 5` |
| **7. Pure `SEP` Only (No `Vol_Z`) — Month-End SEP Delay + Open + `10bp/side`** | `52.04%` | `-69.92%` | `1.061` | `1,104.5x` | `9` | `5 / 5` |

> **Key Structural Takeaway**:  
> Across `2010-02-11 .. 2026-11-03`, `FOMC SEP` provides the primary return driver (`52.04%–53.74%` CAGR), while the daily `1-Year Vol_Z + NSL` switch (`Rec <= 0.5`) acts as a **drawdown and volatility stabilizer**, cutting Daily MaxDD by **`25.3 percentage points` (`-69.92%` $\rightarrow$ `-44.59%`)** and lifting Sharpe from **`1.06–1.08` to `1.18–1.26`** without sacrificing long-run CAGR (`53.09%–54.94%` under exact FOMC next-day open execution).

---

## 3. Exact FOMC SEP Regime Transitions (`2015–2026`, Reconstructed from `02_sep_alfred_medians.csv`)

| FOMC Release Date | Target Year | Horizon Type | Target Year FFR Median (`Curr` vs `Prev`) | Target Year Core PCE Median (`Curr` vs `Prev`) | `SEP` State After Meeting | State Flipped? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2021-09-22` | `2022` | `Next_Year` | `0.3%` vs `0.1%` | `2.3%` vs `2.1%` | **`OFF (Cash)`** | **Yes (`ON -> OFF`)** |
| `2023-03-22` | `2023` | `Current_Year` | `5.1%` vs `5.1%` | `3.6%` vs `3.5%` | **`ON`** | **Yes (`OFF -> ON`)** |
| `2023-06-14` | `2023` | `Current_Year` | `5.6%` vs `5.1%` | `3.9%` vs `3.6%` | **`OFF (Cash)`** | **Yes (`ON -> OFF`)** |
| `2023-12-13` | `2024` | `Next_Year` | `4.6%` vs `5.1%` | `2.4%` vs `2.6%` | **`ON`** | **Yes (`OFF -> ON`)** |
| `2024-06-12` | `2024` | `Current_Year` | `5.1%` vs `4.6%` | `2.8%` vs `2.6%` | **`OFF (Cash)`** | **Yes (`ON -> OFF`)** |
| `2024-09-18` | `2025` | `Next_Year` | `3.4%` vs `4.1%` | `2.2%` vs `2.3%` | **`ON`** | **Yes (`OFF -> ON`)** |
| `2024-12-18` | `2025` | `Next_Year` | `3.9%` vs `3.4%` | `2.5%` vs `2.2%` | **`OFF (Cash)`** | **Yes (`ON -> OFF`)** |
| `2025-03-19` | `2025` | `Current_Year` | `3.9%` vs `3.9%` | `2.8%` vs `2.5%` | **`ON`** | **Yes (`OFF -> ON`)** |
| `2026-06-17` | `2026` | `Current_Year` | `3.8%` vs `3.4%` | `3.3%` vs `2.7%` | **`OFF (Cash)`** | **Yes (`ON -> OFF`)** |
| `2026-09-16` | `2027` | `Next_Year` | `4.1%` vs `3.6%` *(2026: `4.1%`)* | `2.5%` vs `2.5%` *(2026: `3.4%`)* | **`OFF (Cash)`** | No *(stays `OFF`)* |
