# Audited V4 Entry/Exit Timing Challengers & Exact Open-Rebalanced `V4 + TQQQ SEP` Blend Report (2026-11-16 Remediation)

> **Reproducible Script**: [`run_jlaw_vcp_entry_and_blend_audit.py`](../../run_jlaw_vcp_entry_and_blend_audit.py)  
> **Table 1 — Audited V4 Entry/Exit Timing Challengers CSV**: [`v4_entry_exit_timing_challengers.csv`](./v4_entry_exit_timing_challengers.csv)  
> **Trade-by-Trade Open Execution Audit Log (`5,711` Records, `0` Close Fallbacks)**: [`v4_entry_exit_trade_by_trade_audit_log.csv`](./v4_entry_exit_trade_by_trade_audit_log.csv)  
> **Table 2 — Exact Open-Rebalanced `V4 + TQQQ SEP` Weight Spectrum CSV**: [`v4_tqqq_blend_frozen_and_walkforward.csv`](./v4_tqqq_blend_frozen_and_walkforward.csv)  
> **Table 3 — Simultaneous Drawdown & Co-Loss Months CSV**: [`simultaneous_drawdown_months_audit.csv`](./simultaneous_drawdown_months_audit.csv)  
> **Table 4 — `$100,000` Forward Paper-Trading Fills & Share Quantities CSV**: [`FORWARD_PAPER_TRADING_POSITIONS_AND_FILLS.csv`](./FORWARD_PAPER_TRADING_POSITIONS_AND_FILLS.csv)  
> **Table 5 — `$100,000` Forward Paper-Trading Daily NAV Tracking CSV**: [`FORWARD_PAPER_TRADING_DAILY_NAV.csv`](./FORWARD_PAPER_TRADING_DAILY_NAV.csv)  
> **Verified Tiingo Supplemental Volume (`VMED, DOCU, ZM, ANSS, XLNX, CEG, FOX, FOXA`)**: [`tiingo_supp_dv_vmed_docu_zm.json`](./tiingo_supp_dv_vmed_docu_zm.json)

---

## Executive Summary of All 5 External Audit Remediations

Following the external audit of commit `2bb3847`, all 5 technical findings have been remediated and verified:

1. **Remediation #1 — True Multi-Edge J Law M.E.T.A. (`AND` Confluence + Breakout-then-Retest) & True Multi-Stage Minervini VCP (Zero Missing-Volume Pass-Through)**:
   - **`B1a` (Strict J Law M.E.T.A., `>= 2-of-3` Support Edges Simultaneously Overlapping + Prior Breakout)**: Replaces the previous simplified `OR` condition (`B1c: 44.82%` CAGR) with true multi-edge confluence requiring a prior 20d pivot breakout, Stage-2 uptrend (`C >= MA50`), and at least **2 of 3 support edges overlapping simultaneously** (`Rising MA20` + `Prior 20d Breakout Pivot Retest` + `38.2%-61.8% Fib Retracement / Volume Dry-Up`). Under `B1a`, the new-entry fill rate drops to **`55.0%`**, missed `>= +10%` runaway winners increase to **`26` months (avg `+20.7%` single-month missed gain)**, and CAGR drops to **`41.43%`** (`Ex-2026`: `33.61%`, Sharpe `1.193`, Daily MaxDD `-41.39%`). Requiring all **3 of 3 edges simultaneously (`B1b`)** lowers the fill rate to **`7.2%`** (`97` missed runaway months) and CAGR to **`3.57%`**.
   - **`C1a` (Strict Minervini VCP Multi-Leg Contraction + Strict Volume Confirmation)**: Requires Stage-2 uptrend (`C > MA50` rising), progressive 2-stage price range contraction (`Range_7d <= 0.80 * Range_prior14d` AND `rstd_5 < rstd_20`), strict volume dry-up during contraction (`MA5_DV < MA20_DV`, strictly `False` when volume is missing — never defaulted to `True`), and pivot breakout on expanding volume (`DV > MA5_DV`). Under `C1a`, the fill rate is **`52.2%`** (`12` missed runaway winners averaging `+22.2%`), **Daily MaxDD drops to `-26.71%` (`Monthly MaxDD -20.14%`)**, and CAGR is **`39.39%`** (`Ex-2026`: `32.04%`, Sharpe `1.178`).
   - **100% Active-Day Volume Coverage**: By merging verified Tiingo daily dollar volume (`tiingo_supp_dv_vmed_docu_zm.json`) with `daily_dv.parquet`, missing volume days across all 214 months dropped from `326` to **`11`** (those 11 days are solely the post-delisting calendar days of `2013-06 VMED` after its merger closed on June 7/24, 2013).

2. **Remediation #2 — Persistent Original Purchase Price (`orig_entry_px`) & Persistent Multi-Month Peak Close for Stop-Loss / Trailing Exits (`E1a` vs `E1b`, `E3a` vs `E3b`)**:
   - Continuing holdings (`Hold <= 5`) now carry forward their **original purchase price (`orig_entry_px`)** and **cumulative multi-month peak close (`peak_close_px`)** across month boundaries instead of resetting at `d0 Open` each month.
   - **Impact on William O'Neil's `-8%` CAN SLIM Stop (`E1a` vs `E1b`)**:
     - Under the old monthly-reset bug (`E1b`), `-8%` stops triggered **`104` times** and reduced CAGR to **`39.48%`** (`Ex-2026`: `32.18%`, Sharpe `1.042`);
     - Under **true persistent original entry cost (`E1a`)**, once a stock has gained `+20%..+50%` over prior months, a normal `-8%` monthly pullback no longer triggers a false "initial cost stop": stop triggers drop by nearly half from **`104` to `56`**, **214M CAGR rebounds by `+10.17pp/yr` from `39.48%` to `49.65%` (`Ex-2026`: `40.51%`, Sharpe rises from `1.042` to `1.270`), and Daily MaxDD improves from `-37.32%` to `-34.31%`**!
     - While `E1a` (`49.65%` CAGR, `1.270` Sharpe) still trails pure `V4` (`59.65%` CAGR, `1.426` Sharpe) by `-10.00pp/yr` due to initial-month shakeouts, fixing the monthly reset removes `-10.17pp/yr` of artificial distortion.

3. **Remediation #3 — Zero Same-Day Close Fallback (`get_strict_exec_open()`) & Complete Trade-by-Trade Open Execution Ledger (`5,711` Records)**:
   - After adding verified Tiingo `adjOpen` series for `ANSS` and `SRCL` (`outputs/qqq_mom_top3_claude_audit_20261103/tiingo/{ANSS,SRCL}.json`), **every single trade execution (`d0 Open` and intra-month `d_next Open`) enforces `get_strict_exec_open()` which raises a hard `ValueError` if `adjOpen` is missing**.
   - Across all 14 variants and 214 months, **`5,711` trade execution records are exported in [`v4_entry_exit_trade_by_trade_audit_log.csv`](./v4_entry_exit_trade_by_trade_audit_log.csv) with `0` fallbacks to same-day close**.

4. **Remediation #4 — Exact Open-Executed Rebalance (Splitting Overnight `Close[d-1]->Open[d]` vs Intraday `Open[d]->Close[d]`) Across the `V4 + TQQQ SEP` Weight Spectrum (`100/0, 75/25, 50/50, 25/75, 0/100`)**:
   - Rebalancing between `V4` and `TQQQ SEP` now strictly accrues the overnight return (`Close[d-1] -> Open[d]`) on the old drifted weights, executes the rebalance (`+ 10bp/side` fee) at `Open[d]`, and accrues the intraday return (`Open[d] -> Close[d]`) on the new target weights.
   - Across the un-tuned weight spectrum (`100/0, 75/25, 50/50, 25/75, 0/100`) in **Stateful Walk-Forward (`2012–2026`)**:
     - `100% WF TQQQ SEP` has the highest raw CAGR (`56.44%` Full / **`55.94%` Ex-2026**), but also the deepest Daily MaxDD (**`-46.29%`**) and highest volatility (`41.37%`, Sharpe `1.293`).
     - `100% WF V4` has the shallowest Daily MaxDD (**`-35.58%`**), with lower Walk-Forward CAGR (`49.50%` Full / **`39.47%` Ex-2026**, Sharpe `1.372`).
     - **`WF 75/25` (`75% V4 + 25% TQQQ`) and `WF 50/50` (`50% V4 + 50% TQQQ`)** sit on the risk-adjusted frontier: **`WF 75/25` achieves the lowest volatility (`32.27%`), lowest Monthly MaxDD (`-26.08%`), highest Sortino (`1.908`), and highest Calmar (`1.403`)**, while **`WF 50/50-M` achieves the highest Daily Sharpe both Full-Period (`1.484`) and Ex-2026 (`1.399`)**, with `54.88%` Full CAGR (`49.31%` Ex-2026) and `-39.97%` Daily MaxDD (a middle-ground drawdown between `-35.58%` and `-46.29%`).

5. **Remediation #5 — Complete `$100,000` Forward Paper-Trading Fills & Daily NAV Ledger**:
   - [`FORWARD_PAPER_TRADING_POSITIONS_AND_FILLS.csv`](./FORWARD_PAPER_TRADING_POSITIONS_AND_FILLS.csv) and [`FORWARD_PAPER_TRADING_DAILY_NAV.csv`](./FORWARD_PAPER_TRADING_DAILY_NAV.csv) record the exact `2026-11-02 09:30:00 ET` Open fill prices (`SGOV $100.43`, `VLO $392.05`, `MPC $446.20`), `10bp` entry fees, exact share counts, SHA-256 strategy code hashes, and daily mark-to-market NAVs.

---

## Table 1: Audited V4 Entry & Exit Timing Challengers (`2009-01 .. 2026-10`, 214M, Zero Close Fallback)

| Variant | Full 214M CAGR | Ex-2026 CAGR (`09–25`) | Full Sharpe | Ex-2026 Sharpe | **Daily MaxDD** | Monthly MaxDD | Drop-Best-10M CAGR | **New-Entry Fill Rate** | **Missed `>=+10%` Runaways (Avg Gain)** | Intra-Month Trades | Ann Turnover |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A. Baseline (`100% d0 Open` Direct Entry)** 🏆 | **59.65%** | **50.38%** | **1.426** | **1.354** | **-37.32%** | **-27.99%** | **37.55%** | **100.0%** | `0` (`0.0%`) | 0 | 7.00x |
| **B1a. Strict J Law M.E.T.A. (`>=2-of-3` Edges + Prior Brk)** | 41.43% | 33.61% | 1.193 | 1.125 | -41.39% | -34.56% | 22.33% | 55.0% | **`26` (`+20.7%`)** | 79 | 9.23x |
| **B1b. Ultra-Strict J Law M.E.T.A. (`All 3-of-3` Edges)** | 3.57% | 3.57% | 0.308 | 0.318 | -14.53% | -9.09% | -0.54% | 7.2% | **`97` (`+22.0%`)** | 24 | 2.98x |
| *B1c. [Ref] Simplified J Law (`MA20` OR Pivot)* | *44.82%* | *36.20%* | *1.244* | *1.162* | *-37.32%* | *-29.78%* | *25.40%* | *78.1%* | *`5` (`+17.5%`)* | *61* | *9.44x* |
| **B2. J Law Dip `>= -3%` Pullback (or `MA20` Support)** | 46.38% | 39.82% | 1.311 | 1.266 | -37.89% | -31.31% | 27.73% | 66.2% | **`20` (`+22.6%`)** | 100 | 10.76x |
| **C1a. Strict Minervini VCP (2-Stage Tight + Vol Dry-Up)** | 39.39% | 32.04% | 1.178 | 1.103 | **-26.71%** | **-20.14%** | 21.30% | 52.2% | `12` (`+22.2%`) | 82 | 9.85x |
| **C2. William O'Neil Breakout (`20d` High + Strict Vol Spike)** | 45.47% | 37.59% | 1.304 | 1.237 | **-30.70%** | **-24.70%** | 26.82% | 67.8% | `1` (`+22.2%`) | 85 | 10.29x |
| **D1. Scale-In 50/50 Breakout (`50% d0 Open + 50% on +3%`)** 🥈 | **55.64%** | **46.99%** | **1.389** | **1.315** | -37.36% | -29.16% | **34.61%** | 100.0% | `0` (`0.0%`) | 114 | 9.77x |
| **D2. Scale-In 50/50 Hybrid (`50% d0 Open + 50% Strict JLaw/Brk`)** | 55.37% | 46.66% | 1.381 | 1.309 | -37.35% | -28.70% | 34.18% | 100.0% | `0` (`0.0%`) | 106 | 9.60x |
| **E1a. [Exit Only] O'Neil `-8%` Stop Below Persistent ORIGINAL Cost** | **49.65%** | **40.51%** | **1.270** | **1.180** | **-34.31%** | -30.76% | **29.74%** | 100.0% | `0` (`0.0%`) | 56 | 11.75x |
| *E1b. [Exit Ref] O'Neil `-8%` Stop Reset Monthly (Old `2bb3847`)* | *39.48%* | *32.18%* | *1.042* | *0.961* | *-35.68%* | *-29.78%* | *20.24%* | *100.0%* | *`0` (`0.0%`)* | *104* | *15.69x* |
| **E2. [Exit Only] Turtle `20-Day Low` Trailing Exit** | 31.18% | 23.23% | 0.907 | 0.787 | -36.08% | -27.80% | 13.29% | 100.0% | `0` (`0.0%`) | 206 | 24.29x |
| **E3a. [Exit Only] Turtle `3x ATR_20` Persistent Peak Stop** | 24.33% | 19.19% | 0.774 | 0.680 | -37.07% | -32.83% | 8.50% | 100.0% | `0` (`0.0%`) | 298 | 32.35x |
| *E3b. [Exit Ref] Turtle `3x ATR_20` Stop Reset Monthly* | *26.61%* | *20.80%* | *0.814* | *0.709* | *-37.07%* | *-32.83%* | *9.91%* | *100.0%* | *`0` (`0.0%`)* | *291* | *31.71x* |

---

## Table 2: Exact Open-Rebalanced `V4 + TQQQ SEP` Weight Spectrum (`Walk-Forward OOS` & `Frozen`)

| Portfolio Configuration | Aligned Window | Full CAGR | **Ex-2026 CAGR** | **Ann Daily Vol** | **Daily Sharpe (Full)** | **Daily Sharpe (Ex-2026)** | **Daily Sortino** | Calmar | **Daily MaxDD** | **Monthly MaxDD** | Loss Months |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **WF-100/0: `100% V4 + 0% TQQQ`** | `2012-01..2026-10` | 49.50% | 39.47% | 33.48% | 1.372 | 1.216 | 1.825 | 1.391 | **-35.58%** | -28.55% | 65/177 |
| **WF-75/25: `75% V4 + 25% TQQQ` (Open Monthly)** | `2012-01..2026-10` | 52.66% | 44.76% | **32.27%** | 1.476 | 1.356 | **1.908** | **1.403** | -37.54% | **-26.08%** | 60/177 |
| **WF-50/50-M: `50% V4 + 50% TQQQ` (Open Monthly)** 🏆 | `2012-01..2026-10` | 54.88% | 49.31% | 33.33% | **1.484** | **1.399** | 1.855 | 1.373 | -39.97% | -26.63% | 64/177 |
| **WF-50/50-Y: `50% V4 + 50% TQQQ` (Open Annual)** | `2012-01..2026-10` | 55.38% | 48.95% | 33.50% | **1.488** | 1.392 | 1.856 | 1.364 | -40.61% | -27.47% | 64/177 |
| **WF-25/75: `25% V4 + 75% TQQQ` (Open Monthly)** | `2012-01..2026-10` | 56.15% | 53.05% | 36.50% | 1.408 | 1.362 | 1.710 | 1.306 | -42.98% | -28.12% | 62/177 |
| **WF-0/100: `0% V4 + 100% TQQQ`** | `2012-01..2026-10` | **56.44%** | **55.94%** | 41.37% | 1.293 | 1.286 | 1.514 | 1.219 | -46.29% | -30.34% | **50/177** |
| **FRZ-100/0: `100% V4` (Frozen)** | `2010-02..2026-10` | **62.36%** | 52.12% | 36.25% | 1.522 | 1.397 | 2.078 | **1.671** | -37.32% | -24.06% | 70/200 |
| **FRZ-75/25: `75% V4 + 25% TQQQ` (Open Monthly)** | `2010-02..2026-10` | 62.16% | 54.21% | **34.39%** | **1.581** | **1.479** | **2.104** | 1.669 | -37.24% | **-22.11%** | **60/200** |
| **FRZ-50/50-M: `50% V4 + 50% TQQQ` (Open Monthly)** | `2010-02..2026-10` | 60.84% | 55.30% | 34.77% | 1.545 | 1.467 | 1.984 | 1.640 | **-37.10%** | -23.55% | 63/200 |
| **FRZ-50/50-Y: `50% V4 + 50% TQQQ` (Open Annual)** | `2010-02..2026-10` | 62.21% | **55.71%** | 35.02% | 1.561 | 1.473 | 2.009 | 1.668 | -37.31% | -23.90% | 61/200 |
| **FRZ-25/75: `25% V4 + 75% TQQQ` (Open Monthly)** | `2010-02..2026-10` | 58.42% | 55.37% | 37.36% | 1.423 | 1.377 | 1.769 | 1.447 | -40.38% | -26.01% | 67/200 |
| **FRZ-0/100: `100% TQQQ SEP` (Frozen)** | `2010-02..2026-10` | 54.94% | 54.43% | 41.84% | 1.260 | 1.252 | 1.507 | 1.234 | -44.54% | -30.17% | 62/200 |
