import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "test/phase4_composite_validation/output"


def load(name):
    with (OUT_DIR / name).open() as f:
        return json.load(f)


def main():
    ic = load("02_composite_ic.json")
    oos = load("03_composite_oos.json")
    robust = load("04_composite_robustness.json")

    failures = []
    if not ic.get("valid"):
        failures.append("Primary 5D development IC test invalid/insufficient.")
    else:
        if not ic.get("direction_pass"):
            failures.append("Primary 5D Spearman IC direction failed.")
        if not ic.get("hac_pass"):
            failures.append("Primary 5D HAC rank-regression gate failed.")
        if not ic.get("ic_bootstrap_pass"):
            failures.append("Primary 5D IC moving-block bootstrap CI includes zero/wrong direction.")
        if not ic.get("partial_ic_pass"):
            failures.append("Primary 5D Partial Rank IC direction failed/undefined.")

    if not oos.get("valid"):
        failures.append("True 2025-2026 holdout OOS test invalid/insufficient.")
    elif not oos.get("squared_error_pass"):
        failures.append("True 2025-2026 pooled OOS squared-error gate failed.")

    if not robust.get("valid"):
        failures.append("Development robustness test invalid/insufficient.")
    elif not robust.get("regime_pass"):
        failures.append("Development annual/LOYO robustness rules failed.")

    status = "SUPPORTED" if not failures else "NOT_SUPPORTED"
    verdict = {
        "signal": "systematicFlowComposite",
        "primaryHorizon": 5,
        "status": status,
        "failure_reasons": failures,
        "secondaryHypothesesUsedForGate": False,
        "productionFlowEngineMayBeChanged": status == "SUPPORTED",
    }
    with (OUT_DIR / "05_composite_verdict.json").open("w") as f:
        json.dump(verdict, f, indent=2)

    report = [
        "# Phase 4 Composite Validation",
        "",
        f"**Final verdict: {status}**",
        "",
        "Primary hypothesis: equal-weight Systematic Flow Composite vs 5D SPX forward return.",
        "Phase 3 module verdicts remain unchanged and are not overridden by Phase 4.",
        "",
        "## Failure reasons",
    ]
    report.extend([f"- {r}" for r in failures] if failures else ["- None. All pre-registered Phase 4 gates passed."])
    report.extend([
        "",
        "## Gate components",
        f"- Development IC valid: {ic.get('valid')}",
        f"- Development IC direction: {ic.get('direction_pass')}",
        f"- Development HAC gate: {ic.get('hac_pass')}",
        f"- Development IC bootstrap: {ic.get('ic_bootstrap_pass')}",
        f"- Development Partial IC: {ic.get('partial_ic_pass')}",
        f"- True holdout OOS valid: {oos.get('valid')}",
        f"- True holdout OOS squared-error gate: {oos.get('squared_error_pass')}",
        f"- Development robustness valid: {robust.get('valid')}",
        f"- Development robustness gate: {robust.get('regime_pass')}",
        "",
        "Production flow_engine.js remains untouched unless verdict is SUPPORTED.",
    ])
    (OUT_DIR / "phase4_composite_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
