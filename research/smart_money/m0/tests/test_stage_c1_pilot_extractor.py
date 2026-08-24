"""Synthetic SQLite unit tests for Stage C Part C1 pilot extractor module."""

from datetime import date
from pathlib import Path
import sqlite3
import pytest

from research.smart_money.m0.src.pilot_extractor import (
    build_entity_graph_edges,
    build_line_level_manager_map,
    check_source_db_preflight,
    classify_other_manager,
    extract_berkshire_apple_2023q4,
    extract_point72_2019q4_discovery,
    extract_split_pilot_pair,
    resolve_owner_component_strict,
)
from research.smart_money.m0.src.run_c1_discovery import format_markdown_report


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
    """Test robust classification of other_manager into blank, official N/A, zero sentinel, single numeric, multi-numeric, and free-text name."""
    assert classify_other_manager(None) == ("BLANK", [])
    assert classify_other_manager("") == ("BLANK", [])
    assert classify_other_manager("   ") == ("BLANK", [])

    assert classify_other_manager("N/A") == ("OFFICIAL_NA", ["N/A"])
    assert classify_other_manager("n/a") == ("OFFICIAL_NA", ["N/A"])
    assert classify_other_manager("N/a") == ("OFFICIAL_NA", ["N/A"])

    assert classify_other_manager("0") == ("ZERO_SENTINEL", ["0"])
    assert classify_other_manager("4") == ("SINGLE_NUMERIC", ["4"])
    assert classify_other_manager("193370") == ("SINGLE_NUMERIC", ["193370"])

    # Multi-numeric with commas, spaces, or mixed
    assert classify_other_manager("1,2,4,11") == ("MULTI_NUMERIC_LIST", ["1", "2", "4", "11"])
    assert classify_other_manager("1 3 4") == ("MULTI_NUMERIC_LIST", ["1", "3", "4"])
    assert classify_other_manager("1, 4") == ("MULTI_NUMERIC_LIST", ["1", "4"])
    assert classify_other_manager("2, 3, 4, 7, 10") == ("MULTI_NUMERIC_LIST", ["2", "3", "4", "7", "10"])

    # Dirty variants & free text
    assert classify_other_manager("00") == ("FREE_TEXT_NAME", ["00"])
    assert classify_other_manager("0.0") == ("FREE_TEXT_NAME", ["0.0"])
    assert classify_other_manager("NONE") == ("FREE_TEXT_NAME", ["NONE"])
    assert classify_other_manager("NA") == ("FREE_TEXT_NAME", ["NA"])
    assert classify_other_manager("NOT APPLICABLE") == ("FREE_TEXT_NAME", ["NOT", "APPLICABLE"])
    assert classify_other_manager("N / A") == ("FREE_TEXT_NAME", ["N", "/", "A"])
    assert classify_other_manager("Blue Chip Partners LLC") == ("FREE_TEXT_NAME", ["Blue", "Chip", "Partners", "LLC"])
    assert classify_other_manager("PARAMETRIC PORTFOLIO ASSOCIATES LLC") == ("FREE_TEXT_NAME", ["PARAMETRIC", "PORTFOLIO", "ASSOCIATES", "LLC"])


def test_build_line_level_manager_map_ignores_othermanager_surrogate_keys():
    """Test that build_line_level_manager_map strictly queries OTHERMANAGER2.tsv and ignores OTHERMANAGER.tsv."""
    rows = [
        # OTHERMANAGER.tsv surrogate key
        {"accession_number": "ACC_001", "sequence_number": "1", "related_cik": "0000099999", "source_table": "OTHERMANAGER.tsv"},
        # OTHERMANAGER2.tsv actual line sequence
        {"accession_number": "ACC_001", "sequence_number": "1", "related_cik": "0000022222", "source_table": "OTHERMANAGER2.tsv"},
    ]

    line_map = build_line_level_manager_map(rows)
    assert line_map == {("ACC_001", "1"): "0000022222"}

    # Entity graph edges must include both
    graph_edges = build_entity_graph_edges([
        {"reporter_cik": "0000011111", "related_cik": "0000099999", "source_table": "OTHERMANAGER.tsv"},
        {"reporter_cik": "0000011111", "related_cik": "0000022222", "source_table": "OTHERMANAGER2.tsv"},
    ])
    assert sorted(graph_edges) == [("0000011111", "0000022222"), ("0000011111", "0000099999")]


def test_resolve_owner_component_strict_pure_helper_and_old_default_failure():
    """Test resolve_owner_component_strict pure helper across all cases and demonstrate old default flaw."""
    comp_map = {
        "0000000001": "0000000001",
        "0000000002": "0000000001",  # in Component 1
        "0000000003": "0000000003",  # in Component 3
    }
    filer_comp = "0000000001"

    # Case 1: Missing owner
    ok, reason, res_comp = resolve_owner_component_strict(None, filer_comp, comp_map)
    assert ok is False
    assert reason == "MISSING_ECONOMIC_OWNER"
    assert res_comp is None

    # Case 2: Owner CIK absent from component mapping (e.g. CIK 9999999999)
    absent_owner = "9999999999"
    ok, reason, res_comp = resolve_owner_component_strict(absent_owner, filer_comp, comp_map)
    assert ok is False
    assert reason == "OWNER_NOT_IN_GRAPH"
    assert res_comp is None

    # PROOF OF BUG IN OLD CODE: old code did component_mapping.get(econ_owner, filer_comp)
    old_buggy_owner_comp = comp_map.get(absent_owner, filer_comp)
    # Old code would evaluate old_buggy_owner_comp == filer_comp as TRUE (silent acceptance!)
    assert (old_buggy_owner_comp == filer_comp) is True, "Demonstrates old default silently accepted unmapped owner"

    # Case 3: Cross-component owner
    ok, reason, res_comp = resolve_owner_component_strict("0000000003", filer_comp, comp_map)
    assert ok is False
    assert reason == "CROSS_COMPONENT_OWNER"
    assert res_comp == "00000003" or res_comp == "0000000003"

    # Case 4: Same-component owner
    ok, reason, res_comp = resolve_owner_component_strict("0000000002", filer_comp, comp_map)
    assert ok is True
    assert reason == "SAME_COMPONENT_OWNER"
    assert res_comp == "0000000001"


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
    assert res["primary_m0"]["unresolved_rows_count"] == 1
    assert res["primary_m0"]["unresolved_shares_total"] == 5000
    assert res["zero_excluded_sensitivity"]["unresolved_rows_count"] == 1
    assert res["source_tables_breakdown"]["line_lookup_source_table"] == "OTHERMANAGER2.tsv only"
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
    """Test that two origin filers with duplicate economic disclosures deduplicate and report exact removal metrics."""
    db_file = tmp_path / "two_filer_dedup_test.db"
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

    # Add relationship connecting CIK 1 and CIK 2 in OTHERMANAGER2.tsv for line lookup
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER2.tsv');",
        ("ACC_PREV_2", q_prev),
    )
    conn.execute(
        "INSERT INTO manager_relationships (accession_number, period_of_report, reporter_cik, related_cik, sequence_number, source_table) VALUES (?, ?, '0000000002', '0000000001', '1', 'OTHERMANAGER2.tsv');",
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

    # Exact proof of deduplication:
    # Pre-dedup disclosures had 2 items for Component 1, post-dedup has 1 item -> exactly 1 duplicate removed per quarter
    assert res["component_level_exclusions"]["duplicate_disclosures_removed_q_prev"] == 1
    assert res["component_level_exclusions"]["duplicate_disclosures_removed_q_curr"] == 1
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


def test_format_markdown_report_contains_point72_and_section5_metrics():
    """Test format_markdown_report produces visible Point72 unresolved/on-time counts and Section 5 free-text metrics."""
    mock_data = {
        "status": "STAGE C PART C1 DISCOVERY UNDER CODEX RE-AUDIT",
        "created_utc": "2026-08-24T12:00:00Z",
        "total_execution_time_sec": 1.234,
        "preflight": {
            "db_filename": "13f_full_4409f14.db",
            "db_path": "/path/to/db",
            "size_bytes": 25881661440,
            "query_only_pragma": 1,
        },
        "evidence_a_berkshire_apple_2023q4": {
            "accession_number": "0000950123-24-002518",
            "origin_filer_cik": "0001067983",
            "period_of_report": "2023-12-31",
            "acceptance_datetime": "2024-02-14T21:02:18.000Z",
            "is_confidential_omit": True,
            "raw_matching_rows_count": 12,
            "raw_total_aggregate_shares": 905560000,
            "raw_total_aggregate_value_usd": 174345000000,
            "preregistered_expected_anchor": 905560000,
            "anchor_raw_match": True,
            "primary_resolved_shares": 0,
            "unresolved_rows_count": 12,
            "unresolved_shares_total": 905560000,
            "multi_sequence_rows_count": 11,
            "free_text_name_rows_count": 0,
            "multi_sequence_samples": ["1,2,4,11"],
            "is_primary_eligible": False,
            "ineligibility_reasons": ["CONFIDENTIAL_TREATMENT_OMISSION"],
            "raw_matching_rows": [],
        },
        "evidence_b_point72_2019q4_discovery": {
            "status": "PROPOSED PENDING CODEX MANUAL FREEZE",
            "entity_name": "Point72 Asset Management",
            "period_of_report": "2019-12-31",
            "canonical_entity_id": "0001599822",
            "seed_ciks": ["0001599822"],
            "component_closed_ciks": ["0001599822"],
            "accessions_count": 4,
            "manager_relationships_count": 6,
            "source_tables_breakdown": {
                "line_lookup_source_table": "OTHERMANAGER2.tsv only",
                "graph_edges_source_tables": "OTHERMANAGER.tsv and OTHERMANAGER2.tsv union",
                "line_map_entries_count": 6,
                "graph_edges_count": 6,
            },
            "raw_all_asset_anchor": {
                "total_component_raw_lines": 4457,
                "total_component_raw_shares": 563789558,
                "total_component_raw_value_usd": 25013024000.0,
                "main_accession_raw_lines_total": 917,
                "main_accession_shares_total": 418109088,
                "main_accession_value_usd_total": 19018144000.0,
                "main_accession_asset_breakdown": {
                    "cash_equity": {"rows": 877, "shares": 404693788, "value_usd": 17857865000.0},
                    "call_option": {"rows": 31, "shares": 8930800, "value_usd": 556255000.0},
                    "put_option": {"rows": 9, "shares": 4484500, "value_usd": 604024000.0},
                },
                "primary_all_asset_deduped_shares": 563789558,
                "primary_all_asset_deduped_value_usd": 25013024000.0,
                "zero_excluded_all_asset_deduped_shares": 145680470,
                "zero_excluded_all_asset_deduped_value_usd": 5994880000.0,
            },
            "total_raw_line_items": 4457,
            "on_time_confidential_filings_count": 0,
            "all_period_confidential_filings_count": 0,
            "on_time_amendment_filings_count": 0,
            "all_period_amendment_filings_count": 0,
            "cross_component_excluded_count": 0,
            "execution_time_sec": 0.45,
            "primary_m0": {
                "asset_scope": "CASH_EQUITY_ONLY",
                "raw_line_items_count": 4408,
                "unresolved_rows_count": 0,
                "unresolved_shares_total": 0,
                "unresolved_value_total": 0.0,
                "reconstructed_disclosures_count": 4408,
                "intra_entity_deduped_holdings_count": 4408,
                "total_shares_deduped": 549534258,
                "total_value_usd_deduped": 23800447000.0,
                "main_accession_shares_before_dedup": 404693788,
                "main_accession_value_before_dedup": 17857865000.0,
                "main_accession_raw_lines_retained": 877,
            },
            "zero_excluded_sensitivity": {
                "asset_scope": "CASH_EQUITY_ONLY",
                "raw_line_items_count": 4408,
                "unresolved_rows_count": 877,
                "unresolved_shares_total": 404693788,
                "unresolved_value_total": 17857865000.0,
                "reconstructed_disclosures_count": 3531,
                "intra_entity_deduped_holdings_count": 3531,
                "total_shares_deduped": 144840470,
                "total_value_usd_deduped": 5942582000.0,
                "main_accession_shares_before_dedup": 0,
                "main_accession_value_before_dedup": 0.0,
                "main_accession_raw_lines_retained": 0,
            },
            "accessions": [],
            "manager_relationships": [],
        },
        "mapping_conflict_diagnostics": {
            "total_conflict_keys_in_othermanager2": 50,
            "referenced_conflict_keys_count": 17,
            "affected_raw_line_items_count": 5472,
            "affected_shares_total": 659481568,
            "affected_value_usd_total": 42779736343.0,
        },
        "evidence_c_split_pilot_pairs": [
            {
                "stock_symbol": "NVDA",
                "cusip": "67066G104",
                "q_prev": "2024-03-31",
                "q_curr": "2024-06-30",
                "contract_split_factor": 10.0,
                "contract_ex_date": "2024-06-10",
                "eligible_continuous_entity_count": 2758,
                "raw_median_ratio": 10.01,
                "mad_log": 0.0717,
                "adjusted_median_ratio": 1.0013,
                "waterfall_state": "KNOWN_SPLIT_PASS",
                "waterfall_action": "INCLUDE",
                "is_in_contract_pass_range": True,
                "multi_sequence_other_manager": {
                    "q_prev_multi_sequence_rows": 210,
                    "q_curr_multi_sequence_rows": 211,
                    "q_prev_free_text_rows": 49,
                    "q_curr_free_text_rows": 53,
                    "samples": ["1, 2", "1,3"],
                },
                "component_level_exclusions": {
                    "membership_incomplete_components_excluded": 231,
                    "confidential_omission_components_excluded": 25,
                    "amendment_unresolved_components_excluded": 0,
                    "new_positions_count": 252,
                    "exit_positions_count": 120,
                    "unresolved_ownership_rows_excluded_q_prev": 1331,
                    "unresolved_ownership_rows_excluded_q_curr": 1426,
                },
                "global_dataset_context": {
                    "total_on_time_filers_q_prev": 7130,
                    "total_on_time_filers_q_curr": 7118,
                    "late_filings_excluded_q_prev": 605,
                    "late_filings_excluded_q_curr": 599,
                    "total_connected_components_in_graph": 6601,
                    "total_on_time_relationship_edges": 2752,
                },
            }
        ],
    }

    md = format_markdown_report(mock_data)
    # Check Evidence B fields
    assert "Point72 2019Q4 Multi-Manager Discovery" in md
    assert "Line-Level Sequence Lookup Source" in md
    assert "OTHERMANAGER2.tsv only" in md
    assert "ZERO_SENTINEL_EXCLUDED (Cash Equity Only)" in md
    assert "On-Time Confidential Filings**: 0" in md
    # Check Section 5 header and free text column
    assert "## 5. Real-Data Assumption Discovery: Multi-Manager Sequences and Free-Text Manager Names" in md
    assert "Q-1 Free-Text Rows" in md
    assert "Blue Chip Partners LLC" in md
    assert "## 6. Whole-Database Manager Mapping Conflict Diagnostics & Quarantine Audit" in md
    assert "50" in md
    assert "5,472" in md
    assert "## 8. C1 Implementation Audit & Contract v0.8.3 Reconciliation" in md
