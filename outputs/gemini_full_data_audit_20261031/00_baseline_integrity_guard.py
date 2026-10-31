#!/usr/bin/env python3
"""
Read-only baseline integrity guard for Gemini Full Backtest Data Audit (2026-10-31).
Snapshots fingerprints of all backtest code, data, and prior audit folders before
running our audit, and verifies zero bytes were modified after all audits finish.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path("/Users/happygolucky/Desktop/宏观观察器")
OUT_DIR = ROOT / "outputs/gemini_full_data_audit_20261031"
SNAP_PATH = OUT_DIR / "baseline_fingerprints.json"

PROTECTED_TARGETS = [
    "CLAUDE_AUDITED_VERSION.json",
    "backtest.js",
    "backtest_v2.js",
    "backtest_v3.js",
    "experiment_wealth_sep.py",
    "factor_model.py",
    "inflation_forecast.py",
    "parse_sep.py",
    "data/sector_eps",
    "data/fomc_sep",
    "data/yahoo_validated",
    "data/benchmark",
    "data/sep_revisions.json",
    "backtest",
    "research",
    "backtest_versions/VERSIONS.txt",
    "backtest_versions/2026-10-30_codex_audited_modified/audit",
    "backtest_versions/2026-10-30_codex_full_audit_v2/audit_v2",
    "outputs/backtest_full_audit_v2_20261030",
    "outputs/sector_eps_then_momentum_20261030/AUDIT_REPORT.txt",
    "outputs/sector_eps_then_momentum_20261030/universe_audit/VERDICT.json",
    "outputs/top3_qqq_rebalance_20261030",
    "outputs/top3_include_latest_month_20261030",
    "outputs/top3_leverage_scenarios_20261030",
]

SKIP_DIRS = {"__pycache__", ".venv", "node_modules", ".git"}
LARGE_THRESHOLD = 25 * 1024 * 1024  # 25 MB


def fingerprint_file(p: Path) -> dict:
    st = p.stat()
    sz = st.st_size
    h = hashlib.sha256()
    if sz <= LARGE_THRESHOLD:
        with p.open("rb") as f:
            while True:
                b = f.read(1024 * 1024)
                if not b:
                    break
                h.update(b)
        mode = "sha256_full"
    else:
        with p.open("rb") as f:
            h.update(f.read(2 * 1024 * 1024))
            f.seek(max(0, sz - 2 * 1024 * 1024))
            h.update(f.read(2 * 1024 * 1024))
        mode = "sha256_head_tail_2mb"
    return {"size": sz, "mode": mode, "digest": h.hexdigest()}


def collect() -> dict:
    records = {}
    for rel in PROTECTED_TARGETS:
        target = ROOT / rel
        if not target.exists():
            continue
        if target.is_file():
            records[rel] = fingerprint_file(target)
        else:
            for r, dirs, files in os.walk(target):
                dirs[:] = sorted([d for d in dirs if d not in SKIP_DIRS])
                for fn in sorted(files):
                    if fn.endswith((".pyc", ".pyo", "-shm", "-wal")):
                        continue
                    fp = Path(r) / fn
                    if fp.is_symlink():
                        continue
                    k = str(fp.relative_to(ROOT))
                    records[k] = fingerprint_file(fp)
    return records


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if cmd == "snapshot":
        recs = collect()
        payload = {"file_count": len(recs), "files": recs}
        SNAP_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"[GUARD] Snapshotted {len(recs):,} protected backtest files -> {SNAP_PATH}")
    elif cmd == "verify":
        old = json.loads(SNAP_PATH.read_text())["files"]
        cur = collect()
        missing = sorted(set(old) - set(cur))
        added = sorted(set(cur) - set(old))
        changed = sorted([k for k in (set(old) & set(cur)) if old[k] != cur[k]])
        res = {
            "status": "PASS" if (not missing and not added and not changed) else "FAIL",
            "protected_files_checked": len(old),
            "missing": missing,
            "added": added,
            "changed": changed,
        }
        out_p = OUT_DIR / "baseline_integrity_check.json"
        out_p.write_text(json.dumps(res, indent=2, ensure_ascii=False))
        print(f"[GUARD] Integrity check: {res['status']} ({len(old):,} files, {len(changed)} changed, {len(missing)} missing, {len(added)} added)")
        if res["status"] != "PASS":
            sys.exit(1)
    else:
        raise SystemExit(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
