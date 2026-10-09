import unittest

from fastapi.testclient import TestClient

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


if __name__ == "__main__":
    unittest.main()
