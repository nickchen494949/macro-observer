"""
Resume script: repair asset_class + QA on existing fully-normalized DB.
Normalization already done — skip it. Only fix the options misclassification.

Usage:
  export DB_PATH="data/13f_full_4409f14.db"
  export SEC_USER_AGENT="Your Name your@email.com"
  python resume_normalize_qa.py
"""
import os, sys, sqlite3, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s")

from pipeline import get_db, run_all_qa, _safe_wal_checkpoint

if __name__ == "__main__":
    db_path = Path(os.environ.get("DB_PATH", "data/13f.db"))
    print(f"\n{'='*60}")
    print(f"RESUME: Asset class repair + QA")
    print(f"{'='*60}")
    print(f"  DB:      {db_path}  ({db_path.stat().st_size/1e9:.1f} GB)")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"  Disk:    ", end="", flush=True)
    os.system("df -h . | tail -1")

    db = get_db()

    # ── Step 1: Verify normalization already done ──────────────────────────
    val_null = db.execute(
        "SELECT COUNT(*) FROM filing_line_items WHERE value_usd IS NULL AND raw_value_reported IS NOT NULL"
    ).fetchone()[0]
    val_total = db.execute(
        "SELECT COUNT(*) FROM filing_line_items WHERE value_usd IS NOT NULL"
    ).fetchone()[0]
    print(f"\n[1/3] VALUE NORMALIZATION: already done")
    print(f"  value_usd non-null: {val_total:,}")
    print(f"  value_usd NULL (with raw_value): {val_null:,}")
    if val_null > 0:
        print(f"  ⚠️  {val_null:,} rows still need normalization — run apply_value_normalization first")
        sys.exit(1)

    # ── Step 2: Batch repair asset_class by rowid range ────────────────────
    print(f"\n[2/3] REPAIR asset_class (batched by rowid)")

    # Count before
    before = db.execute("""
        SELECT asset_class, COUNT(*) as n FROM filing_line_items GROUP BY asset_class ORDER BY n DESC
    """).fetchall()
    print("  Before:")
    for r in before:
        print(f"    {r['asset_class']:15s}: {r['n']:>12,}")

    # Find rows that need fixing: put_call is non-empty but asset_class is wrong
    to_fix = db.execute("""
        SELECT COUNT(*) FROM filing_line_items
        WHERE TRIM(put_call) != '' AND put_call IS NOT NULL
          AND asset_class NOT IN ('call_option', 'put_option')
    """).fetchone()[0]
    print(f"  Rows needing fix: {to_fix:,}")

    if to_fix > 0:
        # Get rowid range
        min_id = db.execute("SELECT MIN(rowid) FROM filing_line_items").fetchone()[0]
        max_id = db.execute("SELECT MAX(rowid) FROM filing_line_items").fetchone()[0]
        BATCH = 100_000
        fixed_total = 0
        for start in range(min_id, max_id + 1, BATCH):
            end = start + BATCH - 1
            n = db.execute("""
                UPDATE filing_line_items
                SET asset_class = CASE UPPER(TRIM(put_call))
                    WHEN 'CALL' THEN 'call_option'
                    WHEN 'PUT'  THEN 'put_option'
                    ELSE asset_class
                END
                WHERE rowid BETWEEN ? AND ?
                  AND UPPER(TRIM(put_call)) IN ('CALL', 'PUT')
                  AND asset_class NOT IN ('call_option', 'put_option')
            """, (start, end)).rowcount
            fixed_total += n
            db.commit()
            _safe_wal_checkpoint(db)
            if ((start - min_id) // BATCH) % 50 == 0:
                print(f"  rowid {start:,}–{end:,}: fixed {n:,} (total {fixed_total:,})")
        print(f"  Total fixed: {fixed_total:,}")
    else:
        print("  No rows to fix — already correct")

    # Count after
    after = db.execute("""
        SELECT asset_class, COUNT(*) as n FROM filing_line_items GROUP BY asset_class ORDER BY n DESC
    """).fetchall()
    print("  After:")
    for r in after:
        print(f"    {r['asset_class']:15s}: {r['n']:>12,}")

    # ── Step 3: QA ────────────────────────────────────────────────────────
    print(f"\n[3/3] QA  CH-1 to CH-13")
    results = run_all_qa(db)
    print(f"\n{'='*60}")
    print("CH-1 to CH-13 RESULTS")
    print(f"{'='*60}")
    pass_n = sum(1 for v in results.values() if v == "PASS")
    fail_n = sum(1 for v in results.values() if v == "FAIL")
    skip_n = sum(1 for v in results.values() if v in ("SKIP", "PENDING"))
    for cid, status in sorted(results.items()):
        icon = "✅" if status == "PASS" else ("⏳" if status in ("PENDING","SKIP") else "❌")
        print(f"  {icon} {cid}: {status}")
    print(f"\n  PASS={pass_n}  FAIL={fail_n}  PENDING/SKIP={skip_n}")

    # Final disk check
    print(f"\n  DB size: {db_path.stat().st_size/1e9:.1f} GB")
    print(f"  Disk:    ", end="", flush=True)
    os.system("df -h . | tail -1")

    db.close()
    print(f"\nDone: {datetime.now().isoformat()}")

    if fail_n > 0 or skip_n > 0:
        print(f"\n⚠️  {fail_n} FAIL(s), {skip_n} SKIP(s) — ALL must be PASS before proceeding")
        sys.exit(1)
    else:
        print(f"\n✅ All {pass_n} QA checks PASS — ready for Codex audit")
