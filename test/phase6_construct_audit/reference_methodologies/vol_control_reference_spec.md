# S&P 500 Risk Control Indices — Reference Specification

## 1. Volatility Estimator
- **Daily Risk Control**: Uses an Exponentially Weighted Moving Average (EWMA) of natural-log returns, typically with decay factors of 94% (short-term) and 97% (long-term).
- **Average Daily Risk Control**: Uses a simple moving average (typically taking the higher of a 20-day or 40-day trailing window).

## 2. Lookback Periods
- EWMA requires an initial lookback period of 252 days to seed the calculation.
- Simple variance uses 20-day and 40-day periods.

## 3. Annualization Convention
- Standard 252 trading days.

## 4. Target-Volatility
- The index targets a constant volatility level (e.g., 5%, 10%, 12%, 15%). The user specifies **10%** for this implementation.

## 5. Exposure Formula
- `Exposure (Weight) = Target Volatility / Realized Volatility`

## 6. Exposure Constraints
- The maximum exposure to the underlying S&P 500 index is explicitly capped at **150%** (1.5x leverage). Minimum exposure is 0%.

## 7. Cash Allocation Treatment
- As of Dec 20, 2021, the cash return component uses the Secured Overnight Financing Rate (SOFR) plus a fixed spread (e.g., SOFR + 0.02963%), replacing LIBOR. For excess return indices, the cash allocation yields zero.

## 8. Rebalance Frequency
- **Daily**. Exposure is recalculated and rebalanced at the end of each trading day.

## 9. Underlying Return Series
- Total Return (TR) or Excess Return (ER) version of the S&P 500, depending on the specific risk-control variant.

## 10. Calculation Timing / Lag Conventions
- Uses a **T-2** lag convention. The volatility measured 2 days prior (T-2) determines the exposure for the current rebalance day (T).

---
## Existing Data Audit
**Data required**:
- S&P 500 daily price history (Total Return or Price Return). We have FRED `SP500` (price return) and Yahoo Finance `SPY` (Total Return via adjusted close).
- SOFR/DFF for cash rate. We have `SOFR` and `DFF` from FRED.

**Conclusion**: We have sufficient high-quality daily data in the repository (via `SPY` adjusted close and `DFF`/`SOFR`) to create an **EXACT or NEAR-EXACT** reconstruction of the Average Daily Risk Control 10% index.
