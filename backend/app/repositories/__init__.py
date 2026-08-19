from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.repositories.base import DataStore
from app.repositories.memory import MemoryStore
from app.repositories.supabase import SupabaseStore


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    settings = get_settings()
    if settings.use_in_memory_db:
        return MemoryStore(settings)
    return SupabaseStore(settings)


__all__ = ["DataStore", "get_store"]
