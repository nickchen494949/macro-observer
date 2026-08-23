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
    print(f"\n[1/2] VALUE NORMALIZATION (batched)")
    apply_value_normalization(db)

    # QA
    print(f"\n[2/2] QA  CH-1 to CH-13")
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
