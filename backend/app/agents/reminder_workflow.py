"""Controlled reminder drafting workflow. Sending is a separate human-approved action."""

from __future__ import annotations

from typing import Any, TypedDict

from app.repositories.base import DataStore


class ReminderState(TypedDict, total=False):
    firm_id: str
    client: dict[str, Any]
    application: dict[str, Any]
    checklist: list[dict[str, Any]]
    upload_url: str
    reminder_type: str
    draft_message: str


def build_message(state: ReminderState) -> str:
    missing = [row["label"] for row in state["checklist"] if row.get("status") == "missing"]
    requested = missing or [row["label"] for row in state["checklist"] if row.get("required")]
    numbered = "\n".join(f"{index}. {label}" for index, label in enumerate(requested, start=1))
    client_name = state["client"]["business_name"]
    period = state["application"]["period_label"]
    if state["reminder_type"] == "missing_document_reminder":
        intro = f"Thank you for the documents already shared for {period}. The following item is still pending:"
    else:
        intro = f"We have started preparing your {period} GST work. Please submit the following documents:"
    return (
        f"Hello {client_name},\n\n{intro}\n\n{numbered}\n\n"
        f"Upload securely: {state['upload_url']}\n\n— Sharma & Associates"
    )


async def create_reminder_draft(store: DataStore, state: ReminderState) -> dict[str, Any]:
    message = build_message(state)
    return await store.insert_row(
        "reminders",
        {
            "firm_id": state["firm_id"],
            "application_id": state["application"]["id"],
            "client_id": state["client"]["id"],
            "reminder_type": state["reminder_type"],
            "draft_message": message,
            "approved_message": None,
            "status": "awaiting_approval",
            "provider": None,
        },
    )
