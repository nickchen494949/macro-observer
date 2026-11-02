#!/usr/bin/env bash
# One-command reproduction of the Claude re-audit. Requires the gitignored raw data (see README.md).
# Optional: export MACRO_REPO_ROOT=/path/to/macro-observer   (defaults to two levels above this folder)
set -euo pipefail
cd "$(dirname "$0")"
python3 09_input_manifest.py
python3 01_indep_rebuild.py
python3 02_compare_vs_gemini.py
python3 03_mismatch_diagnosis.py
python3 04_ledger_math_and_big_months.py
python3 05_open_fallback_status.py
python3 06_family_multiple_testing.py
python3 07_spy_excess_regime.py
python3 08_nov2026_signal.py
echo "done -> results/"
