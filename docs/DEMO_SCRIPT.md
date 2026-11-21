# Demonstration scripts

Two versions. The seven-minute one is for a partner with limited patience; the fifteen-minute one is for
someone who wants to know how it is built. Both use only commands that exist in this repository.

## Before they sit down (60 seconds, do this alone)

```powershell
cd C:\Users\Safwan\Desktop\monday
python -m clientflow.cli demo --reset
python -m clientflow.cli serve
```

Leave running. Open two tabs:

- `http://127.0.0.1:8770/` — dashboard
- `http://127.0.0.1:8770/?review=3` — clause review

If anything fails to start, open `dist/index.html` instead and say so: it is the same page, static.

---

## The seven-minute version

| Time | What you do | What you say |
|---|---|---|
| 0:00–0:40 | Terminal: `python -m clientflow.cli stats` | "Six automations, one database, five of them run as jobs. What needs attention first: three drafts waiting for a human, seven stalled matters, forty thousand dirhams of spend with no revenue." |
| 0:40–1:40 | Dashboard top | "Every number here is either measured or labelled an assumption. The hours figure is an assumption and it says so — I would rather give you no number than an invented one." |
| 1:40–2:40 | Approval queue section | "Nothing has been sent. Each of these is a draft. There is no send function anywhere in the codebase — a decision is recorded, not transmitted. That is the whole design." |
| 2:40–3:40 | `?review=3` clause panel | "This is the only real AI in the project. 510 public contracts, 41 clause types, a linear model — micro F1 0.80, macro 0.56. The macro number is the honest one: frequent clauses work, rare ones don't." |
| 3:40–4:40 | Risk items on the same page | "Six listed rules: unlimited liability, no cap found, termination for convenience, governing law outside the UAE. A lawyer can disagree with one line rather than with the whole system." |
| 4:40–5:30 | Terminal: `python -m clientflow.cli run` twice | "Second run: nothing to do. Same enquiries, no duplicates — idempotency keys in the schema, not in my head." |
| 5:30–6:20 | Queue health + register | "Retries with backoff, dead letters stay visible, and a register of every automation with owner, data touched and approval gate — the thing your advert asks for." |
| 6:20–7:00 | Stop. Ask them | "Which of the five would you point me at first?" — then let them talk. |

**Do not** tour the folder. **Do not** explain the code until asked.

---

## The fifteen-minute technical walkthrough

| Time | Focus | Content |
|---|---|---|
| 0:00–1:30 | The shape | Core (db, queue, audit, security) → workflows (business logic only) → services (approvals, metrics, worker) → interfaces (dashboard, API, CLI). Show the mermaid diagram in `docs/ARCHITECTURE.md` if there is a screen. |
| 1:30–3:00 | A request end to end | Enquiry → `enqueue` with idempotency key → `claim` inside `BEGIN IMMEDIATE` → triage rules → contact + enquiry rows → approval row → audit line → `complete`. Mention the duplicate path returns early. |
| 3:00–4:30 | Failure handling | `fail()` → attempts++, backoff 30/120/600 s → dead letter at max. Show `cli jobs` with a failure. Say out loud: retries are unconditional; idempotency is per-handler discipline, not queue-enforced. |
| 4:30–6:00 | The approval gate | `Approvals.create` → pending → `decide` requires role `approver` → cannot re-decide → audited. Point out there is no send function, so the safety is structural. |
| 6:00–8:00 | The model | TF-IDF 60k features → 41 LinearSVCs → split by contract 408/102 → micro 0.802 / macro 0.561. Explain why split-by-contract matters and why there is no validation split (honest limitation). |
| 8:00–9:30 | Localisation and why it is weaker | Coverage/precision at four abstention floors (0.02→99%/23% … 0.16→44%/34%); shipped the abstaining version; labelled a candidate passage. The most impressive two minutes if delivered calmly. |
| 9:30–11:00 | Security model | Redaction before truncation (and the bug that taught me), roles, token closed-by-default, append-only audit, single-tenant gap, pickle risk. |
| 11:00–12:30 | Data model | ER diagram; two unique idempotency keys; polymorphic approvals (`kind` + `entity`) and what it costs. |
| 12:30–13:30 | Tests and CI | 55 tests; what each file covers; CI on a clean Ubuntu runner including corpus download and training; the token bug that failed CI for forty minutes while passing locally. |
| 13:30–15:00 | What I would do next | Document chase scheduler, SSO, multi-tenant filter, alerting, UAE evaluation set. Then ask them what they would prioritise. |

---

## The five strongest demonstration points

1. **There is no send function.** A reviewer cannot accidentally email a client, because the capability does
   not exist. Safety by absence beats safety by configuration.
2. **Idempotency you can watch.** Run the queue twice and the numbers do not move. Ten seconds, no explanation
   needed.
3. **The model, measured honestly.** Micro 0.80 against macro 0.56, with the rare-class table, plus a 22%
   location figure that is labelled rather than dressed up. Most candidates show one flattering number.
4. **Bugs found by auditing.** Token variable name (CI red for 40 minutes), redaction after truncation
   (half an ID could survive), "not urgent" matching `urgent`. Each one is a story about method, not luck.
5. **The systems register.** Purpose, owner, data touched, permissions, approval gate — a partner's governance
   question answered before it is asked.
