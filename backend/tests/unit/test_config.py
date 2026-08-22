import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_parse_comma_separated_cors_origins(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:3000,https://dashboard.example.com",
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://dashboard.example.com",
    ]


def test_vonage_runtime_configuration_requires_all_security_values() -> None:
    with pytest.raises(ValidationError, match="Vonage WhatsApp configuration is incomplete"):
        Settings(
            app_env="development",
            whatsapp_provider="vonage",
            vonage_api_key="",
            vonage_api_secret="",
            vonage_signature_secret="",
            vonage_whatsapp_from="",
            vonage_sandbox_join_message="",
            public_base_url="",
            whatsapp_demo_token_pepper="",
            whatsapp_phone_hash_pepper="",
            whatsapp_phone_encryption_key="",
            _env_file=None,
        )


def test_non_test_runtime_rejects_mock_or_removed_providers() -> None:
    with pytest.raises(ValidationError, match="WHATSAPP_PROVIDER must be vonage"):
        Settings(app_env="development", whatsapp_provider="mock", _env_file=None)
    with pytest.raises(ValidationError, match="WHATSAPP_PROVIDER must be vonage"):
        Settings(app_env="development", whatsapp_provider="unsupported", _env_file=None)
    with pytest.raises(ValidationError, match="WHATSAPP_PROVIDER must be vonage"):
        Settings(app_env="development", whatsapp_provider="twilio", _env_file=None)


def test_non_test_runtime_requires_secure_upload_pepper() -> None:
    with pytest.raises(ValidationError, match="UPLOAD_TOKEN_PEPPER"):
        Settings(
            app_env="development",
            whatsapp_provider="vonage",
            vonage_api_key="api-key",
            vonage_api_secret="api-secret",
            vonage_signature_secret="signature-secret",
            vonage_whatsapp_from="447700900001",
            vonage_sandbox_join_message="allow test",
            public_base_url="https://api.example.com",
            whatsapp_demo_token_pepper="demo-pepper",
            whatsapp_phone_hash_pepper="phone-pepper",
            whatsapp_phone_encryption_key="encryption-key",
            upload_token_pepper="",
            _env_file=None,
        )


def test_default_secure_upload_extensions_include_docx() -> None:
    settings = Settings(app_env="test", whatsapp_provider="mock", _env_file=None)

    assert "docx" in settings.allowed_extensions
