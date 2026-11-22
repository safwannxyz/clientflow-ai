# Clean installation verification

## What was actually verified, and how

| Check | Method | Result |
|---|---|---|
| Dependencies install from a clean machine | GitHub Actions job on `ubuntu-latest`, fresh Python 3.12, `pip install -r requirements.txt` | **passing** (run `44961914523`) |
| Test suite on a clean machine | same CI run: `python -m unittest discover -s tests -t .` | **55 tests OK** |
| Corpus download + training in CI | same run: `fetch-cuad` then `train` | passed |
| CLI end to end | same run: `demo --reset` then `review 3` | passed |
| Local Windows run | Python 3.12.16, scikit-learn 1.9.1, numpy 2.5.5 | passed |
| Database initialisation, reset, dashboard, API | exercised locally, repeatedly | passed |

Not verified: a **fresh Windows virtual environment created from scratch on this machine**. The Linux CI
job is the clean-environment evidence; the Windows path below is the command set that was run here, not a
from-zero proof. Say that if asked — it is still a clean install on a machine that never had these files.

## The failure that actually happened, and what was done about it

Running the quick-start with a bare `python` on this machine produced:

```
ModuleNotFoundError: No module named 'sklearn'
```

That interpreter had no scikit-learn. Two fixes, both now in the repository:

1. **`bootstrap.ps1`** creates `.venv`, installs from `requirements.txt`, fetches, trains, seeds and runs
   the tests — one command, correct interpreter.
2. **Graceful degradation.** The clause model is now an optional dependency at import time. Without it the
   dashboard, API, queue, audit and five workflows still run; `/api/review` returns 503 with the reason,
   the dashboard shows "Model unavailable" plus the exact command, and `cli review` prints the fix instead
   of a traceback. A missing analysis library must not take the enquiry queue down with it.

Verified on both interpreters: the system Python (no scikit-learn) runs `demo`, `serve` and
`scripts/snapshot.py`; `.venv` runs everything including `train` and `review`.

## PowerShell, from nothing

```powershell
# 1. Get the code
git clone https://github.com/safwannxyz/clientflow-ai.git
cd clientflow-ai

# 2. Virtual environment + dependencies
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Data and model (about 40 MB download, ~15 s training)
python -m clientflow.cli fetch-cuad
python -m clientflow.cli train

# 4. Seed, execute the queue, read the summary
python -m clientflow.cli demo --reset

# 5. Verify
python -m unittest discover -s tests -t .
python -m clientflow.cli review 3

# 6. Serve
python -m clientflow.cli serve
#    http://127.0.0.1:8770/          dashboard
#    http://127.0.0.1:8770/?review=3 clause review
```

If `.venv\Scripts\Activate.ps1` is blocked by execution policy:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Expected output of step 4

```
seeded: {'enquiries': 24, 'matters': 14, 'documents': 21, 'campaign_weeks': 30, 'candidates': 25, 'register': 5}
run: {'processed': 4, 'failed': 0}

ClientFlow AI — overview
  enquiries           24
  pending approvals   3
  approved actions    0
  stalled matters     7
  queue   pending 0 · running 0 · done 4 · failed 0

What needs attention
  - 3 drafts are waiting for a human decision.
  - 7 matters have had no activity for over five days.
  - AED 40,410 of campaign spend has produced no revenue.
  - Estimated 6.9 hours of repetitive work replaced (assumption-based).
```

Numbers are deterministic (seed 7), so yours must match exactly. If they do not, something is different
about your environment — which is itself worth knowing before you demo.

## Failure handling to demonstrate on purpose

```powershell
# 1. Nothing to process
python -m clientflow.cli run          # {'processed': 0, 'failed': 0}

# 2. A duplicate delivery
python -m clientflow.cli run          # second time: job keys already seen, no duplicates

# 3. A dead letter (unknown job kind cannot be created from the CLI, so use Python)
python -c "from clientflow.core.db import open_db; from clientflow.core.queue import Queue; db=open_db('clientflow.db'); print(Queue(db).enqueue('does_not_exist', {}, key='bad-1', max_attempts=1))"
python -m clientflow.cli run          # failed: 1
python -m clientflow.cli jobs         # shows status failed with the error
```

## Uninstall / reset

```powershell
python -m clientflow.cli demo --reset   # rebuild the database only
Remove-Item clientflow.db*              # delete it entirely
```
