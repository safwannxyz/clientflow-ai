# Architecture

## The shape of it

```
                    ┌─────────────────────────────────────────────┐
   form / WhatsApp  │  workflows/                                 │
   email / referral │   intake.py      rules.py                   │
   contracts ──────►│   kyc.py         clause_data/model/review   │
   CVs              │                                             │
   spend + revenue  │  each returns a small dict, nothing else    │
                    └───────────────┬─────────────────────────────┘
                                    │  writes only via core
                    ┌───────────────▼─────────────────────────────┐
                    │  core/   db · queue · audit · security       │
                    │          SQLite, retries, append-only log    │
                    └───────────────┬─────────────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────────────┐
                    │  services/  approvals · metrics · seed       │
                    │             worker (dispatch by job kind)    │
                    └───────────────┬─────────────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────────────┐
                    │  api/server.py   dashboard + JSON API        │
                    │  cli.py          commands for humans         │
                    └─────────────────────────────────────────────┘
```

## Why a queue in a project this size

Because the failure mode of a script is that nobody notices it stopped. A queue gives retries with
backoff, a dead-letter state that appears on the dashboard, and a backlog number that is a health signal
rather than a guess. It also forces the workflows to be pure-ish functions of (payload, db), which is
what makes them testable.

The claim mechanism is one `UPDATE ... WHERE id IN (SELECT ...)` inside `BEGIN IMMEDIATE`, which is the
same idea as `FOR UPDATE SKIP LOCKED` using the primitives SQLite actually has. Two workers cannot claim
the same job; there is a test for it.

## Why SQLite

One file, no server, no ops. A group with one part-time developer cannot run Postgres plus a scheduler
plus monitoring, and pretending otherwise is how these projects die. The schema is written so the move
to Postgres is a connection string and a few type swaps, not a rewrite:
- no SQLite-specific SQL beyond `INSERT OR IGNORE`
- timestamps are ISO-8601 text, which sorts correctly everywhere
- migrations are numbered and applied in order

## Why the workflows are thin

Every workflow does three things: read its payload, ask the rules or model a question, then write through
`core`. It never owns retry logic, never writes its own audit lines by hand, never sends anything. That
keeps a new automation to about eighty lines and makes the security story uniform rather than
per-workflow.

## The three data flows

**1. Enquiry → decision.** Enquiry arrives → queue job → triage (rules) → row in `enquiries` → approval
row if the system is confident enough to draft → human decides → audit.

**2. Matter → chase.** Matter has a document pack → pack checked against the checklist → missing,
expiring, mismatched → chase draft in the approval queue. Never sent.

**3. Contract → review sheet.** Text in → model says which of 41 clause types are present → a transparent
scorer finds the clause block → risk rules add listed findings → report out, with a disclaimer attached
to the object itself so no caller can forget it.

## Where a model is and is not used

| Task | Method | Why |
|---|---|---|
| Clause presence | TF-IDF + LinearSVC | Offline, deterministic, coefficients inspectable, evaluated on a real corpus |
| Clause location | Vocabulary scoring over clause blocks | A citation must be checkable by a human; a model that "feels" which clause is right cannot be checked |
| Practice area | Keyword rules | Auditable; a misfiled matter is worse than an unfiled one |
| CV scoring | Explicit weighted rubric | A rejected candidate must be explainable |
| Risk items | Listed regex rules | A lawyer must be able to disagree with one line |

## What is deliberately missing

Scheduler/daemon (deployment decision) · real CRM/email/DMS connectors (need credentials and a data
agreement) · OCR (a later edge step) · authentication beyond a shared write token (requires the firm's
SSO) · horizontal scaling (nothing here needs it yet).
