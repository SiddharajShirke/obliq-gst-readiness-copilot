import pytest
from pydantic import ValidationError

from app.config import Settings


def production_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "app_env": "production",
        "app_debug": False,
        "demo_mode": False,
        "use_in_memory_db": False,
        "frontend_url": "https://obliq.example",
        "backend_url": "https://api.obliq.example",
        "cors_origins": ["https://obliq.example"],
        "supabase_url": "https://project.supabase.co",
        "supabase_anon_key": "public-anon-key",
        "supabase_service_role_key": "service-role-key",
        "ai_mode": "live",
        "vision_llm_provider": "nvidia",
        "groq_api_key": "groq-key",
        "groq_heavy_model": "groq-model",
        "nvidia_api_key": "nvidia-key",
        "nvidia_base_url": "https://integrate.api.nvidia.com/v1",
        "nvidia_small_model": "nvidia-model",
        "embedding_dimension": 384,
        "whatsapp_provider": "vonage",
        "vonage_api_key": "api-key",
        "vonage_api_secret": "api-secret",
        "vonage_signature_secret": "signature-secret",
        "vonage_whatsapp_from": "447700900001",
        "vonage_sandbox_join_message": "allow test",
        "public_base_url": "https://api.obliq.example",
        "whatsapp_demo_token_pepper": "demo-pepper",
        "whatsapp_phone_hash_pepper": "phone-pepper",
        "whatsapp_phone_encryption_key": "fernet-key",
        "upload_token_pepper": "upload-pepper",
    }
    values.update(overrides)
    return values


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


def test_local_memory_development_may_use_mock_whatsapp() -> None:
    settings = Settings(
        app_env="development",
        use_in_memory_db=True,
        whatsapp_provider="mock",
        _env_file=None,
    )

    assert settings.whatsapp_provider == "mock"


def test_non_test_runtime_rejects_mock_with_shared_data_or_removed_providers() -> None:
    with pytest.raises(ValidationError, match="WHATSAPP_PROVIDER must be vonage"):
        Settings(
            app_env="development",
            use_in_memory_db=False,
            whatsapp_provider="mock",
            _env_file=None,
        )
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


def test_live_vonage_rejects_localhost_upload_origin_by_default() -> None:
    with pytest.raises(
        ValidationError,
        match="Live Vonage requires FRONTEND_URL to be a public HTTPS origin",
    ):
        Settings(
            **production_values(
                app_env="development",
                frontend_url="http://localhost:3000",
            ),
            _env_file=None,
        )


def test_development_override_requires_explicit_opt_in_and_never_works_in_production() -> None:
    settings = Settings(
        **production_values(
            app_env="development",
            frontend_url="http://localhost:3000",
            allow_local_whatsapp_links=True,
        ),
        _env_file=None,
    )
    assert settings.allow_local_whatsapp_links is True

    with pytest.raises(ValidationError, match="ALLOW_LOCAL_WHATSAPP_LINKS=false"):
        Settings(
            **production_values(allow_local_whatsapp_links=True),
            _env_file=None,
        )


def test_default_secure_upload_extensions_include_docx() -> None:
    settings = Settings(app_env="test", whatsapp_provider="mock", _env_file=None)

    assert "docx" in settings.allowed_extensions


def test_active_default_vision_provider_is_nvidia_not_gemini() -> None:
    settings = Settings(app_env="test", whatsapp_provider="mock", _env_file=None)

    assert settings.vision_llm_provider == "nvidia"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"use_in_memory_db": True}, "USE_IN_MEMORY_DB=false"),
        ({"ai_mode": "mock"}, "AI_MODE=live"),
        ({"app_debug": True}, "APP_DEBUG=false"),
        ({"frontend_url": "http://localhost:3000"}, "FRONTEND_URL"),
        ({"public_base_url": "http://localhost:8000"}, "PUBLIC_BASE_URL"),
        ({"cors_origins": ["http://localhost:3000"]}, "CORS_ORIGINS"),
        ({"supabase_service_role_key": ""}, "SUPABASE_SERVICE_ROLE_KEY"),
        ({"embedding_dimension": 768}, "EMBEDDING_DIMENSION=384"),
    ],
)
def test_production_runtime_rejects_non_deployable_configuration(
    override: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(**production_values(**override), _env_file=None)


def test_production_runtime_accepts_hosted_phase4_configuration() -> None:
    settings = Settings(**production_values(), _env_file=None)

    assert settings.use_in_memory_db is False
    assert settings.ai_mode == "live"
    assert settings.whatsapp_provider == "vonage"
