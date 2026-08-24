"""Tests for Stage C2 storage calibration."""

import json
import math
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
import pytest

from research.smart_money.m0.src.run_c2_storage_calibration import (
    generate_51_contract_periods,
    run_calibration
)

def test_generate_51_contract_periods():
    periods = generate_51_contract_periods()
    assert len(periods) == 51
    assert periods[0] == "2013-09-30"
    assert periods[-1] == "2026-03-31"

def create_mock_source_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE filing_events (accession_number TEXT PRIMARY KEY, period_of_report TEXT NOT NULL)")
    conn.execute("CREATE TABLE filing_line_items (accession_number TEXT NOT NULL, cusip TEXT, asset_class TEXT)")
    
    # Insert mock data to test filters
    # P1 (top 1) - count 3
    conn.execute("INSERT INTO filing_events VALUES ('A1', '2013-09-30')")
    conn.executemany("INSERT INTO filing_line_items VALUES (?, ?, ?)", [
        ('A1', 'C1', 'cash_equity'),
        ('A1', 'C2', 'cash_equity'),
        ('A1', 'C3', 'cash_equity'),
        ('A1', 'C1', 'cash_equity'), # duplicate
        ('A1', 'C4', 'bond'), # not cash
        ('A1', '', 'cash_equity'), # empty
        ('A1', None, 'cash_equity'), # null
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

def test_gate_failures(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source2.db"
    create_mock_source_db(source_db)
    
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
    
    def mock_disk_usage_fail_persistent(path):
        import collections
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=8000000000)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage_fail_persistent)
    
    with pytest.raises(RuntimeError, match="BLOCK: Storage Calibration Gates Failed"):
        run_calibration("test_fail_1", str(source_db))
        
    manifest_path = tmp_path / "runs2" / "test_fail_1" / "signal" / "c2_calibration_manifest.json"
    with open(manifest_path) as f:
        m = json.load(f)
    assert m["gate_persistent_pass"] is False
    assert m["final_decision"] == "BLOCK"
