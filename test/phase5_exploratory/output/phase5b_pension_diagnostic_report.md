# Phase 5B: Pension Attribution Diagnostic

Following the Phase 5 multi-horizon exploratory results, we isolated the `ShortFlow_1D` active window ($N = 675$) to determine if its positive predictive power was genuinely driven by the Pension module, or if it was an artifact of Volatility Control interacting with end-of-month seasonalities.

## 1. Baseline Isolation Test
We tested the exact same 675 active window observations against the 1D forward return using three different scores:

| Signal Tested | Spearman IC | Interpretation |
| :--- | :--- | :--- |
| **A. Pension Score Alone** | **+0.0941** | Strong, isolated predictive power |
| **B. VC Score Alone** | -0.0172 | Negative edge |
| **C. (VC + Pension) / 2** | +0.0787 | VC actively dragged the composite down |

## 2. Multivariate Regression
We ran an OLS regression on the ranks of the signals to evaluate their independent contributions:
$$ rank(Return_{1D}) = \alpha + \beta_{Pension} \cdot rank(Pension) + \beta_{VC} \cdot rank(VC) $$

| Component | Beta | p-value |
| :--- | :--- | :--- |
| **Pension** | **+0.1044** | **0.013** |
| **Vol Control (VC)** | +0.0253 | 0.546 |

**Finding**: When controlling for VC, Pension retains strong, statistically significant predictive power ($p = 0.013$). VC provides no significant contribution.

## 3. Pension-Alone Deep Dive
Testing the **Pension Score Alone** across its 675 active observations yields the following detailed metrics:

- **N**: 675
- **Spearman IC**: **+0.0941**
- **HAC p-value**: **0.012** (Passes formal <0.05 gate)
- **Bootstrap 95% IC CI**: **`[0.014, 0.166]`** (Strictly positive, does not span zero)
- **Partial Rank IC**: +0.0494 (Controlling for underlying market momentum and volatility)

### Annual Consistency
- **2016**: +0.308
- **2017**: +0.058
- **2018**: +0.257
- **2019**: +0.071
- **2020**: +0.252
- **2021**: +0.038
- **2022**: +0.112
- **2023**: -0.068
- **2024**: +0.004
- **2025**: +0.166
- **2026**: -0.022
*Result: 9 out of 11 years (81.8%) show a positive IC.*

### Mechanism Breakdown
We sliced the active window to understand exactly when the flows are most predictive:

**A. Seasonality / Magnitude**
- **Quarter-End Months** (Mar, Jun, Sep, Dec): **IC = +0.104** ($N=280$)
- **Ordinary Month-End**: **IC = +0.086** ($N=395$)
*Quarter-ends represent larger rebalancing flows and exhibit a stronger predictive edge.*

**B. Execution Window Timing**
- **Pre-Month-End** (Before or on the final trading day): **IC = +0.079** ($N=437$)
- **Post-Month-End** (First 2 days of the new month): **IC = +0.042** ($N=238$)
*The bulk of the predictive power is captured by positioning ahead of the final close, rather than the spillover into the new month.*

## Verdict
Your intuition was completely correct. **The Pension module is the sole survivor of the proxy layer.** It possesses a genuine, statistically robust, and structurally logical predictive edge. Combining it with VC in `ShortFlow_1D` merely diluted its power.

As you outlined:
| Proxy | Status |
| :--- | :--- |
| **Vol Control** | FAILED |
| **CTA ETF** | FAILED |
| **Risk Parity** | FAILED |
| **5D Composite** | FAILED |
| **CTA+RP 20D** | FAILED |
| **Pension Rebalance** | **CONFIRMED SURVIVOR** |
