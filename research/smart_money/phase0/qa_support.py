"""Support data builders for the five Phase 0 QA checks completed after ingest.

The holdings database remains the immutable SEC source layer.  This module only
adds small, reproducible audit tables:

* manager_names / manager_relationships come from SEC bulk ZIP metadata.
* qa_cusip_sample freezes the deterministic CH-13 sample.
* cusip_mappings stores every OpenFIGI result, including explicit failures.

No future-return or price data is read here.
"""

from __future__ import annotations

import csv
import hashlib
import re
import time
import zipfile
from datetime import datetime
from difflib import SequenceMatcher
from io import TextIOWrapper
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import requests


OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
SEC_13F_2020Q1_URL = "https://www.sec.gov/divisions/investment/13f/13flist2020q1.pdf"
CH13_PERIOD = "2020-03-31"
CH13_SAMPLE_SIZE = 100
CH13_SEED = "phase0-v1.5-ch13"
CH13_SAMPLE_METHOD = "sec-13f-official-equity-2020q1-v2"
OFFICIAL_13F_PARSER_VERSION = "2020q1-fixed-layout-v2"

# Source: Twitter Schedule 13D/A states that NYSE delisting was requested for
# 2022-10-28 after the merger.  Keeping this case explicit prevents a mapper
# from silently dropping a security merely because it no longer trades.
KNOWN_DELISTED = {
    "90184L102": {
        "ticker": "TWTR",
        "name": "TWITTER INC",
        "delisted_date": "2022-10-28",
        "source_url": (
            "https://www.sec.gov/Archives/edgar/data/1418091/"
            "000112329222000109/twitter13da.htm"
        ),
    }
}


SUPPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS manager_names (
    cik              TEXT NOT NULL,
    manager_name     TEXT NOT NULL,
    first_period     TEXT,
    last_period      TEXT,
    source           TEXT NOT NULL,
    PRIMARY KEY (cik, manager_name)
);

CREATE TABLE IF NOT EXISTS manager_relationships (
    accession_number TEXT NOT NULL,
    period_of_report TEXT,
    reporter_cik     TEXT NOT NULL,
    related_cik      TEXT NOT NULL,
    related_name     TEXT,
    sequence_number  TEXT NOT NULL DEFAULT '',
    source_table     TEXT NOT NULL,
    PRIMARY KEY (
        accession_number, reporter_cik, related_cik,
        sequence_number, source_table
    )
);

CREATE INDEX IF NOT EXISTS idx_manager_rel_reporter
    ON manager_relationships(reporter_cik, period_of_report);
CREATE INDEX IF NOT EXISTS idx_manager_rel_related
    ON manager_relationships(related_cik, period_of_report);

CREATE TABLE IF NOT EXISTS qa_cusip_sample (
    check_id          TEXT NOT NULL,
    period_of_report  TEXT NOT NULL,
    sample_order      INTEGER NOT NULL,
    cusip             TEXT NOT NULL,
    sec_name          TEXT,
    PRIMARY KEY (check_id, period_of_report, sample_order),
    UNIQUE (check_id, period_of_report, cusip)
);

CREATE TABLE IF NOT EXISTS cusip_mappings (
    cusip             TEXT PRIMARY KEY,
    ticker            TEXT,
    figi              TEXT,
    mapped_name       TEXT,
    exch_code         TEXT,
    mapping_status    TEXT NOT NULL,
    name_match_score  REAL,
    delisted_flag     INTEGER NOT NULL DEFAULT 0,
    delisted_date     TEXT,
    source            TEXT NOT NULL,
    source_url        TEXT,
    mapped_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS official_13f_securities (
    period_of_report  TEXT NOT NULL,
    cusip             TEXT NOT NULL,
    raw_description   TEXT,
    security_kind     TEXT NOT NULL,
    status            TEXT,
    source_url        TEXT NOT NULL,
    PRIMARY KEY (period_of_report, cusip)
);

CREATE TABLE IF NOT EXISTS qa_support_metadata (
    key                TEXT PRIMARY KEY,
    value              TEXT NOT NULL
);
"""


def ensure_support_schema(db) -> None:
    db.executescript(SUPPORT_SCHEMA)


def _zip_member(zf: zipfile.ZipFile, needle: str):
    needle = needle.lower()
    return next((name for name in zf.namelist() if needle in name.lower()), None)


def _rows(zf: zipfile.ZipFile, member: str | None) -> Iterable[dict[str, str]]:
    if not member:
        return ()

    def generate():
        with zf.open(member) as raw:
            with TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="") as text:
                yield from csv.DictReader(text, delimiter="\t")

    return generate()


def _parse_sec_date(raw: str | None) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw


def _upsert_manager_name(db, cik: str, name: str, period: str, source: str) -> None:
    cik = cik.strip().lstrip("0")
    name = name.strip()
    if not cik or not name:
        return
    db.execute(
        """
        INSERT INTO manager_names(cik, manager_name, first_period, last_period, source)
        VALUES (?,?,?,?,?)
        ON CONFLICT(cik, manager_name) DO UPDATE SET
            first_period = MIN(manager_names.first_period, excluded.first_period),
            last_period = MAX(manager_names.last_period, excluded.last_period)
        """,
        (cik, name, period, period, source),
    )


def build_manager_relationships(db, zip_dir: Path) -> dict[str, int]:
    """Build the manager graph from SEC COVERPAGE/OTHERMANAGER metadata.

    This is idempotent and deliberately excludes holdings values.  It can be
    re-run against the immutable ZIP archive without re-ingesting 120M rows.
    """
    ensure_support_schema(db)
    zip_paths = sorted(Path(zip_dir).glob("*.zip"))
    completed = db.execute(
        "SELECT value FROM qa_support_metadata WHERE key='manager_graph_zip_count'"
    ).fetchone()
    relation_rows = db.execute("SELECT COUNT(*) FROM manager_relationships").fetchone()[0]
    if completed and completed[0] == str(len(zip_paths)) and relation_rows > 0:
        return {
            "zips": len(zip_paths),
            "names": db.execute("SELECT COUNT(*) FROM manager_names").fetchone()[0],
            "relationships": relation_rows,
        }

    stats = {"zips": 0, "names": 0, "relationships": 0}

    for zip_path in zip_paths:
        with zipfile.ZipFile(zip_path) as zf:
            sub_member = _zip_member(zf, "submission.tsv")
            cover_member = _zip_member(zf, "coverpage.tsv")
            if not sub_member:
                continue

            submissions: dict[str, tuple[str, str]] = {}
            for row in _rows(zf, sub_member):
                accession = (row.get("ACCESSION_NUMBER") or "").strip()
                cik = (row.get("CIK") or "").strip().lstrip("0")
                period = _parse_sec_date(row.get("PERIODOFREPORT"))
                if accession and cik:
                    submissions[accession] = (cik, period)

            for row in _rows(zf, cover_member):
                accession = (row.get("ACCESSION_NUMBER") or "").strip()
                reporter = submissions.get(accession)
                if not reporter:
                    continue
                cik, period = reporter
                name = (row.get("FILINGMANAGER_NAME") or "").strip()
                if name:
                    _upsert_manager_name(db, cik, name, period, "COVERPAGE.tsv")
                    stats["names"] += 1

            for source_name, needle, sequence_field in (
                ("OTHERMANAGER.tsv", "othermanager.tsv", "OTHERMANAGER_SK"),
                ("OTHERMANAGER2.tsv", "othermanager2.tsv", "SEQUENCENUMBER"),
            ):
                member = _zip_member(zf, needle)
                for row in _rows(zf, member):
                    accession = (row.get("ACCESSION_NUMBER") or "").strip()
                    reporter = submissions.get(accession)
                    if not reporter:
                        continue
                    reporter_cik, period = reporter
                    related_cik = (row.get("CIK") or "").strip().lstrip("0")
                    related_name = (row.get("NAME") or "").strip()
                    sequence = (row.get(sequence_field) or "").strip()
                    if not related_cik or related_cik == reporter_cik:
                        continue
                    _upsert_manager_name(db, related_cik, related_name, period, source_name)
                    db.execute(
                        """
                        INSERT OR REPLACE INTO manager_relationships
                        (accession_number, period_of_report, reporter_cik,
                         related_cik, related_name, sequence_number, source_table)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            accession,
                            period,
                            reporter_cik,
                            related_cik,
                            related_name or None,
                            sequence,
                            source_name,
                        ),
                    )
                    stats["relationships"] += 1

        stats["zips"] += 1
        db.commit()

    db.execute(
        """
        INSERT OR REPLACE INTO qa_support_metadata(key,value)
        VALUES ('manager_graph_zip_count',?)
        """,
        (str(len(zip_paths)),),
    )
    db.commit()
    return stats


def economic_holding_signature(row: Mapping) -> tuple:
    """Exact signature used to remove the same disclosed economic position.

    CUSIP alone is intentionally insufficient: two linked legal entities can
    own different amounts of the same security and both amounts must survive.
    """
    return (
        row.get("cusip"),
        row.get("asset_class"),
        row.get("put_call"),
        row.get("sshprnamt"),
        row.get("value_usd"),
        row.get("voting_sole"),
        row.get("voting_shared"),
        row.get("voting_none"),
    )


def deduplicate_economic_holdings(rows: Sequence[Mapping]) -> tuple[list[Mapping], list[Mapping]]:
    """Return (unique rows, duplicate rows) using exact economic signatures."""
    unique: list[Mapping] = []
    duplicates: list[Mapping] = []
    seen: set[tuple] = set()
    for row in rows:
        signature = economic_holding_signature(row)
        if signature in seen:
            duplicates.append(row)
        else:
            seen.add(signature)
            unique.append(row)
    return unique, duplicates


_NAME_STOPWORDS = {
    "A", "ADR", "ADS", "AG", "B", "CL", "CLASS", "CO", "COM", "COMMON",
    "CORP", "CORPORATION", "ETF", "INC", "INCORPORATED", "LP", "LTD", "LLC",
    "NV", "PLC", "SA", "SH", "SHS", "THE", "TR", "TRUST",
}


def normalize_security_name(value: str | None) -> str:
    tokens = re.findall(r"[A-Z0-9]+", (value or "").upper())
    return " ".join(token for token in tokens if token not in _NAME_STOPWORDS)


def security_name_similarity(sec_name: str | None, mapped_name: str | None) -> float:
    left = normalize_security_name(sec_name)
    right = normalize_security_name(mapped_name)
    if not left or not right:
        return 0.0
    left_tokens, right_tokens = set(left.split()), set(right.split())
    jaccard = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    sequence = SequenceMatcher(None, left, right).ratio()
    return max(jaccard, sequence)


def load_official_13f_list(
    db,
    cache_dir: Path,
    sec_user_agent: str,
    period: str = CH13_PERIOD,
) -> int:
    """Download and parse the official SEC 2020Q1 Section 13(f) list.

    The archived list is a fixed-layout PDF.  Only CUSIP, security kind and
    status are needed to define the valid point-in-time universe.
    """
    ensure_support_schema(db)
    parser_version = db.execute(
        "SELECT value FROM qa_support_metadata WHERE key='official_13f_parser_version'"
    ).fetchone()
    existing = db.execute(
        "SELECT COUNT(*) FROM official_13f_securities WHERE period_of_report=?",
        (period,),
    ).fetchone()[0]
    if (
        existing > 1_000
        and parser_version
        and parser_version[0] == OFFICIAL_13F_PARSER_VERSION
    ):
        return existing

    if not sec_user_agent:
        raise RuntimeError("SEC_USER_AGENT is required to download the official 13F list")
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = cache_dir / "sec_13f_official_2020q1.pdf"
    if not pdf_path.exists() or pdf_path.stat().st_size < 100_000:
        response = requests.get(
            SEC_13F_2020Q1_URL,
            headers={"User-Agent": sec_user_agent},
            timeout=120,
        )
        response.raise_for_status()
        pdf_path.write_bytes(response.content)

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required: pip install -r requirements.txt") from exc

    # pypdf emits the fixed CUSIP columns as three groups: 6 + 2 + 1 chars.
    row_pattern = re.compile(r"^\s*([0-9A-Z]{6})\s+([0-9A-Z]{2})\s+([0-9A-Z])\s+(.+?)\s*$")
    parsed: dict[str, tuple[str, str, str]] = {}
    for page in PdfReader(str(pdf_path)).pages:
        for line in (page.extract_text() or "").splitlines():
            match = row_pattern.match(line.upper())
            if not match:
                continue
            cusip = "".join(match.group(index) for index in (1, 2, 3))
            description = match.group(4).strip()
            if not re.fullmatch(r"[A-Z0-9]{9}", cusip):
                continue
            if re.search(r"\bCALL\b", description):
                kind = "call"
            elif re.search(r"\bPUT\b", description):
                kind = "put"
            elif re.search(r"\b(NOTE|NOTES|DEBT|BOND|BONDS|MTN|DEBENTURE)\b", description):
                kind = "debt"
            elif re.search(r"\b(PFD|PREFERRED|PREFERENCE)\b", description):
                kind = "preferred"
            elif "W EXP" in description or re.search(r"\bWARRANT", description):
                kind = "warrant"
            elif re.search(r"\bRIGHTS?\b", description):
                kind = "right"
            elif re.search(r"\bUNIT\b", description):
                kind = "unit"
            else:
                kind = "equity"
            status = "DELETED" if description.endswith(" DELETED") else (
                "ADDED" if description.endswith(" ADDED") else ""
            )
            parsed[cusip] = (description, kind, status)

    if len(parsed) < 5_000:
        raise RuntimeError(f"Official SEC 13F PDF parse produced only {len(parsed)} rows")

    db.execute("DELETE FROM official_13f_securities WHERE period_of_report=?", (period,))
    db.executemany(
        """
        INSERT INTO official_13f_securities
        (period_of_report,cusip,raw_description,security_kind,status,source_url)
        VALUES (?,?,?,?,?,?)
        """,
        [
            (period, cusip, description, kind, status, SEC_13F_2020Q1_URL)
            for cusip, (description, kind, status) in parsed.items()
        ],
    )
    db.execute(
        """
        INSERT OR REPLACE INTO qa_support_metadata(key,value)
        VALUES ('official_13f_parser_version',?)
        """,
        (OFFICIAL_13F_PARSER_VERSION,),
    )
    db.commit()
    return len(parsed)


def freeze_ch13_sample(
    db,
    period: str = CH13_PERIOD,
    sample_size: int = CH13_SAMPLE_SIZE,
    seed: str = CH13_SEED,
) -> list[dict]:
    """Freeze a deterministic random-like sample of 100 2020Q1 CUSIPs."""
    ensure_support_schema(db)
    sample_method = db.execute(
        "SELECT value FROM qa_support_metadata WHERE key='ch13_sample_method'"
    ).fetchone()
    if not sample_method or sample_method[0] != CH13_SAMPLE_METHOD:
        db.execute("DELETE FROM qa_cusip_sample WHERE check_id='CH-13'")
        db.execute(
            """
            INSERT OR REPLACE INTO qa_support_metadata(key,value)
            VALUES ('ch13_sample_method',?)
            """,
            (CH13_SAMPLE_METHOD,),
        )
        db.commit()

    stored = db.execute(
        """
        SELECT cusip, sec_name, sample_order
        FROM qa_cusip_sample
        WHERE check_id='CH-13' AND period_of_report=?
        ORDER BY sample_order
        """,
        (period,),
    ).fetchall()
    if len(stored) == sample_size:
        return [dict(row) for row in stored]

    candidates = db.execute(
        """
        SELECT UPPER(li.cusip) AS cusip, official.raw_description AS sec_name
        FROM filing_events fe
        JOIN filing_line_items li ON li.accession_number=fe.accession_number
        JOIN official_13f_securities official
          ON official.period_of_report=fe.period_of_report
         AND official.cusip=UPPER(li.cusip)
        WHERE fe.period_of_report=?
          AND fe.form_type='13F-HR'
          AND li.asset_class='cash_equity'
          AND length(trim(li.cusip))=9
          AND official.security_kind='equity'
          AND official.status!='DELETED'
        GROUP BY UPPER(li.cusip), official.raw_description
        """,
        (period,),
    ).fetchall()
    candidates = [
        dict(row) for row in candidates
        if re.fullmatch(r"[A-Z0-9]{9}", (row["cusip"] or "").upper())
    ]
    if len(candidates) < sample_size:
        raise RuntimeError(
            f"CH-13 universe only has {len(candidates)} valid CUSIPs; need {sample_size}"
        )

    ranked = sorted(
        candidates,
        key=lambda row: hashlib.sha256(
            f"{seed}:{row['cusip']}".encode("utf-8")
        ).hexdigest(),
    )[:sample_size]

    db.execute(
        "DELETE FROM qa_cusip_sample WHERE check_id='CH-13' AND period_of_report=?",
        (period,),
    )
    for order, row in enumerate(ranked, start=1):
        db.execute(
            """
            INSERT INTO qa_cusip_sample
            (check_id, period_of_report, sample_order, cusip, sec_name)
            VALUES ('CH-13',?,?,?,?)
            """,
            (period, order, row["cusip"], row.get("sec_name")),
        )
    db.commit()
    return [dict(row, sample_order=i) for i, row in enumerate(ranked, start=1)]


def _choose_openfigi_result(candidates: Sequence[Mapping]) -> Mapping | None:
    candidates = [row for row in candidates if row.get("ticker")]
    if not candidates:
        return None

    def score(row: Mapping) -> tuple:
        return (
            row.get("exchCode") == "US",
            row.get("figi") == row.get("compositeFIGI"),
            row.get("marketSector") == "Equity",
            row.get("securityType2") in {"Common Stock", "Mutual Fund", "ETP"},
        )

    return max(candidates, key=score)


def _openfigi_post(jobs: list[dict], api_key: str | None) -> list[dict]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    for attempt in range(5):
        response = requests.post(OPENFIGI_URL, headers=headers, json=jobs, timeout=60)
        if response.status_code == 429:
            wait = float(response.headers.get("ratelimit-reset", 3)) + 0.25
            time.sleep(max(wait, 1.0))
            continue
        if response.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) != len(jobs):
            raise RuntimeError("OpenFIGI returned an unexpected response shape")
        return payload
    raise RuntimeError("OpenFIGI request failed after retries")


def prepare_ch13_mappings(
    db,
    api_key: str | None = None,
    cache_dir: Path | None = None,
    sec_user_agent: str = "",
    period: str = CH13_PERIOD,
    sample_size: int = CH13_SAMPLE_SIZE,
) -> dict[str, int]:
    """Map the frozen CH-13 sample and retain explicit unmapped rows."""
    ensure_support_schema(db)
    official_count = load_official_13f_list(
        db,
        cache_dir=cache_dir or Path(__file__).parent / "data" / "cache",
        sec_user_agent=sec_user_agent,
        period=period,
    )
    sample = freeze_ch13_sample(db, period=period, sample_size=sample_size)
    existing = {
        row[0] for row in db.execute(
            "SELECT cusip FROM cusip_mappings WHERE cusip IN (%s)"
            % ",".join("?" for _ in sample),
            [row["cusip"] for row in sample],
        ).fetchall()
    }
    pending = [row for row in sample if row["cusip"] not in existing]
    batch_size = 100 if api_key else 5
    now = datetime.utcnow().isoformat()

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        jobs = []
        for row in batch:
            cusip = row["cusip"].upper()
            jobs.append(
                {
                    "idType": "ID_CINS" if cusip[0].isalpha() else "ID_CUSIP",
                    "idValue": cusip,
                    "marketSecDes": "Equity",
                    "includeUnlistedEquities": True,
                }
            )
        payload = _openfigi_post(jobs, api_key)
        for source_row, result in zip(batch, payload):
            chosen = _choose_openfigi_result(result.get("data", []))
            status = "mapped" if chosen else "unmapped"
            mapped_name = chosen.get("name") if chosen else None
            db.execute(
                """
                INSERT INTO cusip_mappings
                (cusip, ticker, figi, mapped_name, exch_code, mapping_status,
                 name_match_score, delisted_flag, source, mapped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(cusip) DO UPDATE SET
                    ticker=excluded.ticker,
                    figi=excluded.figi,
                    mapped_name=excluded.mapped_name,
                    exch_code=excluded.exch_code,
                    mapping_status=excluded.mapping_status,
                    name_match_score=excluded.name_match_score,
                    source=excluded.source,
                    mapped_at=excluded.mapped_at
                """,
                (
                    source_row["cusip"],
                    chosen.get("ticker") if chosen else None,
                    chosen.get("figi") if chosen else None,
                    mapped_name,
                    chosen.get("exchCode") if chosen else None,
                    status,
                    security_name_similarity(source_row.get("sec_name"), mapped_name),
                    0,
                    "OpenFIGI v3",
                    now,
                ),
            )
        db.commit()
        # Unauthenticated limit is 25 requests/minute.  Twenty 5-job requests
        # fit in one window, but this small pause avoids bursting the service.
        if not api_key:
            time.sleep(2.5)

    # The sample is versioned and can change while a cached CUSIP mapping is
    # reused.  Recompute issuer-name verification against the current official
    # SEC description rather than retaining a stale score from an older sample.
    for row in db.execute(
        """
        SELECT s.cusip, s.sec_name, m.mapped_name
        FROM qa_cusip_sample s
        JOIN cusip_mappings m ON m.cusip=s.cusip
        WHERE s.check_id='CH-13' AND s.period_of_report=?
          AND m.mapping_status='mapped'
        """,
        (period,),
    ).fetchall():
        db.execute(
            "UPDATE cusip_mappings SET name_match_score=? WHERE cusip=?",
            (security_name_similarity(row["sec_name"], row["mapped_name"]), row["cusip"]),
        )
    db.commit()

    # Delisted securities are retained explicitly, never silently dropped.
    for cusip, known in KNOWN_DELISTED.items():
        db.execute(
            """
            INSERT INTO cusip_mappings
            (cusip, ticker, mapped_name, mapping_status, name_match_score,
             delisted_flag, delisted_date, source, source_url, mapped_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(cusip) DO UPDATE SET
                ticker=COALESCE(cusip_mappings.ticker, excluded.ticker),
                mapped_name=COALESCE(cusip_mappings.mapped_name, excluded.mapped_name),
                mapping_status='mapped',
                name_match_score=MAX(COALESCE(cusip_mappings.name_match_score, 0), excluded.name_match_score),
                delisted_flag=1,
                delisted_date=excluded.delisted_date,
                source=excluded.source,
                source_url=excluded.source_url,
                mapped_at=excluded.mapped_at
            """,
            (
                cusip,
                known["ticker"],
                known["name"],
                "mapped",
                1.0,
                1,
                known["delisted_date"],
                "SEC known-delisted reference",
                known["source_url"],
                now,
            ),
        )
    db.commit()

    mapped = db.execute(
        """
        SELECT COUNT(*)
        FROM qa_cusip_sample s
        JOIN cusip_mappings m USING(cusip)
        WHERE s.check_id='CH-13' AND s.period_of_report=?
          AND m.mapping_status='mapped' AND m.ticker IS NOT NULL
        """,
        (period,),
    ).fetchone()[0]
    return {
        "official_sec_cusips": official_count,
        "sample": sample_size,
        "mapped": mapped,
        "requested": len(pending),
    }
