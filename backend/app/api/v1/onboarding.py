from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import authenticated_identity
from app.repositories import DataStore, get_store
from app.schemas.auth import AuthenticatedIdentity
from app.services.onboarding import bootstrap_user_workspace

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/bootstrap")
async def bootstrap_workspace(
    identity: Annotated[AuthenticatedIdentity, Depends(authenticated_identity)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    return await bootstrap_user_workspace(store, identity.model_dump())
