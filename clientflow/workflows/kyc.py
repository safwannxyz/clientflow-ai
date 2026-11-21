"""
kyc.py — document pack checker.

What it does: compares a matter's document pack against the checklist for that
matter type, flags what is missing and what is expiring, and drafts the chase for
a human to approve.

What it does NOT do, and says so in its own output: verify authenticity. Whether a
document is genuine is a human judgement. A tool that claims to verify identity
documents is a liability in a law firm; one that checks completeness is an
assistant.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .rules import DOCUMENT_CHECKLIST

EXPIRY_WARNING_DAYS = 30


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None


def check_pack(matter_id: str, area: str, documents: list[dict],
               supplied_types: list[str] | None = None,
               today: date | None = None) -> dict:
    """Return a completeness report for one matter.

    `documents` items: {"type": "passport", "holder": "...", "expires": "2027-04-01"}
    """
    today = today or date.today()
    required = DOCUMENT_CHECKLIST.get(area, DOCUMENT_CHECKLIST["Unassigned"])
    present = {d.get("type", "").lower() for d in documents} | {t.lower() for t in (supplied_types or [])}

    missing = [d for d in required if d not in present]
    expiring, expired = [], []
    for doc in documents:
        exp = _parse_date(doc.get("expires", ""))
        if not exp:
            continue
        delta = (exp - today).days
        if delta < 0:
            expired.append({"type": doc.get("type"), "expires": exp.isoformat(), "days": delta})
        elif delta <= EXPIRY_WARNING_DAYS:
            expiring.append({"type": doc.get("type"), "expires": exp.isoformat(), "days": delta})

    holders = {str(d.get("holder", "")).strip().lower() for d in documents if d.get("holder")}
    name_mismatch = len(holders) > 1

    issues = []
    if missing:
        issues.append(f"missing: {', '.join(missing)}")
    if expired:
        issues.append("expired: " + ", ".join(e["type"] for e in expired))
    if expiring:
        issues.append("expiring within %d days: " % EXPIRY_WARNING_DAYS +
                      ", ".join(e["type"] for e in expiring))
    if name_mismatch:
        issues.append("holder names differ across documents")

    return {
        "matter_id": matter_id,
        "practice_area": area,
        "required": required,
        "present": sorted(present & set(required)),
        "missing": missing,
        "expiring": expiring,
        "expired": expired,
        "name_mismatch": name_mismatch,
        "holders": sorted(holders),
        "complete": not (missing or expired or expiring or name_mismatch),
        "issues": issues,
        "note": ("Completeness only. Authenticity and legal sufficiency are for a "
                 "qualified person to confirm."),
    }


def chase_email(report: dict, client_name: str = "Sir/Madam") -> dict:
    """The draft that goes to the approval queue — never sent by the system."""
    lines = []
    if report["missing"]:
        lines.append("We still need: " + ", ".join(d.replace("_", " ") for d in report["missing"]) + ".")
    for item in report["expired"]:
        lines.append(f"The {item['type'].replace('_',' ')} on file expired on {item['expires']}.")
    for item in report["expiring"]:
        lines.append(f"The {item['type'].replace('_',' ')} expires on {item['expires']} "
                     f"({item['days']} days).")
    if report["name_mismatch"]:
        lines.append("The names on the documents do not match; please confirm the correct "
                      "legal name.")

    body = (f"Dear {client_name},\n\nRegarding matter {report['matter_id']}, to progress "
            f"the file we need the following:\n\n"
            + "\n".join(f"  - {line}" for line in lines)
            + "\n\nKind regards,\nClient Services\n")
    return {
        "kind": "kyc_chase",
        "entity": report["matter_id"],
        "subject": f"Documents needed to progress {report['matter_id']}",
        "body": body,
    }
