from __future__ import annotations

import os

from cryptography.fernet import Fernet

# Runtime defaults are intentionally strict. Tests opt into the internal mock transport.
os.environ["APP_ENV"] = "test"
os.environ["USE_IN_MEMORY_DB"] = "true"
os.environ["WHATSAPP_PROVIDER"] = "mock"
os.environ["WHATSAPP_DEMO_TOKEN_PEPPER"] = "test-token-pepper"
os.environ["WHATSAPP_PHONE_HASH_PEPPER"] = "test-phone-pepper"
os.environ["WHATSAPP_PHONE_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["VONAGE_API_KEY"] = "test-api-key"
os.environ["VONAGE_API_SECRET"] = "test-api-secret"
os.environ["VONAGE_SIGNATURE_SECRET"] = "test-signature-secret"
os.environ["VONAGE_WHATSAPP_FROM"] = "447700900001"
os.environ["VONAGE_SANDBOX_JOIN_MESSAGE"] = "allow test-sandbox"
os.environ["PUBLIC_BASE_URL"] = "https://api.example.test"
