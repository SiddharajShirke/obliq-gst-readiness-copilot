"""FastAPI dependencies for authentication and tenant access."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext

bearer_scheme = HTTPBearer(auto_error=False)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    store: Annotated[DataStore, Depends(get_store)],
) -> UserContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    user = await store.get_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return UserContext(
        user_id=user["id"],
        firm_id=user["firm_id"],
        role=user["role"],
        email=user.get("email", ""),
    )


def require_roles(*roles: str):
    async def dependency(user: Annotated[UserContext, Depends(current_user)]) -> UserContext:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="This role cannot perform the requested action")
        return user
    return dependency


async def require_firm_row(store: DataStore, table: str, row_id: str, firm_id: str) -> dict:
    row = await store.get_row(table, row_id)
    if not row or str(row.get("firm_id")) != str(firm_id):
        raise HTTPException(status_code=404, detail=f"{table.rstrip('s').title()} not found")
    return row
