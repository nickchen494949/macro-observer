"""
Resume script: run VALUE normalization + QA on an existing fully-ingested+enriched DB.
Skips download, ingest, and enrich — those are already done.

Usage:
  export DB_PATH="data/13f_full_4409f14.db"
  python resume_normalize_qa.py
"""
import os, sys, sqlite3, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s")

from pipeline import apply_value_normalization, run_all_qa, get_db

if __name__ == "__main__":
    db_path = Path(os.environ.get("DB_PATH", "data/13f.db"))
    print(f"\n{'='*60}")
    print(f"RESUME: Normalization + QA")
    print(f"{'='*60}")
    print(f"  DB:      {db_path}  ({db_path.stat().st_size/1e9:.1f} GB)")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"  Disk:    ", end="", flush=True)
    os.system("df -h . | tail -1")

    db = get_db()

    # Quick baseline
    fe = db.execute("SELECT COUNT(*) FROM filing_events").fetchone()[0]
    accept = db.execute("SELECT COUNT(*) FROM filing_events WHERE acceptance_datetime IS NOT NULL").fetchone()[0]
    print(f"\n  Filings: {fe:,}  (acceptance_datetime: {accept:,} = {accept/max(fe,1)*100:.1f}%)")

    # Normalization (batched, with WAL checkpoint)
    print(f"\n[1/3] VALUE NORMALIZATION (batched)")
    apply_value_normalization(db)

    # Repair asset_class using fixed case-insensitive classify_asset
    print(f"\n[2/3] REPAIR asset_class (case-insensitive classify_asset)")
    from pipeline import classify_asset, _safe_wal_checkpoint
    BATCH = 500
    all_accs = [r[0] for r in db.execute(
        "SELECT DISTINCT accession_number FROM filing_line_items"
    ).fetchall()]
    print(f"  {len(all_accs):,} accessions to reclassify")
    for i in range(0, len(all_accs), BATCH):
        batch = all_accs[i:i+BATCH]
        placeholders = ",".join("?" * len(batch))
        rows = db.execute(f"""
            SELECT rowid, put_call, sshprnamttype
            FROM filing_line_items
            WHERE accession_number IN ({placeholders})
        """, batch).fetchall()
        for row in rows:
            new_class = classify_asset(row["put_call"], row["sshprnamttype"])
            db.execute("UPDATE filing_line_items SET asset_class = ? WHERE rowid = ?",
                       (new_class, row["rowid"]))
        db.commit()
        _safe_wal_checkpoint(db)
        if (i // BATCH) % 100 == 0:
            print(f"  reclassified: {min(i+BATCH, len(all_accs)):,}/{len(all_accs):,}")
    # Verify
    counts = db.execute("""
        SELECT asset_class, COUNT(*) as n FROM filing_line_items GROUP BY asset_class ORDER BY n DESC
    """).fetchall()
    for r in counts:
        print(f"    {r['asset_class']:15s}: {r['n']:>12,}")

    # QA
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
