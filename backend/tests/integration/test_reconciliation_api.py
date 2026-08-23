import asyncio
import json
from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
RAJ_CLIENT_ID = "20000000-0000-0000-0000-000000000001"


def make_purchase_xlsx() -> bytes:
    frame = pd.DataFrame(
        [
            {
                "Invoice No": "P-1",
                "Invoice Date": "2026-04-10",
                "Supplier GSTIN": "27ABCDE1234F1Z5",
                "Taxable Amount": 1000,
                "CGST": 90,
                "SGST": 90,
                "Total": 1180,
            },
            {
                "Invoice No": "P-2",
                "Invoice Date": "2026-04-11",
                "Supplier GSTIN": "27ABCDE1234F1Z5",
                "Taxable Amount": 2000,
                "CGST": 180,
                "SGST": 180,
                "Total": 2360,
            },
        ]
    )
    output = BytesIO()
    frame.to_excel(output, index=False)
    return output.getvalue()


def test_reconciliation_and_readiness_exports() -> None:
    created = client.post(
        f"/api/v1/clients/{RAJ_CLIENT_ID}/applications",
        headers=AUTH,
        json={
            "financial_year": "2026-27",
            "period_label": "April 2026 export test",
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "filing_frequency": "monthly",
            "due_date": "2026-05-20",
        },
    )
    assert created.status_code == 201, created.text
    app_id = created.json()["id"]
    purchase = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=AUTH,
        data={"requirement_type": "purchase_register"},
        files={
            "file": (
                "Purchase_Register_April.xlsx",
                make_purchase_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert purchase.status_code == 201

    store = get_store()
    purchase_records = asyncio.run(store.list_rows("invoice_records", {"application_id": app_id}))
    for row in purchase_records:
        asyncio.run(store.update_row("invoice_records", row["id"], {"review_status": "approved"}))
    validation = client.post(f"/api/v1/applications/{app_id}/validate", headers=AUTH)
    assert validation.status_code == 200, validation.text
    for finding in validation.json()["findings"]:
        resolved = client.post(
            f"/api/v1/findings/{finding['id']}/resolve",
            headers=AUTH,
            json={"status": "accepted"},
        )
        assert resolved.status_code == 200, resolved.text

    gstr_payload = {
        "records": [
            {
                "Invoice No": "P-1",
                "Invoice Date": "2026-04-10",
                "Supplier GSTIN": "27ABCDE1234F1Z5",
                "Taxable Amount": 1000,
                "CGST": 90,
                "SGST": 90,
                "Total": 1180,
            },
            {
                "Invoice No": "P-2",
                "Invoice Date": "2026-04-11",
                "Supplier GSTIN": "27ABCDE1234F1Z5",
                "Taxable Amount": 2100,
                "CGST": 189,
                "SGST": 189,
                "Total": 2478,
            },
            {
                "Invoice No": "G-ONLY",
                "Invoice Date": "2026-04-12",
                "Supplier GSTIN": "27ABCDE1234F1Z5",
                "Taxable Amount": 500,
                "CGST": 45,
                "SGST": 45,
                "Total": 590,
            },
        ]
    }
    gstr = client.post(
        f"/api/v1/applications/{app_id}/reconciliation/gstr2b",
        headers=AUTH,
        files={
            "file": ("GSTR2B_April.json", json.dumps(gstr_payload).encode(), "application/json")
        },
    )
    assert gstr.status_code == 201
    assert gstr.json()["document_type"] == "gstr2b"

    reconciliation = client.post(f"/api/v1/applications/{app_id}/reconcile", headers=AUTH)
    assert reconciliation.status_code == 200
    assert reconciliation.json()["summary"]["exact_match"] == 1
    assert reconciliation.json()["summary"]["value_mismatch"] == 1
    assert reconciliation.json()["summary"]["gstr2b_only"] == 1

    readiness = client.get(f"/api/v1/applications/{app_id}/readiness-summary", headers=AUTH)
    assert readiness.status_code == 200
    assert readiness.json()["reconciliation"]["summary"]["exact_match"] == 1
    assert "subject to CA verification" in readiness.json()["disclaimer"]
    assert readiness.json()["readiness"]["ready_for_filing"] is True

    export = client.post(f"/api/v1/applications/{app_id}/export", headers=AUTH)
    assert export.status_code == 200
    assert {
        "preparatory_report_pdf",
        "document_manifest_csv",
        "normalized_sales_csv",
        "normalized_purchase_csv",
        "validation_summary_csv",
    }.issubset(export.json())

    premature_reconciliation_export = client.post(
        f"/api/v1/applications/{app_id}/reconciliation/export", headers=AUTH
    )
    assert premature_reconciliation_export.status_code == 409
    review_required = [
        row["id"] for row in reconciliation.json()["items"] if row["match_status"] != "exact_match"
    ]
    reviewed = client.post(
        f"/api/v1/applications/{app_id}/reconciliation/items/bulk-review",
        headers=AUTH,
        json={"item_ids": review_required, "action": "mark_reviewed"},
    )
    assert reviewed.status_code == 200, reviewed.text
    reconciliation_export = client.post(
        f"/api/v1/applications/{app_id}/reconciliation/export", headers=AUTH
    )
    assert reconciliation_export.status_code == 200, reconciliation_export.text
    assert {
        "reconciliation_report_pdf",
        "reconciliation_details_csv",
        "reconciliation_export_zip",
    }.issubset(reconciliation_export.json())
    repeated_reconciliation_export = client.post(
        f"/api/v1/applications/{app_id}/reconciliation/export", headers=AUTH
    )
    assert repeated_reconciliation_export.status_code == 200
    assert (
        reconciliation_export.json()["reconciliation_export_zip"]
        != repeated_reconciliation_export.json()["reconciliation_export_zip"]
    )
