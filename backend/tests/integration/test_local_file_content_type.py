from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
ROOT = Path(__file__).resolve().parents[3]


def test_signed_local_pdf_uses_pdf_content_type() -> None:
    link = client.post(
        "/api/v1/applications/30000000-0000-0000-0000-000000000001/upload-link",
        headers=AUTH,
    )
    assert link.status_code == 201, link.text
    requirement = next(
        row
        for row in client.get(
            "/api/v1/applications/30000000-0000-0000-0000-000000000001/checklist",
            headers=AUTH,
        ).json()
        if row["requirement_type"] == "purchase_invoice"
    )
    source = ROOT / "demo_data" / "documents" / "Purchase_Invoice_SD-1042.pdf"
    with source.open("rb") as handle:
        uploaded = client.post(
            f"/api/v1/public/upload/{link.json()['token']}",
            data={"requirement_id": requirement["id"]},
            files={"file": (source.name, handle, "application/pdf")},
        )
    assert uploaded.status_code == 201, uploaded.text

    metadata = client.get(f"/api/v1/documents/{uploaded.json()['id']}", headers=AUTH)
    assert metadata.status_code == 200, metadata.text

    response = client.get(metadata.json()["signed_url"])
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
