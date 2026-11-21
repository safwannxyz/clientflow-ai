# Runbook

## Health checks

```bash
python -m clientflow.cli stats     # numbers a human reads
python -m clientflow.cli jobs      # queue depth, failures, attempts
python -m clientflow.cli approvals # anything stuck waiting for a decision
curl -s localhost:8770/health      # {"status":"ok","schema":1}
```

## When the queue backs up

1. `cli jobs` — is it `pending` (nothing is processing) or `failed` (something is broken)?
2. `failed` with the same error: the dead-letter is a record of a real bug. Read `last_error`, fix,
   then `Queue.requeue_dead_letters()`.
3. `pending` growing: nothing is calling `run`. On a laptop that is expected; in deployment the
   scheduler is missing — restart it and confirm `done` starts moving.

## When a workflow misroutes

1. `audit_log` rows `intake_triaged` carry the matched keywords and the confidence.
2. Fix the rule in `workflows/rules.py`, add the failing sentence as a test, redeploy.
3. Never edit a row in `enquiries` to "fix" it — record a correction instead.

## When the clause model is wrong

1. `python -m clientflow.cli review <idx>` reproduces any finding from the corpus.
2. Weak classes have low support (2–16 examples). Either accept it for triage, or extend training data.
3. If you change preprocessing, retrain and **re-read the metrics** — do not trust a single run.

## Schema changes

Add a numbered migration to `MIGRATIONS` in `core/db.py`. Never edit an applied migration: existing
databases have already run it. `Database.version` tells you where a database is.

## Restoring the demo

```bash
python -m clientflow.cli demo --reset
```

Deterministic: same seed, same data, same numbers.

## What to do if a credential leaks

1. Rotate the token (`CLIENTFLOW_API_TOKEN`) — everything else degrades to read-only immediately.
2. Grep `audit_log` for `[SECRET-REDACTED]` events around the window; the log never stored the value.
3. If it reached a workflow payload, that payload is in `jobs.payload` — purge the row after exporting the
   incident record.
