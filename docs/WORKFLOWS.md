# The six workflows, traced to source

Line references are to the files as committed at `1812149` + docs. Every claim here was checked against the
code, not written from memory.

**One correction to the obvious assumption:** five workflows are queue jobs
(`clientflow/services/worker.py::HANDLERS`). The sixth, clause review, is **synchronous** — it is called by
the API and the CLI directly, because a reviewer is waiting for the answer and there is nothing to schedule.
Saying that plainly is better than implying all six run through the queue.

---

## 1. Intake triage

| | |
|---|---|
| **Business problem** | Enquiries arrive through four doors (form, WhatsApp, email, referral). One desk reads each one, decides the practice area, guesses urgency and writes the acknowledgement. Response time depends on who is at their desk. |
| **Trigger** | `Queue.enqueue("intake", payload, key=f"intake:{enquiry_id}")` — in production a webhook or a mail poller; in tests, `tests/test_workflows.py::WorkerTests`. |
| **Input** | `{id, received_at, source, name, email, phone, message, documents_supplied[]}` |
| **Processing** | `rules.classify_area()` scores the message against 9 practice areas → `rules.urgency()` → `rules.language_of()` → `rules.missing_documents()` → choose status (`routed` / `needs_human`) → insert contact + enquiry → create acknowledgement approval. |
| **AI involvement** | None. Keyword rules with a negation strip (`rules.NEGATIONS`), because a misfiled matter is a missed deadline and a rule can be read and corrected. |
| **Modules** | `workflows/intake.py`, `workflows/rules.py`, `services/approvals.py`, `core/audit.py` |
| **Database** | INSERT `contacts`; INSERT `enquiries` (`idempotency_key = "intake:<id>"`, UNIQUE); INSERT `approvals`; INSERT `audit_log` ×2–4 |
| **API** | None directly. Visible via `GET /api/enquiries` and in the dashboard. |
| **Output** | `{id, outcome, practice_area, priority, confidence, owner, status, missing[], approval_id}` |
| **Error handling** | Duplicate id → `{"outcome": "duplicate"}`, no second row. Unassigned area → `status=needs_human`, no draft. Queue-level failure → retry, then dead-letter. |
| **Human approval** | The acknowledgement exists only as `approvals` row with `status='pending'`. No send path. |
| **Limitations** | Rules are brittle on unusual phrasing; one urgency keyword list for all areas; no entity extraction (names/amounts are not parsed); owner mapping is demo configuration, not the firm's rota. |

## 2. KYC pack checker

| | |
|---|---|
| **Business problem** | Paralegals and assistants chase Emirates IDs, passports, trade licences and board resolutions by hand. Nobody can say how long a pack takes to complete. |
| **Trigger** | `Queue.enqueue("kyc", {"matter_id", "practice_area", "client_name"})` — in `seed.py`/`demo` it is enqueued per matter. |
| **Input** | Matter id + practice area; document rows read from `documents` (`doc_type`, and `*_expiry:` marker rows written by the seed). |
| **Processing** | Rebuild doc list → `kyc.check_pack()` → required-vs-present diff → expiry windows (30 days) → expired items → holder-name comparison → issues list. |
| **AI involvement** | None. No OCR, no extraction — the prototype reads metadata, and says so. |
| **Modules** | `workflows/kyc.py`, `workflows/rules.py` (checklists), `services/worker.py::handle_kyc`, `services/approvals.py` |
| **Database** | SELECT `documents`; INSERT `approvals` (kind `kyc_chase`) when incomplete; INSERT `audit_log` (`kyc_checked`) |
| **API** | Visible through `GET /api/approvals`; no dedicated KYC endpoint. |
| **Output** | `{matter_id, complete, issues[], approval_id}` plus a chase draft in the queue |
| **Error handling** | Missing matter/documents → empty pack is a *valid* result ("everything missing"), not an exception. Expiry date unparsable → skipped, not guessed. |
| **Human approval** | Every chase is an approval row. |
| **Limitations** | Completeness only — explicitly not authenticity. No file storage, no image reading, no per-client checklist variants, no reminder schedule. |

## 3. CV triage

| | |
|---|---|
| **Business problem** | The group's own recruitment arm receives more CVs than it can screen, and its public marketing names exactly this ("too many CVs, not enough real candidates"). |
| **Trigger** | `Queue.enqueue("cv_screen", {"role_ref": "ROLE-AUTOMATION"})` |
| **Input** | Rows from `candidates` where `decision='pending'`, each with `cv_text` |
| **Processing** | `rules.score_cv()` → 8 weighted criteria (`rules.CV_RUBRIC`: python 3.0, automation 3.0, AI 2.0, data/SQL 2.0, commercial evidence 2.0, cloud 1.0, JS 1.0, client-facing 1.0) → score 0–100 → sort → top third (min 3) → shortlist approval |
| **AI involvement** | None. A weighted rubric, because a rejected candidate must be explainable to them and to the client. |
| **Modules** | `services/worker.py::handle_cv`, `workflows/rules.py`, `services/approvals.py` |
| **Database** | SELECT `candidates`; UPDATE score + `reasons` JSON; INSERT `approvals` (kind `shortlist`); INSERT `audit_log` |
| **API** | Not exposed by endpoint; the shortlist appears in the approval queue. |
| **Output** | `{screened, shortlisted, approval_id}` |
| **Error handling** | No pending candidates → `{"screened": 0}`. |
| **Human approval** | The system ranks and explains; the recruiter decides. |
| **Limitations** | Keyword rubric rewards vocabulary, not capability — a well-written CV with different words scores low. No PDF parsing, no bias testing, no adverse-action logging. This is the weakest workflow ethically and should be described as such. |

## 4. Stalled-matter watchdog

| | |
|---|---|
| **Business problem** | Matters go quiet. Nobody notices until the client rings, which is the worst possible moment. |
| **Trigger** | `Queue.enqueue("watchdog", {}, key="watchdog:daily")` — intended for a daily schedule. |
| **Input** | `matters` where `status IN ('open','awaiting_client')` and `last_activity < now-5 days` |
| **Processing** | SELECT stale rows → build a plain-text list → create one digest approval |
| **AI involvement** | None. |
| **Modules** | `services/worker.py::handle_watchdog`, `services/approvals.py` |
| **Database** | SELECT `matters`; INSERT `approvals` (kind `watchdog`, entity `matters`); INSERT `audit_log` (`watchdog_ran`) |
| **API** | `GET /api/stats` exposes `matters.stalled`; dashboard card "Stalled matters" |
| **Output** | `{stalled: n}` and a digest draft |
| **Error handling** | Nothing stale → no approval row created, `stalled: 0`. |
| **Human approval** | The digest is a draft for the partner; the system does not contact clients. |
| **Limitations** | "Activity" is a column nobody updates automatically in this prototype; a real deployment needs the activity signal from the practice-management system. 5 days is hard-coded. |

## 5. Campaign attribution

| | |
|---|---|
| **Business problem** | The agency's own homepage asks "Cool. Did anyone buy anything?" — spend is visible, return is not. |
| **Trigger** | `Queue.enqueue("attribution", {}, key="attribution:weekly")` |
| **Input** | `campaign_weeks` (campaign, week, spend, impressions, clicks, leads, revenue) |
| **Processing** | `metrics.attribution()` → per-campaign SUMs → cost per lead → ROAS → flag `no revenue` / `no leads` |
| **AI involvement** | None. Arithmetic, and that is the point: this number must be defensible in a client meeting. |
| **Modules** | `services/metrics.py::attribution`, `services/worker.py::handle_attribution` |
| **Database** | SELECT `campaign_weeks`; INSERT `audit_log` (`report_built`) |
| **API** | `GET /api/attribution`; dashboard table |
| **Output** | `{campaigns: [...], spend_with_no_return: n}` |
| **Error handling** | Zero spend or zero leads → `None` rather than `inf`; no division by zero. |
| **Human approval** | None needed — read-only report. Nothing is sent. |
| **Limitations** | Demo data only; no real ad-platform connector, no attribution window, no multi-touch model, no currency handling. The report is a shape, not a product. |

## 6. Contract clause review (synchronous, not queued)

| | |
|---|---|
| **Business problem** | Corporate review starts with "which clauses are in here, and which of them should worry me?" — an hour of reading before any judgement. |
| **Trigger** | `GET /api/review?idx=3` (corpus contract) or `?text=...`; CLI `python -m clientflow.cli review 3` |
| **Input** | Contract text (CUAD filing, or any text supplied) |
| **Processing** | `clause_data.split_clauses()` (600-char blocks) → `clause_model.predict_present()` (41 labels) → `_best_clause()` TF-IDF retrieval per detected category → `risk_flags()` (6 listed rules) |
| **AI involvement** | **Yes** — TF-IDF + One-vs-Rest LinearSVC, trained on CUAD. Local, offline, 13 s to train. |
| **Modules** | `workflows/clause_data.py`, `clause_model.py`, `clause_review.py`, `api/server.py` |
| **Database** | None. Stateless: same input, same output. No audit row — a gap, since a review of a real contract should be logged. |
| **API** | `GET /api/review?idx=N`, `GET /api/review?text=...`; dashboard `/?review=3` (`&compare=1` for the accuracy column) |
| **Output** | `{title, findings[], key_clauses_absent[], risk_flags[], located, passage_agreement, disclaimer}` |
| **Error handling** | Unknown idx → 404 JSON. Missing corpus/model → CLI raises with the fetch/train instruction. Empty text → zero findings, disclaimer still returned. |
| **Human approval** | Nothing to approve — no side effect. The disclaimer travels inside the result object. |
| **Limitations** | Presence F1 0.80 micro / 0.56 macro; location 22% agreement; US drafting; no OCR; no UAE evaluation; risk rules are heuristics (heading-only evidence possible). |

---

## How the workflows relate to the four business arms

| Arm | Workflow | Why that one |
|---|---|---|
| Law | KYC, clause review, watchdog | Document completeness, review triage, deadlines |
| Recruitment | CV triage | Their own stated bottleneck |
| Marketing | Attribution | Their own public question |
| All | Intake | Shared front door, one record per enquiry |

## What a seventh workflow would be, and why it is not here

A **document intake/chase scheduler** (recurring reminders at 3/7/14 days) would be the natural next build: it
is the same approval-gate shape, it needs a scheduler rather than new logic, and it is what turns the KYC
checker from a one-shot into a process. It was excluded on purpose — the brief said not to expand the
architecture, and five real workflows plus an honest model is a better interview asset than six unfinished
ones.
