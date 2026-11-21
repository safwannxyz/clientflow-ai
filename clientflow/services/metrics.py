"""
metrics.py — the numbers on the dashboard, and the honesty to label them.

The advert this platform was designed against measures success in hours of
repetitive work eliminated, missed follow-ups, response times, reporting accuracy,
adoption and attributable revenue. Those are the six sections below.

Anything derived from an assumption rather than a measurement is returned with
`assumption: True` and the basis spelled out, so nobody can quote an estimate as
if it were a fact.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core.db import Database, now_iso
from ..core.queue import Queue

# Stated once, used everywhere. Changing these changes the headline number, which
# is exactly why they live in code and not in a slide.
ASSUMED_MINUTES = {
    "enquiry_triage": 6,      # read, decide area, route, acknowledge
    "document_chase": 12,     # assemble missing list and write the chase
    "cv_screen": 9,           # first-pass screen per CV
    "report_assembly": 45,    # one weekly management report
}


def overview(db: Database) -> dict:
    q = Queue(db)

    enquiry_status = {r["status"]: int(r["c"]) for r in db.q(
        "SELECT status, COUNT(*) c FROM enquiries GROUP BY status")}
    by_area = [dict(r) for r in db.q(
        "SELECT practice_area, COUNT(*) c FROM enquiries GROUP BY practice_area ORDER BY c DESC")]
    priority = {r["priority"]: int(r["c"]) for r in db.q(
        "SELECT priority, COUNT(*) c FROM enquiries GROUP BY priority")}

    approvals = {r["status"]: int(r["c"]) for r in db.q(
        "SELECT status, COUNT(*) c FROM approvals GROUP BY status")}
    jobs = q.stats()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=5)).replace(microsecond=0).isoformat()
    stale = db.scalar(
        "SELECT COUNT(*) FROM matters WHERE status IN ('open','awaiting_client') "
        "AND last_activity < ?", (cutoff,)) or 0

    return {
        "generated_at": now_iso(),
        "enquiries": {"total": sum(enquiry_status.values()), "by_status": enquiry_status,
                      "by_area": by_area, "by_priority": priority},
        "approvals": {"pending": approvals.get("pending", 0),
                      "approved": approvals.get("approved", 0),
                      "rejected": approvals.get("rejected", 0)},
        "queue": jobs,
        "matters": {"stalled": int(stale)},
    }


def hours_saved(db: Database) -> dict:
    """Estimate, clearly labelled as one, built from counted actions."""
    enquiries = int(db.scalar("SELECT COUNT(*) FROM enquiries") or 0)
    approved = int(db.scalar("SELECT COUNT(*) FROM approvals WHERE status='approved'") or 0)
    candidates = int(db.scalar("SELECT COUNT(*) FROM candidates") or 0)
    reports = int(db.scalar("SELECT COUNT(*) FROM audit_log WHERE action='report_built'") or 0)

    minutes = (enquiries * ASSUMED_MINUTES["enquiry_triage"]
               + approved * ASSUMED_MINUTES["document_chase"]
               + candidates * ASSUMED_MINUTES["cv_screen"]
               + reports * ASSUMED_MINUTES["report_assembly"])
    return {
        "minutes": minutes,
        "hours": round(minutes / 60, 1),
        "assumption": True,
        "basis": ASSUMED_MINUTES,
        "counts": {"enquiries": enquiries, "approved_actions": approved,
                   "candidates_screened": candidates, "reports": reports},
        "note": ("An estimate built from counted actions multiplied by stated allowances. "
                 "The measured version needs a two-week baseline of real times, which is "
                 "the first thing to instrument in a live deployment."),
    }


def attribution(db: Database) -> dict:
    """Spend vs revenue per campaign — the question Altara Social asks publicly."""
    rows = [dict(r) for r in db.q(
        """SELECT campaign,
                  SUM(spend) spend, SUM(impressions) impressions, SUM(clicks) clicks,
                  SUM(leads) leads, SUM(revenue) revenue
           FROM campaign_weeks GROUP BY campaign ORDER BY revenue DESC""")]
    out = []
    for r in rows:
        spend, leads, revenue = r["spend"] or 0, r["leads"] or 0, r["revenue"] or 0
        out.append({
            "campaign": r["campaign"],
            "spend": round(spend, 2),
            "leads": leads,
            "revenue": round(revenue, 2),
            "cost_per_lead": round(spend / leads, 2) if leads else None,
            "roas": round(revenue / spend, 2) if spend else None,
            "flag": "no revenue" if revenue == 0 and spend > 0 else
                    ("no leads" if leads == 0 and spend > 0 else ""),
        })
    wasted = sum(o["spend"] for o in out if o["flag"])
    return {"campaigns": out, "spend_with_no_return": round(wasted, 2)}


def findings(db: Database) -> list[str]:
    """Plain sentences for the top of a report. A partner reads sentences, not JSON."""
    ov = overview(db)
    hs = hours_saved(db)
    at = attribution(db)
    lines = []
    if ov["approvals"]["pending"]:
        lines.append(f"{ov['approvals']['pending']} drafts are waiting for a human decision.")
    if ov["matters"]["stalled"]:
        lines.append(f"{ov['matters']['stalled']} matters have had no activity for over five days.")
    if at["spend_with_no_return"]:
        lines.append(f"AED {at['spend_with_no_return']:,.0f} of campaign spend has produced no revenue.")
    lines.append(f"Estimated {hs['hours']} hours of repetitive work replaced (assumption-based).")
    return lines
