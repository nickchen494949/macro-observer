#!/usr/bin/env python3
"""
v2_00_cleanroom_ast_and_readonly_guard.py — Mechanical Clean-Room & Read-Only Enforcement Guard.

Audits all Python scripts inside `outputs/gemini_full_data_audit_20261031/v2_standalone/` using
Python's `ast` module and enforces:
  1. ZERO imports of any audited project module (`backtest`, `ml2_run`, `fundamentals_pit`,
     `build_fundamentals`, `historical_sectors`, `ticker_aliases`, `winners_tracks`, `winners_holdout`, etc.).
     Only an explicit allowlist of Python stdlib modules, standard scientific packages
     (`numpy`, `pandas`, `openpyxl`, `pypdf`, `scipy`), and `v2_cleanroom_lib` is permitted.
  2. ZERO `sys.path.insert` / `sys.path.append` calls pointing outside `v2_standalone/`.
  3. ZERO false-pass fallback anti-patterns (`else led_g`, `else: ok = True`, `else: ok_13f = True`,
     or `LIMIT 25` in 13F line-item verification).
  4. ZERO modifications to any of the 10,964 protected baseline files (`00_baseline_integrity_guard.py verify`).
"""
import ast
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(AUDIT_ROOT))

ALLOWED_TOP_LEVEL_MODULES = {
    # Python stdlib
    "ast",
    "collections",
    "csv",
    "datetime",
    "functools",
    "glob",
    "hashlib",
    "io",
    "itertools",
    "json",
    "math",
    "os",
    "pathlib",
    "random",
    "re",
    "sqlite3",
    "statistics",
    "subprocess",
    "sys",
    "time",
    "typing",
    "urllib",
    "zipfile",
    # Third-party standard packages
    "numpy",
    "pandas",
    "openpyxl",
    "pypdf",
    "scipy",
    # Clean-room standalone helper inside v2_standalone/ ONLY
    "v2_cleanroom_lib",
}

FORBIDDEN_PROJECT_MODULES = {
    "backtest",
    "build_fundamentals",
    "composite3",
    "earnings_factor",
    "eps_momentum",
    "explosive_factors",
    "explosive_v2",
    "factor_combo",
    "factor_screen",
    "fundamentals_pit",
    "historical_sectors",
    "ml2_features",
    "ml2_run",
    "ml_features",
    "ml_pipeline",
    "ndx_expand",
    "ndx_fundamentals",
    "ndx_universe",
    "smallcap_data_audit",
    "smallcap_universe",
    "ticker_aliases",
    "winners_holdout",
    "winners_tracks",
}

FORBIDDEN_SUBSTRINGS = [
    "else led_g",
    "else: ok = True",
    "else: ok_13f = True",
    "LIMIT 25",
    "implied_cost = led_g - led_n",
    'float(row["gross"]) - float(row["net"])',
]


def check_script(py_path: str) -> dict:
    bn = os.path.basename(py_path)
    with open(py_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=py_path)

    imports_found = []
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                imports_found.append(alias.name)
                if top in FORBIDDEN_PROJECT_MODULES or top not in ALLOWED_TOP_LEVEL_MODULES:
                    violations.append(f"Line {node.lineno}: forbidden import `{alias.name}`")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".")[0] if mod else ""
            imports_found.append(f"from {mod}")
            if node.level > 0 and top not in ("", "v2_cleanroom_lib"):
                violations.append(f"Line {node.lineno}: relative import `{mod}`")
            elif top in FORBIDDEN_PROJECT_MODULES or (top and top not in ALLOWED_TOP_LEVEL_MODULES):
                violations.append(f"Line {node.lineno}: forbidden from-import `{mod}`")
        elif isinstance(node, ast.Call):
            # Detect sys.path.insert / sys.path.append
            func_src = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
            if func_src in ("sys.path.insert", "sys.path.append"):
                call_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                if "HERE" not in call_src:
                    violations.append(f"Line {node.lineno}: forbidden sys.path mutation `{call_src}`")
            if func_src in ("__import__", "importlib.import_module"):
                violations.append(f"Line {node.lineno}: dynamic import `{func_src}` forbidden")

    # Skip self-inspection literal table inside v2_00 itself
    if bn != "v2_00_cleanroom_ast_and_readonly_guard.py":
        for pat in FORBIDDEN_SUBSTRINGS:
            if pat in src:
                violations.append(f"Forbidden false-pass pattern `{pat}` present in source")

    return {
        "script": bn,
        "imports": sorted(set(imports_found)),
        "violation_count": len(violations),
        "violations": violations,
    }


def main() -> None:
    scripts = sorted(glob.glob(os.path.join(HERE, "*.py")))
    results = [check_script(p) for p in scripts]
    total_violations = sum(r["violation_count"] for r in results)

    # Run read-only baseline integrity guard across all 10,964 protected files
    guard_script = os.path.join(AUDIT_ROOT, "00_baseline_integrity_guard.py")
    proc = subprocess.run(
        [sys.executable, guard_script, "verify"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    baseline_json_path = os.path.join(AUDIT_ROOT, "baseline_integrity_check.json")
    baseline_res = {}
    if os.path.exists(baseline_json_path):
        with open(baseline_json_path, "r", encoding="utf-8") as fh:
            baseline_res = json.load(fh)

    baseline_ok = (
        proc.returncode == 0
        and baseline_res.get("status") == "PASS"
        and len(baseline_res.get("changed", ["x"])) == 0
        and len(baseline_res.get("missing", ["x"])) == 0
        and len(baseline_res.get("added", ["x"])) == 0
    )

    report = {
        "status": "PASS" if (total_violations == 0 and baseline_ok) else "FAIL",
        "scripts_checked": len(results),
        "total_ast_or_pattern_violations": total_violations,
        "per_script": results,
        "readonly_baseline_guard": baseline_res,
    }
    out_path = os.path.join(HERE, "v2_00_cleanroom_guard_report.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"[v2_00] Clean-Room AST & Anti-Fallback Check: scripts={len(results)}, violations={total_violations}")
    print(f"[v2_00] Read-Only Baseline Check ({baseline_res.get('protected_files_checked')} protected files): {baseline_res.get('status')} "
          f"(changed={len(baseline_res.get('changed', []))}, missing={len(baseline_res.get('missing', []))}, added={len(baseline_res.get('added', []))})")
    if total_violations > 0 or not baseline_ok:
        for r in results:
            for v in r["violations"]:
                print(f"  VIOLATION in {r['script']}: {v}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
