"""Synthetic SQLite unit tests for Stage C Part C1 pilot extractor module."""

from datetime import date
from pathlib import Path
import sqlite3
import pytest

from research.smart_money.m0.src.pilot_extractor import (
    check_source_db_preflight,
    classify_other_manager,
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


def test_classify_other_manager_robustness():
    """Test robust classification of other_manager into blank, single numeric, multi-numeric, and free-text name."""
    assert classify_other_manager(None) == ("BLANK", [])
    assert classify_other_manager("") == ("BLANK", [])
    assert classify_other_manager("   ") == ("BLANK", [])

    assert classify_other_manager("4") == ("SINGLE_NUMERIC", ["4"])
    assert classify_other_manager("193370") == ("SINGLE_NUMERIC", ["193370"])

    # Multi-numeric with commas, spaces, or mixed
    assert classify_other_manager("1,2,4,11") == ("MULTI_NUMERIC_LIST", ["1", "2", "4", "11"])
    assert classify_other_manager("1 3 4") == ("MULTI_NUMERIC_LIST", ["1", "3", "4"])
    assert classify_other_manager("1, 4") == ("MULTI_NUMERIC_LIST", ["1", "4"])
    assert classify_other_manager("2, 3, 4, 7, 10") == ("MULTI_NUMERIC_LIST", ["2", "3", "4", "7", "10"])

    # Free-text names with spaces (must NOT be classified as multi-sequence list)
    assert classify_other_manager("Blue Chip Partners LLC") == ("FREE_TEXT_NAME", ["Blue", "Chip", "Partners", "LLC"])
    assert classify_other_manager("PARAMETRIC PORTFOLIO ASSOCIATES LLC") == ("FREE_TEXT_NAME", ["PARAMETRIC", "PORTFOLIO", "ASSOCIATES", "LLC"])


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


def test_berkshire_apple_raw_vs_resolved_and_ineligibility(tmp_path: Path):
    """Test Berkshire Apple extraction reports raw anchor match, unresolved other_manager, and confidential ineligibility."""
    db_file = tmp_path / "berkshire_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    acc = "0000950123-24-002518"
    cik = "1067983"
    period = "2023-12-31"

    # Insert filing event with confidential omit = 1
    conn.execute(
        """
        INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type, is_confidential_omit)
        VALUES (?, ?, ?, '2024-02-14T21:02:18.000Z', '13F-HR', 1);
        """,
        (acc, cik, period),
    )

    # Insert 2 matching rows totaling 905,560,000 shares with comma-separated and discrete other_manager
    conn.execute(
        """
        INSERT INTO filing_line_items (accession_number, line_seq, cusip, security_name, sshprnamt, value_usd, asset_class, investment_discretion, other_manager)
        VALUES (?, 1, '037833100', 'APPLE INC', 900000000, 180000000000, 'cash_equity', 'DFND', '1,2,4,11'),
               (?, 2, '037833100', 'APPLE INC', 5560000, 1112000000, 'cash_equity', 'DFND', '4');
        """,
        (acc, acc),
    )
    conn.commit()
    conn.close()

    ro_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    res = extract_berkshire_apple_2023q4(ro_conn)
    ro_conn.close()

    assert res["raw_matching_rows_count"] == 2
    assert res["raw_total_aggregate_shares"] == 905_560_000
    assert res["anchor_raw_match"] is True
    assert res["unresolved_rows_count"] == 2
    assert res["primary_resolved_shares"] == 0
    assert res["multi_sequence_rows_count"] == 1
    assert res["is_primary_eligible"] is False
    assert any("CONFIDENTIAL_TREATMENT_OMISSION" in r for r in res["ineligibility_reasons"])


def test_point72_discovery_real_timestamps_and_unknown_owner_handling(tmp_path: Path):
    """Test Point72 discovery uses actual acceptance datetimes and does NOT default unknown economic owners."""
    db_file = tmp_path / "p72_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    period = "2019-12-31"
    conn.execute("INSERT INTO manager_names VALUES ('1603466', 'Point72 Asset Management, L.P.', '2014-03-31', '2026-03-31', 'sec');")

    conn.execute(
        """
        INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type)
        VALUES ('0001567619-20-004063', '1603466', ?, '2020-02-14T21:44:41.000Z', '13F-HR'),
               ('0001567619-20-004066', '1599822', ?, '2020-02-14T16:47:23.000Z', '13F-HR');
        """,
        (period, period),
    )

    conn.execute(
        """
        INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, related_name, sequence_number, source_table)
        VALUES ('0001567619-20-004066', ?, '1599822', '1603466', 'Point72 Asset Management, L.P.', '1', 'OTHERMANAGER2.tsv');
        """,
        (period,),
    )

    conn.execute(
        """
        INSERT INTO filing_line_items (accession_number, line_seq, cusip, security_name, sshprnamt, value_usd, asset_class, other_manager)
        VALUES ('0001567619-20-004066', 1, '026874784', 'AIG INC', 10000, 500000, 'cash_equity', '1'),
               ('0001567619-20-004066', 2, '026874784', 'AIG INC', 5000, 250000, 'cash_equity', '999'),
               ('0001567619-20-004063', 1, '026874784', 'AIG INC', 20000, 1000000, 'cash_equity', NULL);
        """,
    )
    conn.commit()
    conn.close()

    ro_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    res = extract_point72_2019q4_discovery(ro_conn)
    ro_conn.close()

    assert res["status"] == "PROPOSED PENDING CODEX MANUAL FREEZE"
    assert res["canonical_entity_id"] == "0001599822"
    assert res["component_closed_ciks"] == ["0001599822", "0001603466"]
    assert res["unresolved_rows_count"] == 1
    assert res["unresolved_shares_total"] == 5000
    assert res["manager_relationships"][0]["acceptance_datetime"] == "2020-02-14T16:47:23.000Z"


def test_point72_late_filing_exclusion(tmp_path: Path):
    """Test that late filings in Point72 fixture are excluded from on-time counts."""
    db_file = tmp_path / "p72_late_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    period = "2019-12-31"
    conn.execute("INSERT INTO manager_names VALUES ('1603466', 'Point72 Asset Management, L.P.', '2014-03-31', '2026-03-31', 'sec');")

    conn.execute(
        """
        INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type, is_confidential_omit)
        VALUES ('0001567619-20-004063', '1603466', ?, '2020-02-14T21:44:41.000Z', '13F-HR', 0),
               ('0001567619-20-009999', '1603466', ?, '2020-02-20T10:00:00.000Z', '13F-HR', 1);
        """,
        (period, period),
    )
    conn.commit()
    conn.close()

    ro_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    res = extract_point72_2019q4_discovery(ro_conn)
    ro_conn.close()

    assert res["all_period_confidential_filings_count"] == 1
    assert res["on_time_confidential_filings_count"] == 0


def test_two_filer_component_intra_entity_dedup_in_split_pair(tmp_path: Path):
    """Test that two origin filers in same component with identical economic signature deduplicate to 1 disclosure."""
    db_file = tmp_path / "two_filer_dedup_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    # Setup 20 entities. Entity 1 has two origin filers: CIK 1 and CIK 2.
    for i in range(1, 21):
        cik = f"{i:010d}"
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR');",
            (f"ACC_PREV_{i}", cik, q_prev),
        )
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', '13F-HR');",
            (f"ACC_CURR_{i}", cik, q_curr),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 100, 100000, 'cash_equity');",
            (f"ACC_PREV_{i}", cusip),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity');",
            (f"ACC_CURR_{i}", cusip),
        )

    # Add relationship connecting CIK 1 and CIK 2
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        ("ACC_PREV_2", q_prev),
    )
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        ("ACC_CURR_2", q_curr),
    )

    # Let CIK 2 file a duplicate disclosure pointing economic owner to CIK 1
    conn.execute(
        "UPDATE filing_line_items SET other_manager = '1' WHERE accession_number IN ('ACC_PREV_2', 'ACC_CURR_2');"
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

    assert res["eligible_continuous_entity_count"] == 19
    assert res["adjusted_median_ratio"] == 1.0


def test_split_pair_membership_incomplete_exclusion(tmp_path: Path):
    """Test that a component with membership change between Q-1 and Q is excluded by MEMBERSHIP_INCOMPLETE."""
    db_file = tmp_path / "membership_incomplete_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    for i in range(1, 21):
        cik = f"{i:010d}"
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR');",
            (f"ACC_PREV_{i}", cik, q_prev),
        )
        if i != 2:
            conn.execute(
                "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', '13F-HR');",
                (f"ACC_CURR_{i}", cik, q_curr),
            )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 100, 100000, 'cash_equity');",
            (f"ACC_PREV_{i}", cusip),
        )
        if i != 2:
            conn.execute(
                "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity');",
                (f"ACC_CURR_{i}", cusip),
            )

    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        ("ACC_PREV_2", q_prev),
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

    assert res["component_level_exclusions"]["membership_incomplete_components_excluded"] == 1
    assert res["eligible_continuous_entity_count"] == 18


def test_split_pair_late_relationship_edge_exclusion(tmp_path: Path):
    """Test that a late relationship edge is excluded and does not merge components."""
    db_file = tmp_path / "late_edge_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    for i in range(1, 21):
        cik = f"{i:010d}"
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR');",
            (f"ACC_PREV_{i}", cik, q_prev),
        )
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', '13F-HR');",
            (f"ACC_CURR_{i}", cik, q_curr),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 100, 100000, 'cash_equity');",
            (f"ACC_PREV_{i}", cusip),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity');",
            (f"ACC_CURR_{i}", cusip),
        )

    # Insert a LATE filing event for accession ACC_LATE (filed 2024-05-20 > deadline 2024-05-15)
    conn.execute(
        "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES ('ACC_LATE', '0000000002', ?, '2024-05-20T10:00:00Z', '13F-HR');",
        (q_prev,),
    )
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES ('ACC_LATE', ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        (q_prev,),
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

    # Late edge excluded -> CIK 1 and CIK 2 remain separate components (20 total components)
    assert res["global_dataset_context"]["total_on_time_filers_q_prev"] == 20
    assert res["eligible_continuous_entity_count"] == 20
    assert res["global_dataset_context"]["late_filings_excluded_q_prev"] == 1


def test_split_pair_all_members_confidential_gate_zero_target_rows(tmp_path: Path):
    """Counterexample: Filers A and B in one component, only A holds target, B has confidential omission -> component excluded."""
    db_file = tmp_path / "conf_zero_target_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    for i in range(1, 21):
        cik = f"{i:010d}"
        is_conf_prev = 1 if i == 2 else 0

        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type, is_confidential_omit) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR', ?);",
            (f"ACC_PREV_{i}", cik, q_prev, is_conf_prev),
        )
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', '13F-HR');",
            (f"ACC_CURR_{i}", cik, q_curr),
        )

        c_insert = "OTHER_CUSIP" if i == 2 else cusip
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 100, 100000, 'cash_equity');",
            (f"ACC_PREV_{i}", c_insert),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity');",
            (f"ACC_CURR_{i}", c_insert),
        )

    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        ("ACC_PREV_2", q_prev),
    )
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        ("ACC_CURR_2", q_curr),
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

    assert res["component_level_exclusions"]["confidential_omission_components_excluded"] == 1
    assert res["eligible_continuous_entity_count"] == 18


def test_split_pair_all_members_unresolved_amendment_zero_target_rows(tmp_path: Path):
    """Counterexample: Filers A and B in one component, only A holds target, B has UNKNOWN amendment -> component excluded."""
    db_file = tmp_path / "amend_zero_target_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    for i in range(1, 21):
        cik = f"{i:010d}"
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR');",
            (f"ACC_PREV_{i}", cik, q_prev),
        )

        form_q = "13F-HR/A" if i == 2 else "13F-HR"
        amend_q = "UNKNOWN" if i == 2 else None
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type, amendment_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', ?, ?);",
            (f"ACC_CURR_{i}", cik, q_curr, form_q, amend_q),
        )

        c_insert = "OTHER_CUSIP" if i == 2 else cusip
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 100, 100000, 'cash_equity');",
            (f"ACC_PREV_{i}", c_insert),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity');",
            (f"ACC_CURR_{i}", c_insert),
        )

    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        ("ACC_PREV_2", q_prev),
    )
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER.tsv');",
        ("ACC_CURR_2", q_curr),
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

    assert res["component_level_exclusions"]["amendment_unresolved_components_excluded"] == 1
    assert res["eligible_continuous_entity_count"] == 18


def test_13f_nt_exclusion_from_holdings_and_graph(tmp_path: Path):
    """Test that 13F-NT and 13F-NT/A notice filings are strictly excluded from holdings and relationship graph."""
    db_file = tmp_path / "nt_exclusion_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    for i in range(1, 21):
        cik = f"{i:010d}"
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR');",
            (f"ACC_PREV_{i}", cik, q_prev),
        )
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', '13F-HR');",
            (f"ACC_CURR_{i}", cik, q_curr),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 100, 100000, 'cash_equity');",
            (f"ACC_PREV_{i}", cusip),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity');",
            (f"ACC_CURR_{i}", cusip),
        )

    # Insert a 13F-NT notice filing for CIK 999 with a relationship edge connecting CIK 1 and CIK 999
    conn.execute(
        "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES ('ACC_NT_999', '0000000999', ?, '2024-05-10T10:00:00Z', '13F-NT');",
        (q_prev,),
    )
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES ('ACC_NT_999', ?, '0000000999', '0000000001', '1', 'OTHERMANAGER.tsv');",
        (q_prev,),
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

    assert res["global_dataset_context"]["total_on_time_filers_q_prev"] == 20
    assert res["eligible_continuous_entity_count"] == 20


def test_split_pair_unknown_or_cross_component_owner_excluded(tmp_path: Path):
    """Counterexample for P1-unsafe-default: Unknown or unmapped economic owner is excluded and counted as unresolved."""
    db_file = tmp_path / "unsafe_default_test.db"
    conn = _init_synthetic_phase0_db(db_file)

    q_prev = "2024-03-31"
    q_curr = "2024-06-30"
    cusip = "67066G104"

    for i in range(1, 21):
        cik = f"{i:010d}"
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-05-10T10:00:00Z', '13F-HR');",
            (f"ACC_PREV_{i}", cik, q_prev),
        )
        conn.execute(
            "INSERT INTO filing_events (accession_number, cik, period_of_report, acceptance_datetime, form_type) VALUES (?, ?, ?, '2024-08-10T10:00:00Z', '13F-HR');",
            (f"ACC_CURR_{i}", cik, q_curr),
        )
        # Filer 1 files with unknown sequence 999 (not mapped to any manager in manager_relationships)
        om_prev = "999" if i == 1 else None
        om_curr = "999" if i == 1 else None
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class, other_manager) VALUES (?, 1, ?, 100, 100000, 'cash_equity', ?);",
            (f"ACC_PREV_{i}", cusip, om_prev),
        )
        conn.execute(
            "INSERT INTO filing_line_items (accession_number, line_seq, cusip, sshprnamt, value_usd, asset_class, other_manager) VALUES (?, 1, ?, 1000, 1000000, 'cash_equity', ?);",
            (f"ACC_CURR_{i}", cusip, om_curr),
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

    # Filer 1's position is strictly excluded because sequence 999 has no manager mapping
    # Filer 1 is NOT defaulted into Component 1
    # It is strictly counted as unresolved rows in both Q-1 and Q
    assert res["component_level_exclusions"]["unresolved_ownership_rows_excluded_q_prev"] == 1
    assert res["component_level_exclusions"]["unresolved_ownership_rows_excluded_q_curr"] == 1
    # 19 continuous holders remain (CIK 2 through CIK 20)
    assert res["eligible_continuous_entity_count"] == 19
