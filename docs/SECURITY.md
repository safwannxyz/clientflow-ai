# Security and confidentiality model

A law firm cannot be casual about this, so the boundaries are written down and enforced in code.

## 1. Nothing sends

There is no send function anywhere in ClientFlow. `services/approvals.py` can create a row and record a
decision. Emailing a client, messaging a candidate or filing a document is a separate system with its own
credentials and its own owner. The automation prepares; a person decides.

## 2. Redaction before logging

`core/security.py` masks, at the point of writing:
- Emirates ID patterns and 784-prefixed 15-digit numbers
- passport numbers
- card-number sequences
- credential strings: `password=…`, `token: …`, `Bearer …`

Order matters: **redact first, truncate second**. Truncating first let half an ID survive at the cut — a
bug caught by the test suite, not by reading the code.

Email addresses and phone numbers are *not* masked by default, because they are usually the key you trace
a matter by. They can be masked on request.

## 3. Roles

| Role | Can |
|---|---|
| viewer | read |
| operator | read, run jobs, create drafts |
| approver | read, run jobs, create drafts, approve |
| admin | everything |

Enforced in one place (`require(role, capability)`) rather than scattered conditionals. The API binds the
`approver` role to token-authenticated requests.

## 4. Tokens

Write endpoints require `X-Clientflow-Token` matching `CLIENTFLOW_API_TOKEN`. If the variable is unset,
**every write is refused** — the default is closed, not open. Tokens are read from the environment at call
time, never from a file in the repository, and a test scans the source for hardcoded secrets.

This is not authentication. It is the smallest control that means "not anyone who can reach the port".
Real deployment needs the firm's SSO, named users and per-user audit.

## 5. Audit

`audit_log` is append-only in shape: the module exposes no update or delete. Every job, decision, redaction
event and failure writes a row with a named actor (`system`, `worker:<id>`, or a human role).

## 6. Data minimisation in the demo

Synthetic records only. Names invented, domains `example.ae`, contract texts from the public CUAD corpus
(CC BY 4.0). The KYC checker reports completeness and explicitly not authenticity — a tool that claims to
verify identity documents is a liability, and the output says so in its own words.

## 7. Regulatory position (stated, not implied)

- **UAE PDPL** (Federal Decree-Law 45/2021) applies to this data class: consent basis, records of
  processing, breach notification. A DPIA is required before processing real client data.
- **DIFC** practice expects declarations of AI-generated content and keeps the lawyer responsible for it.
  That is why every review sheet carries a disclaimer as part of the returned object.
- **Retention** is undefined in the prototype and must be tied to the firm's schedule before any live use.

## 8. What an attacker gets

Local file access to `clientflow.db` is game over, and no code here changes that — it is why the UI binds
to `127.0.0.1`. In deployment: database encryption at rest, service-account-only access, network egress
restricted to the approved APIs, and the audit log shipped somewhere the application cannot rewrite.
