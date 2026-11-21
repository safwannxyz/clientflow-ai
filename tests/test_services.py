"""Services: metrics, approvals and the API."""

from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from clientflow.api.server import Handler
from clientflow.core.security import PermissionDenied
from clientflow.services import metrics, seed as seed_mod
from clientflow.services.approvals import Approvals
from tests.helpers import TempDB


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDB()
        seed_mod.seed_all(self.tmp.db)

    def tearDown(self):
        self.tmp.close()

    def test_overview_counts(self):
        ov = metrics.overview(self.tmp.db)
        self.assertGreater(ov["enquiries"]["total"], 0)
        self.assertIn("pending", ov["queue"])

    def test_hours_saved_is_labelled_an_assumption(self):
        hs = metrics.hours_saved(self.tmp.db)
        self.assertTrue(hs["assumption"])
        self.assertIn("basis", hs)
        self.assertGreater(hs["minutes"], 0)

    def test_attribution_flags_spend_with_no_revenue(self):
        at = metrics.attribution(self.tmp.db)
        flagged = [c for c in at["campaigns"] if c["flag"]]
        self.assertTrue(flagged, "seed data should include a campaign with no revenue")
        self.assertGreater(at["spend_with_no_return"], 0)

    def test_findings_are_sentences(self):
        lines = metrics.findings(self.tmp.db)
        self.assertTrue(all(isinstance(line, str) for line in lines))


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDB()
        self.approvals = Approvals(self.tmp.db)

    def tearDown(self):
        self.tmp.close()

    def test_create_and_decide(self):
        approval_id = self.approvals.create("acknowledgement", "ENQ-1", "Subject", "Body")
        decided = self.approvals.decide(approval_id, "approver", "approved", note="looks fine")
        self.assertEqual(decided["status"], "approved")
        self.assertEqual(decided["decision_note"], "looks fine")

    def test_viewer_cannot_approve(self):
        approval_id = self.approvals.create("acknowledgement", "ENQ-2", "S", "B")
        with self.assertRaises(PermissionDenied):
            self.approvals.decide(approval_id, "viewer", "approved")

    def test_cannot_decide_twice(self):
        approval_id = self.approvals.create("acknowledgement", "ENQ-3", "S", "B")
        self.approvals.decide(approval_id, "approver", "approved")
        with self.assertRaises(ValueError):
            self.approvals.decide(approval_id, "approver", "rejected")

    def test_decision_is_audited(self):
        approval_id = self.approvals.create("kyc_chase", "MAT-1", "S", "B")
        self.approvals.decide(approval_id, "approver", "rejected", note="wrong client")
        actions = {r["action"] for r in self.tmp.db.q("SELECT action FROM audit_log")}
        self.assertIn("approval_rejected", actions)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDB()
        seed_mod.seed_all(cls.tmp.db)
        Handler.db_path = str(cls.tmp.path)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.close()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read().decode()

    def test_health(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_stats(self):
        status, body = self._get("/api/stats")
        self.assertEqual(status, 200)
        self.assertIn("hours_saved", json.loads(body))

    def test_dashboard_renders(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("ClientFlow AI", body)
        self.assertIn("Approval queue", body)

    def test_write_requires_token(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/approvals/1/decide",
            data=json.dumps({"decision": "approved"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 401)

    def test_write_with_token_works(self):
        approval_id = Approvals(self.tmp.db).create("acknowledgement", "ENQ-9", "S", "B")
        os.environ["CLIENTFLOW_API_TOKEN"] = "test-token"
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/approvals/{approval_id}/decide",
                data=json.dumps({"decision": "approved", "note": "ok"}).encode(),
                headers={"Content-Type": "application/json",
                         "X-Clientflow-Token": "test-token"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as response:
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read().decode())
            self.assertEqual(payload["status"], "approved")
        finally:
            os.environ.pop("CLIENTFLOW_API_TOKEN", None)


if __name__ == "__main__":
    unittest.main()
