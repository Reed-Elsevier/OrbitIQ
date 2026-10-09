import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.data.sample_data import INVOICES, INVOICE_EXCEPTIONS, PAYMENTS
from backend.app.services.bedrock_analysis import BedrockAnalysisError, assess_evidence


class InvoiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("backend.app.services.invoice_analysis.assess_evidence", side_effect=BedrockAnalysisError("unavailable"))
    def test_fixture_facts_and_fallback_provenance(self, mocked_assessment) -> None:
        payload = self.client.get("/api/invoices/INV-1001/analyze").json()
        self.assertEqual(payload["analysis"]["source"], "rule_based_fallback")
        self.assertNotIn("ai_analysis", payload)
        self.assertEqual(payload["ai_status"], "unavailable")
        self.assertFalse(payload["ai_enabled"])
        checks = {check["code"]: check for check in payload["checks"]}
        self.assertEqual(checks["APPROVAL_LEVEL"]["status"], "pass")
        self.assertNotIn("APPROVAL_THRESHOLD", checks)
        self.assertEqual(checks["PO_AMOUNT_EXCEEDED"]["amount_over_po"], 1250.0)
        self.assertAlmostEqual(checks["PO_AMOUNT_EXCEEDED"]["percent_over_po"], 7.142857, places=5)
        self.assertEqual(checks["DUPLICATE_INVOICE"]["evidence_ids"], ["INV-1001", "INV-1003"])
        self.assertEqual(payload["duplicate_matches"][0]["invoice_date"], "2026-09-29")
        self.assertNotIn("prior invoice", checks["DUPLICATE_INVOICE"]["details"])
        self.assertIn("Supplier has 3 recorded historical exceptions.", payload["analysis"]["reasons"])
        self.assertNotIn("3-signal", payload["analysis"]["summary"])
        self.assertEqual(payload["final_decision"]["recommendation"], "ESCALATE")
        self.assertIn("DUPLICATE_INVOICE", payload["final_decision"]["triggered_by"])
        self.assertIn("PO_AMOUNT_EXCEEDED", payload["final_decision"]["triggered_by"])
        self.assertTrue(payload["final_decision"]["human_review_required"])
        self.assertEqual(mocked_assessment.call_args.args[0]["invoice"]["duplicate_matches"], payload["duplicate_matches"])

    @patch("backend.app.services.invoice_analysis.assess_evidence", side_effect=BedrockAnalysisError("unavailable"))
    def test_analysis_marks_fixture_data_as_synthetic_and_ai_as_disabled(self, mocked_assessment) -> None:
        response = self.client.get("/api/invoices/INV-1002/analyze")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["recommendation"], "ESCALATE")
        self.assertEqual(payload["data_source"], "synthetic demo fixtures")
        self.assertFalse(payload["ai_enabled"])

    @patch("backend.app.services.invoice_analysis.assess_evidence")
    def test_hard_gates_override_claude_auto_process(self, mocked_assessment) -> None:
        for invoice_id, expected in (("INV-1002", "ESCALATE"), ("INV-1003", "ESCALATE"), ("INV-1005", "ESCALATE"), ("INV-1004", "REVIEW")):
            with self.subTest(invoice_id=invoice_id):
                mocked_assessment.return_value = {
                    "summary": "No risk identified", "risk_level": "low",
                    "recommendation": "AUTO-PROCESS CANDIDATE", "reasons": ["Routine invoice"],
                    "evidence_ids": [invoice_id], "questions_for_analyst": [],
                }
                payload = self.client.get(f"/api/invoices/{invoice_id}/analyze").json()
                self.assertEqual(payload["recommendation"], expected)
                self.assertTrue(payload["ai_enabled"])
                self.assertEqual(payload["ai_status"], "success")
                self.assertEqual(payload["analysis"]["source"], "bedrock_claude")
                self.assertEqual(payload["analysis"], payload["ai_analysis"])
                self.assertEqual(payload["ai_analysis"]["evidence"], [invoice_id])
        evidence = mocked_assessment.call_args.args[0]
        self.assertEqual(set(evidence), {"invoice", "purchase_order", "supplier", "previous_invoices", "exceptions", "rule_flags"})
        self.assertTrue(evidence["previous_invoices"])

    @patch("backend.app.services.invoice_analysis.assess_evidence")
    def test_claude_escalation_is_not_downgraded(self, mocked_assessment) -> None:
        mocked_assessment.return_value = {
            "summary": "Investigate", "risk_level": "high", "recommendation": "ESCALATE",
            "reasons": ["Supplier concern"], "evidence_ids": ["SUP-318"], "questions_for_analyst": [],
        }
        payload = self.client.get("/api/invoices/INV-1004/analyze").json()
        self.assertEqual(payload["recommendation"], "ESCALATE")

    def test_unknown_invoice_returns_404(self) -> None:
        response = self.client.get("/api/invoices/unknown/analyze")

        self.assertEqual(response.status_code, 404)

    @patch("backend.app.services.invoice_analysis.assess_evidence")
    def test_ai_analysis_is_omitted_for_unsuccessful_assessments(self, mocked_assessment) -> None:
        for failure_code in ("NOT_CONFIGURED", "ACCESS_DENIED", "TRANSPORT_ERROR", "INVALID_RESPONSE", "INVALID_EVIDENCE"):
            with self.subTest(failure_code=failure_code):
                mocked_assessment.side_effect = BedrockAnalysisError("unavailable", failure_code)
                payload = self.client.get("/api/invoices/INV-1001/analyze").json()
                self.assertEqual(payload["ai_status"], "unavailable")
                self.assertEqual(payload["ai_failure_reason"], failure_code)
                self.assertNotIn("ai_analysis", payload)
                self.assertEqual(payload["analysis"]["source"], "rule_based_fallback")

    @patch("backend.app.services.invoice_analysis.assess_evidence")
    def test_clean_invoice_requires_valid_ai_before_auto_process(self, mocked_assessment) -> None:
        clean_invoice = {**INVOICES["INV-1004"], "gross_amount": 6000.0}
        assessment = {
            "summary": "Consistent", "risk_level": "low", "recommendation": "AUTO-PROCESS CANDIDATE",
            "reasons": ["Within PO"], "evidence_ids": ["PO-3301"], "questions_for_analyst": [],
        }
        with patch.dict(INVOICES, {"INV-1004": clean_invoice}), patch.dict(INVOICE_EXCEPTIONS, {"INV-1004": []}), patch.dict(PAYMENTS, {"INV-1004": {"status": "pending"}}):
            mocked_assessment.return_value = assessment
            payload = self.client.get("/api/invoices/INV-1004/analyze").json()
            self.assertEqual(payload["recommendation"], "AUTO-PROCESS CANDIDATE")
            mocked_assessment.side_effect = BedrockAnalysisError("unavailable")
            payload = self.client.get("/api/invoices/INV-1004/analyze").json()
            self.assertEqual(payload["recommendation"], "REVIEW")
            self.assertFalse(payload["ai_enabled"])

    @patch("backend.app.services.invoice_analysis.assess_evidence", side_effect=BedrockAnalysisError("unavailable"))
    def test_unknown_po_cannot_pass_hard_gate(self, mocked_assessment) -> None:
        with patch.dict(INVOICES, {"INV-1004": {**INVOICES["INV-1004"], "po_id": "PO-UNKNOWN"}}):
            payload = self.client.get("/api/invoices/INV-1004/analyze").json()
            self.assertEqual(payload["recommendation"], "ESCALATE")
            self.assertIn("INVALID_PO", mocked_assessment.call_args.args[0]["rule_flags"])

    @patch("backend.app.services.invoice_analysis.assess_evidence", side_effect=BedrockAnalysisError("unavailable"))
    def test_duplicate_requires_matching_loaded_record(self, mocked_assessment) -> None:
        with patch.dict(INVOICES, {"INV-1001": INVOICES["INV-1001"]}, clear=True):
            payload = self.client.get("/api/invoices/INV-1001/analyze").json()
        self.assertEqual(payload["duplicate_matches"], [])
        self.assertNotIn("DUPLICATE_INVOICE", payload["final_decision"]["triggered_by"])
        self.assertNotIn("DUPLICATE_INVOICE", mocked_assessment.call_args.args[0]["rule_flags"])
        self.assertEqual(payload["recommendation"], "REVIEW")

    @patch("backend.app.services.invoice_analysis.assess_evidence")
    def test_high_value_alone_does_not_invent_approval_limit(self, mocked_assessment) -> None:
        clean_invoice = {**INVOICES["INV-1004"], "gross_amount": 18000.0, "po_id": "PO-8812"}
        from backend.app.data.sample_data import PURCHASE_ORDERS

        mocked_assessment.return_value = {
            "summary": "Consistent", "risk_level": "low", "recommendation": "AUTO-PROCESS CANDIDATE",
            "reasons": ["Matching approval level"], "evidence_ids": ["INV-1004"], "questions_for_analyst": [],
        }
        with patch.dict(INVOICES, {"INV-1004": clean_invoice}), patch.dict(PURCHASE_ORDERS, {"PO-8812": {**PURCHASE_ORDERS["PO-8812"], "supplier_id": "SUP-318", "po_amount": 20000.0}}), patch.dict(INVOICE_EXCEPTIONS, {"INV-1004": []}), patch.dict(PAYMENTS, {"INV-1004": {"status": "pending"}}):
            payload = self.client.get("/api/invoices/INV-1004/analyze").json()
        self.assertEqual(payload["recommendation"], "AUTO-PROCESS CANDIDATE")
        self.assertEqual(payload["final_decision"]["triggered_by"], [])

    @patch("backend.app.services.invoice_analysis.assess_evidence", side_effect=BedrockAnalysisError("unavailable"))
    def test_different_approval_levels_require_verification_not_invented_hierarchy(self, mocked_assessment) -> None:
        payload = self.client.get("/api/invoices/INV-1003/analyze").json()
        approval_check = next(check for check in payload["checks"] if check["code"] == "APPROVAL_LEVEL")
        self.assertEqual(approval_check["status"], "warning")
        self.assertIn("director", approval_check["details"])
        self.assertIn("manager", approval_check["details"])
        self.assertNotIn("specialist", approval_check["details"])


class BedrockAssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = {
            "invoice": {"invoice_id": "INV-1004"}, "purchase_order": {"po_id": "PO-3301"},
            "supplier": {"supplier_id": "SUP-318"}, "previous_invoices": [],
            "exceptions": [], "rule_flags": [],
        }
        self.assessment = {
            "summary": "Consistent", "risk_level": "low", "recommendation": "AUTO-PROCESS CANDIDATE",
            "reasons": ["Within PO"], "evidence_ids": ["INV-1004", "PO-3301"], "questions_for_analyst": [],
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
        self.assertIn("anthropic.claude", request["modelId"])
        self.assertEqual(request["toolConfig"]["toolChoice"], {"tool": {"name": "submit_assessment"}})
        self.assertNotIn("test-placeholder", str(request))

    def test_invalid_fields_and_unknown_evidence_are_rejected(self) -> None:
        for field, value in (("risk_level", "safe"), ("evidence_ids", ["INVENTED"]), ("reasons", []), ("summary", " "), ("recommendation", "PAY"), ("extra", "unexpected")):
            with self.subTest(field=field):
                self.client.converse.return_value["output"]["message"]["content"][0]["toolUse"]["input"] = {**self.assessment, field: value}
                with self.assertRaises(BedrockAnalysisError):
                    assess_evidence(self.evidence)

    def test_truncated_response_is_rejected(self) -> None:
        self.client.converse.return_value["stopReason"] = "max_tokens"
        with self.assertRaises(BedrockAnalysisError):
            assess_evidence(self.evidence)

    def test_bedrock_error_is_sanitized(self) -> None:
        self.client.converse.side_effect = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "private detail"}}, "Converse")
        with self.assertRaises(BedrockAnalysisError) as captured:
            assess_evidence(self.evidence)
        self.assertNotIn("private detail", str(captured.exception))
        self.assertEqual(captured.exception.code, "ACCESS_DENIED")

    def test_missing_key_skips_bedrock(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(BedrockAnalysisError):
                assess_evidence(self.evidence)
        self.client_factory.assert_not_called()

    def test_duplicate_match_can_be_cited(self) -> None:
        self.evidence["invoice"]["duplicate_matches"] = [{"invoice_id": "INV-1003"}]
        self.evidence["rule_flags"] = ["DUPLICATE_INVOICE"]
        self.assessment["evidence_ids"] = ["INV-1003", "DUPLICATE_INVOICE"]
        self.assertEqual(assess_evidence(self.evidence)["evidence_ids"], ["INV-1003", "DUPLICATE_INVOICE"])

    def test_failure_is_logged_without_service_message_or_credentials(self) -> None:
        self.client.converse.side_effect = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "private detail test-placeholder"}}, "Converse")
        with self.assertLogs("backend.app.services.invoice_analysis", level="WARNING") as captured:
            payload = TestClient(app).get("/api/invoices/INV-1001/analyze").json()
        self.assertEqual(payload["ai_failure_reason"], "ACCESS_DENIED")
        self.assertEqual(payload["analysis"]["source"], "rule_based_fallback")
        self.assertIn("ACCESS_DENIED", str(captured.output))
        self.assertNotIn("private detail", str(captured.output))
        self.assertNotIn("test-placeholder", str(captured.output))


if __name__ == "__main__":
    unittest.main()
