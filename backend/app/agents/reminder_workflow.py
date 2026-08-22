"""Controlled reminder drafting workflow. Sending is a separate human-approved action."""

from __future__ import annotations

from typing import Any, TypedDict

from app.middleware import redact_upload_token_path
from app.repositories.base import DataStore


class ReminderState(TypedDict, total=False):
    firm_id: str
    client: dict[str, Any]
    application: dict[str, Any]
    checklist: list[dict[str, Any]]
    upload_url: str | None
    reminder_type: str
    base_application_id: str
    demo_session_id: str | None
    upload_link_id: str | None


def build_message(state: ReminderState) -> str:
    missing = [
        row["label"]
        for row in state["checklist"]
        if row.get("required", True) and row.get("status") == "missing"
    ]
    items = "\n".join(f"• {label}" for label in missing)
    client_name = state["client"]["business_name"]
    period = state["application"]["period_label"]
    if state["reminder_type"] == "missing_document_reminder":
        intro = (
            "Thank you for the documents already submitted.\n\n"
            f"The following documents are still pending for {period}:"
        )
        link_instruction = "Please upload them using your existing secure upload link."
    else:
        intro = f"Please provide the following documents for {period} GST:"
        link_instruction = (
            f"Upload securely here:\n{state['upload_url']}"
            if state.get("upload_url")
            else "Connect WhatsApp to receive your secure upload link."
        )
    return (
        f"Hello {client_name},\n\n{intro}\n\n{items}\n\n"
        f"{link_instruction}\n\nThank you."
    )


async def create_reminder_draft(
    store: DataStore, state: ReminderState
) -> dict[str, Any]:
    message = build_message(state)
    stored = await store.insert_row(
        "reminders",
        {
            "firm_id": state["firm_id"],
            "application_id": state["application"]["id"],
            "base_application_id": state.get("base_application_id")
            or state["application"]["id"],
            "client_id": state["client"]["id"],
            "demo_session_id": state.get("demo_session_id"),
            "upload_link_id": state.get("upload_link_id"),
            "provider_message_id": None,
            "reminder_type": state["reminder_type"],
            "draft_message": redact_upload_token_path(message),
            "approved_message": None,
            "status": "awaiting_approval",
            "provider": None,
        },
    )
    return {**stored, "draft_message": message}
