from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
ROOT = Path(__file__).resolve().parents[3]
DEMO_FILES = ROOT / "demo_data" / "documents"


def _upload(application_id: str, client_id: str, requirement_type: str, filename: str) -> dict:
    path = DEMO_FILES / filename
    with path.open("rb") as handle:
        response = client.post(
            "/api/v1/demo/upload",
            data={
                "client_id": client_id,
                "application_id": application_id,
                "requirement_type": requirement_type,
            },
            files={"file": (path.name, handle, "application/octet-stream")},
        )
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_mock_gst_readiness_walkthrough() -> None:
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
    sent = client.post(
        f"/api/v1/applications/{application_id}/document-request/approve-send",
        headers=AUTH,
        json={"reminder_id": reminder["id"], "message": reminder["draft_message"]},
    )
    assert sent.status_code == 200, sent.text

    first_document = _upload(application_id, client_id, "sales_register", "Sales_Register_April.csv")
    _upload(application_id, client_id, "sales_invoice", "Sales_Invoice_RT-501.pdf")
    _upload(application_id, client_id, "purchase_invoice", "Purchase_Invoice_SD-1042.pdf")
    _upload(application_id, client_id, "gstr2b", "GSTR2B_April.json")

    checklist = client.get(
        f"/api/v1/applications/{application_id}/checklist", headers=AUTH
    ).json()
    assert sum(row["status"] != "missing" for row in checklist) == 4
    assert next(row for row in checklist if row["requirement_type"] == "purchase_register")[
        "status"
    ] == "missing"

    reminder_draft = client.post(
        f"/api/v1/applications/{application_id}/reminders/draft", headers=AUTH
    )
    assert reminder_draft.status_code == 201, reminder_draft.text
    missing_reminder = reminder_draft.json()
    assert "Purchase Register" in missing_reminder["draft_message"]
    reminder_sent = client.post(
        f"/api/v1/reminders/{missing_reminder['id']}/approve-send",
        headers=AUTH,
        json={"reminder_id": missing_reminder["id"], "message": missing_reminder["draft_message"]},
    )
    assert reminder_sent.status_code == 200, reminder_sent.text

    _upload(application_id, client_id, "purchase_register", "Purchase_Register_April.xlsx")
    checklist = client.get(
        f"/api/v1/applications/{application_id}/checklist", headers=AUTH
    ).json()
    assert all(row["status"] != "missing" for row in checklist)

    extraction = client.get(
        f"/api/v1/documents/{first_document['id']}/extraction", headers=AUTH
    )
    assert extraction.status_code == 200, extraction.text
    approved = client.post(
        f"/api/v1/documents/{first_document['id']}/approve",
        headers=AUTH,
        json={"notes": "Reviewed in guided demo"},
    )
    assert approved.status_code == 200, approved.text

    validation = client.post(
        f"/api/v1/applications/{application_id}/validate", headers=AUTH
    )
    assert validation.status_code == 200, validation.text

    reconciliation = client.post(
        f"/api/v1/applications/{application_id}/reconcile", headers=AUTH
    )
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

    export = client.post(
        f"/api/v1/applications/{application_id}/export", headers=AUTH
    )
    assert export.status_code == 200, export.text
    assert set(export.json()) == {"readiness_pdf", "invoice_csv", "reconciliation_csv"}

    audit = client.get(
        f"/api/v1/applications/{application_id}/audit", headers=AUTH
    )
    assert audit.status_code == 200, audit.text
    assert len(audit.json()) >= 5
