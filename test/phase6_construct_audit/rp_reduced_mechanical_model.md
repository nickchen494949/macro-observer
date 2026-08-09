# Phase 6.7 — Reduced Risk Parity Mechanical Model

> **Date**: 2026-08-09
> **Commit baseline**: `e83c98b` on `agent/phase4-composite-validation`
> **Diagnostic script**: [`rp_v2_diagnostic.js`](file:///Users/happygolucky/Desktop/宏观观察器/test/phase6_construct_audit/rp_v2_diagnostic.js)

---

## Model Architecture

```
Layer 1: Inverse-Vol Relative Weights (same as V1)
  w_eq = (1/σ_eq) / (1/σ_eq + 1/σ_bond)
  ↓
Layer 2: Portfolio Covariance & Volatility
  σ_p² = w_eq²·σ_eq² + w_bond²·σ_bond² + 2·w_eq·w_bond·Cov(eq,bond)
  ↓
Layer 3: Target-Vol Implied Leverage
  leverage = targetVol / σ_p   (capped at 3.0x, floored at 0.2x)
  ↓
Layer 4: Gross Exposures & Deleveraging Detection
  eqGross = w_eq × leverage
  bondGross = w_bond × leverage
  broadDeleveraging = (ΔeqGross < 0) AND (ΔbondGross < 0)
```

### Configuration (ASSUMPTIONS — NOT VERIFIED)

| Parameter | Value | Source |
|---|---|---|
| Vol lookback | 20 business days | Standard short-term estimate |
| Correlation lookback | 60 business days | ~3 months, captures regime transitions |
| Bond duration | 8 | Approximate 10Y Treasury modified duration |
| **Target portfolio vol** | **10% annualized** | ASSUMPTION — S&P Risk Parity 10% reference |
| **Leverage cap** | **3.0×** | ASSUMPTION — conservative upper bound |
| Leverage floor | 0.2× | Prevent near-zero gross exposure |

---

## Diagnostic Results (10 years: 2016-11 to 2026-08)

### Current State (2026-08-04)

| Metric | Value |
|---|---|
| Equity Vol (20d) | 13.3% |
| Bond Vol (20d) | 5.2% |
| Stock-Bond Corr (60d) | +0.510 |
| Inv-Vol Equity Weight | 28.0% |
| Portfolio Vol | 6.84% |
| Target Leverage | 1.462× |
| Equity Gross Exposure | 41.0% |
| Bond Gross Exposure | 105.2% |
| Total Gross | 146.2% |
| Pressure Direction | leveraging |

### Correlation Impact (the key mechanism V1 missed)

| Corr Bucket | Days | Avg PortVol | Avg Leverage | Avg Total Gross |
|---|---|---|---|---|
| Strong negative (<−0.3) | 888 | 4.4% | 2.44× | 244% |
| Weak negative (−0.3 to −0.1) | 593 | 5.4% | 2.03× | 203% |
| Near zero (−0.1 to +0.1) | 308 | 6.7% | 1.66× | 166% |
| Weak positive (+0.1 to +0.3) | 348 | 7.5% | 1.42× | 142% |
| Strong positive (>+0.3) | 290 | 9.3% | 1.15× | 115% |

> [!IMPORTANT]
> **Correlation is the primary driver of leverage changes.** When stock-bond correlation flips from negative to positive, portfolio vol doubles (4.4% → 9.3%), and implied leverage drops by half (2.44× → 1.15×). This is the mechanism V1 completely lacked.

### Top Deleveraging Episodes

| Date | ΔLev (5d) | Leverage | PortVol | Corr | EqVol | BondVol | Context |
|---|---|---|---|---|---|---|---|
| 2021-03-04 | −0.951 | 1.73× | 5.8% | +0.11 | 15.7% | 6.6% | Bond tantrum / reflation trade |
| 2021-03-03 | −0.906 | 1.77× | 5.6% | +0.08 | 15.6% | 6.6% | Same episode |
| 2020-03-13 | −0.759 | 1.43× | 7.0% | −0.41 | 59.5% | 11.8% | COVID crash |
| 2020-03-18 | −0.664 | 1.32× | 7.6% | −0.57 | 85.4% | 16.1% | COVID peak volatility |
| 2020-11-12 | −0.748 | 1.88× | 5.3% | −0.14 | 22.4% | 6.0% | Post-election vol spike |

### V1 vs V2 Comparison

| Metric | V1 | V2 |
|---|---|---|
| Deleveraging detection days | 0 (100% miss rate) | 619 days (25.6% of sample) |
| Leverage model | Hardcoded `null` | Target-vol implied, 0.2×–3.0× |
| Correlation in allocation | Computed but unused | Drives portfolio vol → leverage |
| Broad deleveraging (both assets sold) | Heuristic label only | Quantitative: 224 days (9.2%) |

> [!CAUTION]
> **V1 missed 100% of deleveraging events.** Every single day where the V2 leverage model detected meaningful deleveraging (5d change < −5%), V1's heuristic (`eqVol>20% AND bondVol>15% AND corr>0.3`) returned `none`. The thresholds were too high to ever trigger in practice.

---

## Plain-Language Answers

### 1. Does V1 get the relative stock/bond allocation broadly right?

**Partially.** Average weight difference between inverse-vol and true equal-risk-contribution (ERC) is **10.6 pp**, with a max of **52.1 pp**. The two formulas diverge significantly when correlation is far from zero. When correlation is strongly negative, ERC gives MORE weight to equities (because the diversification benefit makes equities less risky to the portfolio); inverse-vol ignores this.

However, for a 2-asset portfolio, the relative allocation is much less important than the leverage decision. Even with 10 pp weight error, the directional signal (equity weight rising/falling) is usually correct.

### 2. How often does V2 leverage produce meaningful deleveraging that V1 completely missed?

**100% of the time.** V2 detected 619 days of meaningful deleveraging (25.6% of the sample). V1's hard-coded thresholds never triggered. The V1 thresholds (eqVol>20%, bondVol>15%, corr>0.3) represent extremely stressed conditions — basically requiring a simultaneous stock crash AND bond crash with positive correlation. This combination is rare.

The V2 model detects subtler but economically important deleveraging: portfolio vol rising from 5% to 7% causes leverage to drop from 2× to 1.4×, forcing mechanical selling even when neither asset individually crosses V1's thresholds.

### 3. During stock-bond correlation spikes, how much does portfolio vol and leverage change?

**Dramatically.** Moving from strong negative correlation (−0.3 or below) to strong positive correlation (+0.3 or above):
- Portfolio vol: 4.4% → 9.3% (+112%)
- Leverage: 2.44× → 1.15× (−53%)
- Total gross exposure: 244% → 115% (−53%)

This is the defining mechanism of Risk Parity deleveraging: when diversification breaks down (correlation turns positive), the portfolio becomes much riskier, and the leverage overlay forces selling of ALL assets.

### 4. Which historical stress periods show the biggest mechanical deleveraging?

1. **2021 Feb-Mar Bond Tantrum**: Largest single-episode leverage drop (−0.95× in 5 days). Bond yields spiked, correlation flipped positive, equity vol elevated. This is the textbook "RP selling both stocks and bonds."
2. **2020 March COVID**: Extreme equity vol (85%!) drove massive deleveraging despite negative stock-bond correlation. Even with diversification benefit, the sheer magnitude of equity vol overwhelmed the portfolio.
3. **2020 November**: Post-election vol spike with correlation near zero — a moderate deleveraging event.
4. **2023 November**: Brief 3-day broad deleveraging, leverage hit 1.12×.

---

## Implementation Recommendation

The V2 model should be integrated into `flow_engine.js` as a new parallel module `rpMechanicalPressure`, following the pattern of `vcMechanicalPressure`. Key output fields:

```javascript
{
  status: 'ok',
  equityWeight: 0.280,           // inverse-vol relative weight
  bondWeight: 0.720,
  portfolioVol: 0.0684,          // annualized
  stockBondCorrelation: 0.510,
  targetLeverage: 1.462,
  leverageChange1d: 0.0134,
  leverageChange5d: 0.0120,
  equityGrossExposure: 0.410,
  bondGrossExposure: 1.052,
  equityExposureChange5d: ...,
  bondExposureChange5d: ...,
  pressureDirection: 'leveraging',   // leveraging | deleveraging | neutral
  broadDeleveraging: false,          // true when BOTH exposures shrink
  observationDate: '2026-08-04',
  assumptions: {
    targetPortfolioVol: 0.10,        // ASSUMPTION
    leverageCap: 3.0,                // ASSUMPTION
    volLookback: 20,
    corrLookback: 60,
    bondDuration: 8,
  },
  disclaimer: 'Reduced 2-asset RP proxy. Does not represent actual RP fund positions or AUM.'
}
```
