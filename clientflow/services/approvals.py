"""
approvals.py — the human-in-the-loop gate.

Every outbound artefact the platform produces (an acknowledgement, a document
chase, a shortlist recommendation) becomes a row here with status 'pending'.
There is no send function anywhere in ClientFlow: this module can record a
decision, not transmit one. That is deliberate and it is the first thing to say
when someone asks how the automation is kept safe.
"""

from __future__ import annotations

from ..core.audit import Audit
from ..core.db import Database, now_iso
from ..core.security import PermissionDenied, require

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


class Approvals:
    def __init__(self, db: Database):
        self.db = db
        self.audit = Audit(db)

    def create(self, kind: str, entity: str, subject: str, body: str) -> int:
        cur = self.db.execute(
            """INSERT INTO approvals (kind, entity, subject, body, status, created_at)
               VALUES (?,?,?,?,?,?)""",
            (kind, entity, subject, body, PENDING, now_iso()),
        )
        self.audit.log("system", "approval_requested", entity, f"{kind}: {subject}")
        return int(cur.lastrowid)

    def pending(self) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT * FROM approvals WHERE status = ? ORDER BY id", (PENDING,))]

    def all(self, limit: int = 100) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT * FROM approvals ORDER BY id DESC LIMIT ?", (limit,))]

    def get(self, approval_id: int) -> dict | None:
        row = self.db.one("SELECT * FROM approvals WHERE id = ?", (approval_id,))
        return dict(row) if row else None

    def decide(self, approval_id: int, role: str, decision: str,
               actor: str = "approver", note: str = "") -> dict:
        """Record a human decision. Requires the 'approve' capability."""
        require(role, "approve")
        if decision not in (APPROVED, REJECTED):
            raise ValueError("decision must be 'approved' or 'rejected'")
        row = self.get(approval_id)
        if row is None:
            raise KeyError(f"approval {approval_id} not found")
        if row["status"] != PENDING:
            raise ValueError(f"approval {approval_id} already {row['status']}")

        self.db.execute(
            """UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?, decision_note = ?
               WHERE id = ?""",
            (decision, actor, now_iso(), note, approval_id),
        )
        self.audit.log(actor, f"approval_{decision}", row["entity"],
                       f"#{approval_id} {row['kind']} — {note}")
        return self.get(approval_id) or {}

    def stats(self) -> dict:
        rows = self.db.q("SELECT status, COUNT(*) c FROM approvals GROUP BY status")
        stats = {r["status"]: int(r["c"]) for r in rows}
        return {k: stats.get(k, 0) for k in (PENDING, APPROVED, REJECTED)}
