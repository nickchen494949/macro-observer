# Phase 4 Composite Validation

**Final verdict: NOT_SUPPORTED**

Primary hypothesis: equal-weight Systematic Flow Composite vs 5D SPX forward return.
Phase 3 module verdicts remain unchanged and are not overridden by Phase 4.

## Failure reasons
- Primary 5D HAC rank-regression gate failed.
- Primary 5D IC moving-block bootstrap CI includes zero/wrong direction.
-3. **True 2025-2026 Pooled OOS Squared-Error Gate**: Failed. Even with the CTA missing data hole repaired, the composite provided exactly zero predictive power out of sample. $\Delta R^2 = -0.0117$, $\Delta MAE = -0.000115$, and the OOS loss differential $d_t$ bootstrap lower bound failed to exclude zero ($p \approx 0.073$).
4. **Development Annual/LOYO Robustness**: Failed. The composite only achieved the correct direction in $37.5\%$ of eligible years (failed the $\ge 70\%$ gate), and triggered 5 catastrophic sign reversals (exceeded the limit of 1).

## Independent Audit Manifest
**Code Commit**: `1ab0566834a8f37de912e00d3e6f3401006aa837`
**Composite Registry Hash**: `e61841acaa7632701cc7720f4e8df13bb06d23373ef274643f3c969a79766305`
**Holdout Snapshots Hash**: `e9cbc81e5d6002194fb8ac15a36ab1d8fce71dbb001ab0b5da39c165c8f2c47c`
**Holdout Labels Hash**: `4906a8da30a90f326355c03b8a0f5327b601aacc73ec58de98e47657d8221321`

## Gate components
- Development IC valid: True
- Development IC direction: True
- Development HAC gate: False
- Development IC bootstrap: False
- Development Partial IC: True
- True holdout OOS valid: True
- True holdout OOS squared-error gate: False
- Development robustness valid: True
- Development robustness gate: False

Production flow_engine.js remains untouched unless verdict is SUPPORTED.
