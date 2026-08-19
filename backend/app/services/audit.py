from __future__ import annotations

from typing import Any

from app.repositories.base import DataStore


async def record_audit(
    store: DataStore,
    *,
    firm_id: str,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    client_id: str | None = None,
    application_id: str | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await store.insert_row(
        "audit_events",
        {
            "firm_id": firm_id,
            "user_id": user_id,
            "client_id": client_id,
            "application_id": application_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "before_data": before_data,
            "after_data": after_data,
            "metadata": metadata or {},
        },
    )
