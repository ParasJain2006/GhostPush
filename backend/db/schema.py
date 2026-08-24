"""SQLite DDL schema definitions and table creation for GhostPush."""

import sqlite3

CREATE_JOBS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY NOT NULL,
    status TEXT NOT NULL,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    language TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    response_json TEXT,
    commit_hash TEXT,
    push_success INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);",
]


def create_tables(conn: sqlite3.Connection) -> None:
    """Execute DDL statements to create tables and indexes."""
    with conn:
        conn.execute(CREATE_JOBS_TABLE_SQL)
        for idx_sql in CREATE_INDEXES_SQL:
            conn.execute(idx_sql)

        # Migration: ensure push_success column exists in pre-existing SQLite databases
        cur = conn.execute("PRAGMA table_info(jobs)")
        columns = [row[1] for row in cur.fetchall()]
        if "push_success" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN push_success INTEGER DEFAULT NULL")
