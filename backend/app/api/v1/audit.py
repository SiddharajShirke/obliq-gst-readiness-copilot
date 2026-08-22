from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.services.whatsapp.sessions import verify_dashboard_access

router = APIRouter(tags=["audit"])


@router.get("/applications/{application_id}/audit")
async def list_audit_events(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    session_id: Annotated[
        str | None, Header(alias="X-OBLIQ-Demo-Session-Id")
    ] = None,
    access_token: Annotated[
        str | None, Header(alias="X-OBLIQ-Demo-Access-Token")
    ] = None,
) -> list[dict]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    events = await store.list_rows(
        "audit_events",
        {"application_id": application_id},
        order="created_at",
        desc=True,
    )
    if session_id and access_token:
        session = await store.get_row("whatsapp_demo_sessions", session_id)
        if (
            session
            and session.get("firm_id") == user.firm_id
            and session.get("base_application_id") == application_id
            and await verify_dashboard_access(store, settings, session_id, access_token)
        ):
            events.extend(
                await store.list_rows(
                    "audit_events",
                    {"application_id": session["session_application_id"]},
                    order="created_at",
                    desc=True,
                )
            )
    return sorted(events, key=lambda row: str(row.get("created_at", "")), reverse=True)
