"""SQLite storage guard, read-only URI formatting with immutable flag, and schema initializers."""

import os
from pathlib import Path
import sqlite3
import urllib.parse


def _check_sqlite_sidecars(db_file: Path) -> list[Path]:
    """Find any existing WAL, SHM, or journal sidecar files for the target DB."""
    sidecar_candidates = [
        Path(str(db_file) + "-wal"),
        Path(str(db_file) + "-shm"),
        Path(str(db_file) + "-journal"),
    ]
    if db_file.suffix == ".db":
        sidecar_candidates.extend(
            [
                db_file.with_name(db_file.stem + ".db-wal"),
                db_file.with_name(db_file.stem + ".db-shm"),
            ]
        )
    existing = []
    seen: set[str] = set()
    for cand in sidecar_candidates:
        cand_str = str(cand.resolve()) if cand.is_file() else str(cand)
        if cand.exists() and cand_str not in seen:
            seen.add(cand_str)
            existing.append(cand)
    return existing


def make_readonly_sqlite_uri(db_path: str | Path, immutable: bool = True) -> str:
    """Generate a valid SQLite read-only URI supporting special characters and immutable flag.

    Verifies that the target database file physically exists.
    If immutable=True, rejects opening if any sibling .db-wal, .db-shm, or journal sidecars exist.
    """
    if type(immutable) is not bool:
        raise TypeError("immutable flag must be a strict boolean.")

    path_obj = Path(db_path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"SQLite database file not found: {db_path}")

    if immutable:
        existing_sidecars = _check_sqlite_sidecars(path_obj)
        if existing_sidecars:
            sidecar_names = [s.name for s in existing_sidecars]
            raise ValueError(
                f"Immutable open rejected for {path_obj.name}: sibling sidecar(s) exist {sidecar_names}. "
                f"Database is not frozen or has uncheckpointed WAL/SHM content."
            )

    abs_path = os.path.abspath(str(path_obj))
    quoted_path = urllib.parse.quote(abs_path)
    uri = f"file:{quoted_path}?mode=ro"
    if immutable:
        uri += "&immutable=1"
    return uri


def open_readonly_sqlite(db_path: str | Path, immutable: bool = True) -> sqlite3.Connection:
    """Open an SQLite database strictly in read-only mode using a URI connection.

    Enforces:
    1. File existence validation;
    2. Sibling sidecar absence check when immutable=True;
    3. URI mode=ro with immutable=1 when immutable=True;
    4. PRAGMA query_only = ON.
    """
    uri = make_readonly_sqlite_uri(db_path, immutable=immutable)
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON;")
    return conn


def init_signal_db(db_path: str | Path) -> None:
    """Initialize schema for m0_signal.db."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS m0_signals (
                    primary_stock_id TEXT NOT NULL,
                    period_of_report TEXT NOT NULL,
                    m0_signal REAL NOT NULL,
                    PRIMARY KEY (primary_stock_id, period_of_report)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS m0_signals_zero_excluded (
                    primary_stock_id TEXT NOT NULL,
                    period_of_report TEXT NOT NULL,
                    m0_signal REAL NOT NULL,
                    PRIMARY KEY (primary_stock_id, period_of_report)
                );
                """
            )
    finally:
        conn.close()


def init_outcome_db(db_path: str | Path) -> None:
    """Initialize schema for m0_outcome.db."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS m0_forward_returns (
                    primary_stock_id TEXT NOT NULL,
                    period_of_report TEXT NOT NULL,
                    forward_return REAL,
                    outcome_status TEXT NOT NULL,
                    rolled_le_5_return REAL,
                    PRIMARY KEY (primary_stock_id, period_of_report)
                );
                """
            )
    finally:
        conn.close()
