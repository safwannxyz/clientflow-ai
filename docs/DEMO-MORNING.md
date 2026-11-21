# Monday morning — what to run, in order

## Before you leave the flat

```bash
cd C:\Users\Safwan\Desktop\monday
python -m clientflow.cli demo --reset      # seed + run queue + summary (about 3 seconds)
python -m clientflow.cli serve             # leave this window open
```

Open two browser tabs: `http://127.0.0.1:8770/` and `http://127.0.0.1:8770/?review=3`.
If the clause model is missing, `fetch-cuad` then `train` first (~1 minute).

## The 3-minute demo

1. **Dashboard.** "Everything you see is synthetic. Six counters: enquiries, drafts waiting for a human,
   stalled matters, queue failures, estimated hours replaced."
2. **Approval queue.** "Nothing has been sent. Each of these is a draft. There is no send function in the
   code — an approval is a recorded decision, not an email."
3. **Clause review tab.** "This is real: 510 public contracts annotated by lawyers across 41 clause types.
   The model says which clauses are present; a separate scorer tells you which clause number to read; the
   risk rules are listed so you can disagree with one line rather than the whole system."
4. **Risk items.** "Unlimited liability, no cap found, termination for convenience, governing law outside
   the UAE. Each one is a rule you can read in thirty seconds."
5. **Numbers.** "Micro F1 0.80, macro 0.56 on a held-out 20%. The weak classes are the rare ones. I'd
   rather give you the real distribution than one flattering number."
6. **Queue + register.** "Retries, dead letters, and a register of every automation with its owner and
   permissions — the thing your advert asks for."
7. Stop. Do not tour the folder.

## If they ask "did you build this for us"

> "I read your advert and built a small version of what I'd propose, so we'd have something real to talk
> about. It's a prototype on public and synthetic data — no client information. The gap to production is
> the list in the README: real connectors, scheduler, SSO, retention."

## The three sentences to have ready

- **On safety:** "Nothing sends. Drafts wait for a person, and the audit log holds redacted previews, never
  full messages."
- **On the model:** "A model decides presence, not location — location has to be checkable by a human, so
  it's a scorer you can read."
- **On numbers:** "Every figure here is either measured on a held-out split or labelled as an assumption.
  The hours-saved number is the latter."

## Questions to ask them

1. "Of the five automations in ninety days, which would make the most difference to you personally?"
2. "When an enquiry arrives today, what happens between the form and the first reply?"
3. "Who signs off before an automation touches client data?"

## If the laptop dies

`docs/ALTARA_PUBLIC_RESEARCH.md`, the model metrics and this file are readable without running anything.
Talk about the queue design, the approval gate and the false-positive bugs you fixed — those are the
signal, not the dashboard.
