# Phase 4 Composite Validation

This pipeline is independent of Phase 3. Phase 3 module verdicts remain locked and are never overwritten.

## Holdout prerequisite

Phase 3 canonical snapshots stop at 2024-12-31, so Phase 4 requires a separate, uninspected holdout replay for 2025-2026.

Generate it before running the Python pipeline (replace the end date with the latest available date if needed):

```bash
node backtest/build_historical_snapshots.js 2025-01-01 2026-08-07 phase4/snapshots_phase4_holdout.json 0
```

`01_build_composite_panel.py` will fail closed if this holdout artifact is missing or if it does not contain both 2025 and 2026 with complete 5D labels available from the local SPX data.

## Run

```bash
python3 test/phase4_composite_validation/01_build_composite_panel.py
python3 test/phase4_composite_validation/02_test_composite_ic.py
python3 test/phase4_composite_validation/03_composite_oos.py
python3 test/phase4_composite_validation/04_composite_robustness.py
python3 test/phase4_composite_validation/05_composite_gate.py
```

The production `lib/flow_engine.js` composite is intentionally untouched until the Phase 4 verdict is `SUPPORTED`.
