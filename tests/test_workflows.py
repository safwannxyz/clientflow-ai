"""Workflows: rules, intake, KYC, clause review."""

from __future__ import annotations

import unittest
from datetime import date

from clientflow.core.audit import Audit
from clientflow.core.queue import Queue
from clientflow.services.approvals import Approvals
from clientflow.services.worker import run_once
from clientflow.workflows import kyc as kyc_wf
from clientflow.workflows import rules
from clientflow.workflows.intake import ingest
from tests.helpers import ENQUIRY, TempDB


class RuleTests(unittest.TestCase):
    def test_classifies_known_areas(self):
        area, hits, conf = rules.classify_area("bounced cheque, police complaint")
        self.assertEqual(area, "Dispute Resolution")
        self.assertGreater(conf, 0.5)
        self.assertIn("cheque", hits)

    def test_unknown_text_is_not_guessed(self):
        area, hits, conf = rules.classify_area("hello, I have a question")
        self.assertEqual(area, "Unassigned")
        self.assertEqual(conf, 0.0)
        self.assertEqual(hits, [])

    def test_negated_urgency(self):
        self.assertEqual(rules.urgency("this is not urgent at all"), [])
        self.assertIn("urgent", rules.urgency("urgent: hearing tomorrow"))

    def test_missing_documents(self):
        missing = rules.missing_documents("Dispute Resolution", ["cheque_copy"])
        self.assertIn("emirates_id", missing)
        self.assertNotIn("cheque_copy", missing)

    def test_cv_scoring_ranks_stronger_cv_higher(self):
        weak, _ = rules.score_cv("I know some Excel.")
        strong, reasons = rules.score_cv(
            "Python pandas n8n webhook REST API LLM RAG SQL docker production clients")
        self.assertGreater(strong, weak)
        self.assertTrue(all(r["criterion"] for r in reasons))

    def test_arabic_detected(self):
        self.assertEqual(rules.language_of("أرغب في استشارة بخصوص عقد العمل"), "ar")


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDB()

    def tearDown(self):
        self.tmp.close()

    def test_intake_records_and_drafts(self):
        result = ingest(self.tmp.db, ENQUIRY)
        self.assertEqual(result["outcome"], "recorded")
        self.assertEqual(result["practice_area"], "Corporate & Commercial")
        self.assertIsNotNone(result["approval_id"])
        pending = Approvals(self.tmp.db).pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["status"], "pending")

    def test_intake_is_idempotent(self):
        ingest(self.tmp.db, ENQUIRY)
        second = ingest(self.tmp.db, ENQUIRY)
        self.assertEqual(second["outcome"], "duplicate")
        self.assertEqual(self.tmp.db.scalar("SELECT COUNT(*) FROM enquiries"), 1)

    def test_arabic_enquiry_escalates_and_does_not_draft(self):
        enquiry = dict(ENQUIRY, id="ENQ-AR", message="أرغب في استشارة بخصوص عقد العمل والراتب")
        result = ingest(self.tmp.db, enquiry)
        self.assertEqual(result["status"], "needs_human")
        self.assertIsNone(result["approval_id"])

    def test_urgent_priority(self):
        enquiry = dict(ENQUIRY, id="ENQ-URG",
                       message="Urgent: cheque bounced, hearing on Thursday")
        result = ingest(self.tmp.db, enquiry)
        self.assertEqual(result["priority"], "urgent")

    def test_audit_rows_written(self):
        ingest(self.tmp.db, ENQUIRY)
        actions = {r["action"] for r in Audit(self.tmp.db).recent(20)}
        self.assertIn("intake_triaged", actions)
        self.assertIn("approval_requested", actions)


class KycTests(unittest.TestCase):
    def test_complete_pack(self):
        docs = [{"type": t} for t in rules.DOCUMENT_CHECKLIST["Employment & Labour"]]
        report = kyc_wf.check_pack("MAT-1", "Employment & Labour", docs)
        self.assertTrue(report["complete"])
        self.assertEqual(report["missing"], [])

    def test_missing_document(self):
        report = kyc_wf.check_pack("MAT-2", "Employment & Labour",
                                   [{"type": "passport"}])
        self.assertIn("emirates_id", report["missing"])
        self.assertFalse(report["complete"])

    def test_expiring_document(self):
        today = date(2026, 11, 22)
        report = kyc_wf.check_pack("MAT-3", "Employment & Labour",
                                   [{"type": t} for t in rules.DOCUMENT_CHECKLIST["Employment & Labour"]]
                                   + [{"type": "emirates_id", "expires": "2026-12-03"}],
                                   today=today)
        self.assertEqual(len(report["expiring"]), 1)
        self.assertFalse(report["complete"])

    def test_expired_document(self):
        today = date(2026, 11, 22)
        report = kyc_wf.check_pack("MAT-4", "Employment & Labour",
                                   [{"type": t} for t in rules.DOCUMENT_CHECKLIST["Employment & Labour"]]
                                   + [{"type": "passport", "expires": "2026-01-01"}],
                                   today=today)
        self.assertEqual(len(report["expired"]), 1)

    def test_name_mismatch(self):
        report = kyc_wf.check_pack("MAT-5", "Employment & Labour",
                                   [{"type": "passport", "holder": "A Person"},
                                    {"type": "emirates_id", "holder": "B Person"}])
        self.assertTrue(report["name_mismatch"])

    def test_chase_email_lists_what_is_missing(self):
        report = kyc_wf.check_pack("MAT-6", "Employment & Labour", [])
        draft = kyc_wf.chase_email(report, "Client")
        self.assertIn("MAT-6", draft["subject"])
        self.assertIn("emirates id", draft["body"].lower())
        self.assertEqual(draft["kind"], "kyc_chase")


class ClauseReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from clientflow.workflows import clause_data, clause_model
        try:
            cls.docs = clause_data.load_cuad()
            cls.bundle = clause_model.load()
        except (FileNotFoundError, OSError):
            raise unittest.SkipTest("CUAD corpus or trained model not present "
                                    "(run: fetch-cuad && train)")

    def test_review_returns_findings_with_clause_numbers(self):
        from clientflow.workflows.clause_review import review
        doc = self.docs[3]
        result = review(doc.text, doc.title)
        self.assertGreater(len(result["findings"]), 0)
        self.assertTrue(any(f["clause_no"] for f in result["findings"]))

    def test_governing_law_false_positive_is_not_flagged(self):
        """"governed by separate agreement" is not a governing-law clause."""
        from clientflow.workflows.clause_review import risk_flags
        text = "The parties will act as governed by separate agreement(s) between them."
        checks = {f["check"] for f in risk_flags(text, [])}
        self.assertNotIn("Governing law outside the UAE", checks)

    def test_foreign_governing_law_is_flagged(self):
        from clientflow.workflows.clause_review import risk_flags
        text = "This Agreement shall be governed by the laws of the State of Kansas."
        flags = risk_flags(text, [])
        self.assertIn("Governing law outside the UAE", {f["check"] for f in flags})

    def test_uae_governing_law_is_not_flagged(self):
        from clientflow.workflows.clause_review import risk_flags
        text = "This Agreement is governed by the laws of the Dubai International Financial Centre."
        checks = {f["check"] for f in risk_flags(text, [])}
        self.assertNotIn("Governing law outside the UAE", checks)

    def test_review_always_carries_disclaimer(self):
        from clientflow.workflows.clause_review import review
        result = review("Short agreement with no clauses at all.")
        self.assertIn("Not legal advice", result["disclaimer"])

    def test_split_clauses_offsets_are_consistent(self):
        from clientflow.workflows.clause_data import split_clauses
        text = "1. First clause text here.\n\n2. Second clause text here.\n\n3. Third."
        blocks = split_clauses(text)
        for b in blocks:
            self.assertLessEqual(b["start"], b["end"])
            self.assertGreaterEqual(b["start"], 0)
        self.assertEqual(blocks[0]["clause_no"], 1)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDB()

    def tearDown(self):
        self.tmp.close()

    def test_unknown_handler_is_recorded_as_failure(self):
        Queue(self.tmp.db).enqueue("nonexistent", {}, key="bad", max_attempts=1)
        report = run_once(self.tmp.db)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["queue"]["failed"], 1)

    def test_intake_job_through_queue(self):
        Queue(self.tmp.db).enqueue("intake", ENQUIRY, key="intake:ENQ-T1")
        report = run_once(self.tmp.db)
        self.assertEqual(report["processed"], 1)
        self.assertEqual(self.tmp.db.scalar("SELECT COUNT(*) FROM enquiries"), 1)


if __name__ == "__main__":
    unittest.main()
