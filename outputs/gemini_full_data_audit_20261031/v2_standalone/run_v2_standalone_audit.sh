#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
cd "$REPO_ROOT"

echo "=== [1/7] Pre-Flight Clean-Room AST, Forbidden-Cost-Read & Read-Only Guard (v2_00) ==="
python3 "$HERE/v2_00_cleanroom_ast_and_readonly_guard.py"

echo "=== [2/7] Clean-Room 100% First-Principles Standalone Audit of ALL 347 Strategy Ledgers (v2_01) ==="
python3 "$HERE/v2_01_standalone_all_347_ledgers_auditor.py"

echo "=== [3/7] Clean-Room 100 Random SEC Raw XBRL Non-Null Fact & Live data.sec.gov Checks (v2_02) ==="
python3 "$HERE/v2_02_sec_xbrl_100_random_facts_auditor.py"

echo "=== [4/7] Clean-Room Two-Stage Unrestricted 200 Cards + 300-Card Master Audit (v2_03) ==="
python3 "$HERE/v2_03_twostage_unrestricted_200_cards_auditor.py"

echo "=== [5/7] Clean-Room 100 Random SEC Fundamental NULL / Missing Completeness Audit (v2_04) ==="
python3 "$HERE/v2_04_sec_xbrl_100_null_completeness_auditor.py"

echo "=== [6/7] Clean-Room Full-Chain End-to-End PIT Strategy Signal, Model & Pick Reconstruction (v2_05) ==="
python3 "$HERE/v2_05_full_chain_pit_strategy_reconstructor.py"

echo "=== [7/7] Post-Flight Clean-Room AST & 10,964-File Read-Only Baseline Verification (v2_00) ==="
python3 "$HERE/v2_00_cleanroom_ast_and_readonly_guard.py"

echo "=== ALL CLEAN-ROOM STANDALONE FINAL SIGN-OFF AUDITS COMPLETED SUCCESSFULLY ==="
