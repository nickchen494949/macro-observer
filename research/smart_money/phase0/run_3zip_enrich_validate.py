"""
3-ZIP cross-era validation — v2 (with real acceptance enrichment).
Approved by Codex audit of commit 0eb12d3.

Phase 1 (raw ingest) already done — DB: data/13f_3zip_0eb12d3.db
Phase 2 (this script): enrich acceptance_datetime via SEC submissions.zip,
  normalize VALUE, verify cross-era multipliers with hard gates, run CH-1.

Rules:
- Does NOT re-ingest (DB already has 3-ZIP raw data)
- Downloads submissions.zip from SEC (~1GB, cached after first run)
- Hard gate: any check SKIP or FAIL → exits 1
- Normalization run twice: checksums must be identical
- CH-1 must PASS (not SKIP)

Run:
  export SEC_USER_AGENT="SmartMoneyResearch research@example.com"
  python run_3zip_enrich_validate.py
"""

import os, sys, sqlite3, hashlib
from pathlib import Path
from datetime import datetime

os.environ.setdefault("SEC_USER_AGENT", "SmartMoneyResearch research@example.com")

DB_NAME = "data/13f_3zip_0eb12d3.db"
os.environ["DB_PATH"] = str(Path(__file__).parent / DB_NAME)

sys.path.insert(0, str(Path(__file__).parent))
import pipeline as pl
from pipeline import enrich_acceptance_timestamps

FAILURES = []

def sep(title=""):
    print("\n" + "=" * 60 + (f" {title}" if title else ""))

def gate(name, cond, detail):
    """Hard gate — records failure but continues to collect all results."""
    mark = "PASS ✓" if cond else "FAIL ✗"
    print(f"  [{mark}] {name}: {detail}")
    if not cond:
        FAILURES.append(f"{name}: {detail}")
    return cond

def require_not_skip(name, status, detail):
    """Treat SKIP as failure — cross-era fixture must have both regimes."""
    if status == "SKIP":
        FAILURES.append(f"{name}: SKIP — {detail}")
        print(f"  [FAIL ✗] {name}: SKIP — {detail}")
        return False
    if status == "PASS":
        print(f"  [PASS ✓] {name}: {detail}")
        return True
    FAILURES.append(f"{name}: {status} — {detail}")
    print(f"  [FAIL ✗] {name}: {status} — {detail}")
    return False


if __name__ == "__main__":
    db_path = Path(os.environ["DB_PATH"])
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}")
        print("Run the raw ingest first: python run_3zip_validation.py")
        sys.exit(1)

    sep("3-ZIP Cross-Era Validation — Phase 2: Enrich + Verify")
    print(f"  Commit:  0eb12d3b3aa8cbddecf1382b968f18828261bed0")
    print(f"  DB:      {db_path}  ({db_path.stat().st_size/1e6:.0f} MB)")
    print(f"  Started: {datetime.utcnow().isoformat()}Z")

    db = pl.get_db()

    # ── BASELINE: confirm raw ingest ──────────────────────────────────────────
    sep("Baseline (raw ingest counts)")
    fe = db.execute("SELECT COUNT(*) FROM filing_events").fetchone()[0]
    li = db.execute("SELECT COUNT(*) FROM filing_line_items").fetchone()[0]
    empty_cik = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE cik='' OR cik IS NULL"
    ).fetchone()[0]
    accept_before = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE acceptance_datetime IS NOT NULL"
    ).fetchone()[0]

    print(f"  Filing events:      {fe:>8,}")
    print(f"  Line items:         {li:>8,}")
    gate("baseline-empty-cik", empty_cik == 0, f"empty_cik={empty_cik}")
    print(f"  acceptance_datetime before enrich: {accept_before:,} / {fe:,}")

    # ── ENRICH: real acceptanceDateTime from SEC per-CIK submissions API ──────
    sep("Enriching acceptance_datetime from SEC EDGAR submissions API")
    unique_ciks = db.execute(
        "SELECT COUNT(DISTINCT cik) FROM filing_events WHERE acceptance_datetime IS NULL"
    ).fetchone()[0]
    print(f"  Unique CIKs to fetch: {unique_ciks:,}")
    print(f"  Estimated time: ~{unique_ciks * 0.12 / 60:.0f} min at 10 req/sec")
    print(f"  (per-CIK API: https://data.sec.gov/submissions/CIK{{cik}}.json)")

    enrich_acceptance_timestamps(db)

    accept_after = db.execute(
        "SELECT COUNT(*) FROM filing_events WHERE acceptance_datetime IS NOT NULL"
    ).fetchone()[0]
    coverage = accept_after / fe if fe else 0
    print(f"\n  acceptance_datetime after enrich: {accept_after:,} / {fe:,} = {coverage:.1%}")
    gate("enrich-coverage-95pct", coverage >= 0.95,
         f"coverage={coverage:.1%} (must be >=95%)")


    # ── NORMALIZATION: run twice, compare checksums ────────────────────────────
    sep("VALUE normalization — run 1")
    pl.apply_value_normalization(db)
    value_after_1 = db.execute(
        "SELECT COUNT(*) FROM filing_line_items WHERE value_usd IS NOT NULL"
    ).fetchone()[0]
    print(f"  value_usd non-null after run 1: {value_after_1:,}")

    # Checksum of all (accession_number, line_seq, value_usd) after run 1
    rows1 = db.execute(
        "SELECT accession_number, line_seq, value_usd FROM filing_line_items ORDER BY accession_number, line_seq"
    ).fetchall()
    cksum1 = hashlib.md5(str(rows1).encode()).hexdigest()
    print(f"  Checksum run 1: {cksum1}")

    sep("VALUE normalization — run 2 (idempotency check)")
    pl.apply_value_normalization(db)
    rows2 = db.execute(
        "SELECT accession_number, line_seq, value_usd FROM filing_line_items ORDER BY accession_number, line_seq"
    ).fetchall()
    cksum2 = hashlib.md5(str(rows2).encode()).hexdigest()
    print(f"  Checksum run 2: {cksum2}")
    gate("normalization-idempotent", cksum1 == cksum2,
         f"run1={cksum1[:8]} run2={cksum2[:8]} (must be identical)")

    # ── REGIME VERIFICATION: count violating rows = 0 ─────────────────────────
    sep("Cross-era regime verification")

    # Old regime: acceptance < 2023-01-03 → value_usd must equal raw * 1000 exactly
    old_total = db.execute("""
        SELECT COUNT(*) FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.acceptance_datetime IS NOT NULL
          AND substr(fe.acceptance_datetime,1,10) < '2023-01-03'
          AND li.raw_value_reported IS NOT NULL AND li.value_usd IS NOT NULL
    """).fetchone()[0]

    old_wrong = db.execute("""
        SELECT COUNT(*) FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.acceptance_datetime IS NOT NULL
          AND substr(fe.acceptance_datetime,1,10) < '2023-01-03'
          AND li.raw_value_reported IS NOT NULL AND li.value_usd IS NOT NULL
          AND li.value_usd != li.raw_value_reported * 1000
    """).fetchone()[0]

    # New regime: acceptance >= 2023-01-03 → value_usd must equal raw exactly
    new_total = db.execute("""
        SELECT COUNT(*) FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.acceptance_datetime IS NOT NULL
          AND substr(fe.acceptance_datetime,1,10) >= '2023-01-03'
          AND li.raw_value_reported IS NOT NULL AND li.value_usd IS NOT NULL
    """).fetchone()[0]

    new_wrong = db.execute("""
        SELECT COUNT(*) FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.acceptance_datetime IS NOT NULL
          AND substr(fe.acceptance_datetime,1,10) >= '2023-01-03'
          AND li.raw_value_reported IS NOT NULL AND li.value_usd IS NOT NULL
          AND li.value_usd != li.raw_value_reported
    """).fetchone()[0]

    print(f"  Pre-2023  regime rows:  {old_total:>8,}  violation rows: {old_wrong}")
    print(f"  Post-2023 regime rows:  {new_total:>8,}  violation rows: {new_wrong}")

    # Both regimes must have data — SKIP = FAIL for cross-era fixture
    if old_total == 0:
        FAILURES.append("regime-old-has-data: 0 rows in pre-2023 regime — enrichment insufficient")
        print("  [FAIL ✗] regime-old-has-data: 0 rows (SKIP treated as FAIL)")
    else:
        gate("regime-old-violations-zero", old_wrong == 0,
             f"{old_wrong} rows with value_usd != raw*1000 in pre-2023 regime")

    if new_total == 0:
        FAILURES.append("regime-new-has-data: 0 rows in post-2023 regime — enrichment insufficient")
        print("  [FAIL ✗] regime-new-has-data: 0 rows (SKIP treated as FAIL)")
    else:
        gate("regime-new-violations-zero", new_wrong == 0,
             f"{new_wrong} rows with value_usd != raw in post-2023 regime")

    # ── CH-1: must PASS (not SKIP) ────────────────────────────────────────────
    sep("CH-1 Berkshire reconciliation (must PASS, not SKIP)")
    ch1_results = []
    pl.check_ch1(db, lambda c, s, d: ch1_results.append((c, s, d)))
    if ch1_results:
        c, s, d = ch1_results[0]
        require_not_skip("CH-1", s, d)
    else:
        FAILURES.append("CH-1: no result returned")
        print("  [FAIL ✗] CH-1: no result returned")

    # ── ORPHAN CHECK ──────────────────────────────────────────────────────────
    sep("Orphan line items")
    orphans = db.execute("""
        SELECT COUNT(*) FROM filing_line_items li
        LEFT JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.accession_number IS NULL
    """).fetchone()[0]
    gate("no-orphan-lines", orphans == 0, f"orphan_lines={orphans}")

    # ── FIELD COMPLETENESS ────────────────────────────────────────────────────
    sep("Field completeness (combined 3-ZIP)")
    for col, label, threshold in [
        ("cik", "empty-cik", 0),
        ("period_of_report", "empty-period", 0),
    ]:
        n_empty = db.execute(
            f"SELECT COUNT(*) FROM filing_events WHERE {col}='' OR {col} IS NULL"
        ).fetchone()[0]
        gate(label, n_empty == threshold, f"empty_{col}={n_empty}")

    # ── AMENDMENT DISTRIBUTION ────────────────────────────────────────────────
    sep("Amendment distribution")
    for zip_label in ["2013q3", "2023q1", "01mar2026-31may2026"]:
        r = db.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN amendment_type='RESTATEMENT' THEN 1 ELSE 0 END) as restate,
                SUM(CASE WHEN amendment_type='ADD_NEW_HOLDINGS' THEN 1 ELSE 0 END) as add_new,
                SUM(CASE WHEN amendment_type='UNKNOWN' THEN 1 ELSE 0 END) as unknown_a
            FROM filing_events WHERE ingest_zip=?
        """, (zip_label,)).fetchone()
        print(f"  {zip_label}: total={r['total']:,} RESTATEMENT={r['restate']} ADD={r['add_new']} UNKNOWN={r['unknown_a']}")

    # ── FINAL VERDICT ─────────────────────────────────────────────────────────
    sep("FINAL VERDICT")
    print(f"  Finished: {datetime.utcnow().isoformat()}Z")
    print(f"  DB size:  {db_path.stat().st_size/1e6:.0f} MB")

    if FAILURES:
        print(f"\n  BLOCK — {len(FAILURES)} gate(s) failed:")
        for f in FAILURES:
            print(f"    ✗ {f}")
        sys.exit(1)
    else:
        print(f"\n  PASS — all gates passed. Ready for Codex cross-era audit.")
        sys.exit(0)
