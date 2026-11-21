"""
rules.py — shared domain rules: practice areas, urgency, document checklists.

Deliberately one module, not five copies. Every workflow that classifies a piece
of text (an enquiry, a CV, a matter note) imports from here, so a change to the
firm's practice areas is a one-line change in one place.
"""

from __future__ import annotations

import re

PRACTICE_KEYWORDS: dict[str, list[str]] = {
    "Corporate & Commercial": [
        "company setup", "company formation", "free zone", "trade licence", "trade license",
        "shareholder", "incorporation", "mainland", "branch office", "share transfer",
        "memorandum of association", "moa", "liquidation",
    ],
    "Dispute Resolution": [
        "cheque", "bounced", "dishonoured", "dispute", "arbitration", "claim", "court",
        "judgment", "judgement", "bailiff", "summons", "litigation", "debt collection",
        "execution", "injunction",
    ],
    "Employment & Labour": [
        "employment", "labour", "labor", "salary", "wages", "termination", "resignation",
        "gratuity", "work permit", "visa cancellation", "notice period", "end of service",
        "overtime", "annual leave", "عقد عمل", "راتب", "استقالة",
    ],
    "Banking & Finance": [
        "loan", "facility", "mortgage", "bank account", "finance", "refinance", "lending",
    ],
    "Real Estate & Property": [
        "property", "tenancy", "lease", "landlord", "tenant", "rent", "ejari", "handover",
        "title deed", "service charge",
    ],
    "Family & Personal": [
        "divorce", "custody", "inheritance", "will", "marriage", "guardianship", "maintenance",
    ],
    "Criminal": ["criminal", "arrest", "police case", "fraud", "theft", "complaint filed"],
    "Tax & Investment": [
        "corporate tax", "vat", "tax registration", "investment", "structuring", "excise",
    ],
    "Intellectual Property": [
        "trademark", "copyright", "patent", "brand registration", "ip", "infringement",
    ],
}

# Keyword matching fails on real language in predictable ways. "Not urgent" matching
# "urgent" is the classic one. Strip negations before matching.
NEGATIONS = [
    "not urgent", "no rush", "not an emergency", "not time sensitive", "no urgency",
    "not a complaint", "غير عاجل", "ليس عاجلا",
]

URGENCY_KEYWORDS = [
    "urgent", "hearing", "court date", "deadline", "tomorrow", "today", "bailiff",
    "summons", "injunction", "immediately", "asap", "travel ban", "arrest", "seized",
]

DOCUMENT_CHECKLIST: dict[str, list[str]] = {
    "Corporate & Commercial": ["trade_licence", "passport", "emirates_id", "board_resolution"],
    "Dispute Resolution": ["emirates_id", "passport", "contract", "cheque_copy"],
    "Employment & Labour": ["emirates_id", "passport", "employment_contract"],
    "Real Estate & Property": ["emirates_id", "passport", "title_deed"],
    "Banking & Finance": ["emirates_id", "passport", "financial_statements"],
    "Family & Personal": ["emirates_id", "passport", "marriage_certificate"],
    "Criminal": ["emirates_id", "passport", "police_report"],
    "Tax & Investment": ["trade_licence", "emirates_id", "financial_statements"],
    "Intellectual Property": ["trade_licence", "emirates_id", "brand_samples"],
    "Unassigned": ["emirates_id", "passport"],
}

# Demo routing configuration — not a claim about anyone's real rota.
OWNER_BY_AREA = {
    "Corporate & Commercial": "Legal Director",
    "Dispute Resolution": "Legal Director",
    "Employment & Labour": "Legal Consultant",
    "Banking & Finance": "Legal Director",
    "Real Estate & Property": "Legal Consultant",
    "Family & Personal": "Legal Consultant",
    "Criminal": "In-House Legal Counsel",
    "Tax & Investment": "In-House Legal Counsel",
    "Intellectual Property": "In-House Legal Counsel",
    "Unassigned": "Partner (manual review)",
}

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

# Recruitment rubric: the criteria a recruiter would actually apply.
CV_RUBRIC: list[tuple[str, float, list[str]]] = [
    ("python", 3.0, ["python", "pandas", "numpy", "fastapi", "flask", "django"]),
    ("automation/integration", 3.0, ["n8n", "zapier", "make.com", "webhook", "rest api", "integration", "etl"]),
    ("ai/llm", 2.0, ["llm", "openai", "prompt", "rag", "embedding", "machine learning", "pytorch", "tensorflow"]),
    ("data/sql", 2.0, ["sql", "postgres", "mysql", "sqlite", "database", "bigquery"]),
    ("cloud/devops", 1.0, ["aws", "azure", "gcp", "docker", "kubernetes", "ci/cd"]),
    ("javascript", 1.0, ["javascript", "typescript", "react", "node"]),
    ("commercial evidence", 2.0, ["deployed", "production", "saved", "reduced", "clients", "revenue", "hours"]),
    ("client-facing", 1.0, ["stakeholder", "client", "consult", "training", "documentation"]),
]


def strip_negations(text: str) -> str:
    low = (text or "").lower()
    for phrase in NEGATIONS:
        low = low.replace(phrase, " ")
    return low


def keyword_hits(text: str, terms: list[str]) -> list[str]:
    low = (text or "").lower()
    return [t for t in terms if t in low]


def classify_area(text: str) -> tuple[str, list[str], float]:
    """Return (area, matched terms, confidence).

    A text that matches nothing is NOT guessed into an area. Guessing is the most
    damaging thing this system could do: a misfiled matter is a missed deadline.
    """
    matchable = strip_negations(text)
    best_area, best_hits = "Unassigned", []
    for area, terms in PRACTICE_KEYWORDS.items():
        hits = keyword_hits(matchable, terms)
        if len(hits) > len(best_hits):
            best_area, best_hits = area, hits
    if not best_hits:
        return "Unassigned", [], 0.0
    return best_area, best_hits, round(min(0.95, 0.55 + 0.15 * len(best_hits)), 2)


def urgency(text: str) -> list[str]:
    return keyword_hits(strip_negations(text), URGENCY_KEYWORDS)


def language_of(text: str, declared: str = "") -> str:
    if declared:
        return declared
    return "ar" if ARABIC_RE.search(text or "") else "en"


def missing_documents(area: str, supplied: list[str]) -> list[str]:
    required = DOCUMENT_CHECKLIST.get(area, DOCUMENT_CHECKLIST["Unassigned"])
    supplied = [s.lower() for s in (supplied or [])]
    return [d for d in required if d not in supplied]


def score_cv(cv_text: str) -> tuple[float, list[dict]]:
    """Score a CV against the rubric and return (score, reasons).

    Reasons matter more than the score: a recruiter has to be able to explain to a
    candidate (and to a client) why someone was or was not shortlisted.
    """
    text = (cv_text or "").lower()
    total, weight_sum = 0.0, 0.0
    reasons = []
    for name, weight, terms in CV_RUBRIC:
        hits = [t for t in terms if t in text]
        weight_sum += weight
        awarded = weight if hits else 0.0
        total += awarded
        reasons.append({
            "criterion": name,
            "weight": weight,
            "matched": hits,
            "awarded": awarded,
        })
    score = round(100 * total / weight_sum, 1) if weight_sum else 0.0
    return score, reasons
