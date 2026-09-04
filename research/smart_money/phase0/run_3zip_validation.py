"""
3-ZIP cross-era validation script.
Approved by Codex audit of commit 0eb12d3.

ZIPs: 2013q3.zip | 2023q1.zip | 01mar2026-31may2026.zip
DB:   data/13f_3zip_0eb12d3.db  (created fresh; never reuses existing data)

Run:
  export SEC_USER_AGENT="SmartMoneyResearch research@example.com"
  python run_3zip_validation.py
"""

import os, sys, sqlite3
from pathlib import Path
from datetime import datetime

os.environ.setdefault("SEC_USER_AGENT", "SmartMoneyResearch research@example.com")

# Point to fresh DB — NEVER use existing 13f.db
DB_NAME = "data/13f_3zip_0eb12d3.db"
os.environ["DB_PATH"] = str(Path(__file__).parent / DB_NAME)

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import SCHEMA, ingest_zip, apply_value_normalization, run_all_qa, get_db

ZIPS = [
    Path(__file__).parent / "data" / "zips" / "2013q3.zip",
    Path(__file__).parent / "data" / "zips" / "2023q1.zip",
    Path(__file__).parent / "data" / "zips" / "01mar2026-31may2026.zip",
]

def sep(title=""):
    print("\n" + "="*60 + (f" {title}" if title else ""))

def qa_per_zip(db, label):
    """Print per-ZIP QA numbers."""
    sep(f"QA: {label}")
    cur = db.execute("""
        SELECT
            COUNT(*) as filings,
            SUM(CASE WHEN cik='' OR cik IS NULL THEN 1 ELSE 0 END) as empty_cik,
            SUM(CASE WHEN period_of_report='' OR period_of_report IS NULL THEN 1 ELSE 0 END) as empty_period,
            SUM(CASE WHEN form_type='' OR form_type IS NULL THEN 1 ELSE 0 END) as empty_form,
            SUM(CASE WHEN amendment_type IS NOT NULL THEN 1 ELSE 0 END) as amendments,
            SUM(CASE WHEN amendment_type='RESTATEMENT' THEN 1 ELSE 0 END) as restatements,
            SUM(CASE WHEN amendment_type='ADD_NEW_HOLDINGS' THEN 1 ELSE 0 END) as adds,
            SUM(CASE WHEN amendment_type='UNKNOWN' THEN 1 ELSE 0 END) as unknown_amend,
            SUM(CASE WHEN acceptance_datetime IS NOT NULL THEN 1 ELSE 0 END) as has_accept_dt
        FROM filing_events
        WHERE ingest_zip=?
    """, (label,)).fetchone()

    li = db.execute("""
        SELECT
            COUNT(*) as lines,
            SUM(CASE WHEN value_usd IS NOT NULL THEN 1 ELSE 0 END) as has_value,
            SUM(CASE WHEN raw_value_reported IS NOT NULL THEN 1 ELSE 0 END) as has_raw,
            SUM(CASE WHEN security_name IS NOT NULL AND security_name!='' THEN 1 ELSE 0 END) as has_name,
            SUM(CASE WHEN cusip='' OR cusip IS NULL THEN 1 ELSE 0 END) as empty_cusip
        FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.ingest_zip=?
    """, (label,)).fetchone()

    print(f"  Filings:        {cur['filings']:>8,}")
    print(f"  Empty CIK:      {cur['empty_cik']:>8,}  ← must be 0")
    print(f"  Empty period:   {cur['empty_period']:>8,}  ← must be 0")
    print(f"  Empty form:     {cur['empty_form']:>8,}  ← must be 0")
    print(f"  Amendments:     {cur['amendments']:>8,}  (RESTATEMENT={cur['restatements']} ADD={cur['adds']} UNKNOWN={cur['unknown_amend']})")
    print(f"  Acceptance DT:  {cur['has_accept_dt']:>8,} / {cur['filings']} have acceptance_datetime")
    print(f"  Line items:     {li['lines']:>8,}")
    print(f"  With value_usd: {li['has_value']:>8,}  ← must be 0 before enrich (set after)")
    print(f"  With raw_value: {li['has_raw']:>8,}  ← must match line items")
    print(f"  With name:      {li['has_name']:>8,}  ← security_name coverage")
    print(f"  Empty CUSIP:    {li['empty_cusip']:>8,}  ← must be 0")

    # Amendment orphan check — all accession_numbers in line_items must exist in filing_events
    orphans = db.execute("""
        SELECT COUNT(*) FROM filing_line_items li
        LEFT JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.accession_number IS NULL
    """).fetchone()[0]
    print(f"  Orphan lines:   {orphans:>8,}  ← must be 0")

    return cur["filings"]


def qa_value_normalization(db):
    """Verify no regime mixing after apply_value_normalization."""
    sep("VALUE normalization cross-era check")

    # Pre-2023: acceptance < 2023-01-03
    old = db.execute("""
        SELECT COUNT(*) as n, AVG(CAST(li.value_usd AS REAL)/NULLIF(li.raw_value_reported,0)) as avg_mult
        FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.acceptance_datetime IS NOT NULL
          AND substr(fe.acceptance_datetime,1,10) < '2023-01-03'
          AND li.value_usd IS NOT NULL AND li.raw_value_reported IS NOT NULL
          AND li.raw_value_reported > 0
    """).fetchone()

    new = db.execute("""
        SELECT COUNT(*) as n, AVG(CAST(li.value_usd AS REAL)/NULLIF(li.raw_value_reported,0)) as avg_mult
        FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.acceptance_datetime IS NOT NULL
          AND substr(fe.acceptance_datetime,1,10) >= '2023-01-03'
          AND li.value_usd IS NOT NULL AND li.raw_value_reported IS NOT NULL
          AND li.raw_value_reported > 0
    """).fetchone()

    old_mult = round(old["avg_mult"], 1) if old["avg_mult"] else None
    new_mult = round(new["avg_mult"], 1) if new["avg_mult"] else None

    print(f"  Pre-2023 regime:  {old['n']:>8,} rows, avg multiplier={old_mult} (expected 1000.0)")
    print(f"  Post-2023 regime: {new['n']:>8,} rows, avg multiplier={new_mult} (expected 1.0)")

    ok_old = old_mult == 1000.0 if old_mult else None
    ok_new = new_mult == 1.0 if new_mult else None
    print(f"  Old regime:  {'PASS ✓' if ok_old else 'FAIL ✗' if ok_old is not None else 'SKIP (no data)'}")
    print(f"  New regime:  {'PASS ✓' if ok_new else 'FAIL ✗' if ok_new is not None else 'SKIP (no data)'}")


if __name__ == "__main__":
    db_path = Path(os.environ["DB_PATH"])
    if db_path.exists():
        print(f"ERROR: DB already exists at {db_path}. Delete it first or choose a different path.")
        sys.exit(1)

    sep("3-ZIP Cross-Era Validation")
    print(f"  Commit:  0eb12d3b3aa8cbddecf1382b968f18828261bed0")
    print(f"  DB:      {db_path}")
    print(f"  Started: {datetime.utcnow().isoformat()}Z")

    db = get_db()

    # ── INGEST ────────────────────────────────────────────────────────────────
    total_filings = 0
    total_lines   = 0
    for zp in ZIPS:
        label = zp.stem
        print(f"\nIngesting {zp.name} ...", flush=True)
        try:
            stats = ingest_zip(db, zp, label)
            total_filings += stats["filings"]
            total_lines   += stats["line_items"]
            print(f"  → {stats['filings']:,} filings  {stats['line_items']:,} lines")
        except Exception as e:
            db.rollback()
            print(f"  ERROR: {e} — rolled back")
            sys.exit(1)

    # ── PRE-ENRICH QA ─────────────────────────────────────────────────────────
    sep("Pre-enrich totals")
    print(f"  Total filings:    {total_filings:,}")
    print(f"  Total line items: {total_lines:,}")
    for zp in ZIPS:
        qa_per_zip(db, zp.stem)

    # ── NORMALIZATION (no network — acceptance_datetime needed first) ─────────
    # For this 3-ZIP test we apply normalization only to rows that already
    # have acceptance_datetime from SUBMISSION.tsv filing_date as proxy
    # (full acceptance_datetime requires enrich from submissions API — not running here)
    print("\nNOTE: Skipping SEC submissions API enrich (no network call in this validation).")
    print("Applying normalization on rows where acceptance_datetime already available...")
    apply_value_normalization(db)

    # ── POST-NORM QA ──────────────────────────────────────────────────────────
    qa_value_normalization(db)

    # ── FINAL SUMMARY ─────────────────────────────────────────────────────────
    sep("Final field-completeness summary (all 3 ZIPs combined)")
    total = db.execute("SELECT COUNT(*) FROM filing_line_items").fetchone()[0]
    fe_total = db.execute("SELECT COUNT(*) FROM filing_events").fetchone()[0]
    empty_cik = db.execute("SELECT COUNT(*) FROM filing_events WHERE cik='' OR cik IS NULL").fetchone()[0]
    empty_period = db.execute("SELECT COUNT(*) FROM filing_events WHERE period_of_report='' OR period_of_report IS NULL").fetchone()[0]
    amendments = db.execute("SELECT COUNT(*) FROM filing_events WHERE amendment_type IS NOT NULL").fetchone()[0]
    unknown_a = db.execute("SELECT COUNT(*) FROM filing_events WHERE amendment_type='UNKNOWN'").fetchone()[0]

    print(f"  Filing events:    {fe_total:>8,}")
    print(f"  Empty CIK:        {empty_cik:>8,}  {'PASS ✓' if empty_cik==0 else 'FAIL ✗'}")
    print(f"  Empty period:     {empty_period:>8,}  {'PASS ✓' if empty_period==0 else 'FAIL ✗'}")
    print(f"  Amendments:       {amendments:>8,}")
    print(f"  UNKNOWN amend:    {unknown_a:>8,}")
    print(f"  Line items:       {total:>8,}")

    orphans = db.execute("""
        SELECT COUNT(*) FROM filing_line_items li
        LEFT JOIN filing_events fe ON fe.accession_number=li.accession_number
        WHERE fe.accession_number IS NULL
    """).fetchone()[0]
    print(f"  Orphan lines:     {orphans:>8,}  {'PASS ✓' if orphans==0 else 'FAIL ✗'}")

    print(f"\n  Finished: {datetime.utcnow().isoformat()}Z")
    print(f"  DB size:  {db_path.stat().st_size / 1e6:.1f} MB")
    sep("DONE — freeze this output with commit SHA above")
