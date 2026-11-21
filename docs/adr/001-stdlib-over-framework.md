# ADR 001 — standard library over a web framework

**Status:** accepted · **Date:** 22 November 2026

## Context
The platform needs a dashboard, a JSON API and a job runner. FastAPI plus Celery plus Redis would be the
conventional stack.

## Decision
Use `http.server`, `sqlite3` and plain Python modules.

## Reasons
- The deployment target is a laptop or a single small server inside a firm with no platform team.
- Fewer moving parts means fewer silent failures — the failure mode of this project is "nobody notices it
  stopped", and every dependency is another thing that can stop unnoticed.
- It runs offline, with no credentials, which is what makes it demonstrable in an interview room.

## Consequences
- No async I/O and no built-in schema validation: request handling is manual and small.
- Concurrency is thread-per-request plus SQLite locking. Fine at this scale; wrong at a thousand times
  this scale.
- Moving to FastAPI later is a rewrite of `api/` only; the workflows and core do not change.
