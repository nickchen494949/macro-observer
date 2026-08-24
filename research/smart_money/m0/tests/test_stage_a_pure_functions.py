"""Stage A pure-function unit test suite covering 10 major M0 modules.

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
)
from research.smart_money.m0.src.ownership_state_machine import (
    compute_13f_deadline,
    is_pit_accepted,
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
    compute_k_ledger,
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

def test_storage_guard_readonly_uri_encoding(tmp_path: Path):
    """Test read-only SQLite URI generation with special characters."""
    special_dir = tmp_path / "test?dir#with special chars"
    special_dir.mkdir(parents=True, exist_ok=True)
    db_file = special_dir / "sample.db"

    # Create dummy DB
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test (id INT);")
    conn.execute("INSERT INTO test VALUES (42);")
    conn.commit()
    conn.close()

    uri = make_readonly_sqlite_uri(db_file)
    assert uri.startswith("file:")
    assert uri.endswith("?mode=ro")
    assert "%3F" in uri or "?" in uri

    # Open with read-only connection
    ro_conn = open_readonly_sqlite(db_file)
    cur = ro_conn.cursor()
    cur.execute("SELECT id FROM test;")
    row = cur.fetchone()
    assert row[0] == 42

    # Attempt write on read-only connection must fail
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


def test_run_paths_path_traversal_blocked(tmp_path: Path):
    """Test that invalid run_ids with path traversal are rejected."""
    for bad_id in ["../escape", "run/nested", "run;id", "", " "]:
        with pytest.raises(ValueError):
            create_run_paths(bad_id, m0_root=tmp_path)


# ============================================================================
# Module 3: Manifest Integrity Tests
# ============================================================================

def test_manifest_integrity_canonical_json_and_sha256():
    """Test deterministic JSON serialization and SHA-256 calculation."""
    obj = {"z": 1, "a": "hello", "b": [3, 2, 1]}
    dumps1 = canonical_json_dumps(obj)
    dumps2 = canonical_json_dumps({"b": [3, 2, 1], "a": "hello", "z": 1})
    assert dumps1 == dumps2

    h1 = compute_sha256_json(obj)
    h2 = compute_sha256_str(dumps1)
    assert h1 == h2
    assert len(h1) == 64

    # allow_nan=False check
    with pytest.raises(ValueError):
        canonical_json_dumps({"bad": float("nan")})
    with pytest.raises(ValueError):
        canonical_json_dumps({"bad": float("inf")})


def test_manifest_integrity_file_and_cache(tmp_path: Path):
    """Test file hashing and cache verification."""
    f = tmp_path / "test_file.txt"
    f.write_text("antigravity_m0_test_data", encoding="utf-8")

    file_hash = compute_sha256_file(f)
    assert file_hash == compute_sha256_bytes(b"antigravity_m0_test_data")

    # Cache integrity verification
    assert verify_cache_integrity(b"antigravity_m0_test_data", file_hash) is True
    with pytest.raises(ValueError):
        verify_cache_integrity(b"tampered_data", file_hash)


def test_manifest_integrity_binding():
    """Test cross-stage manifest binding verification."""
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

    # Should pass without error
    verify_manifest_binding(sig_manifest, price_manifest)

    # Tampered run_id in price manifest must raise ValueError
    bad_price_manifest = dict(price_manifest)
    bad_price_manifest["run_id"] = "run_002"
    with pytest.raises(ValueError):
        verify_manifest_binding(sig_manifest, bad_price_manifest)

    # Mismatched signal_manifest_sha256 must raise ValueError
    bad_price_manifest2 = dict(price_manifest)
    bad_price_manifest2["signal_manifest_sha256"] = "invalid_hash"
    with pytest.raises(ValueError):
        verify_manifest_binding(sig_manifest, bad_price_manifest2)


# ============================================================================
# Module 4: Ownership & State Machine Tests
# ============================================================================

def test_compute_13f_deadline_sec_calendar():
    """Test SEC Rule 0-3 filing deadline calculation with weekend and holiday roll forward."""
    # 2025-12-31: +45 days is 2026-02-14 (Sat) -> Sun Feb 15 -> Mon Feb 16 (Presidents' Day) -> Tue 2026-02-17
    assert compute_13f_deadline("2025-12-31") == "2026-02-17"

    # 2024-03-31: +45 days is 2024-05-15 (Wed, business day)
    assert compute_13f_deadline("2024-03-31") == "2024-05-15"

    # 2024-06-30: +45 days is 2024-08-14 (Wed, business day)
    assert compute_13f_deadline("2024-06-30") == "2024-08-14"

    # 2023-12-31: +45 days is 2024-02-14 (Wed, business day)
    assert compute_13f_deadline("2023-12-31") == "2024-02-14"


def test_is_pit_accepted():
    """Test PIT acceptance date check in Eastern Time."""
    # 2025-12-31 deadline is 2026-02-17
    assert is_pit_accepted("2026-02-17T17:30:00Z", "2025-12-31") is True
    # 2026-02-18 UTC afternoon is after Eastern deadline
    assert is_pit_accepted("2026-02-18T18:00:00Z", "2025-12-31") is False


def test_resolve_ownership():
    """Test economic ownership resolution from other_manager."""
    filer_cik = "0000012345"
    om_map = {"1": "0000099999", "2": "0000088888"}

    # No other manager -> self
    owner, unresolved = resolve_ownership(None, filer_cik, om_map)
    assert owner == filer_cik and unresolved is False

    owner, unresolved = resolve_ownership("", filer_cik, om_map)
    assert owner == filer_cik and unresolved is False

    # Resolved other manager
    owner, unresolved = resolve_ownership("1", filer_cik, om_map)
    assert owner == "0000099999" and unresolved is False

    # Unresolved other manager
    owner, unresolved = resolve_ownership("99", filer_cik, om_map)
    assert owner is None and unresolved is True


def test_reconstruct_filer_state_original_and_amendments():
    """Test state reconstruction for Original, Restatement, and Add New Holdings."""
    filer_cik = "0001000001"
    period = "2024-03-31"

    # 1. Original filing
    h1 = FilingHeader(
        accession_number="0001-24-000001",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-10T10:00:00Z",
        form_type="13F-HR",
    )
    rows1 = [
        HoldingRow(
            accession_number="0001-24-000001",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="037833100",  # AAPL
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=1000.0,
            total_value_usd=150000.0,
        ),
        HoldingRow(
            accession_number="0001-24-000001",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="594918104",  # MSFT
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=500.0,
            total_value_usd=100000.0,
        ),
    ]

    # 2. Amendment: ADD_NEW_HOLDINGS (updates AAPL with 1200 shares, does NOT add to 1000)
    h2 = FilingHeader(
        accession_number="0001-24-000002",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-12T10:00:00Z",
        form_type="13F-HR/A",
        amendment_type="ADD_NEW_HOLDINGS",
    )
    rows2 = [
        HoldingRow(
            accession_number="0001-24-000002",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="037833100",  # AAPL updated to 1200
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=1200.0,
            total_value_usd=180000.0,
        ),
    ]

    state, meta = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert meta["filings_count"] == 2
    assert meta["amendment_unresolved"] is False

    # AAPL must be 1200.0 (overwritten, not 2200.0)
    aapl_key = ("037833100", "SH", filer_cik)
    msft_key = ("594918104", "SH", filer_cik)
    assert state[aapl_key]["total_shares"] == 1200.0
    assert state[msft_key]["total_shares"] == 500.0


def test_reconstruct_filer_state_restatement_replaces_all():
    """Test that RESTATEMENT replaces the entire state."""
    filer_cik = "0001000001"
    period = "2024-03-31"

    h1 = FilingHeader(
        accession_number="0001-24-000001",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-10T10:00:00Z",
        form_type="13F-HR",
    )
    rows1 = [
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

    h2 = FilingHeader(
        accession_number="0001-24-000002",
        origin_filer_cik=filer_cik,
        period_of_report=period,
        acceptance_datetime="2024-05-12T10:00:00Z",
        form_type="13F-HR/A",
        amendment_type="RESTATEMENT",
    )
    rows2 = [
        HoldingRow(
            accession_number="0001-24-000002",
            origin_filer_cik=filer_cik,
            period_of_report=period,
            cusip="67066G104",  # NVDA replaces AAPL completely
            asset_class="SH",
            economic_owner_cik=filer_cik,
            ownership_unresolved=False,
            total_shares=3000.0,
            total_value_usd=300000.0,
        )
    ]

    state, _ = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert ("037833100", "SH", filer_cik) not in state
    assert state[("67066G104", "SH", filer_cik)]["total_shares"] == 3000.0


# ============================================================================
# Module 5: Entity Membership & Dedup Tests
# ============================================================================

def test_entity_connected_components():
    """Test graph connected component construction with deterministic canonical ID."""
    edges = [
        ("000100", "000200"),
        ("000200", "000300"),
        ("000400", "000500"),
    ]
    mapping = build_entity_connected_components(edges)
    assert mapping["000100"] == "000100"
    assert mapping["000200"] == "000100"
    assert mapping["000300"] == "000100"
    assert mapping["000400"] == "000400"
    assert mapping["000500"] == "000400"


def test_entity_membership_validation():
    """Test membership consistency between Q-1 and Q."""
    # Exact match
    ok, reason = validate_entity_membership({"000100", "000200"}, {"000100", "000200"})
    assert ok is True and reason == "ELIGIBLE"

    # Member dropped
    ok, reason = validate_entity_membership({"000100", "000200"}, {"000100"})
    assert ok is False and reason == "MEMBERSHIP_INCOMPLETE"

    # Empty
    ok, reason = validate_entity_membership(set(), set())
    assert ok is False and reason == "EMPTY_FILING_MEMBERS"


def test_deduplicate_entity_disclosures():
    """Test intra-entity deduplication based on exact economic signatures."""
    entity_id = "000100"
    holdings = [
        # Duplicate 1
        {
            "canonical_entity_id": entity_id,
            "cusip": "037833100",
            "period_of_report": "2024-03-31",
            "economic_owner_cik": "000100",
            "total_shares": 5000.0,
            "total_value_usd": 750000.0,
            "total_vote_sole": 5000.0,
            "total_vote_shared": 0.0,
            "total_vote_none": 0.0,
        },
        # Duplicate 2 (same signature -> should fold)
        {
            "canonical_entity_id": entity_id,
            "cusip": "037833100",
            "period_of_report": "2024-03-31",
            "economic_owner_cik": "000100",
            "total_shares": 5000.0,
            "total_value_usd": 750000.0,
            "total_vote_sole": 5000.0,
            "total_vote_shared": 0.0,
            "total_vote_none": 0.0,
        },
        # Distinct holding (different shares)
        {
            "canonical_entity_id": entity_id,
            "cusip": "037833100",
            "period_of_report": "2024-03-31",
            "economic_owner_cik": "000100",
            "total_shares": 2000.0,
            "total_value_usd": 300000.0,
            "total_vote_sole": 2000.0,
            "total_vote_shared": 0.0,
            "total_vote_none": 0.0,
        },
    ]

    deduped = deduplicate_entity_disclosures(entity_id, holdings)
    assert len(deduped) == 2
    assert deduped[0]["total_shares"] == 5000.0
    assert deduped[1]["total_shares"] == 2000.0

    # Cross-entity mixing must raise error
    with pytest.raises(ValueError):
        bad_holdings = list(holdings)
        bad_holdings.append({"canonical_entity_id": "000999"})
        deduplicate_entity_disclosures(entity_id, bad_holdings)


# ============================================================================
# Module 6: Security Mapping Tests
# ============================================================================

def test_cusip_validation():
    """Test standard CUSIP checksum validation."""
    # Valid CUSIPs
    assert is_valid_cusip("037833100") is True  # Apple
    assert is_valid_cusip("67066G104") is True  # Nvidia
    assert is_valid_cusip("023135106") is True  # Amazon
    assert is_valid_cusip("88160R101") is True  # Tesla
    assert is_valid_cusip("02079K305") is True  # Alphabet

    # Invalid CUSIPs
    assert is_valid_cusip("037833109") is False  # Wrong checksum
    assert is_valid_cusip("INVALID") is False
    assert is_valid_cusip("") is False


def test_jaro_winkler_similarity():
    """Test Jaro-Winkler string similarity."""
    assert jaro_winkler_similarity("APPLE INC", "APPLE INC") == 1.0
    assert jaro_winkler_similarity("APPLE INC", "APPLE INC.") > 0.95
    assert jaro_winkler_similarity("APPLE INC", "MICROSOFT CORP") < 0.5


def test_openfigi_resolution_waterfall():
    """Test OpenFIGI waterfall filtering, shareClass preference, and ETF exclusion."""
    cusip = "037833100"
    issuer_name = "APPLE INC"

    cand_valid = OpenFIGICandidate(
        figi="BBG000B9XRY4",
        name="APPLE INC",
        ticker="AAPL",
        exchCode="US",
        marketSector="Equity",
        securityType2="Common Stock",
        shareClassFIGI="BBG001S5N8V8",
        compositeFIGI="BBG000B9XVV8",
    )

    cand_etf = OpenFIGICandidate(
        figi="BBG000ETF001",
        name="APPLE ETF FUND",
        ticker="AAPLETF",
        exchCode="US",
        marketSector="Equity",
        securityType2="Exchange Traded Fund",  # Strictly excluded
        shareClassFIGI="BBG001ETF999",
    )

    # Valid candidate resolution
    resolved_id, meta = resolve_openfigi_waterfall(cusip, issuer_name, [cand_valid])
    assert resolved_id == "BBG001S5N8V8"
    assert meta["status"] == "RESOLVED"
    assert meta["composite_fallback"] is False

    # ETF candidate rejection
    resolved_etf, meta_etf = resolve_openfigi_waterfall(cusip, issuer_name, [cand_etf])
    assert resolved_etf is None
    assert meta_etf["status"] == "NO_MATCH"

    # Ambiguity detection: multiple distinct primary IDs
    cand_ambig = OpenFIGICandidate(
        figi="BBG000OTHER2",
        name="APPLE INC",
        ticker="AAPL",
        exchCode="UN",
        marketSector="Equity",
        securityType2="Common Stock",
        shareClassFIGI="BBG001DIFF99",  # Different primary ID
    )
    resolved_amb, meta_amb = resolve_openfigi_waterfall(cusip, issuer_name, [cand_valid, cand_ambig])
    assert resolved_amb is None
    assert meta_amb["status"] == "MAPPING_AMBIGUOUS"


# ============================================================================
# Module 7: Split Waterfall & Rational Factors Tests
# ============================================================================

def test_rational_split_factors_size():
    """Verify that FROZEN_RATIONAL_SPLIT_FACTORS contains exactly 204 distinct factors."""
    assert len(FROZEN_RATIONAL_SPLIT_FACTORS) == 204
    assert 2.0 in FROZEN_RATIONAL_SPLIT_FACTORS
    assert 0.5 in FROZEN_RATIONAL_SPLIT_FACTORS
    assert 1.25 in FROZEN_RATIONAL_SPLIT_FACTORS
    assert round(4.0 / 3.0, 6) in {round(x, 6) for x in FROZEN_RATIONAL_SPLIT_FACTORS}


def test_split_waterfall_all_8_states():
    """Verify all 8 canonical states in the ordered waterfall precedence truth table."""
    # Gate 0: Corporate Action Unknown
    res_g0 = evaluate_split_waterfall(
        is_corporate_action_unknown=True,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 100.0) for i in range(25)],
    )
    assert res_g0.state == "CORPORATE_ACTION_UNKNOWN"
    assert res_g0.action == "EXCLUDE"
    assert res_g0.split_factor is None

    # Gate 1.1: Known Split, Low Power (N < 20)
    res_g11 = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
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
        k_ledger=2.0,
        holders=[ContinuousHolder(str(i), 100.0, 300.0) for i in range(25)],
    )
    assert res_g12b.state == "KNOWN_SPLIT_MISMATCH"
    assert res_g12b.action == "EXCLUDE"
    assert res_g12b.split_factor is None

    # Gate 2.1: Ledger Only, Low Power (k_ledger == 1.0, N < 20)
    res_g21 = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 100.0) for i in range(15)],
    )
    assert res_g21.state == "LEDGER_ONLY_LOW_POWER"
    assert res_g21.action == "INCLUDE"
    assert res_g21.split_factor == 1.0
    assert res_g21.sensitivity_action == "EXCLUDE"

    # Gate 2.2a: Clean (k_ledger == 1.0, N >= 20, no split match)
    res_g22a = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 101.0) for i in range(25)],
    )
    assert res_g22a.state == "CLEAN"
    assert res_g22a.action == "INCLUDE"
    assert res_g22a.split_factor == 1.0
    assert res_g22a.sensitivity_action == "INCLUDE"

    # Gate 2.2b: Split Unknown (k_ledger == 1.0, N >= 20, matched 4:1 split, MAD_log <= 0.15)
    res_g22b = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100.0, 399.0) for i in range(25)],
    )
    assert res_g22b.state == "SPLIT_UNKNOWN"
    assert res_g22b.action == "EXCLUDE"
    assert res_g22b.split_factor is None

    # Gate 2.2c: Split Audit Ambiguous High Dispersion (matched factor e.g. 2.0, but MAD_log > 0.15)
    # 15 holders with ratio 1.5 (150/100) and 15 holders with ratio 2.666667 (266.6667/100)
    # median log ratio = (ln(1.5)+ln(2.666667))/2 = ln(2.0) -> tilde_r = 2.0 (exact match to 2.0)
    # deviations from ln(2.0) = |ln(1.5)-ln(2.0)| = 0.2877 > 0.15
    holders_disp = [
        ContinuousHolder(str(i), 100.0, 150.0 if i < 15 else (100.0 * 2.0 * 2.0 / 1.5))
        for i in range(30)
    ]
    res_g22c = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        k_ledger=1.0,
        holders=holders_disp,
    )
    assert res_g22c.state == "SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION"
    assert res_g22c.action == "EXCLUDE"


# ============================================================================
# Module 8: Signal Math Tests
# ============================================================================

def test_signal_math_censor_weight():
    """Test 3x conservative censor-risk heuristic weighting."""
    # NEW position < 30,000 shares
    w, label = compute_censor_weight(
        is_new=True, is_exit=False,
        prev_shares=0.0, prev_value_usd=0.0,
        curr_shares=20000.0, curr_value_usd=1000000.0,
    )
    assert w == 0.3 and label == "LOW_CONFIDENCE_NEW"

    # NEW position < $600,000 value
    w, label = compute_censor_weight(
        is_new=True, is_exit=False,
        prev_shares=0.0, prev_value_usd=0.0,
        curr_shares=50000.0, curr_value_usd=400000.0,
    )
    assert w == 0.3 and label == "LOW_CONFIDENCE_NEW"

    # NEW position >= 30,000 shares AND >= $600,000
    w, label = compute_censor_weight(
        is_new=True, is_exit=False,
        prev_shares=0.0, prev_value_usd=0.0,
        curr_shares=50000.0, curr_value_usd=1000000.0,
    )
    assert w == 1.0 and label == "REGULAR_NEW"

    # EXIT position < 30,000 shares
    w, label = compute_censor_weight(
        is_new=False, is_exit=True,
        prev_shares=15000.0, prev_value_usd=1000000.0,
        curr_shares=0.0, curr_value_usd=0.0,
    )
    assert w == 0.3 and label == "LOW_CONFIDENCE_EXIT"

    # State consistency violations
    with pytest.raises(ValueError):
        compute_censor_weight(True, False, 100.0, 100.0, 100.0, 100.0)  # NEW with prev > 0
    with pytest.raises(ValueError):
        compute_censor_weight(False, True, 100.0, 100.0, 100.0, 100.0)  # EXIT with curr > 0


def test_signal_math_aggregation():
    """Test delta calculation and stock-level signal aggregation."""
    # Delta shares
    delta = compute_entity_delta_shares(prev_shares=100.0, curr_shares=250.0, split_factor=2.0)
    assert delta == 50.0  # 250 - (100 * 2)

    # Aggregation
    entity_signals = [
        {"primary_stock_id": "STK_A", "delta_shares": 1000.0, "censor_weight": 1.0},
        {"primary_stock_id": "STK_A", "delta_shares": 500.0, "censor_weight": 0.3},
        {"primary_stock_id": "STK_B", "delta_shares": -2000.0, "censor_weight": 1.0},
    ]
    signals = aggregate_m0_signals(entity_signals)
    assert signals["STK_A"] == 1000.0 * 1.0 + 500.0 * 0.3  # 1150.0
    assert signals["STK_B"] == -2000.0


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
# Module 10: Outcome Policies Tests
# ============================================================================

def test_outcome_policies_adjusted_open_and_return():
    """Test adjusted open price calculation and return formula."""
    # Adjusted open: 100.0 * (150.0 / 300.0) = 50.0
    adj_open = compute_adjusted_open_price(raw_open=100.0, raw_close=300.0, adj_close=150.0)
    assert adj_open == 50.0

    # Non-positive / invalid prices return None
    assert compute_adjusted_open_price(-10.0, 100.0, 100.0) is None
    assert compute_adjusted_open_price(100.0, 0.0, 100.0) is None
    assert compute_adjusted_open_price(float("nan"), 100.0, 100.0) is None

    # Forward return: (60.0 / 50.0) - 1.0 = +0.20
    ret = compute_forward_return(entry_adj_open=50.0, exit_adj_open=60.0)
    assert ret == pytest.approx(0.20)


def test_outcome_policies_cash_m_and_a():
    """Test cash M&A privatization buyout settlement."""
    # Entry at 50.0, cash buyout at 55.0 -> +10% return
    ret, status = settle_cash_m_and_a(entry_adj_open=50.0, cash_consideration_per_share=55.0, is_cash_only=True)
    assert ret == pytest.approx(0.10)
    assert status == "CASH_M_AND_A_SETTLED"

    # Non-cash or unknown M&A -> None, CORPORATE_ACTION_UNKNOWN
    ret_bad, status_bad = settle_cash_m_and_a(50.0, 55.0, is_cash_only=False)
    assert ret_bad is None
    assert status_bad == "CORPORATE_ACTION_UNKNOWN"


def test_outcome_policies_calendar_roll():
    """Test price selection with calendar-based trading day roll forward."""
    calendar = ["2024-05-15", "2024-05-16", "2024-05-17", "2024-05-20", "2024-05-21", "2024-05-22"]
    # Suspended on 05-15 and 05-16, trades on 05-17
    price_by_date = {
        "2024-05-15": None,
        "2024-05-16": None,
        "2024-05-17": 105.0,
    }

    price, roll_days, trade_date = select_open_price_with_roll(calendar, price_by_date, "2024-05-15", max_roll_days=5)
    assert price == 105.0
    assert roll_days == 2
    assert trade_date == "2024-05-17"


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
        # STK_3 has no return record (missing)
    ]

    joined, metrics = verify_cardinality_invariant(signals, returns)
    assert len(joined) == len(signals)  # Cardinality conserved
    assert metrics["cardinality_conserved"] is True
    assert metrics["missing_count"] == 2
    assert metrics["valid_outcome_count"] == 1

    # Duplicate key in signals must raise ValueError
    with pytest.raises(ValueError):
        dup_signals = list(signals) + [signals[0]]
        verify_cardinality_invariant(dup_signals, returns)

    # Sensitivities derivation
    branches = derive_sensitivity_branches(joined)
    assert len(branches["primary"]) == 1
    assert len(branches["missing_minus_100"]) == 3
    assert branches["missing_minus_100"][1]["forward_return"] == -1.0
    assert len(branches["missing_zero"]) == 3
    assert branches["missing_zero"][1]["forward_return"] == 0.0
    assert len(branches["rolled_le_5"]) == 2  # STK_1 and STK_2 (which has rolled return)
