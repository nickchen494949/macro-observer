# Phase 6 Construct Audit: Reference Model Readiness

This document outlines our ability to faithfully reconstruct the official S&P methodologies for Volatility Control and Risk Parity, which will serve as the benchmark for grading our Phase 6 proxies.

## Part A: S&P 500 Daily Risk Control 10%
**Can we faithfully reproduce S&P Vol Control?**
Yes. The mathematical formulation (EWMA or 20/40-day Simple Variance) and the required data series (S&P 500 daily price return / total return, and daily SOFR/DFF rates) are well within our current repository's capabilities.

**Reconstruction Feasibility**: `NEAR_EXACT_REPLICA_FEASIBLE`
*(Note: It is "near-exact" rather than strictly exact only because we may use the SPY ETF adjusted close as a proxy for the S&P 500 Total Return index, or DFF instead of exact SOFR spreads prior to 2021, but mathematically it will be essentially identical to the official behavior).*

---

## Part B: S&P Risk Parity
**Can we faithfully reproduce S&P Risk Parity?**
No. The official S&P Risk Parity indices employ a highly complex, 26-constituent futures portfolio spanning three asset classes (Equities, Fixed Income, Commodities) across multiple global regions (US, Europe, Japan).

**Data Availability Matrix**:

| Required series | Exact instrument | Required history | Existing in repo? | Substitute available? | Exact / approximate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Equities** (6+ series) | S&P 500, Euro Stoxx 50, Nikkei 225, Russell 2000, etc. Futures | 15+ years daily | ❌ SPY only | Yes (ETFs) | Approximate |
| **Fixed Income** (10+ series) | US Treasuries (5Y/10Y/Long), Gilts, Bunds, JGBs Futures | 15+ years daily | ❌ US Treasuries only | Yes (ETFs) | Approximate |
| **Commodities** (10+ series) | WTI, Brent, Gold, Silver, Corn, Soybeans, etc. Futures | 15+ years daily | ❌ WTI/NatGas only | Yes (ETFs/Prices) | Approximate |
| **FX Rates** | WM/Reuters Spot Rates | 15+ years daily | ❌ No | Yes (Yahoo FX) | Approximate |
| **Borrowing Rates** | SOFR/LIBOR | 15+ years daily | ✅ Yes (DFF) | N/A | Exact |

**Reconstruction Feasibility**: `REDUCED_REFERENCE_ONLY`

---

## Summary & Next Steps
1. **What new market datasets are required?**
   - For a true exact S&P Risk Parity replica, we would need to build a massive new pipeline downloading daily historical continuous futures data for 26 global instruments, plus daily FX rates. This is deemed out of scope.
2. **Which comparisons against V1 would actually be scientifically valid?**
   - **Vol Control**: We can safely compare our existing V1 exposure against the `NEAR_EXACT_REPLICA` we build here. If our V1 behaves like the S&P Average Daily Risk Control 10%, it validates our Vol Control proxy as a mature vol-targeting algorithm.
   - **Risk Parity**: We can only build a **Simplified 2-Asset Reference** (SPY + DGS10 or TLT) using inverse volatility weighting. We must explicitly label this as a "Simplified Reduced Reference" rather than an S&P replica. We can compare our RP V1 against this simplified reference to ensure basic parity mechanics (inverse-vol weighting, constant vol targeting) are functioning correctly.

*(Note: We will not ingest CFTC data or write V2 proxies until these reference comparisons are complete).*
