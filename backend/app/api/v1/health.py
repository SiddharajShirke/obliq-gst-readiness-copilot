from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.repositories import DataStore, get_store

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.app_env,
        "database": store.name,
        "ai_mode": settings.ai_mode,
        "whatsapp_provider": settings.whatsapp_provider,
    }
