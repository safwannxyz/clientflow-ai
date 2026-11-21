"""
clause_review.py — turn a contract into a review sheet a lawyer can use.

Three stages, kept separate on purpose so each can be argued about on its own:

  1. PRESENCE   trained model (clause_model) says which of the 41 CUAD clause
                categories this contract contains. A triage signal, not an opinion.
  2. LOCALISE   a transparent scorer finds the clause block that best matches the
                category, so every finding carries a clause number the reader can
                turn to. No model involved — this is text matching you can inspect.
  3. RISK       explicit, listed rules that flag the things a corporate reviewer
                looks for first. Rules are readable, so a lawyer can disagree with
                a specific line rather than with the whole system.

Nothing here advises. The output ends with the sentence that matters: prepared for
review, a lawyer decides.
"""

from __future__ import annotations

import re
from functools import lru_cache

from . import clause_model
from .clause_data import split_clauses

STOPWORDS = {"with", "that", "this", "from", "into", "than", "then", "they", "their",
             "shall", "such", "have", "been", "were", "will", "which", "under", "upon",
             "each", "other", "more", "less", "not", "and", "for", "the", "any", "all"}

# "governing law" as a phrase is often absent; contracts usually say "governed by
# the laws of ...". Matching only the literal phrase produced false "missing clause"
# findings on contracts that clearly had one — found by running it on real files.
GOVERNING_LAW_RE = re.compile(
    r"(governing law|governed by[^.]{0,160}|laws of[^.]{0,120}|exclusive jurisdiction[^.]{0,160})",
    re.I,
)
NONCOMPETE_RE = re.compile(r"non[- ]compet\w*[^.]{0,300}", re.I)
MONTHS_RE = re.compile(r"(\d{1,2})\s*(month|months|year|years)", re.I)


@lru_cache(maxsize=1)
def _bundle() -> dict:
    return clause_model.load()


def _category_tokens(category: str) -> list[str]:
    words = re.findall(r"[a-z]{4,}", category.lower())
    return [w for w in words if w not in STOPWORDS]


def _best_clause(category: str, clauses: list[dict]) -> tuple[int | None, float, str]:
    """Score clauses by how much of the category's vocabulary they contain."""
    tokens = _category_tokens(category)
    if not tokens:
        return None, 0.0, ""
    best_no, best_score, best_text = None, 0.0, ""
    for block in clauses:
        low = block["text"].lower()
        hits = sum(1 for t in tokens if t in low)
        score = hits / len(tokens)
        if score > best_score:
            best_no, best_score, best_text = int(block["clause_no"]), score, block["text"].strip()
    return best_no, round(best_score, 2), best_text[:400]


def risk_flags(text: str, clauses: list[dict]) -> list[dict]:
    """Listed checks. Each returns evidence, not just a verdict."""
    low = text.lower()
    flags: list[dict] = []

    def add(name: str, severity: str, detail: str, evidence: str = "") -> None:
        flags.append({"check": name, "severity": severity, "detail": detail,
                      "evidence": evidence[:300]})

    # liability cap
    if "unlimited liability" in low or "without limitation of liability" in low:
        m = re.search(r"unlimited liabilit\w*[^.]{0,200}", text, re.I)
        add("Unlimited liability", "high",
            "The contract appears to expose a party to unlimited liability.",
            m.group(0) if m else "")
    elif "cap on liability" not in low and "limitation of liability" not in low:
        add("No liability cap found", "high",
            "No limitation-of-liability language was detected. Absence is a finding, "
            "and one a reviewer should confirm by reading the document.")

    # auto renewal
    if re.search(r"automatically renew|auto-?renew|automatically extend", low):
        m = re.search(r"[^.]*automatic\w*[^.]{0,200}", text, re.I)
        add("Automatic renewal", "medium",
            "The term may renew without a positive act from the client.",
            m.group(0) if m else "")

    # unilateral termination
    if re.search(r"terminate[^.]{0,120}for convenience|terminate[^.]{0,120}without cause", low):
        m = re.search(r"[^.]*terminat\w*[^.]{0,200}", text, re.I)
        add("Termination for convenience", "medium",
            "One party may exit without cause — confirm notice period and consequences.",
            m.group(0) if m else "")

    # governing law / jurisdiction
    law = GOVERNING_LAW_RE.search(text)
    if law:
        snippet = law.group(0)
        if not re.search(r"uae|united arab emirates|dubai|difc|adgm", snippet, re.I):
            add("Governing law outside the UAE", "medium",
                "Governing law is not UAE, DIFC or ADGM — cross-border enforcement "
                "consequences should be confirmed by a lawyer.", snippet)
    else:
        add("No governing law clause found", "medium",
            "No governing-law provision was located in the text supplied.")

    # non-compete duration
    nc = NONCOMPETE_RE.search(text)
    if nc:
        span = nc.group(0)
        months = MONTHS_RE.search(span)
        if months:
            n = int(months.group(1))
            in_months = n * 12 if months.group(2).lower().startswith("year") else n
            if in_months > 12:
                add("Restrictive covenant over 12 months", "medium",
                    f"Non-compete appears to run for about {in_months} months.", span)
        else:
            add("Restrictive covenant with unclear duration", "low",
                "A non-compete clause exists but its duration was not parsed.", span)

    # assignment
    if re.search(r"may not assign|shall not assign|consent[^.]{0,80}assign", low):
        m = re.search(r"[^.]*assign\w*[^.]{0,150}", text, re.I)
        add("Assignment restricted", "low",
            "Assignment needs consent — relevant on any change of control.",
            m.group(0) if m else "")

    return flags


def review(contract_text: str, title: str = "Untitled contract") -> dict:
    """Produce the review sheet. Pure function: same input, same output."""
    bundle = _bundle()
    clauses = split_clauses(contract_text)
    present = clause_model.predict_present(bundle, contract_text)

    findings = []
    for item in present:
        clause_no, match_score, snippet = _best_clause(item["category"], clauses)
        findings.append({
            "category": item["category"],
            "score": item["score"],
            "clause_no": clause_no,
            "match": match_score,
            "excerpt": " ".join(snippet.split())[:260],
        })

    flags = risk_flags(contract_text, clauses)

    key_categories = ["Governing Law", "Cap On Liability", "Termination For Convenience",
                      "Anti-Assignment", "Non-Compete", "Expiration Date", "Renewal Term"]
    found = {f["category"] for f in findings}
    absent_key = [c for c in key_categories if c not in found]

    return {
        "title": title,
        "clauses_detected": len(clauses),
        "characters": len(contract_text),
        "findings": findings,
        "key_clauses_absent": absent_key,
        "risk_flags": flags,
        "disclaimer": ("Prepared as a review aid from a trained model and listed rules. "
                       "Not legal advice. A qualified lawyer decides."),
    }
