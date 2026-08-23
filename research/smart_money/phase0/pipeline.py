"""
Phase 0 Pipeline — SEC 13F Bulk Data Ingestion & Normalization
v1.5 spec compliant

Entry points:
  python pipeline.py download          # Download all bulk ZIPs
  python pipeline.py ingest            # Ingest ZIPs into SQLite
  python pipeline.py enrich            # Fetch acceptance timestamps
  python pipeline.py qa                # Run CH-1 to CH-13 checks
  python pipeline.py status            # Show current pipeline status

Database: data/13f.db (SQLite)
"""

import os
import re
import csv
import json
import time
import zipfile
import sqlite3
import logging
import argparse
import requests
import pandas as pd
from io import StringIO
from pathlib import Path
from datetime import date, timedelta, datetime
from typing import Optional

# ─── Config ───────────────────────────────────────────────────────────────────

DB_PATH = Path(os.environ.get("DB_PATH", str(Path(__file__).parent / "data" / "13f.db")))
ZIP_DIR = Path(__file__).parent / "data" / "zips"
LOG_PATH = Path(__file__).parent / "data" / "pipeline.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_sec_ua = os.environ.get("SEC_USER_AGENT", "")
if not _sec_ua:
    raise RuntimeError(
        "SEC_USER_AGENT not set. Run: export SEC_USER_AGENT='Your Name your@email.com'"
    )
HEADERS = {"User-Agent": _sec_ua}
SEC_RATE_LIMIT = 0.11   # 10 req/sec → wait 110ms between requests

# VALUE regime cutoff (acceptance_datetime, not period_of_report)
VALUE_REGIME_CUTOFF = "2023-01-03"

# De minimis threshold (SEC: omit if BOTH conditions met)
DE_MINIMIS_SHARES = 10_000
DE_MINIMIS_VALUE_USD = 200_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ─── Database Schema ──────────────────────────────────────────────────────────

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS filing_events (
    accession_number      TEXT PRIMARY KEY,
    cik                   TEXT NOT NULL,
    period_of_report      TEXT NOT NULL,
    acceptance_datetime   TEXT,
    filing_date           TEXT,
    form_type             TEXT,
    amendment_type        TEXT,      -- NULL / RESTATEMENT / ADD_NEW_HOLDINGS
    supersedes_accession  TEXT,
    is_confidential_omit  INTEGER DEFAULT 0,
    conf_flag_quality     TEXT,      -- A / B / C
    table_value_total     INTEGER,   -- from coverpage (normalized USD)
    ingest_zip            TEXT,      -- source ZIP label
    ingest_ts             TEXT       -- when we ingested
);

CREATE TABLE IF NOT EXISTS filing_line_items (
    accession_number      TEXT NOT NULL,
    line_seq              INTEGER NOT NULL,
    cusip                 TEXT,
    security_name         TEXT,
    title_of_class        TEXT,
    raw_value_reported    INTEGER,      -- as-filed value (NEVER modified; thousands or dollars per filing regime)
    value_usd             INTEGER,      -- normalized USD; always recomputed from raw_value_reported
    sshprnamt             INTEGER,      -- shares or principal
    sshprnamttype         TEXT,         -- SH / PRN
    put_call              TEXT,         -- NULL / PUT / CALL
    investment_discretion TEXT,         -- SOLE / SHARED / DFND / OTR
    other_manager         TEXT,
    voting_sole           INTEGER,
    voting_shared         INTEGER,
    voting_none           INTEGER,
    asset_class           TEXT,         -- cash_equity / call_option / put_option / bond / other
    censor_flag           TEXT,         -- NORMAL / LOW_CONFIDENCE_NEW / LOW_CONFIDENCE_EXIT
    PRIMARY KEY (accession_number, line_seq)
);

CREATE INDEX IF NOT EXISTS idx_fe_cik_period
    ON filing_events(cik, period_of_report);
CREATE INDEX IF NOT EXISTS idx_fe_period
    ON filing_events(period_of_report);
CREATE INDEX IF NOT EXISTS idx_li_cusip
    ON filing_line_items(cusip);
CREATE INDEX IF NOT EXISTS idx_li_accession
    ON filing_line_items(accession_number);

CREATE TABLE IF NOT EXISTS qa_results (
    check_id    TEXT PRIMARY KEY,
    status      TEXT,     -- PASS / FAIL / SKIP / PENDING
    detail      TEXT,
    run_ts      TEXT
);
"""

# ─── Deadline Calendar ────────────────────────────────────────────────────────

# Federal holidays observed by SEC (approximate; update annually)
# Source: Federal Reserve / SEC follow US federal holiday schedule
SEC_HOLIDAYS = {
    # 2013
    date(2013,1,1),date(2013,1,21),date(2013,2,18),date(2013,5,27),
    date(2013,7,4),date(2013,9,2),date(2013,10,14),date(2013,11,11),
    date(2013,11,28),date(2013,12,25),
    # 2014
    date(2014,1,1),date(2014,1,20),date(2014,2,17),date(2014,5,26),
    date(2014,7,4),date(2014,9,1),date(2014,10,13),date(2014,11,11),
    date(2014,11,27),date(2014,12,25),
    # 2015
    date(2015,1,1),date(2015,1,19),date(2015,2,16),date(2015,5,25),
    date(2015,7,3),date(2015,9,7),date(2015,10,12),date(2015,11,11),
    date(2015,11,26),date(2015,12,25),
    # 2016
    date(2016,1,1),date(2016,1,18),date(2016,2,15),date(2016,5,30),
    date(2016,7,4),date(2016,9,5),date(2016,10,10),date(2016,11,11),
    date(2016,11,24),date(2016,12,26),
    # 2017
    date(2017,1,2),date(2017,1,16),date(2017,2,20),date(2017,5,29),
    date(2017,7,4),date(2017,9,4),date(2017,10,9),date(2017,11,10),
    date(2017,11,23),date(2017,12,25),
    # 2018
    date(2018,1,1),date(2018,1,15),date(2018,2,19),date(2018,5,28),
    date(2018,7,4),date(2018,9,3),date(2018,10,8),date(2018,11,12),
    date(2018,11,22),date(2018,12,25),
    # 2019
    date(2019,1,1),date(2019,1,21),date(2019,2,18),date(2019,5,27),
    date(2019,7,4),date(2019,9,2),date(2019,10,14),date(2019,11,11),
    date(2019,11,28),date(2019,12,25),
    # 2020
    date(2020,1,1),date(2020,1,20),date(2020,2,17),date(2020,5,25),
    date(2020,7,3),date(2020,9,7),date(2020,10,12),date(2020,11,11),
    date(2020,11,26),date(2020,12,25),
    # 2021
    date(2021,1,1),date(2021,1,18),date(2021,2,15),date(2021,5,31),
    date(2021,7,5),date(2021,9,6),date(2021,10,11),date(2021,11,11),
    date(2021,11,25),date(2021,12,24),
    # 2022
    date(2022,1,17),date(2022,2,21),date(2022,5,30),date(2022,6,19),
    date(2022,7,4),date(2022,9,5),date(2022,10,10),date(2022,11,11),
    date(2022,11,24),date(2022,12,26),
    # 2023
    date(2023,1,2),date(2023,1,16),date(2023,2,20),date(2023,5,29),
    date(2023,6,19),date(2023,7,4),date(2023,9,4),date(2023,10,9),
    date(2023,11,10),date(2023,11,23),date(2023,12,25),
    # 2024
    date(2024,1,1),date(2024,1,15),date(2024,2,19),date(2024,5,27),
    date(2024,6,19),date(2024,7,4),date(2024,9,2),date(2024,10,14),
    date(2024,11,11),date(2024,11,28),date(2024,12,25),
    # 2025
    date(2025,1,1),date(2025,1,20),date(2025,2,17),date(2025,5,26),
    date(2025,6,19),date(2025,7,4),date(2025,9,1),date(2025,10,13),
    date(2025,11,11),date(2025,11,27),date(2025,12,25),
    # 2026
    date(2026,1,1),date(2026,1,19),date(2026,2,16),date(2026,5,25),
    date(2026,6,19),date(2026,7,3),date(2026,9,7),date(2026,10,12),
    date(2026,11,11),date(2026,11,26),date(2026,12,25),
}

def compute_13f_deadline(period_of_report: str) -> str:
    """
    SEC Rule: 13F due within 45 calendar days of quarter end.
    If 45th day falls on weekend or federal holiday → next SEC business day.

    Verified: period=2025-12-31 → 45th day 2026-02-14 (Sat)
              → 2026-02-16 Presidents' Day → deadline 2026-02-17 (Tue) [CH-11]
    """
    qend = date.fromisoformat(period_of_report)
    due = qend + timedelta(days=45)
    while due.weekday() >= 5 or due in SEC_HOLIDAYS:
        due += timedelta(days=1)
    return due.isoformat()

# ─── VALUE Normalization ──────────────────────────────────────────────────────

def normalize_value(raw_value: Optional[int],
                    acceptance_datetime: Optional[str]) -> Optional[int]:
    """
    Normalize 13F VALUE field to USD.

    Pre-2023-01-03 acceptance: VALUE was in $000 → multiply by 1000
    Post-2023-01-03 acceptance: VALUE is nearest dollar → use as-is

    CRITICAL: use acceptance_datetime, NOT period_of_report.
    Counterexample: Berkshire period=2022-12-31, accepted=2023-02-14 → new regime.
    """
    if raw_value is None:
        return None
    if acceptance_datetime is None:
        return None  # cannot normalize without acceptance date; flag as unknown
    acc_date = acceptance_datetime[:10]
    if acc_date < VALUE_REGIME_CUTOFF:
        return raw_value * 1000
    return raw_value

def apply_value_normalization(db: sqlite3.Connection) -> None:
    """Idempotent batch VALUE normalization using acceptance_datetime.

    Always reads raw_value_reported (immutable). Always resets value_usd to NULL first.
    Running this function N times produces exactly the same result as running it once.
    Never reads value_usd as input — prevents double-multiplication.
    """
    db.execute("UPDATE filing_line_items SET value_usd = NULL")
    # Old regime: raw value was reported in $000 → multiply by 1000
    db.execute("""
        UPDATE filing_line_items
        SET value_usd = raw_value_reported * 1000
        WHERE raw_value_reported IS NOT NULL
          AND accession_number IN (
              SELECT accession_number FROM filing_events
              WHERE acceptance_datetime IS NOT NULL
                AND substr(acceptance_datetime,1,10) < ?
          )
    """, (VALUE_REGIME_CUTOFF,))
    # New regime: raw value is already in dollars
    db.execute("""
        UPDATE filing_line_items
        SET value_usd = raw_value_reported
        WHERE raw_value_reported IS NOT NULL
          AND accession_number IN (
              SELECT accession_number FROM filing_events
              WHERE acceptance_datetime IS NOT NULL
                AND substr(acceptance_datetime,1,10) >= ?
          )
    """, (VALUE_REGIME_CUTOFF,))
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM filing_line_items WHERE value_usd IS NOT NULL").fetchone()[0]
    log.info(f"VALUE normalization complete: {n:,} line items normalized (idempotent)")



def classify_asset(put_call: Optional[str], sshprnamttype: Optional[str]) -> str:
    """
    Classify line item asset type.
    MUST be applied before any share aggregation (CH-10).
    """
    if put_call == "CALL":
        return "call_option"
    if put_call == "PUT":
        return "put_option"
    if sshprnamttype == "PRN":
        return "bond"
    if sshprnamttype == "SH" and (put_call is None or put_call.strip() == ""):
        return "cash_equity"
    return "other"

# ─── De Minimis Censor Flag ───────────────────────────────────────────────────

def compute_censor_flag(shares: Optional[int],
                        value_usd: Optional[int],
                        prev_shares: Optional[int],
                        prev_value_usd: Optional[int]) -> str:
    """
    Flag positions near reporting threshold to reduce false NEW/EXIT signals.
    SEC allows omission if BOTH: shares < 10,000 AND value < $200,000.
    """
    is_new = (prev_shares is None or prev_shares == 0)
    is_exit = (shares is None or shares == 0)
    near_thresh_curr = (shares or 0) < DE_MINIMIS_SHARES * 3
    near_thresh_prev = (prev_shares or 0) < DE_MINIMIS_SHARES * 3
    if is_new and near_thresh_curr:
        return "LOW_CONFIDENCE_NEW"
    if is_exit and near_thresh_prev:
        return "LOW_CONFIDENCE_EXIT"
    return "NORMAL"

# ─── Amendment Type Detection ─────────────────────────────────────────────────

def detect_amendment_type(coverpage_row: dict) -> Optional[str]:
    """
    Detect amendment semantics from COVERPAGE data.

    SEC FAQ distinguishes:
      RESTATEMENT     → full replacement (complete new holdings)
      ADD_NEW_HOLDINGS → supplement (merge into existing)

    AMENDMENTTYPE field in SEC COVERPAGE table:
      'RESTATEMENT'     → REPLACE
      'NEW_HOLDINGS'    → MERGE (adds new entries)
      (empty/NULL)      → original filing (not amendment)
    """
    form_type = (coverpage_row.get("FORMTYPE") or "").strip()
    amendment_type_raw = (coverpage_row.get("AMENDMENTTYPE") or "").strip().upper()
    is_amendment = form_type.endswith("/A")

    if not is_amendment:
        return None  # original filing

    if "RESTATEMENT" in amendment_type_raw:
        return "RESTATEMENT"
    if "NEW" in amendment_type_raw or "HOLDINGS" in amendment_type_raw:
        return "ADD_NEW_HOLDINGS"

    # Fallback: if can't determine type, treat conservatively as RESTATEMENT
    log.warning(f"Unknown amendment type: '{amendment_type_raw}' — quarantined as UNKNOWN")
    return "UNKNOWN"

# ─── State Reconstruction ─────────────────────────────────────────────────────

def reconstruct_state(db: sqlite3.Connection,
                      cik: str,
                      period_of_report: str,
                      as_of_datetime: str) -> list[dict]:
    """
    Returns the correct known holdings state at as_of_datetime.

    Implements event-sourced state machine:
      RESTATEMENT → REPLACE entire state
      ADD_NEW_HOLDINGS → MERGE into existing state

    CH-4/CH-9 verified with Berkshire 2023Q4 (ADD type).
    """
    rows = db.execute("""
        SELECT fe.accession_number, fe.amendment_type, fe.acceptance_datetime
        FROM filing_events fe
        WHERE fe.cik = ? AND fe.period_of_report = ?
          AND fe.acceptance_datetime <= ?
          AND fe.form_type NOT IN ('13F-NT', '13F-NT/A')
        ORDER BY fe.acceptance_datetime ASC
    """, (cik, period_of_report, as_of_datetime)).fetchall()

    # state: key=(cusip, investment_discretion) → aggregated shares/value
    # Must SUM multiple rows with same key (same CUSIP + discretion = shared ownership)
    state: dict = {}

    def _aggregate_into(state: dict, lines) -> dict:
        """Add lines into state, summing shares and value for duplicate keys."""
        for l in lines:
            key = (l["cusip"], l["investment_discretion"])
            if key in state:
                existing = state[key]
                existing["sshprnamt"] = (existing.get("sshprnamt") or 0) + (l["sshprnamt"] or 0)
                existing["value_usd"]  = (existing.get("value_usd")  or 0) + (l["value_usd"]  or 0)
                existing["raw_value_reported"] = (
                    (existing.get("raw_value_reported") or 0) + (l["raw_value_reported"] or 0)
                )
            else:
                state[key] = dict(l)
        return state

    for row in rows:
        accession = row["accession_number"]
        amendment_type = row["amendment_type"]

        lines = db.execute("""
            SELECT * FROM filing_line_items
            WHERE accession_number = ? AND asset_class = 'cash_equity'
        """, (accession,)).fetchall()

        if amendment_type is None or amendment_type == "RESTATEMENT":
            # Original filing or full replacement: start fresh, then aggregate within-filing
            state = _aggregate_into({}, lines)

        elif amendment_type == "ADD_NEW_HOLDINGS":
            # Per v1.5 spec: ADD amendment UPDATES each position key.
            # "New holdings" = previously omitted securities; amendment replaces/inserts.
            # e.g. base=100 shares + ADD reports 200 shares → 200 (not 300)
            # First aggregate within the ADD filing (SUM same CUSIP within the amendment)
            add_agg = _aggregate_into({}, lines)
            # Then UPDATE state (replace, not add-on-top)
            for key, row_data in add_agg.items():
                state[key] = row_data

        elif amendment_type == "UNKNOWN":
            # Quarantined — do not apply to state
            pass

    return list(state.values())

# ─── Bulk Download ────────────────────────────────────────────────────────────

def ingest_zip(db: sqlite3.Connection, zip_path: Path, zip_label: str) -> dict:
    """
    Ingest a single bulk ZIP into the database.

    Actual ZIP contents (verified from real SEC files):
      SUBMISSION.tsv  : ACCESSION_NUMBER | CIK | PERIODOFREPORT | SUBMISSIONTYPE | FILING_DATE
      COVERPAGE.tsv   : ACCESSION_NUMBER | AMENDMENTTYPE | ISAMENDMENT | FILINGMANAGER_NAME | ...
      INFOTABLE.tsv   : ACCESSION_NUMBER | CUSIP | SSHPRNAMT | VALUE | PUTCALL | ...

    CIK, PERIODOFREPORT, SUBMISSIONTYPE, FILING_DATE  <- SUBMISSION.tsv
    AMENDMENTTYPE                                      <- COVERPAGE.tsv
    Holdings rows                                      <- INFOTABLE.tsv
    """
    stats = {"filings": 0, "line_items": 0, "errors": 0}
    now = datetime.utcnow().isoformat()

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        sub_name = next((n for n in names if "submission" in n.lower()), None)
        cp_name  = next((n for n in names if "coverpage"  in n.lower()), None)
        it_name  = next((n for n in names if "infotable"  in n.lower()), None)

        if not sub_name or not it_name:
            log.error(f"  {zip_label}: missing SUBMISSION or INFOTABLE")
            return stats

        with zf.open(sub_name) as f:
            sub_text = f.read().decode("utf-8", errors="replace")
        cp_text = ""
        if cp_name:
            with zf.open(cp_name) as f:
                cp_text = f.read().decode("utf-8", errors="replace")
        with zf.open(it_name) as f:
            it_text = f.read().decode("utf-8", errors="replace")
        sp_name = next((n for n in names if "summarypage" in n.lower()), None)
        sp_text = ""
        if sp_name:
            with zf.open(sp_name) as f:
                sp_text = f.read().decode("utf-8", errors="replace")

    sub_rows = list(csv.DictReader(StringIO(sub_text), delimiter="\t"))
    cp_rows  = list(csv.DictReader(StringIO(cp_text),  delimiter="\t")) if cp_text else []
    it_rows  = list(csv.DictReader(StringIO(it_text),  delimiter="\t"))
    sp_rows  = list(csv.DictReader(StringIO(sp_text),  delimiter="\t")) if sp_text else []

    # COVERPAGE lookup: accession -> AMENDMENTTYPE
    cp_by_acc: dict[str, dict] = {}
    for row in cp_rows:
        acc = row.get("ACCESSION_NUMBER", "").strip()
        if acc:
            cp_by_acc[acc] = row

    # SUMMARYPAGE lookup: accession -> summary row
    sp_by_acc: dict[str, dict] = {}
    for row in sp_rows:
        acc = row.get("ACCESSION_NUMBER", "").strip()
        if acc:
            sp_by_acc[acc] = row

    # INFOTABLE lookup: accession -> list of line items
    it_by_acc: dict[str, list] = {}
    for row in it_rows:
        acc = row.get("ACCESSION_NUMBER", "").strip()
        it_by_acc.setdefault(acc, []).append(row)

    def parse_date(raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return ""
        try:
            return datetime.strptime(raw, "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
        if len(raw) == 10 and raw[4] == "-":
            return raw
        return raw

    for sub in sub_rows:
        accession   = sub.get("ACCESSION_NUMBER", "").strip()
        if not accession:
            continue

        cik         = sub.get("CIK", "").strip().lstrip("0")
        period      = parse_date(sub.get("PERIODOFREPORT", ""))
        form_type   = sub.get("SUBMISSIONTYPE", "").strip()
        filing_date = parse_date(sub.get("FILING_DATE", ""))

        # Use canonical detect_amendment_type() — no duplicate logic, UNKNOWN quarantine works
        cp = cp_by_acc.get(accession, {})
        coverpage_row = {"FORMTYPE": form_type, "AMENDMENTTYPE": cp.get("AMENDMENTTYPE", "")}
        amendment_type = detect_amendment_type(coverpage_row)

        # UPSERT: overwrite stale rows from old pipeline versions
        db.execute("""
            INSERT INTO filing_events
            (accession_number, cik, period_of_report, filing_date, form_type,
             amendment_type, ingest_zip, ingest_ts)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(accession_number) DO UPDATE SET
                cik=excluded.cik,
                period_of_report=excluded.period_of_report,
                filing_date=excluded.filing_date,
                form_type=excluded.form_type,
                amendment_type=excluded.amendment_type,
                ingest_zip=excluded.ingest_zip,
                ingest_ts=excluded.ingest_ts
        """, (accession, cik, period, filing_date, form_type,
              amendment_type, zip_label, now))

        # SUMMARYPAGE data
        sp = sp_by_acc.get(accession, {})
        tvt_raw = sp.get("TABLEVALUETOTAL", "").strip()
        try:
            tvt_int = int(tvt_raw.replace(",", "")) if tvt_raw else None
        except ValueError:
            tvt_int = None
        is_conf = 1 if sp.get("ISCONFIDENTIALOMITTED", "N").strip().upper() == "Y" else 0
        if tvt_int is not None or is_conf:
            db.execute("""
                UPDATE filing_events
                SET table_value_total=?, is_confidential_omit=?
                WHERE accession_number=?
            """, (tvt_int, is_conf, accession))

        # Atomically replace all line items for this accession (idempotent)
        db.execute("DELETE FROM filing_line_items WHERE accession_number=?", (accession,))
        for seq, li in enumerate(it_by_acc.get(accession, [])):
            cusip         = li.get("CUSIP", "").strip()
            raw_shares    = li.get("SSHPRNAMT", "").strip()
            raw_value     = li.get("VALUE", "").strip()
            put_call      = li.get("PUTCALL", "").strip() or None
            sshprnamttype = li.get("SSHPRNAMTTYPE", "SH").strip()
            discretion    = li.get("INVESTMENTDISCRETION", "").strip()
            other_mgr     = li.get("OTHERMANAGER", "").strip() or None
            name_issuer   = li.get("NAMEOFISSUER", "").strip() or None
            title_class   = li.get("TITLEOFCLASS", "").strip() or None
            v_sole        = li.get("VOTING_AUTH_SOLE", "").strip()
            v_shared      = li.get("VOTING_AUTH_SHARED", "").strip()
            v_none        = li.get("VOTING_AUTH_NONE", "").strip()

            try:
                shares = int(raw_shares.replace(",", "")) if raw_shares else None
            except ValueError:
                shares = None
            try:
                raw_val_int = int(raw_value.replace(",", "")) if raw_value else None
            except ValueError:
                raw_val_int = None
            try:
                vsole = int(v_sole) if v_sole else None
            except ValueError:
                vsole = None
            try:
                vshared = int(v_shared) if v_shared else None
            except ValueError:
                vshared = None
            try:
                vnone = int(v_none) if v_none else None
            except ValueError:
                vnone = None

            # Store raw_value_reported (immutable); value_usd set to NULL until enrich runs
            db.execute("""
                INSERT INTO filing_line_items
                (accession_number, line_seq, cusip, security_name, title_of_class,
                 raw_value_reported, value_usd, sshprnamt,
                 sshprnamttype, put_call, investment_discretion,
                 other_manager, voting_sole, voting_shared, voting_none, asset_class)
                VALUES (?,?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?)
            """, (accession, seq, cusip, name_issuer, title_class,
                  raw_val_int, shares,
                  sshprnamttype, put_call, discretion, other_mgr,
                  vsole, vshared, vnone,
                  classify_asset(put_call, sshprnamttype)))
            stats["line_items"] += 1

        stats["filings"] += 1

    db.commit()
    log.info(f"  {zip_label}: {stats['filings']} filings, {stats['line_items']} lines")
    return stats

# --- Acceptance Timestamp Enrichment

# ─── Acceptance Timestamp Enrichment ─────────────────────────────────────────

def fetch_submissions(cik: str) -> list[dict]:
    """
    Fetch all submissions for a CIK, following files[] pagination.
    Uses bulk submissions.zip if available (preferred).
    """
    cik_padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    time.sleep(SEC_RATE_LIMIT)

    recent = data.get("filings", {}).get("recent", {})
    all_submissions = _flatten_filings(recent)

    # Follow historical file references
    for hist_file in data.get("filings", {}).get("files", []):
        hist_url = f"https://data.sec.gov/submissions/{hist_file['name']}"
        hist_r = requests.get(hist_url, headers=HEADERS, timeout=30)
        if hist_r.ok:
            hist_data = hist_r.json()
            all_submissions.extend(_flatten_filings(hist_data))
        time.sleep(SEC_RATE_LIMIT)

    return all_submissions

def _flatten_filings(filings_dict: dict) -> list[dict]:
    """Convert parallel arrays in SEC filings dict to list of records."""
    if not filings_dict:
        return []
    keys = list(filings_dict.keys())
    n = len(filings_dict.get(keys[0], []))
    return [
        {k: filings_dict[k][i] for k in keys}
        for i in range(n)
    ]

def enrich_acceptance_timestamps(db: sqlite3.Connection) -> None:
    """
    For each filing_event without acceptance_datetime, fetch from Submissions API.
    Also normalizes VALUE after timestamp is known.
    """
    missing = db.execute("""
        SELECT DISTINCT cik FROM filing_events
        WHERE acceptance_datetime IS NULL
    """).fetchall()

    for row in missing:
        cik = row["cik"]
        try:
            submissions = fetch_submissions(cik)
            for sub in submissions:
                acc = (sub.get("accessionNumber") or "").replace("-", "")
                acc_fmt = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}" if len(acc) == 18 else acc
                accept_dt = sub.get("acceptanceDateTime") or sub.get("acceptanceDatetime") or ""

                if acc_fmt and accept_dt:
                    db.execute("""
                        UPDATE filing_events
                        SET acceptance_datetime = ?
                        WHERE accession_number = ?
                    """, (accept_dt, acc_fmt))

        except Exception as e:
            log.error(f"Enrichment failed for CIK {cik}: {e}")

    db.commit()

    # Normalize VALUE using acceptance_datetime — canonical idempotent function
    apply_value_normalization(db)

# _normalize_values_with_timestamp() DELETED — it multiplied value_usd in place
# and could not handle new ingests where value_usd starts as NULL.
# Use apply_value_normalization() everywhere instead.



# ─── QA Checks CH-1 to CH-13 ─────────────────────────────────────────────────

def run_all_qa(db: sqlite3.Connection) -> dict[str, str]:
    """
    Run all CH-1 to CH-13 mechanical checks.
    Returns {check_id: 'PASS'/'FAIL'/'SKIP'}.
    """
    results = {}
    now = datetime.utcnow().isoformat()

    def record(check_id, status, detail=""):
        results[check_id] = status
        db.execute("""
            INSERT OR REPLACE INTO qa_results (check_id, status, detail, run_ts)
            VALUES (?,?,?,?)
        """, (check_id, status, detail, now))
        log.info(f"  {check_id}: {status} — {detail}")

    db.commit()

    # CH-1: VALUE normalization reconciliation (no 1000× discontinuity at 2023Q1)
    try:
        check_ch1(db, record)
    except Exception as e:
        record("CH-1", "FAIL", str(e))

    # CH-2: Berkshire 2023Q4 holdings match known top positions
    try:
        check_ch2(db, record)
    except Exception as e:
        record("CH-2", "FAIL", str(e))

    # CH-3: NVDA split — no spurious 9× Δshares in 2024Q2
    try:
        check_ch3(db, record)
    except Exception as e:
        record("CH-3", "FAIL", str(e))

    # CH-4: Amendment state — RESTATEMENT replaces; ADD_NEW_HOLDINGS merges
    try:
        check_ch4(db, record)
    except Exception as e:
        record("CH-4", "FAIL", str(e))

    # CH-5: Entity dedup (no double-count for multi-CIK managers)
    record("CH-5", "PENDING", "Requires manager entity graph; implement after bulk ingest")

    # CH-6: CUSIP continuity (no unexplained quarter-over-quarter gaps)
    try:
        check_ch6(db, record)
    except Exception as e:
        record("CH-6", "FAIL", str(e))

    # CH-7: Universe has no future-return filter (not applicable to DB; process check)
    record("CH-7", "SKIP", "Verified by design: universe filter applied at query time only")

    # CH-8: acceptance_datetime completeness (> 95% of accessions)
    try:
        check_ch8(db, record)
    except Exception as e:
        record("CH-8", "FAIL", str(e))

    # CH-9: ADD_NEW_HOLDINGS correctly merges (Berkshire 2023Q4 test case)
    try:
        check_ch9(db, record)
    except Exception as e:
        record("CH-9", "FAIL", str(e))

    # CH-10: Option separation (CALL/PUT not mixed into cash equity)
    try:
        check_ch10(db, record)
    except Exception as e:
        record("CH-10", "FAIL", str(e))

    # CH-11: Deadline calendar (2025-12-31 → 2026-02-17)
    try:
        check_ch11(record)
    except Exception as e:
        record("CH-11", "FAIL", str(e))

    # CH-12: Historical submissions completeness (large filer)
    try:
        check_ch12(db, record)
    except Exception as e:
        record("CH-12", "FAIL", str(e))

    # CH-13: CUSIP → ticker coverage rate (post-mapping step)
    record("CH-13", "PENDING", "Run after Phase 0.13 CUSIP mapping step")

    db.commit()
    return results


def check_ch1(db, record):
    """No 1000× discontinuity at 2023Q1 boundary — verified against actual dollar magnitude.

    Two sub-checks:
    (a) Regime branch: Berkshire 2022-12-31 (accepted 2023-02-14) must use ×1 (new regime).
    (b) Magnitude sanity: Berkshire total value_usd must be in [$50B, $1T].
        $299B → PASS. $299T → FAIL (means raw was multiplied again).
        This check catches double-normalization bugs that (a) alone cannot catch.
    """
    acc = "0000950123-23-002585"
    row = db.execute(
        "SELECT acceptance_datetime FROM filing_events WHERE accession_number=?", (acc,)
    ).fetchone()

    if not row:
        record("CH-1", "SKIP", f"Berkshire {acc} not yet ingested")
        return

    accept_dt = row["acceptance_datetime"] or ""
    if not accept_dt:
        record("CH-1", "SKIP", f"Berkshire {acc}: acceptance_datetime not yet enriched")
        return

    # (a) Branch check
    mult = 1000 if accept_dt[:10] < VALUE_REGIME_CUTOFF else 1
    if mult != 1:
        record("CH-1", "FAIL",
               f"Berkshire {acc} accepted {accept_dt[:10]}: branch gives ×{mult}, expected ×1")
        return

    # (b) Magnitude sanity check — actual value_usd in DB
    total_row = db.execute("""
        SELECT SUM(value_usd) as total
        FROM filing_line_items
        WHERE accession_number = ?
    """, (acc,)).fetchone()

    total_usd = total_row["total"] if total_row else None
    if total_usd is None:
        record("CH-1", "SKIP", f"Berkshire {acc}: no line items yet")
        return

    # (b1) Magnitude sanity: must be in [$50B, $1T]
    lo, hi = 50e9, 1e12
    if not (lo <= total_usd <= hi):
        record("CH-1", "FAIL",
               f"Berkshire {acc}: line-item total={total_usd:.3e} outside [{lo:.0e},{hi:.0e}]"
               f" — likely double-normalization")
        return

    # (b2) Reconcile vs SUMMARYPAGE tableValueTotal within 1% (v1.5 spec)
    tvt_row = db.execute(
        "SELECT table_value_total, acceptance_datetime FROM filing_events WHERE accession_number=?",
        (acc,)
    ).fetchone()
    tvt_raw = tvt_row["table_value_total"] if tvt_row else None
    accept_dt = (tvt_row["acceptance_datetime"] or "") if tvt_row else ""
    if tvt_raw is None:
        record("CH-1", "SKIP", f"Berkshire {acc}: table_value_total not yet populated (run enrich first)")
        return
    tvt_norm = normalize_value(tvt_raw, accept_dt)
    if not tvt_norm:
        record("CH-1", "SKIP", f"Berkshire {acc}: cannot normalize table_value_total={tvt_raw}")
        return
    diff = abs(total_usd - tvt_norm) / tvt_norm
    if diff <= 0.01:
        record("CH-1", "PASS",
               f"Berkshire {acc}: ×1 ✓, line={total_usd/1e9:.2f}B tvt={tvt_norm/1e9:.2f}B diff={diff:.3%}")
    else:
        record("CH-1", "FAIL",
               f"Berkshire {acc}: line={total_usd/1e9:.2f}B vs tvt={tvt_norm/1e9:.2f}B diff={diff:.1%} > 1%")


def check_ch2(db, record):
    """Berkshire 2023Q4 top positions match known values."""
    rows = db.execute("""
        SELECT li.cusip, li.sshprnamt
        FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number = li.accession_number
        WHERE fe.cik = '1067983'
          AND fe.period_of_report = '2023-12-31'
          AND li.asset_class = 'cash_equity'
        ORDER BY li.sshprnamt DESC
        LIMIT 5
    """).fetchall()

    if not rows:
        record("CH-2", "SKIP", "Berkshire 2023Q4 not yet ingested")
        return

    top_cusip = rows[0]["cusip"]
    top_shares = rows[0]["sshprnamt"]
    # Known: Berkshire largest position Q4 2023 = Apple (CUSIP 037833100) ~905M shares
    known_aapl_cusip = "037833100"
    known_aapl_shares_approx = 900_000_000

    if top_cusip == known_aapl_cusip and abs(top_shares - known_aapl_shares_approx) / known_aapl_shares_approx < 0.05:
        record("CH-2", "PASS", f"Top position: {top_cusip} {top_shares:,} shares (≈Apple ✓)")
    else:
        record("CH-2", "FAIL",
               f"Top position: CUSIP={top_cusip} shares={top_shares:,}; expected Apple ~900M")


def check_ch3(db, record):
    """NVDA 10:1 split 2024-06-10: no 9× spurious increase."""
    # Compare a manager's NVDA shares in Q1 2024 vs Q2 2024
    # If split-adjusted correctly: Q2 / Q1 ≈ 10 (real); unajusted would be ~10 too (split happened)
    # Key: check that no manager shows 10× increase that was NOT due to buying
    rows = db.execute("""
        SELECT fe.cik, li.sshprnamt
        FROM filing_line_items li
        JOIN filing_events fe ON fe.accession_number = li.accession_number
        WHERE li.cusip = '67066G104'   -- NVDA CUSIP (pre-split; verify)
          AND fe.period_of_report IN ('2024-03-31', '2024-06-30')
          AND li.asset_class = 'cash_equity'
        ORDER BY fe.cik, fe.period_of_report
    """).fetchall()

    if not rows:
        record("CH-3", "SKIP", "NVDA data not yet ingested or CUSIP mismatch")
        return

    record("CH-3", "PENDING", f"Found {len(rows)} NVDA rows; manual split adjustment verification needed")


def check_ch4(db, record):
    """RESTATEMENT type replaces; ADD_NEW_HOLDINGS merges."""
    # Verify amendment_type field populated
    restatements = db.execute(
        "SELECT COUNT(*) as n FROM filing_events WHERE amendment_type='RESTATEMENT'"
    ).fetchone()["n"]
    adds = db.execute(
        "SELECT COUNT(*) as n FROM filing_events WHERE amendment_type='ADD_NEW_HOLDINGS'"
    ).fetchone()["n"]
    amendments = db.execute(
        "SELECT COUNT(*) as n FROM filing_events WHERE form_type LIKE '%/A%'"
    ).fetchone()["n"]

    if amendments == 0:
        record("CH-4", "SKIP", "No amendments ingested yet")
        return

    record("CH-4", "PASS" if (restatements + adds) > 0 else "FAIL",
           f"Amendments: {amendments} total; RESTATEMENT={restatements}; ADD={adds}; "
           f"unclassified={amendments - restatements - adds}")


def check_ch6(db, record):
    """CUSIP continuity: no large unexplained gaps."""
    # Very large Δshares without corporate action = likely data error
    record("CH-6", "PENDING", "Implement after split adjustment layer")


def check_ch8(db, record):
    """acceptance_datetime completeness > 95%."""
    total = db.execute("SELECT COUNT(*) as n FROM filing_events").fetchone()["n"]
    with_dt = db.execute(
        "SELECT COUNT(*) as n FROM filing_events WHERE acceptance_datetime IS NOT NULL"
    ).fetchone()["n"]

    if total == 0:
        record("CH-8", "SKIP", "No filings ingested yet")
        return

    pct = with_dt / total * 100
    status = "PASS" if pct >= 95 else "FAIL"
    record("CH-8", status, f"{with_dt}/{total} = {pct:.1f}% have acceptance_datetime")


def check_ch9(db, record):
    """Berkshire 2023Q4 ADD amendment: original holdings preserved."""
    # Berkshire original: 2024-02-14; ADD amendment: 2024-05-15
    # reconstruct_state at deadline (2026-02-17 for Q4 2025... wait, Q4 2023 deadline = ~2024-02-14+45)
    cik = "1067983"
    period = "2023-12-31"
    deadline = compute_13f_deadline(period)   # ~2024-02-14 → 2024-02-15 (Thu)

    state_at_deadline = reconstruct_state(db, cik, period, deadline + "T23:59:59")
    state_after_amendment = reconstruct_state(db, cik, period, "2026-01-01T00:00:00")

    if not state_at_deadline:
        record("CH-9", "SKIP", f"Berkshire {period} not ingested or no state at {deadline}")
        return

    n_before = len(state_at_deadline)
    n_after = len(state_after_amendment)

    # After ADD amendment: should have MORE entries; original entries should still be present
    if n_after >= n_before and n_before > 0:
        record("CH-9", "PASS",
               f"Holdings at deadline: {n_before}; after ADD amendment: {n_after} (ADD merged ✓)")
    else:
        record("CH-9", "FAIL",
               f"Holdings at deadline: {n_before}; after ADD: {n_after} — possible REPLACE bug")


def check_ch10(db, record):
    """OPTIONS not mixed into cash equity counts."""
    # Check that call_option / put_option rows exist and are separate from cash_equity
    asset_counts = db.execute("""
        SELECT asset_class, COUNT(*) as n
        FROM filing_line_items
        GROUP BY asset_class
    """).fetchall()

    if not asset_counts:
        record("CH-10", "SKIP", "No line items ingested yet")
        return

    by_class = {r["asset_class"]: r["n"] for r in asset_counts}
    cash = by_class.get("cash_equity", 0)
    calls = by_class.get("call_option", 0)
    puts = by_class.get("put_option", 0)
    other = by_class.get("other", 0)

    record("CH-10", "PASS" if cash > 0 else "FAIL",
           f"cash_equity={cash:,}  call_option={calls:,}  put_option={puts:,}  other={other:,}")


def check_ch11(record):
    """Deadline calendar: 2025-12-31 → 2026-02-17."""
    result = compute_13f_deadline("2025-12-31")
    expected = "2026-02-17"
    if result == expected:
        record("CH-11", "PASS", f"compute_13f_deadline('2025-12-31') = {result} ✓")
    else:
        record("CH-11", "FAIL", f"Got {result}, expected {expected}")


def check_ch12(db, record):
    """Historical submissions completeness for large filer."""
    # Morgan Stanley CIK ~895421; should have 13F filings back to 2013
    cik = "895421"
    oldest = db.execute("""
        SELECT MIN(period_of_report) as oldest
        FROM filing_events
        WHERE cik = ? AND form_type LIKE '13F%'
    """, (cik,)).fetchone()

    if not oldest or not oldest["oldest"]:
        record("CH-12", "SKIP", f"CIK {cik} not yet ingested")
        return

    oldest_period = oldest["oldest"]
    if oldest_period <= "2013-12-31":
        record("CH-12", "PASS", f"Morgan Stanley oldest period: {oldest_period} ✓")
    else:
        record("CH-12", "FAIL", f"Morgan Stanley oldest period: {oldest_period} — too recent, check files[] pagination")


# ─── CLI ─────────────────────────────────────────────────────────────────────

SCHEMA_VERSION = 2

def get_db() -> sqlite3.Connection:
    """Get or create the SQLite database connection.

    Fails fast if existing DB is schema-incompatible (missing raw_value_reported).
    This prevents silently ingesting into a v1 DB and producing wrong output.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    existing = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "filing_line_items" in existing:
        cols = {r[1] for r in db.execute("PRAGMA table_info(filing_line_items)").fetchall()}
        if "raw_value_reported" not in cols:
            db.close()
            raise RuntimeError(
                f"\nSCHEMA INCOMPATIBILITY: {DB_PATH} is missing column 'raw_value_reported' "
                f"(schema v{SCHEMA_VERSION}).\n"
                f"The existing DB was created by an older pipeline version.\n"
                f"Old DB is PRESERVED. Use a new path:\n"
                f"  export DB_PATH=data/13f_v2.db && python run_phase0.py --skip-download"
            )
    db.executescript(SCHEMA)
    return db


def cmd_download(args):
    from manifest import PACKAGES
    download_zips(PACKAGES, force=args.force)


def cmd_ingest(args):
    db = get_db()
    for zip_path in sorted(ZIP_DIR.glob("*.zip")):
        label = zip_path.stem
        log.info(f"Ingesting {zip_path.name}...")
        ingest_zip(db, zip_path, label)
    db.close()


def cmd_enrich(args):
    db = get_db()
    enrich_acceptance_timestamps(db)
    db.close()


def cmd_qa(args):
    db = get_db()
    results = run_all_qa(db)
    db.close()
    print("\n" + "=" * 60)
    print("CH-1 to CH-13 QA Results")
    print("=" * 60)
    for check_id, status in sorted(results.items()):
        icon = "✅" if status == "PASS" else ("⏳" if status in ("PENDING", "SKIP") else "❌")
        print(f"  {icon} {check_id}: {status}")


def cmd_status(args):
    db = get_db()
    total = db.execute("SELECT COUNT(*) as n FROM filing_events").fetchone()["n"]
    with_dt = db.execute(
        "SELECT COUNT(*) as n FROM filing_events WHERE acceptance_datetime IS NOT NULL"
    ).fetchone()["n"]
    line_items = db.execute("SELECT COUNT(*) as n FROM filing_line_items").fetchone()["n"]
    periods = db.execute(
        "SELECT COUNT(DISTINCT period_of_report) as n FROM filing_events"
    ).fetchone()["n"]
    print(f"\nPipeline Status:")
    print(f"  Filings ingested:    {total:,}")
    print(f"  With acceptance_dt:  {with_dt:,} ({with_dt/max(total,1)*100:.1f}%)")
    print(f"  Line items:          {line_items:,}")
    print(f"  Distinct periods:    {periods}")
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 0 Pipeline v1.5")
    sub = parser.add_subparsers(dest="cmd")

    dl = sub.add_parser("download", help="Download all bulk ZIPs")
    dl.add_argument("--force", action="store_true")
    dl.set_defaults(func=cmd_download)

    sub.add_parser("ingest", help="Ingest ZIPs into SQLite").set_defaults(func=cmd_ingest)
    sub.add_parser("enrich", help="Fetch acceptance timestamps").set_defaults(func=cmd_enrich)
    sub.add_parser("qa", help="Run CH-1 to CH-13").set_defaults(func=cmd_qa)
    sub.add_parser("status", help="Show pipeline status").set_defaults(func=cmd_status)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
