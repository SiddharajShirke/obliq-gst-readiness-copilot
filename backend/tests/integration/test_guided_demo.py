from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
ROOT = Path(__file__).resolve().parents[3]
DEMO_FILES = ROOT / "demo_data" / "documents"


def _upload(application_id: str, client_id: str, requirement_type: str, filename: str) -> dict:
    del client_id
    link = client.post(f"/api/v1/applications/{application_id}/upload-link", headers=AUTH)
    assert link.status_code == 201, link.text
    token = link.json()["token"]
    checklist = client.get(f"/api/v1/applications/{application_id}/checklist", headers=AUTH).json()
    requirement_id = next(
        row["id"] for row in checklist if row["requirement_type"] == requirement_type
    )
    mime_types = {
        ".csv": "text/csv",
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    path = DEMO_FILES / filename
    with path.open("rb") as handle:
        response = client.post(
            f"/api/v1/public/upload/{token}",
            data={"requirement_id": requirement_id},
            files={"file": (path.name, handle, mime_types[path.suffix.lower()])},
        )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["processing_status"] == "awaiting_submission"
    submitted = client.post(f"/api/v1/public/upload/{token}/submit")
    assert submitted.status_code == 202, submitted.text
    return document


def test_complete_gst_readiness_walkthrough() -> None:
    created_client = client.post(
        "/api/v1/clients",
        headers=AUTH,
        json={
            "business_name": "Walkthrough Traders",
            "legal_name": "Walkthrough Traders",
            "gstin": "27WALKT1234A1Z5",
            "state": "Maharashtra",
            "business_type": "Retail",
            "filing_frequency": "monthly",
            "contact_name": "Demo Client",
            "whatsapp_phone": "+919899999999",
            "preferred_language": "English",
            "whatsapp_consent": True,
        },
    )
    assert created_client.status_code == 201, created_client.text
    client_id = created_client.json()["id"]

    created_application = client.post(
        f"/api/v1/clients/{client_id}/applications",
        headers=AUTH,
        json={
            "financial_year": "2026-27",
            "period_label": "April 2026",
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "filing_frequency": "monthly",
            "due_date": "2026-05-20",
        },
    )
    assert created_application.status_code == 201, created_application.text
    application_id = created_application.json()["id"]

    draft = client.post(
        f"/api/v1/applications/{application_id}/document-request/draft", headers=AUTH
    )
    assert draft.status_code == 201, draft.text
    reminder = draft.json()
    assert reminder["status"] == "awaiting_approval"
    assert reminder["requires_connection"] is True
    assert reminder["upload_url"] is None

    first_document = _upload(
        application_id, client_id, "sales_register", "Sales_Register_April.csv"
    )
    _upload(application_id, client_id, "sales_invoices", "Sales_Invoice_RT-501.pdf")
    _upload(
        application_id,
        client_id,
        "purchase_expense_invoices",
        "Purchase_Invoice_SD-1042.pdf",
    )
    _upload(
        application_id,
        client_id,
        "credit_debit_notes",
        "Purchase_Invoice_Duplicate_A.pdf",
    )
    _upload(
        application_id,
        client_id,
        "gst_special_transactions",
        "Purchase_Invoice_Wrong_Period.pdf",
    )

    checklist = client.get(f"/api/v1/applications/{application_id}/checklist", headers=AUTH).json()
    assert sum(row["status"] != "missing" for row in checklist) == 5
    assert (
        next(row for row in checklist if row["requirement_type"] == "purchase_register")["status"]
        == "missing"
    )

    reminder_draft = client.post(
        f"/api/v1/applications/{application_id}/reminders/draft", headers=AUTH
    )
    assert reminder_draft.status_code == 201, reminder_draft.text
    missing_reminder = reminder_draft.json()
    assert "Purchase Register" in missing_reminder["draft_message"]
    assert missing_reminder["requires_connection"] is True

    _upload(application_id, client_id, "purchase_register", "Purchase_Register_April.xlsx")
    checklist = client.get(f"/api/v1/applications/{application_id}/checklist", headers=AUTH).json()
    assert all(row["status"] != "missing" for row in checklist)

    gstr_path = DEMO_FILES / "GSTR2B_April.json"
    with gstr_path.open("rb") as handle:
        gstr2b = client.post(
            f"/api/v1/applications/{application_id}/reconciliation/gstr2b",
            headers=AUTH,
            files={"file": (gstr_path.name, handle, "application/json")},
        )
    assert gstr2b.status_code == 201, gstr2b.text

    extraction = client.get(f"/api/v1/documents/{first_document['id']}/extraction", headers=AUTH)
    assert extraction.status_code == 200, extraction.text
    approved = client.post(
        f"/api/v1/documents/{first_document['id']}/approve",
        headers=AUTH,
        json={"notes": "Reviewed in guided demo"},
    )
    assert approved.status_code == 200, approved.text

    validation = client.post(f"/api/v1/applications/{application_id}/validate", headers=AUTH)
    assert validation.status_code == 200, validation.text
    for finding in validation.json()["findings"]:
        resolved = client.post(
            f"/api/v1/findings/{finding['id']}/resolve",
            headers=AUTH,
            json={"status": "accepted"},
        )
        assert resolved.status_code == 200, resolved.text

    reconciliation = client.post(f"/api/v1/applications/{application_id}/reconcile", headers=AUTH)
    assert reconciliation.status_code == 200, reconciliation.text
    assert "summary" in reconciliation.json()

    answer = client.post(
        "/api/v1/assistant/query",
        headers=AUTH,
        json={
            "question": "What does a GSTR-2B mismatch mean?",
            "application_id": application_id,
        },
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["citations"]

    export = client.post(f"/api/v1/applications/{application_id}/export", headers=AUTH)
    assert export.status_code == 200, export.text
    assert set(export.json()) == {
        "preparatory_report_pdf",
        "document_manifest_csv",
        "normalized_sales_csv",
        "normalized_purchase_csv",
        "validation_summary_csv",
        "export_pack_zip",
    }

    audit = client.get(f"/api/v1/applications/{application_id}/audit", headers=AUTH)
    assert audit.status_code == 200, audit.text
    assert len(audit.json()) >= 5
