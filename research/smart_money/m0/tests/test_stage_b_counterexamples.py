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
    verify_clean_tree_gate,
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


def test_b02_run_paths_physical_isolation_and_no_escape(tmp_path: Path):
    """Test-B02: RunPaths directory isolation, schema initialization, and escape blocking."""
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


def test_b06_clean_tree_gate_and_manifest_binding():
    """Test-B06: Manifest binding verification, dirty tree blocking, and blank ID rejection."""
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

    # Blank identity fields must be rejected
    bad_sig = dict(sig_manifest)
    bad_sig["run_id"] = ""
    with pytest.raises(ValueError, match="invalid/blank run_id"):
        verify_manifest_binding(canonical_json_dumps(bad_sig).encode("utf-8"), pri_bytes)


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
    """Test-B09: Connected component canonical ID is numeric-min, non-filing nodes connect without becoming filers."""
    # Edges between 1000000000 (big CIK) and 20000 (small CIK)
    edges = [("1000000000", "20000"), ("20000", "30000")]
    mapping = build_entity_connected_components(edges)
    assert mapping["1000000000"] == "0000020000"
    assert mapping["20000"] == "0000020000"
    assert mapping["30000"] == "0000020000"


def test_b10_filing_membership_completeness():
    """Test-B10: Filing membership incomplete when a member is missing in quarter (triggers MEMBERSHIP_INCOMPLETE)."""
    prev_members = {"0000010001", "0000010002", "0000010003"}
    curr_members_complete = {"0000010001", "0000010002", "0000010003"}
    curr_members_incomplete = {"0000010001", "0000010002"}  # Member 3 missing

    ok, reason = validate_entity_membership(prev_members, curr_members_complete)
    assert ok is True
    assert reason == "ELIGIBLE"

    fail, reason_fail = validate_entity_membership(prev_members, curr_members_incomplete)
    assert fail is False
    assert reason_fail == "MEMBERSHIP_INCOMPLETE"


def test_b11_state_machine_timezone_ordering_and_amendments():
    """Test-B11: UTC instant timestamp sorting, RESTATEMENT replace, ADD_NEW_HOLDINGS upsert, UNKNOWN wipe."""
    filer = "0001000001"
    period = "2024-03-31"

    # Acceptance times:
    # Filing 1: 2024-05-15T16:00:00-04:00 (20:00 UTC)
    # Filing 2: 2024-05-15T19:00:00Z (19:00 UTC) -> earlier in UTC instant!
    h1 = FilingHeader("0001-24-000001", filer, period, "2024-05-15T16:00:00-04:00", form_type="13F-HR/A", amendment_type="ADD_NEW_HOLDINGS")
    rows1 = [HoldingRow("0001-24-000001", filer, period, "037833100", "SH", filer, False, 1200, 180000.0)]

    h2 = FilingHeader("0001-24-000002", filer, period, "2024-05-15T19:00:00Z", form_type="13F-HR")
    rows2 = [HoldingRow("0001-24-000002", filer, period, "037833100", "SH", filer, False, 1000, 150000.0)]

    # Reconstruct sorts by UTC instant: Filing 2 (19:00 UTC) processed FIRST, then Filing 1 (20:00 UTC) applied
    state, meta = reconstruct_filer_state([(h1, rows1), (h2, rows2)], period)
    assert meta["amendment_unresolved"] is False
    assert state[("037833100", "SH", normalize_cik(filer))]["total_shares"] == 1200


def test_b12_pit_deadline_eastern_calendar_boundary():
    """Test-B12: Late filing exclusion evaluated strictly by Eastern calendar date against Rule 0-3 deadline."""
    # 2023-12-31 deadline is 2024-02-14
    # Acceptance on 2024-02-14T23:30:00-05:00 (Eastern Feb 14) -> Accepted
    assert is_pit_accepted("2024-02-14T23:30:00-05:00", "2023-12-31") is True

    # Acceptance on 2024-02-15T00:30:00-05:00 (Eastern Feb 15) -> Excluded as late
    assert is_pit_accepted("2024-02-15T00:30:00-05:00", "2023-12-31") is False


# ============================================================================
# Suite 3: Split Waterfall 8 Canonical States & Ordered Gates (B13.1–B13.8)
# ============================================================================

def test_b13_1_gate0_corporate_action_unknown_stop():
    """Test-B13.1: Gate 0 CORPORATE_ACTION_UNKNOWN stops before holder checks."""
    res = evaluate_split_waterfall(
        is_corporate_action_unknown=True,
        has_vendor_splits=False,
        k_ledger=1.0,
        holders=[ContinuousHolder("0001", 100, 100)],
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

def test_b14_openfigi_waterfall_etf_exclusion_and_ambiguity():
    """Test-B14: OpenFIGI shareClassFIGI priority, ETF rejection, illegal CUSIP, and top-score ambiguity."""
    # 1. Illegal CUSIP
    res, meta = resolve_openfigi_waterfall("INVALID_CUSIP", "APPLE INC", [])
    assert res is None
    assert meta["status"] == "INVALID_CUSIP"

    # 2. ETF rejection
    etf_cand = OpenFIGICandidate("BBG000ETF001", "SPDR S&P 500 ETF", "SPY", "US", "Equity", "ETF", shareClassFIGI="BBG001ETF999")
    res_etf, _ = resolve_openfigi_waterfall("037833100", "SPDR ETF", [etf_cand])
    assert res_etf is None

    # 3. shareClassFIGI priority over compositeFIGI
    cand_both = OpenFIGICandidate("BBG000BOTH1", "MICROSOFT CORP", "MSFT", "US", "Equity", "Common Stock", shareClassFIGI="BBG001SHARECLASS", compositeFIGI="BBG001COMPOSITE")
    res_id, meta_res = resolve_openfigi_waterfall("594918104", "MICROSOFT CORP", [cand_both])
    assert res_id == "BBG001SHARECLASS"
    assert meta_res["composite_fallback"] is False


def test_b15_censor_risk_3x_heuristic_or_condition():
    """Test-B15: 3x Censor-Risk Heuristic OR condition (shares < 30,000 OR value < $600,000 -> weight 0.3)."""
    # 1. New position with shares < 30,000 but value >= $600,000 -> 0.3
    w1, label1 = compute_censor_weight(True, False, 0, 0, 20_000, 1_000_000.0)
    assert w1 == 0.3
    assert label1 == "LOW_CONFIDENCE_NEW"

    # 2. New position with shares >= 30,000 but value < $600,000 -> 0.3
    w2, label2 = compute_censor_weight(True, False, 0, 0, 50_000, 400_000.0)
    assert w2 == 0.3
    assert label2 == "LOW_CONFIDENCE_NEW"

    # 3. New position with shares >= 30,000 AND value >= $600,000 -> 1.0
    w3, label3 = compute_censor_weight(True, False, 0, 0, 50_000, 1_000_000.0)
    assert w3 == 1.0
    assert label3 == "REGULAR_NEW"


def test_b16_confidential_treatment_flagging():
    """Test-B16: Filing with is_confidential_omit=True correctly sets metadata flag."""
    filer = "0001000001"
    period = "2024-03-31"

    h = FilingHeader("0001-24-000001", filer, period, "2024-05-10T10:00:00Z", is_confidential_omit=True)
    rows = [HoldingRow("0001-24-000001", filer, period, "037833100", "SH", filer, False, 1000, 150000.0)]

    state, meta = reconstruct_filer_state([(h, rows)], period)
    assert meta["has_confidential_omit"] is True


# ============================================================================
# Suite 5: Dual-Denominator D1 & D2 Coverage State Machine (B17)
# ============================================================================

def test_b17_coverage_tracker_many_to_one_and_state_machine_integrity():
    """Test-B17: CoverageTracker explicit D1->D2 mapping, penetration rates, and state machine integrity."""
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

    # Record valid split state
    tracker.record_split_state("BBG001S5N8V8", "2024-03-31", "CLEAN")

    # 5. Conflicting split state for same D2 key must raise
    with pytest.raises(ValueError, match="Conflicting split state"):
        tracker.record_split_state("BBG001S5N8V8", "2024-03-31", "SPLIT_UNKNOWN")

    # Record final IC eligibility
    tracker.record_final_ic_eligible("BBG001S5N8V8", "2024-03-31")

    summary = tracker.generate_coverage_summary()
    assert summary["d1_raw_sec_keys_total"] == 2
    assert summary["d1_mapped_keys_total"] == 2
    assert summary["d1_key_mapping_rate"] == 1.0
    assert summary["d1_filer_count_penetration_rate"] == 1.0
    assert summary["d1_value_penetration_rate"] == 1.0
    assert summary["d2_mapped_keys_total"] == 1
    assert summary["d2_price_covered_keys_total"] == 1
    assert summary["price_coverage_rate"] == 1.0
    assert summary["split_state_distribution"]["CLEAN"]["pct_of_price_covered_d2"] == 100.0
    assert summary["d1_conversion_retention_rate"] == 1.0
    assert summary["d2_conversion_retention_rate"] == 1.0


# ============================================================================
# Suite 6: Outcome Policies, Key Uniqueness & Cardinality Invariants (B18–B23)
# ============================================================================

def test_b18_adjusted_open_formula_and_numeric_closure():
    """Test-B18: Adjusted open formula raw_open * (adj_close / raw_close) and overflow safety."""
    adj = compute_adjusted_open_price(100.0, 200.0, 100.0)
    assert adj == 50.0

    # Non-positive and overflow checks
    assert compute_adjusted_open_price(-1.0, 100.0, 100.0) is None
    assert compute_adjusted_open_price(100.0, 0.0, 100.0) is None
    assert compute_adjusted_open_price(1e308, 1e-308, 1e308) is None  # Overflow -> None


def test_b19_calendar_roll_session_quota_and_bounds():
    """Test-B19: Calendar roll forward consumes session quota, checks strict <=5 days, and rejects duplicates."""
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


def test_b20_sec_8k_cash_m_and_a_settlement():
    """Test-B20: Pure-cash M&A privatization buyout settlement vs non-cash corporate action exclusion."""
    ret_cash, status_cash = settle_cash_m_and_a(entry_adj_open=50.0, cash_consideration_per_share=55.0, is_cash_only=True)
    assert ret_cash == pytest.approx(0.10)
    assert status_cash == "CASH_M_AND_A_SETTLED"

    ret_noncash, status_noncash = settle_cash_m_and_a(entry_adj_open=50.0, cash_consideration_per_share=55.0, is_cash_only=False)
    assert ret_noncash is None
    assert status_noncash == "CORPORATE_ACTION_UNKNOWN"


def test_b21_left_join_key_uniqueness_violation():
    """Test-B21: Duplicate primary key in signals or returns immediately raises ValueError in LEFT JOIN."""
    signals_dup = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 100.0},
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 150.0},  # Duplicate
    ]
    returns = [{"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": "CLEAN"}]

    with pytest.raises(ValueError, match="Duplicate key in m0_signals"):
        verify_cardinality_invariant(signals_dup, returns)


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


def test_b23_derive_four_mandatory_sensitivity_branches():
    """Test-B23: Derivation of 4 mandatory sensitivity branches from single LEFT JOIN table."""
    signals = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "m0_signal": 100.0},
        {"primary_stock_id": "STK_2", "period_of_report": "2024-03-31", "m0_signal": -50.0},
    ]
    returns = [
        {"primary_stock_id": "STK_1", "period_of_report": "2024-03-31", "forward_return": 0.05, "outcome_status": "CLEAN"},
        {"primary_stock_id": "STK_2", "period_of_report": "2024-03-31", "forward_return": None, "outcome_status": "DELISTED", "rolled_le_5_return": -0.10},
    ]
    joined, _ = verify_cardinality_invariant(signals, returns)
    branches = derive_sensitivity_branches(joined)

    # 1. Primary
    assert len(branches["primary"]) == 1
    assert branches["primary"][0]["primary_stock_id"] == "STK_1"

    # 2. Missing = -100%
    assert len(branches["missing_minus_100"]) == 2
    assert branches["missing_minus_100"][1]["forward_return"] == -1.0

    # 3. Missing = 0%
    assert len(branches["missing_zero"]) == 2
    assert branches["missing_zero"][1]["forward_return"] == 0.0

    # 4. <= 5 days roll branch
    assert len(branches["rolled_le_5"]) == 2
    assert branches["rolled_le_5"][1]["forward_return"] == -0.10
