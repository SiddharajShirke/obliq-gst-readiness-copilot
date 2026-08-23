from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.dependencies import current_user, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.services.guided_demo import (
    complete_guided_demo_run,
    list_guided_demo_runs,
    start_guided_demo_run,
)

router = APIRouter(prefix="/guided-demo-runs", tags=["guided-demo"])


@router.get("")
async def list_runs(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    return await list_guided_demo_runs(store, firm_id=user.firm_id, user_id=user.user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_run(
    user: Annotated[
        UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))
    ],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        result = await start_guided_demo_run(
            store, settings, user.user_id, firm_id=user.firm_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    created = result.pop("created_session")
    session = asdict(created)
    session.pop("start_token", None)
    return {
        **result,
        "session": {
            **session,
            "base_client_name": result["client_name"],
            "gst_period": result["gst_period"],
            "status": "waiting_for_start",
            "sandbox_sender": settings.vonage_whatsapp_from.removeprefix("+"),
        },
    }


@router.post("/{run_id}/complete")
async def complete_run(
    run_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    try:
        return await complete_guided_demo_run(
            store, run_id=run_id, firm_id=user.firm_id, user_id=user.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
