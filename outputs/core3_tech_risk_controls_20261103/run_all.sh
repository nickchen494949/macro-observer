#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "[1/2] Running Core3 Technical Risk Controls Audit (Cash = 0% Return)..."
python3 run_tech_brakes_audit.py

echo "[2/2] Generating Markdown Report Tables..."
python3 build_tech_brakes_report.py

echo "=== CORE3 TECHNICAL RISK CONTROLS AUDIT COMPLETE ==="
