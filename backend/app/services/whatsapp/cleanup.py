from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.repositories.base import DataStore


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def cleanup_demo_sessions(store: DataStore, settings: Settings) -> dict[str, int]:
    now = datetime.now(UTC)
    retention_cutoff = now - timedelta(
        hours=settings.whatsapp_demo_data_retention_hours
    )
    expired = 0
    deleted = 0
    sessions = await store.list_rows("whatsapp_demo_sessions")
    for session in sessions:
        if (
            session.get("status") not in {"expired", "cancelled", "completed"}
            and _parse_timestamp(session["expires_at"]) <= now
        ):
            await store.update_row(
                "whatsapp_demo_sessions",
                session["id"],
                {
                    "status": "expired",
                    "judge_phone_hash": None,
                    "judge_phone_encrypted": None,
                    "provider_user_id_hash": None,
                    "anonymized_at": now.isoformat(),
                },
            )
            expired += 1

        if _parse_timestamp(session["created_at"]) > retention_cutoff:
            continue
        for message in await store.list_rows(
            "whatsapp_messages", {"demo_session_id": session["id"]}
        ):
            await store.delete_row("whatsapp_messages", message["id"])
        application_id = session.get("session_application_id")
        if application_id:
            for document in await store.list_rows(
                "documents", {"application_id": application_id}
            ):
                if document.get("storage_path"):
                    await store.delete_file(
                        document.get("storage_bucket")
                        or settings.supabase_documents_bucket,
                        document["storage_path"],
                    )
                await store.delete_row("documents", document["id"])
            for upload_link in await store.list_rows(
                "upload_links", {"application_id": application_id}
            ):
                await store.delete_row("upload_links", upload_link["id"])
            for requirement in await store.list_rows(
                "document_requirements", {"application_id": application_id}
            ):
                await store.delete_row("document_requirements", requirement["id"])
            await store.delete_row("applications", application_id)
        await store.delete_row("whatsapp_demo_sessions", session["id"])
        deleted += 1

    # Invalid/expired START attempts have no session row to cascade through. They
    # remain temporary demo data and must not retain encrypted phone values past
    # the same retention window. Ordinary approved reminder messages are kept.
    for message in await store.list_rows("whatsapp_messages"):
        metadata = message.get("metadata") or {}
        if (
            message.get("demo_session_id") is None
            and metadata.get("temporary_demo") is True
            and _parse_timestamp(message["created_at"]) <= retention_cutoff
        ):
            await store.delete_row("whatsapp_messages", message["id"])
    return {"expired": expired, "deleted": deleted}
