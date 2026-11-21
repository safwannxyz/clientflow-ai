# Interview pack — ClientFlow AI

Everything needed to explain and demonstrate this project. Start here.

| File | What it is for |
|---|---|
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

- Branch `main`, all commits pushed, **CI green** (`fix(security): read CLIENTFLOW_API_TOKEN…`).
- **55 tests passing** locally and in CI.
- Tested: build from clean Linux runner (CI), local Windows run (Python 3.12.16, scikit-learn 1.9.1),
  demo/reset, CLI, API, dashboard, queue retries and dead letter, approval decisions.
- Not tested: fresh Windows virtual environment created from scratch; public deployment; real connectors.

## The one-line positioning

> "A small platform that runs six automations with a queue, an approval gate and an audit trail — where the
> only AI is one contract classifier whose weak numbers I publish rather than hide."
