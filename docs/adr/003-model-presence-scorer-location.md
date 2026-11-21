# ADR 003 — a model decides presence, a scorer decides location

**Status:** accepted · **Date:** 22 November 2026

## Context
Two questions per clause type: is it in the contract, and where. A span-extraction model (or an LLM) could
answer both.

## Decision
Presence comes from the trained classifier. Location comes from a transparent scorer that ranks clause
blocks by how much of the category's vocabulary they contain.

## Reasons
- A citation must be checkable. If a model says "clause 14", a lawyer has to verify it anyway — so the
  localisation should be something they can audit, not something they must trust.
- The scorer is a dozen lines with no weights to defend, and it degrades visibly: when it finds nothing it
  returns `None` rather than inventing a location.
- It keeps the expensive, evaluated part of the system narrowly scoped to the question that has ground
  truth in CUAD.

## Consequences
- When a clause is split across blocks or uses unusual vocabulary, the scorer may pick the wrong block.
  The excerpt is shown so the reader sees what was matched.
- If span-level evaluation later shows this is the weak link, replace it with a span model and keep the
  scorer as a baseline — the interface (`category -> (clause_no, excerpt)`) does not change.
