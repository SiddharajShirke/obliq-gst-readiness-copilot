import pytest

from app.config import Settings
from app.services.document_processing.processor import DocumentProcessor
from app.services.document_processing.routing import choose_extraction_route
from app.services.llm.providers import (
    build_nvidia_text_payload,
    build_nvidia_vision_payload,
)


def test_clean_tabular_files_are_deterministic_only() -> None:
    assert choose_extraction_route("sales_register", ".csv", has_clean_text=True) == "deterministic"
    assert (
        choose_extraction_route("purchase_register", ".xlsx", has_clean_text=True)
        == "deterministic"
    )


def test_small_and_complex_tasks_route_to_the_approved_provider() -> None:
    assert choose_extraction_route("sales_invoices", ".pdf", has_clean_text=True) == "nvidia"
    assert choose_extraction_route("credit_debit_notes", ".pdf", has_clean_text=False) == "groq"
    assert (
        choose_extraction_route("gst_special_transactions", ".pdf", has_clean_text=False) == "groq"
    )
    assert (
        choose_extraction_route("sales_invoices", ".png", has_clean_text=False, vision_capable=True)
        == "nvidia"
    )
    assert (
        choose_extraction_route(
            "sales_invoices", ".png", has_clean_text=False, vision_capable=False
        )
        == "groq"
    )


def test_nvidia_payloads_use_environment_selected_models() -> None:
    text_payload = build_nvidia_text_payload(
        model="nvidia-small-model",
        system_prompt="Return JSON",
        user_prompt="Classify this document",
    )
    assert text_payload["model"] == "nvidia-small-model"
    assert text_payload["response_format"] == {"type": "json_object"}

    vision_payload = build_nvidia_vision_payload(
        model="nvidia-vision-model",
        system_prompt="Return JSON",
        user_prompt="Read this image",
        content=b"image-bytes",
        mime_type="image/png",
    )
    assert vision_payload["model"] == "nvidia-vision-model"
    assert (
        "data:image/png;base64," in vision_payload["messages"][1]["content"][1]["image_url"]["url"]
    )


def test_live_ai_requires_nvidia_and_groq_without_gemini() -> None:
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        Settings(
            app_env="test",
            whatsapp_provider="mock",
            ai_mode="live",
            groq_api_key="groq-key",
            groq_heavy_model="groq-heavy",
            nvidia_api_key="",
            nvidia_base_url="https://integrate.api.nvidia.com/v1",
            nvidia_small_model="nvidia-small",
        )

    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        ai_mode="live",
        groq_api_key="groq-key",
        groq_heavy_model="groq-heavy",
        nvidia_api_key="nvidia-key",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
        nvidia_small_model="nvidia-small",
        gemini_api_key="",
    )
    assert settings.groq_heavy_model == "groq-heavy"
    assert settings.nvidia_small_model == "nvidia-small"


@pytest.mark.asyncio
async def test_schema_invalid_nvidia_extraction_falls_back_to_groq(monkeypatch) -> None:
    class ApplicationStore:
        async def get_row(self, table: str, row_id: str):
            assert table == "applications"
            return {"id": row_id, "period_label": "May 2026"}

    calls: list[str] = []

    async def invalid_nvidia(*args, **kwargs):
        calls.append("nvidia")
        return {
            "rows": [
                {
                    "document_type": "sales_invoices",
                    "document_number": "INV-INVALID",
                    "taxable_value": {"not": "a decimal"},
                }
            ]
        }

    async def valid_groq(*args, **kwargs):
        calls.append("groq")
        return {
            "rows": [
                {
                    "document_type": "sales_invoices",
                    "document_number": "INV-VALID",
                    "taxable_value": "12500.00",
                }
            ]
        }

    monkeypatch.setattr(
        "app.services.document_processing.processor.read_pdf_text",
        lambda content: "Invoice INV-VALID taxable value 12500.00",
    )
    monkeypatch.setattr(
        "app.services.document_processing.processor.complete_nvidia_json", invalid_nvidia
    )
    monkeypatch.setattr(
        "app.services.document_processing.processor.complete_groq_json", valid_groq
    )
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        ai_mode="live",
        groq_api_key="groq-key",
        groq_heavy_model="groq-heavy",
        nvidia_api_key="nvidia-key",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
        nvidia_small_model="nvidia-small",
        _env_file=None,
    )
    processor = DocumentProcessor(ApplicationStore(), settings)

    result = await processor.parse_and_extract(
        {
            "document": {
                "id": "document-id",
                "application_id": "application-id",
                "original_name": "invoice.pdf",
                "mime_type": "application/pdf",
            },
            "document_type": "sales_invoices",
            "content": b"synthetic-pdf",
        }
    )

    assert calls == ["nvidia", "groq"]
    assert result["provider"] == "groq"
    assert result["fallback_reason"] == "ValidationError"
    assert result["invoice_rows"][0]["document_number"] == "INV-VALID"


@pytest.mark.asyncio
async def test_processing_failure_never_leaves_document_stuck_in_processing() -> None:
    class TrackingStore:
        def __init__(self) -> None:
            self.updates: list[tuple[str, str, dict]] = []

        async def update_row(self, table: str, row_id: str, data: dict):
            self.updates.append((table, row_id, data))
            return {"id": row_id, **data}

    class FailingGraph:
        async def ainvoke(self, state):
            raise RuntimeError("provider failed")

    store = TrackingStore()
    settings = Settings(app_env="test", whatsapp_provider="mock", _env_file=None)
    processor = DocumentProcessor(store, settings)
    processor.graph = FailingGraph()

    with pytest.raises(RuntimeError, match="provider failed"):
        await processor.process("document-id")

    assert store.updates == [
        (
            "documents",
            "document-id",
            {"processing_status": "processing_failed", "processing_error": "RuntimeError"},
        )
    ]


@pytest.mark.asyncio
async def test_successful_retry_clears_previous_processing_error() -> None:
    class TrackingStore:
        def __init__(self) -> None:
            self.updates: list[tuple[str, str, dict]] = []

        async def update_row(self, table: str, row_id: str, data: dict):
            self.updates.append((table, row_id, data))
            return {"id": row_id, **data}

    class SuccessfulGraph:
        async def ainvoke(self, state):
            return {**state, "status": "awaiting_human_review"}

    store = TrackingStore()
    settings = Settings(app_env="test", whatsapp_provider="mock", _env_file=None)
    processor = DocumentProcessor(store, settings)
    processor.graph = SuccessfulGraph()

    result = await processor.process("document-id")

    assert result["status"] == "awaiting_human_review"
    assert store.updates == [
        ("documents", "document-id", {"processing_error": None})
    ]
