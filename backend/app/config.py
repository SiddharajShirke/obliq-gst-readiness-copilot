"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
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
    vision_llm_provider: str = "gemini"
    llm_fallback_provider: str = "openai"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
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

    ocr_enabled: bool = True
    tesseract_cmd: str = ""
    max_upload_mb: int = 20
    allowed_upload_extensions: str = "pdf,png,jpg,jpeg,csv,xlsx,json"
    upload_link_ttl_hours: int = 72
    upload_token_pepper: str = "prototype-pepper"
    local_upload_dir: Path = Path(".runtime/uploads")
    local_export_dir: Path = Path(".runtime/exports")

    whatsapp_provider: str = "mock"
    meta_access_token: str = ""
    meta_phone_number_id: str = ""
    meta_waba_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = "obliq-local-verify-token"
    meta_graph_api_version: str = "v26.0"
    meta_test_recipient_number: str = ""
    meta_document_request_template: str = "gst_document_request_v1"
    meta_reminder_template: str = "gst_document_reminder_v1"
    allow_local_credential_setup: bool = False
    local_meta_credentials_file: Path = Path(".runtime/meta_credentials.json")
    public_webhook_base_url: str = ""

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

    @property
    def allowed_extensions(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_upload_extensions.split(",")}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
