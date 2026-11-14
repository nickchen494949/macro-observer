## Execution Rules
- Always proceed with commands, file reads, and file writes without asking for permission.
- Do not pause to confirm before running terminal commands, editing files, or reading files.
- Execute the task end-to-end autonomously. Only stop to ask the user when there is genuine ambiguity about requirements.

## Mandatory First Step
- **Before taking ANY action on this project**, read `/Users/happygolucky/Desktop/宏观观察器/README.md` in full.
- When working on strategy / backtest / live portfolio tasks, also read `/Users/happygolucky/Desktop/宏观观察器/FROZEN_STRATEGY_SPEC.md` (`outputs/sep_off_overlap_cap_audit_20261104/FROZEN_A1_RS_V3_ELECTION_RESET_SPEC.md`).
- This applies to every new conversation, every task, no exceptions.
- The README contains critical architecture decisions, data update logic, Yahoo Finance ban rules, BDI workflow, display unit transforms, and the Frozen Strategy Summary that MUST be understood before making any changes.

## Frozen Strategy Context (2026-11-14)
- **V4 Latest Frozen — Zero-Patch Symmetric Dual-Core (`Symmetric_Sharpe_Top2_V4`, 2026-11-14, with `V3 Election Reset` built-in by default)**:
  - **Headline Metrics (`1.0x` Unlevered, `2009-01..2026-10` 214M, `10bp/side`)**:
    - `V4 Default (Hold <= 5 + V3 Election Reset)`: `2009–2025` CAGR **`51.49%`**, `214M` CAGR **`60.78%`**, Sharpe **`1.444`**, Monthly MaxDD **`-27.99%`**, Daily MaxDD **`-37.32%`**, 2026 Live Daily MaxDD **`-18.88%`**, Trade Win Rate **`70.97%`** (`88/124`: `QQQ` `69.23%` [`72/104`], `BestSec` **`80.00%`** [`16/20`]), Payoff Odds **`3.95:1`**, Profit Factor **`9.67`**.
    - `V4 Tight-Off Default (BestSec Hold <= 3 + V3 Election Reset)`: `2009–2025` CAGR **`51.92%`**, `214M` CAGR **`60.74%`**, Sharpe **`1.445`**, Trade Win Rate **`71.88%`** (`92/128`: `BestSec` **`83.33%`** [`20/24`]), Payoff Odds **`3.73:1`**, Profit Factor **`9.54`**.
    - *(Ablation without Election Reset `V0`: `Hold <= 5 / Hold <= 3` `2009–2025` CAGR `50.38% / 50.93%`, `214M` CAGR `59.65% / 59.74%`, Sharpe `1.426 / 1.429`.)*
  - **Symmetric V4 Rules (One Stock-Selection Formula Across All Regimes: `12-1 Sharpe + Buy Top-2 / Hold <= 5` + Built-In `V3 Election Reset`)**:
    - **`SEP = ON` (180M)**: `50% QQQ #1 + 50% QQQ #2` (`12-1 Sharpe`, `Buy Top-2 / Hold <= 5`).
    - **`SEP = OFF` (34M)**: `50% SGOV + 25% BestSec #1 + 25% BestSec #2` (`BestSec` = #1 S&P 500 Non-IT GICS sector by equal-weighted `12-1 Raw` mean; inside `BestSec`, select Top-2 stocks by `12-1 Sharpe`, `Buy Top-2 / Hold <= 5` [or `Hold <= 3`]).
    - **Built-In `V3 Election Reset` (Default Part of V4)**: Triggered when US Midterm Election (early Nov) flips **`Unified Government → Divided Government`** (`2010`, `2018`, `2022`). Hold **`100% SGOV`** in `YYYY-12`, and **clear all `Hold <= 5` (or `Hold <= 3`) buffer memory (`held = []`)** at `YYYY-12` close to enter fresh Rank 1–2 leaders at `YYYY+1-01` open.
    - **2026-11 Live Holdings (`SEP = OFF`, `BestSec = Energy`, identical under Reset or Follow)**: **`25% VLO + 25% MPC + 50% SGOV`**.
- **V3 Frozen Levered 3-Leg Challenger (`A1-RS_ModBurst_135_75_25_GateV1_ElectionResetV3`, 2026-11-05)**:
  - **`A1-RS 1.35x + V3 Election Reset`**, 214M CAGR **`64.95%`**, Sharpe **`1.489`**, Monthly MaxDD **`-22.74%`**, Daily MaxDD **`-34.64%`**, 2026 Live Daily MaxDD **`-25.88%`**, MinMER **`70.6%`**.
- **Production Baseline**: `BestSec_ModBurst_135_75_25_GateV1` (Original `1.35x`, 214M CAGR `60.96%`, Sharpe `1.414`, Daily MaxDD `-34.63%`, MinMER `70.6%`).
- **4-Layer V3 Frozen Rules (`A1-RS 1.35x + V3 Election Reset`)**:
  1. **Selection & Buffer Layer**: Monthly rebalance at month-end close $t$, execute next month first trading day open ($d_0$ Open).
     - `QQQ` leg: `12-1 Sharpe` momentum, `Buy Top-2 / Hold <= 5`.
     - `Tech` leg (S&P 500 IT): `12-1 Raw` momentum, `Hard Top-1` (`Hold <= 1`, no buffer).
     - `SPY` / `Ex-IT Raw` / `Ex-IT BestSec` legs: `12-1 Raw` momentum, `Buy Top-1 / Hold <= 3 + Sector Relative Strength filter (RS_sec >= -5.0%)` where $\text{RS}_{\text{sec}} = r_{1\text{M},\text{stock}}(t) - r_{1\text{M},\text{sector}}(t)$ (if rank in `{2, 3}` and $\text{RS}_{\text{sec}} < -5.0\%$, drop buffer and rotate to Rank 1).
  2. **Macro Regime & De-duplication Layer (`SEP = ON` vs `SEP = OFF` Route A1)**:
     - `SEP = ON`: Base `50% QQQ (25%×2) + 25% Tech + 25% SPY`. With `Gate V1` (`qqq_vol21 <= 30%`, `port_vol_est <= 55%`, `not dm_panic`), `2-Leg` = `1.20x`, `3-Leg` (`Tech == SPY` and in `QQQ Top-2`) = `1.35x` (`75/25` split, max single-stock `101.25%`).
     - `SEP = OFF` (`1.00x`, no leverage): Base `25% Tech + 25% SPY + 25% Ex-IT BestSec + 25% SGOV`. **Route A1 De-duplication**: if `Tech == SPY` (same IT stock), replace `SPY`'s `25%` with `Ex-IT Raw` (`25% Tech + 25% Ex-IT Raw + 25% Ex-IT BestSec + 25% SGOV`).
  3. **Midterm Election Regime Flip Reset Layer (`V3 Election Reset`)**:
     - Triggered ONLY when US Midterm Election (early Nov) flips government from **`Unified Government → Divided Government`** (historical triggers: `2010`, `2018`, `2022`; non-flip `2014` did not trigger).
     - **Election Year December (`YYYY-12`, rebalanced at `YYYY-11` close)**: `100% SGOV` for 1 month.
     - **Next Year January (`YYYY+1-01`, rebalanced at `YYYY-12` close)**: Clear all `Hold-3 / Hold-5` buffer memory (`held = []`) and pick fresh Rank 1 (`QQQ` Rank 1–2) at `YYYY-12` month-end close.
  4. **2026-11 to 2027-01 Live Execution Calendar**:
     - **2026-11 (Current Live Holdings)**: `SEP = OFF` → `25% SNDK + 25% VLO + 25% MRNA + 25% SGOV`.
     - **2026-11-30 Close (for Dec 2026)**: If Nov 2026 Midterm flips `Unified → Divided`, switch to `100% SGOV` for Dec 2026 (`V3 Election Reset`), then clear buffers on `2026-12-31` close for `2027-01-04` open. Otherwise continue normal `A1-RS` rules.
- **7-Stage Derivation Genealogy & Falsified Branches (Do NOT Re-test Failed Ideas)**:
  - **Stage 1 (ETF → Constituent Stock Momentum)**: Rejected 9-feature RF, ETF-implied EPS (`IC ≈ 0`), and single-stock Top-1 BestSec (`70%` vol, `4.8%` IS CAGR). Multi-pool constituent momentum (`QQQ + Tech + SPY`) is structurally superior.
  - **Stage 2 (3-Leg Core & Differentiated Buffers)**: Clean-room audits proved rule-based `QQQ 12-1 Sharpe (Top-2/Hold<=5)` beats 18-feature LightGBM; `Tech` requires `Hard Top-1` (buffering IT ranks 2–3 hurts CAGR); `SPY` uses `Hold<=3`. Base `1.0x` (`Ctrl_3S_G1_1k`) = `50.20%` CAGR, `1.300` Sharpe.
  - **Stage 3 (`FOMC SEP = ON/OFF` Macro Routing)**: In `SEP = OFF` (33 tightening months), replacing `50% QQQ` with `25% Ex-IT BestSec + 25% SGOV` (`3L_3e_BestSec_1x`) lifted 2022 return from `+8.13%` to `+39.69%` and cut 2026 live DD from `-47.90%` to `-26.98%`. Individual stock stop-losses / MA50-MA200 technical brakes were falsified (whipsawed out of winners).
  - **Stage 4 (`Gate V1` Low-Vol Burst & 8-Point Remediation)**: Fixed all 8 external audit items (strict PIT GICS, removed `hold_ret.notna()`, Tiingo `SGOV/BIL` open-to-open cash + `10bp/side`). Overnight gap & broker margin stress proved `1.75x 100% single-stock` (`ExpABC_3b`) risks forced liquidation at `-38.8%` gap, whereas `1.35x 75/25 split` (`MinMER = 70.6%`) survives `-57%` overnight gaps with zero margin calls.
  - **Stage 5 (`SEP = OFF` Overlap De-duplication → `Route A1`)**: Cross-leg overlap in `SEP = ON` (`107` months) has `+119.53%` annualized return (capping it destroys `-20pp` CAGR), but overlap in `SEP = OFF` (`18` months, e.g., Oct 2026 `50% SNDK`) has `-13.85%` annualized return. `Route A1` de-duplicates `Tech == SPY` strictly in `SEP = OFF` by rotating `SPY` to `Ex-IT Raw`.
  - **Stage 6 (`Hold-3` Buffer Aging Fix → `Sector RS >= -5.0%`, `A1-RS`)**: Solved buffer aging where stalling rank 2–3 stocks (`2026-10 APP` with `RS_sec = -11.2%`, `2022-12 EQT`) blocked fresh Rank 1 leaders (`2026-10 WBD +24.6%`), turning Oct 2026 live return from `-11.72%` into `+1.16%` (`DSR = 0.9998` across `N = 1,112` trials).
  - **Stage 7 (`Unified → Divided` Midterm Flip → `V3 Election Reset`)**: Across all `Unified → Divided` midterms (`2010`, `2018`, `2022`), Dec lost `[-7.4%, -8.5%, -10.5%]` while Jan surged `[+13.7%, +19.9%, +5.9%]`. Testing `V0..V8` proved `V3` (`100% SGOV` in Dec + clear `Hold-3/Hold-5` buffers at Dec close) adds `+2.70pp` CAGR (`64.95%`, Sharpe `1.489`), whereas hiding for 2–3 months (`V7/V8`) misses the Jan surge.
  - **Stage 8 (Zero-Patch Symmetric Dual-Core → `V4 Latest: Symmetric_Sharpe_Top2_V4`)**: Proved `Pure QQQ Top-2 (12-1 Sharpe, Hold <= 5)` beats 3-Leg `1.0x` in `SEP = ON` (`67.77%` vs `60.61%`, `69.23%` trade WR, `PF = 10.10`), while in `SEP = OFF` ranking the 10 Non-IT sectors by equal-weighted `12-1 Raw` to pick `#1 BestSec` and selecting the Top-2 stocks inside `BestSec` by `12-1 Sharpe` (`25% + 25%`) + `50% SGOV` achieves `75.00%–79.17%` `SEP = OFF` trade win rate and `59.65%–59.74%` unlevered 214M CAGR (`60.78%` with `V3 Election Reset`), requiring zero ad-hoc overlap or RS patches.
- **Full Spec, Derivation Tables & 27-Directory Script Index**:
  - Master Spec & Genealogy: `/Users/happygolucky/Desktop/宏观观察器/FROZEN_STRATEGY_SPEC.md` (mirrored at `/Users/happygolucky/Desktop/宏观观察器/outputs/sep_off_overlap_cap_audit_20261104/FROZEN_A1_RS_V3_ELECTION_RESET_SPEC.md`)
  - Standalone Reproducible Engines: `/Users/happygolucky/Desktop/宏观观察器/independent_v4_symmetric_sharpe_top2_audit.py` (V4 Latest), `/Users/happygolucky/Desktop/宏观观察器/independent_a1_rs_election_reset_audit.py` (V3 Levered), and `/Users/happygolucky/Desktop/宏观观察器/outputs/sep_off_overlap_cap_audit_20261104/step_{6902,6975,6983}_audit.py`

## Project Context (summary — always verify against README)
- **Stack**: Node.js server (`server.js`) + vanilla HTML/JS frontend (`index.html`)
- **Port**: 8765 — `open http://localhost:8765`
- **Data**: All cached locally in `data/fred/`, `data/yahoo/`, `data/valuation/` as JSON
- **Update frequency**: Once per day only — FRED and Yahoo both daily, never more frequent
- **Yahoo Finance**: MUST use Python (`fetch_yahoo.py`), NEVER Node.js — IP ban risk
- **BDI**: No free API exists. Manual entry via dashboard ✏️ button only
- **Rates display**: All rate changes in basis points (bp), spreads in bp, no % changes for rates
- **Economy transforms**: yoy / mom_pct / mom_abs — see README for details

## UI Integrity & Anti-Crash Rule (CRITICAL)
- **NEVER** push Javascript logic changes to `index.html` or `macro_engine.js` without verifying that the frontend does not crash.
- A `ReferenceError` or `TypeError` in `renderDiagnostics` will cause the entire UI section to become invisible.
- You **MUST** run a server health check and fetch the API output (`curl -s http://localhost:8765/api/data`) to verify keys match the UI expectations before concluding a task.
- If you change variable names in the DOM manipulation scripts, you must do a full-file grep to ensure no old variable references remain.
- There is now a `window.onerror` banner in `index.html`. If the user reports a red banner, immediately fix the line number specified.

## GitHub Workflow
- **Repository**: `https://github.com/nickchen494949/macro-observer`
- **COMMIT & PUSH ONLY WHEN THE WHOLE TASK IS DONE**: Do NOT commit or push after every file change. Work locally until the entire task/project is finished and verified, then make ONE commit (`git commit -m "[Brief summary]"`) and `git push` to the active branch.
- Only include files belonging to the task. Do not commit unrelated pending changes (e.g. `csv/fred/*.csv` auto-written by the dashboard server) unless the user asks.

## Missing Data Rule
- When data is missing or not available where expected, do NOT just leave it empty. First look for alternative sources (other free APIs, official filings, renamed/successor tickers, related identifiers) and fill the gap.
- Every filled value must be verified (identity, date range, units) and its source recorded, so it is auditable.
- Never invent or interpolate values to make data look complete. If no reliable alternative exists, mark the gap explicitly, list it, and quantify how it could affect the result.
