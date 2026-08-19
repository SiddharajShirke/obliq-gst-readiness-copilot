from __future__ import annotations

from app.config import Settings
from app.services.whatsapp.base import WhatsAppProvider
from app.services.whatsapp.meta import MetaCredentials, MetaWhatsAppProvider
from app.services.whatsapp.mock import MockWhatsAppProvider


def load_meta_credentials(settings: Settings) -> MetaCredentials:
    path = settings.local_meta_credentials_file
    if settings.allow_local_credential_setup and path.exists():
        return MetaCredentials.from_file(path)
    return MetaCredentials(
        access_token=settings.meta_access_token,
        phone_number_id=settings.meta_phone_number_id,
        waba_id=settings.meta_waba_id,
        app_secret=settings.meta_app_secret,
        webhook_verify_token=settings.meta_webhook_verify_token,
        graph_api_version=settings.meta_graph_api_version,
        test_recipient_number=settings.meta_test_recipient_number,
        document_request_template=settings.meta_document_request_template,
        reminder_template=settings.meta_reminder_template,
    )


def get_whatsapp_provider(settings: Settings) -> WhatsAppProvider:
    if settings.whatsapp_provider == "meta":
        credentials = load_meta_credentials(settings)
        if not credentials.access_token or not credentials.phone_number_id:
            raise RuntimeError("Meta access token and Phone Number ID are required")
        return MetaWhatsAppProvider(credentials)
    return MockWhatsAppProvider()
