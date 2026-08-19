from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import current_user
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


@router.get("/me")
async def me(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    profile = await store.get_row("profiles", user.user_id)
    return {**user.model_dump(), "profile": profile}


@router.patch("/me")
async def update_me(
    payload: ProfileUpdate,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    row = await store.update_row("profiles", user.user_id, payload.model_dump())
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row
