"""
Phase 0 Full Execution Script
Discovers all ZIPs from SEC page, downloads, ingests, enriches, runs QA.
"""
import re
import csv
import sys
import time
import json
import zipfile
import sqlite3
import logging
import requests
from io import StringIO
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import (
    DB_PATH, ZIP_DIR, HEADERS, SEC_RATE_LIMIT,
    normalize_value, classify_asset, compute_censor_flag,
    detect_amendment_type, compute_13f_deadline, VALUE_REGIME_CUTOFF,
    SCHEMA, get_db, ingest_zip, run_all_qa
)

log = logging.getLogger(__name__)

SEC_BASE = "https://www.sec.gov"
SEC_INDEX = f"{SEC_BASE}/data-research/sec-markets-data/form-13f-data-sets"

def discover_zip_urls() -> list[tuple[str, str]]:
    """Scrape actual ZIP URLs from SEC bulk data page."""
    r = requests.get(SEC_INDEX, headers=HEADERS, timeout=30)
    r.raise_for_status()
    paths = re.findall(
        r'href=["\'](/files/structureddata/data/form-13f-data-sets/[^"\']+\.zip)["\']',
        r.text
    )
    paths = sorted(set(paths))
    result = []
    for p in paths:
        label = Path(p).stem.replace("_form13f", "")
        result.append((label, f"{SEC_BASE}{p}"))
    print(f"Discovered {len(result)} ZIP packages")
    return result

def download_all(packages: list[tuple[str,str]], force: bool = False):
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    for label, url in packages:
        dest = ZIP_DIR / f"{label}.zip"
        if dest.exists() and dest.stat().st_size > 1000 and not force:
            print(f"  EXISTS  {label:35s} ({dest.stat().st_size/1e6:6.1f} MB)")
            continue
        print(f"  GET     {label:35s} {url}")
        try:
            r = requests.get(url, headers=HEADERS, stream=True, timeout=300)
            r.raise_for_status()
            size = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    size += len(chunk)
            print(f"  SAVED   {label:35s} {size/1e6:6.1f} MB")
        except Exception as e:
            print(f"  FAIL    {label}: {e}")
        time.sleep(SEC_RATE_LIMIT)

def ingest_all(db: sqlite3.Connection):
    zips = sorted(ZIP_DIR.glob("*.zip"))
    print(f"\nIngesting {len(zips)} ZIPs...")
    total_filings = 0
    total_lines = 0
    for zp in zips:
        if zp.stat().st_size < 100:
            print(f"  SKIP (empty)  {zp.name}")
            continue
        label = zp.stem
        print(f"  Ingesting {zp.name} ...", end=" ", flush=True)
        try:
            stats = ingest_zip(db, zp, label)
            total_filings += stats.get("filings", 0)
            total_lines += stats.get("line_items", 0)
            print(f"{stats.get('filings',0):,} filings  {stats.get('line_items',0):,} lines")
        except Exception as e:
            db.rollback()  # discard any partial writes from this failed ZIP
            print(f"ERROR: {e} -- rolled back")
    print(f"\nTotal ingested: {total_filings:,} filings  {total_lines:,} line items")

def enrich_from_submissions_bulk(db: sqlite3.Connection):
    """
    Enrich acceptance_datetime via SEC EDGAR nightly bulk submissions archive.

    Official URL (nightly, documented at sec.gov/edgar/sec-api-documentation):
      https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip

    Falls back to per-CIK API for any CIKs still missing after the bulk pass.
    """
    sub_zip_url = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
    sub_zip_path = ZIP_DIR / "submissions_bulk.zip"

    if not sub_zip_path.exists() or sub_zip_path.stat().st_size < 1_000_000:
        print(f"\nDownloading SEC bulk submissions.zip (nightly archive)...")
        r = requests.get(sub_zip_url, headers=HEADERS, stream=True, timeout=600)
        r.raise_for_status()
        size = 0
        with open(sub_zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=4 << 20):
                f.write(chunk)
                size += len(chunk)
                print(f"\r  {size/1e6:.0f} MB downloaded...", end="", flush=True)
        print(f"\n  submissions_bulk.zip saved: {size/1e6:.0f} MB")
    else:
        print(f"\nsubmissions_bulk.zip cached ({sub_zip_path.stat().st_size/1e6:.0f} MB)")

    # First: inspect structure of the ZIP to understand file layout
    print("Parsing bulk submissions.zip...")
    updated = 0
    skipped = 0
    try:
        with zipfile.ZipFile(sub_zip_path) as zf:
            names = [n for n in zf.namelist() if n.endswith(".json")]
            print(f"  {len(names):,} JSON files in bulk archive")
            for name in names:
                try:
                    with zf.open(name) as f:
                        data = json.loads(f.read())
                    cik_raw = data.get("cik", "")
                    cik = str(int(cik_raw)) if cik_raw else ""
                    if not cik:
                        skipped += 1
                        continue
                    filings = data.get("filings", {}).get("recent", {})
                    accs = filings.get("accessionNumber", [])
                    adts = filings.get("acceptanceDateTime", [])
                    for acc, adt in zip(accs, adts):
                        if acc and adt:
                            db.execute("""
                                UPDATE filing_events
                                SET acceptance_datetime = ?
                                WHERE accession_number = ?
                                  AND acceptance_datetime IS NULL
                            """, (adt, acc))
                            updated += 1
                    # Historical pagination files within the ZIP
                    for hf in data.get("filings", {}).get("files", []):
                        hf_name = hf.get("name", "")
                        if not hf_name:
                            continue
                        try:
                            with zf.open(hf_name) as hff:
                                hdata = json.loads(hff.read())
                            haccs = hdata.get("accessionNumber", [])
                            hadts = hdata.get("acceptanceDateTime", [])
                            for acc, adt in zip(haccs, hadts):
                                if acc and adt:
                                    db.execute("""
                                        UPDATE filing_events SET acceptance_datetime = ?
                                        WHERE accession_number = ? AND acceptance_datetime IS NULL
                                    """, (adt, acc))
                                    updated += 1
                        except Exception:
                            pass
                except Exception:
                    skipped += 1
        db.commit()
    except Exception as e:
        print(f"  bulk parse error: {e}")
        raise

    print(f"  Bulk pass: {updated:,} rows updated, {skipped} files skipped")

    # Fallback: per-CIK API for anything still missing
    still_missing = db.execute(
        "SELECT COUNT(DISTINCT cik) FROM filing_events WHERE acceptance_datetime IS NULL"
    ).fetchone()[0]
    if still_missing > 0:
        print(f"  Fallback: {still_missing} CIKs still missing — fetching per-CIK API")
        from pipeline import enrich_acceptance_timestamps
        enrich_acceptance_timestamps(db)
    else:
        print("  No fallback needed — all CIKs covered by bulk archive")


def apply_value_normalization(db: sqlite3.Connection):
    """Idempotent VALUE normalization: always recompute value_usd from raw_value_reported.

    CRITICAL: reads raw_value_reported (immutable), writes value_usd.
    Running this function 1×, 2×, 10× must give identical value_usd results.
    Never reads value_usd as input (prevents double-multiplication).
    """
    print("\nApplying VALUE normalization (idempotent, from raw_value_reported)...")

    # First: set all value_usd to NULL (will be recomputed)
    db.execute("UPDATE filing_line_items SET value_usd = NULL")

    # Old regime (pre-2023-01-03): raw_value_reported is in $000 → ×1000
    old_regime = db.execute("""
        SELECT li.accession_number
        FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number = li.accession_number
        WHERE fe.acceptance_datetime IS NOT NULL
          AND substr(fe.acceptance_datetime, 1, 10) < ?
        GROUP BY li.accession_number
    """, (VALUE_REGIME_CUTOFF,)).fetchall()

    old_accs = {r["accession_number"] for r in old_regime}

    db.execute("""
        UPDATE filing_line_items
        SET value_usd = raw_value_reported * 1000
        WHERE accession_number IN (
            SELECT accession_number FROM filing_events
            WHERE acceptance_datetime IS NOT NULL
              AND substr(acceptance_datetime, 1, 10) < ?
        ) AND raw_value_reported IS NOT NULL
    """, (VALUE_REGIME_CUTOFF,))

    # New regime (2023-01-03+): raw_value_reported is already in dollars → ×1
    db.execute("""
        UPDATE filing_line_items
        SET value_usd = raw_value_reported
        WHERE accession_number IN (
            SELECT accession_number FROM filing_events
            WHERE acceptance_datetime IS NOT NULL
              AND substr(acceptance_datetime, 1, 10) >= ?
        ) AND raw_value_reported IS NOT NULL
    """, (VALUE_REGIME_CUTOFF,))

    db.commit()
    total = db.execute("SELECT COUNT(*) FROM filing_line_items WHERE value_usd IS NOT NULL").fetchone()[0]
    print(f"  Normalized {total:,} line items (idempotent; ran from raw_value_reported)")

def print_status(db: sqlite3.Connection):
    total = db.execute("SELECT COUNT(*) as n FROM filing_events").fetchone()["n"]
    with_dt = db.execute(
        "SELECT COUNT(*) as n FROM filing_events WHERE acceptance_datetime IS NOT NULL"
    ).fetchone()["n"]
    line_items = db.execute("SELECT COUNT(*) as n FROM filing_line_items").fetchone()["n"]
    periods = db.execute(
        "SELECT COUNT(DISTINCT period_of_report) as n FROM filing_events WHERE period_of_report != ''"
    ).fetchone()["n"]
    min_p = db.execute(
        "SELECT MIN(period_of_report) FROM filing_events WHERE period_of_report != ''"
    ).fetchone()[0]
    max_p = db.execute(
        "SELECT MAX(period_of_report) FROM filing_events WHERE period_of_report != ''"
    ).fetchone()[0]
    asset_dist = db.execute(
        "SELECT asset_class, COUNT(*) as n FROM filing_line_items GROUP BY asset_class ORDER BY n DESC"
    ).fetchall()

    print(f"\n{'='*60}")
    print(f"DATABASE STATUS")
    print(f"{'='*60}")
    print(f"  Filing events:          {total:>12,}")
    print(f"  With acceptance_dt:     {with_dt:>12,}  ({with_dt/max(total,1)*100:.1f}%)")
    print(f"  Line items:             {line_items:>12,}")
    print(f"  Distinct periods:       {periods:>12,}")
    print(f"  Period range:           {min_p} → {max_p}")
    print(f"\n  Asset class distribution:")
    for row in asset_dist:
        print(f"    {row['asset_class']:20s}: {row['n']:>12,}")
    print(f"{'='*60}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--skip-download", action="store_true")
    p.add_argument("--skip-ingest",   action="store_true")
    p.add_argument("--skip-enrich",   action="store_true")
    p.add_argument("--skip-qa",       action="store_true")
    p.add_argument("--force",         action="store_true", help="Re-download existing ZIPs")
    args = p.parse_args()

    print("\n" + "="*60)
    print("PHASE 0 FULL EXECUTION — v1.5")
    print("="*60)
    print(f"Started: {datetime.now().isoformat()}")

    db = get_db()

    if not args.skip_download:
        print("\n[1/4] DISCOVER + DOWNLOAD")
        packages = discover_zip_urls()
        download_all(packages, force=args.force)

    if not args.skip_ingest:
        print("\n[2/4] INGEST")
        ingest_all(db)

    if not args.skip_enrich:
        print("\n[3/4] ENRICH (acceptance timestamps + VALUE normalization)")
        enrich_from_submissions_bulk(db)

    print_status(db)

    if not args.skip_qa:
        print("\n[4/4] QA  CH-1 to CH-13")
        results = run_all_qa(db)
        print("\n" + "="*60)
        print("CH-1 to CH-13 RESULTS")
        print("="*60)
        pass_n = sum(1 for v in results.values() if v == "PASS")
        fail_n = sum(1 for v in results.values() if v == "FAIL")
        skip_n = sum(1 for v in results.values() if v in ("SKIP", "PENDING"))
        for cid, status in sorted(results.items()):
            icon = "✅" if status == "PASS" else ("⏳" if status in ("PENDING","SKIP") else "❌")
            print(f"  {icon} {cid}: {status}")
        print(f"\n  PASS={pass_n}  FAIL={fail_n}  PENDING/SKIP={skip_n}")
        if fail_n == 0 and pass_n >= 10:
            print("\n✅ FREEZE phase0.sqlite → open future returns → M0")
        else:
            print("\n⚠️  Fix FAILs before proceeding to M0")

    db.close()
    print(f"\nDone: {datetime.now().isoformat()}")
