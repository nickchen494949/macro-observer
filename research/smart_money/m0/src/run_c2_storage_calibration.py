"""Stage C2 Storage Calibration orchestrator."""

import argparse
import math
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import re
from pathlib import Path

from research.smart_money.m0.src.storage_guard import open_readonly_sqlite, _check_sqlite_sidecars, init_signal_db
from research.smart_money.m0.src.run_paths import create_run_paths, get_default_m0_root
from research.smart_money.m0.src.manifest_integrity import compute_sha256_file, canonical_json_dumps, compute_sha256_str

_HEX_40_OR_64_PATTERN = re.compile(r"^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")

def generate_51_contract_periods():
    periods = []
    for year in range(2013, 2027):
        for md in ["03-31", "06-30", "09-30", "12-31"]:
            p = f"{year}-{md}"
            if "2013-03" <= p < "2013-09":
                continue
            if p > "2026-03-31":
                break
            periods.append(p)
    if len(periods) != 51:
        raise RuntimeError("Missing contract periods")
    return periods

def normalize_cusip(c):
    if c is None:
        return None
    c = str(c).strip().upper()
    return c if c else None

def build_injective_mapping(cusip_sets):
    all_cusips = set()
    for s in cusip_sets:
        all_cusips.update(s)

    sorted_cusips = sorted(all_cusips)
    mapping = {}
    for i, c in enumerate(sorted_cusips):
        sid = f"P{i:011d}"
        if len(sid) != 12:
            raise RuntimeError(f"Synthetic ID capacity exceeded or invalid length: {sid}")
        mapping[c] = sid
    return mapping

def compute_projection_and_gates(base_bytes, inserted_rows, populated_bytes, all_period_upper_rows, page_size, free_bytes):
    if not isinstance(page_size, int) or page_size <= 0:
        raise ValueError("Invalid page size")
    if not isinstance(inserted_rows, int) or inserted_rows <= 0:
        raise ValueError("inserted_rows is not positive")
    if not isinstance(populated_bytes, int) or populated_bytes <= base_bytes:
        raise ValueError("populated_bytes is not greater than base_bytes")
    if not isinstance(free_bytes, int) or free_bytes < 0:
        raise ValueError("Invalid free bytes")
    if not isinstance(all_period_upper_rows, int) or all_period_upper_rows < 0:
        raise ValueError("Invalid all_period_upper_rows")

    two_branch_all_period_upper_rows = 2 * all_period_upper_rows

    bytes_per_row = math.ceil((populated_bytes - base_bytes) / inserted_rows)

    empirical_signal_db_bytes = math.ceil(1.20 * (base_bytes + bytes_per_row * two_branch_all_period_upper_rows) / page_size) * page_size
    explicit_non_db_reserve = 512 * 1024 * 1024
    provisional_floor = int(4.5 * 1024**3)

    projected_total_persistent_bytes = max(empirical_signal_db_bytes + explicit_non_db_reserve, provisional_floor)

    transient_reserve = int(1.5 * 1024**3)

    gate_persistent = free_bytes >= 2 * projected_total_persistent_bytes
    gate_transient = free_bytes >= (projected_total_persistent_bytes + transient_reserve)
    final_pass = gate_persistent and gate_transient

    return {
        "bytes_per_row": bytes_per_row,
        "two_branch_all_period_upper_rows": two_branch_all_period_upper_rows,
        "empirical_signal_db_bytes": empirical_signal_db_bytes,
        "explicit_non_db_reserve": explicit_non_db_reserve,
        "provisional_floor": provisional_floor,
        "projected_total_persistent_bytes": projected_total_persistent_bytes,
        "transient_reserve": transient_reserve,
        "gate_persistent_pass": gate_persistent,
        "gate_transient_pass": gate_transient,
        "final_pass": final_pass
    }

def get_git_info(m0_root):
    m0_path = Path(m0_root).resolve()

    def _run_git(cmd, cwd):
        res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            stdout_str = res.stdout.decode("utf-8", errors="replace").strip()
            stderr_str = res.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Git command failed. stdout: {stdout_str}, stderr: {stderr_str}")
        return res.stdout

    try:
        sha = _run_git(["git", "rev-parse", "HEAD"], cwd=str(m0_path)).decode("utf-8").strip()
        if not _HEX_40_OR_64_PATTERN.match(sha):
            raise RuntimeError(f"Invalid SHA format: {sha}")

        repo_root_str = _run_git(["git", "rev-parse", "--show-toplevel"], cwd=str(m0_path)).decode("utf-8").strip()
        repo_path = Path(repo_root_str).resolve()

        if not m0_path.is_relative_to(repo_path):
            raise RuntimeError(f"m0_root {m0_path} is not inside repo root {repo_path}")

        status_out = _run_git(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=str(repo_path))
    except subprocess.SubprocessError as e:
        raise RuntimeError(f"Git command failed: {e}")

    dirty_paths = []
    if status_out:
        parts = status_out.split(b'\0')
        i = 0
        while i < len(parts) - 1:
            if not parts[i]:
                i += 1
                continue
            status = parts[i][:2].decode('utf-8', errors='replace')
            path = parts[i][3:].decode('utf-8', errors='replace')
            dirty_paths.append(path)
            if status[0] in ('R', 'C') or (len(status) > 1 and status[1] in ('R', 'C')):
                orig_path = parts[i+1].decode('utf-8', errors='replace')
                dirty_paths.append(orig_path)
                i += 2
            else:
                i += 1

    try:
        rel_m0 = m0_path.relative_to(repo_path)
    except ValueError:
        raise RuntimeError(f"m0_root {m0_path} is not inside repo root {repo_path}")

    rel_m0_str = str(rel_m0)
    if not rel_m0_str.endswith('/'):
        rel_m0_str += '/'

    m0_dirty_paths = [p for p in dirty_paths if p.startswith(rel_m0_str)]
    return sha, str(repo_path), bool(m0_dirty_paths), m0_dirty_paths, dirty_paths

def write_atomic_canonical_json(filepath, data):
    dir_path = filepath.parent
    fd, temp_path = tempfile.mkstemp(dir=dir_path, text=True)
    temp_path_obj = Path(temp_path)
    try:
        payload = canonical_json_dumps(data).encode("utf-8")
        with os.fdopen(fd, 'wb') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, filepath)
    except Exception:
        if temp_path_obj.exists():
            temp_path_obj.unlink()
        raise

def validate_page_geometry(page_size, page_count, expected_size):
    if not isinstance(page_size, int) or page_size <= 0:
        raise ValueError("Invalid page size")
    if not isinstance(page_count, int) or page_count < 0:
        raise ValueError("Invalid page count")
    if not isinstance(expected_size, int) or expected_size < 0:
        raise ValueError("Invalid expected size")
    if page_size * page_count != expected_size:
        raise ValueError("Geometry mismatch")

def get_page_info(db_path):
    conn = sqlite3.connect(db_path)
    try:
        ps = conn.execute("PRAGMA page_size").fetchone()[0]
        pc = conn.execute("PRAGMA page_count").fetchone()[0]
    finally:
        conn.close()
    return ps, pc

def validate_and_hash_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()

        expected_tables = {"m0_signals", "m0_signals_zero_excluded"}
        actual_tables = set(name for name, _ in rows)
        if actual_tables != expected_tables:
            raise RuntimeError(f"Missing or extra tables in schema: {actual_tables}")

        schema_str = ""
        for name, sql in rows:
            tinfo = conn.execute(f"PRAGMA table_info({name})").fetchall()
            expected_cols = [
                (0, 'primary_stock_id', 'TEXT', 1, None, 1),
                (1, 'period_of_report', 'TEXT', 1, None, 2),
                (2, 'm0_signal', 'REAL', 1, None, 0)
            ]
            if tinfo != expected_cols:
                raise RuntimeError(f"Invalid schema for {name}: {tinfo}")
            norm_sql = " ".join(sql.replace("\n", " ").split())
            schema_str += f"{name}:{norm_sql};"
    finally:
        conn.close()
    return compute_sha256_str(schema_str)

def run_calibration(run_id, source_db_path):
    t0 = time.time()

    paths = create_run_paths(run_id)
    if paths.base_dir.exists():
        raise FileExistsError(f"Run directory already exists, refusing to overwrite: {paths.base_dir}")

    m0_root = get_default_m0_root()

    nearest = paths.base_dir.parent
    while nearest and not nearest.exists():
        nearest = nearest.parent
    if not nearest:
        nearest = Path("/")
    preflight_free_bytes = shutil.disk_usage(nearest).free
    if preflight_free_bytes < 256 * 1024 * 1024:
        raise RuntimeError("Preflight failed: Insufficient disk space (< 256MB)")

    sha, repo_root, m0_dirty_before, m0_dirty_paths_before, global_dirty_before = get_git_info(m0_root)
    if m0_dirty_before:
        raise RuntimeError(f"M0 dirty preflight abort: working tree must be clean in {m0_root}. Dirty: {m0_dirty_paths_before}")

    source_p = Path(source_db_path).resolve()
    if not source_p.is_file():
        raise FileNotFoundError(f"Source DB missing: {source_p}")

    contract_p = m0_root / "CONTRACT.md"
    if not contract_p.is_file():
        raise FileNotFoundError(f"CONTRACT.md missing at {contract_p}")
    contract_hash = compute_sha256_file(contract_p)

    import research.smart_money.m0.src.storage_guard
    storage_guard_hash = compute_sha256_file(Path(research.smart_money.m0.src.storage_guard.__file__))
    runner_hash = compute_sha256_file(Path(__file__))

    source_stat_before = source_p.stat()
    source_size_before = source_stat_before.st_size
    source_mtime_before = source_stat_before.st_mtime_ns
    sidecars_before = sorted([s.name for s in _check_sqlite_sidecars(source_p)])

    periods = generate_51_contract_periods()
    period_counts = {}
    top4_sets = {}

    def update_top4(count, p, cusips):
        top4_sets[p] = (count, cusips)
        sorted_keys = sorted(top4_sets.keys(), key=lambda k: (-top4_sets[k][0], k))
        if len(sorted_keys) > 4:
            del top4_sets[sorted_keys[-1]]

    conn = None
    query_only_val = -1
    scan_exception = None

    try:
        conn = open_readonly_sqlite(source_p, immutable=True)
        query_only_val = conn.execute("PRAGMA query_only").fetchone()[0]
        if query_only_val != 1:
            raise RuntimeError(f"query_only PRAGMA is {query_only_val}, expected 1")

        cursor = conn.cursor()
        cursor.arraysize = 500
        try:
            for p in periods:
                cursor.execute("SELECT accession_number FROM filing_events WHERE period_of_report = ?", (p,))
                period_cusips = set()
                while True:
                    acc_batch = cursor.fetchmany(500)
                    if not acc_batch:
                        break
                    acc_list = [row[0] for row in acc_batch]
                    qs = ",".join("?" * len(acc_list))
                    query = f"SELECT cusip FROM filing_line_items WHERE accession_number IN ({qs}) AND asset_class = 'cash_equity'"
                    c2 = conn.cursor()
                    try:
                        c2.execute(query, acc_list)
                        while True:
                            cbatch = c2.fetchmany(500)
                            if not cbatch:
                                break
                            for row in cbatch:
                                norm = normalize_cusip(row[0])
                                if norm:
                                    period_cusips.add(norm)
                    finally:
                        c2.close()

                c = len(period_cusips)
                if c < 0:
                    raise RuntimeError("Impossible count")
                period_counts[p] = c
                update_top4(c, p, period_cusips)
        finally:
            cursor.close()

    except Exception as e:
        scan_exception = e
    finally:
        if conn:
            conn.close()

    source_stat_after = source_p.stat()
    source_size_after = source_stat_after.st_size
    source_mtime_after = source_stat_after.st_mtime_ns
    sidecars_after = sorted([s.name for s in _check_sqlite_sidecars(source_p)])

    invariance_pass = (source_size_before == source_size_after) and \
                      (source_mtime_before == source_mtime_after) and \
                      (sidecars_before == []) and (sidecars_after == []) and \
                      (query_only_val == 1)

    if scan_exception:
        if not invariance_pass:
            raise RuntimeError(f"Scan exception AND Invariance failure: {scan_exception}") from scan_exception
        raise scan_exception

    paths.ensure_directories()

    manifest = {
        "source_db_canonical_path": str(source_p),
        "source_db_exact_size": source_size_before,
        "source_db_exact_size_after": source_size_after,
        "source_db_mtime": source_mtime_before,
        "source_db_mtime_after": source_mtime_after,
        "sidecars_before": sidecars_before,
        "sidecars_after": sidecars_after,
        "query_only_pragma": query_only_val,
        "source_git_sha": sha,
        "repo_root": repo_root,
        "contract_hash": contract_hash,
        "contract_version": "0.8.3",
        "storage_guard_hash": storage_guard_hash,
        "runner_hash": runner_hash,
        "m0_tree_dirty_preflight": m0_dirty_before,
        "m0_dirty_paths_preflight": m0_dirty_paths_before,
        "m0_dirty_scope": "research/smart_money/m0",
        "global_dirty_paths_preflight": global_dirty_before,
        "periods": periods,
        "raw_upper_bound_per_period_counts": period_counts,
        "preflight_free_bytes": preflight_free_bytes,
        "formulas": {},
        "reserves": {},
        "final_decision": "BLOCK"
    }

    if not invariance_pass:
        manifest["invariance_failure"] = True
        write_atomic_canonical_json(paths.signal_dir / "c2_calibration_manifest.json", manifest)
        raise RuntimeError("BLOCK: Source invariance or query_only gate failed.")

    sorted_top4_keys = sorted(top4_sets.keys(), key=lambda k: (-top4_sets[k][0], k))

    pilot_db_path = paths.signal_dir / "m0_signal.db"
    init_signal_db(pilot_db_path)

    base_bytes = pilot_db_path.stat().st_size
    base_ps, base_pc = get_page_info(pilot_db_path)
    validate_page_geometry(base_ps, base_pc, base_bytes)

    schema_hash = validate_and_hash_schema(pilot_db_path)
    manifest["schema_definition_sha256"] = schema_hash
    manifest["schema_version"] = "1.0"

    cusip_list_of_sets = [top4_sets[p][1] for p in sorted_top4_keys]
    id_mapping = build_injective_mapping(cusip_list_of_sets)

    conn_pilot = None
    inserted_rows = 0
    selected_sets_info = {}
    try:
        conn_pilot = sqlite3.connect(pilot_db_path)
        with conn_pilot:
            for p in sorted_top4_keys:
                count, cusips = top4_sets[p]
                rows = []

                c_list = sorted(list(cusips))
                set_hash = compute_sha256_str(canonical_json_dumps(c_list))
                selected_sets_info[p] = {"count": count, "hash": set_hash}

                for c in c_list:
                    sid = id_mapping[c]
                    rows.append((sid, p, 1.0))
                conn_pilot.executemany("INSERT INTO m0_signals VALUES (?, ?, ?)", rows)
                conn_pilot.executemany("INSERT INTO m0_signals_zero_excluded VALUES (?, ?, ?)", rows)
                inserted_rows += 2 * len(rows)

        conn_pilot.execute("PRAGMA optimize;")
        conn_pilot.execute("VACUUM;")
        conn_pilot.commit()
    finally:
        if conn_pilot:
            conn_pilot.close()

    populated_bytes = pilot_db_path.stat().st_size
    pop_ps, pop_pc = get_page_info(pilot_db_path)

    if base_ps != pop_ps:
        raise RuntimeError("Page size is not stable")
    validate_page_geometry(pop_ps, pop_pc, populated_bytes)

    real_disk = os.stat(paths.base_dir)
    disk_device = real_disk.st_dev
    disk_path = str(paths.base_dir.resolve())
    free_bytes = shutil.disk_usage(disk_path).free

    all_upper = sum(period_counts.values())
    proj_gates = compute_projection_and_gates(base_bytes, inserted_rows, populated_bytes, all_upper, pop_ps, free_bytes)

    sha_after, _, m0_dirty_after, m0_dirty_paths_after, global_dirty_after = get_git_info(m0_root)
    if sha_after != sha:
        raise RuntimeError("HEAD changed during run")

    try:
        run_dir_rel_str = str(paths.base_dir.relative_to(Path(repo_root)))
    except ValueError:
        raise RuntimeError("Run dir not in repo")
    if not run_dir_rel_str.endswith('/'):
        run_dir_rel_str += '/'

    # Check that any M0 dirty files are solely under the current run dir
    # Relies on the fact that m0_root starts with repo_root.
    for p in global_dirty_after:
        if p.startswith("research/smart_money/m0/"):
            if not p.startswith(run_dir_rel_str):
                raise RuntimeError(f"Concurrent modification of source/test outside run dir: {p}")

    manifest.update({
        "m0_tree_dirty_after_output": m0_dirty_after,
        "m0_dirty_paths_after": m0_dirty_paths_after,
        "global_dirty_paths_after": global_dirty_after,
        "selected_pilot_periods": sorted_top4_keys,
        "selected_sets": selected_sets_info,
        "page_size": pop_ps,
        "page_counts": {"empty": base_pc, "populated": pop_pc},
        "inserted_rows": inserted_rows,
        "base_bytes": base_bytes,
        "populated_bytes": populated_bytes,
        "bytes_per_row": proj_gates["bytes_per_row"],
        "two_branch_all_period_upper_rows": proj_gates["two_branch_all_period_upper_rows"],
        "constants": {
            "explicit_non_db_reserve": proj_gates["explicit_non_db_reserve"],
            "provisional_floor": proj_gates["provisional_floor"],
            "transient_reserve": proj_gates["transient_reserve"],
            "persistent_margin": 1.2
        },
        "formulas": {
            "bytes_per_row": "ceil((populated_bytes - base_bytes) / inserted_rows)",
            "empirical_signal_db_bytes": "ceil(1.20 * (base_bytes + bytes_per_row * two_branch_all_period_upper_rows) / page_size) * page_size",
            "projected_total_persistent_bytes": "max(empirical_signal_db_bytes + explicit_non_db_reserve, provisional_floor)",
            "gate_persistent": "free_bytes >= 2 * projected_total_persistent_bytes",
            "gate_transient": "free_bytes >= projected_total_persistent_bytes + transient_reserve"
        },
        "explanation": "4.5GiB remains a fail-safe floor because OpenFIGI/vendor/SEC evidence raw caches are not empirically calibrated yet. The transient gate is mathematically redundant under the 4.5GiB floor and 2x persistent gate, but computed/recorded independently.",
        "reserves": {
            "empirical_signal_db_bytes": proj_gates["empirical_signal_db_bytes"],
            "projected_total_persistent_bytes": proj_gates["projected_total_persistent_bytes"]
        },
        "free_space_device": disk_device,
        "free_space_path": disk_path,
        "free_space_bytes": free_bytes,
        "gate_persistent_pass": proj_gates["gate_persistent_pass"],
        "gate_transient_pass": proj_gates["gate_transient_pass"],
        "final_decision": "PASS" if proj_gates["final_pass"] else "BLOCK",
        "runtime_sec": time.time() - t0
    })

    write_atomic_canonical_json(paths.signal_dir / "c2_calibration_manifest.json", manifest)

    if not proj_gates["final_pass"]:
        raise RuntimeError("BLOCK: Storage Calibration Gates Failed")

    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-db", default="research/smart_money/phase0/data/13f_full_4409f14.db")
    args = parser.parse_args()

    run_calibration(args.run_id, args.source_db)

if __name__ == "__main__":
    main()
