"""
Integration tests for Phase 0 pipeline — v2.
Designed to CATCH bugs that existed in f351e52 and earlier.

Rules:
- Uses a real SEC ZIP (2013q3.zip must be in data/zips/)
- Uses a fresh temporary database (never reuses existing DB)
- Each test is an independent regression guard
- Old bug → test FAILS; fixed code → test PASSES
- Run: python integration_tests.py
"""

import os
import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

# Must set SEC_USER_AGENT before importing pipeline
os.environ.setdefault("SEC_USER_AGENT", "IntegrationTest test@test.com")

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import (
    SCHEMA, ingest_zip, reconstruct_state, classify_asset,
    compute_13f_deadline, detect_amendment_type,
    normalize_value, VALUE_REGIME_CUTOFF,
)

ZIP_PATH = Path(__file__).parent / "data" / "zips" / "2013q3.zip"
RESULTS = []

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    RESULTS.append((name, status, detail))
    mark = "✓" if cond else "✗"
    print(f"  [{mark}] {name}: {detail}")
    return cond

def fresh_db() -> sqlite3.Connection:
    """Return a new in-memory database with schema applied."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    db.commit()
    return db


# ─── GROUP 1: Real ZIP ingest basics ─────────────────────────────────────────

def test_real_zip_ingest():
    """Regression: CIK/period/form_type must NOT be empty after ingest (was broken in f351e52)."""
    print("\n[GROUP 1] Real ZIP ingest")
    if not ZIP_PATH.exists():
        check("G1-skip", False, f"ZIP not found: {ZIP_PATH}")
        return

    db = fresh_db()
    stats = ingest_zip(db, ZIP_PATH, "2013q3")

    check("G1-filing-count",    stats["filings"] > 5000, f"filings={stats['filings']}")
    check("G1-lineitem-count",  stats["line_items"] > 1_000_000, f"line_items={stats['line_items']}")

    empty_cik = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE cik='' OR cik IS NULL"
    ).fetchone()[0]
    check("G1-cik-populated",  empty_cik == 0, f"empty CIK={empty_cik}")

    empty_period = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE period_of_report='' OR period_of_report IS NULL"
    ).fetchone()[0]
    check("G1-period-populated", empty_period == 0, f"empty period={empty_period}")

    empty_form = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE form_type='' OR form_type IS NULL"
    ).fetchone()[0]
    check("G1-formtype-populated", empty_form == 0, f"empty form_type={empty_form}")

    amendments = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE amendment_type IS NOT NULL"
    ).fetchone()[0]
    check("G1-amendments-present", amendments > 0, f"amendments={amendments}")

    db.close()


# ─── GROUP 2: UPSERT — stale rows MUST be updated ────────────────────────────

def test_upsert_overwrites_stale():
    """Regression: INSERT OR IGNORE silently kept stale empty CIK (P0 in audit)."""
    print("\n[GROUP 2] UPSERT overwrites stale rows")
    if not ZIP_PATH.exists():
        check("G2-skip", False, "ZIP not found"); return

    db = fresh_db()

    # Pre-populate with WRONG data (simulates old broken pipeline)
    db.execute("""
        INSERT INTO filing_events
        (accession_number, cik, period_of_report, form_type, ingest_zip, ingest_ts)
        VALUES ('0001062993-13-003701', '', '', '', 'BROKEN', '2000-01-01')
    """)
    db.commit()

    # Now re-ingest with correct pipeline
    ingest_zip(db, ZIP_PATH, "2013q3")

    row = db.execute(
        "SELECT cik, period_of_report FROM filing_events WHERE accession_number='0001062993-13-003701'"
    ).fetchone()

    check("G2-cik-updated",    row and row["cik"] != "", f"cik='{row['cik'] if row else None}'")
    check("G2-period-updated", row and row["period_of_report"] != "",
          f"period='{row['period_of_report'] if row else None}'")
    db.close()


# ─── GROUP 3: VALUE normalization is idempotent ───────────────────────────────

def test_value_normalization_idempotent():
    """Regression: value_usd * 1000 in-place caused double-multiplication (P0 in audit)."""
    print("\n[GROUP 3] VALUE normalization idempotency")

    # Simulate: old-regime filing (accepted 2015-05-15 → should be ×1000)
    try:
        from run_phase0 import apply_value_normalization
    except ImportError:
        check("G3-import", False, "cannot import run_phase0"); return

    db = fresh_db()
    db.execute("""
        INSERT INTO filing_events
        (accession_number, cik, period_of_report, filing_date, form_type,
         acceptance_datetime, ingest_zip, ingest_ts)
        VALUES ('TESTOLD001','12345','2015-03-31','2015-05-15','13F-HR',
                '2015-05-15T10:00:00','test','2026')
    """)
    db.execute("""
        INSERT INTO filing_line_items
        (accession_number, line_seq, cusip, raw_value_reported, sshprnamt, asset_class)
        VALUES ('TESTOLD001', 0, 'TESTCUSIP', 123, 1000, 'cash_equity')
    """)
    db.commit()

    apply_value_normalization(db)
    v1 = db.execute(
        "SELECT value_usd FROM filing_line_items WHERE accession_number='TESTOLD001'"
    ).fetchone()["value_usd"]

    # Run again — must produce IDENTICAL result
    apply_value_normalization(db)
    v2 = db.execute(
        "SELECT value_usd FROM filing_line_items WHERE accession_number='TESTOLD001'"
    ).fetchone()["value_usd"]

    check("G3-first-run",    v1 == 123_000, f"run1 value_usd={v1} (expected 123000)")
    check("G3-second-run",   v2 == 123_000, f"run2 value_usd={v2} (expected 123000, would be 123M if broken)")
    check("G3-idempotent",   v1 == v2,      f"run1={v1} run2={v2}")
    db.close()


# ─── GROUP 4: reconstruct_state sums duplicate CUSIP rows ────────────────────

def test_reconstruct_sums_rows():
    """Regression: dict overwrite meant 100+200 shares returned 200 (P1 in audit)."""
    print("\n[GROUP 4] reconstruct_state SUM aggregation")

    db = fresh_db()
    db.execute("""
        INSERT INTO filing_events
        (accession_number, cik, period_of_report, filing_date, form_type,
         acceptance_datetime, ingest_zip, ingest_ts)
        VALUES ('TESTSUM001','99999','2020-12-31','2021-02-10','13F-HR',
                '2021-02-10T10:00:00','test','2026')
    """)
    # Two rows: same CUSIP + SOLE discretion → should SUM to 300 shares
    db.execute("""
        INSERT INTO filing_line_items
        (accession_number, line_seq, cusip, raw_value_reported, value_usd,
         sshprnamt, sshprnamttype, investment_discretion, asset_class)
        VALUES ('TESTSUM001', 0, 'AAPLTEST1', 100, 100000, 100, 'SH', 'SOLE', 'cash_equity')
    """)
    db.execute("""
        INSERT INTO filing_line_items
        (accession_number, line_seq, cusip, raw_value_reported, value_usd,
         sshprnamt, sshprnamttype, investment_discretion, asset_class)
        VALUES ('TESTSUM001', 1, 'AAPLTEST1', 200, 200000, 200, 'SH', 'SOLE', 'cash_equity')
    """)
    db.commit()

    state = reconstruct_state(db, "99999", "2020-12-31", "2021-02-11T00:00:00")
    total_shares = sum(r["sshprnamt"] for r in state if r["cusip"] == "AAPLTEST1")

    check("G4-sum-not-overwrite", total_shares == 300,
          f"AAPLTEST1 shares={total_shares} (expected 300, broken code gives 200)")
    db.close()


# ─── GROUP 5: CH-1 catches $299T magnitude error ─────────────────────────────

def test_ch1_catches_dollar_magnitude():
    """Regression: CH-1 passed even when value_usd was ~$299T (P1 in audit)."""
    print("\n[GROUP 5] CH-1 magnitude sanity")
    from pipeline import check_ch1

    results = []
    def record(chk, status, detail):
        results.append((chk, status, detail))

    db = fresh_db()
    # Insert Berkshire 2022Q4 with wrong ~$299T value (simulates double ×1000)
    db.execute("""
        INSERT INTO filing_events
        (accession_number, cik, period_of_report, filing_date, form_type,
         acceptance_datetime, ingest_zip, ingest_ts)
        VALUES ('0000950123-23-002585','1067983','2022-12-31','2023-02-14','13F-HR',
                '2023-02-14T16:00:00','test','2026')
    """)
    db.execute("""
        INSERT INTO filing_line_items
        (accession_number, line_seq, cusip, raw_value_reported, value_usd,
         sshprnamt, asset_class)
        VALUES ('0000950123-23-002585', 0, 'TESTCUSIP', 299000000000, 299000000000000, 1, 'cash_equity')
    """)  # value_usd = $299T (broken double multiplication)
    db.commit()

    check_ch1(db, record)
    ch1_status = results[0][1] if results else "NO_RESULT"
    check("G5-ch1-fails-on-299T", ch1_status == "FAIL",
          f"CH-1 status={ch1_status} (must FAIL on $299T, not PASS)")

    # Now with correct $299B
    db.execute("""
        UPDATE filing_line_items SET value_usd=299000000000
        WHERE accession_number='0000950123-23-002585'
    """)
    db.commit()
    results2 = []
    check_ch1(db, lambda c,s,d: results2.append((c,s,d)))
    ch1_status2 = results2[0][1] if results2 else "NO_RESULT"
    check("G5-ch1-passes-on-299B", ch1_status2 == "PASS",
          f"CH-1 status={ch1_status2} (must PASS on $299B)")
    db.close()


# ─── GROUP 6: INFOTABLE and SUMMARYPAGE fields populated ─────────────────────

def test_infotable_fields_populated():
    """Regression: security_name, title_of_class, voting fields were all NULL (P1 in audit)."""
    print("\n[GROUP 6] INFOTABLE/SUMMARYPAGE fields populated")
    if not ZIP_PATH.exists():
        check("G6-skip", False, "ZIP not found"); return

    db = fresh_db()
    ingest_zip(db, ZIP_PATH, "2013q3")

    total = db.execute("SELECT COUNT(*) FROM filing_line_items").fetchone()[0]
    with_name = db.execute(
        "SELECT COUNT(*) FROM filing_line_items WHERE security_name IS NOT NULL AND security_name != ''"
    ).fetchone()[0]
    with_title = db.execute(
        "SELECT COUNT(*) FROM filing_line_items WHERE title_of_class IS NOT NULL AND title_of_class != ''"
    ).fetchone()[0]
    with_voting = db.execute(
        "SELECT COUNT(*) FROM filing_line_items WHERE voting_sole IS NOT NULL"
    ).fetchone()[0]
    with_tvt = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE table_value_total IS NOT NULL"
    ).fetchone()[0]

    check("G6-security-name",   with_name  / total > 0.9,  f"{with_name}/{total} have security_name")
    check("G6-title-of-class",  with_title / total > 0.9,  f"{with_title}/{total} have title_of_class")
    check("G6-voting-sole",     with_voting/ total > 0.9,  f"{with_voting}/{total} have voting_sole")
    # 13F-NT filings do not have SUMMARYPAGE by SEC design — measure only HR filers
    hr_total = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE form_type IN ('13F-HR','13F-HR/A')"
    ).fetchone()[0]
    hr_with_tvt = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE form_type IN ('13F-HR','13F-HR/A') AND table_value_total IS NOT NULL"
    ).fetchone()[0]
    check("G6-table-value-total", hr_with_tvt / hr_total > 0.99,
          f"{hr_with_tvt}/{hr_total} 13F-HR filings have table_value_total (13F-NT excluded: no SUMMARYPAGE by SEC design)")
    db.close()


# ─── GROUP 7: Holiday calendar covers 2013-2026 ──────────────────────────────

def test_holiday_calendar():
    """Regression: calendar was 2024-2026 only; 2020Q4 gave wrong deadline."""
    print("\n[GROUP 7] Holiday calendar 2013-2026")
    from pipeline import SEC_HOLIDAYS
    from datetime import date

    years = {d.year for d in SEC_HOLIDAYS}
    check("G7-covers-2013", 2013 in years, f"years covered: {sorted(years)}")
    check("G7-covers-2026", 2026 in years, f"max year={max(years)}")

    # Known deadline: 2020Q4 (period 2020-12-31)
    # 45th day = 2021-02-14 (Sun) → 2021-02-15 (Presidents' Day) → 2021-02-16 (Tue)
    dl_2020q4 = compute_13f_deadline("2020-12-31")
    check("G7-2020q4-deadline", dl_2020q4 == "2021-02-16",
          f"2020Q4 deadline={dl_2020q4} (expected 2021-02-16)")

    # Known deadline: 2025Q4 (period 2025-12-31)
    # 45th day = 2026-02-14 (Sat) → 2026-02-16 (Presidents' Day) → 2026-02-17
    dl_2025q4 = compute_13f_deadline("2025-12-31")
    check("G7-2025q4-deadline", dl_2025q4 == "2026-02-17",
          f"2025Q4 deadline={dl_2025q4} (expected 2026-02-17, CH-11)")


# ─── GROUP 8: SEC_USER_AGENT from env ────────────────────────────────────────

def test_user_agent_from_env():
    """Regression: hardcoded User-Agent ignored SEC_USER_AGENT env var."""
    print("\n[GROUP 8] SEC_USER_AGENT env var")
    import pipeline
    check("G8-user-agent-is-env",
          os.environ.get("SEC_USER_AGENT", "") in pipeline.HEADERS.get("User-Agent", ""),
          f"HEADERS={pipeline.HEADERS}")


# ─── GROUP 9: Unknown amendment type quarantined ─────────────────────────────

def test_unknown_amendment_quarantined():
    """Regression: blank AMENDMENTTYPE on /A was silently promoted to RESTATEMENT."""
    print("\n[GROUP 9] Unknown amendment quarantine")
    fake_cp_row = {"AMENDMENTTYPE": ""}
    result = detect_amendment_type({"FORMTYPE": "13F-HR/A", "AMENDMENTTYPE": ""})
    check("G9-unknown-quarantined", result == "UNKNOWN",
          f"detect_amendment_type returned '{result}' (expected UNKNOWN, old code gave RESTATEMENT)")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 0 Integration Tests — v2")
    print("Designed to catch bugs present in commit f351e52")
    print("=" * 60)

    test_real_zip_ingest()
    test_upsert_overwrites_stale()
    test_value_normalization_idempotent()
    test_reconstruct_sums_rows()
    test_ch1_catches_dollar_magnitude()
    test_infotable_fields_populated()
    test_holiday_calendar()
    test_user_agent_from_env()
    test_unknown_amendment_quarantined()

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"RESULTS: {passed} PASS / {failed} FAIL / {len(RESULTS)} total")
    if failed:
        print("\nFAILED:")
        for name, status, detail in RESULTS:
            if status == "FAIL":
                print(f"  FAIL  {name}: {detail}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
