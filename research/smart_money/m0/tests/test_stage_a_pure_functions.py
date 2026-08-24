"""Stage A pure-function unit and regression test suite covering 10 major M0 modules.

Guarantees:
- Zero network requests.
- Zero access to Phase 0 DB.
- Zero future price fetching.
- 100% pure function validation.
"""

from datetime import date
import json
import math
import os
from pathlib import Path
import sqlite3
import pytest

from research.smart_money.m0.src.storage_guard import (
    make_readonly_sqlite_uri,
    open_readonly_sqlite,
    init_signal_db,
    init_outcome_db,
)
from research.smart_money.m0.src.run_paths import (
    RunPaths,
    create_run_paths,
)
from research.smart_money.m0.src.manifest_integrity import (
    canonical_json_dumps,
    compute_sha256_bytes,
    compute_sha256_str,
    compute_sha256_file,
    compute_sha256_json,
    check_git_clean_tree,
    verify_cache_integrity,
    verify_manifest_binding,
    parse_and_validate_manifest,
)
from research.smart_money.m0.src.ownership_state_machine import (
    compute_13f_deadline,
    is_pit_accepted,
    is_valid_cik,
    normalize_cik,
    resolve_ownership,
    OwnershipPolicy,
    parse_datetime_to_utc,
    FilingHeader,
    HoldingRow,
    aggregate_accession_holdings,
    reconstruct_filer_state,
)
from research.smart_money.m0.src.entity_membership_dedup import (
    build_entity_connected_components,
    validate_entity_membership,
    deduplicate_entity_disclosures,
)
from research.smart_money.m0.src.security_mapping import (
    jaro_similarity,
    jaro_winkler_similarity,
    is_valid_cusip,
    OpenFIGICandidate,
    resolve_openfigi_waterfall,
)
from research.smart_money.m0.src.split_waterfall import (
    FROZEN_RATIONAL_SPLIT_FACTORS,
    SplitEvent,
    ContinuousHolder,
    compute_k_ledger_and_presence,
    compute_holder_log_statistics,
    is_rational_split_factor_match,
    evaluate_split_waterfall,
)
from research.smart_money.m0.src.signal_math import (
    compute_censor_weight,
    compute_entity_delta_shares,
    aggregate_m0_signals,
)
from research.smart_money.m0.src.coverage_keys import CoverageTracker
from research.smart_money.m0.src.outcome_policies import (
    compute_adjusted_open_price,
    compute_forward_return,
    settle_cash_m_and_a,
    select_open_price_with_roll,
    verify_cardinality_invariant,
    derive_sensitivity_branches,
)


# ============================================================================
# Module 1: Storage Guard Tests
# ============================================================================

def test_storage_guard_readonly_uri_and_immutable(tmp_path: Path):
    """Test read-only SQLite URI generation with special characters and immutable=1."""
    special_dir = tmp_path / "test?dir#with special chars"
    special_dir.mkdir(parents=True, exist_ok=True)
    db_file = special_dir / "sample.db"

    with pytest.raises(FileNotFoundError):
        make_readonly_sqlite_uri(tmp_path / "non_existent.db")

    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test (id INT);")
    conn.execute("INSERT INTO test VALUES (42);")
    conn.commit()
    conn.close()

    uri = make_readonly_sqlite_uri(db_file, immutable=True)
    assert uri.startswith("file:")
    assert "mode=ro" in uri
    assert "immutable=1" in uri

    ro_conn = open_readonly_sqlite(db_file, immutable=True)
    cur = ro_conn.cursor()
    cur.execute("SELECT id FROM test;")
    row = cur.fetchone()
    assert row[0] == 42

    with pytest.raises(sqlite3.OperationalError):
        cur.execute("INSERT INTO test VALUES (99);")
    ro_conn.close()


def test_storage_guard_reject_sidecars(tmp_path: Path):
    """Test that immutable=True rejects DB when sibling .db-wal/.db-shm exist, while immutable=False allows it."""
    db_file = tmp_path / "frozen.db"
    wal_file = tmp_path / "frozen.db-wal"

    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (x INT);")
    conn.commit()
    conn.close()

    # Create dummy WAL sidecar
    wal_file.write_bytes(b"dummy_wal_content")

    # immutable=True must reject opening
    with pytest.raises(ValueError, match="sibling sidecar"):
        open_readonly_sqlite(db_file, immutable=True)

    with pytest.raises(ValueError, match="sibling sidecar"):
        make_readonly_sqlite_uri(db_file, immutable=True)

    # immutable=False must allow connecting with mode=ro
    ro_conn = open_readonly_sqlite(db_file, immutable=False)
    cur = ro_conn.cursor()
    cur.execute("SELECT count(*) FROM t;")
    assert cur.fetchone()[0] == 0
    ro_conn.close()


def test_storage_guard_schema_init(tmp_path: Path):
    """Test table schema creation for m0_signal.db and m0_outcome.db."""
    sig_db = tmp_path / "signal" / "m0_signal.db"
    out_db = tmp_path / "outcome" / "m0_outcome.db"

    init_signal_db(sig_db)
    init_outcome_db(out_db)

    c_sig = sqlite3.connect(str(sig_db))
    cur = c_sig.cursor()
    cur.execute("PRAGMA table_info(m0_signals);")
    sig_cols = {row[1]: row[2] for row in cur.fetchall()}
    assert sig_cols == {
        "primary_stock_id": "TEXT",
        "period_of_report": "TEXT",
        "m0_signal": "REAL",
    }
    cur.execute("PRAGMA table_info(m0_signals_zero_excluded);")
    sig_zero_cols = {row[1]: row[2] for row in cur.fetchall()}
    assert sig_zero_cols == {
        "primary_stock_id": "TEXT",
        "period_of_report": "TEXT",
        "m0_signal": "REAL",
    }
    c_sig.close()

    c_out = sqlite3.connect(str(out_db))
    cur = c_out.cursor()
    cur.execute("PRAGMA table_info(m0_forward_returns);")
    out_cols = {row[1]: row[2] for row in cur.fetchall()}
    assert out_cols == {
        "primary_stock_id": "TEXT",
        "period_of_report": "TEXT",
        "forward_return": "REAL",
        "outcome_status": "TEXT",
        "rolled_le_5_return": "REAL",
    }
    c_out.close()


# ============================================================================
# Module 2: Run Paths Tests
# ============================================================================

def test_run_paths_valid_isolation(tmp_path: Path):
    """Test RunPaths creation and physical isolation."""
    run_paths = create_run_paths("test_run_2026_01", m0_root=tmp_path)
    assert run_paths.run_id == "test_run_2026_01"
    assert run_paths.signal_dir.name == "signal"
    assert run_paths.outcome_dir.name == "outcome"
    assert run_paths.signal_dir != run_paths.outcome_dir
    assert not run_paths.signal_dir.is_relative_to(run_paths.outcome_dir)
    assert not run_paths.outcome_dir.is_relative_to(run_paths.signal_dir)

    run_paths.ensure_directories()
    assert run_paths.signal_dir.is_dir()
    assert run_paths.outcome_dir.is_dir()


def test_run_paths_path_traversal_and_symlink_escape(tmp_path: Path):
    """Test that invalid run_ids and symlink runs_root escapes are rejected."""
    for bad_id in ["../escape", "run/nested", "run;id", "", " ", "run..id"]:
        with pytest.raises(ValueError):
            create_run_paths(bad_id, m0_root=tmp_path)

    outside_dir = tmp_path / "outside_jail"
    outside_dir.mkdir(parents=True, exist_ok=True)
    m0_root = tmp_path / "m0_root"
    m0_root.mkdir(parents=True, exist_ok=True)

    symlink_runs = m0_root / "runs"
    os.symlink(outside_dir, symlink_runs)

    with pytest.raises(ValueError):
        create_run_paths("run_escaped", m0_root=m0_root)


# ============================================================================
# Module 3: Manifest Integrity Tests (P0-1)
# ============================================================================

def test_manifest_integrity_canonical_json_and_strict_types():
    """Test deterministic JSON serialization, strict type rejections, and SHA-256 calculation."""
    obj = {"z": 1, "a": "hello", "b": [3, 2, 1]}
    dumps1 = canonical_json_dumps(obj)
    dumps2 = canonical_json_dumps({"b": [3, 2, 1], "a": "hello", "z": 1})
    assert dumps1 == dumps2

    h1 = compute_sha256_json(obj)
    h2 = compute_sha256_str(dumps1)
    assert h1 == h2
    assert len(h1) == 64

    with pytest.raises(TypeError):
        canonical_json_dumps({123: "int key"})
    with pytest.raises(TypeError):
        canonical_json_dumps({("a", "b"): "tuple key"})
    with pytest.raises(TypeError):
        canonical_json_dumps({"a": (1, 2, 3)})
    with pytest.raises(TypeError):
        canonical_json_dumps({"a": {1, 2, 3}})
    with pytest.raises(ValueError):
        canonical_json_dumps({"bad": float("nan")})


def test_manifest_integrity_cache_sha64(tmp_path: Path):
    """Test cache verification with exactly 64-hex SHA-256."""
    f = tmp_path / "test_file.txt"
    f.write_text("antigravity_m0_test_data", encoding="utf-8")

    file_hash = compute_sha256_file(f)
    assert len(file_hash) == 64

    assert verify_cache_integrity(b"antigravity_m0_test_data", file_hash) is True
    with pytest.raises(ValueError):
        verify_cache_integrity(b"tampered_data", file_hash)

    with pytest.raises(ValueError):
        verify_cache_integrity(b"antigravity_m0_test_data", "tooshort")
    with pytest.raises(ValueError):
        verify_cache_integrity(b"antigravity_m0_test_data", "g" * 64)


def test_manifest_raw_bytes_exactness_and_binding():
    """Test parse_and_validate_manifest rejects non-canonical bytes and verify_manifest_binding enforces raw bytes & clean tree."""
    valid_sig = {
        "manifest_type": "SIGNAL_MANIFEST",
        "run_id": "run_001",
        "contract_sha256": "0" * 64,
        "source_git_sha": "a" * 40,
        "m0_code_git_sha": "b" * 40,
        "git_tree_dirty": False,
    }
    canonical_sig_bytes = canonical_json_dumps(valid_sig).encode("utf-8")
    sig_hash = compute_sha256_bytes(canonical_sig_bytes)

    valid_pri = {
        "manifest_type": "PRICE_MANIFEST",
        "run_id": "run_001",
        "contract_sha256": "0" * 64,
        "source_git_sha": "a" * 40,
        "m0_code_git_sha": "b" * 40,
        "signal_manifest_sha256": sig_hash,
        "git_tree_dirty": False,
    }
    canonical_pri_bytes = canonical_json_dumps(valid_pri).encode("utf-8")

    verify_manifest_binding(canonical_sig_bytes, canonical_pri_bytes)

    non_canonical_sig_bytes = b'{"manifest_type":"SIGNAL_MANIFEST","run_id":"run_001","contract_sha256":"0000000000000000000000000000000000000000000000000000000000000000","source_git_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","m0_code_git_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","git_tree_dirty":false}'
    with pytest.raises(ValueError):
        parse_and_validate_manifest(non_canonical_sig_bytes)

    with pytest.raises(TypeError):
        verify_manifest_binding(valid_sig, valid_pri)

    dirty_sig = dict(valid_sig)
    dirty_sig["git_tree_dirty"] = True
    with pytest.raises(ValueError):
        verify_manifest_binding(canonical_json_dumps(dirty_sig).encode("utf-8"), canonical_pri_bytes)


def test_manifest_blank_fields_rejection():
    """Test verify_manifest_binding rejects blank fields (P0-1 counterexample)."""
    blank_sig = {
        "manifest_type": "SIGNAL_MANIFEST",
        "run_id": "",
        "contract_sha256": "",
        "source_git_sha": "",
        "m0_code_git_sha": "",
        "git_tree_dirty": False,
    }
    blank_pri = {
        "manifest_type": "PRICE_MANIFEST",
        "run_id": "",
        "contract_sha256": "",
        "source_git_sha": "",
        "m0_code_git_sha": "",
        "signal_manifest_sha256": compute_sha256_json(blank_sig),
        "git_tree_dirty": False,
    }
    with pytest.raises(ValueError):
        verify_manifest_binding(
            canonical_json_dumps(blank_sig).encode("utf-8"),
            canonical_json_dumps(blank_pri).encode("utf-8"),
        )


# ============================================================================
# Module 4: Ownership & State Machine Tests (P1-2 & P1-3)
# ============================================================================

def test_is_valid_cik_positive_digits():
    """Test is_valid_cik rejects 0 and 0000000000 and requires positive 1..10 digits."""
    assert is_valid_cik("0") is False
    assert is_valid_cik("0000000000") is False
    assert is_valid_cik(0) is False
    assert is_valid_cik(False) is False
    assert is_valid_cik("12345") is True
    assert is_valid_cik("0000012345") is True
    assert normalize_cik("12345") == "0000012345"

    with pytest.raises(ValueError):
        normalize_cik("0")


def test_compute_13f_deadline_sec_calendar():
    """Test SEC Rule 0-3 filing deadline calculation with weekend and holiday roll forward."""
    assert compute_13f_deadline("2025-12-31") == "2026-02-17"
    assert compute_13f_deadline("2024-03-31") == "2024-05-15"
    assert compute_13f_deadline("2024-06-30") == "2024-08-14"
    assert compute_13f_deadline("2023-12-31") == "2024-02-14"


def test_filing_header_datetime_time_component():
    """Test acceptance_datetime requires a valid time component (P1-3)."""
    with pytest.raises(ValueError, match="must contain a time component"):
        parse_datetime_to_utc("2024-05-15")

    with pytest.raises(ValueError, match="must contain a time component"):
        FilingHeader("0001-24-000001", "12345", "2024-03-31", "2024-05-15").validate()

    # Valid time component passes
    dt = parse_datetime_to_utc("2024-05-15T14:30:00")
    assert dt is not None
    header = FilingHeader("0001-24-000001", "12345", "2024-03-31", "2024-05-15T14:30:00Z")
    header.validate()


def test_is_pit_accepted():
    """Test PIT acceptance check with Eastern time boundary."""
    assert is_pit_accepted("2026-02-17T17:30:00Z", "2025-12-31") is True
    assert is_pit_accepted("2026-02-18T18:00:00Z", "2025-12-31") is False


def test_holding_row_semantic_invariants_and_direct_aggregation():
    """Test HoldingRow semantic invariants, accession/asset_class/ISO validation, and direct aggregation."""
    filer = "0001000001"
    acc1 = "0001-24-000001"
    acc2 = "0001-24-000002"
    period = "2024-03-31"

    # Blank accession_number rejected
    with pytest.raises(ValueError):
        HoldingRow("", filer, period, "037833100", "SH", filer, False, 100, 100).validate()

    # Blank asset_class rejected
    with pytest.raises(ValueError):
        HoldingRow(acc1, filer, period, "037833100", "", filer, False, 100, 100).validate()

    # Non-ISO period rejected
    with pytest.raises(ValueError):
        HoldingRow(acc1, filer, "not-a-date", "037833100", "SH", filer, False, 100, 100).validate()

    # Invariant: ownership_unresolved=True requires economic_owner_cik=None
    with pytest.raises(ValueError):
        HoldingRow(acc1, filer, period, "037833100", "SH", filer, True, 100, 100).validate()

    # Invariant: ownership_unresolved=False requires economic_owner_cik to be provided
    with pytest.raises(ValueError):
        HoldingRow(acc1, filer, period, "037833100", "SH", None, False, 100, 100).validate()

    # Fractional shares rejected
    with pytest.raises(ValueError):
        HoldingRow(acc1, filer, period, "037833100", "SH", filer, False, 100.5, 100).validate()

    # Bool rejected in shares
    with pytest.raises(ValueError):
        HoldingRow(acc1, filer, period, "037833100", "SH", filer, False, True, 100).validate()

    row1 = HoldingRow(acc1, filer, period, "037833100", "SH", filer, False, 100, 100)
    row2 = HoldingRow(acc2, filer, period, "037833100", "SH", filer, False, 200, 200)

    # Mixed accession numbers in direct aggregate call must raise ValueError
    with pytest.raises(ValueError):
        aggregate_accession_holdings([row1, row2])


def test_resolve_ownership_keyed_by_accession_and_seq():
    """Test economic ownership resolution keyed by (accession_number, sequence) under Contract v0.8.2."""
    filer_cik = "0000012345"
    acc1 = "0000012345-24-000001"
    acc2 = "0000012345-24-000002"
    om_map = {
        (acc1, "1"): "0000099999",
        (acc2, "1"): "0000077777",
    }

    # 1. Primary origin sentinels (None, blank, N/A, exact "0" under Primary)
    for sent in [None, "", "   ", "N/A", "n/a", "0"]:
        owner, unresolved = resolve_ownership(sent, filer_cik, acc1, om_map, policy=OwnershipPolicy.PRIMARY_EMPIRICAL_ZERO)
        assert owner == normalize_cik(filer_cik) and unresolved is False

    # 2. ZERO_SENTINEL_EXCLUDED policy: exact "0" is unresolved, while None/blank/N-A remain origin sentinels
    owner, unresolved = resolve_ownership("0", filer_cik, acc1, om_map, policy=OwnershipPolicy.ZERO_SENTINEL_EXCLUDED)
    assert owner is None and unresolved is True

    for sent in [None, "", "N/A", "n/a"]:
        owner, unresolved = resolve_ownership(sent, filer_cik, acc1, om_map, policy=OwnershipPolicy.ZERO_SENTINEL_EXCLUDED)
        assert owner == normalize_cik(filer_cik) and unresolved is False

    # 3. Positive integer sequence lookups
    owner, unresolved = resolve_ownership("1", filer_cik, acc1, om_map)
    assert owner == normalize_cik("0000099999") and unresolved is False

    owner, unresolved = resolve_ownership("1", filer_cik, acc2, om_map)
    assert owner == normalize_cik("0000077777") and unresolved is False

    # Unmapped sequence
    owner, unresolved = resolve_ownership("2", filer_cik, acc1, om_map)
    assert owner is None and unresolved is True

    # 4. Dirty variants and free text: strictly unresolved
    for dirty in ["NONE", "NA", "NOT APPLICABLE", "N / A", "00", "0.0", "1,2", "Blue Chip Partners LLC"]:
        owner, unresolved = resolve_ownership(dirty, filer_cik, acc1, om_map)
        assert owner is None and unresolved is True


def test_reconstruct_filer_state_form_validation_and_invalidation():
    """Test invalid form combinations and state invalidation on unknown amendments."""
    filer_cik = "0001000001"
    period = "2024-03-31"

    h_nt = FilingHeader(
        accession_number="0001-24-000001",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-10T10:00:00Z",
        form_type="13F-NT",
    )
    rows_nt = [
        HoldingRow(
            accession_number="0001-24-000001",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="037833100",
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=1000,
            total_value_usd=150000.0,
        )
    ]
    with pytest.raises(ValueError):
        reconstruct_filer_state([(h_nt, rows_nt)], period)

    h1 = FilingHeader(
        accession_number="0001-24-000003",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-10T10:00:00Z",
        form_type="13F-HR",
    )
    rows1 = [
        HoldingRow(
            accession_number="0001-24-000003",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="037833100",
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=1000,
            total_value_usd=150000.0,
        )
    ]
    h2 = FilingHeader(
        accession_number="0001-24-000004",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-12T10:00:00Z",
        form_type="13F-HR/A",
        amendment_type="UNKNOWN_AMENDMENT_TYPE",
    )
    rows2 = [
        HoldingRow(
            accession_number="0001-24-000004",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="037833100",
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=500,
            total_value_usd=75000.0,
        )
    ]
    state, meta = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert meta["amendment_unresolved"] is True
    assert state == {}


def test_reconstruct_filer_state_add_new_holdings_upsert():
    """Test that ADD_NEW_HOLDINGS overwrites in place without accumulating."""
    filer_cik = "0001000001"
    period = "2024-03-31"

    h1 = FilingHeader(
        accession_number="0001-24-000005",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-10T10:00:00Z",
        form_type="13F-HR",
    )
    rows1 = [
        HoldingRow(
            accession_number="0001-24-000005",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="037833100",
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=1000,
            total_value_usd=150000.0,
        )
    ]
    h2 = FilingHeader(
        accession_number="0001-24-000006",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-12T10:00:00Z",
        form_type="13F-HR/A",
        amendment_type="ADD_NEW_HOLDINGS",
    )
    rows2 = [
        HoldingRow(
            accession_number="0001-24-000006",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="037833100",
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=1200,
            total_value_usd=180000.0,
        )
    ]
    state, meta = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert meta["amendment_unresolved"] is False
    assert state[("037833100", "SH", normalize_cik(filer_cik))]["total_shares"] == 1200


# ============================================================================
# Module 5: Entity Membership & Dedup Tests
# ============================================================================

def test_entity_components_and_membership_invalid_ciks():
    """Test build_entity_connected_components and validate_entity_membership raise on invalid CIKs."""
    with pytest.raises(ValueError):
        build_entity_connected_components([("000100", "BAD_CIK")])

    with pytest.raises(ValueError):
        build_entity_connected_components([], all_ciks={"000100", ""})

    with pytest.raises(ValueError):
        validate_entity_membership({"000100", "INVALID"}, {"000100"})


def test_entity_connected_components_numeric_min():
    """Test that canonical CIK is NUMERIC minimum, not lexical minimum."""
    edges = [("1000000000", "20000")]
    mapping = build_entity_connected_components(edges)
    assert mapping["1000000000"] == "0000020000"
    assert mapping["20000"] == "0000020000"


def test_deduplicate_entity_disclosures_integral_and_owner_requirements():
    """Test deduplicate_entity_disclosures requires economic_owner_cik, ISO period, and integral shares/votes."""
    entity_id = "0000000100"

    with pytest.raises(ValueError):
        bad_date = [{"canonical_entity_id": entity_id, "cusip": "037833100", "period_of_report": "not-a-date", "economic_owner_cik": entity_id, "total_shares": 100, "total_value_usd": 100.0}]
        deduplicate_entity_disclosures(entity_id, bad_date)

    with pytest.raises(ValueError):
        bad = [{"canonical_entity_id": entity_id, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": None, "total_shares": 100, "total_value_usd": 100.0}]
        deduplicate_entity_disclosures(entity_id, bad)

    with pytest.raises(ValueError):
        bad_shares = [{"canonical_entity_id": entity_id, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": entity_id, "total_shares": 100.25, "total_value_usd": 100.0}]
        deduplicate_entity_disclosures(entity_id, bad_shares)

    with pytest.raises(ValueError):
        bad_bool = [{"canonical_entity_id": entity_id, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": entity_id, "total_shares": True, "total_value_usd": 100.0}]
        deduplicate_entity_disclosures(entity_id, bad_bool)

    valid_holdings = [
        {"canonical_entity_id": entity_id, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": entity_id, "total_shares": 5000, "total_value_usd": 750000.5, "total_vote_sole": 5000, "total_vote_shared": 0, "total_vote_none": 0},
        {"canonical_entity_id": entity_id, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": entity_id, "total_shares": 5000, "total_value_usd": 750000.5, "total_vote_sole": 5000, "total_vote_shared": 0, "total_vote_none": 0},
    ]
    deduped = deduplicate_entity_disclosures(entity_id, valid_holdings)
    assert len(deduped) == 1


# ============================================================================
# Module 6: Security Mapping Tests (P1-1)
# ============================================================================

def test_cusip_validation():
    """Test standard CUSIP checksum validation."""
    assert is_valid_cusip("037833100") is True
    assert is_valid_cusip("67066G104") is True
    assert is_valid_cusip("023135106") is True
    assert is_valid_cusip("88160R101") is True
    assert is_valid_cusip("02079K305") is True
    assert is_valid_cusip("037833109") is False
    assert is_valid_cusip("INVALID") is False
    assert is_valid_cusip("") is False


def test_jaro_winkler_similarity():
    """Test Jaro-Winkler string similarity."""
    assert jaro_winkler_similarity("APPLE INC", "APPLE INC") == 1.0
    assert jaro_winkler_similarity("APPLE INC", "APPLE INC.") > 0.95
    assert jaro_winkler_similarity("APPLE INC", "MICROSOFT CORP") < 0.5


def test_openfigi_top_score_ambiguity_and_alphanumeric_gate():
    """Test OpenFIGI waterfall filters candidates, top-score ambiguity, and alphanumeric requirements (P1-1)."""
    cusip = "037833100"
    issuer_name = "APPLE INC"

    cand_high = OpenFIGICandidate("BBG000B9XRY4", "APPLE INC", "AAPL", "US", "Equity", "Common Stock", shareClassFIGI="BBG001S5N8V8")
    cand_lower = OpenFIGICandidate("BBG000OTHER2", "APPLE INC - CLA", "AAPL.A", "US", "Equity", "Common Stock", shareClassFIGI="BBG001DIFF99")

    resolved_id, meta = resolve_openfigi_waterfall(cusip, issuer_name, [cand_high, cand_lower])
    assert resolved_id == "BBG001S5N8V8"
    assert meta["status"] == "RESOLVED"

    # Alphanumeric issuer name gate test (P1-1)
    res_nonalpha, meta_nonalpha = resolve_openfigi_waterfall(cusip, "!!!", [cand_high])
    assert res_nonalpha is None
    assert meta_nonalpha["status"] == "EMPTY_OR_NONALPHANUMERIC_ISSUER_NAME"

    # Non-alphanumeric candidate name test
    cand_nonalpha = OpenFIGICandidate("BBG000PUNCT1", "!!!", "AAPL", "US", "Equity", "Common Stock", shareClassFIGI="BBG001PUNCT1")
    res_cand_na, _ = resolve_openfigi_waterfall(cusip, issuer_name, [cand_nonalpha])
    assert res_cand_na is None


# ============================================================================
# Module 7: Split Waterfall Tests (P1-4, P1-5, P2)
# ============================================================================

def test_frozen_rational_split_factors_frozenset():
    """Verify that FROZEN_RATIONAL_SPLIT_FACTORS is an immutable frozenset containing 204 factors."""
    assert isinstance(FROZEN_RATIONAL_SPLIT_FACTORS, frozenset)
    assert len(FROZEN_RATIONAL_SPLIT_FACTORS) == 204
    assert 2.0 in FROZEN_RATIONAL_SPLIT_FACTORS
    assert 0.5 in FROZEN_RATIONAL_SPLIT_FACTORS
    assert 1.25 in FROZEN_RATIONAL_SPLIT_FACTORS


def test_split_waterfall_gate0_stop_precedence():
    """Test Gate 0 STOP executes before holder computation without raising on invalid holder data (P1-5)."""
    # Holder with 0 prev_shares is invalid for Gate 1/2, but Gate 0 MUST intercept and return EXCLUDE cleanly
    invalid_holder = ContinuousHolder("0001", 0, 0)
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=True,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[invalid_holder],
    )
    assert res.state == "CORPORATE_ACTION_UNKNOWN"
    assert res.action == "EXCLUDE"
    assert res.split_factor is None


def test_split_ledger_date_comparison_and_overflow():
    """Test split ledger parsed date comparisons (with whitespace) and overflow validation (P1-4)."""
    splits = [SplitEvent(" 2024-06-10 ", 10.0)]
    k, has_splits = compute_k_ledger_and_presence("2024-03-31 ", " 2024-06-30", splits)
    assert k == 10.0
    assert has_splits is True

    # Overflow rejection test
    overflow_splits = [SplitEvent("2024-06-10", 1e308), SplitEvent("2024-06-11", 1e308)]
    with pytest.raises(ValueError, match="overflow"):
        compute_k_ledger_and_presence("2024-03-31", "2024-06-30", overflow_splits)


def test_split_waterfall_all_8_states():
    """Verify all 8 canonical states in the ordered waterfall precedence truth table."""
    # Gate 0: Corporate Action Unknown
    res_g0 = evaluate_split_waterfall(True, False, 1.0, [ContinuousHolder(str(i), 100, 100) for i in range(25)])
    assert res_g0.state == "CORPORATE_ACTION_UNKNOWN"
    assert res_g0.action == "EXCLUDE"

    # Gate 1.1: Known Split, Low Power (N < 20)
    res_g11 = evaluate_split_waterfall(False, True, 2.0, [ContinuousHolder(str(i), 100, 200) for i in range(10)])
    assert res_g11.state == "KNOWN_SPLIT_LOW_POWER"
    assert res_g11.action == "INCLUDE"

    # Gate 1.2a: Known Split, Pass (N >= 20, adjusted median in [0.8, 1.2])
    res_g12a = evaluate_split_waterfall(False, True, 2.0, [ContinuousHolder(str(i), 100, 202) for i in range(25)])
    assert res_g12a.state == "KNOWN_SPLIT_PASS"
    assert res_g12a.action == "INCLUDE"

    # Gate 1.2b: Known Split, Mismatch (N >= 20, adjusted median not in [0.8, 1.2])
    res_g12b = evaluate_split_waterfall(False, True, 2.0, [ContinuousHolder(str(i), 100, 300) for i in range(25)])
    assert res_g12b.state == "KNOWN_SPLIT_MISMATCH"
    assert res_g12b.action == "EXCLUDE"

    # Gate 2.1: Ledger Only, Low Power (has_vendor_splits == False, N < 20)
    res_g21 = evaluate_split_waterfall(False, False, 1.0, [ContinuousHolder(str(i), 100, 100) for i in range(15)])
    assert res_g21.state == "LEDGER_ONLY_LOW_POWER"
    assert res_g21.action == "INCLUDE"

    # Gate 2.2a: Clean (has_vendor_splits == False, N >= 20, no split match)
    res_g22a = evaluate_split_waterfall(False, False, 1.0, [ContinuousHolder(str(i), 100, 101) for i in range(25)])
    assert res_g22a.state == "CLEAN"
    assert res_g22a.action == "INCLUDE"

    # Gate 2.2b: Split Unknown (has_vendor_splits == False, N >= 20, matched 4:1 split, MAD_log <= 0.15)
    res_g22b = evaluate_split_waterfall(False, False, 1.0, [ContinuousHolder(str(i), 100, 399) for i in range(25)])
    assert res_g22b.state == "SPLIT_UNKNOWN"
    assert res_g22b.action == "EXCLUDE"

    # Gate 2.2c: Split Audit Ambiguous High Dispersion (matched factor e.g. 2.0, MAD_log > 0.15)
    holders_disp = [
        ContinuousHolder(str(i), 100, 150 if i < 15 else (100 * 2 * 2 / 1.5))
        for i in range(30)
    ]
    res_g22c = evaluate_split_waterfall(False, False, 1.0, holders_disp)
    assert res_g22c.state == "SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION"
    assert res_g22c.action == "EXCLUDE"


# ============================================================================
# Module 8: Signal Math Tests (P1-6)
# ============================================================================

def test_signal_math_exact_weights_and_overflow():
    """Test rejection of bool, invalid ISO dates, non-exact weights, and overflow in signal math (P1-6)."""
    with pytest.raises(ValueError):
        compute_censor_weight(True, False, True, 0, 1000, 1000)

    with pytest.raises(ValueError):
        compute_entity_delta_shares(True, 100, 1.0)

    # Inexact censor weight (e.g. 0.30000002) must raise ValueError
    with pytest.raises(ValueError):
        aggregate_m0_signals([{"primary_stock_id": "STK_A", "period_of_report": "2024-03-31", "delta_shares": 100, "censor_weight": 0.30000002}])

    # Non-ISO date in aggregation
    with pytest.raises(ValueError):
        aggregate_m0_signals([{"primary_stock_id": "STK_A", "period_of_report": "not-a-date", "delta_shares": 100, "censor_weight": 0.3}])

    # Exact valid weights 0.3 and 1.0 succeed
    signals = aggregate_m0_signals([
        {"primary_stock_id": "STK_A", "period_of_report": "2024-03-31", "delta_shares": 100, "censor_weight": 0.3},
        {"primary_stock_id": "STK_A", "period_of_report": "2024-03-31", "delta_shares": 200, "censor_weight": 1.0},
    ])
    assert signals[("STK_A", "2024-03-31")] == 100 * 0.3 + 200 * 1.0


# ============================================================================
# Module 9: Coverage Keys Tests (P0-2)
# ============================================================================

def test_coverage_tracker_d1_d2_projection_and_penetration():
    """Test CoverageTracker D1->D2 projection, penetration rates, and price-covered split denominator (P0-2)."""
    tracker = CoverageTracker()

    # D1 A (count 10, value 100) + D1 B (count 20, value 200) -> same D2 stock X
    tracker.record_d1("037833100", "2024-03-31", filer_count=10, value_usd=100.0)
    tracker.record_d1("037833200", "2024-03-31", filer_count=20, value_usd=200.0)

    tracker.record_d2_mapping("037833100", "2024-03-31", "BBG001S5N8V8")
    tracker.record_d2_mapping("037833200", "2024-03-31", "BBG001S5N8V8")

    tracker.record_d2_price_covered("BBG001S5N8V8", "2024-03-31")
    tracker.record_split_state("BBG001S5N8V8", "2024-03-31", "CLEAN")
    tracker.record_final_ic_eligible("BBG001S5N8V8", "2024-03-31")

    summary = tracker.generate_coverage_summary()

    # Assert D1 & D2 honest counts and penetration rates
    assert summary["d1_raw_sec_keys_total"] == 2
    assert summary["d1_total_filer_count"] == 30
    assert summary["d1_total_value_usd"] == 300.0
    assert summary["d1_mapped_keys_total"] == 2
    assert summary["d1_mapped_filer_count"] == 30
    assert summary["d1_mapped_value_usd"] == 300.0
    assert summary["d1_key_mapping_rate"] == 1.0
    assert summary["d1_filer_count_penetration_rate"] == 1.0
    assert summary["d1_value_penetration_rate"] == 1.0
    assert summary["openfigi_mapping_rate"] == 1.0

    assert summary["d2_mapped_keys_total"] == 1
    assert summary["d2_price_covered_keys_total"] == 1
    assert summary["price_coverage_rate"] == 1.0
    assert summary["split_state_distribution"]["CLEAN"]["pct_of_price_covered_d2"] == 100.0
    assert summary["final_ic_eligible_d2_keys_total"] == 1
    assert summary["d1_conversion_retention_rate"] == 1.0
    assert summary["d2_conversion_retention_rate"] == 1.0


# ============================================================================
# Module 10: Outcome Policies Tests
# ============================================================================

def test_outcome_policies_calendar_roll_session_inclusive():
    """Test price selection with calendar-based trading day roll forward up to 5 sessions inclusive."""
    calendar = [
        "2024-05-15", "2024-05-16", "2024-05-17", "2024-05-20", "2024-05-21", "2024-05-22", "2024-05-23"
    ]
    price_by_date = {
        "2024-05-15": None,
        "2024-05-16": None,
        "2024-05-17": None,
        "2024-05-20": None,
        "2024-05-21": None,
        "2024-05-22": 150.0,
    }

    price, roll_days, trade_date = select_open_price_with_roll(calendar, price_by_date, "2024-05-15", max_roll_days=5)
    assert price == 150.0
    assert roll_days == 5
    assert trade_date == "2024-05-22"

    with pytest.raises(ValueError):
        select_open_price_with_roll(calendar, price_by_date, "2024-05-15", max_roll_days=-1)

    with pytest.raises(ValueError):
        select_open_price_with_roll(calendar, price_by_date, "2024-05-15", max_roll_days=True)

    with pytest.raises(ValueError):
        select_open_price_with_roll(["2024-05-15", "2024-05-15"], price_by_date, "2024-05-15", max_roll_days=5)

    with pytest.raises(ValueError):
        select_open_price_with_roll(["not-a-date"], price_by_date, "2024-05-15", max_roll_days=5)


def test_outcome_policies_adjusted_open_and_return():
    """Test adjusted open price calculation and return formula."""
    adj_open = compute_adjusted_open_price(raw_open=100.0, raw_close=300.0, adj_close=150.0)
    assert adj_open == 50.0

    assert compute_adjusted_open_price(-10.0, 100.0, 100.0) is None
    assert compute_adjusted_open_price(100.0, 0.0, 100.0) is None
    assert compute_adjusted_open_price(True, 100.0, 100.0) is None

    ret = compute_forward_return(entry_adj_open=50.0, exit_adj_open=60.0)
    assert ret == pytest.approx(0.20)


def test_outcome_policies_cash_m_and_a():
    """Test cash M&A privatization buyout settlement."""
    ret, status = settle_cash_m_and_a(entry_adj_open=50.0, cash_consideration_per_share=55.0, is_cash_only=True)
    assert ret == pytest.approx(0.10)
    assert status == "CASH_M_AND_A_SETTLED"

    ret_bad, status_bad = settle_cash_m_and_a(50.0, 55.0, is_cash_only=False)
    assert ret_bad is None
    assert status_bad == "CORPORATE_ACTION_UNKNOWN"


def test_outcome_policies_cardinality_invariant_and_sensitivities():
    """Test cardinality invariant enforcement in LEFT JOIN and derivation of sensitivity branches."""
    signals = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 100.0},
        {"primary_stock_id": "STK_2", "period_of_report": "2024-03-31", "m0_signal": -50.0},
        {"primary_stock_id": "STK_3", "period_of_report": "2024-03-31", "m0_signal": 200.0},
    ]

    returns = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": "CLEAN"},
        {"primary_stock_id": "STK_2", "period_of_report": "2024-03-31", "forward_return": None, "outcome_status": "DELISTED", "rolled_le_5_return": -0.10},
    ]

    joined, metrics = verify_cardinality_invariant(signals, returns)
    assert len(joined) == len(signals)
    assert metrics["cardinality_conserved"] is True
    assert metrics["missing_count"] == 2
    assert metrics["valid_outcome_count"] == 1

    branches = derive_sensitivity_branches(joined)
    assert len(branches["primary"]) == 1
    assert len(branches["missing_minus_100"]) == 3
    assert len(branches["missing_zero"]) == 3
    assert len(branches["rolled_le_5"]) == 2

    # Cardinality input integrity counterexamples
    with pytest.raises(ValueError):
        verify_cardinality_invariant([{"primary_stock_id": "", "period_of_report": "2024-03-31", "m0_signal": 10.0}], returns)

    with pytest.raises(ValueError):
        verify_cardinality_invariant([{"primary_stock_id": "STK_1", "period_of_report": "not-a-date", "m0_signal": 10.0}], returns)

    with pytest.raises(ValueError):
        verify_cardinality_invariant([{"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": float("nan")}], returns)

    with pytest.raises(ValueError):
        verify_cardinality_invariant([{"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": True}], returns)

    with pytest.raises(ValueError):
        bad_returns = [{"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": ""}]
        verify_cardinality_invariant(signals, bad_returns)

    with pytest.raises(ValueError):
        bad_ret2 = [{"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": True, "outcome_status": "CLEAN"}]
        verify_cardinality_invariant(signals, bad_ret2)
