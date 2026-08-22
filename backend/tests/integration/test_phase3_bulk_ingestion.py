import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


def _link() -> str:
    response = client.post(f"/api/v1/applications/{APP_ID}/upload-link", headers=AUTH)
    assert response.status_code == 201
    return response.json()["token"]


def _zip(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_folder_upload_routes_ground_truth_gstr2b_and_client_documents() -> None:
    token = _link()
    response = client.post(
        f"/api/v1/public/upload/{token}/bulk-folder",
        files=[
            (
                "files",
                ("00_Set_Index_and_Ground_Truth.pdf", b"%PDF-1.4 reference", "application/pdf"),
            ),
            ("files", ("01_Sales_Register.csv", b"Invoice No,Taxable Value\nS-1,100", "text/csv")),
            (
                "files",
                (
                    "07_GSTR-2B_Synthetic.json",
                    json.dumps({"records": []}).encode(),
                    "application/json",
                ),
            ),
        ],
    )
    assert response.status_code == 201, response.text
    documents = response.json()["documents"]
    assert {row["document_type"] for row in documents} == {
        "developer_ground_truth",
        "sales_register",
        "gstr2b",
    }
    ground_truth = next(
        row for row in documents if row["document_type"] == "developer_ground_truth"
    )
    assert ground_truth["processing_status"] == "excluded_reference"
    gstr2b = next(row for row in documents if row["document_type"] == "gstr2b")
    assert gstr2b["requirement_id"] is None


def test_zip_upload_reuses_bulk_ingestion_and_rejects_traversal() -> None:
    token = _link()
    accepted = client.post(
        f"/api/v1/public/upload/{token}/bulk-zip",
        files={
            "file": (
                "dataset.zip",
                _zip({"02_Purchase_Register.csv": b"Invoice No,Taxable Value\nP-1,200"}),
                "application/zip",
            )
        },
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["documents"][0]["document_type"] == "purchase_register"

    rejected = client.post(
        f"/api/v1/public/upload/{token}/bulk-zip",
        files={"file": ("dataset.zip", _zip({"../escape.pdf": b"%PDF-1.4"}), "application/zip")},
    )
    assert rejected.status_code == 400
    assert "unsafe path" in rejected.json()["detail"].lower()
