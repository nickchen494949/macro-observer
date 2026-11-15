# Frozen V1 TQQQ Strategy Specification (2026-11-15)

> **Reproducible Engine**: [`frozen_v1_tqqq_strategy.py`](../../frozen_v1_tqqq_strategy.py)  
> **Summary Table**: [`v1_tqqq_summary.csv`](./v1_tqqq_summary.csv)  
> **Monthly Ledger (`2009–2026`)**: [`v1_tqqq_monthly_ledger_2009_2026.csv`](./v1_tqqq_monthly_ledger_2009_2026.csv)

---

## 1. Core Division of Labor (`SEP = Pure Cash`, `Volatility = 1x QQQ`)

1. **Macro Gate (`FOMC SEP`)**:
   - **Target Horizon**:
     - March & June (`month < 9`): compare current-year (`YYYY`) median Core PCE & Fed Funds Rate projections vs previous SEP.
     - September & December (`month >= 9`): compare next-year (`YYYY + 1`) median projections vs previous SEP.
   - **`EXIT (SEP = OFF)`**: `(c_rate > p_rate) and (c_pce > p_pce) and (c_pce > 2.0%)` $\rightarrow$ **`100% Pure Cash (SGOV)`** (unconditionally overrides `NSL`).
   - **`ENTER (SEP = ON)`**: `(c_rate <= p_rate)`.

2. **Volatility Layer (`When SEP = ON` — switches strictly between `3x TQQQ` and `1x QQQ` with `NSL` [Never Sell in Loss / 只止盈不割肉])**:
   - **`V1-Monthly` (Monthly Ratio Rebalance)**:
     - At each month-end $t$, compute on `QQQ` daily returns:
       - $\sigma_{252}(t) = \text{std}(r_{\text{QQQ}}, \text{past 252 trading days})$
       - $\sigma_{21}(t) = \text{std}(r_{\text{QQQ}}, \text{past 21 trading days})$
     - Target `3x TQQQ` weight:
       $$w_{\text{target}}(t) = \min\left(1.0,\; \left(\frac{k \cdot \sigma_{252}(t)}{\sigma_{21}(t)}\right)^2\right) \quad (k = 1.0 \text{ standard}, \; k = 1.1 \text{ sweet spot})$$
     - Remainder $1 - w_{\text{target}}(t)$ is allocated to **`1x QQQ`**.
     - **`NSL` Rule**: When $w_{\text{target}}(t) < w_{\text{current}}(t)$, only trim `TQQQ` to `QQQ` if the current `TQQQ` position is in profit ($\text{TQQQ\_Value} \ge \text{TQQQ\_Cost\_Basis}$). If underwater, hold existing `TQQQ` and `QQQ` buckets without selling `TQQQ` at a loss.
   - **`V1-Daily` (Daily `1-Year Vol_Z + NSL` — `QQQ_Risk_Strategy` Engine)**:
     - Compute 20-day annualized volatility $\text{rvol}_{20}$ of `QQQ`, and its 252-day rolling mean and std:
       $$\text{Vol\_Z}(d) = \frac{\text{rvol}_{20}(d) - \mu_{252}(d)}{\sigma_{252}(d)}$$
     - When `Vol_Z > Trig` (`1.5` standard / `1.2` sweet spot) **AND in profit (`NSL`)**: switch `3x TQQQ` $\rightarrow$ **`1x QQQ`**.
     - When `Vol_Z < Rec` (`0.5` standard / `0.3` sweet spot): switch `1x QQQ` $\rightarrow$ **`3x TQQQ`**.

---

## 2. Headline Performance (`2009–2026` & `2010–2026`)

| Strategy Variant | `2009–2026` CAGR | `2009–2026` Daily MaxDD | `2009–2026` Sharpe | `2009–2026` Multiple | `2010–2026` CAGR | `2010–2026` Daily MaxDD | `2010–2026` Sharpe | `2010–2026` Multiple |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0. Pure SEP Baseline (`SEP=ON` 100% TQQQ, `SEP=OFF` Cash)** | `55.7%` | `-69.9%` | `1.08` | `2,701x` | `49.9%` | `-69.9%` | `1.03` | `907x` |
| **1. `V1-Monthly` Standard (`k=1.0`, `(std_252/std_21)^2 + NSL`)** 🏆 | **`55.9%`** | **`-54.3%`** | **`1.16`** | **`2,745x`** | **`49.6%`** | **`-54.3%`** | **`1.10`** | **`876x`** |
| **2. `V1-Monthly` Sweet-Spot (`k=1.1`, `(1.1*std_252/std_21)^2 + NSL`)** 🏆 | **`56.2%`** | **`-56.1%`** | **`1.14`** | **`2,841x`** | **`49.8%`** | **`-56.1%`** | **`1.09`** | **`905x`** |
| **3. `V1-Daily` Standard (`1Y Vol_Z 1.5/0.5 + NSL`)** 🏆 | **`57.6%`** | **`-48.3%`** | **`1.21`** | **`3,361x`** | **`51.7%`** | **`-43.5%`** | **`1.18`** | **`1,129x`** |
| **4. `V1-Daily` Sweet-Spot (`1Y Vol_Z 1.2/0.3 + NSL`)** 🏆 | **`57.7%`** | **`-48.3%`** | **`1.23`** | **`3,428x`** | **`52.7%`** | **`-44.5%`** | **`1.21`** | **`1,258x`** |

---

## 3. Live 2026-11 Status

- **Macro Gate (`SEP`)**: **`SEP = OFF`** (triggered `2026-06-17`, confirmed `2026-09-16` with Core PCE `3.4%` and 2027 dot `4.1%`) $\rightarrow$ **Actual Position = `100% SGOV (Pure Cash)`**.
- **Volatility Readout (`2026-11-13`)**:
  - `QQQ` 252-day daily std = `1.33%` (`21.0%` ann), 21-day daily std = `2.00%` (`31.7%` ann) $\rightarrow$ `V1-Monthly` target ratio (if `SEP` were ON) = **`44.1% TQQQ / 55.9% QQQ`**.
  - `V1-Daily` `Vol_Z` = **`+2.15`** (`> 1.5`, `VOL DANGER`).
