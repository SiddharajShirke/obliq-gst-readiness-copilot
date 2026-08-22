from io import BytesIO

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


def make_invoice_pdf() -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output)
    lines = [
        "Supplier: Sharma Distributors",
        "Supplier GSTIN: 27ABCDE1234F1Z5",
        "Customer: Raj Traders",
        "Customer GSTIN: 27RAJTR1234A1Z5",
        "Invoice Number: SD-2042",
        "Invoice Date: 18-04-2026",
        "Taxable Value: 50000",
        "CGST: 4500",
        "SGST: 4500",
        "IGST: 0",
        "Invoice Total: 59000",
    ]
    y = 780
    for line in lines:
        pdf.drawString(60, y, line)
        y -= 24
    pdf.save()
    return output.getvalue()


def test_secure_upload_link_stores_document_before_explicit_processing() -> None:
    link_response = client.post(f"/api/v1/applications/{APP_ID}/upload-link", headers=AUTH)
    assert link_response.status_code == 201
    token = link_response.json()["token"]

    public_context = client.get(f"/api/v1/public/upload/{token}")
    assert public_context.status_code == 200
    assert public_context.json()["client"]["business_name"] == "Raj Traders"
    purchase_requirement = next(
        row
        for row in client.get(
            f"/api/v1/applications/{APP_ID}/checklist", headers=AUTH
        ).json()
        if row["requirement_type"] == "purchase_invoice"
    )

    upload = client.post(
        f"/api/v1/public/upload/{token}",
        data={"requirement_id": purchase_requirement["id"]},
        files={"file": ("Purchase_Invoice_SD-2042.pdf", make_invoice_pdf(), "application/pdf")},
    )
    assert upload.status_code == 201
    document = upload.json()
    assert document["processing_status"] == "awaiting_processing"

    extraction = client.get(f"/api/v1/documents/{document['id']}/extraction", headers=AUTH)
    assert extraction.status_code == 404

    processed = client.post(f"/api/v1/documents/{document['id']}/process", headers=AUTH)
    assert processed.status_code == 200

    extraction = client.get(f"/api/v1/documents/{document['id']}/extraction", headers=AUTH)
    assert extraction.status_code == 200
    assert extraction.json()["structured_data"]["invoice_number"] == "SD-2042"


def test_secure_upload_rejects_unknown_checklist_category() -> None:
    link_response = client.post(f"/api/v1/applications/{APP_ID}/upload-link", headers=AUTH)
    assert link_response.status_code == 201
    token = link_response.json()["token"]

    upload = client.post(
        f"/api/v1/public/upload/{token}",
        data={"requirement_id": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
        files={"file": ("statement.pdf", make_invoice_pdf(), "application/pdf")},
    )

    assert upload.status_code == 400
    assert "checklist category" in upload.json()["detail"].lower()
