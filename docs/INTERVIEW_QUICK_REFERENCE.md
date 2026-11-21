# Quick reference

## Overview
**ClientFlow AI** — group business automation and intelligence platform: six automations for a group spanning
law, recruitment, marketing and e-commerce, with a durable queue, approval gate, append-only audit and a
dashboard. Independent portfolio proof-of-concept; synthetic and public data only.

## Technologies
Python 3.12 standard library (queue, audit, API, dashboard, CLI) · SQLite with numbered migrations ·
scikit-learn + NumPy for the clause model · `http.server` for the API/UI · Docker, Render blueprint, GitHub
Actions CI.

## The six workflows
| # | Workflow | Trigger | AI | Output |
|---|---|---|---|---|
| 1 | Intake triage | queue job `intake` | none (rules) | routed enquiry + acknowledgement draft |
| 2 | KYC pack checker | queue job `kyc` | none (metadata) | completeness report + chase draft |
| 3 | CV triage | queue job `cv_screen` | none (weighted rubric) | shortlist draft |
| 4 | Stalled watchdog | queue job `watchdog` | none | daily digest draft |
| 5 | Campaign attribution | queue job `attribution` | none (arithmetic) | spend vs revenue report |
| 6 | Clause review | API/CLI, synchronous | **TF-IDF + LinearSVC** | review sheet + risk flags |

## Important modules
`core/db.py` schema + migrations · `core/queue.py` retries, backoff, dead letter, atomic claim ·
`core/audit.py` append-only · `core/security.py` redaction, roles, token · `services/worker.py` dispatch ·
`services/approvals.py` human gate · `services/metrics.py` numbers + assumptions · `workflows/rules.py`
practice areas, checklists, rubric · `workflows/clause_*.py` data, model, review.

## API endpoints
Read (localhost): `/health` · `/api/stats` · `/api/enquiries` · `/api/approvals` · `/api/jobs` ·
`/api/register` · `/api/attribution` · `/api/review?idx=N|?text=…`
Write (token): `POST /api/approvals/<id>/decide`

## Database
Ten tables: `contacts`, `matters`, `documents`, `enquiries`, `candidates`, `campaign_weeks`, `jobs`,
`approvals`, `audit_log`, `systems_register`. Unique idempotency keys on `jobs`, `enquiries`, `candidates`.

## Model results and caveats
| Metric | Value |
|---|---|
| Micro F1 (102 held-out contracts) | **0.802** |
| Macro F1 | **0.561** |
| Training time | 13 s |
| Clause location | passage returned for **44%** of findings; **34%** of those agree with the lawyer |
| Corpus | CUAD v1, 510 contracts, 41 categories, CC BY 4.0, US drafting |
Caveats: rare classes near zero; no validation split; no UAE evaluation; location is a pointer, not a citation.

## Demo commands
```powershell
python -m clientflow.cli demo --reset     # seed + run queue + summary
python -m clientflow.cli stats            # numbers a human reads
python -m clientflow.cli run              # process due jobs (run twice: idempotent)
python -m clientflow.cli review 3         # clause review in the terminal
python -m clientflow.cli serve            # dashboard + /?review=3
python -m unittest discover -s tests -t . # 55 tests
```

## Five strongest talking points
1. **No send function exists** — approval is a recorded decision, so client-facing action needs a person.
2. **Idempotency in the schema** — run the queue twice, nothing duplicates.
3. **Honest metrics** — micro 0.80 with macro 0.56 exposed, and location at 22% labelled instead of dressed up.
4. **Three bugs found by auditing** — token variable name, redaction order, "not urgent".
5. **Systems register** — purpose, owner, data touched, permissions, approval gate per automation.

## If asked "what is missing"
SSO and per-user identity · multi-tenant isolation · retention/deletion (PDPL) · alerting on dead letters ·
document chase scheduler · UAE evaluation set for the model · OCR for scanned packs.
