#!/bin/sh
# Post-audit-3 rerun (2026-10-29, external audit of e93da7c): per-feature fundamental availability (+ fundamentals
# truncation test), real 6-month tranche ledger and daily NAV, fail-fast chains. Every step must succeed (set -e);
# tests must print their PASS markers. Log: logs/postaudit3_chain.log
cd "$(dirname "$0")"
set -eu
L=logs/postaudit3_chain.log
echo "start $(date)" > $L
step() { echo "== $1 $(date +%T)" >> $L; shift; "$@" >> $L 2>&1; }
step "run_final (price + fundamentals truncation, determinism, unit tests, backtest, gap ledger, eps_momentum)" ./run_final.sh
grep -q ALLDONE logs/backtest_run.log
step "test_portfolio_ledger" python3 test_portfolio_ledger.py
step "ml_features" python3 ml_features.py
step "ml_pipeline dev (re-run after the 2026-10-29 fundamentals fix; disclosed)" python3 ml_pipeline.py dev
step "ml_pipeline holdout (re-run; disclosed)" python3 ml_pipeline.py holdout
step "sma200_overlay" python3 sma200_overlay.py
step "composite3" python3 composite3.py
step "mom30_roe" python3 mom30_roe.py
step "tech_only" python3 tech_only.py
rm -f results/explosive/panel_explosive.parquet
step "explosive_factors" python3 explosive_factors.py
step "explosive_v2" python3 explosive_v2.py
step "improve_v3" python3 improve_v3.py
step "earnings_factor" python3 earnings_factor.py
step "factor_screen build" python3 factor_screen.py build
step "factor_screen screen" python3 factor_screen.py screen
step "factor_combo" python3 factor_combo.py
step "winners_tracks" python3 winners_tracks.py
step "identity_screen_earnings" python3 identity_screen_earnings.py
step "risk_report" python3 risk_report.py
echo "CHAIN_DONE $(date)" >> $L
