# ADR 004 — there is no send function

**Status:** accepted · **Date:** 22 November 2026

## Context
An automation that drafts a client email is one line away from sending it. Sending would remove a human
from a client-facing decision at a law firm.

## Decision
No component can transmit. Drafts are rows with `status='pending_approval'`. A decision records who
decided, when and why. Transmission, if it ever exists, belongs to a separate service with its own
credentials, its own owner and its own entry in the systems register.

## Reasons
- The advertised role's own requirement: human approval must remain in place for client-facing, legal,
  employment and financial decisions.
- A missing capability is easier to defend than a disabled one. There is no configuration flag to
  accidentally flip, and no code path to review.
- It makes the approval queue the product rather than a feature.

## Consequences
- Someone has to click. That is the point.
- Every workflow must end in an approval row or a report, which turns out to be a useful design constraint:
  it forces each automation to produce something reviewable.
