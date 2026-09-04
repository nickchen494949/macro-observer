# S&P 500 Average Daily Risk Control 10% Price Return Index (SPXAV10P) — Reference Specification

## 1. Verified Core Parameters
*(Source: Official S&P Dow Jones Risk Control Indices Parameters Document)*
- **Underlying Price Return index**: S&P 500 Price Return (SPX)
- **Risk Control target**: 10%
- **Maximum leverage / equity exposure**: 100%
- **Volatility calculation type**: Average
- **Return frequency for volatility**: Daily
- **Short volatility window**: 20 days
- **Long volatility window**: 40 days
- **Volatility input used**: Higher of the two simple volatility estimates computed over the trailing 20-day and 40-day windows.
- **Rebalancing frequency**: Daily
- **Lag to rebalancing date**: 2 days (T-2)

## 2. Unverified Mathematical Parameters
*(Source: Mathematical expansion not explicitly defined in the Parameters document)*
- **Exact realized-volatility mathematical equation**: UNKNOWN (Specific variance denominator, return type transformation, and annualization constant remain approximations in our reference model).

## 3. Exposure Formula
- `Target Exposure = Target Volatility (10%) / Selected Volatility`
- `Effective Exposure = min(Target Exposure, 100%)` applied with a 2-day lag.

## 4. Rebalance/Calculation Timing and Rounding
- **Rounding Rules**: UNKNOWN

---
*(Note: Previous assumptions of a 150% maximum exposure apply to other Risk Control variants and have been explicitly removed. SPXAV10P uses a strict 100% cap).*
