import pytest

from app.agents.reminder_workflow import create_reminder_draft
from app.config import Settings
from app.repositories.memory import MemoryStore


@pytest.mark.asyncio
async def test_reminder_returns_capability_once_but_persists_only_redacted_text() -> None:
    store = MemoryStore(Settings(app_env="test", whatsapp_provider="mock", _env_file=None))
    token = "A" * 43
    reminder = await create_reminder_draft(
        store,
        {
            "firm_id": "11111111-1111-1111-1111-111111111111",
            "client": {
                "id": "client-1",
                "business_name": "Raj Traders",
            },
            "application": {
                "id": "application-1",
                "period_label": "April 2026",
            },
            "checklist": [{"label": "Sales Register", "status": "missing"}],
            "upload_url": f"https://app.example/upload/{token}",
            "reminder_type": "initial_document_request",
        },
    )

    assert token in reminder["draft_message"]
    stored = await store.get_row("reminders", reminder["id"])
    assert stored is not None
    assert token not in stored["draft_message"]
    assert "/upload/[REDACTED]" in stored["draft_message"]
