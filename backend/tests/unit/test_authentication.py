from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase_auth.errors import AuthApiError

from app.dependencies import authenticated_identity, current_user
from app.repositories.supabase import SupabaseStore


class _AuthStore:
    name = "supabase"

    def __init__(self, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    async def get_user_from_token(self, token: str) -> dict | None:
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_supabase_store_disables_unstable_http2_transport(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_client(url: str, key: str, options: object) -> SimpleNamespace:
        captured.update(url=url, key=key, options=options)
        return SimpleNamespace()

    monkeypatch.setattr("supabase.create_client", fake_create_client)
    settings = SimpleNamespace(
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="service-role-key",
    )

    store = SupabaseStore(settings)  # type: ignore[arg-type]
    try:
        options = captured["options"]
        assert options.httpx_client is store.http_client  # type: ignore[union-attr]
        transport = store.http_client._transport  # noqa: SLF001
        assert isinstance(transport, httpx.HTTPTransport)
        assert transport._pool._http2 is False  # noqa: SLF001
    finally:
        store.http_client.close()


@pytest.mark.asyncio
async def test_supabase_runtime_rejects_malformed_demo_token_before_auth_api() -> None:
    store = _AuthStore()

    with pytest.raises(HTTPException) as caught:
        await current_user(_bearer("demo-admin-token"), store)  # type: ignore[arg-type]

    assert caught.value.status_code == 401
    assert caught.value.detail == "Invalid or expired authentication session"
    assert store.calls == 0


@pytest.mark.asyncio
async def test_current_user_rejects_missing_bearer_token() -> None:
    store = _AuthStore()

    with pytest.raises(HTTPException) as caught:
        await current_user(None, store)  # type: ignore[arg-type]

    assert caught.value.status_code == 401
    assert store.calls == 0


@pytest.mark.asyncio
async def test_valid_supabase_jwt_shape_resolves_current_user() -> None:
    store = _AuthStore(
        {
            "id": "user-id",
            "firm_id": "firm-id",
            "role": "firm_admin",
            "email": "ca@example.com",
        }
    )

    user = await current_user(_bearer("header.payload.signature"), store)  # type: ignore[arg-type]

    assert user.user_id == "user-id"
    assert user.firm_id == "firm-id"
    assert user.role == "firm_admin"
    assert store.calls == 1


@pytest.mark.asyncio
async def test_valid_supabase_user_without_firm_membership_is_forbidden() -> None:
    store = _AuthStore({"id": "user-id", "email": "ca@example.com"})

    with pytest.raises(HTTPException) as caught:
        await current_user(_bearer("header.payload.signature"), store)  # type: ignore[arg-type]

    assert caught.value.status_code == 403
    assert caught.value.detail == "User is not assigned to an OBLIQ firm"


@pytest.mark.asyncio
async def test_authenticated_identity_allows_bootstrap_before_firm_membership() -> None:
    store = _AuthStore(
        {
            "id": "user-id",
            "firm_id": None,
            "role": None,
            "email": "ca@example.com",
            "full_name": "CA User",
        }
    )

    identity = await authenticated_identity(
        _bearer("header.payload.signature"), store  # type: ignore[arg-type]
    )

    assert identity.user_id == "user-id"
    assert identity.firm_id is None
    assert identity.full_name == "CA User"


class _AuthApiFailure:
    def get_user(self, token: str) -> None:
        del token
        raise AuthApiError("invalid JWT", 403, None)


class _UnexpectedFailure:
    def get_user(self, token: str) -> None:
        del token
        raise RuntimeError("network or server failure")


class _ValidAuthWithoutMembership:
    def get_user(self, token: str) -> SimpleNamespace:
        del token
        return SimpleNamespace(
            user=SimpleNamespace(id="user-id", email="ca@example.com")
        )


class _EmptyMembershipQuery:
    data: list[dict] = []

    def select(self, columns: str) -> _EmptyMembershipQuery:
        del columns
        return self

    def eq(self, column: str, value: str) -> _EmptyMembershipQuery:
        del column, value
        return self

    def limit(self, count: int) -> _EmptyMembershipQuery:
        del count
        return self

    def execute(self) -> _EmptyMembershipQuery:
        return self


def _store_with_auth(auth: object) -> SupabaseStore:
    store = object.__new__(SupabaseStore)
    store.client = SimpleNamespace(auth=auth)
    return store


@pytest.mark.asyncio
async def test_supabase_store_preserves_valid_user_when_membership_is_missing() -> None:
    store = object.__new__(SupabaseStore)
    store.client = SimpleNamespace(
        auth=_ValidAuthWithoutMembership(),
        table=lambda name: _EmptyMembershipQuery(),
    )

    assert await store.get_user_from_token("header.payload.signature") == {
        "id": "user-id",
        "firm_id": None,
        "role": None,
        "email": "ca@example.com",
        "full_name": "",
    }


@pytest.mark.asyncio
async def test_supabase_auth_api_error_is_an_unauthenticated_result() -> None:
    store = _store_with_auth(_AuthApiFailure())

    assert await store.get_user_from_token("header.payload.signature") is None


@pytest.mark.asyncio
async def test_unexpected_supabase_failure_is_not_converted_to_unauthorized() -> None:
    store = _store_with_auth(_UnexpectedFailure())

    with pytest.raises(RuntimeError, match="network or server failure"):
        await store.get_user_from_token("header.payload.signature")
