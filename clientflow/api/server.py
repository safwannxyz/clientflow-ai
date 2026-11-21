"""
server.py — JSON API plus a server-rendered dashboard.

Deliberately built on http.server from the standard library: no framework to
install, nothing to configure, and the whole thing runs on a laptop with no
network access. For a firm with no platform team, that is the point.

Routes
  GET  /                        dashboard (HTML)
  GET  /health                  liveness
  GET  /api/stats               metrics overview + hours saved
  GET  /api/enquiries           enquiry list
  GET  /api/approvals           approval queue
  GET  /api/jobs                queue health
  GET  /api/register            systems register
  GET  /api/attribution         campaign spend vs revenue
  GET  /api/review?idx=3        clause review of CUAD contract #3 (or ?text=...)
  POST /api/approvals/<id>/decide   {"decision": "approved"|"rejected", "note": "..."}

Writes require the X-Clientflow-Token header to match CLIENTFLOW_API_TOKEN.
If that variable is unset, every write is refused — closed, not open, by default.
"""

from __future__ import annotations

import html
import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..core.db import Database, open_db
from ..core.queue import Queue
from ..core.security import PermissionDenied, token_ok
from ..services import metrics
from ..services.approvals import Approvals
from ..workflows import clause_data, clause_review


# ---------------------------------------------------------------- helpers
def _badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{html.escape(str(text))}</span>'


def _priority_kind(priority: str) -> str:
    return "danger" if str(priority).startswith("urgent") else "ok"


def _table(headers: list[str], rows: list[list[str]], empty: str = "None") -> str:
    if not rows:
        return f'<p class="empty">{html.escape(empty)}</p>'
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_dashboard(db: Database, run_id: str, review_idx: int | None = None,
                     compare: bool = False) -> str:
    ov = metrics.overview(db)
    hs = metrics.hours_saved(db)
    at = metrics.attribution(db)
    notes = metrics.findings(db)

    enquiry_rows = []
    for r in db.q("""SELECT id, source, practice_area, priority, owner, status
                     FROM enquiries ORDER BY CASE priority WHEN 'urgent' THEN 0 ELSE 1 END, id
                     LIMIT 12"""):
        enquiry_rows.append([
            f"<b>{html.escape(r['id'])}</b>",
            html.escape(r["source"]),
            html.escape(r["practice_area"]),
            _badge(r["priority"], _priority_kind(r["priority"])),
            html.escape(r["owner"] or "—"),
            html.escape(r["status"]),
        ])

    approval_rows = []
    for a in Approvals(db).pending()[:10]:
        approval_rows.append([
            f"#{a['id']}", html.escape(a["kind"]), html.escape(a["entity"]),
            html.escape(a["subject"])[:70],
            _badge("pending", "warn"),
        ])

    campaign_rows = []
    for c in at["campaigns"][:8]:
        roas = "—" if c["roas"] is None else f"{c['roas']:.2f}x"
        cpl = "—" if c["cost_per_lead"] is None else f"AED {c['cost_per_lead']:,.0f}"
        campaign_rows.append([
            html.escape(c["campaign"]), f"AED {c['spend']:,.0f}", str(c["leads"]), cpl,
            f"AED {c['revenue']:,.0f}", roas,
            _badge(c["flag"], "danger") if c["flag"] else _badge("ok", "ok"),
        ])

    queue = ov["queue"]
    job_rows = [[html.escape(j["id"]), html.escape(j["kind"]),
                 _badge(j["status"], "ok" if j["status"] == "done" else "warn"),
                 f"{j['attempts']}/{j['max_attempts']}",
                 html.escape((j["last_error"] or "")[:60])] for j in Queue(db).recent(8)]

    register_rows = [[html.escape(r["name"]), html.escape(r["owner"]),
                      html.escape(r["data_touched"])[:54],
                      html.escape(r["approval_gate"])[:46],
                      _badge(r["status"], "muted")] for r in db.q(
        "SELECT * FROM systems_register ORDER BY id")]

    audit_rows = [[html.escape(a["ts"][11:19]), html.escape(a["action"]),
                   html.escape(a["entity"]), html.escape(a["detail"][:90])]
                  for a in db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT 10")]

    review_html = ""
    if review_idx is not None:
        docs = clause_data.load_cuad()
        if 0 <= review_idx < len(docs):
            doc = docs[review_idx]
            result = clause_review.review(doc.text, doc.title, annotated=doc.spans)
            def _where(f):
                ours = f"passage {f['clause_no']}" if f["clause_no"] else "none"
                if not compare:
                    return ours
                truth = f"passage {f['annotated_clause']}" if f["annotated_clause"] else "—"
                mark = "✓" if f["clause_no"] and f["clause_no"] == f["annotated_clause"] else "≠"
                return f"{ours} <span class='muted'>{mark} CUAD {truth}</span>"
            finding_rows = [[html.escape(f["category"]),
                             _where(f),
                             f"{f['score']:.2f}",
                             html.escape(f["excerpt"][:110])]
                            for f in result["findings"][:12]]
            flag_rows = [[_badge(f["severity"], "danger" if f["severity"] == "high" else "warn"),
                          html.escape(f["check"]), html.escape(f["detail"][:110])]
                         for f in result["risk_flags"]]
            review_html = f"""
      <h2>Clause review — {html.escape(doc.title[:70])}</h2>
      <p class="sub">{result['clauses_detected']} clause blocks · {result['characters']:,} characters ·
      {len(result['findings'])} clause types detected · located {result['located']}
      {f"· matched the lawyer annotation on {result['located_correctly']}" if compare and result['located_correctly'] is not None else ""}</p>
      <p class="sub">{"" if not compare else "Comparison view: add ?compare=1 to see this."}</p>
      <p class="sub">The passage is a pointer to verify, not a citation: a passage is returned for 44%
      of findings and 34% of those match the lawyer's choice — a pointer to verify, not a citation. Presence classification is the evaluated part; localisation is a
      convenience that is honest about its accuracy.</p>
      <div class="grid2">
        <div><h3>Detected clauses</h3>
          {_table(["Category", "Candidate passage", "Score", "Excerpt"], finding_rows)}</div>
        <div><h3>Risk items</h3>
          {_table(["Severity", "Check", "Why"], flag_rows, "No risk items matched")}</div>
      </div>
      <p class="disclaimer">{html.escape(result['disclaimer'])}</p>"""

    cards = [
        ("Enquiries", ov["enquiries"]["total"], "processed from four channels"),
        ("Awaiting approval", ov["approvals"]["pending"], "nothing sent automatically"),
        ("Stalled matters", ov["matters"]["stalled"], "no activity for 5+ days"),
        ("Queue failures", queue.get("failed", 0), f"{queue.get('pending', 0)} pending"),
        ("Est. hours saved", hs["hours"], "assumption-based, labelled"),
    ]
    card_html = "".join(
        f'<div class="card"><b>{html.escape(str(value))}</b><small>{html.escape(label)}'
        f'<br>{html.escape(sub)}</small></div>' for label, value, sub in cards)

    note_html = "".join(f"<li>{html.escape(n)}</li>" for n in notes)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>ClientFlow AI — group operations</title>
<style>
  :root {{--navy:#14283f;--teal:#0b7777;--ink:#253243;--muted:#5e6b78;--line:#dbe4e8;--bg:#f7fafb;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
        font:14px/1.55 "Segoe UI",system-ui,sans-serif}}
  .wrap{{max-width:1100px;margin:0 auto;padding:26px 20px 60px}}
  h1{{font-size:22px;color:var(--navy);margin:0}}
  h2{{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--navy);
      margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}}
  h3{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 6px}}
  .sub{{color:var(--muted);font-size:12.5px;margin:3px 0 0}}
  .note{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:16px 0}}
  .note ul{{margin:0;padding-left:18px}} .note li{{margin:3px 0}}
  .cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:16px 0}}
  .card{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
  .card b{{display:block;font-size:22px;color:var(--teal);letter-spacing:-.02em}}
  .card small{{color:var(--muted);font-size:11.5px;line-height:1.35;display:block;margin-top:3px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);
         border-radius:9px;overflow:hidden;font-size:12.6px}}
  th,td{{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
  th{{background:#eef4f6;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}
  .badge{{display:inline-block;font-size:10.5px;font-weight:600;padding:1px 7px;border-radius:999px;border:1px solid}}
  .badge.ok{{color:#0b6b4f;border-color:#b7e0d0;background:#eafaf3}}
  .badge.warn{{color:#8a5a00;border-color:#f0dca8;background:#fdf6e6}}
  .badge.danger{{color:#9b1c1c;border-color:#f0b4b4;background:#fdecec}}
  .badge.muted{{color:var(--muted);border-color:var(--line);background:#f3f6f7}}
  .muted{{color:var(--muted);font-size:11px}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  .empty{{color:var(--muted);font-size:12.5px;margin:6px 0}}
  .disclaimer{{color:#8a5a00;background:#fdf6e6;border:1px solid #f0dca8;border-radius:8px;
               padding:9px 12px;font-size:12.3px;margin-top:12px}}
  footer{{margin-top:26px;color:var(--muted);font-size:11.5px;border-top:1px solid var(--line);padding-top:12px}}
  @media (max-width:820px){{.cards{{grid-template-columns:repeat(2,1fr)}} .grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">

  <h1>ClientFlow AI <span class="sub">— group operations · run {html.escape(run_id)}</span></h1>
  <div class="note"><b>What needs attention</b><ul>{note_html}</ul></div>
  <div class="cards">{card_html}</div>

  <h2>Enquiries</h2>
  {_table(["Ref", "Source", "Practice area", "Priority", "Owner", "Status"], enquiry_rows)}

  <h2>Approval queue — nothing leaves without a human</h2>
  {_table(["#", "Kind", "Entity", "Subject", "Status"], approval_rows, "Nothing waiting")}

  {review_html}

  <h2>Campaign attribution — spend vs revenue</h2>
  {_table(["Campaign", "Spend", "Leads", "Cost/lead", "Revenue", "ROAS", ""], campaign_rows)}

  <h2>Queue health</h2>
  {_table(["Job", "Kind", "Status", "Attempts", "Last error"], job_rows, "No jobs yet")}

  <h2>Systems register</h2>
  {_table(["System", "Owner", "Data touched", "Approval gate", "Status"], register_rows)}

  <h2>Audit trail — most recent 10</h2>
  {_table(["Time", "Action", "Entity", "Detail"], audit_rows)}

  <footer>ClientFlow AI · independent portfolio proof-of-concept · synthetic data only ·
  no connection to Altara's systems · identity numbers and credentials are redacted before logging.</footer>
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    db_path = "clientflow.db"

    def _send(self, body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status: int = 200):
        self._send(json.dumps(payload, indent=2, default=str).encode(), status,
                   "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        db = open_db(self.db_path)
        try:
            if path in ("/", "/dashboard"):
                idx = int(query["review"][0]) if "review" in query else None
                compare = query.get("compare", ["0"])[0] in ("1", "true", "yes")
                return self._send(render_dashboard(db, uuid.uuid4().hex[:6], idx, compare).encode())
            if path == "/health":
                return self._json({"status": "ok", "schema": db.version})
            if path == "/api/stats":
                return self._json({"overview": metrics.overview(db),
                                   "hours_saved": metrics.hours_saved(db),
                                   "findings": metrics.findings(db)})
            if path == "/api/enquiries":
                return self._json([dict(r) for r in db.q(
                    "SELECT id, source, practice_area, priority, owner, status FROM enquiries "
                    "ORDER BY id LIMIT 200")])
            if path == "/api/approvals":
                return self._json(Approvals(db).pending())
            if path == "/api/jobs":
                return self._json(Queue(db).stats())
            if path == "/api/register":
                return self._json([dict(r) for r in db.q("SELECT * FROM systems_register")])
            if path == "/api/attribution":
                return self._json(metrics.attribution(db))
            if path == "/api/review":
                docs = clause_data.load_cuad()
                if "idx" in query:
                    idx = int(query["idx"][0])
                    if not (0 <= idx < len(docs)):
                        return self._json({"error": "idx out of range"}, 404)
                    doc = docs[idx]
                    return self._json(clause_review.review(doc.text, doc.title))
                if "text" in query:
                    return self._json(clause_review.review(query["text"][0]))
                return self._json({"error": "pass ?idx=N or ?text=..."}, 400)
            return self._json({"error": "not found", "path": path}, 404)
        finally:
            db.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if not token_ok(self.headers.get("X-Clientflow-Token")):
            return self._json({"error": "unauthorised: missing or wrong X-Clientflow-Token"}, 401)

        parts = [p for p in parsed.path.split("/") if p]
        db = open_db(self.db_path)
        try:
            if len(parts) == 4 and parts[:2] == ["api", "approvals"] and parts[3] == "decide":
                approval_id = int(parts[2])
                payload = json.loads(raw or b"{}")
                try:
                    row = Approvals(db).decide(
                        approval_id, role="approver",
                        decision=payload.get("decision", ""),
                        actor=payload.get("actor", "approver"), note=payload.get("note", ""))
                except (KeyError, ValueError, PermissionDenied) as exc:
                    return self._json({"error": str(exc)}, 400)
                return self._json(row)
            return self._json({"error": "not found"}, 404)
        finally:
            db.close()

    def log_message(self, *args):
        pass


def serve(db_path: str, port: int = 8770, host: str = "127.0.0.1") -> None:
    """Bind to 127.0.0.1 by default. 0.0.0.0 is only for a container where the
    platform terminates TLS and handles authentication in front of the app."""
    Handler.db_path = db_path
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"ClientFlow AI on http://{host}:{port}   (Ctrl+C to stop)")
    print(f"  dashboard   http://{host}:{port}/")
    print(f"  clause demo http://{host}:{port}/?review=3")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
