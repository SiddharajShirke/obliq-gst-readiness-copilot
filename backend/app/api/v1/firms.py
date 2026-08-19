from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.dependencies import current_user, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext

router = APIRouter(prefix="/firms", tags=["firms"])


class MemberCreate(BaseModel):
    user_id: str
    role: str = Field(pattern="^(firm_admin|gst_preparer|reviewer)$")
    email: EmailStr | None = None


@router.get("/current")
async def current_firm(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    firm = await store.get_row("firms", user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    return firm


@router.get("/current/members")
async def list_members(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    memberships = await store.list_rows("firm_members", {"firm_id": user.firm_id})
    profiles = {row["id"]: row for row in await store.list_rows("profiles")}
    return [{**row, "profile": profiles.get(row["user_id"])} for row in memberships]


@router.post("/current/members", status_code=201)
async def add_member(
    payload: MemberCreate,
    user: Annotated[UserContext, Depends(require_roles("firm_admin"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    return await store.insert_row(
        "firm_members",
        {"firm_id": user.firm_id, "user_id": payload.user_id, "role": payload.role},
    )
