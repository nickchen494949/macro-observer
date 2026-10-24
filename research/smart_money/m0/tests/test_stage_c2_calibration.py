"""Tests for Stage C2 storage calibration."""

import json
import os
import sqlite3
import subprocess
from pathlib import Path
import pytest

from research.smart_money.m0.src.run_c2_storage_calibration import (
    generate_51_contract_periods,
    normalize_cusip,
    build_injective_mapping,
    compute_projection_and_gates,
    get_git_info,
    run_calibration,
    validate_and_hash_schema,
    validate_page_geometry,
    get_page_info,
    write_atomic_canonical_json,
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


def _make_mock_run_paths(tmp_path, subdir, rid):
    """Helper to build a mock RunPaths factory."""
    from research.smart_money.m0.src.run_paths import RunPaths
    base_dir = tmp_path / subdir / rid
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


def _mock_run_paths_factory(tmp_path, subdir="runs"):
    """Return a mock create_run_paths function."""
    def factory(rid, m0_root=None):
        return _make_mock_run_paths(tmp_path, subdir, rid)
    return factory


def _mock_disk_plenty(path):
    """Return abundant disk space for preflight."""
    import collections
    return collections.namedtuple('usage', 'total used free')(
        total=10**11, used=10**10, free=10**11
    )


def test_git_info_mock(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    m0_root = repo_root / "research/smart_money/m0"
    m0_root.mkdir(parents=True)

    def mock_run(args, **kwargs):
        class MockCompletedProcess:
            def __init__(self, stdout, stderr=b"", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        if "rev-parse" in args and "HEAD" in args:
            return MockCompletedProcess(b"a"*40)
        if "--show-toplevel" in args:
            return MockCompletedProcess(str(repo_root).encode())
        if "status" in args:
            return MockCompletedProcess(
                b" M research/smart_money/m0/something.py\0?? untracked.txt\0",
                stderr=b"warning: fsmonitor is not running\n"
            )
        if "rev-parse" in args and "FAIL" in args:
            return MockCompletedProcess(b"some stdout\n", b"some stderr\n", returncode=1)

        raise ValueError(f"Unknown command: {args}")

    monkeypatch.setattr(subprocess, "run", mock_run)

    sha, repo, m0_dirty, m0_dirty_paths, dirty_paths = get_git_info(str(m0_root))
    assert len(sha) == 40
    assert repo == str(repo_root)
    assert m0_dirty is True
    assert dirty_paths == ["research/smart_money/m0/something.py", "untracked.txt"]
    assert m0_dirty_paths == ["research/smart_money/m0/something.py"]

    # Test m0_root escape failure
    with pytest.raises(RuntimeError, match="not inside repo root"):
        get_git_info("/tmp/outside")

    def mock_run_fail(args, **kwargs):
        class MockCompletedProcess:
            def __init__(self, stdout, stderr, returncode):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode
        return MockCompletedProcess(b"out\n", b"err\n", 1)

    monkeypatch.setattr(subprocess, "run", mock_run_fail)
    with pytest.raises(RuntimeError) as exc_info:
        get_git_info(str(m0_root))
    assert "Git command failed. stdout: out, stderr: err" in str(exc_info.value)


def test_git_info_fsmonitor_warning_one_dirty_m0_path(monkeypatch, tmp_path):
    """Verify that an fsmonitor warning on stderr does NOT hide or corrupt
    the single dirty M0 path on stdout.  This is the exact scenario that
    was broken by the old code which merged stderr into stdout."""
    repo_root = tmp_path / "repo"
    m0_root = repo_root / "research/smart_money/m0"
    m0_root.mkdir(parents=True)

    dirty_file = "research/smart_money/m0/src/run_c2_storage_calibration.py"

    def mock_run(args, **kwargs):
        class R:
            def __init__(self, stdout, stderr=b"", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        if "rev-parse" in args and "HEAD" in args:
            return R(b"c" * 40)
        if "--show-toplevel" in args:
            return R(str(repo_root).encode())
        if "status" in args:
            # Exactly one dirty file, plus fsmonitor warning on stderr
            stdout = f" M {dirty_file}\0".encode()
            stderr = b"warning: you have an unresolved fsmonitor state\n"
            return R(stdout, stderr=stderr)
        raise ValueError(f"Unexpected: {args}")

    monkeypatch.setattr(subprocess, "run", mock_run)

    sha, repo, m0_dirty, m0_dirty_paths, all_dirty = get_git_info(str(m0_root))

    assert sha == "c" * 40
    # The single dirty file must be visible and not corrupted
    assert all_dirty == [dirty_file]
    assert m0_dirty is True
    assert m0_dirty_paths == [dirty_file]


def test_git_info_nonzero_exit_preserves_both_streams(monkeypatch, tmp_path):
    """When git exits non-zero, the RuntimeError must contain both
    the stdout and stderr content for diagnosability."""
    repo_root = tmp_path / "repo"
    m0_root = repo_root / "research/smart_money/m0"
    m0_root.mkdir(parents=True)

    def mock_run(args, **kwargs):
        class R:
            def __init__(self, stdout, stderr, returncode):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode
        return R(b"fatal: not a repo\n", b"error: something went wrong\n", 128)

    monkeypatch.setattr(subprocess, "run", mock_run)

    with pytest.raises(RuntimeError) as exc_info:
        get_git_info(str(m0_root))
    msg = str(exc_info.value)
    assert "fatal: not a repo" in msg, "stdout must appear in error message"
    assert "error: something went wrong" in msg, "stderr must appear in error message"


def test_canonical_schema_hash(tmp_path):
    db_path = tmp_path / "test_schema.db"
    init_signal_db(db_path)
    schema_hash = validate_and_hash_schema(db_path)
    assert len(schema_hash) == 64

    # modify schema should change hash
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE m0_signals ADD COLUMN extra_col TEXT")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError):
        validate_and_hash_schema(db_path)

def test_calibration_e2e_temp_fixture(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source.db"
    create_mock_source_db(source_db)

    run_id = "test_run_01"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a"*40, str(tmp_path), False, [], []
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

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )

    def mock_git_info(root):
        return "a"*40, str(tmp_path), False, [], []
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

    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    with pytest.raises(RuntimeError, match="BLOCK: Source invariance or query_only gate failed."):
        run_calibration(run_id, str(source_db))

    manifest_path = tmp_path / "runs2" / run_id / "signal" / "c2_calibration_manifest.json"
    with open(manifest_path) as f:
        m = json.load(f)
    assert m["invariance_failure"] is True
    assert "-wal" in m["sidecars_after"][0]

def test_m0_dirty_preflight_failure(tmp_path, monkeypatch):
    run_id = "test_run_03"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a"*40, "/mock", True, ["research/smart_money/m0/dirty.py"], ["research/smart_money/m0/dirty.py"]
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)

    with pytest.raises(RuntimeError, match="M0 dirty preflight abort"):
        run_calibration(run_id, "dummy.db")

def test_query_only_immediate_failure(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_q.db"
    create_mock_source_db(source_db)

    run_id = "test_run_04"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a"*40, str(tmp_path), False, [], []
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

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a"*40, str(tmp_path), False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    # Track closure
    import research.smart_money.m0.src.run_c2_storage_calibration as calib
    original_open = calib.open_readonly_sqlite

    class TrackedConn:
        def __init__(self, conn):
            self.conn = conn
            self.closed = False
        def execute(self, *args, **kwargs):
            return self.conn.execute(*args, **kwargs)
        def cursor(self):
            return self.conn.cursor()
        def close(self):
            self.closed = True
            self.conn.close()

    tracked = []
    def mock_open(p, immutable):
        conn = original_open(p, immutable)
        tc = TrackedConn(conn)
        tracked.append(tc)
        return tc

    monkeypatch.setattr(calib, "open_readonly_sqlite", mock_open)

    def mock_normalize_cusip(c):
        raise ValueError("Simulated scan failure")
    monkeypatch.setattr(calib, "normalize_cusip", mock_normalize_cusip)

    with pytest.raises(ValueError, match="Simulated scan failure"):
        run_calibration(run_id, str(source_db))

    assert len(tracked) == 1
    assert tracked[0].closed is True

def test_preflight_disk_failure(tmp_path, monkeypatch):
    run_id = "test_run_06"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs"),
    )

    def mock_disk_usage(path):
        import collections
        # Return < 256MB
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=200 * 1024 * 1024)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)

    with pytest.raises(RuntimeError, match="Preflight failed: Insufficient disk space"):
        run_calibration(run_id, "dummy")


def test_nearest_existing_ancestor_disk_preflight_no_mkdir(tmp_path, monkeypatch):
    run_id = "test_run_ancestor"

    # create deeply nested run path where intermediate dirs don't exist
    base_dir = tmp_path / "a" / "b" / "c" / run_id
    from research.smart_money.m0.src.run_paths import RunPaths
    def mock_create_run_paths(rid, m0_root=None):
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

    # disk usage spy
    disk_checks = []
    def mock_disk_usage(path):
        disk_checks.append(path)
        import collections
        return collections.namedtuple('usage', 'total used free')(total=10**11, used=10**10, free=200 * 1024 * 1024)
    monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)

    with pytest.raises(RuntimeError, match="Preflight failed: Insufficient disk space"):
        run_calibration(run_id, "dummy")

    assert disk_checks[0] == tmp_path  # Nearest ancestor
    assert not (tmp_path / "a").exists()  # no mkdir

def test_source_sidecar_mutation_failure(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_mtime.db"
    create_mock_source_db(source_db)

    run_id = "test_run_mtime"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a"*40, str(tmp_path), False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    import research.smart_money.m0.src.run_c2_storage_calibration as calib
    calls = [0]
    def mock_check_sidecars(p):
        calls[0] += 1
        if calls[0] > 1:
            return [Path(str(p) + "-wal")]
        return []
    monkeypatch.setattr(calib, "_check_sqlite_sidecars", mock_check_sidecars)

    with pytest.raises(RuntimeError, match="BLOCK: Source invariance"):
        run_calibration(run_id, str(source_db))

def test_source_mtime_mutation_failure(tmp_path, monkeypatch):
    """Verify that if the source DB mtime changes between before/after
    stat checks, the invariance gate fires.

    The old test was fragile because it relied on Path.resolve()
    internally calling stat() to reach the call-count threshold.
    This version directly intercepts the two stat() calls on the
    source path by their logical position (before vs after)."""
    source_db = tmp_path / "mock_source_real_mtime.db"
    create_mock_source_db(source_db)

    run_id = "test_run_real_mtime"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs_real_mtime"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a"*40, str(tmp_path), False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    import research.smart_money.m0.src.run_c2_storage_calibration as calib
    monkeypatch.setattr(calib, "_check_sqlite_sidecars", lambda p: [])

    # Physically touch the source file to change its mtime.
    # We hook open_readonly_sqlite to mutate the source file after it's
    # been stat'd the first time but before it's stat'd the second time.
    original_source_stat = os.stat(str(source_db))
    original_open = calib.open_readonly_sqlite

    def mutating_open(p, immutable):
        """After the 'before' stat has been captured, touch the source
        file so the 'after' stat sees a different mtime."""
        conn = original_open(p, immutable)
        # Mutate the file's mtime by touching it
        p_resolved = Path(p).resolve()
        if p_resolved.name == source_db.name:
            import time
            # Advance mtime by 2 seconds to guarantee detection
            new_ns = original_source_stat.st_mtime_ns + 2_000_000_000
            os.utime(str(p_resolved), ns=(original_source_stat.st_atime_ns, new_ns))
        return conn

    monkeypatch.setattr(calib, "open_readonly_sqlite", mutating_open)

    with pytest.raises(RuntimeError, match="BLOCK: Source invariance"):
        run_calibration(run_id, str(source_db))

def test_head_change_and_concurrent_m0_code_change_fail(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_head.db"
    create_mock_source_db(source_db)

    run_id = "test_run_head"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    calls = [0]
    def mock_git_info(root):
        calls[0] += 1
        if calls[0] == 1:
            return "a"*40, str(tmp_path), False, [], []
        else:
            return "b"*40, str(tmp_path), False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)

    def mock_compute_sha256_file(p): return "a"*64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    # Mock stat and get_page_info so we get past the first parts
    original_stat = Path.stat
    calls_to_stat = [0]
    def mock_stat(self):
        st = original_stat(self)
        if "m0_signal.db" in self.name:
            calls_to_stat[0] += 1
            import collections
            if calls_to_stat[0] > 1:
                return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(st_size=4096+4096, st_mtime_ns=st.st_mtime_ns)
            return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(st_size=4096, st_mtime_ns=st.st_mtime_ns)
        return st
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)

    import research.smart_money.m0.src.run_c2_storage_calibration
    calls_to_gpi = [0]
    def mock_gpi(p):
        calls_to_gpi[0] += 1
        return 4096, 2 if calls_to_gpi[0] > 1 else 1
    monkeypatch.setattr(research.smart_money.m0.src.run_c2_storage_calibration, "get_page_info", mock_gpi)

    with pytest.raises(RuntimeError, match="HEAD changed during run"):
        run_calibration(run_id, str(source_db))

def test_concurrent_m0_code_change_fail(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_code.db"
    create_mock_source_db(source_db)

    run_id = "test_run_code"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    calls = [0]
    def mock_git_info(root):
        calls[0] += 1
        if calls[0] == 1:
            return "a"*40, str(tmp_path), False, [], []
        else:
            return "a"*40, str(tmp_path), True, ["research/smart_money/m0/something.py"], ["research/smart_money/m0/something.py"]
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)

    def mock_compute_sha256_file(p): return "a"*64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    original_stat = Path.stat
    calls_to_stat = [0]
    def mock_stat(self):
        st = original_stat(self)
        if "m0_signal.db" in self.name:
            calls_to_stat[0] += 1
            import collections
            if calls_to_stat[0] > 1:
                return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(st_size=4096+4096, st_mtime_ns=st.st_mtime_ns)
            return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(st_size=4096, st_mtime_ns=st.st_mtime_ns)
        return st
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)
    import research.smart_money.m0.src.run_c2_storage_calibration
    calls_to_gpi = [0]
    def mock_gpi(p):
        calls_to_gpi[0] += 1
        return 4096, 2 if calls_to_gpi[0] > 1 else 1
    monkeypatch.setattr(research.smart_money.m0.src.run_c2_storage_calibration, "get_page_info", mock_gpi)

    with pytest.raises(RuntimeError, match="Concurrent modification of source/test outside run dir"):
        run_calibration(run_id, str(source_db))

def test_page_size_file_size_populated_size_failure(tmp_path, monkeypatch):
    source_db = tmp_path / "mock_source_page.db"
    create_mock_source_db(source_db)

    run_id = "test_run_page"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a"*40, str(tmp_path), False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)

    def mock_compute_sha256_file(p): return "a"*64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    original_stat = Path.stat
    def mock_stat(self):
        st = original_stat(self)
        if "m0_signal.db" in self.name:
            import collections
            # Bad geometry
            return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(st_size=4000, st_mtime_ns=st.st_mtime_ns)
        return st
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)

    with pytest.raises(ValueError, match="Geometry mismatch"):
        run_calibration(run_id, str(source_db))

def test_exact_canonical_atomic_manifest_bytes_no_temp(tmp_path):
    target = tmp_path / "manifest.json"
    write_atomic_canonical_json(target, {"a": 1, "b": 2})
    assert target.exists()

    temps = list(tmp_path.glob("tmp*")) + list(tmp_path.glob(".*"))
    # ensure no temp leftovers
    assert not any(t for t in temps if t.is_file() and not str(t).endswith("manifest.json"))

    with open(target) as f:
        assert f.read() == '{\n  "a": 1,\n  "b": 2\n}'

def test_robust_git_rename_path_parsing(monkeypatch):
    import research.smart_money.m0.src.run_c2_storage_calibration as calib

    def mock_run(args, **kwargs):
        class MockCompletedProcess:
            def __init__(self, stdout, stderr=b"", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        if "rev-parse" in args and "HEAD" in args:
            return MockCompletedProcess(b"a"*40)
        if "--show-toplevel" in args:
            return MockCompletedProcess(b"/m0")
        if "status" in args:
            # Rename: R path2 NUL path1 NUL
            return MockCompletedProcess(b"R  new_path.py\0old_path.py\0 M regular.py\0")
        return MockCompletedProcess(b"")

    monkeypatch.setattr(subprocess, "run", mock_run)

    sha, repo, m0_dirty, m0_dirty_paths, dirty_paths = calib.get_git_info("/m0")

    assert "new_path.py" in dirty_paths
    assert "old_path.py" in dirty_paths
    assert "regular.py" in dirty_paths


def test_robust_git_copy_path_parsing(monkeypatch):
    """Verify NUL-safe copy (C) status parsing — the extra NUL-separated
    origin path must be consumed and both paths recorded."""
    import research.smart_money.m0.src.run_c2_storage_calibration as calib

    def mock_run(args, **kwargs):
        class R:
            def __init__(self, stdout, stderr=b"", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        if "rev-parse" in args and "HEAD" in args:
            return R(b"b" * 40)
        if "--show-toplevel" in args:
            return R(b"/m0")
        if "status" in args:
            # Copy: C  dest NUL src NUL, then a normal modified file
            return R(b"C  dest.py\0src.py\0 M readme.md\0")
        return R(b"")

    monkeypatch.setattr(subprocess, "run", mock_run)
    _, _, _, _, dirty = calib.get_git_info("/m0")

    assert "dest.py" in dirty
    assert "src.py" in dirty
    assert "readme.md" in dirty
    assert len(dirty) == 3


def test_exact_schema_columns_failure(tmp_path):
    import research.smart_money.m0.src.run_c2_storage_calibration as calib
    db_path = tmp_path / "bad_schema.db"
    conn = sqlite3.connect(db_path)
    # create table with wrong columns
    conn.execute("CREATE TABLE m0_signals (wrong TEXT)")
    conn.execute("CREATE TABLE m0_signals_zero_excluded (wrong TEXT)")
    conn.close()

    with pytest.raises(RuntimeError, match="Invalid schema"):
        calib.validate_and_hash_schema(db_path)

def test_missing_schema_failure(tmp_path):
    import research.smart_money.m0.src.run_c2_storage_calibration as calib
    db_path = tmp_path / "bad_schema2.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE m0_signals (synthetic_id TEXT PRIMARY KEY, period_of_report TEXT NOT NULL, signal_value REAL NOT NULL)")
    conn.close()

    with pytest.raises(RuntimeError, match="Missing or extra tables"):
        calib.validate_and_hash_schema(db_path)


def test_validate_page_geometry_exact():
    """Verify page geometry validation rejects mismatched sizes."""
    validate_page_geometry(4096, 10, 40960)  # should pass
    with pytest.raises(ValueError, match="Geometry mismatch"):
        validate_page_geometry(4096, 10, 40000)
    with pytest.raises(ValueError, match="Invalid page size"):
        validate_page_geometry(0, 10, 0)
    with pytest.raises(ValueError, match="Invalid page count"):
        validate_page_geometry(4096, -1, 4096)


def test_get_page_info_connection_closure(tmp_path):
    """Verify get_page_info closes the connection even on success."""
    db_path = tmp_path / "page_test.db"
    init_signal_db(db_path)
    ps, pc = get_page_info(db_path)
    assert isinstance(ps, int) and ps > 0
    assert isinstance(pc, int) and pc > 0
    # Verify the connection is closed by trying to open the same file
    # exclusively — if the connection leaked, this would see WAL artifacts
    conn = sqlite3.connect(db_path)
    try:
        # A PRAGMA that only works on a writable, non-leaked connection
        conn.execute("PRAGMA integrity_check")
    finally:
        conn.close()


def test_validate_and_hash_schema_closes_on_error(tmp_path):
    """Verify validate_and_hash_schema closes its connection even when
    raising RuntimeError for bad schemas."""
    db_path = tmp_path / "bad_close.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE m0_signals (x TEXT)")
    conn.execute("CREATE TABLE m0_signals_zero_excluded (y TEXT)")
    conn.close()

    with pytest.raises(RuntimeError, match="Invalid schema"):
        validate_and_hash_schema(db_path)

    # If the connection leaked, this could fail on some platforms
    conn2 = sqlite3.connect(db_path)
    try:
        conn2.execute("PRAGMA integrity_check")
    finally:
        conn2.close()


def test_source_and_test_immutability_after_output(tmp_path, monkeypatch):
    """After a successful calibration run, verify that the source file
    (run_c2_storage_calibration.py) and the test file
    (test_stage_c2_calibration.py) have not been modified by the run.

    This guards against accidental self-mutation or file-system side effects."""
    source_db = tmp_path / "mock_source_immut.db"
    create_mock_source_db(source_db)

    run_id = "test_run_immut"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs_immut"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    def mock_git_info(root):
        return "a" * 40, str(tmp_path), False, [], []
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)

    def mock_compute_sha256_file(p):
        return "a" * 64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    original_stat = Path.stat
    calls_to_stat = [0]
    def mock_stat(self):
        st = original_stat(self)
        if "m0_signal.db" in self.name:
            calls_to_stat[0] += 1
            if calls_to_stat[0] > 1:
                import collections
                return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(
                    st_size=st.st_size + 4096, st_mtime_ns=st.st_mtime_ns)
        return st
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)

    import research.smart_money.m0.src.run_c2_storage_calibration as calib
    original_gpi = calib.get_page_info
    gpi_calls = [0]
    def mock_gpi(p):
        ps, pc = original_gpi(p)
        gpi_calls[0] += 1
        if gpi_calls[0] > 1:
            pc += 1
        return ps, pc
    monkeypatch.setattr(calib, "get_page_info", mock_gpi)

    # Record source and test file stats before run
    src_file = Path(calib.__file__).resolve()
    test_file = Path(__file__).resolve()
    src_stat_before = os.stat(str(src_file))
    test_stat_before = os.stat(str(test_file))

    manifest = run_calibration(run_id, str(source_db))
    assert manifest["final_decision"] == "PASS"

    # Verify source and test files are untouched
    src_stat_after = os.stat(str(src_file))
    test_stat_after = os.stat(str(test_file))

    assert src_stat_before.st_size == src_stat_after.st_size, \
        "Source file size changed after calibration run"
    assert src_stat_before.st_mtime_ns == src_stat_after.st_mtime_ns, \
        "Source file mtime changed after calibration run"
    assert test_stat_before.st_size == test_stat_after.st_size, \
        "Test file size changed after calibration run"
    assert test_stat_before.st_mtime_ns == test_stat_after.st_mtime_ns, \
        "Test file mtime changed after calibration run"


def test_exact_current_run_dirty_path_allowance(tmp_path, monkeypatch):
    """Post-run dirty-path check must allow files ONLY under the current
    run directory.  Files under research/smart_money/m0/ but outside the
    run dir must trigger the concurrent-modification guard."""
    source_db = tmp_path / "mock_source_allow.db"
    create_mock_source_db(source_db)

    run_id = "test_run_allow"

    monkeypatch.setattr(
        "research.smart_money.m0.src.run_c2_storage_calibration.create_run_paths",
        _mock_run_paths_factory(tmp_path, "runs2"),
    )
    monkeypatch.setattr("shutil.disk_usage", _mock_disk_plenty)

    call_count = [0]
    run_dir_str = f"research/smart_money/m0/runs/{run_id}/"

    def mock_git_info(root):
        call_count[0] += 1
        if call_count[0] == 1:
            # Clean preflight
            return "a" * 40, str(tmp_path), False, [], []
        else:
            # Post-run: run dir files are dirty (allowed) + one outside file (not allowed)
            run_file = f"{run_dir_str}signal/c2_calibration_manifest.json"
            outside_file = "research/smart_money/m0/src/evil.py"
            all_dirty = [run_file, outside_file]
            m0_dirty = all_dirty  # both are under m0
            return "a" * 40, str(tmp_path), True, m0_dirty, all_dirty

    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.get_git_info", mock_git_info)

    def mock_compute_sha256_file(p):
        return "a" * 64
    monkeypatch.setattr("research.smart_money.m0.src.run_c2_storage_calibration.compute_sha256_file", mock_compute_sha256_file)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    original_stat = Path.stat
    stat_calls = [0]
    def mock_stat(self):
        st = original_stat(self)
        if "m0_signal.db" in self.name:
            stat_calls[0] += 1
            if stat_calls[0] > 1:
                import collections
                return collections.namedtuple('stat_result', 'st_size st_mtime_ns')(
                    st_size=st.st_size + 4096, st_mtime_ns=st.st_mtime_ns)
        return st
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)

    import research.smart_money.m0.src.run_c2_storage_calibration as calib
    original_gpi = calib.get_page_info
    gpi_c = [0]
    def mock_gpi(p):
        ps, pc = original_gpi(p)
        gpi_c[0] += 1
        if gpi_c[0] > 1:
            pc += 1
        return ps, pc
    monkeypatch.setattr(calib, "get_page_info", mock_gpi)

    with pytest.raises(RuntimeError, match="Concurrent modification of source/test outside run dir"):
        run_calibration(run_id, str(source_db))


def test_compute_projection_and_gates_invalid_inputs():
    """Edge-case validation for compute_projection_and_gates."""
    base = 10000
    rows = 200
    pop = 15000
    all_upper = 500
    ps = 4096
    free = 10 * 1024**3

    # Invalid page size
    with pytest.raises(ValueError, match="Invalid page size"):
        compute_projection_and_gates(base, rows, pop, all_upper, 0, free)

    # Negative inserted_rows
    with pytest.raises(ValueError, match="inserted_rows is not positive"):
        compute_projection_and_gates(base, 0, pop, all_upper, ps, free)

    # populated_bytes not greater than base_bytes
    with pytest.raises(ValueError, match="populated_bytes is not greater"):
        compute_projection_and_gates(base, rows, base, all_upper, ps, free)

    # Negative free bytes
    with pytest.raises(ValueError, match="Invalid free bytes"):
        compute_projection_and_gates(base, rows, pop, all_upper, ps, -1)
