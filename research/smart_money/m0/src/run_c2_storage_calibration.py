"""Stage C2 Storage Calibration orchestrator."""

import argparse
import hashlib
import math
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

from research.smart_money.m0.src.storage_guard import open_readonly_sqlite, _check_sqlite_sidecars
from research.smart_money.m0.src.run_paths import create_run_paths, get_default_m0_root
from research.smart_money.m0.src.manifest_integrity import compute_sha256_file, canonical_json_dumps, compute_sha256_str

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
    assert len(periods) == 51
    return periods

def normalize_cusip(c):
    if c is None:
        return None
    c = str(c).strip().upper()
    return c if c else None

def get_synthetic_id(cusip):
    # Deterministic exactly-12-char ID
    return hashlib.md5(cusip.encode('utf-8')).hexdigest()[:12].upper()

def compute_projection_and_gates(base_bytes, inserted_rows, populated_bytes, all_period_upper_rows, page_size, free_bytes):
    two_branch_all_period_upper_rows = 2 * all_period_upper_rows
    if inserted_rows > 0:
        bytes_per_row = math.ceil((populated_bytes - base_bytes) / inserted_rows)
    else:
        bytes_per_row = 0
    
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
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=m0_root, stderr=subprocess.STDOUT).decode("utf-8").strip()
        repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=m0_root, stderr=subprocess.STDOUT).decode("utf-8").strip()
        status_out = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, stderr=subprocess.STDOUT).decode("utf-8")
    except subprocess.SubprocessError as e:
        raise RuntimeError(f"Git command failed: {e}")
        
    dirty_paths = []
    for line in status_out.splitlines():
        if len(line) > 3:
            dirty_paths.append(line[3:])
            
    try:
        rel_m0 = Path(m0_root).resolve().relative_to(Path(repo_root).resolve())
    except ValueError:
        rel_m0 = "research/smart_money/m0"
        
    rel_m0_str = str(rel_m0)
    if not rel_m0_str.endswith('/'):
        rel_m0_str += '/'
        
    m0_dirty = any(p.startswith(rel_m0_str) for p in dirty_paths)
    return sha, repo_root, m0_dirty, dirty_paths

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

def get_page_info(db_path):
    conn = sqlite3.connect(db_path)
    ps = conn.execute("PRAGMA page_size").fetchone()[0]
    pc = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.close()
    return ps, pc

def run_calibration(run_id, source_db_path):
    t0 = time.time()
    m0_root = get_default_m0_root()
    
    sha, repo_root, m0_dirty_before, global_dirty_before = get_git_info(m0_root)
    if m0_dirty_before:
        raise RuntimeError(f"M0 dirty preflight abort: working tree must be clean in {m0_root}")
        
    paths = create_run_paths(run_id)
    if paths.base_dir.exists():
        raise FileExistsError(f"Run directory already exists, refusing to overwrite: {paths.base_dir}")
        
    source_p = Path(source_db_path).resolve()
    if not source_p.is_file():
        raise FileNotFoundError(f"Source DB missing: {source_p}")
        
    contract_p = m0_root / "CONTRACT.md"
    if not contract_p.is_file():
        raise FileNotFoundError(f"CONTRACT.md missing at {contract_p}")
    contract_hash = compute_sha256_file(contract_p)
    
    schema_ddl = "CREATE TABLE IF NOT EXISTS m0_signals (primary_stock_id TEXT NOT NULL, period_of_report TEXT NOT NULL, m0_signal REAL NOT NULL, PRIMARY KEY (primary_stock_id, period_of_report));\nCREATE TABLE IF NOT EXISTS m0_signals_zero_excluded (primary_stock_id TEXT NOT NULL, period_of_report TEXT NOT NULL, m0_signal REAL NOT NULL, PRIMARY KEY (primary_stock_id, period_of_report));"
    schema_hash = compute_sha256_str(schema_ddl)
    runner_hash = compute_sha256_file(Path(__file__))
    
    source_size_before = source_p.stat().st_size
    source_mtime_before = source_p.stat().st_mtime_ns
    sidecars_before = sorted([s.name for s in _check_sqlite_sidecars(source_p)])
    
    conn = open_readonly_sqlite(source_p, immutable=True)
    query_only_val = conn.execute("PRAGMA query_only").fetchone()[0]
    
    periods = generate_51_contract_periods()
    period_counts = {}
    top4_sets = {}
    
    def update_top4(count, p, cusips):
        top4_sets[p] = (count, cusips)
        sorted_keys = sorted(top4_sets.keys(), key=lambda k: (-top4_sets[k][0], k))
        if len(sorted_keys) > 4:
            del top4_sets[sorted_keys[-1]]

    cursor = conn.cursor()
    cursor.arraysize = 500
    
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
            c2.execute(query, acc_list)
            while True:
                cbatch = c2.fetchmany(500)
                if not cbatch:
                    break
                for row in cbatch:
                    norm = normalize_cusip(row[0])
                    if norm:
                        period_cusips.add(norm)
            c2.close()
        
        c = len(period_cusips)
        period_counts[p] = c
        update_top4(c, p, period_cusips)
        
    conn.close()
    
    source_size_after = source_p.stat().st_size
    source_mtime_after = source_p.stat().st_mtime_ns
    sidecars_after = sorted([s.name for s in _check_sqlite_sidecars(source_p)])
    
    invariance_pass = (source_size_before == source_size_after) and \
                      (source_mtime_before == source_mtime_after) and \
                      (sidecars_before == []) and (sidecars_after == []) and \
                      (query_only_val == 1)
                      
    paths.ensure_directories()
    
    manifest = {
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
        "schema_hash": schema_hash,
        "schema_version": "1.0",
        "runner_hash": runner_hash,
        "m0_tree_dirty_preflight": m0_dirty_before,
        "m0_dirty_scope": "research/smart_money/m0",
        "global_dirty_paths_preflight": global_dirty_before,
        "periods": periods,
        "per_period_counts": period_counts,
        "selected_pilot_periods": [],
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
    conn_pilot = sqlite3.connect(pilot_db_path)
    conn_pilot.execute("PRAGMA auto_vacuum = 0;")
    conn_pilot.executescript(schema_ddl)
    conn_pilot.commit()
    conn_pilot.close()
    
    base_bytes = pilot_db_path.stat().st_size
    base_ps, base_pc = get_page_info(pilot_db_path)
    
    conn_pilot = sqlite3.connect(pilot_db_path)
    inserted_rows = 0
    selected_sets_info = {}
    id_mapping = {}
    with conn_pilot:
        for p in sorted_top4_keys:
            count, cusips = top4_sets[p]
            rows = []
            c_list = sorted(list(cusips))
            selected_sets_info[p] = {"count": count, "cusips": c_list}
            for c in c_list:
                sid = get_synthetic_id(c)
                if c in id_mapping and id_mapping[c] != sid:
                    raise RuntimeError("Collision in synthetic ID mapping")
                if sid in id_mapping.values() and c not in id_mapping:
                     assigned = [k for k,v in id_mapping.items() if v == sid]
                     if assigned and assigned[0] != c:
                         raise RuntimeError("Collision: different CUSIPs mapped to same synthetic ID")
                id_mapping[c] = sid
                rows.append((sid, p, 1.0))
            conn_pilot.executemany("INSERT INTO m0_signals VALUES (?, ?, ?)", rows)
            conn_pilot.executemany("INSERT INTO m0_signals_zero_excluded VALUES (?, ?, ?)", rows)
            inserted_rows += 2 * len(rows)
            
    conn_pilot.execute("PRAGMA optimize;")
    conn_pilot.execute("VACUUM;")
    conn_pilot.commit()
    conn_pilot.close()
    
    populated_bytes = pilot_db_path.stat().st_size
    pop_ps, pop_pc = get_page_info(pilot_db_path)
    
    assert base_ps == pop_ps, "Page size must remain stable"
    assert populated_bytes == pop_ps * pop_pc, "File size must equal page_size * page_count after VACUUM"
    
    free_bytes = shutil.disk_usage(paths.base_dir).free
    real_disk = os.stat(paths.base_dir)
    disk_device = real_disk.st_dev
    disk_path = str(paths.base_dir.resolve())
    
    all_upper = sum(period_counts.values())
    proj_gates = compute_projection_and_gates(base_bytes, inserted_rows, populated_bytes, all_upper, pop_ps, free_bytes)
    
    _, _, _, global_dirty_after = get_git_info(m0_root)
    
    manifest.update({
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
            "bytes_per_row": "ceil((populated_bytes - base_bytes) / inserted_rows) if inserted_rows > 0 else 0",
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
