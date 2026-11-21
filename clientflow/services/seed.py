"""
seed.py — deterministic synthetic data.

Everything here is invented: names, domains, contracts references, campaign names.
Domains use example.ae so no accidental resemblance to a real business is possible.

Deterministic because a demo that changes every run is not evidence. Same seed ->
same folders, same results, same numbers to quote.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from ..core.db import Database, now_iso
from ..workflows import rules

FIRST = ["Rashid", "Faisal", "Noura", "Priya", "Omar", "Layla", "Hassan", "Aisha",
         "Daniel", "Meera", "Yousef", "Sofia", "Karan", "Fatima", "Adel", "Hana"]
LAST = ["Al Mansoori", "Al Zaabi", "Al Hashimi", "Nair", "Haddad", "Rahman", "Khan",
        "Fernandes", "Qureshi", "Bakri", "Saab", "Iqbal"]
CAMPAIGNS = ["Ramadan Retail Push", "Fountain Views Launch", "Q4 Beauty Retargeting",
             "B2B Legal Awareness", "Shopping Festival Search"]

ENQUIRY_MESSAGES = [
    ("contact_form", "We are a UK company looking to set up a branch office in a Dubai free zone and need help with the trade licence."),
    ("whatsapp", "Urgent: a cheque has bounced and the bank is threatening a travel ban. There is a hearing on Thursday."),
    ("email", "My employer ended my contract without notice and has not paid the final salary. What can I claim?"),
    ("email", "Following up on the tenancy dispute — the landlord still has not returned the security deposit."),
    ("contact_form", "We need a shareholders agreement for a new mainland company with two UAE partners."),
    ("referral", "Not urgent, but we would like to review our trademark registration for the GCC."),
    ("whatsapp", "Can you help with a VAT registration question? No rush."),
    ("email", "Our supplier agreement needs a governing law clause. Can you advise?"),
]


def _name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def seed_enquiries(db: Database, rng: random.Random, n: int = 24) -> int:
    created = 0
    for i in range(1, n + 1):
        source, message = rng.choice(ENQUIRY_MESSAGES)
        name = _name(rng)
        slug = name.lower().replace(" ", ".")
        received = (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 12),
                                                           hours=rng.randint(0, 23)))
        cur = db.execute("INSERT INTO contacts (name, email, phone) VALUES (?,?,?)",
                         (name, f"{slug}{i}@example.ae", f"+971 50 000 {1000 + i}"))
        contact_id = int(cur.lastrowid)
        area, hits, conf = rules.classify_area(message)
        urgent = bool(rules.urgency(message))
        lang = rules.language_of(message)
        needs_human = area == "Unassigned" or conf < 0.6
        db.execute(
            """INSERT INTO enquiries (id, contact_id, source, received_at, message, language,
                practice_area, priority, after_hours, confidence, needs_human, needs_arabic_review,
                status, owner, documents_supplied, documents_missing, last_activity, idempotency_key)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"ENQ-{2000 + i}", contact_id, source, received.replace(microsecond=0).isoformat(),
             message, lang, area, "urgent" if urgent else "normal",
             int(received.hour >= 18 or received.hour < 8), conf, int(needs_human), int(lang == "ar"),
             "needs_human" if needs_human else "routed",
             rules.OWNER_BY_AREA.get(area, "Unassigned"), json.dumps([]),
             json.dumps(rules.missing_documents(area, [])),
             received.replace(microsecond=0).isoformat(), f"seed:ENQ-{2000 + i}"),
        )
        created += 1
    return created


def seed_matters(db: Database, rng: random.Random, n: int = 14) -> int:
    areas = [a for a in rules.PRACTICE_KEYWORDS]
    count = 0
    for i in range(1, n + 1):
        area = rng.choice(areas)
        opened = datetime.now(timezone.utc) - timedelta(days=rng.randint(10, 90))
        idle = rng.choice([1, 2, 3, 4, 6, 9, 14, 21])
        last = datetime.now(timezone.utc) - timedelta(days=idle)
        db.execute(
            """INSERT INTO matters (id, client, practice_area, status, opened_at, last_activity, fee_estimate)
               VALUES (?,?,?,?,?,?,?)""",
            (f"MAT-{3000 + i}", _name(rng), area,
             rng.choice(["open", "open", "awaiting_client", "closed"]),
             opened.replace(microsecond=0).isoformat(), last.replace(microsecond=0).isoformat(),
             round(rng.uniform(5_000, 60_000), -2)),
        )
        count += 1
    return count


def seed_documents(db: Database, rng: random.Random) -> int:
    """Eight packs with one deliberate defect each, so every KYC rule fires once."""
    packs = [
        ("MAT-3001", "Corporate & Commercial", ["trade_licence", "passport", "emirates_id", "board_resolution"], None),
        ("MAT-3002", "Corporate & Commercial", ["trade_licence", "emirates_id", "board_resolution"], "missing_passport"),
        ("MAT-3003", "Dispute Resolution", ["emirates_id", "passport", "contract", "cheque_copy"], "expiring_id"),
        ("MAT-3004", "Employment & Labour", ["emirates_id", "passport"], "missing_contract"),
        ("MAT-3005", "Real Estate & Property", ["emirates_id", "passport"], "missing_title_deed"),
        ("MAT-3006", "Banking & Finance", ["emirates_id", "passport"], "missing_financials"),
        ("MAT-3007", "Intellectual Property", ["trade_licence", "emirates_id"], "missing_brand_samples"),
        ("MAT-3008", "Tax & Investment", ["trade_licence", "emirates_id"], "missing_financials"),
    ]
    written = 0
    today = datetime.now(timezone.utc)
    for matter_id, area, supplied, defect in packs:
        for doc_type in supplied:
            expires = None
            if doc_type in ("emirates_id", "passport"):
                days = 11 if (defect == "expiring_id" and doc_type == "emirates_id") else rng.randint(200, 2000)
                expires = (today + timedelta(days=days)).date().isoformat()
            db.execute(
                """INSERT INTO documents (matter_id, doc_type, received_at, verified)
                   VALUES (?,?,?,?)""",
                (matter_id, doc_type, today.replace(microsecond=0).isoformat(), 1),
            )
            written += 1
            if expires:
                db.execute(
                    "INSERT INTO documents (matter_id, doc_type, received_at, verified) VALUES (?,?,?,?)",
                    (matter_id, f"{doc_type}_expiry:{expires}", today.replace(microsecond=0).isoformat(), 1),
                )
    return written


def seed_campaigns(db: Database, rng: random.Random, weeks: int = 6) -> int:
    count = 0
    for campaign in CAMPAIGNS:
        for w in range(weeks):
            spend = round(rng.uniform(1_500, 12_000), -1)
            clicks = int(spend / rng.uniform(2.5, 6.0))
            leads = int(clicks * rng.uniform(0.02, 0.09))
            revenue = 0.0 if campaign == "B2B Legal Awareness" else round(leads * rng.uniform(900, 4_200), -1)
            db.execute(
                """INSERT OR REPLACE INTO campaign_weeks
                   (campaign, week, spend, impressions, clicks, leads, revenue)
                   VALUES (?,?,?,?,?,?,?)""",
                (campaign, f"W{w + 1}", spend, clicks * rng.randint(20, 60), clicks, leads, revenue),
            )
            count += 1
    return count


def seed_candidates(db: Database, rng: random.Random, n: int = 25) -> int:
    skills = ["python", "pandas", "n8n", "webhook", "rest api", "llm", "rag", "sql",
              "postgres", "docker", "javascript", "react", "production", "clients",
              "stakeholder", "documentation", "pytorch", "machine learning"]
    count = 0
    for i in range(1, n + 1):
        chosen = rng.sample(skills, k=rng.randint(3, 10))
        cv = f"Candidate {i}. Experience: {' '.join(chosen)}. Built and deployed systems for clients."
        score, reasons = rules.score_cv(cv)
        db.execute(
            """INSERT INTO candidates (role_ref, name, cv_text, score, reasons, decision, idempotency_key)
               VALUES (?,?,?,?,?,?,?)""",
            ("ROLE-AUTOMATION", _name(rng), cv, score, json.dumps(reasons), "pending", f"seed:cv:{i}"),
        )
        count += 1
    return count


def seed_register(db: Database) -> int:
    entries = [
        ("Intake triage", "Turn enquiries into routed records with an owner and a drafted acknowledgement",
         "Partner — client intake", "Enquiry text, name, email, phone", "Read webhook, write CRM, no document access",
         "Every acknowledgement"),
        ("KYC pack checker", "Compare a document pack against the matter checklist and draft the chase",
         "Paralegal lead", "Document types, holders, expiry dates", "Read matter folder only",
         "Every chase email"),
        ("Clause review", "Flag clause presence and risk items in a contract for a lawyer to review",
         "Legal Director", "Contract text supplied by the reviewer", "No network access, local model only",
         "Nothing sends: output is a report"),
        ("CV triage", "Score inbound CVs against a client rubric and rank for a recruiter",
         "Head of HR", "Candidate CV text", "Read upload folder, write candidate record",
         "Every shortlist"),
        ("Attribution report", "Join campaign spend to leads and revenue and flag spend with no return",
         "Marketing Manager", "Campaign spend, leads, revenue", "Read-only analytics copy",
         "Nothing sends: output is a report"),
    ]
    for entry in entries:
        db.execute(
            """INSERT OR IGNORE INTO systems_register
               (name, purpose, owner, data_touched, permissions, approval_gate)
               VALUES (?,?,?,?,?,?)""",
            entry,
        )
    return len(entries)


def seed_all(db: Database, seed: int = 7) -> dict:
    rng = random.Random(seed)
    counts = {
        "enquiries": seed_enquiries(db, rng),
        "matters": seed_matters(db, rng),
        "documents": seed_documents(db, rng),
        "campaign_weeks": seed_campaigns(db, rng),
        "candidates": seed_candidates(db, rng),
        "register": seed_register(db),
    }
    return counts
