# Security review

Adversarial read of the code, not a marketing page. Each item states what exists, what does not, and
whether it can be described as production-ready.

## 1. Authentication

**Exists:** a shared token on write endpoints (`X-Clientflow-Token`), compared with
`hmac.compare_digest` against `CLIENTFLOW_API_TOKEN`.
**Does not exist:** user accounts, sessions, MFA, per-user permissions, rate limiting, TLS.
**Verdict: not production-ready.** One shared secret means no attribution, no revocation per person and no
way to answer "who approved this". Real deployment needs the firm's identity provider.

> A real bug was found here during the audit: the token was read from `BUREAU_API_TOKEN` (a leftover name
> from an earlier prototype), so the documented variable was never read and every authenticated request
> returned 401. It failed in CI on every run for 40 minutes while passing locally, because the fix sat
> uncommitted. That is the single most useful thing in this document.

## 2. Environment variables

Only `CLIENTFLOW_API_TOKEN` (writes) and `CLIENTFLOW_DB` (path, used in the container) are read, at call
time, never at import. A test scans every source file for `sk-…`, `AKIA…`, `password="…"` patterns and
fails the build if one appears.

## 3. Sensitive information

Redaction happens **before** any value reaches `audit_log` or a preview:

| Pattern | Mask |
|---|---|
| Emirates ID (`784…`, `NNN-YYYY-NNNNNNN-N`) | `[ID-REDACTED]` |
| Passport (`A1234567`) | `[PASSPORT-REDACTED]` |
| Card sequences | `[CARD-REDACTED]` |
| `password=` / `token:` / `Bearer …` | `[SECRET-REDACTED]` |

Order matters and was a bug: truncating to 160 characters first let half an ID survive at the cut. Redact,
then truncate. Email and phone are deliberately **not** masked by default — they are usually the key you
trace a matter by — and can be masked on request.

## 4. KYC handling

- Documents are metadata only (`doc_type`, `received_at`, optional `expires`); no files, no images.
- The checker reports **completeness**, and states in its output that it does not verify authenticity.
- Chase emails are created as approval rows; nothing is transmitted.
- Real KYC packs are not used anywhere in this project. All records are synthetic, domains `example.ae`.

## 5. CV handling

- CV text is held in `candidates.cv_text`; scoring is a rubric over keywords, no model, no external call.
- Scores are stored **with reasons per criterion**, so a rejection can be explained.
- No real candidate data. Names invented.
- Gap: no retention policy, no deletion endpoint, no consent record — all required before real use.

## 6. Document handling (contracts)

- CUAD contracts are public SEC filings; no client document is stored.
- Inference is local: the trained model is a pickle on disk, loaded with `pickle.load`, which is safe only
  because the file is produced locally. A pickle from an untrusted source would be remote code execution —
  worth saying out loud if anyone asks about the `.pkl`.

## 7. Audit integrity

- `audit_log` is append-only in shape: the module exposes no update or delete, and a test asserts that.
- Every job, decision, escalation, redaction and failure writes a row with a named actor.
- **Gap:** SQLite has no row-level protection. Anyone with the file can edit history. Production needs
  append-only storage elsewhere (WORM bucket or a log service) and periodic hash chaining.

## 8. Approval enforcement

- `Approvals.decide` calls `require(role, "approve")`; `viewer` and `operator` raise `PermissionDenied`.
- A decision cannot be changed once made (tested).
- There is **no send function anywhere in the codebase** — the strongest control here is an absent
  capability, not a disabled one.

## 9. Retry behaviour

- Failures reschedule with 30 s / 120 s / 600 s backoff, then dead-letter at `max_attempts`.
- **Risk:** retries are unconditional. A non-idempotent side effect would repeat on retry. Today every
  handler writes rows keyed by an idempotency key, but that is discipline, not enforcement — the queue does
  not check before re-running.

## 10. Dead-letter queue

- `status='failed'` rows stay visible in `cli jobs` and on the dashboard; `requeue_dead_letters()` returns
  them to `pending` after a fix.
- **Gap:** no alerting. A dead letter is only discovered when somebody looks, which is exactly the failure
  mode this project claims to fix for other people.

## 11. Client data separation

- One database file, no tenant column. All four business arms share it.
- **Honest verdict:** this is a single-tenant design. Separating client data per arm (or per entity) would
  need a tenant key on every table plus row-level filters, and is a change to the schema, not a
  configuration flag.

## 12. What must not be presented as production-ready

1. Single shared token, no user identity.
2. No TLS inside the app; HTTP on localhost only.
3. No retention, deletion or consent handling (PDPL).
4. No alerting on dead letters or stalled runs.
5. Single-tenant data model.
6. Unconditional retries.
7. SQLite file access equals full compromise — and audit history is editable with it.
8. The clause model has not been evaluated on UAE drafting.

## 13. What is genuinely defensible today

- No send capability, so no client-facing action can happen without a human.
- Redaction enforced at the logging boundary, with tests.
- Least-privilege intent written into the systems register per automation.
- Closed-by-default writes when no token is configured.
- Every decision traceable to an actor and a timestamp.
