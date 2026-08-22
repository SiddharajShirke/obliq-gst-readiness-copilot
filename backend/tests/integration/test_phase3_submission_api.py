from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


def _upload_link() -> tuple[str, dict]:
    created = client.post(f"/api/v1/applications/{APP_ID}/upload-link", headers=AUTH)
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    context = client.get(f"/api/v1/public/upload/{token}")
    assert context.status_code == 200, context.text
    requirement = next(
        row for row in context.json()["checklist"] if row["label"] == "Sales Register"
    )
    return token, requirement


def _upload(token: str, requirement: dict, marker: str) -> dict:
    response = client.post(
        f"/api/v1/public/upload/{token}",
        data={"requirement_id": requirement["id"]},
        files={
            "file": (
                f"01_Sales_Register_{marker}.csv",
                f"Invoice No,Taxable Value\nS-{marker},1000\n".encode(),
                "text/csv",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_waits_for_submit_then_creates_one_processing_batch() -> None:
    token, requirement = _upload_link()
    uploaded = _upload(token, requirement, "batch-one")

    assert uploaded["processing_status"] == "awaiting_submission"

    submitted = client.post(f"/api/v1/public/upload/{token}/submit")
    assert submitted.status_code == 202, submitted.text
    payload = submitted.json()
    assert payload["document_count"] == 1
    assert payload["status"] in {"submitted", "processing", "completed"}
    assert payload["id"]

    repeated = client.post(f"/api/v1/public/upload/{token}/submit")
    assert repeated.status_code == 409


def test_later_upload_creates_a_new_submission_batch() -> None:
    token, requirement = _upload_link()
    _upload(token, requirement, "first-later")
    first = client.post(f"/api/v1/public/upload/{token}/submit")
    assert first.status_code == 202, first.text

    _upload(token, requirement, "second-later")
    second = client.post(f"/api/v1/public/upload/{token}/submit")
    assert second.status_code == 202, second.text
    assert second.json()["id"] != first.json()["id"]


def test_public_status_exposes_only_scoped_submission_progress() -> None:
    token, requirement = _upload_link()
    _upload(token, requirement, "status")

    before = client.get(f"/api/v1/public/upload/{token}/status")
    assert before.status_code == 200
    assert before.json()["ready_to_submit_count"] == 1
    assert before.json()["latest_submission_batch"] is None

    submitted = client.post(f"/api/v1/public/upload/{token}/submit")
    assert submitted.status_code == 202, submitted.text
    after = client.get(f"/api/v1/public/upload/{token}/status")
    assert after.status_code == 200
    assert after.json()["ready_to_submit_count"] == 0
    assert after.json()["latest_submission_batch"]["id"] == submitted.json()["id"]
    assert set(after.json()["latest_submission_batch"]) == {
        "id",
        "status",
        "document_count",
        "completed_count",
        "failed_count",
        "submitted_at",
        "completed_at",
    }
