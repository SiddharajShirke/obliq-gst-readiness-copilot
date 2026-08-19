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
