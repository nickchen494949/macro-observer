# Phase 6.5 — VC Measurement Redesign

## Status: CLOSED — VC audit complete, ready for migration

---

## 1. Evidence Summary (Phase 6.3–6.4)

| Finding | Value | Source |
|---|---|---|
| Exposure level rank correlation (V1 vs S&P Ref) | **ρ = 0.97** | Phase 6.3 |
| Daily ΔExposure correlation | **r = 0.31** | Phase 6.3 |
| Daily direction agreement | **48%** | Phase 6.3 |
| V1 timing vs Reference | **V1 LEADS by ~2 days** | Phase 6.4 (corrected) |
| Primary timing cause | Missing T-2 observation lag | Phase 6.4 Q2 |
| Primary bias cause | 150% cap (should be 100%) | Phase 6.4 Q1 |
| Smoothing (λ=0.25) role | Accidentally masks early reaction; compresses daily magnitude ~40% | Phase 6.4 Q3 |

**Conclusion**: V1 correctly identifies the volatility regime / exposure state (ρ = 0.97), but cannot be used as a reliable daily institutional flow indicator (direction agreement ≈ coin flip).

---

## 2. Formal Separation of Concepts

### 2A. `VC_Regime_State` (preserve V1 as-is for this role)

**What it is**: A descriptive indicator of the current volatility environment and the implied equity exposure level for a generic 10%-target vol-control strategy.

**Validated use**:
- "Is the vol environment low / normal / elevated / crisis?"
- "Would a vol-control fund be near-full or significantly underweight right now?"
- Rank-ordering of exposure across time (ρ = 0.97 vs official methodology)

**Not validated for**:
- "Today the vol-control industry is buying/selling $X billion"
- "The exact daily rebalancing pressure is +/- Y%"

**Existing V1 fields that remain valid for this role**:

| Field | Status | Note |
|---|---|---|
| `volForecastToday` | ✅ Valid as regime indicator | 20/60 blend tracks general vol well |
| `targetExposureToday` | ⚠️ Use with caution | Level is directionally right but biased +11pp |
| `actualExposureToday` | ⚠️ Use with caution | Smoothed; regime-correct but flow-incorrect |
| `regime_vc` | ✅ Valid | low / normal / elevated / crisis thresholds |

### 2B. `VC_Mechanical_Pressure` (new parallel construct)

**What it is**: A standardised model-implied trading-pressure proxy built from transparent, verifiable S&P-style risk control mechanics.

**Methodology** (all parameters verified from official S&P Risk Control Indices Parameters document, July 2026):

```
Underlying:       S&P 500 Price Return (SPX)
Vol windows:      20-day, 40-day simple volatility
Vol selection:    higher of the two estimates
Target vol:       10%
Max exposure:     100%
Observation lag:  T-2 business days
Rebalance:        daily, instant snap to target
```

**Exact variance equation**: UNKNOWN (approximated with sample std dev, ddof=1, sqrt(252) annualisation).

**Output fields**:

| Field | Type | Description |
|---|---|---|
| `targetExposure` | float [0, 1.0] | min(10% / selected_vol, 1.0) using T-2 observation |
| `deltaExposure` | float | targetExposure[t] − targetExposure[t−1] |
| `pressureDirection` | enum | `buying` / `selling` / `neutral` |
| `pressureMagnitudePct` | float | abs(deltaExposure) as percentage |
| `extremeDeleveraging` | bool | true when deltaExposure falls in bottom 5th percentile historically |
| `selectedVol` | float | max(vol20, vol40) |
| `vol20` | float | 20-day annualised simple vol |
| `vol40` | float | 40-day annualised simple vol |
| `observationDate` | date | T-2 date used for vol calculation |

**What it is NOT**:
- NOT actual aggregate industry dollar flow
- NOT calibrated to real-world AUM ($400bn or any other figure)
- NOT a prediction of SPX future returns

**Claim boundary**:

> `VC_Mechanical_Pressure` is a standardised model-implied trading-pressure proxy validated against a transparent mature volatility-control methodology. It describes what a rule-following fund *would* do mechanically, not what the entire industry *actually* does.

---

## 3. Fields to Mark as UNVALIDATED

The following existing V1 output fields in [flow_engine.js](file:///Users/happygolucky/Desktop/%E5%AE%8F%E8%A7%82%E8%A7%82%E5%AF%9F%E5%99%A8/lib/flow_engine.js#L310-L352) rely on `$400bn × ΔExposure`:

| Field | Line | Action |
|---|---|---|
| `estimatedDailyFlowUsd` | L342 | Mark `UNVALIDATED_DOLLAR_ESTIMATE` |
| `nextDayEstimateIfTargetUnchanged` | L343 | Mark `UNVALIDATED_DOLLAR_ESTIMATE` |
| `estimatedFlowRange` | L344 | Mark `UNVALIDATED_DOLLAR_ESTIMATE` |

These should either:
1. Be tagged with an explicit `amountValidation: 'UNVALIDATED_DOLLAR_ESTIMATE'` flag, or
2. Be removed from any summary/predictive output that treats them as calibrated numbers

The `estimatedAum = 400e9` constant on L310 has no verified source and should not be used for quantitative claims.

---

## 4. Migration Path

### Immediate (Phase 6.5 scope)
- [x] Document the two-concept separation (this file)
- [ ] Build `VC_Mechanical_Pressure` as a parallel compute path in flow_engine
- [ ] Tag existing dollar-flow outputs as UNVALIDATED
- [ ] No production UI changes yet

### Future (post-Phase 6, if desired)
- Replace V1 dollar-flow display with `VC_Mechanical_Pressure` outputs
- If real industry AUM data becomes available, calibrate `pressureMagnitudePct × AUM` as a validated dollar figure
- Evaluate whether keeping V1's 20/60 blend + smoothing adds value as an independent "smoothed regime" view

---

## 5. What VC Has Graduated To

Before Phase 6:
> "Vol-control funds are buying/selling $X billion today based on our model"

After Phase 6:
> "The vol environment implies [high/low] equity exposure for a standard 10%-target strategy. A rule-following fund would be [increasing/decreasing] its position by [X]% today. This is a mechanical model output, not a measured industry flow."

---

## 6. VC Work Status: SEALED

No further ablation, parameter tuning, or SPX return testing.

Next construct to audit: **Risk Parity**.
