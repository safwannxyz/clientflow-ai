"""
queue.py — a durable job queue on SQLite.

Why a queue at all? Because the failure mode of a script is that nobody notices
it stopped. A queue gives three things a demo script cannot:

  1. **Retries with backoff** — a flaky API call does not lose the work.
  2. **Dead-letter** — after max_attempts the job lands in 'failed' and shows up
     on the dashboard instead of disappearing.
  3. **A visible backlog** — pending/running/failed counts are the health signal.

Locking uses a single UPDATE ... WHERE id IN (SELECT ...) inside a transaction,
so two workers cannot claim the same job. That is the same idea as
FOR UPDATE SKIP LOCKED in Postgres, done with the primitives SQLite has.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from .db import Database, now_iso

PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"

BACKOFF_SECONDS = (30, 120, 600)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


class Queue:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------- enqueue
    def enqueue(self, kind: str, payload: dict, key: str | None = None,
                max_attempts: int = 3, run_after: str | None = None) -> str | None:
        """Enqueue a job. Returns the job id, or None if the key was already seen.

        The idempotency key is the caller's promise that this piece of work should
        only ever happen once, even if a webhook fires twice.
        """
        job_id = uuid.uuid4().hex[:12]
        key = key or f"{kind}:{job_id}"
        if self.db.one("SELECT id FROM jobs WHERE idempotency_key = ?", (key,)):
            return None
        self.db.execute(
            """INSERT INTO jobs (id, kind, payload, status, attempts, max_attempts,
                                 run_after, idempotency_key, created_at, updated_at)
               VALUES (?,?,?,?,0,?,?,?,?,?)""",
            (job_id, kind, json.dumps(payload), PENDING, max_attempts,
             run_after or now_iso(), key, now_iso(), now_iso()),
        )
        return job_id

    # --------------------------------------------------------------- claim
    def claim(self, worker: str, limit: int = 10) -> list[dict]:
        """Claim up to `limit` due jobs atomically and return them."""
        due = [r["id"] for r in self.db.q(
            "SELECT id FROM jobs WHERE status = ? AND run_after <= ? ORDER BY run_after LIMIT ?",
            (PENDING, now_iso(), limit),
        )]
        if not due:
            return []
        placeholders = ",".join("?" * len(due))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                f"""UPDATE jobs SET status = ?, locked_by = ?, locked_at = ?, updated_at = ?
                    WHERE id IN ({placeholders}) AND status = ?""",
                (RUNNING, worker, now_iso(), now_iso(), *due, PENDING),
            )
            claimed = self.db.q(
                f"SELECT * FROM jobs WHERE id IN ({placeholders}) AND locked_by = ? AND status = ?",
                (*due, worker, RUNNING),
            )
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return [dict(r) for r in claimed]

    # --------------------------------------------------------- complete/fail
    def complete(self, job_id: str, result: dict | None = None) -> None:
        self.db.execute(
            "UPDATE jobs SET status = ?, updated_at = ?, last_error = NULL WHERE id = ?",
            (DONE, now_iso(), job_id),
        )
        if result is not None:
            self.db.execute(
                "UPDATE jobs SET last_error = ? WHERE id = ?",
                (None, job_id),
            )

    def fail(self, job_id: str, error: str) -> str:
        """Record a failure. Reschedules with backoff, or dead-letters the job."""
        row = self.db.one("SELECT attempts, max_attempts FROM jobs WHERE id = ?", (job_id,))
        if row is None:
            raise KeyError(job_id)
        attempts = int(row["attempts"]) + 1
        if attempts >= int(row["max_attempts"]):
            self.db.execute(
                """UPDATE jobs SET status = ?, attempts = ?, last_error = ?, updated_at = ?,
                          locked_by = NULL WHERE id = ?""",
                (FAILED, attempts, error[:500], now_iso(), job_id),
            )
            return FAILED
        delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
        run_after = _iso(datetime.now(timezone.utc) + timedelta(seconds=delay))
        self.db.execute(
            """UPDATE jobs SET status = ?, attempts = ?, last_error = ?, run_after = ?,
                      updated_at = ?, locked_by = NULL WHERE id = ?""",
            (PENDING, attempts, error[:500], run_after, now_iso(), job_id),
        )
        return PENDING

    def requeue_dead_letters(self, kind: str | None = None) -> int:
        sql = "UPDATE jobs SET status = ?, attempts = 0, run_after = ?, updated_at = ? WHERE status = ?"
        params = [PENDING, now_iso(), now_iso(), FAILED]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        return self.db.execute(sql, tuple(params)).rowcount

    # ---------------------------------------------------------------- stats
    def stats(self) -> dict:
        rows = self.db.q("SELECT status, COUNT(*) c FROM jobs GROUP BY status")
        by_status = {r["status"]: int(r["c"]) for r in rows}
        oldest = self.db.one(
            "SELECT id, kind, created_at FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1",
            (PENDING,),
        )
        return {
            "pending": by_status.get(PENDING, 0),
            "running": by_status.get(RUNNING, 0),
            "done": by_status.get(DONE, 0),
            "failed": by_status.get(FAILED, 0),
            "oldest_pending": dict(oldest) if oldest else None,
        }

    def recent(self, limit: int = 20) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT id, kind, status, attempts, max_attempts, last_error, updated_at "
            "FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
        )]
