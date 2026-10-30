# S&P Risk Parity Indices — Reference Specification

## 1. Asset Classes
The official S&P Risk Parity Index methodology divides the universe into three primary asset classes:
- Equities
- Fixed Income
- Commodities

## 2. Current Constituent Futures Contracts
A total of **26 rolling futures contracts** make up the index:
1.  **Equities** (e.g., S&P 500, Euro Stoxx 50, Nikkei 225, Russell 2000, NASDAQ 100, E-mini Dow)
2.  **Fixed Income** (e.g., US Treasury 10Y, US Treasury 5Y, US Treasury Long Bond, UK Long Gilt, Euro Bund, Euro Bobl, Euro Buxl, JGB)
3.  **Commodities** (e.g., WTI Crude, Brent Crude, Natural Gas, Gold, Silver, Copper, Corn, Soybeans, Wheat, Live Cattle, Lean Hogs)

*(Note: The exact list of 26 contracts varies slightly over the years depending on liquidity screening, but the core 26 remain stable).*

## 3. Constituent Weighting
- **Inverse Volatility Weighting**: Within each asset class, every individual futures contract is weighted inversely to its long-term realized volatility. This ensures that every contract contributes equally to the risk of its respective asset class.

## 4. Asset-Class Weighting
- **Equal Risk Contribution**: The weights of the three asset classes are dynamically adjusted so that Equities, Fixed Income, and Commodities each contribute exactly **33.3%** to the total portfolio volatility.

## 5. Realized-Volatility Lookback
- Uses a long-term lookback window starting at a minimum of **5 years (1,260 trading days)** and expanding to a maximum of **15 years (3,780 trading days)** for covariance and volatility calculations.

## 6. Rebalance Frequency
- The asset class weights and constituent weights are reviewed and rebalanced **monthly**.
- Portfolio leverage is adjusted dynamically (often daily with a lag) to maintain the target volatility.

## 7. Portfolio Volatility Calculation
- Calculated using long-term realized volatility and the covariances across all 26 sub-indices/futures.

## 8. Leverage / Target-Volatility Multiplier
- `Multiplier = Target Volatility / Portfolio Realized Volatility`.
- If realized volatility < target, multiplier > 1 (leverage applied). If realized volatility > target, multiplier < 1 (deleveraged). Implemented with a 3-day lag.

## 9. Target-Volatility Variants
- Standard variants include **8%, 10%, 12%, and 15%** target volatilities.

## 10. Roll Methodology Dependencies
- Uses systematic rolling futures positions. Transitions from expiring contracts to deferred contracts over a multi-day roll period before expiration to maintain continuous exposure without physical settlement.

## 11. FX Treatment
- Constituent returns are calculated in local currencies and converted to USD using WMR spot exchange rates (typically 4:00 PM London time).

---
## Existing Data Audit
**Data required**:
- 15 years (3,780 trading days) of daily historical prices for **all 26 constituent futures contracts**.
- Historical daily WM/Reuters FX spot rates to convert foreign futures returns (e.g., Euro Stoxx, Gilts, JGBs) into USD.
- SOFR/LIBOR rates for the cash/leverage borrowing costs.

**Conclusion**: The official S&P Risk Parity family uses a multi-asset futures universe (26 contracts, cross-currency), **not a two-asset SPY/DGS10 portfolio**. We do not currently have the required 26 global futures price series or the historical daily FX rates in our repository. Therefore, an **EXACT** replica is currently impossible without a major new data pipeline.
