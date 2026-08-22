from __future__ import annotations

import re
from dataclasses import dataclass

from app.repositories.base import DataStore
from app.services.document_collection import get_document_collection_status

MEDIA_PHASE_MESSAGE = (
    "Your WhatsApp attachment reached the OBLIQ webhook successfully.\n\n"
    "The attachment itself was not downloaded or stored. Please use the secure upload "
    "link sent by your CA. Direct WhatsApp attachment processing remains "
    "deferred."
)


@dataclass(frozen=True, slots=True)
class ConversationReply:
    action: str
    text: str


async def _context(store: DataStore, session: dict) -> tuple[dict, dict, list[dict]]:
    application = await store.get_row("applications", session["session_application_id"])
    client = await store.get_row("clients", session["base_client_id"])
    if not application or not client:
        raise RuntimeError("Demo session application context is unavailable")
    checklist = await store.list_rows(
        "document_requirements",
        {"application_id": application["id"]},
        order="label",
    )
    return application, client, checklist


def _numbered(labels: list[str]) -> str:
    return "\n".join(f"{index}. {label}" for index, label in enumerate(labels, 1))


async def build_welcome_message(
    store: DataStore,
    session: dict,
) -> str:
    application, client, checklist = await _context(store, session)
    labels = [row["label"] for row in checklist if row.get("required", True)]
    return (
        "Welcome to the OBLIQ GST workflow demo.\n\n"
        "You are acting as the client for:\n\n"
        f"{client['business_name']}\n"
        f"GST Period: {application['period_label']}\n\n"
        "The following documents are required:\n\n"
        f"{_numbered(labels)}\n\n"
        "The live Vonage WhatsApp connection is active.\n\n"
        "Your CA will send the secure upload link after review. Documents uploaded "
        "through that link are stored privately and marked as awaiting processing. "
        "Direct WhatsApp attachments are not processed.\n\n"
        "You can reply:\nSTATUS\nHELP\nCANCEL"
    )


def _looks_like_tax_or_legal_question(text: str) -> bool:
    return bool(
        re.search(
            r"\b(itc|input tax credit|gst rate|tax rate|legally|legal|eligible|eligibility|"
            r"file(?:d| this)? return|tax calculation|claim)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


async def handle_text_command(
    store: DataStore,
    session: dict,
    body: str,
) -> ConversationReply:
    command = body.strip().upper()
    if command == "STATUS":
        application, client, _ = await _context(store, session)
        collection = await get_document_collection_status(store, application["id"])
        pending = [
            row["label"] for row in collection["requirements"] if row["status"] == "missing"
        ]
        return ConversationReply(
            "status",
            "OBLIQ WhatsApp session is active.\n\n"
            f"Client: {client['business_name']}\n"
            f"GST Period: {application['period_label']}\n\n"
            "Pending document categories:\n\n"
            f"{_numbered(pending) if pending else 'None'}\n\n"
            "Use the secure browser upload link sent by your CA. Direct WhatsApp "
            "attachments are not processed.",
        )
    if command == "HELP":
        return ConversationReply(
            "help",
            "Available commands:\n\n"
            "STATUS — View the selected GST period and current checklist\n"
            "HELP — View these instructions\n"
            "CANCEL — End this temporary demo session",
        )
    if command == "CANCEL":
        return ConversationReply(
            "cancel",
            "Your temporary OBLIQ WhatsApp demo session has been cancelled.",
        )
    if _looks_like_tax_or_legal_question(body):
        return ConversationReply(
            "escalate",
            "I have recorded your question for CA review.\n\n"
            "OBLIQ does not provide final tax or legal decisions through WhatsApp.",
        )
    return ConversationReply(
        "unknown",
        "The live OBLIQ WhatsApp connection is active.\n\n"
        "Reply STATUS to view the GST checklist or HELP for available commands.",
    )
