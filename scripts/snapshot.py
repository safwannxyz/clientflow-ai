"""
snapshot.py — render the dashboard and a clause review to static HTML files.

Why: a static snapshot can be dropped on any host (GitHub Pages, Netlify drop, a
shared drive) without running Python, a database or a container. Use it when the
audience only needs to look, and keep the live service for people who need to try.

    python scripts/snapshot.py --out dist
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clientflow.api.server import render_dashboard          # noqa: E402
from clientflow.core.db import open_db                      # noqa: E402
from clientflow.services import seed as seed_mod            # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--db", default="clientflow.db")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    db = open_db(args.db)
    if db.scalar("SELECT COUNT(*) FROM enquiries") == 0:
        seed_mod.seed_all(db)
    db.close()

    db = open_db(args.db)
    (out / "index.html").write_text(render_dashboard(db, "snapshot"), encoding="utf-8")
    (out / "review.html").write_text(render_dashboard(db, "snapshot", 3), encoding="utf-8")
    db.close()
    print(f"wrote {out/'index.html'} and {out/'review.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
