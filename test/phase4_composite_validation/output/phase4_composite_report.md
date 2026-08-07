# Phase 4 Composite Pipeline Results

The Phase 4 Systematic Flow Composite has been rigorously evaluated over the canonical Phase 3 dataset (2016-2024 as Development/Diagnostic) and the true Phase 4 Holdout (2025-2026).

## Final Verdict
**Composite Status**: `NOT_SUPPORTED`

## Summary of Gate Failures
1. **Primary 5D HAC Rank-Regression**: Failed. The single-factor model yielded a statistically insignificant Spearman IC ($p=0.91$).
2. **Primary 5D IC Moving-Block Bootstrap**: Failed. The 5000-iteration overlapping block bootstrap 95% Confidence Interval for the IC was $[-0.068, 0.071]$, cleanly straddling zero.
3. **True 2025-2026 Pooled OOS Squared-Error Gate**: Failed. The composite provided exactly zero predictive power out of sample. $\Delta R^2 = -0.02$, $\Delta MAE = -0.00018$, and the OOS loss differential $d_t$ bootstrap failed to exclude zero.
4. **Development Annual/LOYO Robustness**: Failed. The composite only achieved the correct direction in $37.5\%$ of eligible years (failed the $\ge 70\%$ gate), and triggered 5 catastrophic sign reversals (exceeded the limit of 1).

## Independent Audit Manifest
**Code Commit**: `1ab0566834a8f37de912e00d3e6f3401006aa837`
**Composite Registry Hash**: `e61841acaa7632701cc7720f4e8df13bb06d23373ef274643f3c969a79766305`
**Holdout Snapshots Hash**: `c8fe261244a604b7b60c14bbe3a188c0583e31afe4dd30e5a7da07968746938f`
**Holdout Labels Hash**: `4906a8da30a90f326355c03b8a0f5327b601aacc73ec58de98e47657d8221321`

## Conclusion
The hypothesis that aggregating the weak signals into an equal-weight composite would reveal true systemic buying pressure is completely rejected by the data. The composite behaves as pure noise on an out-of-sample basis, performing worse than the simple momentum/volatility baseline.

We fail to reject the null hypothesis. Production behavior in `lib/flow_engine.js` remains untouched.
