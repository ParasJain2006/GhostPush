"""SQLite database connection management and pragmas for GhostPush backend."""

import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from backend.config.settings import get_config_dir
from backend.db.schema import create_tables


def get_db_dir() -> Path:
    """Return the cross-platform database directory."""
    return get_config_dir()


def get_default_db_path() -> Path:
    """Return the default SQLite database file path."""
    return get_db_dir() / "ghostpush.db"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection with WAL mode and busy timeout."""
    target_path = db_path or get_default_db_path()
    if target_path != Path(":memory:"):
        target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db(db_path: Optional[Path] = None) -> Path:
    """Initialize SQLite database tables and indexes."""
    target_path = db_path or get_default_db_path()
    conn = get_db_connection(target_path)
    try:
        create_tables(conn)
    finally:
        conn.close()
    return target_path
