# Phase 6.2: External Benchmark Feasibility & Reference Models

This document assesses the feasibility of acquiring or constructing external benchmarks to validate our flow proxies. The goal is to establish a "ground truth" (or reference methodology) for proxy mechanics and positioning *before* testing predictive edge.

We evaluate benchmark candidates across the four proxy layers, assessing their data characteristics, biases, and ultimate suitability.

---

## 1. Volatility Control

**Candidate 1: S&P 500 Daily Risk Control 10% Index**
- **Provider**: S&P Dow Jones Indices
- **Dataset/Index**: SPXT10D (S&P 500 Daily Risk Control 10% TR)
- **Exact quantity measured**: Equity exposure required to maintain a 10% target volatility using short-term realized volatility.
- **Frequency**: Daily
- **History start**: Base date often 1990s, live since ~2009.
- **Publication lag**: End of day (for index level), methodology is public.
- **Public/free vs paid**: Methodology is free/public. Official daily weights require paid subscription.
- **Reproducibility**: Highly reproducible based on the public index methodology document.
- **Measures**: Model mechanics.
- **Major contamination/biases**: Assumes continuous daily rebalancing without threshold triggers; represents only one specific vol-target methodology, not the entire industry.
- **Suitability score**: **HIGH** (for mechanics validation)

**Candidate 2: S&P 500 Average Daily Risk Control 10% Index**
- **Provider**: S&P Dow Jones Indices
- **Dataset/Index**: SPXADR10 (Average Daily Risk Control)
- **Exact quantity measured**: Equity exposure targeting 10% volatility using a blended 20-day / 40-day volatility lookback.
- **Frequency**: Daily
- **History start**: Base date 1990s.
- **Publication lag**: End of day.
- **Public/free vs paid**: Methodology is free/public. 
- **Reproducibility**: Highly reproducible.
- **Measures**: Model mechanics.
- **Major contamination/biases**: See above.
- **Suitability score**: **HIGH** (for mechanics validation)

---

## 2. Risk Parity

**Candidate 1: S&P Risk Parity Index Family (8%, 10%, 12%, 15% Target Vol)**
- **Provider**: S&P Dow Jones Indices
- **Dataset/Index**: S&P Risk Parity Index - 10% Target Volatility (SPRP10T)
- **Exact quantity measured**: Asset class weights (Equity, Fixed Income, Commodities) achieving equal risk contribution, plus the total gross leverage required to hit the target volatility.
- **Frequency**: Daily (rebalanced monthly)
- **History start**: Backtested to 2004, live since 2018.
- **Publication lag**: End of day.
- **Public/free vs paid**: Methodology is publicly available and detailed. 
- **Reproducibility**: Reproducible. The methodology document details the exact covariance matrix formulation (often an exponentially weighted moving average) and leverage scaling rules.
- **Measures**: Model mechanics (specifically asset risk allocation, portfolio volatility, gross leverage, and leverage change).
- **Major contamination/biases**: Represents a formalized, monthly-rebalanced index rather than active proprietary funds (which may de-risk intra-month).
- **Suitability score**: **HIGH** (for mechanics validation)

---

## 3. CTA (Triangulation Approach)

Since no single ground truth exists for aggregate CTA dollar positioning, we evaluate three candidates for a triangulated validation.

**Candidate 1: CFTC Traders in Financial Futures (TFF) - Leveraged Money**
- **Provider**: Commodity Futures Trading Commission (CFTC)
- **Dataset/Index**: TFF Report (E-mini S&P 500, Nasdaq 100, Russell 2000)
- **Exact quantity measured**: Net long/short position of "Leveraged Money" traders.
- **Frequency**: Weekly (Positions as of Tuesday)
- **History start**: 2006.
- **Publication lag**: Released Friday at 3:30 PM EST (3-day lag).
- **Public/free vs paid**: Public and free.
- **Reproducibility**: 100% reproducible directly from CFTC CSV downloads.
- **Measures**: Actual positioning / Position change.
- **Major contamination/biases**: "Leveraged Money" includes all hedge funds, quantitative macro funds, and relative-value funds, not just CTAs. It is heavily contaminated by non-trend positioning.
- **Suitability score**: **MEDIUM** (Required for the triangulation approach)

**Candidate 2: Société Générale (SG) Trend / CTA Indices**
- **Provider**: Société Générale Prime Services
- **Dataset/Index**: SG Trend Index, SG CTA Index
- **Exact quantity measured**: Daily net returns of the largest trend-following managers.
- **Frequency**: Daily
- **History start**: 2000.
- **Publication lag**: 1-2 days.
- **Public/free vs paid**: Publicly visible, but official historical downloads are gated / paid / require Bloomberg.
- **Reproducibility**: Hard to cleanly reproduce historical data programmatically without a paid data feed.
- **Measures**: Returns (which can be regressed against asset returns to estimate rolling equity beta/positioning).
- **Major contamination/biases**: Survivorship bias in index constituents.
- **Suitability score**: **MEDIUM** (Data sourcing is the primary bottleneck)

**Candidate 3: AQR Time Series Momentum (TSMOM) Dataset**
- **Provider**: AQR Capital Management
- **Dataset/Index**: Time Series Momentum Original Paper Data
- **Exact quantity measured**: Theoretical returns of a standard 1-to-12 month time-series momentum strategy across global asset classes.
- **Frequency**: Monthly
- **History start**: 1880.
- **Publication lag**: Updated periodically (often quarterly or annually).
- **Public/free vs paid**: Public and free (Excel download).
- **Reproducibility**: 100% reproducible.
- **Measures**: Model mechanics (standardized trend return benchmark).
- **Major contamination/biases**: It is a monthly return series, which makes daily positioning validation impossible.
- **Suitability score**: **LOW** (Frequency and lag make it unsuitable for daily operational validation, though conceptually useful)

---

## 4. Pension Rebalance

**Candidate 1: Institutional Sell-Side Rebalance Estimates**
- **Provider**: J.P. Morgan, Goldman Sachs, UBS, etc.
- **Dataset/Index**: Pre-month-end equity flow estimates ($ Billions).
- **Exact quantity measured**: Estimated aggregate dollar flow required by domestic pensions to rebalance to static IPS targets.
- **Frequency**: Monthly/Quarterly (Ad-hoc desk notes).
- **History start**: Varies.
- **Publication lag**: Ad-hoc, usually T-3 to T-5 days before month-end.
- **Public/free vs paid**: Highly restricted, paid institutional research.
- **Reproducibility**: Zero. Sourced from proprietary desk models and client flow visibility.
- **Measures**: Actual flow estimates.
- **Major contamination/biases**: Estimates are notoriously subjective, highly dispersed between banks, and occasionally front-run by the desks issuing them.
- **Suitability score**: **REJECT / DATA_NOT_AVAILABLE**

*Verdict for Pension*: We will not invent a fake historical dataset. The pension proxy will remain UNVALIDATED via external benchmark data.

---

## Next Step: Minimum Benchmark Ingestion Pipeline

To proceed with Phase 6.2, we propose building the following ingestion pipeline for our **HIGH** and **MEDIUM** suitability targets:

### 1. Risk Control & Risk Parity Mechanics Reference Models
We do not need to purchase the S&P daily weights. Instead, we will:
1. Download the official S&P Daily Risk Control and S&P Risk Parity Index methodology PDFs.
2. Implement exact programmatic replicas (Reference Models) of these methodologies in our codebase.
3. Feed our existing local price/yield data (SPY, DGS10, etc.) into these Reference Models to generate the *Reference Exposure Series* and *Reference Leverage Series*.
4. **Validation Test**: Statistically compare our VC V1 and RP V1 estimated exposures against the Reference Exposure Series to identify mechanical deviations (e.g., Level agreement, ΔExposure agreement, Direction agreement, Extreme-event agreement).

### 2. CFTC TFF Triangulation Pipeline
1. Build a lightweight Python fetcher to download the historical CFTC TFF ZIP/CSV from `cftc.gov`.
2. Extract the "Leveraged Money" net long/short positions for E-mini S&P 500, Nasdaq 100, and Russell 2000.
3. Map the Tuesday release data accurately to our calendar, respecting the Friday publication lag.
4. **Validation Test**: Evaluate whether our CTA V1 proxy's weekly aggregated equity position changes correlate (in magnitude and direction) with the weekly changes in Leveraged Money net positioning.
