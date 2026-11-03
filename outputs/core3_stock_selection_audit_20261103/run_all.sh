#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "[1/3] Building PIT Stock-Selection Panels & Running Truncation Test..."
python3 build_selection_panels.py

echo "[2/3] Running Adversarial Audit of Isolated Stock-Selection Hypotheses (A, B, C, D)..."
python3 run_selection_hypotheses_audit.py

echo "[3/3] Generating Markdown Report Tables..."
python3 build_selection_report.py

echo "=== CORE3 STOCK-SELECTION HYPOTHESES AUDIT COMPLETE ==="
