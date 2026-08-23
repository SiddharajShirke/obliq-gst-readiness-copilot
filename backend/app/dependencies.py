"""FastAPI dependencies for authentication and tenant access."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories import DataStore, get_store
from app.schemas.auth import AuthenticatedIdentity, UserContext

bearer_scheme = HTTPBearer(auto_error=False)
INVALID_AUTH_DETAIL = "Invalid or expired authentication session"


async def authenticated_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    store: Annotated[DataStore, Depends(get_store)],
) -> AuthenticatedIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required"
        )
    if store.name == "supabase" and len(credentials.credentials.split(".")) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_AUTH_DETAIL,
        )
    user = await store.get_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_AUTH_DETAIL,
        )
    return AuthenticatedIdentity(
        user_id=user["id"],
        firm_id=user.get("firm_id"),
        role=user.get("role"),
        email=user.get("email", ""),
        full_name=user.get("full_name", ""),
    )


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    store: Annotated[DataStore, Depends(get_store)],
) -> UserContext:
    identity = await authenticated_identity(credentials, store)
    if not identity.firm_id or not identity.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to an OBLIQ firm",
        )
    return UserContext(
        user_id=identity.user_id,
        firm_id=identity.firm_id,
        role=identity.role,
        email=identity.email,
    )


def require_roles(*roles: str):
    async def dependency(user: Annotated[UserContext, Depends(current_user)]) -> UserContext:
        if user.role not in roles:
            raise HTTPException(
                status_code=403, detail="This role cannot perform the requested action"
            )
        return user

    return dependency


async def require_firm_row(store: DataStore, table: str, row_id: str, firm_id: str) -> dict:
    row = await store.get_row(table, row_id)
    if not row or str(row.get("firm_id")) != str(firm_id):
        raise HTTPException(status_code=404, detail=f"{table.rstrip('s').title()} not found")
    return row
