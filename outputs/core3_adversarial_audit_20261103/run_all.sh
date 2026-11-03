#!/bin/zsh
# run_all.sh — Reproduces the entire Core3 Clean-Room Adversarial Falsification Audit from scratch.
set -e
setopt null_glob
cd "$(dirname "$0")"

echo "[1/2] Running Core3 10-Point Adversarial Falsification Audit Suite..."
python3 run_core3_audit.py --rebuild

echo "[2/2] Building Auto-Generated Markdown Report Tables (REPORT_TABLES.md)..."
python3 build_report_tables.py

echo "=== CORE3 ADVERSARIAL AUDIT PIPELINE COMPLETE ==="
