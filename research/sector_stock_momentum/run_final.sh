#!/bin/sh
# full post-audit run: truncation test, determinism test, backtest, gap ledger, EPS-momentum variant
cd "$(dirname "$0")"
rm -rf results/coverage_detail.csv
python3 pit_truncation_test.py > logs/pit_truncation_test.log 2>&1
python3 determinism_test.py > logs/determinism_test.log 2>&1
python3 backtest.py > logs/backtest_run.log 2>&1
python3 build_gap_ledger.py > logs/gap_ledger.log 2>&1
python3 eps_momentum.py > logs/results_eps_momentum.log 2>&1
echo ALLDONE >> logs/backtest_run.log
