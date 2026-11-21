"""Core: schema, queue, audit, security."""

from __future__ import annotations

import unittest

from clientflow.core.audit import Audit
from clientflow.core.queue import DONE, FAILED, PENDING, Queue
from clientflow.core.security import (PermissionDenied, Role, assert_no_hardcoded_secrets,
                                      can, preview, redact, require, token_ok)
from clientflow.core.db import Database, open_db
from tests.helpers import TempDB


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDB()

    def tearDown(self):
        self.tmp.close()

    def test_schema_version(self):
        self.assertEqual(self.tmp.db.version, 1)

    def test_migrations_are_idempotent(self):
        before = self.tmp.db.table_counts()
        again = Database(str(self.tmp.path))          # reopening must not re-run DDL
        self.assertEqual(again.table_counts(), before)
        again.close()

    def test_expected_tables_exist(self):
        tables = set(self.tmp.db.table_counts())
        for name in ("enquiries", "matters", "documents", "candidates", "jobs",
                     "approvals", "audit_log", "systems_register"):
            self.assertIn(name, tables)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDB()
        self.q = Queue(self.tmp.db)

    def tearDown(self):
        self.tmp.close()

    def test_enqueue_and_claim(self):
        job_id = self.q.enqueue("intake", {"x": 1}, key="k1")
        self.assertIsNotNone(job_id)
        claimed = self.q.claim("w1")
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["kind"], "intake")

    def test_idempotency_key_prevents_duplicate(self):
        self.q.enqueue("intake", {"x": 1}, key="same")
        self.assertIsNone(self.q.enqueue("intake", {"x": 1}, key="same"))
        self.assertEqual(self.q.stats()["pending"], 1)

    def test_claim_is_exclusive(self):
        self.q.enqueue("intake", {}, key="once")
        first = self.q.claim("w1")
        second = self.q.claim("w2")
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_complete_marks_done(self):
        job_id = self.q.enqueue("intake", {}, key="c1")
        self.q.claim("w1")
        self.q.complete(job_id)
        self.assertEqual(self.q.stats()["done"], 1)

    def test_failure_reschedules_then_dead_letters(self):
        job_id = self.q.enqueue("intake", {}, key="f1", max_attempts=2)
        self.q.claim("w1")
        self.assertEqual(self.q.fail(job_id, "boom"), PENDING)   # retry scheduled
        self.assertEqual(self.q.stats()["pending"], 1)
        self.q.claim("w1")
        self.assertEqual(self.q.fail(job_id, "boom again"), FAILED)
        self.assertEqual(self.q.stats()["failed"], 1)

    def test_requeue_dead_letters(self):
        job_id = self.q.enqueue("intake", {}, key="r1", max_attempts=1)
        self.q.claim("w1")
        self.q.fail(job_id, "boom")
        self.assertEqual(self.q.requeue_dead_letters(), 1)
        self.assertEqual(self.q.stats()["pending"], 1)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDB()
        self.audit = Audit(self.tmp.db)

    def tearDown(self):
        self.tmp.close()

    def test_audit_redacts_identity_numbers(self):
        self.audit.log("system", "t", "e", "ID 784-1990-1234567-1 passport A1234567")
        detail = self.audit.recent(1)[0]["detail"]
        self.assertNotIn("784-1990-1234567-1", detail)
        self.assertIn("REDACTED", detail)

    def test_audit_redacts_credentials(self):
        self.audit.log("system", "t", "e", "password=hunter2 token: abc123")
        detail = self.audit.recent(1)[0]["detail"]
        self.assertNotIn("hunter2", detail)
        self.assertNotIn("abc123", detail)

    def test_audit_is_append_only_by_shape(self):
        self.assertTrue(self.audit.verify_append_only())
        self.assertFalse(hasattr(self.audit, "delete"))


class SecurityTests(unittest.TestCase):
    def test_redaction_variants(self):
        out = redact("id 784-1990-1234567-1, card 4111 1111 1111 1111, passport A1234567")
        self.assertNotIn("784-1990-1234567-1", out)
        self.assertNotIn("A1234567", out)
        self.assertIn("[CARD-REDACTED]", out)

    def test_preview_redacts_before_truncating(self):
        out = preview("x" * 150 + " 784-1990-1234567-1", limit=160)
        self.assertNotIn("784-1990", out)

    def test_roles(self):
        self.assertTrue(can("approver", "approve"))
        self.assertFalse(can("viewer", "approve"))
        with self.assertRaises(PermissionDenied):
            require("operator", "approve")

    def test_token_closed_by_default(self):
        self.assertFalse(token_ok(None))
        self.assertFalse(token_ok("anything"))

    def test_no_hardcoded_secrets_in_source(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "clientflow"
        for path in root.rglob("*.py"):
            assert_no_hardcoded_secrets(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
