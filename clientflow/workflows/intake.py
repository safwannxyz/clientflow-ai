"""
intake.py — enquiry triage for the group's front doors.

Form, WhatsApp, email, referral: each becomes one record with a practice area, a
priority, an owner, a document checklist and a drafted acknowledgement that waits
for a human. Same shape as the prototype, now running as a queue job with the
audit trail and approvals service behind it.
"""

from __future__ import annotations

import json

from ..core.audit import Audit
from ..core.db import Database, now_iso
from ..services.approvals import Approvals
from . import rules

ACK_BODY = """Dear {name},

Thank you for contacting us. Your enquiry has been recorded as {ref} and passed to
our {area} team.

{missing}Kind regards,
Client Services
"""


def ingest(db: Database, enquiry: dict) -> dict:
    audit = Audit(db)
    approvals = Approvals(db)

    text = enquiry.get("message", "")
    area, hits, confidence = rules.classify_area(text)
    urgency_hits = rules.urgency(text)
    language = rules.language_of(text, enquiry.get("language", ""))
    supplied = enquiry.get("documents_supplied", [])
    missing = rules.missing_documents(area, supplied)

    priority = "urgent" if urgency_hits else "normal"
    needs_human = area == "Unassigned" or confidence < 0.6 or language == "ar"
    status = "needs_human" if needs_human else "routed"
    owner = rules.OWNER_BY_AREA.get(area, "Unassigned")

    key = f"intake:{enquiry['id']}"
    if db.one("SELECT 1 FROM enquiries WHERE id = ?", (enquiry["id"],)):
        audit.log("system", "intake_duplicate_skipped", enquiry["id"], "already on file")
        return {"id": enquiry["id"], "outcome": "duplicate"}

    cur = db.execute(
        "INSERT INTO contacts (name, email, phone) VALUES (?,?,?)",
        (enquiry.get("name", "Unknown"), enquiry.get("email", ""), enquiry.get("phone", "")),
    )
    contact_id = int(cur.lastrowid)

    db.execute(
        """INSERT INTO enquiries (id, contact_id, source, received_at, message, language,
            practice_area, priority, after_hours, confidence, needs_human, needs_arabic_review,
            status, owner, documents_supplied, documents_missing, last_activity, idempotency_key)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (enquiry["id"], contact_id, enquiry.get("source", "unknown"),
         enquiry.get("received_at", now_iso()), text, language, area, priority,
         int(enquiry.get("after_hours", 0)), confidence, int(needs_human),
         int(language == "ar"), status, owner, json.dumps(supplied),
         json.dumps(missing), now_iso(), key),
    )

    audit.log("system", "intake_triaged", enquiry["id"],
              f"area={area} priority={priority} confidence={confidence} "
              f"matched={','.join(hits) or 'none'}")
    if needs_human:
        audit.log("system", "escalated_for_human", enquiry["id"],
                  "low confidence, unassigned area, or language review required")

    approval_id = None
    if not needs_human:
        body = ACK_BODY.format(
            name=enquiry.get("name", "Sir/Madam"), ref=enquiry["id"], area=area,
            missing=(f"Before we can open the file we will need: "
                     f"{', '.join(d.replace('_',' ') for d in missing)}.\n\n" if missing else ""),
        )
        approval_id = approvals.create("acknowledgement", enquiry["id"],
                                       f"Re: your enquiry — {enquiry['id']}", body)

    return {
        "id": enquiry["id"],
        "outcome": "recorded",
        "practice_area": area,
        "priority": priority,
        "confidence": confidence,
        "owner": owner,
        "status": status,
        "missing": missing,
        "approval_id": approval_id,
    }
