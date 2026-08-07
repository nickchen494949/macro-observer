# Phase 6.1: Measurement Target & External Benchmark Specification

This specification freezes the measurement targets and validation criteria for the core indicator proxies. Do not implement new models or evaluate predictive performance on SPX forward returns until these construct validation standards are met.

---

## 1. Risk Parity

**A. Latent real-world quantity we ultimately want to estimate:**
Future 1–5 day aggregate institutional Risk Parity fund equity trading flow (forced deleveraging or re-leveraging).

**B. What the current proxy actually measures:**
A naive univariate inverse-volatility relative asset allocation shift.

**C. Observable external benchmark(s) that could validate the proxy:**
- Known historical Risk Parity deleveraging episodes (e.g., Feb 2018 "Volmageddon", March 2020).
- Publicly traded Risk Parity mutual fund exposure levels or beta to equities.
- Institutional sell-side estimates of systematic deleveraging.

**D. Required units:**
Dollar flow or percentage of AUM change (incorporating both target weight shifts and total portfolio gross leverage changes).

**E. Required timing/frequency:**
Daily.

**F. Parameters that can be supported by external evidence:**
- Underlying asset realized volatility and covariance (directly computable from market data).

**G. Parameters that remain unobservable assumptions:**
- Exact AUM size of the industry.
- Leverage scaling functions and hard caps utilized by major funds.
- Covariance lookback window utilized by the majority of AUM.
- Strict stop-loss or VaR triggers.

**H. Construct-validation test to perform BEFORE any SPX-return testing:**
Compare the proxy's estimated massive deleveraging days against historically known liquidity events where Risk Parity was cited as a major seller.

**I. Conditions required to classify the proxy as CONSTRUCT_VALIDATED:**
The proxy accurately spikes in selling pressure exactly on dates of historically verified RP deleveraging, without generating excessive false positives during normal volatility regimes.

---

## 2. CTA ETF Proxy

**A. Latent real-world quantity we ultimately want to estimate:**
Aggregate Managed Futures (CTA) industry equity exposure and the resulting daily exposure change.

**B. What the current proxy actually measures:**
The today-versus-yesterday position change of a single, highly specific 50/100/200-day Simple Moving Average crossover model.

**C. Observable external benchmark(s) that could validate the proxy:**
- Prime broker CTA positioning estimates.
- Publicly available CTA indices (e.g., SG CTA Index) equity beta.
- CFTC Commitments of Traders (COT) reports for equity index futures.

**D. Required units:**
Estimated exposure level and exposure change (or trading-pressure score).

**E. Required timing/frequency:**
Daily.

**F. Parameters that can be supported by external evidence:**
- Overall historical trend length tendencies (which can be derived by regressing CTA index returns against market trends of varying lookbacks).

**G. Parameters that remain unobservable assumptions:**
- Exact mix of fast/medium/slow models deployed by the industry.
- True AUM deployed to specific equity buckets.
- Specific risk limits or volatility scaling formulas.

**H. Construct-validation test to perform BEFORE any SPX-return testing:**
Regress the proxy's estimated aggregate position level against the beta of the SG CTA Index to the S&P 500, or compare against known prime-broker positioning estimates over time.

**I. Conditions required to classify the proxy as CONSTRUCT_VALIDATED:**
Strong, statistically significant correlation between the proxy's estimated position level and the externally observed CTA equity beta/positioning over the same periods.

---

## 3. Volatility Control

**A. Latent real-world quantity we ultimately want to estimate:**
The aggregate equity exposure change of the entire Volatility-Targeting fund universe (Variable Annuities, Indexed Annuities, systematic vol-targeting funds).

**B. What the current proxy actually measures:**
Synthetic estimated dollar-equivalent flow of a single, monolithic fund assuming exactly 10% target-volatility, a 25% adjustment speed, and a fixed $400bn AUM.

**C. Observable external benchmark(s) that could validate the proxy:**
- Prime broker estimates of Vol Control equity supply/demand.
- Market footprint studies of Annuity hedging flow.

**D. Required units:**
Estimated dollar flow or percentage exposure change.

**E. Required timing/frequency:**
Daily.

**F. Parameters that can be supported by external evidence:**
- Realized volatility of the underlying index.
- Target volatility distribution (often publicly stated in VA prospectus documents, usually ranging from 8% to 15%).

**G. Parameters that remain unobservable assumptions:**
- Exact aggregate AUM currently active.
- Distribution of adjustment speeds across heterogeneous funds.
- Usage of threshold triggers vs. continuous daily rebalancing.

**H. Construct-validation test to perform BEFORE any SPX-return testing:**
Compare the proxy's estimated daily equity buying/selling magnitude against structural estimates provided by sell-side derivatives desks.

**I. Conditions required to classify the proxy as CONSTRUCT_VALIDATED:**
The proxy successfully tracks the shape and magnitude of known industry-wide de-risking and re-risking cycles without relying on arbitrary hardcoded "cliff" parameters that create false shocks.

---

## 4. Pension Rebalance

**A. Latent real-world quantity we ultimately want to estimate:**
Month-end and quarter-end aggregate institutional pension fund equity rebalancing demand.

**B. What the current proxy actually measures:**
Estimated equity drift magnitude required to mean-revert a simplified 60/40 stock-bond portfolio at the end of the month.

**C. Observable external benchmark(s) that could validate the proxy:**
- Sell-side month-end pension rebalancing flow estimates.
- Aggregate mutual fund/pension flow data.

**D. Required units:**
Dollar magnitude (or trading-pressure score). Must explicitly distinguish between a directional proxy vs. actual dollar magnitude.

**E. Required timing/frequency:**
Month-end and Quarter-end (typically executing in the final few trading days of the month).

**F. Parameters that can be supported by external evidence:**
- 60/40 asset allocation benchmark is an industry standard.
- Execution windows (T-3 to T+2) align with known institutional execution algorithms.

**G. Parameters that remain unobservable assumptions:**
- Actual aggregate AUM adhering strictly to these thresholds.
- Exact duration of the aggregate bond portfolio.
- How many funds allow deviation bands vs. strict mechanical mean-reversion.

**H. Construct-validation test to perform BEFORE any SPX-return testing:**
Evaluate if the proxy's large "sell equities" or "buy equities" directional signals at quarter-ends align with external institutional reports of pension equity flows for those same quarters.

**I. Conditions required to classify the proxy as CONSTRUCT_VALIDATED:**
The proxy consistently predicts the correct *direction* of the imbalance that matches external aggregate pension flow estimates for quarter/month ends, proving its drift mechanism mirrors the real world.
