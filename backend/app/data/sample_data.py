INVOICES = {
    "INV-1001": {
        "invoice_id": "INV-1001",
        "supplier_id": "SUP-201",
        "supplier_name": "Northwind Industrial",
        "invoice_number": "INV-1001",
        "po_id": "PO-8812",
        "gross_amount": 18750.0,
        "net_amount": 15500.0,
        "tax_amount": 3250.0,
        "currency": "USD",
        "status": "pending",
        "approval_level": "manager",
        "due_date": "2026-10-12",
        "invoice_date": "2026-09-28",
        "channel": "EDI",
        "ocr_confidence": 0.96,
        "payment_status": "pending"
    },
    "INV-1002": {
        "invoice_id": "INV-1002",
        "supplier_id": "SUP-118",
        "supplier_name": "Blue Harbor Logistics",
        "invoice_number": "INV-1002",
        "po_id": None,
        "gross_amount": 8400.0,
        "net_amount": 7000.0,
        "tax_amount": 1400.0,
        "currency": "USD",
        "status": "exception",
        "approval_level": "manager",
        "due_date": "2026-10-09",
        "invoice_date": "2026-10-01",
        "channel": "email",
        "ocr_confidence": 0.87,
        "payment_status": "not_started"
    },
    "INV-1003": {
        "invoice_id": "INV-1003",
        "supplier_id": "SUP-201",
        "supplier_name": "Northwind Industrial",
        "invoice_number": "INV-1001",
        "po_id": "PO-8814",
        "gross_amount": 18480.0,
        "net_amount": 15280.0,
        "tax_amount": 3200.0,
        "currency": "USD",
        "status": "exception",
        "approval_level": "director",
        "due_date": "2026-10-11",
        "invoice_date": "2026-09-29",
        "channel": "portal",
        "ocr_confidence": 0.92,
        "payment_status": "pending"
    },
    "INV-1004": {
        "invoice_id": "INV-1004",
        "supplier_id": "SUP-318",
        "supplier_name": "Stonefield Manufacturing",
        "invoice_number": "INV-1004",
        "po_id": "PO-3301",
        "gross_amount": 6430.0,
        "net_amount": 5330.0,
        "tax_amount": 1100.0,
        "currency": "USD",
        "status": "review",
        "approval_level": "manager",
        "due_date": "2026-10-08",
        "invoice_date": "2026-09-25",
        "channel": "supplier_portal",
        "ocr_confidence": 0.81,
        "payment_status": "not_started"
    },
    "INV-1005": {
        "invoice_id": "INV-1005",
        "supplier_id": "SUP-447",
        "supplier_name": "Harborline Supply",
        "invoice_number": "INV-1005",
        "po_id": "PO-5403",
        "gross_amount": 9720.0,
        "net_amount": 8010.0,
        "tax_amount": 1710.0,
        "currency": "USD",
        "status": "exception",
        "approval_level": "manager",
        "due_date": "2026-10-13",
        "invoice_date": "2026-09-30",
        "channel": "EDI",
        "ocr_confidence": 0.94,
        "payment_status": "pending"
    }
}

PURCHASE_ORDERS = {
    "PO-8812": {
        "po_id": "PO-8812",
        "supplier_id": "SUP-201",
        "po_amount": 17500.0,
        "currency": "USD",
        "status": "approved",
        "approval_level": "manager"
    },
    "PO-8814": {
        "po_id": "PO-8814",
        "supplier_id": "SUP-201",
        "po_amount": 17250.0,
        "currency": "USD",
        "status": "approved",
        "approval_level": "manager"
    },
    "PO-3301": {
        "po_id": "PO-3301",
        "supplier_id": "SUP-318",
        "po_amount": 6300.0,
        "currency": "USD",
        "status": "approved",
        "approval_level": "manager"
    },
    "PO-5403": {
        "po_id": "PO-5403",
        "supplier_id": "SUP-447",
        "po_amount": 9800.0,
        "currency": "USD",
        "status": "approved",
        "approval_level": "manager"
    }
}

SUPPLIERS = {
    "SUP-201": {
        "supplier_id": "SUP-201",
        "supplier_name": "Northwind Industrial",
        "approval_threshold": "manager",
        "exception_history": 3,
        "last_invoice_total": 17320.0,
        "risk_band": "medium"
    },
    "SUP-118": {
        "supplier_id": "SUP-118",
        "supplier_name": "Blue Harbor Logistics",
        "approval_threshold": "manager",
        "exception_history": 1,
        "last_invoice_total": 7650.0,
        "risk_band": "low"
    },
    "SUP-318": {
        "supplier_id": "SUP-318",
        "supplier_name": "Stonefield Manufacturing",
        "approval_threshold": "manager",
        "exception_history": 0,
        "last_invoice_total": 6020.0,
        "risk_band": "low"
    },
    "SUP-447": {
        "supplier_id": "SUP-447",
        "supplier_name": "Harborline Supply",
        "approval_threshold": "manager",
        "exception_history": 2,
        "last_invoice_total": 8120.0,
        "risk_band": "medium"
    }
}

INVOICE_EXCEPTIONS = {
    "INV-1001": [
        {
            "exception_id": "EX-9901",
            "type": "Price mismatch",
            "description": "Invoice exceeds the approved PO amount by 7%.",
            "severity": "medium"
        }
    ],
    "INV-1002": [
        {
            "exception_id": "EX-9902",
            "type": "Missing PO",
            "description": "Invoice is missing a valid purchase order reference.",
            "severity": "high"
        }
    ],
    "INV-1003": [
        {
            "exception_id": "EX-9903",
            "type": "Duplicate invoice",
            "description": "Invoice number matches a previous invoice from the same supplier.",
            "severity": "high"
        }
    ],
    "INV-1004": [
        {
            "exception_id": "EX-9904",
            "type": "No payment reference",
            "description": "Payment record not found for the invoice and accounting is waiting on a vendor confirmation.",
            "severity": "medium"
        }
    ],
    "INV-1005": [
        {
            "exception_id": "EX-9905",
            "type": "Bank details changed",
            "description": "Bank detail update was flagged by the AP exception management process.",
            "severity": "high"
        }
    ]
}

PREVIOUS_INVOICES = {
    "SUP-201": [
        {"invoice_id": "INV-0931", "amount": 16850.0, "date": "2026-09-20"},
        {"invoice_id": "INV-0889", "amount": 17120.0, "date": "2026-09-10"},
        {"invoice_id": "INV-0807", "amount": 16400.0, "date": "2026-08-20"}
    ],
    "SUP-118": [
        {"invoice_id": "INV-0840", "amount": 7800.0, "date": "2026-09-08"}
    ],
    "SUP-318": [
        {"invoice_id": "INV-0674", "amount": 6100.0, "date": "2026-08-30"}
    ],
    "SUP-447": [
        {"invoice_id": "INV-0792", "amount": 7950.0, "date": "2026-09-03"}
    ]
}

PAYMENTS = {
    "INV-1001": {"payment_id": "PAY-1521", "status": "pending", "amount": 0.0},
    "INV-1002": {"payment_id": None, "status": "not_started", "amount": 0.0},
    "INV-1003": {"payment_id": "PAY-1522", "status": "pending", "amount": 0.0},
    "INV-1004": {"payment_id": None, "status": "not_started", "amount": 0.0},
    "INV-1005": {"payment_id": "PAY-1523", "status": "on_hold", "amount": 0.0}
}

INVOICE_IDS = list(INVOICES.keys())
