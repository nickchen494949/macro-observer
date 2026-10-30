# Phase 6.7a — RP Model Consistency Fix

> **Date**: 2026-08-10
> **Commit baseline**: `69a39f1` on `agent/phase4-composite-validation`

---

## Problem

The Phase 6.7 RP mechanical model had **two different implementations** computing portfolio volatility:

| Component | Portfolio Vol Formula | Source |
|---|---|---|
| **Diagnostic** (`rp_v2_diagnostic.js`) | 60d coherent covariance matrix: `w²·Var_60d(eq) + w²·Var_60d(bond) + 2·w·w·Cov_60d` | Lines 87-112 |
| **Production** (`flow_engine.js`) | Mixed: `w²·Vol_20d(eq)² + w²·Vol_20d(bond)² + 2·w·w·Corr_60d·Vol_20d(eq)·Vol_20d(bond)` | Lines 674-677 |

These are **mathematically different models**. The mixed formula (20d vol × 60d corr) creates an incoherent matrix where the variance and correlation come from different samples.

### Consequences

The old production code reported `broadDeleveraging=true` on 2026-08-09 while the old diagnostic showed `broadDeleveraging=false` on 2026-08-04 — not just because of date differences, but because the formulas diverged.

---

## Fix: Single Canonical Function

### Architecture

```
lib/rp_mechanical.js           ← SINGLE SOURCE OF TRUTH
  ├── computeRpSnapshot()       ← one point-in-time calculation
  ├── computeRpMechanicalPressure() ← snapshot + deltas (1d, 5d)
  ├── buildAlignedReturns()     ← date-align SPX + DGS10
  └── (pure math helpers)

flow_engine.js                  ← production: calls rp_mechanical.js
rp_v2_diagnostic.js             ← backtest: calls rp_mechanical.js
rp_consistency_test.js          ← equality test: proves they match
```

### Frozen Covariance Convention

| Layer | Lookback | Window | Purpose |
|---|---|---|---|
| **Allocation** (inverse-vol weights) | 20 business days | Separate from risk | More reactive to recent vol changes |
| **Portfolio Risk** (full covariance matrix) | 60 business days | **Coherent** — Var(eq), Var(bond), Cov(eq,bond) ALL from same 60d window | Stable, principled risk estimate |

> [!IMPORTANT]
> The covariance matrix for portfolio volatility is computed entirely from the 60d `riskLookback` window.
> We do NOT mix 20d asset vol with 60d correlation. That was the bug in the Phase 6.7 production code.

### Formula

```
Layer 1:  w_eq = (1/σ_eq_20d) / (1/σ_eq_20d + 1/σ_bond_20d)

Layer 2:  σ_p² = w_eq²·Var_60d(eq)·252 + w_bond²·Var_60d(bond)·252 + 2·w_eq·w_bond·Cov_60d(eq,bond)·252

Layer 3:  leverage = min(max(targetVol / σ_p, 0.2), 3.0)

Layer 4:  eqGross = w_eq × leverage
          bondGross = w_bond × leverage
```

### Assumptions (NOT VERIFIED)

| Parameter | Value | Label |
|---|---|---|
| Target portfolio vol | 10% annualized | ASSUMPTION |
| Leverage cap | 3.0× | ASSUMPTION |
| Leverage floor | 0.2× | ASSUMPTION |
| Bond duration | 8 | ASSUMPTION |

---

## Latest-State Mismatch: Root Cause

| | Production | Diagnostic |
|---|---|---|
| **Last date** | 2026-08-09 | 2026-08-04 |
| **SPX data through** | 2026-08-07 (+ calendar-aligned to 08-09) | 2026-08-07 |
| **DGS10 data through** | 2026-08-04 (carry-forwarded to 08-09) | 2026-08-04 (no carry) |
| **portfolioVol** | 6.89% | 6.97% |
| **targetLeverage** | 1.451× | 1.435× |
| **pressureDirection5d** | neutral | leveraging |
| **broadDeleveraging5d** | false | false |

**Root cause**: NOT a formula difference. Both now use `rp_mechanical.js`. The date gap comes from:
1. Production's calendar-alignment carry-forwards DGS10 yield (08-04 value) into 08-05, 08-06, 08-07, 08-09
2. Diagnostic's `buildAlignedReturns` only uses dates where BOTH series have actual observations (stops at 08-04)
3. Production therefore has ~3 extra days of SPX returns paired with stale bond yields

Both approaches are **correct for their use case**:
- Production: should show the latest available signal even with carry-forwarded FRED data
- Diagnostic: should only compute on days with fresh observations for clean historical analysis

---

## Corrected Deleveraging Counts

### Fixed Terminology

| Term | Definition | Old (wrong) count |
|---|---|---|
| `leverageReduction5d` | Target leverage fell > 0.01× in 5 days | Was called "619 deleveraging days" |
| `broadDeleveraging5d` | BOTH equity AND bond gross exposures fell > 0.005 in 5 days | Was "224 days" |

### Corrected Counts (canonical model, 2433 days)

| Metric | Days | % of sample |
|---|---|---|
| Leverage reduction (1d) | 668 | 27.5% |
| Leverage reduction (5d) | 984 | 40.4% |
| **Broad deleveraging (1d)** | **113** | **4.6%** |
| **Broad deleveraging (5d)** | **227** | **9.3%** |

### Sustained Broad Deleveraging Episodes (≥3 consecutive days, sorted by severity)

| Period | Duration | Min Leverage | Context |
|---|---|---|---|
| 2022-10-03 → 10-11 | 6d | 0.811× | UK gilt crisis / global rates shock |
| 2022-06-10 → 06-16 | 5d | 0.880× | Fed 75bp hike, CPI shock |
| 2020-03-12 → 04-01 | **15d** | 1.065× | COVID crash (longest episode) |
| 2023-11-03 → 11-08 | 4d | 1.094× | Term premium spike |
| 2025-04-22 → 04-30 | 7d | 1.341× | Recent stress |
| 2026-03-20 → 04-01 | 9d | 1.532× | Recent stress |

### V1 Comparison (corrected framing)

> [!WARNING]
> V1 had no leverage model at all. Comparing "V1 miss rate = 100%" is **tautological**, not validation evidence.
> The correct statement is: "The leverage layer detects a mechanism that V1 was not designed to model."

---

## Equality Test Results

```
=== TEST 1: Function purity (same input → same output) ===
  19 passed, 0 failed

=== TEST 2: buildAlignedReturns consistency ===
  23 passed, 0 failed

=== TEST 3: Date-by-date equality (204 historical dates) ===
  204 matched, 0 mismatched

=== TEST 4: Edge cases ===
  3 passed, 0 failed

TOTAL: 28 passed, 0 failed
✅ ALL CONSISTENCY TESTS PASSED
```

---

## Files Changed

| File | Change |
|---|---|
| [rp_mechanical.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/rp_mechanical.js) | **NEW** — canonical RP model function |
| [flow_engine.js](file:///Users/happygolucky/Desktop/宏观观察器/lib/flow_engine.js) | Replaced 100-line inline RP with 10-line call to `rp_mechanical.js` |
| [flow_api_v3.schema.json](file:///Users/happygolucky/Desktop/宏观观察器/config/schemas/flow_api_v3.schema.json) | Updated rpMechanicalPressure: 1d/5d split, leverageReduction, broadDeleveraging |
| [rp_v2_diagnostic.js](file:///Users/happygolucky/Desktop/宏观观察器/test/phase6_construct_audit/rp_v2_diagnostic.js) | Rewritten to call canonical function; corrected terminology |
| [rp_consistency_test.js](file:///Users/happygolucky/Desktop/宏观观察器/test/phase6_construct_audit/rp_consistency_test.js) | **NEW** — 28-assertion equality test |
