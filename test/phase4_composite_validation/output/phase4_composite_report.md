# Phase 4 Composite Validation

**Final verdict: NOT_SUPPORTED**

Primary hypothesis: equal-weight Systematic Flow Composite vs 5D SPX forward return.
Phase 3 module verdicts remain unchanged and are not overridden by Phase 4.

## Failure reasons
- Primary 5D HAC rank-regression gate failed.
- Primary 5D IC moving-block bootstrap CI includes zero/wrong direction.
- True 2025-2026 pooled OOS squared-error gate failed.
- Development annual/LOYO robustness rules failed.

> [!WARNING]
> Commit `187a753` and its outputs are **INVALIDATED** because they were generated using a fabricated 2025-01-09 market observation. The results below reflect the true, corrected rerun where `2025-01-09` is properly recognized as a non-trading day (market closed for National Day of Mourning).

3. **True 2025-2026 Pooled OOS Squared-Error Gate**: Failed. Even with the CTA calendar bug fixed, the composite provided exactly zero predictive power out of sample. $\Delta R^2 = -0.0122$, $\Delta MAE = -0.000124$, and the OOS loss differential $d_t$ bootstrap lower bound failed to exclude zero ($p \approx 0.051$).
4. **Development Annual/LOYO Robustness**: Failed. The composite only achieved the correct direction in $37.5\%$ of eligible years (failed the $\ge 70\%$ gate), and triggered 5 catastrophic sign reversals (exceeded the limit of 1).

## Independent Audit Manifest
**Code Commit**: `1ab0566834a8f37de912e00d3e6f3401006aa837`
**Composite Registry Hash**: `e61841acaa7632701cc7720f4e8df13bb06d23373ef274643f3c969a79766305`
**Holdout Snapshots Hash**: `9a545e803681794ea12c78104b5b4323fa19351678cf74b041fdaaef534ec814`
**Holdout Labels Hash**: `c8d7a6ebf6f4f79a1d12a922b4665179818f8c635e9c1e79c9ab360d37aa7590`

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
