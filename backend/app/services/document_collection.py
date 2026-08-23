from __future__ import annotations

import asyncio
from typing import Any

from app.repositories.base import DataStore

COLLECTION_COMPLETE = "documents_complete"


async def get_document_collection_status(
    store: DataStore,
    application_id: str,
) -> dict[str, Any]:
    requirements = await store.list_rows(
        "document_requirements",
        {"application_id": application_id},
        order="label",
    )
    required = [row for row in requirements if row.get("required", True)]
    received = [row for row in required if row.get("status") == "received"]
    missing = [row for row in required if row.get("status") != "received"]
    required_count = len(required)
    received_count = len(received)
    progress_percent = (
        round(received_count * 100 / required_count) if required_count else 100
    )

    if required_count == received_count:
        workflow_status = COLLECTION_COMPLETE
    elif received_count:
        workflow_status = "partially_received"
    else:
        application, request_rows = await asyncio.gather(
            store.get_row("applications", application_id),
            store.list_rows(
                "reminders",
                {
                    "application_id": application_id,
                    "reminder_type": "initial_document_request",
                },
                order="created_at",
                desc=True,
                limit=1,
            ),
        )
        workflow_status = (
            "documents_requested"
            if request_rows
            or (application and application.get("status") == "documents_requested")
            else "not_started"
        )

    return {
        "required_count": required_count,
        "received_count": received_count,
        "missing_count": len(missing),
        "progress_percent": progress_percent,
        "workflow_status": workflow_status,
        "requirements": [
            {
                "id": row["id"],
                "type": row.get("requirement_type"),
                "label": row["label"],
                "required": row.get("required", True),
                "status": "received" if row.get("status") == "received" else "missing",
            }
            for row in required
        ],
    }
