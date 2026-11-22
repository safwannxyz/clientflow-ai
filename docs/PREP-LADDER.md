# Prep ladder — beginner → advanced

For the **Altara** interview: AI Automation Specialist / AI & Business Systems Engineer (posted through
PRIME HR ADVISORY), Dubai, AED 10,000–12,000/month, office-based, 5 days.

This file is the order to learn things in, not a reading list. A level is finished when you can **say it out
loud without notes**, not when you have read it. Every self-test at the end of a level is a spoken test.

Nothing here replaces the other files — it tells you which one to open and what to extract:

| Level | Read | Time |
|---|---|---|
| 0 — Vocabulary | this file only | 45 min |
| 1 — Know them | `ALTARA_PUBLIC_RESEARCH.md` | 1 h |
| 2 — Your project, conversationally | `INTERVIEW_QUICK_REFERENCE.md`, `DEMO_SCRIPT.md` §7-min | 2 h |
| 3 — Technical depth | `ARCHITECTURE.md`, `MODEL_CARD.md`, `WORKFLOWS.md` | 3–4 h |
| 4 — Think like the hire | `SECURITY_REVIEW.md`, §E of the research file, this file §4 | 2–3 h |
| 5 — Pressure | `INTERVIEW_MASTER_GUIDE.md` last section ("five difficult follow-ups") | 1 h + drills |

**Pick your runway first** (bottom of this file) — 3 days, 1 day, or 2 hours are three different plans.

---

## Level 0 — The vocabulary you must not fumble (45 min)

Interviewers form an opinion fast, and it is usually formed by whether ordinary words come out cleanly.
For each term below, say **one plain sentence** out loud. If you stumble, that is your weak spot.

**Automation and systems**
- **Automation** — a trigger fires, work happens without a person, and the result is recorded.
- **Workflow** — the ordered steps one piece of work passes through, including where a human decides.
- **Integration** — two systems exchanging data; done by API call, webhook, or scheduled polling.
- **API** — the documented way one program asks another to do something.
- **Webhook** — the other program calls *you* the moment something happens, instead of you asking.
- **Polling** — you ask on a timer; simpler, but adds latency and wasted calls.
- **CRM** — the system of record for leads, deals and contact history.
- **RPA vs AI** — RPA clicks the same buttons a human would; AI makes a judgement. This project is mostly
  rules, with one model, and that is deliberate.
- **LLM** — a model that predicts text; useful for reading and drafting, not for decisions.
- **RAG** — retrieve the right passages first, then answer only from them, with citations.
- **Hallucination** — confident output with no basis in the source.
- **Embedding / vector search** — turning text into numbers so "similar meaning" becomes "nearby point".

**Reliability**
- **Queue** — a durable to-do list jobs are pulled from, so work survives a crash.
- **Retry with backoff** — try again after 30s, then 120s, then 600s, instead of hammering a failing service.
- **Idempotency** — running the same job twice produces one result, not two.
- **Dead letter** — a job that failed too often, parked where a human can see it.
- **Rate limit** — the provider's cap on calls per minute; you respect it or get blocked.

**Security and data**
- **Least privilege** — each integration gets the narrowest access that still works.
- **Audit log** — append-only record of who did what, when, with what data.
- **PII** — personal data; in the UAE, PDPL (Federal Decree-Law 45/2021) governs it.
- **Redaction** — stripping identifiers before storing or logging.
- **Human in the loop** — nothing client-facing leaves without a person approving it.
- **DPIA** — the assessment you do before processing personal data at scale.

---

## Level 1 — Know them better than your own project (1 h)

They will test whether you did homework. Open `docs/ALTARA_PUBLIC_RESEARCH.md` §A–E and extract these.

**The structure.** Four operating businesses on one back office: **Altara Law** (Dubai firm, 11 practice
areas, three offices in Downtown and Business Bay), **PRIME HR ADVISORY** (recruitment, executive search, HR
advisory — and the entity that posts the group's own vacancies, including this one), **Altara Social**
(marketing, content, video, WordPress/Shopify sites), and **e-commerce consumer brands** on Shopify.

**Why that structure is the opportunity.** Same enquiry, same candidate, same invoice, same client — crossing
three or four arms with no shared record. Every automation they want is really *one shared record plus a
trigger*. Say that sentence; it is the thesis of your whole interview.

**Their own published promises — quote these back.**
- Altara Social: "we'll get back to you within 24 hours." That is a **written SLA** → instant lead response
  and follow-up automation is measurable against their own number.
- Altara Law: "a consultant will respond within one business day." Same trick, for intake triage.
- Altara Social's own tagline: *"Cool. Did anyone buy anything?"* → they sell **attribution**, so spend-vs-
  revenue reporting is a KPI they already believe in.

**The mandate, in their words.** "Deliver at least five meaningful production automations or AI-enabled
workflows, with measurable business impact, clear documentation and appropriate security controls" in 90 days.
Explicitly **not** "a purely strategic or advisory role."

That last line changes how you answer everything: **ship, don't propose**. Even your "what I'd do first"
answers must end in something that runs and logs.

**What they asked for technically** (nice-to-haves, so name them, don't fake them): M365/Graph, Pipedrive or
similar CRM, legal practice management, SharePoint, Shopify/WooCommerce, Xero, Meta ads, AI APIs and agent
frameworks, RAG, UAE PDPL / DIFC / ADGM.

**Self-test (spoken, 4 minutes):** name the four arms and what each sells · their two response promises ·
the 90-day mandate in their words · why "not purely strategic" matters · three of their nice-to-haves and
which two you'd learn first.

---

## Level 2 — Your project, conversationally (2 h)

The failure mode here is reciting. You want three gears: **20 seconds, 2 minutes, 15 minutes.**

### Gear 1 — 20 seconds
> "I built a small platform that runs six automations for a group like yours — a queue, an approval gate, an
> audit trail, and a dashboard over the top. The only AI in it is one contract-clause classifier, and I
> publish its weak numbers rather than hide them."

### Gear 2 — 2 minutes, in this order
1. **Why** — "your advert asks for five production automations in 90 days. A demo script can't show what
   holds five automations up: retries, duplicates, approvals, audit. So I built the layer underneath too."
2. **What runs** — six workflows: intake triage, KYC pack checker, CV triage, stalled-matter watchdog,
   campaign attribution, contract clause review. Five are queue jobs; clause review is synchronous because
   someone is waiting for the result.
3. **The one that matters most** — "there is no send function anywhere in the code. Drafts wait for a person.
   The safety is an absent capability, not a disabled one."
4. **The honest number** — "micro F1 0.802, macro 0.561 on 102 held-out contracts. The gap is the story:
   frequent clauses work, rare ones don't."
5. **The gap list** — SSO, multi-tenancy, retention, alerting, real connectors. Say it before they find it.

### Gear 3 — the demo, three stop-points only
Follow `docs/DEMO_SCRIPT.md` §7-minute. Do not tour the folder. Bring up:

1. **One number** — the dashboard top line: 3 drafts waiting, 7 stalled matters, AED 40,410 spend with no
   revenue, 6.9 hours replaced *(and say "assumption" in the same breath)*.
2. **One generated file** — the clause review panel: findings in sentences, the risk rules listed, so a
   lawyer can disagree with one line instead of the whole system.
3. **One log row** — run the queue twice: nothing duplicates. "Idempotency is in the schema, not in my head."

**Draw it from memory in 90 seconds** before you drill anything else: enquiry → queue (idempotency key) →
worker claims atomically → rules/model → rows + approval + audit line → human decides. If you can draw that
on a whiteboard, you can survive any "walk me through it" question.

**Self-test:** the 20-second pitch · the five gear-2 beats · the three demo stop-points and the exact number
you show at each · what is synthetic vs real in the demo.

---

## Level 3 — Technical depth (3–4 h)

Only what you will actually be asked. Read the source file named, then close it and say the answer.

### 3A — Queue and reliability (`ARCHITECTURE.md` §queue state machine)
- **Atomic claim** — `UPDATE jobs SET status='running', locked_by=? WHERE id IN (SELECT … WHERE
  status='pending')` inside `BEGIN IMMEDIATE`; the same idea as Postgres `FOR UPDATE SKIP LOCKED`, using what
  SQLite has. A test asserts two workers cannot claim one job.
- **Idempotency key** — `intake:<enquiry_id>`, a `UNIQUE` column. For a webhook you'd hash source + contact +
  normalised message, because a re-delivery differs only in the timestamp.
- **Failure path** — exception caught → `queue.fail()` → attempts++, backoff 30/120/600 s → dead letter at max
  attempts → `job_failed` audit line with the exception type. **Retries are unconditional; idempotency is
  per-handler discipline, not queue-enforced.** Say that limitation yourself.
- **The failure nobody sees** — silence: a job that quietly processes 40 of 400 rows looks like success. That
  is why counts per run exist, and why alerting is named as missing.

### 3B — Data and schema (`ARCHITECTURE.md` §ER)
- 10 business tables (plus `schema_version`): contacts, matters, documents, enquiries, candidates,
  campaign_weeks, jobs, approvals, audit_log, systems_register. Two unique idempotency keys, one job index on
  `(status, run_after)`.
- **Numbered migrations** over "create if not exists" — in a real firm you never get a clean database again;
  `Database.version` tells you where you are.
- **WAL** — readers don't block the writer, which matters because the dashboard reads while a worker writes.
- **JSON columns** for `documents_missing` and `reasons` — read whole, never filtered by field; they are
  snapshots of a decision. Normalise if you ever query by document type.
- **Polymorphic approvals** (`kind` + `entity`, no FK per type) — one queue for all approvals, at the cost of
  referential integrity. A deliberate trade, and the kind of answer that reads as senior.
- **Where it breaks at 10×** — SQLite single-writer contention, synchronous request handling, no per-tenant
  filter. All three are Postgres-and-a-real-queue problems, not logic problems.

### 3C — Security (`SECURITY_REVIEW.md`)
- **No send function** — approval is a recorded decision. Not a flag to flip, no code path to review.
- **Auth** — shared token compared with `hmac.compare_digest`, writes refused when the env var is unset
  (closed by default). What is wrong: no per-user identity, so no per-person attribution or revocation.
- **Redaction before truncation** — IDs, passports, card sequences, `password=`/`token:`/`Bearer`. Order
  matters: truncating first let half an ID survive. That bug is a story you should be able to tell in 30 s.
- **Audit gap** — append-only rows with no mutation API, but SQLite can't stop someone editing the file.
  Production needs WORM storage plus hash chaining.
- **Pickle** — `pickle.load` executes code on load; safe only because the model is produced locally by
  `cli train`. From an untrusted source it is remote code execution.
- **PDPL position** — consent basis, records of processing, breach notification to the UAE Data Office. Before
  real client data: DPIA, retention schedule, approved environment.

### 3D — The model (`MODEL_CARD.md`)
- TF-IDF: 60k features, 1–2 grams, `min_df=2`, sublinear TF, accent stripping → **41 independent LinearSVCs**
  via `OneVsRestClassifier(class_weight="balanced")`. Trains in 13 s, runs offline, coefficients inspectable.
- Corpus: **CUAD v1, 510 contracts, 41 clause categories, CC BY 4.0, US drafting.**
- Split: **408 train / 102 test, by contract, seed 42.** Splitting by paragraph would leak one contract across
  both sides and inflate every score — that is the leakage answer, and they will ask it.
- **Micro 0.802 vs macro 0.561** — frequent clauses strong (Document Name 1.00, Parties 1.00, Governing Law
  0.97), rare ones near zero (support 2–7). Reporting only micro would flatter the model.
- **No validation split** — mildly wrong, written down. Hyperparameters chosen once by judgement, never tuned
  on test.
- **Location 22%** — presence is "is there evidence anywhere in 15,000 characters" (bag-of-words is well suited);
  location is "pick the same paragraph a lawyer picked" out of ~30 blocks with repeated vocabulary. Three
  measured attempts: 2,500-char blocks 28% → finer blocks 21% (worse, so scoring was the problem, not
  segmentation) → TF-IDF retrieval 32% @2,500 → shipped 600-char blocks at 22% for readable excerpts.
  Shipped behaviour now **abstains** below a confidence floor instead of guessing — say that, it is the most
  mature thing in the project.
- **Why not BERT** — 510 contracts, 41 labels, tiny per-class counts; linear + sparse is a strong baseline and
  cannot hallucinate. A fine-tuned transformer might win a few points on frequent classes and lose on speed,
  shipping and explainability.
- **Where an LLM belongs** — behind named seams (`rules.classify_area`, `_best_clause`), approved endpoint,
  no-training terms, output as a suggestion, prompt hash logged, rules fallback. Never for a decision that is
  client-facing or legal.
- **RAG** — internal knowledge (precedents, policies, clause banks), retrieve-then-generate, citations first.
  Evaluate: retrieval recall@k, answer correctness, **refusal rate on unanswerable questions** — "if it can't
  say I don't know, it isn't ready for a lawyer."
- **Biggest failure mode** — vocabulary drift: it has never seen UAE/DIFC drafting.

### 3E — Python and API (`INTERVIEW_MASTER_GUIDE.md` §1B)
- stdlib `http.server` + `sqlite3`, no framework: no dependency can break the demo, runs offline, readable in
  one sitting. The trade is recorded in ADR-001 — no async, no schema validation, thread-per-request.
- Dashboard rendered server-side with f-strings, `html.escape` on every value, no template engine.
- API and dashboard call the same functions, so a number cannot differ between them.
- ISO-8601 UTC strings everywhere — they sort as text, survive JSON, avoid naive-datetime bugs.
- **58 tests**, CI on a clean Linux runner including corpus download and training.

**Self-test (the 8 questions they will actually ask):** why idempotency keys in the schema · how the claim is
atomic · what happens on the third failure · micro vs macro and which one you'd put in a slide · why split by
contract · why location fails when presence works · what stops an email to a client · what's missing before
client data (four items, in order).

---

## Level 4 — Think like the person they're hiring (2–3 h)

Level 3 proves you can build. Level 4 proves you'd be useful on Monday. This is where a student and a
contractor are separated, and it is the level most candidates skip.

### 4A — The 90-day plan, five automations, named and measured
"A numeric deliverable is a request for a plan." Have this ready as a table in your head — five, not fifteen:

| # | Automation | Arm | Measure (baseline → after) | Guardrail | Week |
|---|---|---|---|---|---|
| 1 | Lead capture + instant first response | Altara Social | time to first reply vs their 24 h promise | draft only, human sends | 1–3 |
| 2 | Stalled-deal / follow-up watchdog | Social + PRIME | missed follow-ups per week | digest to owner, no outbound | 2–4 |
| 3 | Intake triage + document chase | Altara Law | minutes to first reply vs 1 business day; documents chased per matter | approval gate on anything client-facing | 4–6 |
| 4 | CV triage for client vacancies | PRIME HR | candidates per role screened; good candidates lost | ranks for a human, never auto-rejects | 5–8 |
| 5 | Campaign attribution reporting | Altara Social | reporting hours per month; spend with no revenue flagged | read-only from ads + Shopify | 7–10 |
| 6 (stretch) | Order/inventory sync | E-commerce | oversells and manual stock edits | staged, per-store | 10–12 |

Say the sequencing rule out loud: **volume × time × cost of error × how easily a human can check the output.**
Rules-based, high-volume, verifiable, reversible goes first. Anything deciding a client's rights goes last and
only with a human in the loop.

### 4B — Baseline before number
"We reply within one business day" is their own written SLA — quote it. Then: "I'd measure the current number
for two weeks before I claim an improvement. The 6.9 hours in my project is explicitly labelled an assumption,
because counted actions × stated allowances is not a measurement."

This is the single most senior-sounding thing you can do in the whole interview: **refuse to give a number
without a baseline.**

### 4C — Integration reality
Order you'd learn, and why: **M365/Graph first** (mail, files, calendar — where the work already lives), then
**Pipedrive** (the CRM the deals sit in), then **Shopify** (orders, inventory), then **Xero** (invoices),
then **Meta ads** (spend). API vs webhook vs polling: webhook when the source supports it (instant, cheap);
polling on a schedule when it doesn't; never a tight loop. Credentials in a secret store, never in code, least
privilege per integration — and the **systems register** records purpose, owner, integrations, permissions,
data access, status, because their advert asks for exactly that.

### 4D — Build vs buy (a senior discriminator)
n8n/Make/Zapier for glue with a clear trigger and a stable target, when a non-engineer needs to change it.
Code when there is state, retries, approvals, audit or a model. The honest answer: **buy the connector, build
the decision** — and keep the register either way, so nobody loses track of what's running.

### 4E — Regulated-sector answers
- No client or candidate data in consumer AI tools; a local model or an approved endpoint with no-training
  terms; the prompt hash logged, not the document.
- PDPL: consent basis, records of processing, breach notification; DPIA before scale.
- DIFC guidance note 2/2023: AI-generated content declared, the lawyer stays responsible. So AI output is a
  suggestion with a named reviewer.
- First hour of a breach: rotate the token so writes degrade to read-only, grep the audit log for redaction
  events in the window, identify what the payloads contained, follow their notification procedure.

### 4F — The seniority gap, said out loud
The band is entry-level (AED 10–12k) but the deliverables are not: five production automations, security
controls, governance register, measurable impact — **interviewed like a junior, judged like a contractor.**
Handle it by naming it calmly, not complaining: "I know the band is junior. I'm answering at the level the
mandate is written at, and I'd rather be measured on the 90-day outcome than on my title."

**Salary and logistics, prepared, not improvised:**
- Band is stated at AED 10,000–12,000/month — don't open below it, don't inflate, ask what the band is for the
  final scope.
- Visa: currently on a university-sponsored student visa; employment needs sponsorship or a transfer. Say it
  plainly and early — it is a routine question in the UAE, not a red flag.
- Start date: give a real one (course commitments), don't say "immediately" if it isn't true.

### 4G — Questions you ask them (pick three, never zero)
1. "Of the five automations in ninety days, which would make the most difference to you personally?"
2. "When an enquiry arrives today, what happens between the form and the first reply?"
3. "Who signs off before an automation touches client data?"
4. "What's running today — n8n, Make, scripts, or nothing yet?"
5. "What did the last attempt at automation get wrong?"
6. "What does success look like at ninety days, in a number?"

Question 5 is the strongest one in the room. It tells you what to avoid and it flatters nobody.

---

## Level 5 — Pressure (1 h, then drills)

### The four traps, with answers
- **"You're a student — why should we trust you with this?"**
  > "You shouldn't trust me with client data on day one. What you can check is that I built the layer that
  > makes a mistake visible: retries, idempotency, an approval gate and an audit trail — and that I publish
  > the numbers that make my own model look weak. That's the habit you're hiring; the domain knowledge I'll
  > pick up in your first two weeks."
- **"Did you build this with AI?"**
  > "I used an AI assistant as a pair — scaffolding, review of my reasoning. The design, the code, the tests,
  > the mistakes and the fixes are mine, and every number was reproduced from the code on my machine,
  > including the ones that embarrassed the project: 22% location accuracy, macro F1 0.56, a token bug that
  > kept CI red for forty minutes."
- **"Is this real client work?"**
  > "No — it's coursework-level engineering on public and synthetic data. No firm data, no client names, and
  > the research document is public sources only. What's real is the shape: intake, validate, decide, report,
  > log — which is the same shape your five automations have."
- **"What's your biggest weakness?"** Pick one that is true and cheap: "I under-estimate how long
  integration work takes, because I've never had to wait on someone else's API credentials. I now plan the
  integration first and the logic second."

### The when-you-don't-know script (use it, don't improvise)
> "I don't know that one. My guess would be X, and I'd check it against Y before I relied on it."

Three parts: **name it · state a hypothesis · name how you'd verify.** Interviewers score the third part.

### The failure story, ready in 45 seconds
Pick one and rehearse it with the number attached:
1. **Redaction after truncation** — a half-ID could survive. Fix: redact before truncating, and a test that
   asserts it. Lesson: order of operations is a security property.
2. **Token variable name** — locally green, CI red for 40 minutes, because the fix was never committed.
   Lesson: a completion report is not evidence; the repository is.
3. **"not urgent" matched `urgent`** — keyword matching lies. Lesson: negative cases belong in the test suite.
4. **Location accuracy 22% → abstain** — I stopped calling it a citation and shipped an abstention instead.
   Lesson: giving up a claim is cheaper than defending a wrong one.

### Drill shape (do this with someone, or out loud)
- **Round 1, 5 questions, 60 s each** — pitch, why this role, why this company, one workflow end to end,
  what's missing. No notes.
- **Round 2, 5 questions, hostile** — "isn't 22% broken?", "why not just use ChatGPT?", "you have no
  per-user auth, that's disqualifying", "why should we pay you over an experienced hire?", "what would you
  do if the automation emailed a client by mistake?"
- **Round 3, whiteboard** — draw the queue + approval + audit from memory, then add a seventh workflow and say
  what it would cost to add (~80 lines, inherits queue/audit/approval).

Anything that comes out badly in a round goes back to the level it belongs to. That is the loop.

---

## Runway — pick one line and follow only that

**3 days (5–6 h/day)**
- Day 1: Levels 0, 1, 2 in order. Finish with the 20-second and 2-minute gears said out loud twice.
- Day 2: Level 3, one subsection per 45 min, self-test after each. Demo runs end to end once, in the venv.
- Day 3: Level 4, write the five-automation table from memory, then Level 5 drills (all three rounds).

**1 day (before tomorrow)**
- 45 min: Level 1 (arms, promises, mandate).
- 60 min: Level 2 gears 1 and 2, plus the 90-second diagram.
- 90 min: Level 3D (the model — micro/macro/location) and 3C (no send function, redaction, audit gap).
- 60 min: Level 4A table + 4G questions + 4F salary/visa lines.
- 30 min: the four traps and the failure story, out loud.

**2 hours (today, soon)**
- 20 min: Level 1 — four arms, two promises, the mandate sentence.
- 25 min: gear 1 + gear 2 pitch, said three times, timed.
- 30 min: the model in one breath — TF-IDF → 41 LinearSVC → split by contract → micro 0.802 / macro 0.561 →
  location 22% labelled, now abstains.
- 20 min: "there is no send function" + what's missing (SSO, multi-tenancy, retention, alerting, connectors).
- 25 min: the five-automation table, week numbers only.

**Non-negotiables, whatever the runway:** the 20-second pitch · micro/macro/location numbers · "no send
function" · the four-item gap list · three questions to ask them.

---

## One-page cheat, in the order you'll need it

1. **Who they are** — law + recruitment + marketing + e-commerce on one back office. Their promises: 24 h
   (Social), 1 business day (Law).
2. **What they want** — five production automations in 90 days, register, human approval, no client data in
   consumer AI. Not advisory.
3. **Your pitch** — "a platform that runs six automations with a queue, an approval gate and an audit trail;
   the only AI is one clause classifier whose weak numbers I publish."
4. **Your numbers** — 58 tests · micro 0.802 / macro 0.561 · location 22% (now abstains) · 6.9 h is an
   assumption.
5. **Your safety line** — "there is no send function in the codebase."
6. **Your gap list** — SSO · multi-tenancy · retention (PDPL) · alerting · real connectors.
7. **Your plan** — the five, in week order, each with a measure against *their* stated promise.
8. **Your questions** — the 90-day priority · their current intake path · who signs off · what failed before.
