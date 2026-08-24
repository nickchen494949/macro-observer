"""SQLite storage guard, read-only URI formatting, and schema initializers."""

import os
from pathlib import Path
import sqlite3
import urllib.parse


def make_readonly_sqlite_uri(db_path: str | Path) -> str:
    """Generate a valid SQLite read-only URI supporting special characters."""
    abs_path = os.path.abspath(str(db_path))
    # quote path to safely handle characters like '?', '#', spaces, etc.
    quoted_path = urllib.parse.quote(abs_path)
    return f"file:{quoted_path}?mode=ro"


def open_readonly_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Open an SQLite database strictly in read-only mode using a URI connection.
    
    Any write attempt on this connection will be blocked by SQLite engine.
    """
    uri = make_readonly_sqlite_uri(db_path)
    conn = sqlite3.connect(uri, uri=True)
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
