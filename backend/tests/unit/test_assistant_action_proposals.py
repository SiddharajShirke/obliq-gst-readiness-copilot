from __future__ import annotations

from app.config import Settings
from app.repositories.memory import MemoryStore


def test_memory_store_initializes_empty_action_proposals() -> None:
    store = MemoryStore(Settings(app_env="test", use_in_memory_db=True, _env_file=None))

    assert "assistant_action_proposals" in store.tables
    assert store.tables["assistant_action_proposals"] == []
