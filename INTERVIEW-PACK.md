# Interview pack — ClientFlow AI

Everything needed to explain and demonstrate this project. Start here.

| File | What it is for |
|---|---|
| `docs/PREP-LADDER.md` | **Start here if you are studying.** Beginner → advanced in 5 levels, with a runway for 3 days / 1 day / 2 hours. |
| `docs/INTERVIEW_QUICK_REFERENCE.md` | One page. Read this last, on the way in. |
| `docs/DEMO_SCRIPT.md` | 7-minute demo and 15-minute technical walkthrough, plus the five strongest points. |
| `docs/INTERVIEW_MASTER_GUIDE.md` | 90 questions with answers: project, Python/API, AI, automation, database, security, business, plus five hard follow-ups. |
| `docs/WORKFLOWS.md` | The six workflows traced to source: trigger, input, processing, DB, output, limits, approval. |
| `docs/ARCHITECTURE.md` | Diagrams: system, request sequence, queue state machine, approval gate, ER, API. |
| `docs/MODEL_CARD.md` | Dataset, architecture, training, metrics (reproduced), failure modes, appropriate use. |
| `docs/SECURITY_REVIEW.md` | Adversarial review and what must not be called production-ready. |
| `docs/CLEAN_INSTALL.md` | PowerShell from nothing, expected output, and failure paths to demo on purpose. |
| `docs/DEPLOY.md` | Local, static snapshot, container. |
| `docs/ALTARA_PUBLIC_RESEARCH.md` | Business context the design was aimed at (public sources only). |
| `docs/RUNBOOK.md` | What to do when something breaks. |
| `docs/adr/` | Four decisions worth arguing about. |

## Status at the time of this pack

- Branch `main`, all commits pushed, **CI green** (`fix: run without scikit-learn instead of not running at
  all`, run 44997467327).
- **58 tests passing** locally (re-verified 22 Nov) and in CI.
- Verified locally: project `.venv` (Python 3.14.6, scikit-learn 1.9.1), `demo --reset` seeding clean,
  CLI, dashboard, queue retries and dead letter paths, approval decisions.
- Not tested: public deployment; real connectors; any UAE contract evaluation.

## The one-line positioning

> "A small platform that runs six automations with a queue, an approval gate and an audit trail — where the
> only AI is one contract classifier whose weak numbers I publish rather than hide."
