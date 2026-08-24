"""SQLite storage guard, read-only URI formatting with immutable flag, and schema initializers."""

import os
from pathlib import Path
import sqlite3
import urllib.parse


def make_readonly_sqlite_uri(db_path: str | Path, immutable: bool = True) -> str:
    """Generate a valid SQLite read-only URI supporting special characters and immutable flag.
    
    Verifies that the target database file physically exists.
    """
    path_obj = Path(db_path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"SQLite database file not found: {db_path}")

    abs_path = os.path.abspath(str(path_obj))
    # quote path to safely handle characters like '?', '#', spaces, etc.
    quoted_path = urllib.parse.quote(abs_path)
    uri = f"file:{quoted_path}?mode=ro"
    if immutable:
        uri += "&immutable=1"
    return uri


def open_readonly_sqlite(db_path: str | Path, immutable: bool = True) -> sqlite3.Connection:
    """Open an SQLite database strictly in read-only mode using a URI connection.
    
    Enforces:
    1. File existence validation;
    2. URI mode=ro with immutable=1 (preventing WAL/SHM/journal generation for frozen sources);
    3. PRAGMA query_only = ON.
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
