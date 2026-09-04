"""Run path resolution, realpath security verification, and directory isolation."""

from dataclasses import dataclass
import os
from pathlib import Path
import re

_SAFE_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class RunPaths:
    """Encapsulates all physical paths for an isolated M0 backtest run."""
    run_id: str
    base_dir: Path
    signal_dir: Path
    outcome_dir: Path
    signal_db_path: Path
    outcome_db_path: Path
    signal_manifest_path: Path
    price_manifest_path: Path
    split_audit_report_path: Path
    signal_coverage_report_path: Path
    outcome_coverage_report_path: Path
    results_report_path: Path

    def ensure_directories(self) -> None:
        """Create base, signal, and outcome directories."""
        self.signal_dir.mkdir(parents=True, exist_ok=True)
        self.outcome_dir.mkdir(parents=True, exist_ok=True)


def get_default_m0_root() -> Path:
    """Return canonical root directory of research/smart_money/m0."""
    return Path(__file__).resolve().parent.parent


def create_run_paths(run_id: str, m0_root: str | Path | None = None) -> RunPaths:
    """Create and validate physically isolated RunPaths for a given run_id.

    Enforces:
    1. Valid identifier syntax for run_id (no path traversal '..' or slashes).
    2. Strict child relationship of runs_root to m0_root (rejecting symlink escapes).
    3. Strict child relationship of base_dir to runs root.
    4. Strict child relationship of signal and outcome to base_dir.
    5. Strict independence and non-overlapping invariant between signal and outcome dirs.
    """
    if not run_id or not isinstance(run_id, str) or not _SAFE_RUN_ID_PATTERN.match(run_id.strip()):
        raise ValueError(
            f"Invalid run_id {run_id!r}. Must be non-empty alphanumeric string with hyphens or underscores only."
        )

    clean_id = run_id.strip()
    root = Path(m0_root).resolve() if m0_root is not None else get_default_m0_root()
    root_realpath = Path(os.path.realpath(root))

    runs_unresolved = root_realpath / "runs"
    # If runs directory exists as a symlink, verify its target doesn't escape m0_root
    if runs_unresolved.is_symlink():
        runs_target_realpath = Path(os.path.realpath(runs_unresolved))
        try:
            rel = runs_target_realpath.relative_to(root_realpath)
            if len(rel.parts) != 1 or rel.parts[0] != "runs":
                raise ValueError(f"runs directory is a symlink escaping m0_root: {runs_target_realpath}")
        except ValueError as err:
            raise ValueError(f"runs directory is an escape symlink: {runs_unresolved} -> {runs_target_realpath}") from err

    runs_root = Path(os.path.realpath(runs_unresolved))
    try:
        rel_runs = runs_root.relative_to(root_realpath)
        if len(rel_runs.parts) != 1 or rel_runs.parts[0] != "runs":
            raise ValueError(f"runs_root must be a direct child of m0_root: {runs_root}")
    except ValueError as err:
        raise ValueError(f"runs_root escapes m0_root: {err}") from err

    base_dir = Path(os.path.realpath(runs_root / clean_id))
    try:
        rel_base = base_dir.relative_to(runs_root)
        if len(rel_base.parts) != 1 or rel_base.parts[0] != clean_id:
            raise ValueError(f"run_dir must be a direct child of runs root: {base_dir}")
    except ValueError as err:
        raise ValueError(f"Path traversal or escape detected: {base_dir} is not inside {runs_root}") from err

    signal_dir = Path(os.path.realpath(base_dir / "signal"))
    outcome_dir = Path(os.path.realpath(base_dir / "outcome"))

    try:
        rel_sig = signal_dir.relative_to(base_dir)
        rel_out = outcome_dir.relative_to(base_dir)
        if len(rel_sig.parts) != 1 or rel_sig.parts[0] != "signal":
            raise ValueError(f"Signal directory must be a direct child of base_dir: {signal_dir}")
        if len(rel_out.parts) != 1 or rel_out.parts[0] != "outcome":
            raise ValueError(f"Outcome directory must be a direct child of base_dir: {outcome_dir}")
    except ValueError as err:
        raise ValueError(f"Symlink alias or path escape detected for subdirectories: {err}") from err

    if signal_dir == outcome_dir:
        raise ValueError("Signal and outcome directories must not be identical.")
    if outcome_dir.is_relative_to(signal_dir) or signal_dir.is_relative_to(outcome_dir):
        raise ValueError("Signal and outcome directories must not be nested or overlapping.")

    return RunPaths(
        run_id=clean_id,
        base_dir=base_dir,
        signal_dir=signal_dir,
        outcome_dir=outcome_dir,
        signal_db_path=signal_dir / "m0_signal.db",
        outcome_db_path=outcome_dir / "m0_outcome.db",
        signal_manifest_path=signal_dir / "SHA256_SIGNAL_MANIFEST.json",
        price_manifest_path=outcome_dir / "SHA256_PRICE_MANIFEST.json",
        split_audit_report_path=signal_dir / "m0_split_waterfall_audit.md",
        signal_coverage_report_path=signal_dir / "m0_signal_coverage.md",
        outcome_coverage_report_path=outcome_dir / "m0_dual_denominator_coverage.md",
        results_report_path=base_dir / "M0_RESULTS.md",
    )
