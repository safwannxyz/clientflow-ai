"""
worker.py — the loop that turns queued jobs into outcomes.

Handlers are registered by name, so adding an automation means adding a function
and a line in HANDLERS. Each handler receives (db, payload) and returns a small
result dict; anything it raises is caught, recorded and retried by the queue.

That separation is the whole trick: a workflow author never writes retry logic,
and the platform never contains business logic.
"""

from __future__ import annotations

import json

from ..core.audit import Audit
from ..core.db import Database
from ..core.queue import Queue
from ..workflows import kyc as kyc_wf
from ..workflows import rules
from ..workflows.intake import ingest as intake_ingest
from ..services.approvals import Approvals


def handle_intake(db: Database, payload: dict) -> dict:
    return intake_ingest(db, payload)


def handle_kyc(db: Database, payload: dict) -> dict:
    approvals = Approvals(db)
    audit = Audit(db)
    docs = []
    for row in db.q("SELECT doc_type, received_at FROM documents WHERE matter_id = ?",
                    (payload["matter_id"],)):
        doc_type = row["doc_type"]
        if doc_type.startswith(("emirates_id_expiry:", "passport_expiry:")):
            base_type, expiry = doc_type.split(":", 1)
            docs = [d for d in docs if d["type"] != base_type.replace("_expiry", "")]
            docs.append({"type": base_type.replace("_expiry", ""), "expires": expiry})
        else:
            docs.append({"type": doc_type})
    report = kyc_wf.check_pack(payload["matter_id"], payload["practice_area"], docs)
    audit.log("system", "kyc_checked", payload["matter_id"],
              f"missing={len(report['missing'])} expiring={len(report['expiring'])}")

    approval_id = None
    if not report["complete"]:
        draft = kyc_wf.chase_email(report, payload.get("client_name", "Sir/Madam"))
        approval_id = approvals.create(draft["kind"], draft["entity"], draft["subject"], draft["body"])
    return {"matter_id": payload["matter_id"], "complete": report["complete"],
            "issues": report["issues"], "approval_id": approval_id}


def handle_cv(db: Database, payload: dict) -> dict:
    approvals = Approvals(db)
    audit = Audit(db)
    candidates = [dict(r) for r in db.q(
        "SELECT id, name, cv_text FROM candidates WHERE decision='pending'")]
    if not candidates:
        return {"screened": 0}
    scored = []
    for c in candidates:
        score, reasons = rules.score_cv(c["cv_text"])
        db.execute("UPDATE candidates SET score=?, reasons=? WHERE id=?",
                   (score, json.dumps(reasons), c["id"]))
        scored.append({"id": c["id"], "name": c["name"], "score": score})
    scored.sort(key=lambda d: -d["score"])
    top = scored[: max(3, len(scored) // 3)]
    body = "Shortlist prepared for review\n\n" + "\n".join(
        f"  - {c['name']}: {c['score']}" for c in top)
    approval_id = approvals.create("shortlist", payload.get("role_ref", "ROLE"),
                                   "Shortlist recommendation", body)
    audit.log("system", "cv_shortlist_built", payload.get("role_ref", "ROLE"),
              f"{len(scored)} screened, {len(top)} proposed")
    return {"screened": len(scored), "shortlisted": len(top), "approval_id": approval_id}


def handle_watchdog(db: Database, payload: dict) -> dict:
    approvals = Approvals(db)
    audit = Audit(db)
    rows = db.q(
        """SELECT id, client, practice_area, last_activity FROM matters
           WHERE status IN ('open','awaiting_client') AND last_activity <
             datetime('now','-5 days') ORDER BY last_activity""")
    stale = [dict(r) for r in rows]
    if stale:
        body = "Matters with no activity for 5+ days\n\n" + "\n".join(
            f"  - {s['id']} · {s['practice_area']} · last activity {s['last_activity'][:10]}"
            for s in stale)
        approvals.create("watchdog", "matters", "Stalled matters — daily digest", body)
    audit.log("system", "watchdog_ran", "matters", f"{len(stale)} stalled matters found")
    return {"stalled": len(stale)}


def handle_attribution(db: Database, payload: dict) -> dict:
    from .metrics import attribution
    audit = Audit(db)
    data = attribution(db)
    flagged = [c for c in data["campaigns"] if c["flag"]]
    audit.log("system", "report_built", "campaigns",
              f"{len(data['campaigns'])} campaigns, {len(flagged)} flagged, "
              f"AED {data['spend_with_no_return']:.0f} with no return")
    return {"campaigns": len(data["campaigns"]), "flagged": len(flagged),
            "spend_with_no_return": data["spend_with_no_return"]}


HANDLERS = {
    "intake": handle_intake,
    "kyc": handle_kyc,
    "cv_screen": handle_cv,
    "watchdog": handle_watchdog,
    "attribution": handle_attribution,
}


def run_once(db: Database, worker_id: str = "worker-1", limit: int = 20) -> dict:
    """Claim and process due jobs once. Returns a small run report."""
    queue = Queue(db)
    audit = Audit(db)
    processed, failed = 0, 0
    for job in queue.claim(worker_id, limit=limit):
        handler = HANDLERS.get(job["kind"])
        try:
            if handler is None:
                raise KeyError(f"no handler registered for kind '{job['kind']}'")
            result = handler(db, json.loads(job["payload"]))
            queue.complete(job["id"], result)
            audit.log(f"worker:{worker_id}", "job_done", job["id"],
                      f"{job['kind']} -> {result}")
            processed += 1
        except Exception as exc:  # noqa: BLE001 - recorded, then retried or dead-lettered
            state = queue.fail(job["id"], f"{type(exc).__name__}: {exc}")
            audit.log(f"worker:{worker_id}", "job_failed", job["id"],
                      f"{job['kind']} -> {state}: {exc}")
            failed += 1
    return {"processed": processed, "failed": failed, "queue": queue.stats()}


def run_until_empty(db: Database, worker_id: str = "worker-1", max_batches: int = 20) -> dict:
    total, failures = 0, 0
    for _ in range(max_batches):
        report = run_once(db, worker_id)
        total += report["processed"]
        failures += report["failed"]
        if report["processed"] == 0 and report["failed"] == 0:
            break
    return {"processed": total, "failed": failures}
