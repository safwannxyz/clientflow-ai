"""
clause_data.py — turn CUAD into a training set we can actually reason about.

CUAD's shape (verified against the file):
    data[i]["title"]          contract name
    data[i]["paragraphs"][0]["context"]   the full contract text
    data[i]["paragraphs"][0]["qas"][j]    one entry per clause category
        qas[j]["id"]          "<title>__<Category>"
        qas[j]["question"]    "Highlight the parts (if any) ... related to "<Category>" ..."
        qas[j]["answers"]     [] when the clause is absent (is_impossible = true)
        qas[j]["answers"][0]  {"text": <span>, "answer_start": <int>}

Two different jobs come out of that:

  1. PRESENCE  — does this contract contain clause type X?  (510 x 41 binary labels)
  2. LOCALISE  — where in the contract is it?               (char offset -> paragraph)

The CLI in this project reports metrics for job 1 and uses job 2 to give every
finding a paragraph number, because "the contract has an unlimited liability
clause" is useless to a lawyer without "…at paragraph 14.2".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cuad" / "CUAD_v1.json"


# The CUAD annotation question for each category doubles as a retrieval query —
# better than guessing vocabulary ("Highlight the parts ... related to 'Cap On
# Liability' ... Details: the maximum amount payable").
CATEGORY_QUESTIONS: dict[str, str] = {}


@dataclass
class ClauseDoc:
    title: str
    text: str
    labels: dict[str, int]          # category -> 1/0
    spans: dict[str, tuple[int, int]]  # category -> (start, end) of first answer


def load_cuad(path: Path | str = DATA_PATH) -> list[ClauseDoc]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    docs: list[ClauseDoc] = []
    for entry in raw["data"]:
        paragraph = entry["paragraphs"][0]
        text = paragraph["context"]
        labels: dict[str, int] = {}
        spans: dict[str, tuple[int, int]] = {}
        for qa in paragraph["qas"]:
            category = qa["id"].split("__", 1)[-1]
            CATEGORY_QUESTIONS.setdefault(category, qa.get("question", ""))
            answers = qa.get("answers") or []
            labels[category] = 1 if answers else 0
            if answers:
                start = int(answers[0]["answer_start"])
                spans[category] = (start, start + len(answers[0]["text"]))
        docs.append(ClauseDoc(entry["title"], text, labels, spans))
    return docs


def categories(docs: list[ClauseDoc]) -> list[str]:
    seen: list[str] = []
    for doc in docs:
        for cat in doc.labels:
            if cat not in seen:
                seen.append(cat)
    return sorted(seen)


# ---- splitting a contract into numbered clauses ----------------------------
CLAUSE_NUMBER_RE = re.compile(r"(?m)^\s*(?:\d+(?:\.\d+)*|[IVXLC]+\.|\([a-z]\))\s+")


def split_clauses(text: str, min_chars: int = 120, max_chars: int = 600) -> list[dict]:
    """Split a contract into clause-ish blocks with their character offsets.

    Contracts in CUAD are inconsistently formatted, so this is deliberately
    forgiving: cut at clause numbers when they exist, otherwise at blank lines,
    then split anything too long at sentence boundaries. The offsets are carried
    through, which is what lets every finding point back at the source.

    max_chars matters more than it looks. At 2,500 a "clause" covered half a
    contract and localisation was only right 28% of the time against CUAD's lawyer
    annotations; tighter blocks give the scorer something to actually discriminate
    between.
    """
    cuts = [m.start() for m in CLAUSE_NUMBER_RE.finditer(text)]
    if len(cuts) < 3:
        cuts = [m.start() for m in re.finditer(r"\n\s*\n", text)]

    boundaries = [0] + cuts + [len(text)]
    blocks: list[dict] = []
    for start, end in zip(boundaries, boundaries[1:]):
        chunk = text[start:end]
        if not chunk.strip():
            continue
        if blocks and len(chunk) < min_chars:
            blocks[-1]["text"] += chunk
            blocks[-1]["end"] = end
            continue
        blocks.append({"start": start, "end": end, "text": chunk})

    # split over-long blocks on sentence boundaries
    out: list[dict] = []
    for block in blocks:
        if len(block["text"]) <= max_chars:
            out.append(block)
            continue
        cursor = block["start"]
        sentences = re.split(r"(?<=[.;])\s+", block["text"])
        buffer, buf_start = "", cursor
        for sentence in sentences:
            if len(buffer) + len(sentence) > max_chars and buffer:
                out.append({"start": buf_start, "end": buf_start + len(buffer), "text": buffer})
                buf_start = buf_start + len(buffer)
                buffer = ""
            buffer += sentence
        if buffer:
            out.append({"start": buf_start, "end": buf_start + len(buffer), "text": buffer})

    for i, block in enumerate(out, start=1):
        block["clause_no"] = i
    return out


def locate_span(clauses: list[dict], span: tuple[int, int]) -> int | None:
    """Which clause contains this character span?"""
    start, _ = span
    for block in clauses:
        if block["start"] <= start < block["end"]:
            return int(block["clause_no"])
    return None
