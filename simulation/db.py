"""SQLite connection helper for the simulation engine."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "inventory" / "inventory.db"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection configured for a long-lived writer process sharing
    the DB with concurrent short-lived readers (the dashboard)."""
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    return conn
