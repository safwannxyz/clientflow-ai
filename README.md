# ClientFlow AI

**Group business automation and intelligence platform** — a portfolio proof-of-concept for an
AI Automation Specialist / AI & Business Systems Engineer role.

> **Independence:** this is a personal portfolio project. It is **not** commissioned by, connected to, or
> endorsed by Altara. No firm data, client information or employee records are used anywhere. All demo
> data is synthetic; the contract texts come from the public CUAD corpus (CC BY 4.0).

---

## What it is

A small platform that runs five automations for a group made of a law firm, a recruitment business, a
marketing agency and e-commerce brands — the four businesses described in the public advert this project
was designed against.

| Layer | What it provides |
|---|---|
| **Core** | SQLite schema with numbered migrations · durable job queue (retries with backoff, dead-letter, atomic claim) · append-only audit log · redaction, roles and API tokens |
| **Workflows** | Intake triage · KYC pack checker · Contract clause review (CUAD) · CV triage with a rubric · Stalled-matter watchdog · Campaign attribution |
| **Human layer** | Every outbound artefact is an approval row. No send function exists anywhere in the codebase |
| **Interface** | Server-rendered dashboard, JSON API, CLI |
| **Proof** | Unit and integration tests, deterministic seed data, honest metrics |

## Quick start

Python 3.10+ and the standard library, plus `scikit-learn` and `numpy` for the clause model.

```bash
pip install scikit-learn numpy

python -m clientflow.cli fetch-cuad     # 39 MB, once
python -m clientflow.cli train          # about 20 seconds
python -m clientflow.cli demo --reset   # seed, run the queue, print a summary
python -m clientflow.cli serve          # dashboard on http://127.0.0.1:8770
```

Then open <http://127.0.0.1:8770/> for the dashboard and
<http://127.0.0.1:8770/?review=3> to watch a contract being reviewed.

## The clause review — the part worth explaining

CUAD is 510 commercial contracts annotated by lawyers across 41 clause categories. The model is
TF-IDF plus One-vs-Rest LinearSVC, split **by contract** so no contract appears on both sides.

Measured on a 408 / 102 split:

| Metric | Value |
|---|---|
| Micro F1 | **0.802** |
| Macro F1 | **0.562** |
| Training time | ~20 seconds on a laptop |

The weak classes are the rare ones (support 2–16) — reported rather than hidden.

**Localisation is a separate, weaker thing, and it says so.** Finding *which para* of the contract contains
a clause turned out to be much harder than finding the clause type. Three attempts, measured against
CUAD's lawyer-annotated spans:

| Attempt | Agreement |
|---|---|
| Vocabulary overlap, 2,500-char blocks | 28% |
| Same, 600-char blocks | 21% |
| TF-IDF retrieval against the CUAD annotation question, 600-char blocks | 32% |

Since 32% is not a citation, the product reports a **candidate passage to verify**, not a clause reference.
That was a deliberate downgrade: a confident wrong clause number costs a reviewer more than no number.

Two deliberate design choices remain:

1. **Presence is a model; location is not.** A transparent scorer finds the clause block containing the
   category's vocabulary, so every finding carries a clause number. "This contract has an unlimited
   liability clause" is useless without "…at clause 14".
2. **Risk items are listed rules**, so a lawyer can disagree with one line rather than with the whole
   system. The output ends with *prepared as a review aid; not legal advice; a lawyer decides.*

## Honest limitations

- Trained on **US** commercial contracts. UAE drafting differs, so this is a triage aid, not an opinion
  on enforceability.
- Text input only — no OCR, so scanned PDFs are a later step.
- 510 contracts is a small training set for 41 labels.
- No queue workers running as a service: `run` processes due jobs once. A scheduler is a deployment
  decision, not a code one.
- No authentication beyond a shared API token on write endpoints; the UI binds to localhost only.
- Hours-saved figures are **estimates** with their basis stated in code — never presented as measurements.

## Deployment

```bash
python scripts/snapshot.py --out dist     # static HTML you can host anywhere
docker build -t clientflow .              # container, one instance by design
```

See `docs/DEPLOY.md`. The two limits worth stating out loud: SQLite plus a file queue does not scale
horizontally, and a public URL is never appropriate for client data without the firm's SSO in front of it.

## Layout

```
clientflow/
  core/        db, queue, audit, security
  workflows/   intake, kyc, clause review (+ CUAD data and model), rules
  services/    approvals, metrics, seed, worker
  api/         JSON API and dashboard
  cli.py       one entry point
docs/          public research, architecture, security, runbook, demo script
tests/         unit and integration tests
```

## Why the pieces are shaped this way

See `docs/ARCHITECTURE.md` for the reasoning, `docs/SECURITY.md` for the confidentiality model,
`docs/adr/` for the three decisions worth arguing about, and `docs/RUNBOOK.md` for what to do when
something breaks.
