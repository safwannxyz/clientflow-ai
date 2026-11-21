"""
db.py — schema, migrations and connection handling for Bureau.

Design decisions:
  * SQLite because the whole point is a system a small firm can run on one box
    without a platform team. The schema is written so a Postgres migration is a
    connection-string change plus a few type swaps, not a rewrite.
  * schema_version table + numbered migrations, so an existing database can be
    upgraded without dropping it. In a firm with real matters, you never get to
    start from a clean database again.
  * All timestamps are ISO-8601 UTC strings. They sort correctly as text, which
    keeps the queries simple and the audit log readable.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE contacts (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            email   TEXT,
            phone   TEXT,
            UNIQUE(email, phone)
        );

        CREATE TABLE matters (
            id            TEXT PRIMARY KEY,
            client        TEXT NOT NULL,
            practice_area TEXT NOT NULL,
            status        TEXT NOT NULL,
            opened_at     TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            fee_estimate  REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE enquiries (
            id                  TEXT PRIMARY KEY,
            contact_id          INTEGER NOT NULL REFERENCES contacts(id),
            source              TEXT NOT NULL,
            received_at         TEXT NOT NULL,
            message             TEXT NOT NULL,
            language            TEXT NOT NULL DEFAULT 'en',
            practice_area       TEXT NOT NULL,
            priority            TEXT NOT NULL,
            after_hours         INTEGER NOT NULL DEFAULT 0,
            confidence          REAL NOT NULL DEFAULT 0,
            needs_human         INTEGER NOT NULL DEFAULT 0,
            needs_arabic_review INTEGER NOT NULL DEFAULT 0,
            status              TEXT NOT NULL,
            owner               TEXT,
            documents_supplied  TEXT NOT NULL DEFAULT '[]',
            documents_missing   TEXT NOT NULL DEFAULT '[]',
            last_activity       TEXT NOT NULL,
            idempotency_key     TEXT NOT NULL UNIQUE
        );

        CREATE TABLE documents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            matter_id   TEXT REFERENCES matters(id),
            enquiry_id  TEXT REFERENCES enquiries(id),
            doc_type    TEXT NOT NULL,
            received_at TEXT NOT NULL,
            verified    INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE candidates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            role_ref      TEXT NOT NULL,
            name          TEXT NOT NULL,
            cv_text       TEXT NOT NULL,
            score         REAL NOT NULL DEFAULT 0,
            reasons       TEXT NOT NULL DEFAULT '[]',
            decision      TEXT NOT NULL DEFAULT 'pending',
            idempotency_key TEXT NOT NULL UNIQUE
        );

        CREATE TABLE campaign_weeks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign   TEXT NOT NULL,
            week       TEXT NOT NULL,
            spend      REAL NOT NULL,
            impressions INTEGER NOT NULL,
            clicks     INTEGER NOT NULL,
            leads      INTEGER NOT NULL,
            revenue    REAL NOT NULL,
            UNIQUE(campaign, week)
        );

        CREATE TABLE jobs (
            id             TEXT PRIMARY KEY,
            kind           TEXT NOT NULL,
            payload        TEXT NOT NULL,
            status         TEXT NOT NULL,
            attempts       INTEGER NOT NULL DEFAULT 0,
            max_attempts   INTEGER NOT NULL DEFAULT 3,
            run_after      TEXT NOT NULL,
            locked_by      TEXT,
            locked_at      TEXT,
            last_error     TEXT,
            idempotency_key TEXT NOT NULL UNIQUE,
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL
        );
        CREATE INDEX idx_jobs_status_run_after ON jobs(status, run_after);

        CREATE TABLE approvals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kind        TEXT NOT NULL,
            entity      TEXT NOT NULL,
            subject     TEXT NOT NULL,
            body        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TEXT NOT NULL,
            decided_by  TEXT,
            decided_at  TEXT,
            decision_note TEXT
        );

        CREATE TABLE audit_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT NOT NULL,
            actor     TEXT NOT NULL,
            action    TEXT NOT NULL,
            entity    TEXT NOT NULL,
            detail    TEXT NOT NULL
        );

        CREATE TABLE systems_register (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            purpose       TEXT NOT NULL,
            owner         TEXT NOT NULL,
            data_touched  TEXT NOT NULL,
            permissions   TEXT NOT NULL,
            approval_gate TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'prototype'
        );
        """,
    ),
]


class Database:
    """Thin wrapper: one connection, explicit transactions, no ORM."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    # ---------------------------------------------------------------- schema
    def _migrate(self) -> None:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
        )
        row = self.conn.execute("SELECT version FROM schema_version").fetchone()
        current = row["version"] if row else 0
        for version, sql in MIGRATIONS:
            if version <= current:
                continue
            self.conn.executescript("BEGIN;" + sql + "COMMIT;")
            if row:
                self.conn.execute("UPDATE schema_version SET version = ?", (version,))
            else:
                self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            current = version

    @property
    def version(self) -> int:
        row = self.conn.execute("SELECT version FROM schema_version").fetchone()
        return int(row["version"]) if row else 0

    # ------------------------------------------------------------ utilities
    def q(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: tuple = ()):
        row = self.conn.execute(sql, params).fetchone()
        return row[0] if row else None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def table_counts(self) -> dict[str, int]:
        names = [r["name"] for r in self.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        return {n: int(self.scalar(f"SELECT COUNT(*) FROM {n}")) for n in names}

    def close(self) -> None:
        self.conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def days_ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()


def open_db(path: str | Path = ":memory:") -> Database:
    return Database(path)
