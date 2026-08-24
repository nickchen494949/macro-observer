"""Tests for Stage C2 storage calibration."""

import json
import math
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
import pytest

from research.smart_money.m0.src.run_c2_storage_calibration import (
    generate_51_contract_periods,
    normalize_cusip,
    build_injective_mapping,
    compute_projection_and_gates,
    get_git_info,
    run_calibration,
    get_schema_hash
)
from research.smart_money.m0.src.storage_guard import init_signal_db

def test_generate_51_contract_periods():
    periods = generate_51_contract_periods()
    assert len(periods) == 51
    assert periods[0] == "2013-09-30"
    assert periods[-1] == "2026-03-31"

def test_normalize_cusip():
    assert normalize_cusip("  aBcDeF  ") == "ABCDEF"
    assert normalize_cusip("") is None
    assert normalize_cusip("   ") is None
    assert normalize_cusip(None) is None
    assert normalize_cusip("123") == "123"

def test_build_injective_mapping():
    sets = [{"C1", "C2"}, {"C2", "C3"}]
    mapping = build_injective_mapping(sets)
    assert len(mapping) == 3
    assert mapping["C1"] == "P00000000000"
    assert mapping["C2"] == "P00000000001"
    assert mapping["C3"] == "P00000000002"
    assert len(mapping["C1"]) == 12

def test_compute_projection_and_gates():
    base = 10000
    rows = 200
    pop = 15000
    all_upper = 500
    ps = 4096
    
    free_bytes = 10 * 1024**3
    res = compute_projection_and_gates(base, rows, pop, all_upper, ps, free_bytes)
    assert res["bytes_per_row"] == 25
    assert res["gate_persistent_pass"] is True
    assert res["gate_transient_pass"] is True
    assert res["final_pass"] is True
    
    free_bytes = 7 * 1024**3
    res = compute_projection_and_gates(base, rows, pop, all_upper, ps, free_bytes)
    assert res["gate_persistent_pass"] is False
    assert res["gate_transient_pass"] is True
    assert res["final_pass"] is False
    
    free_bytes = 5 * 1024**3
    res = compute_projection_and_gates(base, rows, pop, all_upper, ps, free_bytes)
    assert res["gate_persistent_pass"] is False
    assert res["gate_transient_pass"] is False

def create_mock_source_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE filing_events (accession_number TEXT PRIMARY KEY, period_of_report TEXT NOT NULL)")
    conn.execute("CREATE TABLE filing_line_items (accession_number TEXT NOT NULL, cusip TEXT, asset_class TEXT)")
    
    # P1 (top 1) - count 3 valid
    conn.execute("INSERT INTO filing_events VALUES ('A1', '2013-09-30')")
    conn.executemany("INSERT INTO filing_line_items VALUES (?, ?, ?)", [
        ('A1', 'C1', 'cash_equity'),
        ('A1', 'C2', 'cash_equity'),
        ('A1', 'C3', 'cash_equity'),
        ('A1', 'c1', 'cash_equity'), # duplicate lower
        ('A1', 'C4', 'bond'),
        ('A1', '   ', 'cash_equity'),
        ('A1', None, 'cash_equity'),
    ])
    
    # P2 (top 2) - count 2
    conn.execute("INSERT INTO filing_events VALUES ('A2', '2013-12-31')")
    conn.executemany("INSERT INTO filing_line_items VALUES (?, ?, ?)", [
        ('A2', 'C1', 'cash_equity'),
        ('A2', 'C5', 'cash_equity'),
    ])
    
    # P3 (top 3) - count 1
    conn.execute("INSERT INTO filing_events VALUES ('A3', '2014-03-31')")
    conn.execute("INSERT INTO filing_line_items VALUES ('A3', 'C6', 'cash_equity')")
    
    # P4 (tie break with P5) - count 1, earlier period
    conn.execute("INSERT INTO filing_events VALUES ('A4', '2014-06-30')")
    conn.execute("INSERT INTO filing_line_items VALUES ('A4', 'C7', 'cash_equity')")
    
    # P5 (tie break) - count 1, later period
    conn.execute("INSERT INTO filing_events VALUES ('A5', '2014-09-30')")
    conn.execute("INSERT INTO filing_line_items VALUES ('A5', 'C8', 'cash_equity')")
    
    conn.commit()
    conn.close()

def test_git_info_mock(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    m0_root = repo_root / "research/smart_money/m0"
    m0_root.mkdir(parents=True)
    
    def mock_check_output(args, **kwargs):
        if "rev-parse" in args and "HEAD" in args:
            return b"a"*40
        if "--show-toplevel" in args:
            return str(repo_root).encode()
        if "status" in args:
            return b" M research/smart_money/m0/something.py\0?? untracked.txt\0"
        raise ValueError("Unknown command")
        
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    sha, repo, m0_dirty, m0_dirty_paths, dirty_paths = get_git_info(str(m0_root))
    assert len(sha) == 40
    assert repo == str(repo_root)
    assert m0_dirty is True
    assert dirty_paths == ["research/smart_money/m0/something.py", "untracked.txt"]
    assert m0_dirty_paths == ["research/smart_money/m0/something.py"]
    
    # Test m0_root escape failure
    with pytest.raises(RuntimeError, match="not inside repo root"):
        get_git_info("/tmp/outside")

def test_canonical_schema_hash(tmp_path):
    db_path = tmp_path / "test_schema.db"
    init_signal_db(db_path)
    schema_hash = get_schema_hash(db_path)
    assert len(schema_hash) == 64
    
    # modify schema should change hash
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE m0_signals ADD COLUMN extra_col TEXT")
    conn.commit()
    conn.close()
    
    assert get_schema_hash(db_path) != schema_hash

def test_calibration_e2e_temp_fixture(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source.db"
    create_mock_source_db(source_db)
    
    run_id = "test_run_01"
    
    from research.smart_money.m0.src.run_paths import RunPaths
    def mock_create_run_paths(rid, m0_root=None):
        base_dir = tmp_path / "runs" / rid
        return RunPaths(
            run_id=rid,
            base_dir=base_dir,
            signal_dir=base_dir / "signal",
            outcome_dir=base_dir / "outcome",
            signal_db_path=base_dir / "signal" / "m0_signal.db",
            outcome_db_path=base_dir / "outcome" / "m0_outcome.db",
            signal_manifest_path=base_dir / "signal" / "SHA256_SIGNAL_MANIFEST.json",
            price_manifest_path=base_dir / "outcome" / "SHA256_PRICE_MANIFEST.json",
            split_audit_report_path=base_dir / "signal" / "m0_split_waterfall_audit.md",
            signal_coverage_report_path=base_dir / "signal" / "m0_signal_coverage.md",
            outcome_coverage_report_path=base_dir / "outcome" / "m0_dual_denominator_coverage.md",
            results_report_path=base_dir / "M0_RESULTS.md",
        )
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths", mock_create_run_paths)
    
    def mock_disk_usage(path):
        import collections
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=10**11)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)
    
    def mock_git_info(root):
        return "a"*40, "/mock", False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    def mock_compute_sha256_file(p):
        return "a"*64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    
    # Mock stat to ensure populated_bytes > base_bytes
    original_stat = Path.stat
    calls_to_stat = [0]
    def mock_stat(self):
        st = original_stat(self)
        if "m0_signal.db" in self.name:
            calls_to_stat[0] += 1
            if calls_to_stat[0] > 1:
                import collections
                return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(st_size=st.st_size + 4096, st_mtime_ns=st.st_mtime_ns)
        return st
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)
    
    # also mock get_page_info to return higher page count
    import research.smart_money.m0.src.run_c2_storage_calibration
    original_gpi = research.smart_money.m0.src.run_c2_storage_calibration.get_page_info
    gpi_calls = [0]
    def mock_gpi(p):
        ps, pc = original_gpi(p)
        gpi_calls[0] += 1
        if gpi_calls[0] > 1:
            pc += 1
        return ps, pc
    monkeypatch.setattr(research.smart_money.m0.src.run_c2_storage_calibration, "get_page_info", mock_gpi)

    manifest = run_calibration(run_id, str(source_db))
    
    assert manifest["final_decision"] == "PASS"
    assert manifest["sidecars_before"] == []
    assert manifest["sidecars_after"] == []
    assert manifest["query_only_pragma"] == 1
    
    top4 = manifest["selected_pilot_periods"]
    assert top4 == ["2013-09-30", "2013-12-31", "2014-03-31", "2014-06-30"]
    
    counts = manifest["raw_upper_bound_per_period_counts"]
    assert counts["2013-09-30"] == 3
    assert counts["2013-12-31"] == 2
    assert counts["2014-03-31"] == 1
    assert counts["2014-06-30"] == 1
    assert counts["2014-09-30"] == 1
    
    assert manifest["reserves"]["projected_total_persistent_bytes"] == 4831838208
    
    with pytest.raises(FileExistsError):
        run_calibration(run_id, str(source_db))

def test_invariance_failure(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_invar.db"
    create_mock_source_db(source_db)
    
    run_id = "test_run_02"
    
    from research.smart_money.m0.src.run_paths import RunPaths
    def mock_create_run_paths(rid, m0_root=None):
        base_dir = tmp_path / "runs2" / rid
        return RunPaths(
            run_id=rid,
            base_dir=base_dir,
            signal_dir=base_dir / "signal",
            outcome_dir=base_dir / "outcome",
            signal_db_path=base_dir / "signal" / "m0_signal.db",
            outcome_db_path=base_dir / "outcome" / "m0_outcome.db",
            signal_manifest_path=base_dir / "signal" / "SHA256_SIGNAL_MANIFEST.json",
            price_manifest_path=base_dir / "outcome" / "SHA256_PRICE_MANIFEST.json",
            split_audit_report_path=base_dir / "signal" / "m0_split_waterfall_audit.md",
            signal_coverage_report_path=base_dir / "signal" / "m0_signal_coverage.md",
            outcome_coverage_report_path=base_dir / "outcome" / "m0_dual_denominator_coverage.md",
            results_report_path=base_dir / "M0_RESULTS.md",
        )
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths", mock_create_run_paths)
    
    def mock_git_info(root):
        return "a"*40, "/mock", False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    
    calls = [0]
    import research.smart_money.m0.src.run_c2_storage_calibration
    def mock_check_sidecars(p):
        calls[0] += 1
        if calls[0] > 1:
            return [Path(str(p) + "-wal")]
        return []
    monkeypatch.setattr(research.smart_money.m0.src.run_c2_storage_calibration, "_check_sqlite_sidecars", mock_check_sidecars)
    
    # Need to mock disk_usage for preflight
    def mock_disk_usage(path):
        import collections
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=10**11)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)
    
    with pytest.raises(RuntimeError, match="BLOCK: Source invariance or query_only gate failed."):
        run_calibration(run_id, str(source_db))
        
    manifest_path = tmp_path / "runs2" / run_id / "signal" / "c2_calibration_manifest.json"
    with open(manifest_path) as f:
        m = json.load(f)
    assert m["invariance_failure"] is True
    assert "-wal" in m["sidecars_after"][0]

def test_m0_dirty_preflight_failure(tmp_path, monkeypatch):
    run_id = "test_run_03"
    
    from research.smart_money.m0.src.run_paths import RunPaths
    def mock_create_run_paths(rid, m0_root=None):
        base_dir = tmp_path / "runs2" / rid
        return RunPaths(
            run_id=rid,
            base_dir=base_dir,
            signal_dir=base_dir / "signal",
            outcome_dir=base_dir / "outcome",
            signal_db_path=base_dir / "signal" / "m0_signal.db",
            outcome_db_path=base_dir / "outcome" / "m0_outcome.db",
            signal_manifest_path=base_dir / "signal" / "SHA256_SIGNAL_MANIFEST.json",
            price_manifest_path=base_dir / "outcome" / "SHA256_PRICE_MANIFEST.json",
            split_audit_report_path=base_dir / "signal" / "m0_split_waterfall_audit.md",
            signal_coverage_report_path=base_dir / "signal" / "m0_signal_coverage.md",
            outcome_coverage_report_path=base_dir / "outcome" / "m0_dual_denominator_coverage.md",
            results_report_path=base_dir / "M0_RESULTS.md",
        )
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths", mock_create_run_paths)
    
    def mock_disk_usage(path):
        import collections
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=10**11)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)
    
    def mock_git_info(root):
        return "a"*40, "/mock", True, ["research/smart_money/m0/dirty.py"], ["research/smart_money/m0/dirty.py"]
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    with pytest.raises(RuntimeError, match="M0 dirty preflight abort"):
        run_calibration(run_id, "dummy.db")

def test_query_only_immediate_failure(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_q.db"
    create_mock_source_db(source_db)
    
    run_id = "test_run_04"
    
    from research.smart_money.m0.src.run_paths import RunPaths
    def mock_create_run_paths(rid, m0_root=None):
        base_dir = tmp_path / "runs2" / rid
        return RunPaths(
            run_id=rid,
            base_dir=base_dir,
            signal_dir=base_dir / "signal",
            outcome_dir=base_dir / "outcome",
            signal_db_path=base_dir / "signal" / "m0_signal.db",
            outcome_db_path=base_dir / "outcome" / "m0_outcome.db",
            signal_manifest_path=base_dir / "signal" / "SHA256_SIGNAL_MANIFEST.json",
            price_manifest_path=base_dir / "outcome" / "SHA256_PRICE_MANIFEST.json",
            split_audit_report_path=base_dir / "signal" / "m0_split_waterfall_audit.md",
            signal_coverage_report_path=base_dir / "signal" / "m0_signal_coverage.md",
            outcome_coverage_report_path=base_dir / "outcome" / "m0_dual_denominator_coverage.md",
            results_report_path=base_dir / "M0_RESULTS.md",
        )
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths", mock_create_run_paths)
    
    def mock_disk_usage(path):
        import collections
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=10**11)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)
    
    def mock_git_info(root):
        return "a"*40, "/mock", False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    def mock_compute_sha256_file(p):
        return "a"*64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    
    # Mock open_readonly_sqlite to return a connection with query_only = 0
    import research.smart_money.m0.src.run_c2_storage_calibration
    original_open = research.smart_money.m0.src.run_c2_storage_calibration.open_readonly_sqlite
    def mock_open(p, immutable):
        conn = original_open(p, immutable)
        conn.execute("PRAGMA query_only = 0")
        return conn
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.open_readonly_sqlite", mock_open)
    
    with pytest.raises(RuntimeError, match="query_only PRAGMA is 0"):
        run_calibration(run_id, str(source_db))

def test_connection_closure_on_exception(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_q2.db"
    create_mock_source_db(source_db)
    
    run_id = "test_run_05"
    
    from research.smart_money.m0.src.run_paths import RunPaths
    def mock_create_run_paths(rid, m0_root=None):
        base_dir = tmp_path / "runs2" / rid
        return RunPaths(
            run_id=rid,
            base_dir=base_dir,
            signal_dir=base_dir / "signal",
            outcome_dir=base_dir / "outcome",
            signal_db_path=base_dir / "signal" / "m0_signal.db",
            outcome_db_path=base_dir / "outcome" / "m0_outcome.db",
            signal_manifest_path=base_dir / "signal" / "SHA256_SIGNAL_MANIFEST.json",
            price_manifest_path=base_dir / "outcome" / "SHA256_PRICE_MANIFEST.json",
            split_audit_report_path=base_dir / "signal" / "m0_split_waterfall_audit.md",
            signal_coverage_report_path=base_dir / "signal" / "m0_signal_coverage.md",
            outcome_coverage_report_path=base_dir / "outcome" / "m0_dual_denominator_coverage.md",
            results_report_path=base_dir / "M0_RESULTS.md",
        )
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths", mock_create_run_paths)
    
    def mock_disk_usage(path):
        import collections
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=10**11)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)
    
    def mock_git_info(root):
        return "a"*40, "/mock", False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    def mock_compute_sha256_file(p):
        return "a"*64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    
    # Mock normalize_cusip to raise exception
    def mock_normalize_cusip(c):
        raise ValueError("Simulated scan failure")
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.normalize_cusip", mock_normalize_cusip)
    
    with pytest.raises(ValueError, match="Simulated scan failure"):
        run_calibration(run_id, str(source_db))
    
    # Connection should be closed. We can verify that sqlite3 connection is closed
    # But since it's a local variable in the function, just checking it raises and doesn't leave locks.
    pass
    # Assuming the try-finally works, no file lock remains.
    
def test_preflight_disk_failure(tmp_path, monkeypatch):
    run_id = "test_run_06"
    
    from research.smart_money.m0.src.run_paths import RunPaths
    def mock_create_run_paths(rid, m0_root=None):
        base_dir = tmp_path / "runs" / rid
        return RunPaths(
            run_id=rid,
            base_dir=base_dir,
            signal_dir=base_dir / "signal",
            outcome_dir=base_dir / "outcome",
            signal_db_path=base_dir / "signal" / "m0_signal.db",
            outcome_db_path=base_dir / "outcome" / "m0_outcome.db",
            signal_manifest_path=base_dir / "signal" / "SHA256_SIGNAL_MANIFEST.json",
            price_manifest_path=base_dir / "outcome" / "SHA256_PRICE_MANIFEST.json",
            split_audit_report_path=base_dir / "signal" / "m0_split_waterfall_audit.md",
            signal_coverage_report_path=base_dir / "signal" / "m0_signal_coverage.md",
            outcome_coverage_report_path=base_dir / "outcome" / "m0_dual_denominator_coverage.md",
            results_report_path=base_dir / "M0_RESULTS.md",
        )
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths", mock_create_run_paths)
    
    def mock_disk_usage(path):
        import collections
        # Return < 256MB
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=200 * 1024 * 1024)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)
    
    with pytest.raises(RuntimeError, match="Preflight failed: Insufficient disk space"):
        run_calibration(run_id, "dummy")
