"""Stage A pure-function unit and regression test suite covering 10 major M0 modules.

Guarantees:
- Zero network requests.
- Zero access to Phase 0 DB.
- Zero future price fetching.
- 100% pure function validation.
"""

import json
import math
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
    validate_canonical_json_value,
)
from research.smart_money.m0.src.ownership_state_machine import (
    compute_13f_deadline,
    is_pit_accepted,
    is_valid_cik,
    normalize_cik,
    resolve_ownership,
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
# Module 1: Storage Guard Tests (Finding 1)
# ============================================================================

def test_storage_guard_readonly_uri_and_immutable(tmp_path: Path):
    """Test read-only SQLite URI generation with special characters and immutable=1."""
    special_dir = tmp_path / "test?dir#with special chars"
    special_dir.mkdir(parents=True, exist_ok=True)
    db_file = special_dir / "sample.db"

    # Non-existent file must raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        make_readonly_sqlite_uri(tmp_path / "non_existent.db")

    # Create dummy DB
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test (id INT);")
    conn.execute("INSERT INTO test VALUES (42);")
    conn.commit()
    conn.close()

    uri = make_readonly_sqlite_uri(db_file, immutable=True)
    assert uri.startswith("file:")
    assert "mode=ro" in uri
    assert "immutable=1" in uri

    # Open with read-only connection
    ro_conn = open_readonly_sqlite(db_file, immutable=True)
    cur = ro_conn.cursor()
    cur.execute("SELECT id FROM test;")
    row = cur.fetchone()
    assert row[0] == 42

    # Attempt write on read-only connection with query_only=ON must fail
    with pytest.raises(sqlite3.OperationalError):
        cur.execute("INSERT INTO test VALUES (99);")
    ro_conn.close()


def test_storage_guard_schema_init(tmp_path: Path):
    """Test table schema creation for m0_signal.db and m0_outcome.db."""
    sig_db = tmp_path / "signal" / "m0_signal.db"
    out_db = tmp_path / "outcome" / "m0_outcome.db"

    init_signal_db(sig_db)
    init_outcome_db(out_db)

    # Verify signal table schema
    c_sig = sqlite3.connect(str(sig_db))
    cur = c_sig.cursor()
    cur.execute("PRAGMA table_info(m0_signals);")
    sig_cols = {row[1]: row[2] for row in cur.fetchall()}
    assert sig_cols == {
        "primary_stock_id": "TEXT",
        "period_of_report": "TEXT",
        "m0_signal": "REAL",
    }
    c_sig.close()

    # Verify outcome table schema
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
# Module 2: Run Paths Tests (Finding 10)
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


def test_run_paths_path_traversal_and_strict_children(tmp_path: Path):
    """Test that invalid run_ids with path traversal are rejected."""
    for bad_id in ["../escape", "run/nested", "run;id", "", " ", "run..id"]:
        with pytest.raises(ValueError):
            create_run_paths(bad_id, m0_root=tmp_path)


# ============================================================================
# Module 3: Manifest Integrity Tests (Finding 2)
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

    # Non-string dict keys must be rejected
    with pytest.raises(TypeError):
        canonical_json_dumps({123: "int key"})
    with pytest.raises(TypeError):
        canonical_json_dumps({("a", "b"): "tuple key"})

    # Non-standard types (tuples, sets, custom objects) must be rejected
    with pytest.raises(TypeError):
        canonical_json_dumps({"a": (1, 2, 3)})
    with pytest.raises(TypeError):
        canonical_json_dumps({"a": {1, 2, 3}})

    # allow_nan=False check
    with pytest.raises(ValueError):
        canonical_json_dumps({"bad": float("nan")})
    with pytest.raises(ValueError):
        canonical_json_dumps({"bad": float("inf")})


def test_manifest_integrity_cache_sha64(tmp_path: Path):
    """Test cache verification with exactly 64-hex SHA-256."""
    f = tmp_path / "test_file.txt"
    f.write_text("antigravity_m0_test_data", encoding="utf-8")

    file_hash = compute_sha256_file(f)
    assert len(file_hash) == 64

    # Cache integrity verification
    assert verify_cache_integrity(b"antigravity_m0_test_data", file_hash) is True
    with pytest.raises(ValueError):
        verify_cache_integrity(b"tampered_data", file_hash)

    # Invalid non-64 hex expected hash
    with pytest.raises(ValueError):
        verify_cache_integrity(b"antigravity_m0_test_data", "tooshort")
    with pytest.raises(ValueError):
        verify_cache_integrity(b"antigravity_m0_test_data", "g" * 64)  # 'g' is not hex


def test_manifest_integrity_binding_exact_bytes():
    """Test cross-stage manifest binding verification on exact canonical bytes."""
    sig_manifest = {
        "run_id": "run_001",
        "contract_sha256": "contract_hash_123",
        "source_git_sha": "git_hash_abc",
        "m0_code_git_sha": "code_hash_xyz",
        "signals_count": 100,
    }
    sig_hash = compute_sha256_json(sig_manifest)

    price_manifest = {
        "run_id": "run_001",
        "contract_sha256": "contract_hash_123",
        "source_git_sha": "git_hash_abc",
        "m0_code_git_sha": "code_hash_xyz",
        "signal_manifest_sha256": sig_hash,
    }

    # Should pass with dict or raw bytes
    verify_manifest_binding(sig_manifest, price_manifest)
    verify_manifest_binding(
        canonical_json_dumps(sig_manifest).encode("utf-8"),
        canonical_json_dumps(price_manifest).encode("utf-8"),
    )

    # Tampered run_id in price manifest must raise ValueError
    bad_price = dict(price_manifest)
    bad_price["run_id"] = "run_002"
    with pytest.raises(ValueError):
        verify_manifest_binding(sig_manifest, bad_price)


# ============================================================================
# Module 4: Ownership & State Machine Tests (Findings 3 & 9)
# ============================================================================

def test_compute_13f_deadline_sec_calendar():
    """Test SEC Rule 0-3 filing deadline calculation with weekend and holiday roll forward."""
    # 2025-12-31: +45 days is 2026-02-14 (Sat) -> Sun Feb 15 -> Mon Feb 16 (Presidents' Day) -> Tue 2026-02-17
    assert compute_13f_deadline("2025-12-31") == "2026-02-17"
    assert compute_13f_deadline("2024-03-31") == "2024-05-15"
    assert compute_13f_deadline("2024-06-30") == "2024-08-14"
    assert compute_13f_deadline("2023-12-31") == "2024-02-14"


def test_is_pit_accepted():
    """Test PIT acceptance check with Eastern time boundary."""
    assert is_pit_accepted("2026-02-17T17:30:00Z", "2025-12-31") is True
    assert is_pit_accepted("2026-02-18T18:00:00Z", "2025-12-31") is False


def test_resolve_ownership_keyed_by_accession_and_seq():
    """Test economic ownership resolution keyed by (accession_number, sequence)."""
    filer_cik = "0000012345"
    acc1 = "0000012345-24-000001"
    acc2 = "0000012345-24-000002"
    om_map = {
        (acc1, "1"): "0000099999",
        (acc1, "2"): "0000088888",
        (acc2, "1"): "0000077777",
    }

    # No other manager -> self
    owner, unresolved = resolve_ownership(None, filer_cik, acc1, om_map)
    assert owner == normalize_cik(filer_cik) and unresolved is False

    # Resolved matching accession and sequence
    owner, unresolved = resolve_ownership("1", filer_cik, acc1, om_map)
    assert owner == normalize_cik("0000099999") and unresolved is False

    owner, unresolved = resolve_ownership("1", filer_cik, acc2, om_map)
    assert owner == normalize_cik("0000077777") and unresolved is False

    # Sequence not in acc2
    owner, unresolved = resolve_ownership("2", filer_cik, acc2, om_map)
    assert owner is None and unresolved is True


def test_reconstruct_filer_state_form_validation_and_invalidation():
    """Test invalid form combinations and state invalidation on unknown amendments."""
    filer_cik = "0001000001"
    period = "2024-03-31"

    # 13F-NT with holdings must raise ValueError
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
            total_shares=1000.0,
            total_value_usd=150000.0,
        )
    ]
    with pytest.raises(ValueError):
        reconstruct_filer_state([(h_nt, rows_nt)], period)

    # 13F-HR with amendment_type must raise ValueError
    h_bad_hr = FilingHeader(
        accession_number="0001-24-000002",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-10T10:00:00Z",
        form_type="13F-HR",
        amendment_type="RESTATEMENT",
    )
    with pytest.raises(ValueError):
        h_bad_hr.validate()

    # 13F-HR/A with unknown amendment type wipes entire state
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
            total_shares=1000.0,
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
            total_shares=500.0,
            total_value_usd=75000.0,
        )
    ]
    state, meta = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert meta["amendment_unresolved"] is True
    assert state == {}  # Wiped completely


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
            total_shares=1000.0,
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
            total_shares=1200.0,
            total_value_usd=180000.0,
        )
    ]
    state, meta = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert meta["amendment_unresolved"] is False
    assert state[("037833100", "SH", normalize_cik(filer_cik))]["total_shares"] == 1200.0


# ============================================================================
# Module 5: Entity Membership & Dedup Tests (Finding 4)
# ============================================================================

def test_entity_connected_components_numeric_min():
    """Test that canonical CIK is NUMERIC minimum, not lexical minimum."""
    # "1000000000" vs "20000": lexically "1000000000" < "20000", but numerically 20,000 < 1,000,000,000
    edges = [
        ("1000000000", "20000"),
    ]
    mapping = build_entity_connected_components(edges)
    assert mapping["1000000000"] == "0000020000"
    assert mapping["20000"] == "0000020000"


def test_deduplicate_entity_disclosures_unrounded_signatures():
    """Test intra-entity deduplication preserves exact unrounded floating signatures and rejects invalid keys."""
    entity_id = "0000000100"
    holdings = [
        {
            "canonical_entity_id": entity_id,
            "cusip": "037833100",
            "period_of_report": "2024-03-31",
            "economic_owner_cik": "0000000100",
            "total_shares": 5000.1234567,
            "total_value_usd": 750000.891,
            "total_vote_sole": 5000.1234567,
            "total_vote_shared": 0.0,
            "total_vote_none": 0.0,
        },
        # Duplicate with exact same unrounded signature
        {
            "canonical_entity_id": entity_id,
            "cusip": "037833100",
            "period_of_report": "2024-03-31",
            "economic_owner_cik": "0000000100",
            "total_shares": 5000.1234567,
            "total_value_usd": 750000.891,
            "total_vote_sole": 5000.1234567,
            "total_vote_shared": 0.0,
            "total_vote_none": 0.0,
        },
        # Slightly different unrounded signature (must not fold)
        {
            "canonical_entity_id": entity_id,
            "cusip": "037833100",
            "period_of_report": "2024-03-31",
            "economic_owner_cik": "0000000100",
            "total_shares": 5000.1234568,
            "total_value_usd": 750000.891,
            "total_vote_sole": 5000.1234568,
            "total_vote_shared": 0.0,
            "total_vote_none": 0.0,
        },
    ]

    deduped = deduplicate_entity_disclosures(entity_id, holdings)
    assert len(deduped) == 2

    # Blank CUSIP must raise ValueError
    with pytest.raises(ValueError):
        bad = [{"canonical_entity_id": entity_id, "cusip": "", "period_of_report": "2024-03-31", "total_shares": 10.0, "total_value_usd": 10.0}]
        deduplicate_entity_disclosures(entity_id, bad)


# ============================================================================
# Module 6: Security Mapping Tests (Finding 5)
# ============================================================================

def test_cusip_validation():
    """Test standard CUSIP checksum validation."""
    assert is_valid_cusip("037833100") is True  # Apple
    assert is_valid_cusip("67066G104") is True  # Nvidia
    assert is_valid_cusip("023135106") is True  # Amazon
    assert is_valid_cusip("88160R101") is True  # Tesla
    assert is_valid_cusip("02079K305") is True  # Alphabet

    assert is_valid_cusip("037833109") is False  # Wrong checksum
    assert is_valid_cusip("INVALID") is False
    assert is_valid_cusip("") is False


def test_openfigi_top_score_ambiguity_and_jaro():
    """Test OpenFIGI waterfall filters to highest-name-score candidates before checking ambiguity."""
    cusip = "037833100"
    issuer_name = "APPLE INC"

    cand_high_score = OpenFIGICandidate(
        figi="BBG000B9XRY4",
        name="APPLE INC",  # Sim = 1.0
        ticker="AAPL",
        exchCode="US",
        marketSector="Equity",
        securityType2="Common Stock",
        shareClassFIGI="BBG001S5N8V8",
    )

    cand_lower_score = OpenFIGICandidate(
        figi="BBG000OTHER2",
        name="APPLE INC - CLA",  # Lower sim
        ticker="AAPL.A",
        exchCode="US",
        marketSector="Equity",
        securityType2="Common Stock",
        shareClassFIGI="BBG001DIFF99",  # Different ID at lower score
    )

    # Higher score wins, NOT ambiguous
    resolved_id, meta = resolve_openfigi_waterfall(cusip, issuer_name, [cand_high_score, cand_lower_score])
    assert resolved_id == "BBG001S5N8V8"
    assert meta["status"] == "RESOLVED"

    # Two candidates at EQUAL top score with different IDs -> MAPPING_AMBIGUOUS
    cand_equal_score = OpenFIGICandidate(
        figi="BBG000EQUAL3",
        name="APPLE INC",  # Exact same name
        ticker="AAPL2",
        exchCode="UN",
        marketSector="Equity",
        securityType2="Common Stock",
        shareClassFIGI="BBG001DIFF99",  # Different ID
    )
    resolved_amb, meta_amb = resolve_openfigi_waterfall(cusip, issuer_name, [cand_high_score, cand_equal_score])
    assert resolved_amb is None
    assert meta_amb["status"] == "MAPPING_AMBIGUOUS"


# ============================================================================
# Module 7: Split Waterfall Tests (Finding 6)
# ============================================================================

def test_split_waterfall_all_8_states():
    """Verify all 8 canonical states in the ordered waterfall precedence truth table."""
    # Gate 0: Corporate Action Unknown
    res_g0 = evaluate_split_waterfall(
        is_corporate_action_unknown=True,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 100.0) for i in range(25)],
    )
    assert res_g0.state == "CORPORATE_ACTION_UNKNOWN"
    assert res_g0.action == "EXCLUDE"
    assert res_g0.split_factor is None

    # Gate 1.1: Known Split, Low Power (N < 20)
    res_g11 = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=True,
        k_ledger=2.0,
        holders=[ContinuousHolder(str(i), 100.0, 200.0) for i in range(10)],
    )
    assert res_g11.state == "KNOWN_SPLIT_LOW_POWER"
    assert res_g11.action == "INCLUDE"
    assert res_g11.split_factor == 2.0
    assert res_g11.sensitivity_action == "EXCLUDE"

    # Gate 1.2a: Known Split, Pass (N >= 20, adjusted median in [0.8, 1.2])
    res_g12a = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=True,
        k_ledger=2.0,
        holders=[ContinuousHolder(str(i), 100.0, 202.0) for i in range(25)],
    )
    assert res_g12a.state == "KNOWN_SPLIT_PASS"
    assert res_g12a.action == "INCLUDE"
    assert res_g12a.split_factor == 2.0
    assert res_g12a.sensitivity_action == "INCLUDE"

    # Gate 1.2b: Known Split, Mismatch (N >= 20, adjusted median not in [0.8, 1.2])
    res_g12b = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=True,
        k_ledger=2.0,
        holders=[ContinuousHolder(str(i), 100.0, 300.0) for i in range(25)],
    )
    assert res_g12b.state == "KNOWN_SPLIT_MISMATCH"
    assert res_g12b.action == "EXCLUDE"
    assert res_g12b.split_factor is None

    # Gate 2.1: Ledger Only, Low Power (has_vendor_splits == False, N < 20)
    res_g21 = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 100.0) for i in range(15)],
    )
    assert res_g21.state == "LEDGER_ONLY_LOW_POWER"
    assert res_g21.action == "INCLUDE"
    assert res_g21.split_factor == 1.0
    assert res_g21.sensitivity_action == "EXCLUDE"

    # Gate 2.2a: Clean (has_vendor_splits == False, N >= 20, no split match)
    res_g22a = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 101.0) for i in range(25)],
    )
    assert res_g22a.state == "CLEAN"
    assert res_g22a.action == "INCLUDE"
    assert res_g22a.split_factor == 1.0
    assert res_g22a.sensitivity_action == "INCLUDE"

    # Gate 2.2b: Split Unknown (has_vendor_splits == False, N >= 20, matched 4:1 split, MAD_log <= 0.15)
    res_g22b = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 399.0) for i in range(25)],
    )
    assert res_g22b.state == "SPLIT_UNKNOWN"
    assert res_g22b.action == "EXCLUDE"
    assert res_g22b.split_factor is None

    # Gate 2.2c: Split Audit Ambiguous High Dispersion (matched factor e.g. 2.0, MAD_log > 0.15)
    holders_disp = [
        ContinuousHolder(str(i), 100.0, 150.0 if i < 15 else (100.0 * 2.0 * 2.0 / 1.5))
        for i in range(30)
    ]
    res_g22c = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=holders_disp,
    )
    assert res_g22c.state == "SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION"
    assert res_g22c.action == "EXCLUDE"


def test_split_waterfall_explicit_split_presence():
    """Test that split existence is separate from net k_ledger (e.g. 2.0 * 0.5 = 1.0)."""
    splits = [
        SplitEvent(ex_date="2024-01-15", ratio=2.0),
        SplitEvent(ex_date="2024-02-15", ratio=0.5),
    ]
    k, has_splits = compute_k_ledger_and_presence("2023-12-31", "2024-03-31", splits)
    assert k == pytest.approx(1.0)
    assert has_splits is True

    # Gate 1 must trigger when has_vendor_splits == True
    holders = [ContinuousHolder(str(i), 100.0, 100.0) for i in range(25)]
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=has_splits,
        k_ledger=k,
        holders=holders,
    )
    # Passed Gate 1.2a
    assert res.state == "KNOWN_SPLIT_PASS"
    assert res.action == "INCLUDE"


def test_split_waterfall_invalid_holder_rejection():
    """Test that ContinuousHolder rejects non-positive shares or blank entity_id."""
    with pytest.raises(ValueError):
        ContinuousHolder("", 100.0, 100.0).validate()
    with pytest.raises(ValueError):
        ContinuousHolder("0001", -10.0, 100.0).validate()
    with pytest.raises(ValueError):
        ContinuousHolder("0001", 100.0, 0.0).validate()
    with pytest.raises(ValueError):
        ContinuousHolder("0001", float("nan"), 100.0).validate()


# ============================================================================
# Module 8: Signal Math Tests (Finding 8)
# ============================================================================

def test_signal_math_strict_validation_and_stock_period_key():
    """Test strict validation and (stock, period) preservation."""
    with pytest.raises(ValueError):
        compute_censor_weight(True, False, 0.0, 0.0, float("nan"), 1000000.0)
    with pytest.raises(ValueError):
        compute_censor_weight(True, False, 0.0, 0.0, -100.0, 1000000.0)

    entity_signals = [
        {"primary_stock_id": "STK_A", "period_of_report": "2024-03-31", "delta_shares": 1000.0, "censor_weight": 1.0},
        {"primary_stock_id": "STK_A", "period_of_report": "2024-03-31", "delta_shares": 500.0, "censor_weight": 0.3},
        {"primary_stock_id": "STK_A", "period_of_report": "2024-06-30", "delta_shares": 200.0, "censor_weight": 1.0},
    ]
    signals = aggregate_m0_signals(entity_signals)
    assert signals[("STK_A", "2024-03-31")] == 1000.0 * 1.0 + 500.0 * 0.3
    assert signals[("STK_A", "2024-06-30")] == 200.0

    # Blank stock ID must raise ValueError
    with pytest.raises(ValueError):
        aggregate_m0_signals([{"primary_stock_id": "", "period_of_report": "2024-03-31", "delta_shares": 10.0}])


# ============================================================================
# Module 9: Coverage Keys Tests
# ============================================================================

def test_coverage_tracker():
    """Test dual-denominator tracking and summary generation."""
    tracker = CoverageTracker()
    tracker.record_d1("037833100", "2024-03-31", filer_count=5, value_usd=1000000.0)
    tracker.record_d1("67066G104", "2024-03-31", filer_count=10, value_usd=2000000.0)

    tracker.record_d2_mapping("037833100", "2024-03-31", "BBG001S5N8V8")
    tracker.record_split_state("BBG001S5N8V8", "2024-03-31", "CLEAN")

    summary = tracker.generate_coverage_summary()
    assert summary["d1_raw_sec_keys_total"] == 2
    assert summary["d2_mapped_keys_total"] == 1
    assert summary["openfigi_mapping_rate"] == 0.5
    assert "CLEAN" in summary["split_state_distribution"]


# ============================================================================
# Module 10: Outcome Policies Tests (Finding 7)
# ============================================================================

def test_outcome_policies_calendar_roll_session_inclusive():
    """Test price selection with calendar-based trading day roll forward up to 5 sessions inclusive."""
    calendar = [
        "2024-05-15",  # offset 0
        "2024-05-16",  # offset 1
        "2024-05-17",  # offset 2
        "2024-05-20",  # offset 3
        "2024-05-21",  # offset 4
        "2024-05-22",  # offset 5 (inclusive)
        "2024-05-23",  # offset 6 (exceeds max_roll_days=5)
    ]
    # Quote appears on 2024-05-22 (offset 5)
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

    # If quote only appears on 2024-05-23 (offset 6), it must not be picked
    price_by_date_late = {"2024-05-23": 160.0}
    p_none, rolls, t_none = select_open_price_with_roll(calendar, price_by_date_late, "2024-05-15", max_roll_days=5)
    assert p_none is None
    assert rolls == 5
    assert t_none is None


def test_outcome_policies_adjusted_open_and_return():
    """Test adjusted open price calculation and return formula."""
    adj_open = compute_adjusted_open_price(raw_open=100.0, raw_close=300.0, adj_close=150.0)
    assert adj_open == 50.0

    assert compute_adjusted_open_price(-10.0, 100.0, 100.0) is None
    assert compute_adjusted_open_price(100.0, 0.0, 100.0) is None
    assert compute_adjusted_open_price(float("nan"), 100.0, 100.0) is None

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

    with pytest.raises(ValueError):
        dup_signals = list(signals) + [signals[0]]
        verify_cardinality_invariant(dup_signals, returns)

    branches = derive_sensitivity_branches(joined)
    assert len(branches["primary"]) == 1
    assert len(branches["missing_minus_100"]) == 3
    assert branches["missing_minus_100"][1]["forward_return"] == -1.0
    assert len(branches["missing_zero"]) == 3
    assert branches["missing_zero"][1]["forward_return"] == 0.0
    assert len(branches["rolled_le_5"]) == 2
