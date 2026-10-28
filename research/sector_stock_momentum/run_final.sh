#!/bin/sh
# final post-audit run: determinism test, then the backtest, then the gap ledger
cd "$(dirname "$0")"
python3 determinism_test.py > determinism_test.log 2>&1
python3 backtest.py > backtest_run.log 2>&1
python3 build_gap_ledger.py > gap_ledger.log 2>&1
echo ALLDONE >> backtest_run.log
