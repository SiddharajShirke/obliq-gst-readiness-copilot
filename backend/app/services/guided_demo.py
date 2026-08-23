"""Persistent user-scoped Guided Demo lifecycle over existing session cloning."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.repositories.base import DataStore
from app.services.whatsapp.sessions import cancel_demo_session, create_demo_session


async def _template_context(
    store: DataStore, *, firm_id: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    filters: dict[str, Any] = {"demo_scenario": "guided_demo_template"}
    if firm_id:
        filters["firm_id"] = firm_id
    clients = await store.list_rows("clients", filters, limit=1)
    if not clients:
        raise ValueError("Guided Demo template is unavailable")
    client = clients[0]
    applications = await store.list_rows("applications", {"client_id": client["id"]})
    base = next((row for row in applications if not row.get("demo_session_id")), None)
    if not base:
        raise ValueError("Guided Demo base application is unavailable")
    return client, base


async def list_guided_demo_runs(
    store: DataStore, *, firm_id: str, user_id: str
) -> list[dict[str, Any]]:
    rows = await store.list_rows(
        "guided_demo_runs", {"firm_id": firm_id, "user_id": user_id}
    )
    return sorted(rows, key=lambda row: int(row.get("run_number") or 0), reverse=True)


async def start_guided_demo_run(
    store: DataStore,
    settings: Settings,
    user_id: str,
    firm_id: str | None = None,
) -> dict[str, Any]:
    client, base = await _template_context(store, firm_id=firm_id)
    firm_id = str(base["firm_id"])
    existing = await list_guided_demo_runs(store, firm_id=firm_id, user_id=user_id)
    for run in existing:
        if run.get("status") == "active":
            await cancel_demo_session(store, str(run["demo_session_id"]))
            await store.update_row(
                "guided_demo_runs",
                str(run["id"]),
                {"status": "cancelled", "cancelled_at": datetime.now(UTC).isoformat()},
            )
    run_number = max((int(row.get("run_number") or 0) for row in existing), default=0) + 1
    created = await create_demo_session(store, settings, str(base["id"]), user_id)
    run = await store.insert_row(
        "guided_demo_runs",
        {
            "firm_id": firm_id,
            "user_id": user_id,
            "demo_client_id": client["id"],
            "base_application_id": base["id"],
            "demo_session_id": created.session_id,
            "session_application_id": created.session_application_id,
            "run_number": run_number,
            "name": f"Guided Demo {run_number}",
            "status": "active",
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "cancelled_at": None,
        },
    )
    return {
        **run,
        "created_session": created,
        "client_name": client["business_name"],
        "gst_period": base["period_label"],
    }


async def complete_guided_demo_run(
    store: DataStore,
    *,
    run_id: str,
    firm_id: str,
    user_id: str,
) -> dict[str, Any]:
    run = await store.get_row("guided_demo_runs", run_id)
    if (
        not run
        or str(run.get("firm_id")) != str(firm_id)
        or str(run.get("user_id")) != str(user_id)
    ):
        raise ValueError("Guided Demo run was not found")
    exports = await store.list_rows(
        "audit_events",
        {
            "application_id": run["session_application_id"],
            "action": "gst_export_pack_generated",
        },
        limit=1,
    )
    if not exports:
        raise ValueError("Guided Demo can complete only after Export Pack generation")
    if run.get("status") == "completed":
        return run
    updated = await store.update_row(
        "guided_demo_runs",
        run_id,
        {"status": "completed", "completed_at": datetime.now(UTC).isoformat()},
    )
    if updated is None:
        raise RuntimeError("Guided Demo completion was not persisted")
    return updated
