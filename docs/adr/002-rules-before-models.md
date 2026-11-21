# ADR 002 — rules before models

**Status:** accepted · **Date:** 22 November 2026

## Context
Classification could be done by an LLM for practice area, urgency, document types and CV scoring.

## Decision
Every classification except clause presence is a keyword or weighted rule. Where a model would be
substituted, there is one named function (`rules.classify_area`, `rules.score_cv`) so the seam is explicit.

## Reasons
- Auditability: when a matter is misfiled, a rule can be read and corrected in a minute. A model's reason
  is a guess dressed as an explanation.
- Cost and latency: no API calls, no per-enquiry expense, no dependency on an approved endpoint.
- Data protection: nothing leaves the machine, which removes an entire category of PDPL exposure.
- Asymmetry of error: routing to the wrong lawyer costs a day; asking a human costs two minutes. The
  system should therefore fail toward asking.

## Consequences
- Rules will be brittle on unusual phrasing; the negation list ("not urgent") exists because of exactly
  that, found in testing.
- When rules plateau on real data, the replacement is a model behind the same function signature, with the
  rules kept as a fallback and as evaluation data.
