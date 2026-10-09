import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.data.sample_data import INVOICES, INVOICE_EXCEPTIONS, PREVIOUS_INVOICES, PURCHASE_ORDERS
from backend.app.services import decision_log
from backend.app.main import app


class InvoiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_analysis_marks_fixture_data_as_synthetic_and_ai_as_disabled(self) -> None:
        response = self.client.get("/api/invoices/INV-1002/analyze")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["recommendation"], "ESCALATE")
        self.assertEqual(payload["data_source"], "synthetic demo fixtures")
        self.assertFalse(payload["ai_enabled"])

    def test_unknown_invoice_returns_404(self) -> None:
        response = self.client.get("/api/invoices/unknown/analyze")

        self.assertEqual(response.status_code, 404)

    def test_unknown_purchase_order_is_not_marked_valid(self) -> None:
        invoice = {**INVOICES["INV-1004"], "po_id": "PO-UNKNOWN"}

        with patch.dict(INVOICES, {"INV-1004": invoice}):
            response = self.client.get("/api/invoices/INV-1004/analyze")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        po_check = next(check for check in payload["checks"] if check["code"].startswith("PO_"))
        self.assertEqual(po_check["code"], "PO_NOT_FOUND")
        self.assertEqual(po_check["status"], "fail")
        self.assertEqual(payload["recommendation"], "ESCALATE")

    def test_near_duplicate_in_previous_history_requires_review(self) -> None:
        invoice = {
            **INVOICES["INV-1004"],
            "gross_amount": 6200.0,
            "invoice_number": "INV-NEAR-TEST",
        }
        previous_invoices = {
            "SUP-318": [{"invoice_id": "INV-OLD", "amount": 6150.0, "date": "2026-09-24"}]
        }

        with (
            patch.dict(INVOICES, {"INV-1004": invoice}),
            patch.dict(INVOICE_EXCEPTIONS, {"INV-1004": []}),
            patch.dict(PREVIOUS_INVOICES, previous_invoices),
        ):
            response = self.client.get("/api/invoices/INV-1004/analyze")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        near_duplicate = next(check for check in payload["checks"] if check["code"] == "NEAR_DUPLICATE")
        self.assertEqual(near_duplicate["status"], "warning")
        self.assertEqual(payload["recommendation"], "REVIEW")

    def test_high_value_approval_threshold_cannot_remain_auto_process_candidate(self) -> None:
        invoice = {
            **INVOICES["INV-1004"],
            "gross_amount": 16000.0,
            "invoice_number": "INV-THRESHOLD-TEST",
        }
        purchase_order = {**PURCHASE_ORDERS["PO-3301"], "po_amount": 20000.0}

        with (
            patch.dict(INVOICES, {"INV-1004": invoice}),
            patch.dict(PURCHASE_ORDERS, {"PO-3301": purchase_order}),
            patch.dict(INVOICE_EXCEPTIONS, {"INV-1004": []}),
        ):
            response = self.client.get("/api/invoices/INV-1004/analyze")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        threshold_check = next(check for check in payload["checks"] if check["code"] == "APPROVAL_THRESHOLD")
        self.assertEqual(threshold_check["status"], "warning")
        self.assertEqual(payload["recommendation"], "REVIEW")
        self.assertEqual(payload["ai_analysis"]["recommendation"], "REVIEW")

    def test_blocking_checks_remain_escalations_in_analysis_summary(self) -> None:
        for invoice_id in ("INV-1002", "INV-1003", "INV-1005"):
            with self.subTest(invoice_id=invoice_id):
                response = self.client.get(f"/api/invoices/{invoice_id}/analyze")

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["recommendation"], "ESCALATE")
                self.assertEqual(payload["ai_analysis"]["recommendation"], "ESCALATE")

    def test_decisions_are_persisted_and_can_be_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "decisions.db"
            with patch.object(decision_log, "DATABASE_PATH", database_path):
                response = self.client.post(
                    "/api/invoices/INV-1001/decisions",
                    json={"action": "approve"},
                )
                history = self.client.get("/api/decisions?invoice_id=INV-1001")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["action"], "approve")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()), 1)
        self.assertEqual(history.json()[0]["invoice_id"], "INV-1001")

    def test_decision_requires_known_invoice_and_valid_action(self) -> None:
        unknown_invoice = self.client.post(
            "/api/invoices/unknown/decisions",
            json={"action": "approve"},
        )
        invalid_action = self.client.post(
            "/api/invoices/INV-1001/decisions",
            json={"action": "pay"},
        )

        self.assertEqual(unknown_invoice.status_code, 404)
        self.assertEqual(invalid_action.status_code, 422)


if __name__ == "__main__":
    unittest.main()
