from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
ROOT = Path(__file__).resolve().parents[3]


def test_signed_local_pdf_uses_pdf_content_type() -> None:
    source = ROOT / "demo_data" / "documents" / "Purchase_Invoice_SD-1042.pdf"
    with source.open("rb") as handle:
        uploaded = client.post(
            "/api/v1/demo/upload",
            data={
                "client_id": "20000000-0000-0000-0000-000000000001",
                "application_id": "30000000-0000-0000-0000-000000000001",
                "requirement_type": "purchase_invoice",
            },
            files={"file": (source.name, handle, "application/pdf")},
        )
    assert uploaded.status_code == 201, uploaded.text

    metadata = client.get(f"/api/v1/documents/{uploaded.json()['id']}", headers=AUTH)
    assert metadata.status_code == 200, metadata.text

    response = client.get(metadata.json()["signed_url"])
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
