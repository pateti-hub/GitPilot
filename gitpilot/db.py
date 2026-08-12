"""Tiny SQLite metadata store.

Every DB access lives in this one file, so swapping SQLite for PostgreSQL
later means changing exactly one module - the 'single point of change'
design you describe in interviews.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    repo_id        TEXT PRIMARY KEY,
    repo_url       TEXT NOT NULL,
    status         TEXT NOT NULL,
    files_indexed  INTEGER NOT NULL DEFAULT 0,
    chunks_indexed INTEGER NOT NULL DEFAULT 0,
    indexed_at     TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)


def upsert_repo(
    repo_id: str,
    repo_url: str,
    status: str,
    files_indexed: int = 0,
    chunks_indexed: int = 0,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO repos (repo_id, repo_url, status, files_indexed,
                               chunks_indexed, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_id) DO UPDATE SET
                repo_url       = excluded.repo_url,
                status         = excluded.status,
                files_indexed  = excluded.files_indexed,
                chunks_indexed = excluded.chunks_indexed,
                indexed_at     = excluded.indexed_at
            """,
            (repo_id, repo_url, status, files_indexed, chunks_indexed, now),
        )


def get_repo(repo_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM repos WHERE repo_id = ?", (repo_id,)
        ).fetchone()
    return dict(row) if row else None


def list_repos() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM repos ORDER BY indexed_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]
