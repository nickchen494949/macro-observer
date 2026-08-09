# Phase 6.6 — Risk Parity V1 Construct Audit

> **Date**: 2026-08-09
> **Commit baseline**: `9030407` on `agent/phase4-composite-validation`
> **Source file**: [`lib/flow_engine.js` lines 564–663](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L564-L663)

---

## 1. Frozen V1 Mechanics

### 1.1 Inputs

| Input | Source | Alignment | Notes |
|---|---|---|---|
| **Equity** | `^GSPC` (S&P 500) via Yahoo | Calendar-aligned to NYSE via `alignToCalendar(..., 'cta_close', usEquityCalendar)` | Uses `adjClose` field. Single equity index. |
| **Bond** | `DGS10` (10Y Treasury Yield) via FRED | Calendar-aligned to NYSE with `carryForward = true` | Yield, not price. Converted to pseudo-return via duration approximation. |

> [!IMPORTANT]
> Only two assets. No commodities, no credit, no international, no TIPS, no short-term rates.

### 1.2 Bond Return Approximation

```javascript
// Line 571
returns.push(-duration * (arr[i][1] - arr[i-1][1]) / 100);
```

| Parameter | Value | Notes |
|---|---|---|
| Duration | Hardcoded **8** | Reasonable for a 10Y Treasury (~7.5–8.5 effective duration) |
| Formula | `-D × ΔY` | First-order linear approximation. Ignores convexity, roll yield, coupon carry. |
| Yield source | DGS10 constant-maturity yield | Not a specific bond price. Carry-forwarded across NYSE holidays. |

**Assessment**: The approximation is standard for short-horizon analysis. It underestimates returns during large yield moves (convexity missing) but is adequate for a 20-day vol estimate. **APPROXIMATE but acceptable for this purpose.**

### 1.3 Volatility Calculation

```javascript
// Lines 576–581
const eqRet20 = getDailyReturns(spx, 20);       // log returns
const bondRet20 = getBondReturnsRP(dgs10, 20, 8); // linear duration returns
const eqStd20 = calcStd(eqRet20);                // sample std (N-1 denominator)
const bondStd20 = calcStd(bondRet20);
const eqVol20d = eqStd20 * Math.sqrt(252);       // annualized
const bondVol20d = bondStd20 * Math.sqrt(252);
```

| Parameter | Value |
|---|---|
| Lookback | **20 business days** (1 month) |
| Return type | Equity: log returns. Bonds: linear duration-based returns |
| Annualization | √252 |
| Estimator | Sample standard deviation, (N-1) denominator |

> [!WARNING]
> **No longer-term vol estimate.** S&P RP uses blended short/long-term covariance (e.g., 20d + 120d + 252d). V1 uses only 20d. This means V1 reacts aggressively to short-term vol spikes without any mean-reversion anchor.

### 1.4 Allocation Formula

```javascript
// Lines 627–630
estEqAlloc = (1/eqVol20d) / (1/eqVol20d + 1/bondVol20d);
estBondAlloc = 1 - estEqAlloc;
```

**This is a 2-asset inverse-volatility model.** Specifically:

$$w_{\text{equity}} = \frac{1/\sigma_{\text{eq}}}{1/\sigma_{\text{eq}} + 1/\sigma_{\text{bond}}}$$

Key properties:
- Weights sum to 1.0 (fully invested, no leverage)
- No covariance/correlation in weight calculation
- No target portfolio volatility
- No leverage multiplier

> [!CAUTION]
> **This is NOT Risk Parity.** True Risk Parity equalizes *risk contribution* (weight × marginal risk), which requires the full covariance matrix. Inverse-vol only equalizes risk contribution when assets are uncorrelated ($\rho = 0$). When stock-bond correlation deviates from zero (which it routinely does), inverse-vol gives different weights than risk parity.

### 1.5 Five-Day Allocation Change

```javascript
// Lines 583–588: Calculate 5-day-ago allocation using data ending 5 days earlier
const eqRet20_5d = getDailyReturns(spx.slice(0, spx.length - 5), 20);
const bondRet20_5d = getBondReturnsRP(dgs10.slice(0, dgs10.length - 5), 20, 8);
// ... same inverse-vol formula ...
const allocChange = estEqAlloc - estEqAlloc_5d;
```

This computes Δallocation by comparing today's inverse-vol weights to 5-days-ago inverse-vol weights. **Mechanically correct for what it measures.**

### 1.6 Stock-Bond Correlation

```javascript
// Lines 623–624
const aligned60 = getAlignedReturns(spx, dgs10, 60, logReturn, bondReturn);
const stockBondCorr60d = calcCorr(aligned60.ret1, aligned60.ret2);
```

- 60-day lookback
- Properly date-aligned via `getAlignedReturns`
- Pearson correlation

> [!WARNING]
> **Correlation is computed but does NOT enter the allocation formula.** It is only used in the deleveraging-pressure heuristic (see §1.8). This is the single biggest gap vs. real Risk Parity.

### 1.7 Leverage Calculation

```javascript
// Line 653
modelLeverageChange5d: rpStatus === 'ok' ? 0 : null,
```

**Hardcoded to zero. Always.** There is no leverage model. The weights sum to 1.0 by construction.

In real Risk Parity:
- Portfolio leverage = (target vol) / (realized portfolio vol)
- When both stocks and bonds sell off simultaneously, portfolio vol spikes → leverage drops → forced selling of both assets
- This is the primary deleveraging mechanism

**V1 has no mechanism to produce this.**

### 1.8 Deleveraging Pressure Heuristic

```javascript
// Lines 639–641
if (eqVol20d > 0.20 && bondVol20d > 0.15 && stockBondCorr60d > 0.3)
  dp = 'high';
else if (eqVol20d > 0.20 || bondVol20d > 0.15)
  dp = 'moderate';
```

| Condition | Label | Logic |
|---|---|---|
| Eq vol > 20% AND Bond vol > 15% AND Corr > 0.3 | `broad_deleveraging` | All three must be true |
| Eq vol > 20% OR Bond vol > 15% | `moderate_deleveraging` | Either vol is elevated |
| Neither | `none` | Default |

**This is a qualitative regime label, not a quantitative deleveraging estimate.** It correctly identifies *conditions under which* real RP funds would deleverage, but it does not estimate the magnitude or timing of such deleveraging.

### 1.9 Rebalance/Timing Assumptions

There are **no rebalance timing assumptions** in the RP module. The model assumes continuous rebalancing (today's weights reflect today's vols). Real RP funds rebalance at varying frequencies (daily, weekly, monthly) with smoothing.

### 1.10 `totalDeRisking` Field

```javascript
// Line 656
totalDeRisking: rpStatus === 'ok' ? (dp === 'high') : null,
```

Boolean flag: `true` only when all three conditions (eq vol > 20%, bond vol > 15%, corr > 0.3) are met simultaneously. Used to trigger the "⚠️ Dual Selloff Risk Active" banner in the UI.

---

## 2. Comparison with S&P Risk Parity Methodology

| Mechanism | S&P Risk Parity Index | V1 Implementation | Classification |
|---|---|---|---|
| **Asset universe** | 3 classes (equities, bonds, commodities) with multiple sub-assets per class | 2 assets (SPX, 10Y Treasury) | **MISSING** |
| **Within-class allocation** | Equal risk contribution within each asset class (e.g., US/Intl equities) | N/A — single asset per class | **MISSING** |
| **Cross-asset covariance** | Full covariance matrix drives both allocation AND leverage | Correlation computed but not used in allocation | **MISSING** |
| **Allocation formula** | Minimize portfolio variance subject to equal risk contribution | Inverse-vol (ignores correlation) | **PARTIAL** — same family, wrong formula |
| **Portfolio vol target** | 10% annualized target volatility | None | **MISSING** |
| **Leverage multiplier** | Target vol / realized portfolio vol | Hardcoded to 0 change | **MISSING** |
| **Leverage deleveraging** | Automatic: when portfolio vol rises, leverage falls, forcing selling of ALL assets | Heuristic label only | **MISSING** |
| **Vol estimation** | Blended short + long-term (e.g., 20d + 60d or exponential) | 20-day only | **PARTIAL** |
| **Covariance estimation** | Blended short + long-term with shrinkage | Not used in allocation | **MISSING** |
| **Rebalance frequency** | Monthly with daily monitoring | Continuous (no rebalance model) | **NOT_REPRODUCIBLE_WITH_CURRENT_DATA** |
| **Futures/FX treatment** | Indices implemented via futures; FX hedging creates additional flows | Not modeled | **MISSING** |
| **Risk contribution equalization** | Core objective: each asset contributes equal marginal risk | Not attempted — only inverse-vol | **MISSING** |

### Summary Count

| Classification | Count |
|---|---|
| PRESENT | 0 |
| PARTIAL | 2 |
| MISSING | 9 |
| NOT_REPRODUCIBLE_WITH_CURRENT_DATA | 1 |

> [!CAUTION]
> **Zero mechanisms are fully PRESENT.** The model is fundamentally a different construct from Risk Parity.

---

## 3. Output Field Audit

| Field | Current Value (example) | Classification | Rationale |
|---|---|---|---|
| `equityAllocationChange5d` | `-0.013` | **VALID_DESCRIPTIVE** | Correctly measures the 5-day change in a 2-asset inverse-vol equity weight. But it's inverse-vol, not risk parity. |
| `bondAllocationChange5d` | `+0.013` | **VALID_DESCRIPTIVE** | Mirror of equity change (weights sum to 1). Redundant but consistent. |
| `modelLeverageChange5d` | `0` (always) | **MISLEADING** | Implies leverage was modeled and found unchanged. In reality, no leverage model exists. Should be `null` or removed. |
| `allocationDirection` | `equity_to_bonds` | **VALID_DESCRIPTIVE** | Correctly describes the direction of inverse-vol weight shift. |
| `deleveragingPressure` | `none` / `moderate` / `broad` | **APPROXIMATE** | The heuristic conditions (high vol + positive correlation) are genuinely associated with RP deleveraging episodes. But it's a regime label, not a flow estimate. |
| `totalDeRisking` | `false` | **MISLEADING** | Name implies the model detects total de-risking. Actually just tests three static thresholds. |

### Dashboard UI Claims

| UI Element | Current Text | Classification |
|---|---|---|
| Card title | "风险平价配置与去风险代理 / Risk-Parity Allocation & De-Risking Proxy" | **APPROXIMATE** — "Proxy" qualifier is honest, but "Risk-Parity" is technically wrong |
| "Allocation Shift (5D, pp)" | Shows `equityAllocationChange5d` | **VALID_DESCRIPTIVE** — accurately describes what it measures |
| "Total De-Risking" | Shows `deleveragingPressure` | **MISLEADING** — implies quantitative de-risking detection |
| "⚠️ Dual Selloff Risk Active" banner | Hidden div, triggered by `totalDeRisking` | **APPROXIMATE** — the conditions it checks ARE associated with RP stress, but the name overstates certainty |
| Timeline: "Risk parity model: equity → bonds" | Shows direction + 5D shift | **APPROXIMATE** — describes a real signal but calls it "risk parity" |

---

## 4. Human-Readable Verdict

### 4.1 What does RP V1 actually measure?

**RP V1 is a 2-asset (SPX + 10Y Treasury) inverse-volatility allocation model.** It answers:

> "If you allocated between stocks and bonds proportional to inverse 20-day volatility, would the equity weight be rising or falling this week?"

This is a useful signal. When equity vol spikes, the model correctly shows equity weight dropping. When bond vol spikes, equity weight rises. The 5-day change captures the directional shift.

The deleveraging heuristic is a reasonable qualitative flag: when BOTH assets are volatile AND positively correlated, real RP funds face genuine pressure to reduce gross exposure.

### 4.2 What does it fail to measure?

1. **Leverage.** The defining feature of Risk Parity is that portfolios are levered to hit a vol target. When vol spikes, leverage drops, forcing selling of *all* assets. V1 has no leverage model (hardcoded to 0).

2. **Covariance in allocation.** Inverse-vol ≠ equal risk contribution. When stock-bond correlation is significantly non-zero, the two give different answers. V1 computes correlation but doesn't use it.

3. **Multi-asset universe.** Real RP includes commodities, TIPS, international equities, credit. V1 only has stocks and nominal Treasuries.

4. **Gross flow magnitude.** V1 says "direction is equity → bonds" but cannot estimate how many dollars of rebalancing this implies across the RP industry.

5. **Rebalance timing.** Real RP funds rebalance at different frequencies. V1 assumes continuous rebalancing.

### 4.3 Which existing dashboard claims should be renamed or removed?

| Current | Recommended |
|---|---|
| "Risk-Parity Allocation & De-Risking Proxy" | **"Stock-Bond Relative Volatility Allocation"** or **"Inverse-Vol Allocation Shift"** |
| `modelLeverageChange5d: 0` | **Remove** or change to `null` with comment "leverage not modeled" |
| `totalDeRisking` (boolean) | **Rename** to `dualSelloffConditions` — it detects *conditions*, not actual de-risking |
| `deleveragingPressure` | **Rename** to `dualVolatilityRegime` or `stressRegime` |
| Timeline "Risk parity model" | **Rename** to "Inv-vol allocation model" |
| Summary "Risk parity —" | **Rename** to "Stock/bond vol allocation —" |

### 4.4 Is a reduced but scientifically defensible RP proxy possible with current data?

**Yes, partially.** With only SPX + DGS10, we can build:

1. **Inverse-vol allocation with correlation adjustment** — use the 2×2 covariance matrix to compute proper equal-risk-contribution weights. This is a real 2-asset risk parity, just with a limited universe. Formula:

$$w_{\text{eq}} = \frac{\sigma_{\text{bond}}^2 - \rho \cdot \sigma_{\text{eq}} \cdot \sigma_{\text{bond}}}{\sigma_{\text{eq}}^2 + \sigma_{\text{bond}}^2 - 2\rho \cdot \sigma_{\text{eq}} \cdot \sigma_{\text{bond}}}$$

2. **Portfolio-vol-implied leverage** — compute the portfolio vol of the risk-contribution-equalized portfolio and derive leverage = 10% / portfolio_vol. Track leverage changes over 5d as a proxy for deleveraging pressure.

3. **Multi-window vol estimation** — blend 20d and 60d (or 120d) vol estimates for stability.

**What remains NOT possible** without additional data:
- Commodity allocation (would need commodity futures data — we have CL, GC, but not a broad basket)
- Cross-country equity decomposition
- Credit allocation
- Actual RP fund leverage data (proprietary)

> [!TIP]
> **Bottom line**: V1 is a valid directional indicator for "are conditions shifting toward stocks or bonds?" It is NOT a valid indicator for "are Risk Parity funds deleveraging?" The leverage question requires at minimum a portfolio-vol-based leverage model, which V1 doesn't have.

---

## Appendix: Code Reference Map

| Concept | Lines | File |
|---|---|---|
| Bond return approximation | 565–573 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L565-L573) |
| 20d vol calculation | 576–581 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L576-L581) |
| 5d-ago vol calculation | 583–588 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L583-L588) |
| Correlation (60d) | 590–624 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L590-L624) |
| Inverse-vol allocation | 626–635 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L626-L635) |
| Allocation change | 637 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L637) |
| Deleveraging heuristic | 639–641 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L639-L641) |
| Output object | 649–663 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L649-L663) |
| Summary usage | 838–846, 959–962 | [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js#L838-L846) |
| UI card | 451–473 | [flow.html](file:///Users/happygolucky/Desktop/宏观观察器/flow.html#L451-L473) |
| Render function | 971–1000 | [flow.html](file:///Users/happygolucky/Desktop/宏观观察器/flow.html#L971-L1000) |
| V3 schema | 222–247 | [flow_api_v3.schema.json](file:///Users/happygolucky/Desktop/宏观观察器/config/schemas/flow_api_v3.schema.json#L222-L247) |
