"""Self-service controls for the deterministic hosted demonstration."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import require_roles
from app.repositories import DataStore, get_store
from app.repositories.memory import MemoryStore
from app.schemas.auth import UserContext

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/reset")
async def reset_demo(
    user: Annotated[UserContext, Depends(require_roles("firm_admin"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, int | str]:
    del user
    if not settings.demo_mode or not isinstance(store, MemoryStore):
        raise HTTPException(
            status_code=409, detail="Demo reset is available only in in-memory demo mode"
        )
    return await store.reset_demo()
