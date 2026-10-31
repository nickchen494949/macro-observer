#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1

echo "=== [0/5] Baseline Integrity Snapshot ==="
python3 "$DIR/00_baseline_integrity_guard.py" snapshot

echo "=== [1/5] Equity Prices, Opens, Volumes, IVV, WIKI & Universes Audit ==="
python3 "$DIR/01_audit_equity_prices_and_universes.py"

echo "=== [2/5] SEC EDGAR PIT Fundamentals & Valuation Basis Audit ==="
python3 "$DIR/02_audit_sec_fundamentals.py"

echo "=== [3/5] Macro FRED/ALFRED, ETFs, Sector EPS, FOMC SEP, LSEG & 13F Audit ==="
python3 "$DIR/03_audit_macro_sector_13f_datasets.py"

echo "=== [4/5] All 347 Strategy Ledgers Independent Recomputation ==="
python3 "$DIR/04_audit_all_ledgers.py"

echo "=== [5/5] Fixed-Seed (seed=20261031) 100-Card Stratified Random Spot-Check ==="
python3 "$DIR/05_stratified_random_spotcheck.py"

echo "=== [VERIFY] Confirm Zero Bytes Modified in Protected Project Files ==="
python3 "$DIR/00_baseline_integrity_guard.py" verify
