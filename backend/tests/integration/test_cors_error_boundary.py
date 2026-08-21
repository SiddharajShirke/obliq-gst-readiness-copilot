from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import get_store


class FailingStore:
    name = "memory"

    async def get_user_from_token(self, token: str) -> dict:
        del token
        raise RuntimeError("simulated repository failure")


def test_unhandled_api_error_keeps_cors_header_and_returns_sanitized_response() -> None:
    app.dependency_overrides[get_store] = lambda: FailingStore()
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.get(
            "/api/v1/clients",
            headers={
                "Authorization": "Bearer valid-shaped-test-token",
                "Origin": "http://localhost:3000",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.json() == {"detail": "Internal server error"}
