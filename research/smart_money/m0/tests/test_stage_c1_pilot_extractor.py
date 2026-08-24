"""Synthetic SQLite unit tests for Stage C Part C1 pilot extractor module."""

from datetime import date
from pathlib import Path
import sqlite3
import pytest

from research.smart_money.m0.src.pilot_extractor import (
    check_source_db_preflight,
    extract_berkshire_apple_2023q4,
    extract_point72_2019q4_discovery,
    extract_split_pilot_pair,
)


def _init_synthetic_phase0_db(db_path: Path) -> sqlite3.Connection:
    """Initialize synthetic Phase 0 SQLite DB schema for unit testing."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE filing_events (
            accession_number TEXT PRIMARY KEY,
            cik TEXT NOT NULL,
            period_of_report TEXT NOT NULL,
            acceptance_datetime TEXT,
            filing_date TEXT,
            form_type TEXT,
            amendment_type TEXT,
            supersedes_accession TEXT,
            is_confidential_omit INTEGER DEFAULT 0,
            conf_flag_quality TEXT,
            table_value_total INTEGER,
            ingest_zip TEXT,
            ingest_ts TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE filing_line_items (
            accession_number TEXT NOT NULL,
            line_seq INTEGER NOT NULL,
            cusip TEXT,
            security_name TEXT,
            title_of_class TEXT,
            raw_value_reported INTEGER,
            value_usd INTEGER,
            sshprnamt INTEGER,
            sshprnamttype TEXT,
            put_call TEXT,
            investment_discretion TEXT,
            other_manager TEXT,
            voting_sole INTEGER,
            voting_shared INTEGER,
            voting_none INTEGER,
            asset_class TEXT,
            censor_flag TEXT,
            PRIMARY KEY (accession_number, line_seq)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE manager_names (
            cik TEXT NOT NULL,
            manager_name TEXT NOT NULL,
            first_period TEXT,
            last_period TEXT,
            source TEXT NOT NULL,
            PRIMARY KEY (cik, manager_name)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE manager_relationships (
            accession_number TEXT NOT NULL,
            period_of_report TEXT,
            reporter_cik TEXT NOT NULL,
            related_cik TEXT NOT NULL,
            related_name TEXT,
            sequence_number TEXT NOT NULL DEFAULT '',
            source_table TEXT NOT NULL,
            PRIMARY KEY (accession_number, reporter_cik, related_cik, sequence_number, source_table)
        );
        """
    )
    conn.commit()
    return conn


def test_check_source_db_preflight(tmp_path: Path):
    """Test preflight verification on synthetic DB and rejection of missing DB / sidecars."""
    db_file = tmp_path / "test_phase0.db"
    conn = _init_synthetic_phase0_db(db_file)
    conn.close()

    preflight = check_source_db_preflight(db_file)
    assert preflight["db_filename"] == "test_phase0.db"
    assert preflight["size_bytes"] > 0
    assert preflight["query_only_pragma"] == 1

    # Missing DB
    with pytest.raises(FileNotFoundError):
        check_source_db_preflight(tmp_path / "non_existent.db")

    # Sidecar rejection
    wal_file = tmp_path / "test_phase0.db-wal"
    wal_file.write_bytes(b"wal_dummy")
    with pytest.raises(ValueError, match="sibling sidecar"):
        check_source_db_preflight(db_file)


def test_synthetic_berkshire_apple_extraction(tmp_path: Path):
    """Test Berkshire Apple 2023Q4 accession aggregation logic on synthetic data."""
    db_file = tmp_path / "berkshire_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    acc = "0000950123-24-002518"
    cik = "1067983"
    period = "2023-12-31"

    # Insert filing event
    conn.execute(
        """
        INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type)
        VALUES (?, ?, ?, '2024-02-14T21:02:18.000Z', '13F-HR');
        """,
        (acc, cik, period),
    )

    # Insert 2 matching rows totaling 905,560,000 shares
    conn.execute(
        """
        INSERT INTO filing_line_items (accession_number, line_seq, cusip, security_name, sshprnamt, value_usd, asset_class, investment_discretion)
        VALUES (?, 1, '037833100', 'APPLE INC', 900000000, 180000000000, 'cash_equity', 'DFND'),
               (?, 2, '037833100', 'APPLE INC', 5560000, 1112000000, 'cash_equity', 'DFND');
        """,
        (acc, acc),
    )
    conn.commit()
    conn.close()

    ro_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    res = extract_berkshire_apple_2023q4(ro_conn)
    ro_conn.close()

    assert res["raw_matching_rows_count"] == 2
    assert res["total_aggregate_shares"] == 905_560_000
    assert res["preregistered_expected_anchor"] == 905_560_000
    assert res["anchor_match"] is True


def test_synthetic_point72_discovery(tmp_path: Path):
    """Test Point72 multi-manager relationship discovery and proposed fixture generation on synthetic DB."""
    db_file = tmp_path / "p72_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    period = "2019-12-31"
    # Insert manager names
    conn.execute("INSERT INTO manager_names VALUES ('1603466', 'Point72 Asset Management, L.P.', '2014-03-31', '2026-03-31', 'sec');")
    conn.execute("INSERT INTO manager_names VALUES ('1599822', 'Point72 Asia (Hong Kong) Ltd', '2014-03-31', '2026-03-31', 'sec');")

    # Insert filing events
    conn.execute(
        """
        INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type)
        VALUES ('0001567619-20-004063', '1603466', ?, '2020-02-14T21:44:41.000Z', '13F-HR'),
               ('0001567619-20-004066', '1599822', ?, '2020-02-14T16:47:23.000Z', '13F-HR');
        """,
        (period, period),
    )

    # Insert relationships
    conn.execute(
        """
        INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, related_name, sequence_number, source_table)
        VALUES ('0001567619-20-004066', ?, '1599822', '1603466', 'Point72 Asset Management, L.P.', '1', 'OTHERMANAGER2.tsv');
        """,
        (period,),
    )

    # Insert line items
    conn.execute(
        """
        INSERT INTO filing_line_items (accession_number, line_seq, cusip, security_name, sshprnamt, value_usd, asset_class, other_manager)
        VALUES ('0001567619-20-004066', 1, '026874784', 'AIG INC', 10000, 500000, 'cash_equity', '1'),
               ('0001567619-20-004063', 1, '026874784', 'AIG INC', 20000, 1000000, 'cash_equity', NULL);
        """,
    )
    conn.commit()
    conn.close()

    ro_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    res = extract_point72_2019q4_discovery(ro_conn)
    ro_conn.close()

    assert res["status"] == "PROPOSED PENDING CODEX MANUAL FREEZE"
    assert res["accessions_count"] == 2
    assert res["canonical_entity_id"] == "0001599822"


def test_synthetic_split_pilot_pair_waterfall(tmp_path: Path):
    """Test full split pilot pair extraction, pipeline state machine, and waterfall execution on synthetic DB."""
    db_file = tmp_path / "split_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    # Insert 25 filers with 10:1 split across consecutive quarters
    for i in range(1, 26):
        cik = f"{i:010d}"
        acc_prev = f"ACC_PREV_{i}"
        acc_curr = f"ACC_CURR_{i}"

        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR');",
            (acc_prev, cik, q_prev),
        )
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', '13F-HR');",
            (acc_curr, cik, q_curr),
        )

        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 100, 100000, 'cash_equity');",
            (acc_prev, cusip),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity');",
            (acc_curr, cusip),
        )

    conn.commit()
    conn.close()

    ro_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    res = extract_split_pilot_pair(
        conn=ro_conn,
        cusip=cusip,
        stock_symbol="NVDA",
        q_prev=q_prev,
        q_curr=q_curr,
        split_factor=10.0,
        ex_date="2024-06-10",
    )
    ro_conn.close()

    assert res["eligible_continuous_entity_count"] == 25
    assert res["raw_median_ratio"] == pytest.approx(10.0)
    assert res["adjusted_median_ratio"] == pytest.approx(1.0)
    assert res["waterfall_state"] == "KNOWN_SPLIT_PASS"
    assert res["waterfall_action"] == "INCLUDE"
    assert res["is_in_contract_pass_range"] is True
