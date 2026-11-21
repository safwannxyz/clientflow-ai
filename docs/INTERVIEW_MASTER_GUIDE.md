# Interview master guide

Every answer below is about **this** codebase — `C:\Users\Safwan\Desktop\monday` — not a generic pattern.
Numbers are the ones reproduced in `docs/MODEL_CARD.md`. Where the honest answer is "we don't do that", it
says so, because being caught out is worse than being early.

Part 1: project (20) · Python and API (15) · AI and LLM (15)
Part 2: workflow automation (10) · database and architecture (10) · security (10) · business scenarios (10) ·
the five difficult follow-ups

---

## Part 1A — Project questions (20)

**1. What is ClientFlow AI, in one sentence?**
A small platform that runs six automations for a group with a law firm, a recruitment arm, a marketing agency
and e-commerce brands — with a durable queue, an approval gate, an audit trail and a dashboard over the top.
It is a portfolio project; no firm data is in it.

**2. Why did you build it?**
The advertised role asks for five production automations in 90 days with measurable impact and security
controls. A single demo script cannot show what holds five automations up — retries, dead letters, approvals,
audit, register. So I built the layer underneath as well.

**3. What are the six workflows?**
Intake triage, KYC pack checker, CV triage, stalled-matter watchdog, campaign attribution — those five are
queue jobs — and contract clause review, which is synchronous because a reviewer is waiting for it.

**4. What is actually AI in this project?**
One part: the contract clause classifier, TF-IDF plus One-vs-Rest LinearSVC trained on 510 CUAD contracts.
Everything else is rules and arithmetic, deliberately — a misfiled matter or a rejected candidate has to be
explainable.

**5. How big is it?**
2,519 lines of Python across 19 modules, 10 tables, 9 API endpoints, 55 tests.

**6. What was the hardest part?**
Accepting that clause *location* is a much harder problem than clause *presence*. I measured 22% agreement
with lawyer annotations at the shipped setting, so I stopped calling it a citation, raised the threshold until
it abstains, and labelled what remains a candidate passage. The engineering was easy; giving up the claim was not.

**7. What are you most pleased with?**
That there is no send function anywhere in the codebase. The safety is an absent capability, not a disabled
one — there is no flag to flip and no code path to review.

**8. What would you build second?**
A document chase scheduler: reminders at 3/7/14 days, same approval shape, needs a scheduler rather than new
logic. It turns the KYC checker from a one-shot into a process.

**9. What did you get wrong first?**
Three things, all found by tests rather than reading: the token env var kept the old prototype's name so
every authenticated write 401'd; redaction ran after truncation, letting half an ID survive; and "not urgent"
matched the keyword `urgent`.

**10. What is deliberately unfinished?**
No OCR, no real CRM/email/DMS connectors, no scheduler, no per-user auth, no retention policy, single-tenant
data model. Each is named in the README and in the security review.

**11. How do you know it works?**
55 tests, a deterministic demo (`demo --reset` gives identical numbers every time), CI running the same suite
on a clean Linux machine, and a metrics table reproduced from the code rather than copied from a report.

**12. What does the dashboard actually show?**
Findings in sentences first — drafts waiting, stalled matters, spend with no return, estimated hours — then
enquiries, approval queue, campaign attribution, queue health, systems register and the audit tail.

**13. Why a systems register?**
The advert asks for one. It also answers the question a partner will ask: what does this touch, who owns it,
and how do I stop it.

**14. What would you change if this had ten users?**
Postgres, a real queue with per-tenant isolation, SSO, and the register enforced in code rather than by
convention. SQLite plus a file queue is a single-instance design and I would not pretend otherwise.

**15. How does it handle the four businesses sharing one database?**
It does not, properly — there is no tenant column. That is a schema change, not a config flag, and it is
documented as a gap rather than papered over.

**16. What is in the repo, and what is not?**
42 tracked files: modules, tests, docs, Dockerfile, Render blueprint, CI. Not tracked: the 39 MB CUAD corpus
and the trained `.pkl` — both reproducible with two commands.

**17. How long did it take?**
The first working version about 50 minutes; the platform with tests and docs a few hours; the audit that
found three real bugs another hour. I overestimated at the start and said so.

**18. Why is it private?**
It names a firm in the research document and it is a portfolio artefact, not a product. Private until there
is a reason to open it.

**19. Which part would you defend hardest?**
The approval gate plus the audit log: every decision has an actor, a timestamp and a redacted preview, and
nothing leaves without a human. That is the whole answer to "will this be safe in a law firm".

**20. What would a real deployment need before touching a client file?**
SSO, a DPIA, a retention and deletion policy, alerting on dead letters, encrypted storage, and re-evaluation
of the clause model on UAE drafting. All five are written down rather than promised.

## Part 1B — Python and API (15)

**21. Why the standard library instead of FastAPI?**
`http.server` plus `sqlite3` means no dependency can break the demo, it runs offline, and everything is
readable in one sitting. ADR-001 records the trade: no async, no schema validation, thread-per-request.

**22. How does the queue claim a job atomically?**
`UPDATE jobs SET status='running', locked_by=? WHERE id IN (SELECT ...) AND status='pending'` inside
`BEGIN IMMEDIATE`, then re-select by `locked_by`. The same idea as `FOR UPDATE SKIP LOCKED`, using what SQLite
has. A test asserts two workers cannot claim the same job.

**23. What does an idempotency key look like and why?**
For intake: `intake:<enquiry_id>`; the column is `UNIQUE`. For a webhook-style flow you would hash
source + contact + normalised message, because a re-delivery differs only in timestamp.

**24. How are errors handled in a handler?**
`worker.run_once` wraps each handler; an exception is caught, `queue.fail()` records it and either reschedules
with backoff (30/120/600s) or dead-letters at `max_attempts`. The audit line records `job_failed` with the
exception type.

**25. Why is `--dry-run` implemented against an in-memory database?**
Because the alternative is a code path that behaves differently in dry-run. Using `:memory:` means the same
code runs and simply gets thrown away — so "writes nothing" is structural, not conditional.

**26. How does the API know which decision endpoint was called?**
It splits `self.path` and matches `len(parts) == 4 and parts[:2] == ["api","approvals"] and parts[3] ==
"decide"`. Crude compared with a router, and honest about being crude.

**27. Where does validation happen?**
At the boundaries that matter: `Approvals.decide` rejects anything but approved/rejected and refuses a second
decision; `security.require` raises on a missing capability; the CLI's argparse rejects malformed commands.
There is no request schema validation — that is the framework trade.

**28. How is the dashboard rendered?**
Server-side f-strings over query results, with `html.escape` on every value. No template engine, no JavaScript
build step. It is 40 lines of CSS and about 120 lines of HTML composition.

**29. How do you keep the dashboard and the API consistent?**
Both call the same functions — `metrics.overview`, `metrics.attribution`, `Approvals.pending`. A number cannot
differ between the page and the JSON because there is only one implementation.

**30. What happens if two requests hit SQLite at once?**
WAL mode plus a single connection per request; writes serialise. Fine for a laptop and a handful of users;
wrong at scale, and that is stated in the README rather than discovered later.

**31. How are timestamps handled?**
ISO-8601 UTC strings everywhere (`core/db.py::now_iso`). They sort correctly as text, they survive JSON, and
they avoid the timezone bugs that come from naive datetimes.

**32. How would you add a seventh workflow?**
Write `handle_thing(db, payload)`, add it to `HANDLERS`, enqueue with a key. If it produces anything
outbound, it goes through `Approvals.create`. Roughly 80 lines, and it inherits queue, audit and approval.

**33. How do you test something with an external trigger you do not have?**
The trigger is a queue row. Tests enqueue the payload directly — the seam is the job, not the webhook — which
is why the workflow tests do not need a fake HTTP server.

**34. What is the riskiest dependency in the project?**
`pickle.load` for the model. A pickle from an untrusted source is remote code execution, so the file is only
ever produced by `cli train` locally. That belongs in the security review explicitly.

**35. How is the app deployed?**
Three ways: locally with `cli serve`, a static snapshot via `scripts/snapshot.py`, or the Docker image whose
build fetches CUAD and trains before starting. Render blueprint provided; deliberately single-instance.

## Part 1C — AI and LLM (15)

**36. Why not an LLM for everything?**
Cost, latency, auditability and data protection. A firm with client data cannot send contract text to a
consumer endpoint; a rule or a local model can be inspected when it is wrong. The one place a model earns its
place is clause presence, where there is real labelled data.

**37. Walk me through the model.**
TF-IDF (60k features, 1–2 grams, `min_df=2`, sublinear TF, accent stripping) into 41 independent LinearSVCs
via `OneVsRestClassifier(class_weight="balanced")`. Trains in 13 seconds, runs offline, coefficients
inspectable.

**38. Why LinearSVC and not BERT?**
510 contracts for 41 labels is small; a linear model on sparse features is a strong baseline there, and it
cannot hallucinate. A fine-tuned transformer might win a few points on frequent classes and would lose on
shipping, speed and explainability.

**39. What are your metrics, and what do they hide?**
Micro F1 0.802, macro F1 0.561. The gap is the story: frequent clauses are strong (Document Name 1.00, Parties
1.00, Governing Law 0.97), rare ones are near zero (support 2–7). Macro is the number that should make a
reviewer cautious.

**40. Why micro and macro both?**
Micro tells you how often you are right overall; macro tells you whether it works for the long tail. Reporting
only micro would flatter the model, so both are printed.

**41. How did you split the data?**
By contract, 80/20 with seed 42 — 408 train, 102 test. Splitting by paragraph would leak the same contract
across both sides and inflate every score.

**42. No validation split — is that a problem?**
Yes, mildly. Hyperparameters were chosen once by judgement and never tuned on test. With a validation split
the numbers would be a little more defensible and a little lower. It is written down as a limitation.

**43. Why does location fail when presence works?**
Presence asks "is there evidence anywhere in 15,000 characters" — bag-of-words is well suited. Location asks
"pick the same paragraph a lawyer picked" out of ~30 blocks with repeated vocabulary. It is retrieval with a
near-uniform prior and a lexical scorer, and it measures 22%.

**44. What did you try, and what did you learn?**
Four measured attempts: vocabulary overlap at 2,500-char blocks (28%), finer blocks (21% — worse, which told me
scoring was the problem, not segmentation), TF-IDF retrieval against CUAD's annotation question (32% at 2,500),
and then an abstention sweep: at a 0.16 similarity floor it returns a passage for 44% of findings and is right
34% of the time. I shipped the abstaining version, because a confident wrong pointer is worse than "not
located".

**45. How would you use an LLM here responsibly?**
Behind `rules.classify_area` and `_best_clause` as named seams, on an approved endpoint with no-training
terms, with the output treated as a suggestion, logged with the prompt hash, and a rules fallback. Never for
a decision that is client-facing or legal.

**46. What about hallucination?**
The risk is in the language layer, not the classifier. That is why nothing generates text as an answer: drafts
are templates with fields, risk items are listed rules, and the disclaimer travels inside the result object.

**47. What is RAG and where would it fit?**
Retrieval-augmented generation: embed a corpus, retrieve passages, answer only from them with citations. It
fits internal knowledge — precedents, policies, clause banks — not this classification task. I would build the
retrieval and citation layer first and add generation last, because citations are what make it usable in law.

**48. How would you evaluate an LLM feature?**
A labelled set of real queries with expected citations, measuring retrieval recall at k, answer correctness,
and refusal rate on unanswerable questions. If it cannot say "I don't know", it is not ready for a lawyer.

**49. What is your model's biggest failure mode?**
Vocabulary drift. It has never seen UAE or DIFC drafting; boilerplate differs; a confident wrong label on a
regional contract is the most likely failure in this firm's real work.

**50. If you had one week to improve the model?**
Label 150–200 real (redacted) regional contracts with a lawyer, hold out 50, fine-tune a small transformer,
compare against the linear baseline on the same held-out set, and report both — including if the baseline
wins.

---

## Part 2A — Workflow automation (10)

**51. What makes an automation "production" rather than a script?**
Four things: it can fail and retry, it is idempotent, every run is logged with an actor, and there is a way to
stop it. This project has all four for the five queued workflows.

**52. How do you decide what to automate first?**
Volume × time × cost of error × how easily a human can check the output. Rules-based, high-volume, verifiable
and reversible goes first; anything that decides a client's rights goes last and only with a human in the
loop.

**53. How would you onboard one of these in a real firm?**
Shadow for a day, write down the repeated actions, pick the highest-scoring one, build the smallest version
that runs end to end, ship it to one person, watch them use it, fix it, then move on.

**54. What is the failure mode you worry about most?**
Silence. A job that quietly processes 40 records instead of 400 looks like success. That is why counts,
`job_failed` audit lines and the dead-letter list exist — and why the missing piece (alerting) is named.

**55. How do you measure the benefit honestly?**
Baseline first: enquiries per day, minutes to first reply, documents chased, hours spent. Then the same
numbers after. `metrics.hours_saved` multiplies counted actions by stated allowances and returns
`assumption: True` with the basis, so nobody can quote it as a measurement.

**56. Where does a human stay in the loop?**
Any outbound message, any client-facing text, any shortlist, any chase. The system prepares; a person decides.

**57. How do you handle a workflow that needs rework after go-live?**
Rules are in one module (`workflows/rules.py`); a fix is a small change plus the failing sentence as a test.
Schema changes go through numbered migrations so existing data survives.

**58. What is your answer to "we tried automation and it broke"?**
Ask what happened when it broke — usually nobody knew. The retry, the dead letter and the audit line are the
answer to that specific history.

**59. How do you keep six automations from interfering?**
Each writes to its own tables through `core`; there is no shared mutable state beyond the database. The
register documents what each touches, and `worker.HANDLERS` is the single dispatch point.

**60. What would you refuse to automate?**
Anything where the output is advice, anything that decides money or rights without review, and anything
where the input cannot be verified — a KYC authenticity check is the clearest example, which is why this one
checks completeness only.

## Part 2B — Database and architecture (10)

**61. Walk me through the schema.**
Ten tables: `contacts`, `matters`, `documents`, `enquiries`, `candidates`, `campaign_weeks`, `jobs`,
`approvals`, `audit_log`, `systems_register`. Two unique idempotency keys, one job index on
`(status, run_after)`.

**62. Why numbered migrations instead of "create if not exists"?**
Because in a firm you never get a clean database again. `schema_version` plus ordered migrations means an
existing database upgrades in place, and `Database.version` tells you where it is.

**63. Where would this break at 10× volume?**
Three places: SQLite write contention (single writer), synchronous request handling, and the lack of a
per-tenant filter. All three are Postgres-and-a-real-queue problems, not logic problems.

**64. Why JSON columns for `documents_missing` and `reasons`?**
They are read whole, never queried by field, and they are audit-relevant snapshots of a decision. Normalising
them would add joins for no query benefit. If we ever filtered by missing document type, that changes.

**65. How is the ER model shaped around the domain?**
A contact raises enquiries; a matter requires documents; approvals attach to whatever entity produced them
(hence `kind` + `entity` rather than a foreign key per type). That polymorphism is a deliberate trade: one
queue for all approvals, at the cost of no referential integrity on `entity`.

**66. What is your audit strategy?**
Append-only rows, redacted at the boundary, with a named actor. No update or delete API. The gap is that
SQLite does not prevent edits to the file — production needs WORM storage and hash chaining.

**67. Why does the queue live in the database rather than Redis?**
One fewer service to run for a firm with no platform team, and the backlog becomes a table you can query in
the same transaction as the work. The cost is throughput.

**68. How do you handle schema change with live data?**
Add a migration, never edit one that has run. Tests build a fresh database each time, so the migration path
itself is exercised on every run.

**69. What does `PRAGMA journal_mode=WAL` buy you?**
Readers do not block the writer, which matters because the dashboard reads while a worker writes. It is also
why a second process can see committed rows immediately.

**70. How would you add multi-tenancy?**
A `tenant_id` on every table, a filter in every query, and a session-level tenant in the request context —
plus a test that asserts cross-tenant reads return nothing. It is a schema migration plus discipline, not a
feature flag.

## Part 2C — Security (10)

**71. What stops the automation emailing a client?**
There is no send function. Drafts are rows with `status='pending_approval'`. Not a flag, not a config — an
absent capability.

**72. How is authentication done, and what is wrong with it?**
A shared token compared with `hmac.compare_digest` against `CLIENTFLOW_API_TOKEN`, and writes are refused
when it is unset (closed by default). What is wrong: no user identity, so no per-person attribution and no
per-person revocation. It is the smallest control that means "not anyone who can reach the port".

**73. What is redacted, and in what order?**
Emirates IDs, passports, card sequences, `password=`/`token:`/`Bearer` strings — redacted **before**
truncation, because truncating first let half an ID survive. Email and phone are left intact by default
because they are the trace key, and can be masked on request.

**74. How do you handle KYC documents?**
Metadata only: type, received date, expiry. No files, no images, no real identities. And the checker says in
its own output that it verifies completeness, not authenticity.

**75. What is the PDPL position?**
Federal Decree-Law 45/2021 applies: consent basis, records of processing, breach notification. Before real
client data there must be a DPIA, a retention schedule and an approved processing environment.

**76. What would you do in the first hour of a breach?**
Rotate the token so everything degrades to read-only, grep the audit log for redaction events around the
window, identify what the job payloads contained, and follow the firm's notification procedure. The log never
stored the secret itself, which is the point of redacting at the boundary.

**77. Why is the pickle a security issue?**
`pickle.load` executes code on load. Safe here only because the artefact is produced locally by `cli train`.
From an untrusted source it is remote code execution, and it is listed in the security review.

**78. How is the audit log protected from the application?**
It is not, beyond the absence of mutation APIs. Production needs append-only storage outside the app and
periodic hash chaining so a deleted row is detectable.

**79. What about the shared database between four businesses?**
It is a real gap: single-tenant schema, no row-level filtering. Documented in `SECURITY_REVIEW.md` §11 rather
than claimed as isolation.

**80. Name a bug you found by auditing rather than by testing.**
The token variable name. Locally green, failing in CI for 40 minutes, because the fix was never committed.
The lesson: a completion report is not evidence — the repository is.

## Part 2D — Business scenarios (10)

**81. The partner asks: what will this save us?**
"Nothing until we measure a baseline. Today the estimate is 6.9 hours from counted actions times stated
allowances, and I would rather show you that number labelled as an assumption than a made-up one."

**82. The firm says the automation made a mistake — what now?**
Open the audit log, find the decision, show the matched terms and confidence. Then decide: a rule fix, a
training example, or a human review step. Every finding is traceable by design.

**83. How would you price the 90-day plan?**
Five small automations, each measured on hours removed. The ones I would propose first: follow-up watchdog
(cheapest, visible in a week), KYC chase (three people doing it by hand), attribution (a partner's question),
intake triage (the one-business-day promise), CV triage (their own stated bottleneck).

**84. Marketing wants a dashboard by Friday. What do you say?**
"The numbers exist; the definitions do not. Give me one day to agree what 'a lead' and 'attributed revenue'
mean, then you get a dashboard that survives being questioned."

**85. HR asks you to auto-reject candidates scoring below 60. Do you?**
No. The rubric rewards vocabulary and has no bias testing; it ranks for a human, it does not decide. I would
say that plainly and propose a review step and a documented appeals path instead.

**86. A client asks whether they can put confidential files into the tool.**
Not in this prototype: no per-user auth, no retention policy, single-tenant storage. In a real deployment the
answer depends on the approved environment, and the model runs locally so no text leaves the machine.

**87. The firm wants to cancel the automation after a month. How easy is it?**
Stop the scheduler, drop the register entry, revoke the token, and nothing else depends on it — each workflow
writes to its own tables and there is no send path to unwind.

**88. Which automation would you kill first if time ran out?**
Clause review. It is the most interesting and the least reliable: location accuracy means a lawyer still searches
manually, and the presence flags are a convenience. The watchdog and the KYC chase are boring and
they work.

**89. How do you stop the tool becoming shelfware?**
Adoption is a success measure in the advert, and it is usually won by giving one person a workflow that
removes an annoyance they complain about, then letting them tell the others.

**90. What would make you say this project failed?**
If a partner could not tell me what it does after two minutes, or if a single automation ran for a month
without anyone reading its output. Both are adoption failures, not code failures.

---

## The five difficult follow-ups

**"Your model is 80% micro F1 — why should I trust it on my contracts?"**
> "You shouldn't trust it on yours yet. It was trained and tested on US commercial filings; UAE and DIFC
> drafting is different boilerplate. Treat it as a triage aid that tells you where to look, and let me
> evaluate on fifty of your redacted contracts before it influences anything. I would expect the numbers to
> drop and I would rather show you the drop than hide it."

**"Why is clause location only 22%? That sounds broken."**
> "It is weak — a passage for 44% of findings, right about a third of the time — and I stopped calling it a
citation because of that. Presence is a bag-of-words question the
> model is well suited to; location is retrieval where the vocabulary repeats across paragraphs and a lexical
> scorer has no notion of clause boundaries. The fix is a span model or an LLM with citations, evaluated on a
> held-out set — and I would not ship the number I have as if it were a citation."

**"You have no per-user authentication. Isn't that disqualifying?"**
> "It disqualifies the prototype from handling client data, which is why the server binds to localhost and the
> README says so. What I would bring on day one is the firm's SSO in front of it, which is a deployment
> integration rather than a rewrite: the role checks and the audit lines already take an actor."

**"What did you actually do versus what did the AI do?"**
> "The design, the code, the tests, the docs, the mistakes and the fixes are mine. I used an AI assistant as a
> pair — for scaffolding and for reviewing my reasoning — and every number here was reproduced from the code
> on my machine, including the ones that embarrassed the project: 34% passage agreement, macro F1 0.56, a
> token bug that failed CI for forty minutes."

**"If I gave you a real brief on Monday, where would you start?"**
> "With the process, not the tool: shadow the team, list the repeated actions, score them by volume, time,
> cost of error and checkability. Then build the highest-scoring one end to end, in its smallest version,
> with a log line per run and an approval gate. I would rather ship one workflow that survives contact with a
> partner than five that demo well."
