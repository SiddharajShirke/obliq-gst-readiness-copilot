from __future__ import annotations

from app.config import Settings
from app.services.whatsapp.base import WhatsAppProvider
from app.services.whatsapp.mock import MockWhatsAppProvider
from app.services.whatsapp.vonage import VonageWhatsAppProvider


def get_whatsapp_provider(settings: Settings) -> WhatsAppProvider:
    if settings.whatsapp_provider == "vonage":
        return VonageWhatsAppProvider(
            api_key=settings.vonage_api_key,
            api_secret=settings.vonage_api_secret,
            signature_secret=settings.vonage_signature_secret,
            whatsapp_from=settings.vonage_whatsapp_from,
            messages_base_url=settings.vonage_messages_base_url,
        )
    if (
        settings.whatsapp_provider == "mock"
        and settings.app_env.lower() in {"test", "development"}
        and settings.use_in_memory_db
    ):
        return MockWhatsAppProvider()
    if settings.whatsapp_provider == "mock":
        raise RuntimeError("The mock WhatsApp provider requires isolated in-memory data")
    raise RuntimeError(f"Unsupported WhatsApp provider: {settings.whatsapp_provider}")
