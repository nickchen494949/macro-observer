"""Tests for Stage C2 storage calibration."""

import json
import math
import os
import shutil
import sqlite3
import tempfile
import subprocess
from pathlib import Path
import pytest

from research.smart_money.m0.src.run_c2_storage_calibration import (
    generate_51_contract_periods,
    normalize_cusip,
    get_synthetic_id,
    compute_projection_and_gates,
    get_git_info,
    run_calibration
)

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

def test_get_synthetic_id():
    c1 = "CUSIP1"
    id1 = get_synthetic_id(c1)
    assert len(id1) == 12
    assert id1 == get_synthetic_id(c1)
    
    id2 = get_synthetic_id("CUSIP2")
    assert id1 != id2

def test_compute_projection_and_gates():
    base = 10000
    rows = 200
    pop = 15000
    all_upper = 500 # two_branch = 1000
    ps = 4096
    
    # inserted_rows = 200. diff = 5000. bytes_per_row = ceil(25) = 25
    # emp = ceil(1.2 * (10000 + 25 * 1000) / 4096) * 4096
    # 1.2 * (35000) = 42000 -> ceil(42000/4096)*4096 = 11 * 4096 = 45056
    
    # explicit_non_db = 512 MB
    # floor = 4.5 GB
    # projected = max(45056 + 512MB, 4.5GB) = 4.5 GB
    
    # 2x = 9 GB
    
    # case 1: both pass
    free_bytes = 10 * 1024**3
    res = compute_projection_and_gates(base, rows, pop, all_upper, ps, free_bytes)
    assert res["bytes_per_row"] == 25
    assert res["gate_persistent_pass"] is True
    assert res["gate_transient_pass"] is True
    assert res["final_pass"] is True
    
    # case 2: transient fail (though redundant under 4.5GB floor vs 1.5GB transient)
    # wait, if projected is 4.5GB, persistent needs 9GB. transient needs 4.5 + 1.5 = 6GB.
    # so if free is 7GB, persistent fails, transient passes!
    # it's mathematically impossible for transient to fail while persistent passes.
    # persistent needs 9, transient needs 6.
    
    free_bytes = 7 * 1024**3
    res = compute_projection_and_gates(base, rows, pop, all_upper, ps, free_bytes)
    assert res["gate_persistent_pass"] is False
    assert res["gate_transient_pass"] is True
    assert res["final_pass"] is False
    
    # free bytes 5 GB -> both fail
    free_bytes = 5 * 1024**3
    res = compute_projection_and_gates(base, rows, pop, all_upper, ps, free_bytes)
    assert res["gate_persistent_pass"] is False
    assert res["gate_transient_pass"] is False
    
def create_mock_source_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE filing_events (accession_number TEXT PRIMARY KEY, period_of_report TEXT NOT NULL)")
    conn.execute("CREATE TABLE filing_line_items (accession_number TEXT NOT NULL, cusip TEXT, asset_class TEXT)")
    
    # P1 (top 1) - count 3 valid (c1, c2, c3). duplicate c1, empty, null ignored
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

def test_git_info_mock(monkeypatch):
    def mock_check_output(args, **kwargs):
        if "rev-parse" in args and "HEAD" in args:
            return b"123456"
        if "--show-toplevel" in args:
            return b"/mock/repo"
        if "status" in args:
            return b" M research/smart_money/m0/something.py\n?? untracked.txt"
        raise ValueError("Unknown command")
        
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    sha, repo, m0_dirty, dirty_paths = get_git_info("/mock/repo/research/smart_money/m0")
    assert sha == "123456"
    assert repo == "/mock/repo"
    assert m0_dirty is True
    assert dirty_paths == ["research/smart_money/m0/something.py", "untracked.txt"]

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
        return "sha", "/mock", False, []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    def mock_compute_sha256_file(p):
        return "dummy_hash"
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    
    def mock_is_file():
        return True
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    
    manifest = run_calibration(run_id, str(source_db))
    
    assert manifest["final_decision"] == "PASS"
    assert manifest["sidecars_before"] == []
    assert manifest["sidecars_after"] == []
    assert manifest["query_only_pragma"] == 1
    
    top4 = manifest["selected_pilot_periods"]
    assert top4 == ["2013-09-30", "2013-12-31", "2014-03-31", "2014-06-30"]
    
    counts = manifest["per_period_counts"]
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
        return "sha", "/mock", False, []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)
    
    calls = [0]
    def mock_check_sidecars(p):
        calls[0] += 1
        if calls[0] > 1:
            return [Path(str(p) + "-wal")]
        return []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration._check_sqlite_sidecars", mock_check_sidecars)
    
    with pytest.raises(RuntimeError, match="BLOCK: Source invariance or query_only gate failed."):
        run_calibration(run_id, str(source_db))
        
    manifest_path = tmp_path / "runs2" / run_id / "signal" / "c2_calibration_manifest.json"
    with open(manifest_path) as f:
        m = json.load(f)
    assert m["invariance_failure"] is True
    assert "-wal" in m["sidecars_after"][0]

def test_m0_dirty_preflight_failure(tmp_path, monkeypatch):
    run_id = "test_run_03"
    
    def mock_git_info(root):
        return "sha", "/mock", True, ["research/smart_money/m0/dirty.py"]
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    
    with pytest.raises(RuntimeError, match="M0 dirty preflight abort"):
        run_calibration(run_id, "dummy.db")
