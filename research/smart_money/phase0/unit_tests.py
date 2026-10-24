"""
Local Unit Tests — Phase 0 Pipeline v1.5
Run: python unit_tests.py
All must PASS before any corpus work.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pipeline import (
    normalize_value,
    classify_asset,
    compute_censor_flag,
    detect_amendment_type,
    compute_13f_deadline,
    VALUE_REGIME_CUTOFF,
)
from qa_support import deduplicate_economic_holdings, security_name_similarity

PASS = 0
FAIL = 0

def check(name, got, expected):
    global PASS, FAIL
    if got == expected:
        print(f"  ✅ PASS  {name}")
        PASS += 1
    else:
        print(f"  ❌ FAIL  {name}")
        print(f"           got:      {got!r}")
        print(f"           expected: {expected!r}")
        FAIL += 1

print("\n── VALUE Normalization ──────────────────────────────────────────")
# Old regime: filed before 2023-01-03 → ×1000
check("old regime 2022-11-14",
      normalize_value(1000, "2022-11-14T10:00:00"),
      1_000_000)
check("old regime 2022-12-31 (last day)",
      normalize_value(1000, "2022-12-31T23:59:59"),
      1_000_000)
# New regime: filed on/after 2023-01-03 → ×1
check("new regime 2023-01-03 (cutover day)",
      normalize_value(1000, "2023-01-03T09:00:00"),
      1_000)
check("new regime 2023-02-14 (Berkshire Q4 2022 filing)",
      normalize_value(1000, "2023-02-14T16:02:18"),
      1_000)
check("new regime 2024-01-01",
      normalize_value(1000, "2024-01-01T00:00:00"),
      1_000)
# Edge cases
check("None value → None",
      normalize_value(None, "2022-01-01"),
      None)
check("None acceptance_dt → None",
      normalize_value(1000, None),
      None)

print("\n── Asset Classification ─────────────────────────────────────────")
check("cash equity (SH, no put_call)",
      classify_asset(None, "SH"),
      "cash_equity")
check("cash equity (empty string put_call)",
      classify_asset("", "SH"),
      "cash_equity")
check("call option",
      classify_asset("CALL", "SH"),
      "call_option")
check("put option",
      classify_asset("PUT", "SH"),
      "put_option")
check("mixed-case call option",
      classify_asset("Call", "SH"),
      "call_option")
check("mixed-case put option",
      classify_asset("Put", "SH"),
      "put_option")
check("bond (PRN, no put_call)",
      classify_asset(None, "PRN"),
      "bond")
check("bond (PRN, with CALL — unusual but classify as bond by PRN first? → put_call wins)",
      classify_asset("CALL", "PRN"),
      "call_option")

print("\n── De Minimis Censor Flag ───────────────────────────────────────")
# New position, large → NORMAL
check("new large position → NORMAL",
      compute_censor_flag(5_000_000, 50_000_000, None, None),
      "NORMAL")
# New position, near threshold → LOW_CONFIDENCE_NEW
check("new near threshold (8k shares) → LOW_CONFIDENCE_NEW",
      compute_censor_flag(8_000, 150_000, None, None),
      "LOW_CONFIDENCE_NEW")
# Exit from large position → NORMAL
check("clean exit from large position → NORMAL",
      compute_censor_flag(0, 0, 5_000_000, 50_000_000),
      "NORMAL")
# Exit from near-threshold position → LOW_CONFIDENCE_EXIT
check("exit from near-threshold (9k shares) → LOW_CONFIDENCE_EXIT",
      compute_censor_flag(0, 0, 9_000, 170_000),
      "LOW_CONFIDENCE_EXIT")
# Ongoing large position → NORMAL
check("ongoing large → NORMAL",
      compute_censor_flag(1_000_000, 10_000_000, 900_000, 9_000_000),
      "NORMAL")

print("\n── Amendment Type Detection ─────────────────────────────────────")
# Original filing (no /A suffix)
check("original 13F-HR → None",
      detect_amendment_type({"FORMTYPE": "13F-HR", "AMENDMENTTYPE": ""}),
      None)
# Restatement
check("13F-HR/A RESTATEMENT → RESTATEMENT",
      detect_amendment_type({"FORMTYPE": "13F-HR/A", "AMENDMENTTYPE": "RESTATEMENT"}),
      "RESTATEMENT")
# Add new holdings (Berkshire Chubb case)
check("13F-HR/A NEW HOLDINGS ENTRIES → ADD_NEW_HOLDINGS",
      detect_amendment_type({"FORMTYPE": "13F-HR/A", "AMENDMENTTYPE": "NEW HOLDINGS ENTRIES"}),
      "ADD_NEW_HOLDINGS")
check("13F-HR/A ADDS NEW → ADD_NEW_HOLDINGS",
      detect_amendment_type({"FORMTYPE": "13F-HR/A", "AMENDMENTTYPE": "ADDS NEW"}),
      "ADD_NEW_HOLDINGS")

print("\n── Deadline Calendar ────────────────────────────────────────────")
# Core case from SEC FAQ
check("Q4 2025 → 2026-02-17 (Sat Feb14 + Presidents Day Feb16)",
      compute_13f_deadline("2025-12-31"),
      "2026-02-17")
# Q1 2025: 45th day = 2025-05-15 (Thu — no holiday)
check("Q1 2025 → 2025-05-15",
      compute_13f_deadline("2025-03-31"),
      "2025-05-15")
# Q2 2025: 45th day = 2025-08-14 (Thu)
check("Q2 2025 → 2025-08-14",
      compute_13f_deadline("2025-06-30"),
      "2025-08-14")

print("\n── Entity Dedup / Mapping QA Helpers ────────────────────────────")
base = {
    "reporter_cik": "1", "cusip": "037833100", "asset_class": "cash_equity",
    "put_call": None, "sshprnamt": 100, "value_usd": 10_000,
    "voting_sole": 100, "voting_shared": 0, "voting_none": 0,
}
same_economic_position = dict(base, reporter_cik="2")
different_position_same_cusip = dict(base, reporter_cik="3", sshprnamt=200, value_usd=20_000)
unique, duplicates = deduplicate_economic_holdings(
    [base, same_economic_position, different_position_same_cusip]
)
check("exact shared position removed once", len(duplicates), 1)
check("different amount on same CUSIP preserved", len(unique), 2)
check("dedup is idempotent", len(deduplicate_economic_holdings(unique)[1]), 0)
check("issuer-name verification: Apple",
      security_name_similarity("APPLE INC", "APPLE INC") >= 0.90,
      True)
check("issuer-name verification rejects unrelated names",
      security_name_similarity("APPLE INC", "MICROSOFT CORP") < 0.35,
      True)

print(f"\n{'='*60}")
total = PASS + FAIL
print(f"Results: {PASS}/{total} PASS  |  {FAIL} FAIL")
if FAIL == 0:
    print("✅ ALL TESTS PASS — pipeline logic verified")
else:
    print("❌ FAILURES DETECTED — fix before corpus ingest")
    sys.exit(1)
