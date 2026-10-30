#!/bin/sh
# full post-audit run: truncation tests (prices + fundamentals), determinism test, fundamentals unit tests, backtest,
# gap ledger, EPS-momentum variant. FAIL-FAST (external audit 2026-10-29): any failing command, or any test that does
# not print its PASS marker, stops the chain with a non-zero exit code; ALLDONE is written only if every step passed.
cd "$(dirname "$0")"
set -eu
rm -rf results/coverage_detail.csv
fail() { echo "FAILED: $1" | tee -a logs/backtest_run.log; exit 1; }
python3 pit_truncation_test.py > logs/pit_truncation_test.log 2>&1 || fail pit_truncation_test
grep -q "RESULT: PASS" logs/pit_truncation_test.log || fail "pit_truncation_test (no PASS)"
python3 pit_fundamentals_truncation_test.py > logs/pit_fundamentals_truncation_test.log 2>&1 || fail pit_fundamentals_truncation_test
grep -q "RESULT: PASS" logs/pit_fundamentals_truncation_test.log || fail "pit_fundamentals_truncation_test (no PASS)"
python3 determinism_test.py > logs/determinism_test.log 2>&1 || fail determinism_test
grep -q "RESULT: PASS" logs/determinism_test.log || fail "determinism_test (no PASS)"
python3 test_fundamentals_pit.py > logs/test_fundamentals_pit.log 2>&1 || fail test_fundamentals_pit
grep -q "ALL PASS" logs/test_fundamentals_pit.log || fail "test_fundamentals_pit (no ALL PASS)"
python3 backtest.py > logs/backtest_run.log 2>&1 || fail backtest
python3 build_gap_ledger.py > logs/gap_ledger.log 2>&1 || fail build_gap_ledger
python3 eps_momentum.py > logs/results_eps_momentum.log 2>&1 || fail eps_momentum
echo ALLDONE >> logs/backtest_run.log
