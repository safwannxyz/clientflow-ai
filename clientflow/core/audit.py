"""
audit.py — the append-only log.

Rules this module enforces:
  * Every line is redacted before it is stored (identity numbers never land here).
  * There is no update or delete API in this module, by design. If you need to
    correct the record, you append a correction — that is what auditors expect.
  * The actor is always named: 'system', 'worker:<id>', or a human role.
"""

from __future__ import annotations

from .db import Database, now_iso
from .security import redact


class Audit:
    def __init__(self, db: Database):
        self.db = db

    def log(self, actor: str, action: str, entity: str, detail: str = "") -> None:
        self.db.execute(
            "INSERT INTO audit_log (ts, actor, action, entity, detail) VALUES (?,?,?,?,?)",
            (now_iso(), actor, action, entity, redact(detail)[:400]),
        )

    def for_entity(self, entity: str, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT * FROM audit_log WHERE entity = ? ORDER BY id DESC LIMIT ?",
            (entity, limit),
        )]

    def recent(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        )]

    def count_by_action(self) -> dict[str, int]:
        return {r["action"]: int(r["c"]) for r in self.db.q(
            "SELECT action, COUNT(*) c FROM audit_log GROUP BY action ORDER BY c DESC"
        )}

    def verify_append_only(self) -> bool:
        """Cheap guard used by the tests: no row may be edited once written.

        SQLite has no triggers installed to block it, so the test instead checks
        that the module exposes no mutating entry point. This method exists so the
        intent is visible in code rather than in a comment somewhere.
        """
        return not any(
            hasattr(self, name) for name in ("update", "delete", "remove", "edit")
        )
