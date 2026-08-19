from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.applications import ApplicationCreate, ApplicationUpdate
from app.schemas.auth import UserContext
from app.services.audit import record_audit

router = APIRouter(tags=["applications"])

REQUIREMENTS = {
    "sales_register": "Sales Register",
    "purchase_register": "Purchase Register",
    "sales_invoice": "Sales Invoices",
    "purchase_invoice": "Purchase Invoices",
    "gstr2b": "GSTR-2B",
}


@router.get("/applications")
async def list_applications(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    return await store.list_rows("applications", {"firm_id": user.firm_id}, order="created_at", desc=True)


@router.post("/clients/{client_id}/applications", status_code=status.HTTP_201_CREATED)
async def create_application(
    client_id: str,
    payload: ApplicationCreate,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    client = await require_firm_row(store, "clients", client_id, user.firm_id)
    data = payload.model_dump(mode="json")
    data.update(
        {
            "firm_id": user.firm_id,
            "client_id": client_id,
            "application_type": "gst_readiness",
            "status": "not_started",
            "assigned_preparer_id": data.get("assigned_preparer_id") or client.get("assigned_preparer_id"),
            "reviewer_id": data.get("reviewer_id") or client.get("reviewer_id"),
        }
    )
    application = await store.insert_row("applications", data)
    for requirement_type, label in REQUIREMENTS.items():
        await store.insert_row(
            "document_requirements",
            {
                "application_id": application["id"],
                "requirement_type": requirement_type,
                "label": label,
                "required": True,
                "status": "missing",
            },
        )
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="application.created",
        entity_type="application",
        entity_id=application["id"],
        client_id=client_id,
        application_id=application["id"],
        after_data=application,
    )
    return application


@router.get("/applications/{application_id}")
async def get_application(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    application = await require_firm_row(store, "applications", application_id, user.firm_id)
    client = await store.get_row("clients", application["client_id"])
    return {**application, "client": client}


@router.patch("/applications/{application_id}")
async def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer", "reviewer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    before = await require_firm_row(store, "applications", application_id, user.firm_id)
    updated = await store.update_row("applications", application_id, payload.model_dump(exclude_none=True, mode="json"))
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found")
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="application.updated",
        entity_type="application",
        entity_id=application_id,
        client_id=updated["client_id"],
        application_id=application_id,
        before_data=before,
        after_data=updated,
    )
    return updated


@router.get("/applications/{application_id}/checklist")
async def application_checklist(
    application_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    await require_firm_row(store, "applications", application_id, user.firm_id)
    return await store.list_rows("document_requirements", {"application_id": application_id}, order="label")


@router.get("/dashboard/summary")
async def dashboard_summary(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    clients = await store.list_rows("clients", {"firm_id": user.firm_id})
    applications = await store.list_rows("applications", {"firm_id": user.firm_id})
    missing = 0
    for application in applications:
        requirements = await store.list_rows("document_requirements", {"application_id": application["id"]})
        missing += sum(row.get("status") == "missing" for row in requirements)
    return {
        "total_clients": len(clients),
        "active_applications": sum(app.get("status") != "completed" for app in applications),
        "missing_documents": missing,
        "needs_review": sum(app.get("status") in {"extraction_review", "validation_review", "reconciliation_review"} for app in applications),
        "ready_for_filing": sum(app.get("status") in {"ready_for_ca_review", "approved", "ready_for_filing"} for app in applications),
    }
