import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import decision_log, finance_data, invoice_analysis
from backend.app.services.bedrock_analysis import BedrockAnalysisError, assess_evidence
from backend.app.services.red_team_review import apply_red_gate, review_recommendation

TEST_INVOICE_ID = "INV0000001"


class InvoiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_curated_invoice_context_joins_required_tables(self) -> None:
        context = finance_data.get_invoice_context(TEST_INVOICE_ID)
        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context["invoice"]["invoice_id"], TEST_INVOICE_ID)
        self.assertEqual(context["supplier"]["supplier_id"], context["invoice"]["supplier_id"])
        self.assertEqual(context["po"]["po_id"], context["invoice"]["po_id"])
        self.assertTrue(context["invoice_lines"])
        self.assertTrue(context["payments"])

    def test_invoice_search_is_bounded_and_can_search_supplier(self) -> None:
        by_id = self.client.get(f"/api/invoices?query={TEST_INVOICE_ID}&limit=5")
        by_supplier = self.client.get("/api/invoices?query=Halbrook%20Health&limit=5")

        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(by_id.json()["total_count"], 120000)
        self.assertEqual(by_id.json()["items"][0]["invoice_id"], TEST_INVOICE_ID)
        self.assertEqual(by_supplier.json()["items"][0]["supplier_name"], "Halbrook Health K.K.")
        self.assertLessEqual(len(self.client.get("/api/invoices?limit=500").json()["items"]), 100)

    @patch("backend.app.services.invoice_analysis.assess_evidence", side_effect=BedrockAnalysisError("not configured", "NOT_CONFIGURED"))
    def test_analysis_uses_curated_data_and_safe_fallback(self, mocked_assessment) -> None:
        response = self.client.get(f"/api/invoices/{TEST_INVOICE_ID}/analyze")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data_source"], "curated synthetic finance CSVs")
        self.assertEqual(payload["invoice"]["invoice_id"], TEST_INVOICE_ID)
        self.assertTrue(payload["invoice_lines"])
        self.assertIn("payments", payload)
        self.assertIn("previous_invoices", payload)
        self.assertFalse(payload["ai_enabled"])
        self.assertEqual(payload["analysis"]["source"], "rule_based_fallback")
        self.assertNotIn("ai_analysis", payload)
        self.assertEqual(payload["recommendation"], "REVIEW")
        self.assertEqual(payload["red_team_review"]["status"], "PASS")
        self.assertEqual(payload["red_gate"]["status"], "REVIEW")
        self.assertTrue(payload["final_decision"]["human_review_required"])
        self.assertIn("invoice_lines", mocked_assessment.call_args.args[0])

    def test_unknown_invoice_returns_404(self) -> None:
        response = self.client.get("/api/invoices/INV-NOT-REAL/analyze")
        self.assertEqual(response.status_code, 404)

    @patch("backend.app.services.invoice_analysis.assess_evidence")
    def test_deterministic_duplicate_gate_overrides_claude(self, mocked_assessment) -> None:
        context = finance_data.get_invoice_context(TEST_INVOICE_ID)
        assert context is not None
        context["duplicate_matches"] = [{"invoice_id": "INV0000002"}]
        mocked_assessment.return_value = {
            "summary": "No issue found", "risk_level": "low", "recommendation": "AUTO-PROCESS CANDIDATE",
            "reasons": ["Routine"], "evidence_ids": [TEST_INVOICE_ID], "questions_for_analyst": [],
        }

        with patch.object(invoice_analysis, "get_invoice_context", return_value=context):
            payload = self.client.get(f"/api/invoices/{TEST_INVOICE_ID}/analyze").json()

        self.assertEqual(payload["recommendation"], "ESCALATE")
        self.assertEqual(payload["red_team_review"]["status"], "CHALLENGE")
        self.assertIn("DUPLICATE_INVOICE", payload["red_team_review"]["challenged_flags"])
        self.assertTrue(payload["red_gate"]["overrode_analyst"])
        self.assertIn("DUPLICATE_INVOICE", payload["final_decision"]["triggered_by"])

    def test_unknown_po_cannot_pass_hard_gate(self) -> None:
        context = finance_data.get_invoice_context(TEST_INVOICE_ID)
        assert context is not None
        context["invoice"]["po_id"] = "PO-UNKNOWN"
        context["po"] = None

        unsafe_assessment = {
            "summary": "Routine invoice", "risk_level": "low", "recommendation": "AUTO-PROCESS CANDIDATE",
            "reasons": ["No issues found"], "evidence_ids": [TEST_INVOICE_ID], "questions_for_analyst": [],
        }
        with (
            patch.object(invoice_analysis, "get_invoice_context", return_value=context),
            patch.object(invoice_analysis, "assess_evidence", return_value=unsafe_assessment),
        ):
            payload = self.client.get(f"/api/invoices/{TEST_INVOICE_ID}/analyze").json()

        self.assertEqual(payload["recommendation"], "ESCALATE")
        self.assertEqual(payload["red_team_review"]["status"], "CHALLENGE")
        self.assertIn("PO_NOT_FOUND", payload["final_decision"]["triggered_by"])

    def test_red_team_accepts_safe_recommendation_and_gate_never_lowers_it(self) -> None:
        review = review_recommendation("ESCALATE", [], True)
        gate = apply_red_gate("ESCALATE", review)

        self.assertEqual(review["status"], "PASS")
        self.assertEqual(gate["recommendation"], "ESCALATE")
        self.assertFalse(gate["overrode_analyst"])

    def test_decisions_are_persisted_and_can_be_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "decisions.db"
            with patch.object(decision_log, "DATABASE_PATH", database_path):
                response = self.client.post(f"/api/invoices/{TEST_INVOICE_ID}/decisions", json={"action": "approve"})
                history = self.client.get(f"/api/decisions?invoice_id={TEST_INVOICE_ID}")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["action"], "approve")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()), 1)
        self.assertEqual(history.json()[0]["invoice_id"], TEST_INVOICE_ID)

    def test_decision_requires_known_invoice_and_valid_action(self) -> None:
        unknown_invoice = self.client.post("/api/invoices/INV-NOT-REAL/decisions", json={"action": "approve"})
        invalid_action = self.client.post(f"/api/invoices/{TEST_INVOICE_ID}/decisions", json={"action": "pay"})
        self.assertEqual(unknown_invoice.status_code, 404)
        self.assertEqual(invalid_action.status_code, 422)


class BedrockAssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = {
            "invoice": {"invoice_id": TEST_INVOICE_ID, "duplicate_matches": []},
            "purchase_order": {"po_id": "PO0011179"},
            "supplier": {"supplier_id": "SUP002046"},
            "invoice_lines": [],
            "previous_invoices": [],
            "exceptions": [],
            "rule_flags": [],
        }
        self.assessment = {
            "summary": "Review invoice context", "risk_level": "medium", "recommendation": "REVIEW",
            "reasons": ["Approval policy is not provided"], "evidence_ids": [TEST_INVOICE_ID, "PO0011179"],
            "questions_for_analyst": ["Can the approval level be verified?"],
        }
        environment = patch.dict("os.environ", {"AWS_BEARER_TOKEN_BEDROCK": "test-placeholder", "AWS_REGION": "us-east-1"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        client_patch = patch("backend.app.services.bedrock_analysis.boto3.client")
        self.client_factory = client_patch.start()
        self.addCleanup(client_patch.stop)
        self.client = self.client_factory.return_value
        self.client.converse.return_value = {
            "stopReason": "tool_use",
            "output": {"message": {"content": [{"toolUse": {"name": "submit_assessment", "input": self.assessment}}]}},
        }

    def test_valid_structured_assessment(self) -> None:
        self.assertEqual(assess_evidence(self.evidence), self.assessment)
        request = self.client.converse.call_args.kwargs
        self.assertEqual(request["toolConfig"]["toolChoice"], {"tool": {"name": "submit_assessment"}})
        self.assertNotIn("test-placeholder", str(request))

    def test_unknown_evidence_is_rejected(self) -> None:
        self.assessment["evidence_ids"] = ["INVENTED-ID"]
        with self.assertRaises(BedrockAnalysisError):
            assess_evidence(self.evidence)

    def test_bedrock_error_is_sanitized(self) -> None:
        self.client.converse.side_effect = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "private detail"}}, "Converse")
        with self.assertRaises(BedrockAnalysisError) as captured:
            assess_evidence(self.evidence)
        self.assertNotIn("private detail", str(captured.exception))
        self.assertEqual(captured.exception.code, "ACCESS_DENIED")


if __name__ == "__main__":
    unittest.main()
