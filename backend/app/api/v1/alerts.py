from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import current_user, require_roles
from app.repositories import DataStore, get_store
from app.schemas.alerts import AlertStatusUpdate
from app.schemas.auth import UserContext
from app.services.alert_explanations import generate_alert_explanation
from app.services.audit import record_audit

router = APIRouter(tags=["alerts"])


async def _require_alert(store: DataStore, alert_id: str, firm_id: str) -> dict[str, Any]:
    alert = await store.get_row("alerts", alert_id)
    if not alert or alert.get("firm_id") != firm_id:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


async def generate_and_store_explanation(
    store: DataStore,
    settings: Settings,
    *,
    alert_id: str,
    firm_id: str,
    user_id: str | None,
) -> None:
    alert = await store.get_row("alerts", alert_id)
    if not alert or alert.get("firm_id") != firm_id:
        return
    await store.update_row("alerts", alert_id, {"ai_explanation_status": "pending"})
    try:
        generated = await generate_alert_explanation(settings, alert.get("evidence") or {})
        now = datetime.now(UTC).isoformat()
        await store.update_row(
            "alerts",
            alert_id,
            {
                "ai_explanation": generated.explanation.model_dump(),
                "ai_explanation_status": "generated",
                "ai_explanation_provider": generated.provider,
                "ai_explanation_model": generated.model,
                "ai_explanation_generated_at": now,
            },
        )
        await record_audit(
            store,
            firm_id=firm_id,
            user_id=user_id,
            action="alert_ai_explanation_generated",
            entity_type="alert",
            entity_id=alert_id,
            client_id=alert.get("client_id"),
            application_id=alert.get("application_id"),
            metadata={"provider": generated.provider, "model": generated.model},
        )
    except Exception as exc:
        await store.update_row(
            "alerts",
            alert_id,
            {
                "ai_explanation_status": "failed",
                "ai_explanation": None,
                "ai_explanation_provider": None,
                "ai_explanation_model": None,
            },
        )
        await record_audit(
            store,
            firm_id=firm_id,
            user_id=user_id,
            action="alert_ai_explanation_failed",
            entity_type="alert",
            entity_id=alert_id,
            client_id=alert.get("client_id"),
            application_id=alert.get("application_id"),
            metadata={"error_type": type(exc).__name__},
        )


async def _enrich_alert(store: DataStore, alert: dict[str, Any]) -> dict[str, Any]:
    client = await store.get_row("clients", alert["client_id"]) if alert.get("client_id") else None
    application = (
        await store.get_row("applications", alert["application_id"])
        if alert.get("application_id")
        else None
    )
    return {
        **alert,
        "client_name": (client or {}).get("business_name"),
        "tax_period": (application or {}).get("period_label"),
    }


@router.get("/alerts")
async def list_alerts(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict[str, Any]]:
    rows = await store.list_rows("alerts", {"firm_id": user.firm_id}, order="created_at", desc=True)
    return [await _enrich_alert(store, row) for row in rows]


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    return await _enrich_alert(store, await _require_alert(store, alert_id, user.firm_id))


@router.patch("/alerts/{alert_id}")
async def update_alert_status(
    alert_id: str,
    payload: AlertStatusUpdate,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict[str, Any]:
    await _require_alert(store, alert_id, user.firm_id)
    updated = await store.update_row("alerts", alert_id, {"status": payload.status})
    assert updated is not None
    return await _enrich_alert(store, updated)


@router.post("/alerts/{alert_id}/generate-explanation", status_code=202)
async def retry_alert_explanation(
    alert_id: str,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    await _require_alert(store, alert_id, user.firm_id)
    background_tasks.add_task(
        generate_and_store_explanation,
        store,
        settings,
        alert_id=alert_id,
        firm_id=user.firm_id,
        user_id=user.user_id,
    )
    return {"status": "pending"}
