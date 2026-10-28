#!/bin/sh
# full post-audit run: truncation test, determinism test, backtest, gap ledger, EPS-momentum variant
cd "$(dirname "$0")"
rm -rf results/coverage_detail.csv
python3 pit_truncation_test.py > pit_truncation_test.log 2>&1
python3 determinism_test.py > determinism_test.log 2>&1
python3 backtest.py > backtest_run.log 2>&1
python3 build_gap_ledger.py > gap_ledger.log 2>&1
python3 eps_momentum.py > results_eps_momentum.log 2>&1
echo ALLDONE >> backtest_run.log
