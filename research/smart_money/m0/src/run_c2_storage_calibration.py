"""Stage C2 Storage Calibration orchestrator."""

import argparse
import json
import math
import os
import shutil
import sqlite3
import tempfile
import time
import subprocess
from pathlib import Path

from research.smart_money.m0.src.storage_guard import open_readonly_sqlite, _check_sqlite_sidecars
from research.smart_money.m0.src.run_paths import create_run_paths
from research.smart_money.m0.src.manifest_integrity import compute_sha256_file, check_git_clean_tree

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

def check_sidecars(db_path):
    return sorted([s.name for s in _check_sqlite_sidecars(Path(db_path))])

def get_page_info(db_path):
    conn = sqlite3.connect(db_path)
    ps = conn.execute("PRAGMA page_size").fetchone()[0]
    pc = conn.execute("PRAGMA page_count").fetchone()[0]
    conn.close()
    return ps, pc

def get_git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception:
        return "unknown"

def run_calibration(run_id, source_db_path):
    t0 = time.time()
    paths = create_run_paths(run_id)
    if paths.base_dir.exists():
        raise FileExistsError(f"Run directory already exists, refusing to overwrite: {paths.base_dir}")
        
    paths.ensure_directories()
    
    free_bytes = shutil.disk_usage(paths.base_dir).free
    if free_bytes < 50 * 1024 * 1024:
        raise RuntimeError("Preflight failed: Insufficient disk space (< 50MB)")
        
    source_p = Path(source_db_path)
    sidecars_before = check_sidecars(source_p)
    source_size = os.path.getsize(source_p)
    source_mtime = os.stat(source_p).st_mtime_ns
    
    conn = open_readonly_sqlite(source_p, immutable=True)
    
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
            query = f"SELECT cusip FROM filing_line_items WHERE accession_number IN ({qs}) AND asset_class = 'cash_equity' AND cusip IS NOT NULL AND cusip != ''"
            c2 = conn.cursor()
            c2.execute(query, acc_list)
            while True:
                cbatch = c2.fetchmany(500)
                if not cbatch:
                    break
                for row in cbatch:
                    period_cusips.add(row[0])
            c2.close()
        
        c = len(period_cusips)
        period_counts[p] = c
        update_top4(c, p, period_cusips)
        
    conn.close()
    
    sidecars_after = check_sidecars(source_p)
    
    sorted_top4_keys = sorted(top4_sets.keys(), key=lambda k: (-top4_sets[k][0], k))
    
    pilot_db_path = paths.signal_dir / "m0_signal.db"
    
    conn_pilot = sqlite3.connect(pilot_db_path)
    conn_pilot.execute("PRAGMA auto_vacuum = 0;")
    conn_pilot.execute("CREATE TABLE m0_signals (primary_stock_id TEXT NOT NULL, period_of_report TEXT NOT NULL, m0_signal REAL NOT NULL, PRIMARY KEY (primary_stock_id, period_of_report));")
    conn_pilot.execute("CREATE TABLE m0_signals_zero_excluded (primary_stock_id TEXT NOT NULL, period_of_report TEXT NOT NULL, m0_signal REAL NOT NULL, PRIMARY KEY (primary_stock_id, period_of_report));")
    conn_pilot.commit()
    conn_pilot.close()
    
    base_bytes = os.path.getsize(pilot_db_path)
    base_ps, base_pc = get_page_info(pilot_db_path)
    
    conn_pilot = sqlite3.connect(pilot_db_path)
    inserted_rows = 0
    selected_sets_info = {}
    with conn_pilot:
        for p in sorted_top4_keys:
            count, cusips = top4_sets[p]
            rows = []
            c_list = sorted(list(cusips))
            selected_sets_info[p] = {"count": count, "cusips": c_list}
            for c in c_list:
                padded = c + "XXX"
                rows.append((padded, p, 1.0))
            conn_pilot.executemany("INSERT INTO m0_signals VALUES (?, ?, ?)", rows)
            conn_pilot.executemany("INSERT INTO m0_signals_zero_excluded VALUES (?, ?, ?)", rows)
            inserted_rows += 2 * len(rows)
            
    conn_pilot.execute("PRAGMA optimize;")
    conn_pilot.execute("VACUUM;")
    conn_pilot.commit()
    conn_pilot.close()
    
    populated_bytes = os.path.getsize(pilot_db_path)
    pop_ps, pop_pc = get_page_info(pilot_db_path)
    
    bytes_per_row = (populated_bytes - base_bytes) / inserted_rows if inserted_rows > 0 else 0
    
    all_period_upper_rows = sum(period_counts.values())
    two_branch_all_period_upper_rows = 2 * all_period_upper_rows
    
    empirical_signal_db_bytes = math.ceil(1.20 * (base_bytes + bytes_per_row * two_branch_all_period_upper_rows) / pop_ps) * pop_ps
    explicit_non_db_reserve = 512 * 1024 * 1024
    provisional_floor = int(4.5 * 1024**3)
    
    projected_total_persistent_bytes = max(empirical_signal_db_bytes + explicit_non_db_reserve, provisional_floor)
    
    transient_reserve = int(1.5 * 1024**3)
    
    free_bytes = shutil.disk_usage(paths.base_dir).free
    
    gate_persistent = free_bytes >= 2 * projected_total_persistent_bytes
    gate_transient = free_bytes >= projected_total_persistent_bytes + transient_reserve
    final_pass = gate_persistent and gate_transient
    
    contract_path = Path("research/smart_money/m0/CONTRACT.md")
    contract_hash = compute_sha256_file(contract_path) if contract_path.exists() else "unknown"
    
    manifest = {
        "source_db_exact_size": source_size,
        "source_db_mtime": source_mtime,
        "sidecars_before": sidecars_before,
        "sidecars_after": sidecars_after,
        "query_only_pragma": 1,
        "source_git_sha": get_git_sha(),
        "contract_hash": contract_hash,
        "contract_version": "0.8.3",
        "schema_hash": compute_sha256_file(Path(__file__)),
        "schema_version": "1.0",
        "m0_tree_dirty": not check_git_clean_tree("research/smart_money/m0"),
        "m0_dirty_scope": "research/smart_money/m0",
        "global_dirty_paths": ["data/valuation/FED_PATH_HISTORY.json"],
        "periods": periods,
        "per_period_counts": period_counts,
        "selected_pilot_periods": sorted_top4_keys,
        "selected_sets": selected_sets_info,
        "page_size": pop_ps,
        "page_counts": {"empty": base_pc, "populated": pop_pc},
        "constants": {
            "explicit_non_db_reserve": 536870912,
            "provisional_floor": 4831838208,
            "transient_reserve": 1610612736,
            "persistent_margin": 1.2
        },
        "formulas": {
            "empirical_signal_db_bytes": "page-rounded 1.20 * (base + bytes_per_row * two_branch_all_period_upper_rows)",
            "projected_total_persistent_bytes": "max(empirical_signal_db_bytes + explicit_non_db_reserve, provisional_floor)"
        },
        "explanation": "4.5GiB remains a fail-safe floor because OpenFIGI/vendor/SEC evidence raw caches are not empirically calibrated yet.",
        "reserves": {
            "base_bytes": base_bytes,
            "bytes_per_row": bytes_per_row,
            "two_branch_all_period_upper_rows": two_branch_all_period_upper_rows,
            "empirical_signal_db_bytes": empirical_signal_db_bytes,
            "projected_total_persistent_bytes": projected_total_persistent_bytes
        },
        "free_space_device": paths.base_dir.anchor,
        "free_space_bytes": free_bytes,
        "gate_persistent_pass": gate_persistent,
        "gate_transient_pass": gate_transient,
        "final_decision": "PASS" if final_pass else "BLOCK",
        "runtime_sec": time.time() - t0
    }
    
    fd, temp_path = tempfile.mkstemp(dir=paths.signal_dir, text=True)
    with os.fdopen(fd, 'w') as f:
        json.dump(manifest, f, indent=2, allow_nan=False)
    os.replace(temp_path, paths.signal_dir / "c2_calibration_manifest.json")
    
    if not final_pass:
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
