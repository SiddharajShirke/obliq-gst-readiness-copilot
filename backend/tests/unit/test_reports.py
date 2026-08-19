from app.services.reports import generate_readiness_pdf


def test_generate_readiness_pdf_returns_pdf_bytes() -> None:
    content = generate_readiness_pdf(
        {
            "client": {"business_name": "Raj Traders", "gstin": "27RAJTR1234A1Z5"},
            "application": {"period_label": "April 2026", "status": "ready_for_ca_review"},
            "documents": {"required": 5, "received": 5, "reviewed": 4},
            "sales": {"invoice_count": 2, "taxable_value": 1000, "tax_total": 180},
            "purchases": {"invoice_count": 2, "taxable_value": 500, "tax_total": 90},
            "estimated_liability": 90,
            "open_issues": [],
            "reconciliation": {"matched": 2},
            "disclaimer": "Estimated from uploaded data and subject to CA review.",
        }
    )
    assert content.startswith(b"%PDF")
    assert len(content) > 500
