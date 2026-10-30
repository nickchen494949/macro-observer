# Phase 5 Exploratory Multi-Horizon Validation Report

This report summarizes the performance of exploratory multi-horizon structures tested strictly as diagnostics. This does not constitute a true holdout or confirmatory study. As requested, Phase 4 has been sealed as `NOT_SUPPORTED` and left unmodified.

## General Setup
- **Sample**: Full dataset (2016-2026).
- **Normalization**: Expanding historical ECDF (using strictly prior observations).
- **Weighting**: Equal weight, arithmetic mean.
- **Timing Constraint**: Signal and trade entry strictly delayed to the maximum `firstTradableSession` of active components.

---

## 1. MediumFlow_20D (CTA + RP)
**Hypothesis**: The CTA and Risk Parity modules represent slower-moving capital, whose price impact might only materialize over a longer 20-day horizon.

**Results**:
- **N**: 2292
- **Spearman IC**: -0.0170
- **Expected Direction Pass**: No (Negative IC)
- **HAC p-value (two-sided)**: 0.646
- **Bootstrap 95% IC CI**: `[-0.091, 0.057]` (spans zero)
- **Partial Rank IC**: -0.0006
- **Annual Consistency**: Correct direction in only 40.0% of years (4 of 10).
- **LOYO Median IC**: -0.0148
- **Catastrophic Reversals**: 6

**Verdict on MediumFlow_20D**: **FAILED**. Extending the horizon to 20 days did not reveal any hidden edge for CTA or RP. The relationship remains near-zero, statistically insignificant, and highly unstable across years. This definitively rejects the hypothesis that "the time scale was just too short."

---

## 2. ShortFlow_1D (Vol Control + Pension)
**Hypothesis**: Volatility Control and Pension rebalancing flows act rapidly, predicting 1-day equity returns.

**Results**:
- **N**: 2490
- **Spearman IC**: +0.0037
- **Expected Direction Pass**: Yes (but negligible magnitude)
- **HAC p-value (two-sided)**: 0.841
- **Bootstrap 95% IC CI**: `[-0.034, 0.040]` (spans zero)
- **Partial Rank IC**: +0.0148
- **Annual Consistency**: Correct direction in 54.5% of years.
- **LOYO Median IC**: +0.0045
- **Catastrophic Reversals**: 5

### ShortFlow Diagnostic Decomposition
Because Pension is only active during the final days of the month, we decompose the aggregate result:
- **Pension Inactive Days**: $N = 1815$ (72.9%), **IC = -0.0139**
- **Pension Active Days**: $N = 675$ (27.1%), **IC = +0.0787**

**Verdict on ShortFlow_1D**: **FAILED** overall, but structurally revealing. The aggregate 1D predictive power is zero. However, decomposition shows that Volatility Control (which runs alone on inactive days) has slightly negative/zero edge. The positive IC is almost entirely driven by the Pension module during its active window. 

---

## 3. CoreFlow_5D (VC + CTA + RP + Pension)
*(Benchmark/Control Structure)*

**Results**:
- **N**: 2307
- **Spearman IC**: -0.0187
- **HAC p-value (two-sided)**: 0.535
- **Bootstrap 95% IC CI**: `[-0.079, 0.042]`
- **Partial Rank IC**: -0.0031
- **Annual Consistency**: 30% of years.

**Verdict**: As established in Phase 4, this structure has no predictive power.

---

## Component-to-Component Rank Correlations
*(Measured across the entire Phase 5 panel)*

| Module | VC | CTA | RP | Pension |
| :--- | :--- | :--- | :--- | :--- |
| **Vol Control (VC)** | 1.000 | 0.201 | 0.617 | -0.428 |
| **CTA ETF Proxy** | 0.201 | 1.000 | 0.124 | -0.183 |
| **Risk Parity (RP)** | 0.617 | 0.124 | 1.000 | -0.242 |
| **Pension (active)** | -0.428 | -0.183 | -0.242 | 1.000 |

*Note: VC and Risk Parity are highly correlated (+0.617), which makes sense since both rely heavily on inverse market volatility. Pension flow acts counter-cyclically to the others.*

---

## Conclusion & Next Steps

Following the established interpretation rules:
1. **Both `ShortFlow_1D` and `MediumFlow_20D` remain near-zero, unstable across years, and have bootstrap intervals that comfortably span zero.**
2. Extending the CTA/RP horizon to 20 days did not rescue them.
3. The only glimmer of signal comes from Pension rebalancing on its isolated days, but it is heavily diluted when combined with the negative-edge VC module.

**Recommendation**: We must conclude that the current proxy layer (specifically the CTA and RP ETF-based proxies, and the VC structural estimate) lacks evidence of structural predictive value. We should **STOP** all formula/weight tuning and composite building. The next logical step is to investigate the underlying proxy definitions—i.e., answering the fundamental question of whether the CTA and RP proxies actually represent true institutional positioning changes in the real world.
