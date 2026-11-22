"""
cli.py — one entry point for everything the platform does.

  python -m clientflow.cli demo            seed, run the queue, print a summary
  python -m clientflow.cli seed --reset    rebuild the synthetic database
  python -m clientflow.cli run             process due jobs once
  python -m clientflow.cli stats           metrics + findings
  python -m clientflow.cli review 3        clause review of CUAD contract #3
  python -m clientflow.cli train           (re)train the clause model
  python -m clientflow.cli fetch-cuad      download the CUAD corpus (39 MB)
  python -m clientflow.cli serve           dashboard on http://127.0.0.1:8770
  python -m clientflow.cli jobs            queue health
  python -m clientflow.cli approvals       pending approvals

Every command prints real output from the real database. There is no mock mode.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core.db import Database, open_db
from .core.queue import Queue
from .services import metrics, seed as seed_mod, worker
from .services.approvals import Approvals

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "clientflow.db"
CUAD_URL = ("https://huggingface.co/datasets/theatticusproject/cuad/resolve/main/"
            "CUAD_v1/CUAD_v1.json")
CUAD_PATH = ROOT / "clientflow" / "data" / "cuad" / "CUAD_v1.json"


def _db(args) -> Database:
    return open_db(args.db)


def cmd_seed(db: Database, reset: bool) -> tuple[Database, dict]:
    """Seed the database. Returns the (possibly reopened) handle.

    On Windows the file cannot be deleted while a connection is open, so the
    handle is closed before the unlink — and the caller must use the returned one.
    """
    if reset:
        db.close()
        Path(db.path).unlink(missing_ok=True)
        db = open_db(db.path)
    counts = seed_mod.seed_all(db)
    # queue one job per workflow so `run` has real work
    queue = Queue(db)
    matter = db.one("SELECT id, practice_area, client FROM matters LIMIT 1")
    if matter:
        queue.enqueue("kyc", {"matter_id": matter["id"],
                              "practice_area": matter["practice_area"],
                              "client_name": matter["client"]},
                      key=f"kyc:{matter['id']}")
    queue.enqueue("cv_screen", {"role_ref": "ROLE-AUTOMATION"}, key="cv:ROLE-AUTOMATION")
    queue.enqueue("watchdog", {}, key="watchdog:daily")
    queue.enqueue("attribution", {}, key="attribution:weekly")
    return db, counts


def cmd_run(db: Database) -> dict:
    return worker.run_until_empty(db)


def cmd_stats(db: Database) -> None:
    ov = metrics.overview(db)
    hs = metrics.hours_saved(db)
    print("ClientFlow AI — overview")
    print(f"  enquiries           {ov['enquiries']['total']}")
    print(f"  pending approvals   {ov['approvals']['pending']}")
    print(f"  approved actions    {ov['approvals']['approved']}")
    print(f"  stalled matters     {ov['matters']['stalled']}")
    q = ov["queue"]
    print(f"  queue   pending {q['pending']} · running {q['running']} · done {q['done']} · failed {q['failed']}")
    print()
    print("What needs attention")
    for line in metrics.findings(db):
        print("  -", line)
    print()
    print(f"Estimated hours replaced: {hs['hours']}  (assumption: {json.dumps(hs['basis'])})")


def cmd_review(db: Database, idx: int) -> None:
    from .workflows import clause_data, clause_review
    try:
        docs = clause_data.load_cuad()
    except FileNotFoundError:
        print("Corpus not found. Run: python -m clientflow.cli fetch-cuad")
        raise SystemExit(1)
    doc = docs[idx]
    result = clause_review.review(doc.text, doc.title)
    print(f"Contract: {result['title']}")
    print(f"{result['clauses_detected']} clause blocks · {result['characters']:,} characters\n")
    print(f"{'category':<44}{'clause':>8}{'match':>8}  excerpt")
    print("-" * 110)
    for f in result["findings"]:
        where = f"clause {f['clause_no']}" if f["clause_no"] else "—"
        print(f"{f['category'][:42]:<44}{where:>8}{f['match']:>8.2f}  {f['excerpt'][:48]}")
    print()
    if result["risk_flags"]:
        print("Risk items")
        for f in result["risk_flags"]:
            print(f"  [{f['severity']:<6}] {f['check']}: {f['detail'][:80]}")
    print()
    print("Key clauses not found:", ", ".join(result["key_clauses_absent"]) or "none")
    print(result["disclaimer"])


def cmd_train() -> None:
    from .workflows import clause_data, clause_model
    try:
        clause_model._require_sklearn()
    except clause_model.ModelUnavailable as exc:
        print(exc)
        raise SystemExit(1)
    try:
        docs_ = clause_data.load_cuad()
    except FileNotFoundError:
        print("Corpus not found. Run: python -m clientflow.cli fetch-cuad")
        raise SystemExit(1)
    bundle = clause_model.train(docs_)
    path = clause_model.save(bundle)
    m = bundle["metrics"]
    print(f"trained on {m['contracts_train']} contracts, tested on {m['contracts_test']}")
    print(f"micro F1 {m['micro_f1']} · macro F1 {m['macro_f1']} · {m['categories']} categories")
    print("saved:", path)
    print(clause_model.metrics_table(m))


def cmd_fetch_cuad() -> None:
    import urllib.request
    CUAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("downloading CUAD_v1.json (about 39 MB) from Hugging Face…")
    urllib.request.urlretrieve(CUAD_URL, CUAD_PATH)
    print("saved:", CUAD_PATH, f"({CUAD_PATH.stat().st_size / 1_048_576:.1f} MB)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clientflow", description="ClientFlow AI")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="rebuild the synthetic database")
    p_seed.add_argument("--reset", action="store_true")

    sub.add_parser("run", help="process due jobs once")
    sub.add_parser("stats", help="metrics and findings")
    sub.add_parser("jobs", help="queue health")
    sub.add_parser("approvals", help="pending approvals")
    sub.add_parser("train", help="(re)train the clause model")
    sub.add_parser("fetch-cuad", help="download the CUAD corpus")

    p_review = sub.add_parser("review", help="clause review of a CUAD contract")
    p_review.add_argument("idx", type=int)
    p_review.add_argument("--json", action="store_true")

    p_serve = sub.add_parser("serve", help="dashboard")
    p_serve.add_argument("--port", type=int, default=8770)
    p_serve.add_argument("--host", default="127.0.0.1",
                         help="127.0.0.1 by default; 0.0.0.0 only inside a container")

    p_demo = sub.add_parser("demo", help="seed, run queue, print summary")
    p_demo.add_argument("--reset", action="store_true")

    args = ap.parse_args(argv)

    if args.command == "fetch-cuad":
        cmd_fetch_cuad()
        return 0
    if args.command == "train":
        cmd_train()
        return 0
    if args.command == "review":
        db = _db(args)
        try:
            if args.json:
                from .workflows import clause_data, clause_review
                docs_ = clause_data.load_cuad()
                print(json.dumps(clause_review.review(docs_[args.idx].text, docs_[args.idx].title),
                                 indent=2))
            else:
                cmd_review(db, args.idx)
        except Exception as exc:                    # ModelUnavailable with the fix inside
            print(f"Clause review unavailable: {exc}")
            db.close()
            return 1
        db.close()
        return 0
    if args.command == "serve":
        from .api.server import serve
        serve(args.db, args.port, args.host)
        return 0

    db = open_db(args.db)
    try:
        if args.command == "seed":
            db, counts = cmd_seed(db, args.reset)
            print("seeded:", counts)
        elif args.command == "run":
            print("run:", cmd_run(db))
        elif args.command == "stats":
            cmd_stats(db)
        elif args.command == "jobs":
            print(json.dumps(Queue(db).stats(), indent=2))
            for job in Queue(db).recent(10):
                print(f"  {job['id']} {job['kind']:<12} {job['status']:<8} "
                      f"{job['attempts']}/{job['max_attempts']} {job['last_error'] or ''}")
        elif args.command == "approvals":
            rows = Approvals(db).pending()
            if not rows:
                print("nothing waiting")
            for row in rows:
                print(f"#{row['id']:<3} {row['kind']:<16} {row['entity']:<10} {row['subject']}")
        elif args.command == "demo":
            db, counts = cmd_seed(db, args.reset)
            print("seeded:", counts)
            print("run:", cmd_run(db))
            print()
            cmd_stats(db)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
