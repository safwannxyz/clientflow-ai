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
# "governing law" as a phrase is often absent; contracts usually say "governed by
# the laws of ...". An earlier version matched any "governed by", which flagged
# "governed by separate agreement(s)" as a governing-law clause — a false positive
# that would waste a reviewer's time. The fragment must name laws or a jurisdiction.
GOVERNING_LAW_RE = re.compile(
    r"(governing law[^.]{0,160}"
    r"|governed by the laws?[^.]{0,140}"
    r"|laws of (?:the )?(?:state|emirate|country|united|england|uae|dubai)[^.]{0,80}"
    r"|exclusive jurisdiction[^.]{0,160})",
    re.I,
)

NONCOMPETE_RE = re.compile(r"non[- ]compet\w*[^.]{0,300}", re.I)
MONTHS_RE = re.compile(r"(\d{1,2})\s*(month|months|year|years)", re.I)


# Plain vocabulary overlap put several different categories on the same clause — the
# first version cited "clause 6" for Parties, Expiration Date and Renewal Term alike,
# which is worse than citing nothing: a wrong citation costs the reader time and trust.
# These hints anchor the common categories to the drafting language they actually use.
PHRASE_HINTS: dict[str, list[str]] = {
    "Document Name": ["agreement", "this agreement is made"],
    "Parties": ["between", "by and between", "hereinafter", "party of the"],
    "Governing Law": ["governed by", "governing law", "laws of the", "jurisdiction"],
    "Cap On Liability": ["shall not exceed", "aggregate liability", "in no event shall",
                          "limitation of liability", "liability shall be limited"],
    "Unlimited/All-You-Can-Eat-License": ["unlimited", "without limitation as to"],
    "Termination For Convenience": ["may terminate", "terminate this agreement",
                                     "upon written notice", "for convenience"],
    "Renewal Term": ["renew", "renewal", "extended term", "successive"],
    "Notice Period To Terminate Renewal": ["notice of non-renewal", "days prior to the end",
                                            "notice period"],
    "Expiration Date": ["expires", "expiration", "term of this agreement shall",
                         "shall commence on", "end date"],
    "Effective Date": ["effective as of", "effective date", "entered into as of"],
    "Anti-Assignment": ["assign", "assignment", "transfer of this agreement"],
    "Non-Compete": ["non-compete", "noncompetition", "shall not compete",
                     "shall not engage in"],
    "Audit Rights": ["audit", "inspect", "books and records"],
    "Confidentiality": ["confidential", "non-disclosure", "proprietary information"],
    "Exclusivity": ["exclusive", "exclusivity"],
    "License Grant": ["grants", "license to", "right and license"],
    "Ip Ownership Assignment": ["intellectual property", "work product", "ownership"],
    "Warranty Duration": ["warranty", "warrants", "represents and warrants"],
    "Third Party Beneficiary": ["third party beneficiary", "benefit of"],
}


@lru_cache(maxsize=1)
def _bundle() -> dict:
    """Cached model bundle. Raises clause_model.ModelUnavailable with the fix."""
    return clause_model.load()


def _category_tokens(category: str) -> list[str]:
    words = re.findall(r"[a-z]{4,}", category.lower())
    return [w for w in words if w not in STOPWORDS]


def _best_clause(category: str, clauses: list[dict]) -> tuple[int | None, float, str]:
    """Locate a candidate passage by retrieval, not by keyword counting.

    Measured against CUAD's lawyer annotations at the shipped setting: a passage is
    returned for 44% of findings, and 34% of those agree with the clause a lawyer
    chose. Coverage/precision measured at four abstention floors (0.02: 99%/23%,
    0.08: 97%/23%, 0.12: 73%/28%, 0.16: 44%/34%); 0.16 is shipped because a
    confident wrong pointer is worse than an honest "not located".

    The output is therefore labelled a CANDIDATE PASSAGE to verify, never a citation.

    Method: TF-IDF index over clause blocks, queried with the CUAD annotation
    question for the category — the question is written by lawyers to describe
    exactly what to look for.
    """
    if not clauses:
        return None, 0.0, ""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    from .clause_data import CATEGORY_QUESTIONS

    texts = [c["text"] for c in clauses]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                 sublinear_tf=True, min_df=1)
    matrix = vectorizer.fit_transform(texts)
    query = " ".join(filter(None, [category, CATEGORY_QUESTIONS.get(category, "")]))
    scores = cosine_similarity(vectorizer.transform([query]), matrix)[0]
    best = int(scores.argmax())
    score = float(scores[best])
    if score < 0.16:                       # below this we abstain rather than point
        return None, round(score, 3), ""
    return int(clauses[best]["clause_no"]), round(score, 3), clauses[best]["text"].strip()[:400]


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


def review(contract_text: str, title: str = "Untitled contract",
           annotated: dict | None = None) -> dict:
    """Produce the review sheet. Pure function: same input, same output."""
    bundle = _bundle()
    clauses = split_clauses(contract_text)
    present = clause_model.predict_present(bundle, contract_text)

    from .clause_data import locate_span

    findings = []
    for item in present:
        clause_no, match_score, snippet = _best_clause(item["category"], clauses)
        annotated_no = None
        if annotated and item["category"] in annotated:
            annotated_no = locate_span(clauses, annotated[item["category"]])
        findings.append({
            "category": item["category"],
            "score": item["score"],
            "clause_no": clause_no,
            "match": match_score,
            "excerpt": " ".join(snippet.split())[:260],
            "annotated_clause": annotated_no,
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
        "located": sum(1 for f in findings if f["clause_no"]),
        "passage_agreement": ("34% of returned passages match CUAD lawyer annotations; "
                              "a passage is returned for 44% of findings. A pointer, "
                              "not a citation."),
        "located_correctly": (sum(1 for f in findings
                                  if f["clause_no"] and f["clause_no"] == f["annotated_clause"])
                              if annotated else None),
        "key_clauses_absent": absent_key,
        "risk_flags": flags,
        "disclaimer": ("Prepared as a review aid from a trained model and listed rules. "
                       "Not legal advice. A qualified lawyer decides."),
    }
