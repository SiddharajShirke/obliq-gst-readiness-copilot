import os
import time

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings, is_public_https_origin, normalize_origin
from app.repositories import DataStore, get_store

router = APIRouter(tags=["health"])
PROCESS_STARTED_AT = time.monotonic()


@router.get("/health")
async def health(
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    def safe_origin(value: str) -> str | None:
        try:
            return normalize_origin(value)
        except ValueError:
            return None

    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.app_env,
        "database": store.name,
        "ai_mode": settings.ai_mode,
        "whatsapp_provider": settings.whatsapp_provider,
        "embedding_warmup_enabled": settings.embedding_warmup_enabled,
        "frontend_origin": safe_origin(settings.frontend_url),
        "public_api_origin": safe_origin(settings.public_base_url),
        "live_upload_origin_ready": is_public_https_origin(settings.frontend_url),
        "uptime_seconds": int(time.monotonic() - PROCESS_STARTED_AT),
        "release": os.getenv("RENDER_GIT_COMMIT", "local")[:12],
    }
