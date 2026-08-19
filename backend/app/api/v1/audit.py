from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import current_user, require_firm_row
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext

router = APIRouter(tags=["audit"])


@router.get("/applications/{application_id}/audit")
async def list_audit_events(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    return await store.list_rows(
        "audit_events",
        {"application_id": application_id},
        order="created_at",
        desc=True,
    )
