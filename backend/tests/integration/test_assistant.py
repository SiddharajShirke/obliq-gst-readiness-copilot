from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-admin-token"}
APP_ID = "30000000-0000-0000-0000-000000000001"


def test_assistant_uses_database_for_missing_document_question() -> None:
    response = client.post(
        "/api/v1/assistant/query",
        headers=AUTH,
        json={"question": "Which documents are missing for Raj Traders?", "application_id": APP_ID},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "Purchase Register" in payload["answer"]
    assert payload["used_application_data"] is True


def test_default_demo_knowledge_returns_cited_guidance() -> None:
    response = client.post(
        "/api/v1/assistant/query",
        headers=AUTH,
        json={"question": "What does a GSTR-2B mismatch mean?", "application_id": APP_ID},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"]
    assert "review" in payload["answer"].lower() or "gstr" in payload["answer"].lower()
