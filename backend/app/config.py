"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "OBLIQ GST Readiness Copilot"
    app_env: str = "development"
    app_debug: bool = True
    demo_mode: bool = True
    use_in_memory_db: bool = True
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    api_v1_prefix: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    log_level: str = "INFO"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""
    database_url: str = ""
    supabase_documents_bucket: str = "gst-documents"
    supabase_knowledge_bucket: str = "knowledge-documents"
    supabase_exports_bucket: str = "exports"

    ai_mode: str = "mock"
    text_llm_provider: str = "groq"
    vision_llm_provider: str = "nvidia"
    llm_fallback_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_heavy_model: str = ""
    groq_rag_model: str = ""
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_small_model: str = ""
    nvidia_vision_model: str = ""
    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_vision_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    openai_text_model: str = "gpt-5-mini"
    openai_vision_model: str = "gpt-5-mini"

    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = 384
    rag_vector_top_k: int = 12
    rag_final_top_k: int = 5
    rag_min_similarity: float = 0.45
    rag_chunk_size: int = 900
    rag_chunk_overlap: int = 140
    rag_generation_timeout_seconds: float = 1.5
    rag_max_output_tokens: int = 800

    ocr_enabled: bool = True
    tesseract_cmd: str = ""
    max_upload_mb: int = 20
    bulk_upload_max_files: int = 20
    bulk_upload_max_total_mb: int = 100
    allowed_upload_extensions: str = "pdf,png,jpg,jpeg,csv,xlsx,docx,json"
    upload_link_ttl_hours: int = 72
    upload_token_pepper: str = ""
    local_upload_dir: Path = Path(".runtime/uploads")
    local_export_dir: Path = Path(".runtime/exports")

    whatsapp_provider: str = "vonage"
    vonage_api_key: str = ""
    vonage_api_secret: str = ""
    vonage_signature_secret: str = ""
    vonage_whatsapp_from: str = ""
    vonage_sandbox_join_message: str = ""
    vonage_messages_base_url: str = "https://messages-sandbox.nexmo.com"
    public_base_url: str = ""
    whatsapp_demo_token_expiry_minutes: int = 20
    whatsapp_demo_session_expiry_minutes: int = 120
    whatsapp_demo_data_retention_hours: int = 24
    whatsapp_demo_token_pepper: str = ""
    whatsapp_phone_hash_pepper: str = ""
    whatsapp_phone_encryption_key: str = ""

    demo_admin_email: str = "demo.admin@obliq.local"
    demo_admin_password: str = "ChangeMe123!"
    demo_preparer_email: str = "demo.preparer@obliq.local"
    demo_preparer_password: str = "ChangeMe123!"
    demo_reviewer_email: str = "demo.reviewer@obliq.local"
    demo_reviewer_password: str = "ChangeMe123!"
    demo_reset_on_start: bool = False
    demo_seed_data: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_whatsapp_runtime(self) -> Settings:
        if self.whatsapp_provider == "mock" and self.app_env == "test":
            return self
        if self.whatsapp_provider != "vonage":
            raise ValueError("WHATSAPP_PROVIDER must be vonage outside automated tests")
        required = {
            "VONAGE_API_KEY": self.vonage_api_key,
            "VONAGE_API_SECRET": self.vonage_api_secret,
            "VONAGE_SIGNATURE_SECRET": self.vonage_signature_secret,
            "VONAGE_WHATSAPP_FROM": self.vonage_whatsapp_from,
            "VONAGE_SANDBOX_JOIN_MESSAGE": self.vonage_sandbox_join_message,
            "VONAGE_MESSAGES_BASE_URL": self.vonage_messages_base_url,
            "PUBLIC_BASE_URL": self.public_base_url,
            "WHATSAPP_DEMO_TOKEN_PEPPER": self.whatsapp_demo_token_pepper,
            "WHATSAPP_PHONE_HASH_PEPPER": self.whatsapp_phone_hash_pepper,
            "WHATSAPP_PHONE_ENCRYPTION_KEY": self.whatsapp_phone_encryption_key,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("Vonage WhatsApp configuration is incomplete: " + ", ".join(missing))
        if not self.upload_token_pepper:
            raise ValueError("Secure upload configuration is incomplete: UPLOAD_TOKEN_PEPPER")
        return self

    @model_validator(mode="after")
    def validate_ai_runtime(self) -> Settings:
        if self.ai_mode != "live":
            return self
        required = {
            "GROQ_API_KEY": self.groq_api_key,
            "GROQ_HEAVY_MODEL": self.groq_heavy_model or self.groq_model,
            "NVIDIA_API_KEY": self.nvidia_api_key,
            "NVIDIA_BASE_URL": self.nvidia_base_url,
            "NVIDIA_SMALL_MODEL": self.nvidia_small_model,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("Live Phase 3 AI configuration is incomplete: " + ", ".join(missing))
        return self

    @model_validator(mode="after")
    def validate_production_runtime(self) -> Settings:
        if self.app_env.lower() != "production":
            return self

        violations: list[str] = []
        if self.use_in_memory_db:
            violations.append("USE_IN_MEMORY_DB=false")
        if self.ai_mode != "live":
            violations.append("AI_MODE=live")
        if self.app_debug:
            violations.append("APP_DEBUG=false")
        if not self.supabase_url:
            violations.append("SUPABASE_URL")
        if not self.supabase_service_role_key:
            violations.append("SUPABASE_SERVICE_ROLE_KEY")
        if not self.frontend_url.startswith("https://"):
            violations.append("FRONTEND_URL must be an HTTPS origin")
        if not self.public_base_url.startswith("https://"):
            violations.append("PUBLIC_BASE_URL must be an HTTPS origin")
        if not self.cors_origins or any(
            not origin.startswith("https://") for origin in self.cors_origins
        ):
            violations.append("CORS_ORIGINS must contain only HTTPS production origins")
        if self.embedding_dimension != 384:
            violations.append("EMBEDDING_DIMENSION=384")

        if violations:
            raise ValueError(
                "Production configuration is unsafe or incomplete: " + ", ".join(violations)
            )
        return self

    @property
    def effective_groq_model(self) -> str:
        return self.groq_heavy_model or self.groq_model

    @property
    def effective_groq_rag_model(self) -> str:
        return self.groq_rag_model or self.effective_groq_model

    @property
    def allowed_extensions(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_upload_extensions.split(",")}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
