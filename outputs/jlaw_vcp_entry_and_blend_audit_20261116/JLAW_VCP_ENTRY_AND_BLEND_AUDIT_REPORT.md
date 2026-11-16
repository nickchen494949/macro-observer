# V4 Entry/Exit Timing Challengers (J Law M.E.T.A., Minervini VCP, O'Neil, Scale-In, Turtle) & Walk-Forward 50/50 Blend Audit Report (2026-11-16)

> **Reproducible Script**: [`run_jlaw_vcp_entry_and_blend_audit.py`](../../run_jlaw_vcp_entry_and_blend_audit.py)  
> **V4 Entry/Exit Timing Summary CSV**: [`v4_entry_exit_timing_challengers.csv`](./v4_entry_exit_timing_challengers.csv)  
> **V4 + TQQQ SEP 50/50 Blend (Frozen & Walk-Forward) CSV**: [`v4_tqqq_blend_frozen_and_walkforward.csv`](./v4_tqqq_blend_frozen_and_walkforward.csv)  
> **Simultaneous Drawdown & Co-Loss Months CSV**: [`simultaneous_drawdown_months_audit.csv`](./simultaneous_drawdown_months_audit.csv)  
> **Immutable Forward Paper-Trading Ledger**: [`FORWARD_PAPER_TRADING_LEDGER.csv`](./FORWARD_PAPER_TRADING_LEDGER.csv)

---

## Executive Summary

1. **V4 Entry & Exit Timing Challengers (`Modes A / B / C / D / E`, Keeping Stock Selection & `SEP` Routing 100% Frozen)**:
   - **Month-Start Direct Open Entry (`Mode A`, `59.65%` CAGR / `1.426` Sharpe / `-37.32%` Daily MaxDD) beats all Pullback (`Mode B`), Breakout (`Mode C`), Scale-In (`Mode D`), and Mechanical Stop-Exit (`Mode E`) variants on CAGR, Sharpe, and Drop-Best-10M**.
   - **Why J Law M.E.T.A. Pullback (`B1: 50.40%`, `B2: 47.20%`) Underperforms by `-9.3pp` to `-12.5pp/yr`**:
     - Adverse Selection (逆向选择): Because `V4` already skips the most recent month (`12-1` momentum), newly selected `Top-2` mega-cap leaders that are genuinely starting a major wave take off immediately from Day 1 Open (`15.3%` to `26.4%` of new entries *never* pull back to `MA20` or dip `-3%` during the entire month, including `18` runaway months in `B2` with an average single-month missed gain of **`+22.5%`**!). Conversely, stocks that quickly drop `-3%` or fall back to `MA20` right after month-start are disproportionately false breakouts that keep falling, so waiting for a pullback buys 100% of the losers while missing the biggest winners.
   - **What William O'Neil Breakout (`C2: 45.93%` CAGR, `-30.70%` Daily MaxDD) & 50/50 Scale-In (`D1: 55.64%` CAGR, `1.389` Sharpe) Show**:
     - `C2` (`20-Day High + Volume Breakout`) reduces Daily MaxDD from `-37.32%` to **`-30.70%`** (`-6.62pp` improvement) because it stays in `SGOV` (`39.2%` of new entries) when stocks open weak, but sacrifices `-13.72pp/yr` in CAGR due to delayed entry prices.
     - `D1` (`50% at d0 Open + 50% Add on +3% Confirmation`) is the **best execution challenger** (`55.64%` CAGR, `1.389` Sharpe, `0` missed runaway stocks), proving that if an investor psychologically prefers scaling in, putting `50%` in at `d0 Open` on new entries only is far superior to waiting `0%` in cash for a pullback (`B1/B2`) or scaling in on already-held winners (`D3: 42.86%`).
   - **Why Mechanical Intra-Month Stops (`E1: -8% O'Neil Stop`, `E2: Turtle 20d Low`, `E3: 3x ATR`) Destroy `-20pp` to `-33pp` CAGR**:
     - Consistent with Kaminski & Lo (2014), high-beta momentum leaders (`NVDA`, `TSLA`, `AMD`, `AVGO`) routinely experience `-8%` to `-12%` intra-month shakeouts inside multi-month uptrends; selling to `SGOV` mid-month locks in the dip and misses the subsequent rebound (`E1: 39.48%`, `E2: 31.18%`, `E3: 26.57%`), without materially improving Daily MaxDD (`-35.68%` to `-37.07%` vs `-37.32%`).

2. **Portfolio Combination: `50% V4 + 50% TQQQ SEP` (Both Frozen & Stateful Walk-Forward OOS)**:
   - **Stateful Walk-Forward Out-of-Sample (`2012-01-03 .. 2026-10-29`, Cold-Cash Start, Zero Hindsight)**:
     - `100% WF V4`: CAGR **`49.50%`** (`Ex-2026`: `39.47%`), Daily Vol `33.48%`, Daily Sharpe **`1.372`**, Daily MaxDD **`-35.58%`**, Monthly MaxDD **`-28.55%`**.
     - `100% WF TQQQ SEP`: CAGR **`56.44%`** (`Ex-2026`: `55.94%`), Daily Vol `41.37%`, Daily Sharpe **`1.293`**, Daily MaxDD **`-46.29%`**, Monthly MaxDD **`-30.34%`**.
     - 🏆 **`50/50 WF Blend (Monthly / Annual Rebal)`**: CAGR **`54.84% / 55.47%`** (`+2.50pp/yr` rebalancing bonus over the average of the two individual CAGRs!), **Daily Vol drops to `33.33%` (lower than EITHER strategy alone!)**, **Daily Sharpe rises to `1.483 / 1.490` (beating BOTH individual strategies!)**, and **Monthly MaxDD drops to `-26.58%` (lower than BOTH `-28.55%` and `-30.34%`!)**.
   - **Frozen Full Window (`2010-02-11 .. 2026-10-29`)**:
     - `50/50 Blend (Annual Rebal)` achieves **`62.40%` CAGR** (`Ex-2026`: **`55.89%`**, higher than either `V4` [`52.12%`] or `TQQQ SEP` [`54.43%`] alone in `2010–2025`!), Daily Sharpe **`1.563`**, and Daily MaxDD **`-37.26%`**.

3. **Simultaneous Drawdown & Crash Co-Movement Anatomy (`V4` vs `TQQQ SEP`)**:
   - **In `SEP = OFF` (Tightening / Inflation Bear Markets)**: Daily return correlation is **`0.042` (near zero)** because `TQQQ SEP` is `100% SGOV Cash` while `V4` is `50% SGOV + 50% Non-IT BestSec` (combined 50/50 portfolio = `75% SGOV Cash + 25% Non-IT BestSec`).
   - **In `SEP = ON` (Easing / Normal Regimes)**: Daily return correlation is **`0.611`** because both hold Nasdaq-100 risk (`V4` holds `QQQ Top-2`, `TQQQ SEP` holds `3x TQQQ` or `1x QQQ`).
   - **All 15 worst simultaneous drawdown months (`Blend <= -8.9%`) occurred in `SEP = ON`** during sudden mid-cycle tech/macro shocks (`2018-10 -18.75%`, `2019-05 -15.86%`, `2020-09 -15.64%`, `2010-08 -14.53%`, `2016-01 -13.56%`, `2024-04 -11.12%`, `2020-03 -10.12%`) before `Vol_Z > 1.2 + NSL` or `SEP = OFF` triggered.

---

## Table 1: V4 Entry & Exit Timing Challengers (`2009-01 .. 2026-10`, 214M, `10bp/side`)

| Variant | Full 214M CAGR | Ex-2026 CAGR (`09–25`) | Full Sharpe | Ex-2026 Sharpe | **Daily MaxDD** | Monthly MaxDD | Drop-Best-10M CAGR | **New-Entry Fill Rate** | **Missed `>=+10%` Runaways (Avg Gain)** | Intra-Month Trades | Ann Turnover |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A. Baseline (`100% d0 Open` Direct Entry)** 🏆 | **59.65%** | **50.38%** | **1.426** | **1.354** | **-37.32%** | **-27.99%** | **37.55%** | **100.0%** | `0` (`0.0%`) | 0 | 7.00x |
| **B1. J Law M.E.T.A. Pullback (`MA20` / 20d Pivot, `>= MA50`)** | 50.40% | 41.51% | 1.333 | 1.263 | -37.32% | -27.99% | 30.34% | 84.7% | `1` (`+14.1%`) | 47 | 9.01x |
| **B2. J Law Dip `>= -3%` Pullback (or `MA20` Touch)** | 47.20% | 40.71% | 1.313 | 1.269 | -37.68% | -31.08% | 28.48% | 73.6% | **`18` (`+22.5%`)** | 109 | 11.71x |
| **B3. J Law M.E.T.A. Pullback + 10-Day Max Wait Cap** | 49.68% | 40.66% | 1.313 | 1.237 | -37.32% | -27.99% | 29.68% | 89.9% | `0` (`0.0%`) | 52 | 9.42x |
| **C1. Minervini VCP Breakout (`5d/20d` Contraction + `10d` High)** | 49.55% | 41.49% | 1.347 | 1.275 | -37.41% | -30.47% | 30.29% | 85.4% | `0` (`0.0%`) | 95 | 11.57x |
| **C2. William O'Neil Breakout (`20d` High + Volume Spike)** | 45.93% | 38.04% | 1.322 | 1.259 | **-30.70%** | **-24.70%** | 27.31% | 60.8% | `3` (`+18.7%`) | 81 | 9.68x |
| **D1. Scale-In 50/50 Breakout (`50% d0 Open + 50% on +3%`)** 🥈 | **55.64%** | **46.98%** | **1.389** | **1.315** | -37.36% | -29.16% | **34.60%** | 100.0% | `0` (`0.0%`) | 114 | 9.77x |
| **D2. Scale-In 50/50 Hybrid (`50% d0 Open + 50% JLaw/Brk`)** | 55.25% | 46.54% | 1.367 | 1.292 | -37.35% | -28.70% | 34.07% | 100.0% | `0` (`0.0%`) | 116 | 9.72x |
| **D3. Scale-In 50/50 All Slots Every Month (Stress Test)** | 42.86% | 35.73% | 1.196 | 1.126 | -38.92% | -31.27% | 24.72% | 100.0% | `0` (`0.0%`) | 405 | 24.11x |
| **E1. [Exit Only] O'Neil `-8%` Hard Stop from Entry Open** | 39.48% | 32.18% | 1.042 | 0.961 | -35.68% | -29.78% | 20.24% | 100.0% | `0` (`0.0%`) | 104 | 15.69x |
| **E2. [Exit Only] Turtle `20-Day Low` Trailing Exit** | 31.18% | 23.23% | 0.907 | 0.787 | -36.08% | -27.80% | 13.29% | 100.0% | `0` (`0.0%`) | 206 | 24.29x |
| **E3. [Exit Only] Chandelier / Turtle `3x ATR_20` Stop** | 26.57% | 20.76% | 0.814 | 0.708 | -37.07% | -32.83% | 9.87% | 100.0% | `0` (`0.0%`) | 292 | 31.77x |

---

## Table 2: `V4 + TQQQ SEP` 50/50 Blend — Frozen (`2010–2026`) & Stateful Walk-Forward (`2012–2026`)

| Portfolio Configuration | Aligned Window | Full CAGR | **Ex-2026 CAGR** | **Ann Daily Vol** | **Daily Sharpe** | **Daily Sortino** | Calmar | **Daily MaxDD** | **Monthly MaxDD** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1a. `100% V4` (Frozen Baseline)** | `2010-02..2026-10` | 62.36% | 52.12% | 36.25% | 1.522 | 2.078 | 1.671 | -37.32% | -23.69% |
| **1b. `100% TQQQ SEP` (Frozen Baseline)** | `2010-02..2026-10` | 54.94% | 54.43% | 41.84% | 1.260 | 1.507 | 1.234 | -44.54% | -30.17% |
| **1c. `50/50 Blend` (Frozen, Monthly Rebal)** 🏆 | `2010-02..2026-10` | **60.87%** | **55.29%** | **34.77%** | **1.545** | 1.984 | 1.641 | **-37.10%** | **-23.56%** |
| **1d. `50/50 Blend` (Frozen, Annual Rebal)** 🏆 | `2010-02..2026-10` | **62.40%** | **55.89%** | **35.04%** | **1.563** | **2.013** | **1.675** | **-37.26%** | -23.90% |
| **2a. `100% V4` (Stateful Walk-Forward OOS)** | `2012-01..2026-10` | 49.50% | 39.47% | 33.48% | 1.372 | 1.825 | 1.391 | -35.58% | -28.55% |
| **2b. `100% TQQQ SEP` (Stateful Walk-Forward OOS)** | `2012-01..2026-10` | 56.44% | 55.94% | 41.37% | 1.293 | 1.514 | 1.219 | -46.29% | -30.34% |
| **2c. `50/50 Blend: WF V4 + WF TQQQ SEP` (Monthly Rebal)** 🏆 | `2012-01..2026-10` | **54.84%** | **49.24%** | **33.33%** | **1.483** | **1.854** | 1.368 | -40.10% | **-26.58%** |
| **2d. `50/50 Blend: WF V4 + WF TQQQ SEP` (Annual Rebal)** 🏆 | `2012-01..2026-10` | **55.47%** | **49.04%** | **33.48%** | **1.490** | **1.859** | 1.364 | -40.66% | -27.59% |
| *2e. [Ref] `50/50 Blend: Frozen V4 + Frozen TQQQ` (`2012–26`)* | `2012-01..2026-10` | *62.94%* | *56.67%* | *34.57%* | *1.590* | *2.025* | *1.697* | *-37.10%* | *-23.26%* |

---

## Table 3: Worst Simultaneous Drawdown Months (`V4` vs `TQQQ SEP`, `2010–2026`)

- **Daily Return Correlation**: Full Period = **`0.584`** | When **`SEP = ON`** = **`0.611`** | When **`SEP = OFF`** = **`0.042`**
- **Monthly Loss Co-occurrence**: Out of `200` common months, `V4` lost in `70` months, `TQQQ SEP` lost in `62` months, and **both lost simultaneously in `35` months (`17.5%` of all months)**.

| Year-Month | Macro Regime | `V4` Monthly Return | `TQQQ SEP` Monthly Return | `50/50 Blend` Monthly Return | Root Cause of Simultaneous Loss |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **`2018-10`** | `SEP = ON` | -20.02% | -17.48% | **-18.75%** | Q4 2018 tech/rate selloff; `Vol_Z > 1.2` trimmed `TQQQ` to `1x` mid-month on Oct 17 |
| **`2019-05`** | `SEP = ON` | -7.68% | -24.01% | **-15.86%** | Sudden US-China tariff shock while `Vol_Z` stayed `< 1.2` |
| **`2020-09`** | `SEP = ON` | -12.40% | -18.88% | **-15.64%** | Post-summer mega-cap tech valuation pullback (`ZM/TSLA/NVDA`) |
| **`2010-08`** | `SEP = ON` | -13.93% | -15.12% | **-14.53%** | Summer 2010 double-dip recession scare right after `1x -> 3x` re-entry on Jul 30 |
| **`2016-01`** | `SEP = ON` | -5.99% | -21.13% | **-13.56%** | Early-2016 China/oil shock; `3x TQQQ` was underwater so `NSL` held `3x` |
| **`2010-05`** | `SEP = ON` | -10.61% | -15.63% | **-13.12%** | May 2010 Flash Crash; `Vol_Z > 1.2` trimmed `TQQQ` to `1x` on May 10 |
| **`2015-08`** | `SEP = ON` | -3.52% | -21.28% | **-12.40%** | Aug 2015 RMB devaluation flash crash; `NSL` held underwater `3x` |
| **`2012-10`** | `SEP = ON` | -9.15% | -15.63% | **-12.39%** | Q3 earnings / fiscal cliff tech pullback |
| **`2024-04`** | `SEP = ON` | -7.90% | -14.34% | **-11.12%** | April 2024 inflation/rate scare; `Vol_Z > 1.2` trimmed `TQQQ` to `1x` on May 1 |
| **`2020-03`** | `SEP = ON` | -12.95% | -7.29% | **-10.12%** | COVID crash (`TQQQ` had already de-levered to `1x QQQ` on `2020-02-25`!) |
