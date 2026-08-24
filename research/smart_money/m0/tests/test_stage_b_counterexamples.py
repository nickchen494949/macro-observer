"""Stage B Synthetic Adversarial Counterexamples Test Matrix (B01-B23).

Covers all 6 suites from IMPLEMENTATION_PLAN.md:
- Suite 1: Storage Guard, Manifest & Clean Tree Invariant (B01–B06)
- Suite 2: Ownership State Machine, Scope & Entity Membership (B07–B12)
- Suite 3: Split Waterfall 8 Canonical States & Ordered Gates (B13.1–B13.8)
- Suite 4: Target Mapping, Ambiguity Rejection, 3x Censor & Confidential (B14–B16)
- Suite 5: Dual-Denominator D1 & D2 Coverage State Machine (B17)
- Suite 6: Outcome Policies, Key Uniqueness & Cardinality Invariants (B18–B23)

Guarantees:
- Zero network requests.
- Zero access to Phase 0 DB.
- Zero future price fetching.
- 100% synthetic, adversarial pure-function validation.
"""

from datetime import date
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
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
    verify_clean_tree_gate,
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
    filter_pit_entity_edges,
    validate_entity_pair_confidential_gate,
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
from research.smart_money.m0.src.coverage_keys import (
    CoverageTracker,
    VALID_SPLIT_STATES,
    PRIMARY_INCLUDE_SPLIT_STATES,
)
from research.smart_money.m0.src.outcome_policies import (
    compute_adjusted_open_price,
    compute_forward_return,
    settle_cash_m_and_a,
    select_open_price_with_roll,
    verify_cardinality_invariant,
    derive_sensitivity_branches,
)


# ============================================================================
# Suite 1: Storage Guard, Manifest & Clean Tree Invariant (B01–B06)
# ============================================================================

def test_b01_storage_guard_readonly_and_sidecar_blocking(tmp_path: Path):
    """Test-B01: Storage guard URI mode=ro&immutable=1, PRAGMA query_only=ON, and sidecar rejection."""
    db_file = tmp_path / "source.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE source (val TEXT);")
    conn.execute("INSERT INTO source VALUES ('frozen_data');")
    conn.commit()
    conn.close()

    # Valid immutable connection
    ro_conn = open_readonly_sqlite(db_file, immutable=True)
    cur = ro_conn.cursor()
    cur.execute("SELECT val FROM source;")
    assert cur.fetchone()[0] == "frozen_data"
    with pytest.raises(sqlite3.OperationalError):
        cur.execute("INSERT INTO source VALUES ('mutate');")
    ro_conn.close()

    # Create WAL sidecar -> immutable=True must block
    wal_file = tmp_path / "source.db-wal"
    wal_file.write_bytes(b"wal_uncheckpointed")
    with pytest.raises(ValueError, match="sibling sidecar"):
        open_readonly_sqlite(db_file, immutable=True)

    # immutable=False connects with mode=ro
    ro_mutable = open_readonly_sqlite(db_file, immutable=False)
    assert ro_mutable is not None
    ro_mutable.close()


def test_b02_run_paths_physical_isolation_and_symlink_escape_blocking(tmp_path: Path):
    """Test-B02: RunPaths directory isolation, schema initialization, and actual symlink escape blocking."""
    paths = create_run_paths("test_b02_run", m0_root=tmp_path)
    paths.ensure_directories()

    assert paths.signal_dir.is_dir()
    assert paths.outcome_dir.is_dir()
    assert paths.signal_dir != paths.outcome_dir
    assert not paths.signal_dir.is_relative_to(paths.outcome_dir)
    assert not paths.outcome_dir.is_relative_to(paths.signal_dir)

    init_signal_db(paths.signal_db_path)
    init_outcome_db(paths.outcome_db_path)
    assert paths.signal_db_path.is_file()
    assert paths.outcome_db_path.is_file()

    # Path traversal attack
    with pytest.raises(ValueError):
        create_run_paths("../outside", m0_root=tmp_path)

    # Actual symlink escape attack: symlink runs/ pointing to external directory
    outside_dir = tmp_path / "outside_jail"
    outside_dir.mkdir(parents=True, exist_ok=True)
    m0_root = tmp_path / "m0_root"
    m0_root.mkdir(parents=True, exist_ok=True)

    symlink_runs = m0_root / "runs"
    os.symlink(outside_dir, symlink_runs)

    with pytest.raises(ValueError, match="escape symlink"):
        create_run_paths("run_symlink_escape", m0_root=m0_root)


def test_b03_manifest_canonical_types_and_byte_exactness():
    """Test-B03: Manifest strict canonical serialization and non-canonical raw byte rejection."""
    data = {"run_id": "run_b03", "signals_count": 50, "items": [1, 2, 3]}
    canonical_bytes = canonical_json_dumps(data).encode("utf-8")

    parsed, raw, h = parse_and_validate_manifest(canonical_bytes)
    assert parsed["run_id"] == "run_b03"
    assert len(h) == 64

    # Non-canonical spacing / unformatted bytes must be rejected
    unformatted = b'{"items":[1,2,3],"run_id":"run_b03","signals_count":50}'
    with pytest.raises(ValueError, match="do not match exact canonical JSON"):
        parse_and_validate_manifest(unformatted)

    # Disallowed types
    with pytest.raises(TypeError):
        canonical_json_dumps({123: "int_key"})
    with pytest.raises(TypeError):
        canonical_json_dumps({"tuple": (1, 2)})
    with pytest.raises(ValueError):
        canonical_json_dumps({"nan": float("nan")})


def test_b04_manifest_deterministic_reproducibility():
    """Test-B04: Deterministic reproducibility of signal manifest SHA-256."""
    payload1 = {"z": 100, "a": "text", "b": [1, 2]}
    payload2 = {"a": "text", "b": [1, 2], "z": 100}

    h1 = compute_sha256_json(payload1)
    h2 = compute_sha256_json(payload2)
    assert h1 == h2


def test_b05_raw_cache_tampering_detection(tmp_path: Path):
    """Test-B05: Raw API cache file tampering detection."""
    cache_file = tmp_path / "cache_openfigi.json"
    cache_file.write_text('{"figi": "BBG000B9XRY4"}', encoding="utf-8")

    valid_sha = compute_sha256_file(cache_file)
    assert verify_cache_integrity(b'{"figi": "BBG000B9XRY4"}', valid_sha) is True

    # Tampered cache payload
    with pytest.raises(ValueError, match="Cache integrity verification failed"):
        verify_cache_integrity(b'{"figi": "TAMPERED"}', valid_sha)


def test_b06_clean_tree_gate_and_manifest_binding(tmp_path: Path):
    """Test-B06: Clean tree gate with real git repo, manifest binding, bad hashes, and blank ID rejection."""
    # 1. Real temporary git repo clean tree verification
    git_repo = tmp_path / "git_repo"
    git_repo.mkdir()
    subprocess.run(["git", "init"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=git_repo, check=True, capture_output=True)

    dummy_file = git_repo / "committed.txt"
    dummy_file.write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "committed.txt"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=git_repo, check=True, capture_output=True)

    # Clean state
    assert check_git_clean_tree(git_repo) is True
    verify_clean_tree_gate(git_repo)  # Must not raise

    # Create untracked file -> dirty
    untracked = git_repo / "untracked.txt"
    untracked.write_text("dirty", encoding="utf-8")
    assert check_git_clean_tree(git_repo) is False
    with pytest.raises(RuntimeError, match="Clean tree gate violated"):
        verify_clean_tree_gate(git_repo)

    # 2. Manifest binding verification
    sig_manifest = {
        "manifest_type": "SIGNAL_MANIFEST",
        "run_id": "run_clean_001",
        "contract_sha256": "0" * 64,
        "source_git_sha": "a" * 40,
        "m0_code_git_sha": "b" * 40,
        "git_tree_dirty": False,
    }
    sig_bytes = canonical_json_dumps(sig_manifest).encode("utf-8")
    sig_hash = compute_sha256_bytes(sig_bytes)

    pri_manifest = {
        "manifest_type": "PRICE_MANIFEST",
        "run_id": "run_clean_001",
        "contract_sha256": "0" * 64,
        "source_git_sha": "a" * 40,
        "m0_code_git_sha": "b" * 40,
        "signal_manifest_sha256": sig_hash,
        "git_tree_dirty": False,
    }
    pri_bytes = canonical_json_dumps(pri_manifest).encode("utf-8")

    verify_manifest_binding(sig_bytes, pri_bytes)

    # Mismatched signal_manifest_sha256
    bad_pri = dict(pri_manifest)
    bad_pri["signal_manifest_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="Signal manifest SHA-256 binding mismatch"):
        verify_manifest_binding(sig_bytes, canonical_json_dumps(bad_pri).encode("utf-8"))

    # Bad Git SHA (30 hex chars instead of 40/64)
    bad_git_sig = dict(sig_manifest)
    bad_git_sig["source_git_sha"] = "a" * 30
    with pytest.raises(ValueError, match="invalid/blank source_git_sha"):
        verify_manifest_binding(canonical_json_dumps(bad_git_sig).encode("utf-8"), pri_bytes)

    # Bad Contract SHA (non-hex chars)
    bad_contract_sig = dict(sig_manifest)
    bad_contract_sig["contract_sha256"] = "g" * 64
    with pytest.raises(ValueError, match="invalid/blank contract_sha256"):
        verify_manifest_binding(canonical_json_dumps(bad_contract_sig).encode("utf-8"), pri_bytes)


# ============================================================================
# Suite 2: Ownership State Machine, Scope & Entity Membership (B07–B12)
# ============================================================================

def test_b07_ownership_unresolved_isolation():
    """Test-B07: Unresolved other_manager sequence maps to None and is excluded from primary state."""
    filer_cik = "0000012345"
    acc = "0000012345-24-000001"
    om_map = {(acc, "1"): "0000099999"}

    # Sequence '2' is not in om_map -> unresolved
    owner, unresolved = resolve_ownership("2", filer_cik, acc, om_map)
    assert owner is None
    assert unresolved is True

    # HoldingRow with unresolved ownership cannot have economic_owner_cik
    row_unresolved = HoldingRow(acc, filer_cik, "2024-03-31", "037833100", "SH", None, True, 100, 100)
    row_unresolved.validate()

    # Direct aggregation excludes unresolved rows
    agg = aggregate_accession_holdings([row_unresolved])
    assert len(agg) == 0


def test_b08_intra_entity_dedup_and_cross_entity_blocking():
    """Test-B08: Intra-entity disclosure deduplication preserves exact unrounded signatures and blocks cross-entity."""
    entity_a = "0000000100"
    entity_b = "0000000200"

    holdings_a = [
        {"canonical_entity_id": entity_a, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": entity_a, "total_shares": 500, "total_value_usd": 75000.0, "total_vote_sole": 500, "total_vote_shared": 0, "total_vote_none": 0},
        {"canonical_entity_id": entity_a, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": entity_a, "total_shares": 500, "total_value_usd": 75000.0, "total_vote_sole": 500, "total_vote_shared": 0, "total_vote_none": 0},
    ]
    deduped = deduplicate_entity_disclosures(entity_a, holdings_a)
    assert len(deduped) == 1

    # Cross-entity holding in batch must raise ValueError
    cross_holdings = list(holdings_a) + [
        {"canonical_entity_id": entity_b, "cusip": "037833100", "period_of_report": "2024-03-31", "economic_owner_cik": entity_b, "total_shares": 300, "total_value_usd": 45000.0, "total_vote_sole": 300, "total_vote_shared": 0, "total_vote_none": 0}
    ]
    with pytest.raises(ValueError, match="Cross-entity deduplication prohibited"):
        deduplicate_entity_disclosures(entity_a, cross_holdings)


def test_b09_connected_components_numeric_min_and_advisor_nodes():
    """Test-B09: Connected component connects related advisor nodes without making them expected filing members."""
    # Entity with 2 filing managers and 1 non-filing advisor node
    filer_1 = "0000010001"
    filer_2 = "0000010002"
    advisor = "0000099999"

    edges = [(filer_1, advisor), (filer_2, advisor)]
    mapping = build_entity_connected_components(edges)

    assert mapping[filer_1] == "0000010001"
    assert mapping[filer_2] == "0000010001"
    assert mapping[advisor] == "0000010001"

    # Actual filing members only include the 2 filing managers
    prev_filers = {filer_1, filer_2}
    curr_filers = {filer_1, filer_2}
    is_ok, reason = validate_entity_membership(prev_filers, curr_filers)
    assert is_ok is True
    assert reason == "ELIGIBLE"


def test_b10_filing_membership_completeness_16_cik():
    """Test-B10: 16-CIK entity component triggers MEMBERSHIP_INCOMPLETE when 1 member is missing in Q."""
    ciks = [f"{i:010d}" for i in range(1001, 1017)]  # Exactly 16 CIKs
    prev_filing = set(ciks)

    # Q has 1 member missing (member 16 dropped)
    curr_filing_missing_one = set(ciks[:15])

    ok, reason = validate_entity_membership(prev_filing, curr_filing_missing_one)
    assert ok is False
    assert reason == "MEMBERSHIP_INCOMPLETE"


def test_b11_state_machine_amendment_mechanics_and_ordering():
    """Test-B11: UTC instant sorting, RESTATEMENT replace, ADD_NEW_HOLDINGS in-place upsert, UNKNOWN wipe, and mixed metadata."""
    filer = "0001000001"
    period = "2024-03-31"

    # 1. UTC Instant Sorting Attack
    # Filing 1: 2024-05-15T16:00:00-04:00 (20:00 UTC)
    # Filing 2: 2024-05-15T19:00:00Z (19:00 UTC) -> earlier in UTC instant!
    h1 = FilingHeader("0001-24-000001", filer, period, "2024-05-15T16:00:00-04:00", form_type="13F-HR/A", amendment_type="ADD_NEW_HOLDINGS")
    rows1 = [HoldingRow("0001-24-000001", filer, period, "037833100", "SH", filer, False, 1200, 180000.0)]

    h2 = FilingHeader("0001-24-000002", filer, period, "2024-05-15T19:00:00Z", form_type="13F-HR")
    rows2 = [HoldingRow("0001-24-000002", filer, period, "037833100", "SH", filer, False, 1000, 150000.0)]

    state_utc, meta_utc = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert state_utc[("037833100", "SH", normalize_cik(filer))]["total_shares"] == 1200

    # 2. RESTATEMENT full replacement
    h_orig = FilingHeader("0001-24-000003", filer, period, "2024-05-10T10:00:00Z", form_type="13F-HR")
    rows_orig = [
        HoldingRow("0001-24-000003", filer, period, "037833100", "SH", filer, False, 1000, 150000.0),
        HoldingRow("0001-24-000003", filer, period, "594918104", "SH", filer, False, 500, 75000.0),
    ]
    h_restate = FilingHeader("0001-24-000004", filer, period, "2024-05-12T10:00:00Z", form_type="13F-HR/A", amendment_type="RESTATEMENT")
    rows_restate = [
        HoldingRow("0001-24-000004", filer, period, "023135106", "SH", filer, False, 800, 120000.0),
    ]
    state_restate, _ = reconstruct_filer_state([(h_orig, rows_orig), (h_restate, rows_restate)], period)
    assert len(state_restate) == 1
    assert ("023135106", "SH", normalize_cik(filer)) in state_restate
    assert ("037833100", "SH", normalize_cik(filer)) not in state_restate

    # 3. UNKNOWN amendment wipe
    h_unknown = FilingHeader("0001-24-000005", filer, period, "2024-05-14T10:00:00Z", form_type="13F-HR/A", amendment_type="UNKNOWN_AMENDMENT")
    rows_unknown = [HoldingRow("0001-24-000005", filer, period, "037833100", "SH", filer, False, 100, 100.0)]
    state_unk, meta_unk = reconstruct_filer_state([(h_orig, rows_orig), (h_unknown, rows_unknown)], period)
    assert meta_unk["amendment_unresolved"] is True
    assert state_unk == {}

    # 4. Mixed filer rejection
    h_other_filer = FilingHeader("0001-24-000006", "0002000002", period, "2024-05-10T10:00:00Z", form_type="13F-HR")
    with pytest.raises(ValueError, match="Inconsistent origin_filer_cik"):
        reconstruct_filer_state([(h_orig, rows_orig), (h_other_filer, [])], period)

    # 5. Row/header metadata mismatch
    row_mismatch = [HoldingRow("MISMATCH_ACC", filer, period, "037833100", "SH", filer, False, 100, 100.0)]
    with pytest.raises(ValueError, match="HoldingRow metadata mismatch"):
        reconstruct_filer_state([(h_orig, row_mismatch)], period)


def test_b12_pit_deadline_and_entity_edge_filtering():
    """Test-B12: filter_pit_entity_edges excludes late edges and prevents altering Q-1 entity components."""
    period_q1 = "2023-12-31"  # Deadline: 2024-02-14

    edge_records = [
        # On-time edge before deadline
        {
            "origin_cik": "0000010001",
            "related_cik": "0000010002",
            "period_of_report": period_q1,
            "acceptance_datetime": "2024-02-14T17:30:00-05:00",
        },
        # Late edge after deadline (Eastern Feb 15)
        {
            "origin_cik": "0000010001",
            "related_cik": "0000099999",
            "period_of_report": period_q1,
            "acceptance_datetime": "2024-02-15T09:00:00-05:00",
        },
    ]

    pit_edges = filter_pit_entity_edges(edge_records, period_q1)
    assert len(pit_edges) == 1
    assert pit_edges[0] == ("0000010001", "0000010002")

    # Connected components from on-time edges does NOT include the late related node
    mapping = build_entity_connected_components(pit_edges)
    assert "0000010001" in mapping
    assert "0000010002" in mapping
    assert "0000099999" not in mapping


# ============================================================================
# Suite 3: Split Waterfall 8 Canonical States & Ordered Gates (B13.1–B13.8)
# ============================================================================

def test_b13_1_gate0_corporate_action_unknown_stop():
    """Test-B13.1: Gate 0 CORPORATE_ACTION_UNKNOWN stops before holder validation with invalid holder."""
    invalid_holder = ContinuousHolder("0001", 0, 0)  # prev_shares=0 is invalid
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=True,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[invalid_holder],
    )
    assert res.state == "CORPORATE_ACTION_UNKNOWN"
    assert res.action == "EXCLUDE"
    assert res.split_factor is None
    assert res.sensitivity_action == "EXCLUDE"


def test_b13_2_gate1_1_known_split_low_power():
    """Test-B13.2: Gate 1.1 KNOWN_SPLIT_LOW_POWER (ledger split exists, N < 20)."""
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=True,
        k_ledger=2.0,
        holders=[ContinuousHolder(str(i), 100, 200) for i in range(15)],
    )
    assert res.state == "KNOWN_SPLIT_LOW_POWER"
    assert res.action == "INCLUDE"
    assert res.split_factor == 2.0
    assert res.sensitivity_action == "EXCLUDE"


def test_b13_3_gate1_2a_known_split_pass():
    """Test-B13.3: Gate 1.2a KNOWN_SPLIT_PASS (ledger split exists, N >= 20, adjusted median 1.01)."""
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=True,
        k_ledger=2.0,
        holders=[ContinuousHolder(str(i), 100, 202) for i in range(25)],
    )
    assert res.state == "KNOWN_SPLIT_PASS"
    assert res.action == "INCLUDE"
    assert res.split_factor == 2.0
    assert res.sensitivity_action == "INCLUDE"


def test_b13_4_gate1_2b_known_split_mismatch():
    """Test-B13.4: Gate 1.2b KNOWN_SPLIT_MISMATCH (ledger split exists, N >= 20, adjusted median 1.45)."""
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=True,
        k_ledger=2.0,
        holders=[ContinuousHolder(str(i), 100, 290) for i in range(25)],
    )
    assert res.state == "KNOWN_SPLIT_MISMATCH"
    assert res.action == "EXCLUDE"
    assert res.split_factor is None
    assert res.sensitivity_action == "EXCLUDE"


def test_b13_5_gate2_1_ledger_only_low_power():
    """Test-B13.5: Gate 2.1 LEDGER_ONLY_LOW_POWER (no ledger split, N < 20)."""
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100, 100) for i in range(12)],
    )
    assert res.state == "LEDGER_ONLY_LOW_POWER"
    assert res.action == "INCLUDE"
    assert res.split_factor == 1.0
    assert res.sensitivity_action == "EXCLUDE"


def test_b13_6_gate2_2a_clean():
    """Test-B13.6: Gate 2.2a CLEAN (no ledger split, N >= 20, median 1.02, no rational match)."""
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100, 102) for i in range(25)],
    )
    assert res.state == "CLEAN"
    assert res.action == "INCLUDE"
    assert res.split_factor == 1.0
    assert res.sensitivity_action == "INCLUDE"


def test_b13_7_gate2_2b_split_unknown():
    """Test-B13.7: Gate 2.2b SPLIT_UNKNOWN (no ledger split, N >= 20, median 3.99, MAD_log 0.04 <= 0.15)."""
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder(str(i), 100, 399) for i in range(25)],
    )
    assert res.state == "SPLIT_UNKNOWN"
    assert res.action == "EXCLUDE"
    assert res.split_factor is None
    assert res.sensitivity_action == "EXCLUDE"


def test_b13_8_gate2_2c_split_audit_ambiguous_high_dispersion():
    """Test-B13.8: Gate 2.2c SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION (matched 2:1, MAD_log 0.35 > 0.15)."""
    holders_disp = [
        ContinuousHolder(str(i), 100, 150 if i < 15 else (100 * 2 * 2 / 1.5))
        for i in range(30)
    ]
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=holders_disp,
    )
    assert res.state == "SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION"
    assert res.action == "EXCLUDE"
    assert res.split_factor is None


# ============================================================================
# Suite 4: Target Mapping, Ambiguity Rejection, 3x Censor & Confidential (B14–B16)
# ============================================================================

def test_b14_openfigi_waterfall_comprehensive():
    """Test-B14: OpenFIGI shareClassFIGI priority, composite fallback, ETF exclusion, nonalphanumeric gate, and ambiguity."""
    # 1. Illegal CUSIP
    res_inv, meta_inv = resolve_openfigi_waterfall("INVALID_CUSIP", "APPLE INC", [])
    assert res_inv is None
    assert meta_inv["status"] == "INVALID_CUSIP"

    # 2. Non-alphanumeric SEC issuer name gate
    res_na_iss, meta_na_iss = resolve_openfigi_waterfall("037833100", "!!!", [])
    assert res_na_iss is None
    assert meta_na_iss["status"] == "EMPTY_OR_NONALPHANUMERIC_ISSUER_NAME"

    # 3. Non-alphanumeric candidate name filtering
    cand_punct = OpenFIGICandidate("BBG000PUNCT1", "!!!", "AAPL", "US", "Equity", "Common Stock", shareClassFIGI="BBG001PUNCT1")
    res_na_cand, meta_na_cand = resolve_openfigi_waterfall("037833100", "APPLE INC", [cand_punct])
    assert res_na_cand is None
    assert meta_na_cand["status"] == "NO_MATCH"

    # 4. ETF exclusion
    etf_cand = OpenFIGICandidate("BBG000ETF001", "SPDR S&P 500 ETF", "SPY", "US", "Equity", "ETF", shareClassFIGI="BBG001ETF999")
    res_etf, meta_etf = resolve_openfigi_waterfall("037833100", "SPDR ETF", [etf_cand])
    assert res_etf is None
    assert meta_etf["status"] == "NO_MATCH"

    # 5. shareClassFIGI priority over compositeFIGI
    cand_both = OpenFIGICandidate("BBG000BOTH1", "MICROSOFT CORP", "MSFT", "US", "Equity", "Common Stock", shareClassFIGI="BBG001SHARECLASS", compositeFIGI="BBG001COMPOSITE")
    res_sc, meta_sc = resolve_openfigi_waterfall("594918104", "MICROSOFT CORP", [cand_both])
    assert res_sc == "BBG001SHARECLASS"
    assert meta_sc["composite_fallback"] is False

    # 6. compositeFIGI fallback when shareClassFIGI is empty
    cand_comp = OpenFIGICandidate("BBG000COMP1", "MICROSOFT CORP", "MSFT", "US", "Equity", "Common Stock", shareClassFIGI=None, compositeFIGI="BBG001COMPOSITE_ONLY")
    res_comp, meta_comp = resolve_openfigi_waterfall("594918104", "MICROSOFT CORP", [cand_comp])
    assert res_comp == "BBG001COMPOSITE_ONLY"
    assert meta_comp["composite_fallback"] is True

    # 7. Equal top-score multi-ID ambiguity rejection
    cand_amb_1 = OpenFIGICandidate("BBG000AMB001", "ACME CORP", "ACM", "US", "Equity", "Common Stock", shareClassFIGI="BBG001ID_ONE")
    cand_amb_2 = OpenFIGICandidate("BBG000AMB002", "ACME CORP", "ACM.B", "US", "Equity", "Common Stock", shareClassFIGI="BBG001ID_TWO")
    res_amb, meta_amb = resolve_openfigi_waterfall("000360206", "ACME CORP", [cand_amb_1, cand_amb_2])
    assert res_amb is None
    assert meta_amb["status"] == "MAPPING_AMBIGUOUS"

    # 8. Higher-score wins over lower-score distinct ID (not ambiguity)
    cand_high = OpenFIGICandidate("BBG000HIGH1", "ACME CORP", "ACM", "US", "Equity", "Common Stock", shareClassFIGI="BBG001WINNER")
    cand_low = OpenFIGICandidate("BBG000LOW02", "ACME CORPORATION INC", "ACM.L", "US", "Equity", "Common Stock", shareClassFIGI="BBG001LOSER")
    res_win, meta_win = resolve_openfigi_waterfall("000360206", "ACME CORP", [cand_high, cand_low])
    assert res_win == "BBG001WINNER"
    assert meta_win["status"] == "RESOLVED"


def test_b15_censor_risk_3x_heuristic_comprehensive():
    """Test-B15: 3x Censor-Risk Heuristic OR condition across NEW, EXIT, and inconsistent flag rejections."""
    # NEW position tests
    w1, l1 = compute_censor_weight(True, False, 0, 0, 20_000, 1_000_000.0)
    assert w1 == 0.3 and l1 == "LOW_CONFIDENCE_NEW"

    w2, l2 = compute_censor_weight(True, False, 0, 0, 50_000, 400_000.0)
    assert w2 == 0.3 and l2 == "LOW_CONFIDENCE_NEW"

    w3, l3 = compute_censor_weight(True, False, 0, 0, 50_000, 1_000_000.0)
    assert w3 == 1.0 and l3 == "REGULAR_NEW"

    # EXIT position tests
    w4, l4 = compute_censor_weight(False, True, 20_000, 1_000_000.0, 0, 0)
    assert w4 == 0.3 and l4 == "LOW_CONFIDENCE_EXIT"

    w5, l5 = compute_censor_weight(False, True, 50_000, 400_000.0, 0, 0)
    assert w5 == 0.3 and l5 == "LOW_CONFIDENCE_EXIT"

    w6, l6 = compute_censor_weight(False, True, 50_000, 1_000_000.0, 0, 0)
    assert w6 == 1.0 and l6 == "REGULAR_EXIT"

    # Inconsistent flag rejections
    with pytest.raises(ValueError, match="cannot simultaneously be NEW and EXIT"):
        compute_censor_weight(True, True, 0, 0, 100, 100.0)

    with pytest.raises(ValueError, match="NEW position consistency error"):
        compute_censor_weight(True, False, 100, 100.0, 100, 100.0)

    with pytest.raises(ValueError, match="EXIT position consistency error"):
        compute_censor_weight(False, True, 100, 100.0, 100, 100.0)


def test_b16_entity_pair_confidential_gate():
    """Test-B16: Confidential treatment omission gate across quarter pair (Q-1 and Q)."""
    meta_clean = {"has_confidential_omit": False}
    meta_omit = {"has_confidential_omit": True}

    # 1. Q-1 omit -> Ineligible
    ok1, r1 = validate_entity_pair_confidential_gate(meta_omit, meta_clean)
    assert ok1 is False and r1 == "CONFIDENTIAL_TREATMENT_OMISSION"

    # 2. Q omit -> Ineligible
    ok2, r2 = validate_entity_pair_confidential_gate(meta_clean, meta_omit)
    assert ok2 is False and r2 == "CONFIDENTIAL_TREATMENT_OMISSION"

    # 3. Clean pair -> Eligible
    ok3, r3 = validate_entity_pair_confidential_gate(meta_clean, meta_clean)
    assert ok3 is True and r3 == "ELIGIBLE"


# ============================================================================
# Suite 5: Dual-Denominator D1 & D2 Coverage State Machine (B17)
# ============================================================================

def test_b17_coverage_tracker_many_to_one_and_state_machine_integrity():
    """Test-B17: CoverageTracker D1->D2 mapping, penetration rates, and state machine integrity attacks."""
    tracker = CoverageTracker()

    # D1 A (count 10, value 100) + D1 B (count 20, value 200) -> same D2 stock X
    tracker.record_d1("037833100", "2024-03-31", filer_count=10, value_usd=100.0)
    tracker.record_d1("037833200", "2024-03-31", filer_count=20, value_usd=200.0)

    tracker.record_d2_mapping("037833100", "2024-03-31", "BBG001S5N8V8")
    tracker.record_d2_mapping("037833200", "2024-03-31", "BBG001S5N8V8")

    # State machine integrity attacks:
    # 1. Map unregistered D1 key must raise
    with pytest.raises(ValueError, match="unregistered D1 key"):
        tracker.record_d2_mapping("UNREGISTERED", "2024-03-31", "BBG001S5N8V8")

    # 2. Conflicting remap of D1 key must raise
    with pytest.raises(ValueError, match="Conflicting D2 remap"):
        tracker.record_d2_mapping("037833100", "2024-03-31", "BBG001DIFF99")

    # 3. Price covered for unmapped D2 must raise
    with pytest.raises(ValueError, match="unmapped D2 key"):
        tracker.record_d2_price_covered("UNMAPPED_D2", "2024-03-31")

    # Record valid price coverage
    tracker.record_d2_price_covered("BBG001S5N8V8", "2024-03-31")

    # 4. Mutually exclusive price missing for price covered key must raise
    with pytest.raises(ValueError, match="already recorded as price covered"):
        tracker.record_d2_price_missing("BBG001S5N8V8", "2024-03-31")

    # 5. Invalid split state string must raise
    with pytest.raises(ValueError, match="Invalid split state"):
        tracker.record_split_state("BBG001S5N8V8", "2024-03-31", "NOT_A_VALID_SPLIT_STATE")

    # Record valid split state
    tracker.record_split_state("BBG001S5N8V8", "2024-03-31", "CLEAN")

    # 6. Conflicting split state for same D2 key must raise
    with pytest.raises(ValueError, match="Conflicting split state"):
        tracker.record_split_state("BBG001S5N8V8", "2024-03-31", "SPLIT_UNKNOWN")

    # 7. Final IC eligibility on an EXCLUDE split state must raise
    tracker.record_d1("037833300", "2024-03-31", filer_count=5, value_usd=50.0)
    tracker.record_d2_mapping("037833300", "2024-03-31", "BBG001EXCLUDE1")
    tracker.record_d2_price_covered("BBG001EXCLUDE1", "2024-03-31")
    tracker.record_split_state("BBG001EXCLUDE1", "2024-03-31", "SPLIT_UNKNOWN")
    with pytest.raises(ValueError, match="must be in Primary-INCLUDE"):
        tracker.record_final_ic_eligible("BBG001EXCLUDE1", "2024-03-31")

    # 8. Attrition for unregistered D1 key must raise
    with pytest.raises(ValueError, match="unregistered D1 key"):
        tracker.record_attrition("UNREGISTERED_CUSIP", "2024-03-31", "unmapped_cusip")

    # Record valid final IC eligibility for clean stock
    tracker.record_final_ic_eligible("BBG001S5N8V8", "2024-03-31")

    summary = tracker.generate_coverage_summary()
    assert summary["d1_raw_sec_keys_total"] == 3
    assert summary["d1_mapped_keys_total"] == 3
    assert summary["d1_key_mapping_rate"] == 1.0
    assert 0.0 <= summary["d1_filer_count_penetration_rate"] <= 1.0
    assert 0.0 <= summary["d1_value_penetration_rate"] <= 1.0
    assert summary["d2_mapped_keys_total"] == 2
    assert summary["d2_price_covered_keys_total"] == 2
    assert summary["price_coverage_rate"] == 1.0
    assert summary["split_state_distribution"]["CLEAN"]["pct_of_price_covered_d2"] == 50.0
    assert summary["split_state_distribution"]["SPLIT_UNKNOWN"]["pct_of_price_covered_d2"] == 50.0


# ============================================================================
# Suite 6: Outcome Policies, Key Uniqueness & Cardinality Invariants (B18–B23)
# ============================================================================

def test_b18_price_and_signal_formulas_numeric_closure():
    """Test-B18: Numeric closure and overflow safety across price, outcome, holder stats, and delta shares."""
    # 1. Adjusted open formula & overflow
    assert compute_adjusted_open_price(100.0, 200.0, 100.0) == 50.0
    assert compute_adjusted_open_price(-1.0, 100.0, 100.0) is None
    assert compute_adjusted_open_price(1e308, 1e-308, 1e308) is None

    # 2. Forward return & overflow
    assert compute_forward_return(50.0, 60.0) == pytest.approx(0.20)
    assert compute_forward_return(1e-308, 1e308) is None

    # 3. Cash M&A settlement & overflow
    ret_mna, status_mna = settle_cash_m_and_a(50.0, 55.0, is_cash_only=True)
    assert ret_mna == pytest.approx(0.10) and status_mna == "CASH_M_AND_A_SETTLED"
    ret_over, status_over = settle_cash_m_and_a(1e-308, 1e308, is_cash_only=True)
    assert ret_over is None and status_over == "CORPORATE_ACTION_UNKNOWN"

    # 4. Delta shares & overflow
    assert compute_entity_delta_shares(100, 250, 2.0) == 50.0
    with pytest.raises(ValueError, match="overflow"):
        compute_entity_delta_shares(1e308, 100, 1e308)

    # 5. Holder log statistics & overflow
    h_valid = [ContinuousHolder("0001", 100, 200)]
    t_r, mad, t_adj, n = compute_holder_log_statistics(h_valid, 2.0)
    assert t_r == pytest.approx(2.0) and n == 1

    h_overflow = [ContinuousHolder("0001", 1e-308, 1e308)]
    with pytest.raises(ValueError, match="overflow"):
        compute_holder_log_statistics(h_overflow, 1.0)


def test_b19_calendar_roll_session_quota_and_bounds():
    """Test-B19: Calendar roll forward consumes session quota, checks strict <=5 days, and rejects duplicates/invalid dates."""
    cal = ["2024-05-15", "2024-05-16", "2024-05-17", "2024-05-20", "2024-05-21", "2024-05-22", "2024-05-23"]
    price_map = {"2024-05-22": 150.0}  # Available on 5th rolled session

    p, roll, date_hit = select_open_price_with_roll(cal, price_map, "2024-05-15", max_roll_days=5)
    assert p == 150.0
    assert roll == 5
    assert date_hit == "2024-05-22"

    # Price available only on 6th rolled session (2024-05-23) -> exceeds quota, returns None
    price_map_late = {"2024-05-23": 150.0}
    p_late, roll_late, _ = select_open_price_with_roll(cal, price_map_late, "2024-05-15", max_roll_days=5)
    assert p_late is None
    assert roll_late == 5

    # Invalid / non-positive / overflow prices treated as missing
    price_map_invalid = {"2024-05-15": -10.0, "2024-05-16": float("nan"), "2024-05-17": 120.0}
    p_inv, roll_inv, date_inv = select_open_price_with_roll(cal, price_map_invalid, "2024-05-15", max_roll_days=5)
    assert p_inv == 120.0
    assert roll_inv == 2
    assert date_inv == "2024-05-17"

    # Rejection of duplicate sessions and invalid date strings
    with pytest.raises(ValueError, match="duplicate date"):
        select_open_price_with_roll(["2024-05-15", "2024-05-15"], price_map, "2024-05-15", max_roll_days=5)

    with pytest.raises(ValueError, match="Invalid ISO date format"):
        select_open_price_with_roll(["not-a-date"], price_map, "2024-05-15", max_roll_days=5)


def test_b20_sec_8k_cash_m_and_a_settlement():
    """Test-B20: Pure-cash M&A privatization buyout settlement vs non-cash corporate action exclusion."""
    ret_cash, status_cash = settle_cash_m_and_a(entry_adj_open=50.0, cash_consideration_per_share=55.0, is_cash_only=True)
    assert ret_cash == pytest.approx(0.10)
    assert status_cash == "CASH_M_AND_A_SETTLED"

    ret_noncash, status_noncash = settle_cash_m_and_a(entry_adj_open=50.0, cash_consideration_per_share=55.0, is_cash_only=False)
    assert ret_noncash is None
    assert status_noncash == "CORPORATE_ACTION_UNKNOWN"


def test_b21_left_join_duplicate_key_rejections():
    """Test-B21: Duplicate primary key in signals or returns immediately raises ValueError in LEFT JOIN."""
    signals_dup = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 100.0},
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 150.0},  # Duplicate
    ]
    returns_clean = [{"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": "CLEAN"}]

    with pytest.raises(ValueError, match="Duplicate key in m0_signals"):
        verify_cardinality_invariant(signals_dup, returns_clean)

    signals_clean = [{"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 100.0}]
    returns_dup = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": "CLEAN"},
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.08, "outcome_status": "CLEAN"},  # Duplicate
    ]
    with pytest.raises(ValueError, match="Duplicate key in m0_forward_returns"):
        verify_cardinality_invariant(signals_clean, returns_dup)


def test_b22_cardinality_conservation_invariant():
    """Test-B22: Cardinality invariant COUNT(joined) == COUNT(signals) and missing outcomes 100% preserved."""
    signals = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 100.0},
        {"primary_stock_id": "STK_2", "period_of_report": "2024-03-31", "m0_signal": -50.0},
        {"primary_stock_id": "STK_3", "period_of_report": "2024-03-31", "m0_signal": 200.0},
    ]
    returns = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": "CLEAN"},
    ]

    joined, metrics = verify_cardinality_invariant(signals, returns)
    assert len(joined) == 3
    assert metrics["cardinality_conserved"] is True
    assert metrics["missing_count"] == 2
    assert metrics["valid_outcome_count"] == 1


def test_b23_derive_four_mandatory_sensitivity_branches_and_non_mutation():
    """Test-B23: Derivation of 4 mandatory sensitivity branches and immutability of joined input rows."""
    signals = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 100.0},
        {"primary_stock_id": "STK_2", "period_of_report": "2024-03-31", "m0_signal": -50.0},
    ]
    returns = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": "CLEAN"},
        {"primary_stock_id": "STK_2", "period_of_report": "2024-03-31", "forward_return": None, "outcome_status": "DELISTED", "rolled_le_5_return": -0.10},
    ]
    joined, _ = verify_cardinality_invariant(signals, returns)

    # Snapshot of joined rows before derivation
    joined_snapshot = [dict(r) for r in joined]

    branches = derive_sensitivity_branches(joined)

    # 1. Primary
    assert len(branches["primary"]) == 1
    assert branches["primary"][0]["primary_stock_id"] == "STK_1"
    assert branches["primary"][0]["forward_return"] == 0.05

    # 2. Missing = -100%
    assert len(branches["missing_minus_100"]) == 2
    assert branches["missing_minus_100"][0]["forward_return"] == 0.05
    assert branches["missing_minus_100"][1]["forward_return"] == -1.0

    # 3. Missing = 0%
    assert len(branches["missing_zero"]) == 2
    assert branches["missing_zero"][0]["forward_return"] == 0.05
    assert branches["missing_zero"][1]["forward_return"] == 0.0

    # 4. <= 5 days roll branch
    assert len(branches["rolled_le_5"]) == 2
    assert branches["rolled_le_5"][0]["forward_return"] == 0.05
    assert branches["rolled_le_5"][1]["forward_return"] == -0.10

    # Invariance check: original joined rows must NOT have been mutated
    assert joined == joined_snapshot
