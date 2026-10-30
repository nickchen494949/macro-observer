#!/bin/sh
# Post-audit-2 rerun (2026-10-29): fixes from the external audit of 7f24e9b + availability tie-break + identity fixes.
# Order: main backtest + tests → ML panel → ML dev/holdout → S&P variants → explosive panel/labels → v2 selection →
# v3 portfolios → EAR → identity screen → risk report. Logs: logs/*.log; each step stops the chain on failure.
cd "$(dirname "$0")"
set -e
L=logs/postaudit2_chain.log
echo "start $(date)" > $L
step() { echo "== $1 $(date +%T)" >> $L; shift; "$@" >> $L 2>&1; }
step "run_final (truncation, determinism, backtest, gap ledger, eps_momentum)" ./run_final.sh
grep -q ALLDONE logs/backtest_run.log
step "test_fundamentals_pit" python3 test_fundamentals_pit.py
step "ml_features" python3 ml_features.py
step "ml_pipeline dev" python3 ml_pipeline.py dev
step "ml_pipeline holdout (re-run after bug fixes; disclosed)" python3 ml_pipeline.py holdout
step "sma200_overlay" python3 sma200_overlay.py
step "composite3" python3 composite3.py
step "mom30_roe" python3 mom30_roe.py
step "tech_only" python3 tech_only.py
rm -f results/explosive/panel_explosive.parquet
step "explosive_factors" python3 explosive_factors.py
step "explosive_v2" python3 explosive_v2.py
step "improve_v3" python3 improve_v3.py
step "earnings_factor" python3 earnings_factor.py
step "identity_screen_earnings" python3 identity_screen_earnings.py
step "risk_report" python3 risk_report.py
echo "CHAIN_DONE $(date)" >> $L
