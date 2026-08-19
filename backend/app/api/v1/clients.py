from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.clients import ClientCreate, ClientUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
async def list_clients(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    return await store.list_rows("clients", {"firm_id": user.firm_id}, order="business_name")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    row = await store.insert_row("clients", {"firm_id": user.firm_id, **payload.model_dump()})
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="client.created",
        entity_type="client",
        entity_id=row["id"],
        client_id=row["id"],
        after_data=row,
    )
    return row


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    return await require_firm_row(store, "clients", client_id, user.firm_id)


@router.patch("/{client_id}")
async def update_client(
    client_id: str,
    payload: ClientUpdate,
    user: Annotated[UserContext, Depends(require_roles("firm_admin", "gst_preparer"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    before = await require_firm_row(store, "clients", client_id, user.firm_id)
    data = payload.model_dump(exclude_none=True)
    updated = await store.update_row("clients", client_id, data)
    assert updated is not None
    await record_audit(
        store,
        firm_id=user.firm_id,
        user_id=user.user_id,
        action="client.updated",
        entity_type="client",
        entity_id=client_id,
        client_id=client_id,
        before_data=before,
        after_data=updated,
    )
    return updated


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: str,
    user: Annotated[UserContext, Depends(require_roles("firm_admin"))],
    store: Annotated[DataStore, Depends(get_store)],
) -> Response:
    await require_firm_row(store, "clients", client_id, user.firm_id)
    await store.delete_row("clients", client_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
