import asyncio
from io import BytesIO

import pandas as pd
import pytest
from reportlab.pdfgen import canvas

from app.config import Settings
from app.services.document_processing.classifier import classify_document
from app.services.document_processing.parsers import (
    extract_invoice_from_text,
    parse_tabular_document,
    read_pdf_text,
)
from app.services.document_processing.processor import DocumentProcessor, resolve_demo_data_root


def test_classifier_recognizes_register_and_gstr2b() -> None:
    assert (
        classify_document(
            "April_Sales_Register.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"",
        )
        == "sales_register"
    )
    assert (
        classify_document("gstr2b_april.json", "application/json", b'{"records": []}') == "gstr2b"
    )


def test_parse_tabular_document_maps_aliases_and_summarizes() -> None:
    frame = pd.DataFrame(
        [
            {
                "Invoice No": "P-1",
                "Invoice Date": "2026-04-10",
                "Supplier GSTIN": "27ABCDE1234F1Z5",
                "Taxable Amount": 1000,
                "CGST": 90,
                "SGST": 90,
                "Total": 1180,
            },
            {
                "Invoice No": "P-2",
                "Invoice Date": "2026-04-11",
                "Supplier GSTIN": "27ABCDE1234F1Z5",
                "Taxable Amount": 2000,
                "CGST": 180,
                "SGST": 180,
                "Total": 2360,
            },
        ]
    )
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)

    parsed = parse_tabular_document(buffer.getvalue(), ".xlsx", category="purchase")

    assert parsed.summary["invoice_count"] == 2
    assert parsed.summary["taxable_value"] == 3000.0
    assert parsed.rows[0]["invoice_number"] == "P-1"


def test_pdf_text_and_invoice_extraction_round_trip() -> None:
    output = BytesIO()
    pdf = canvas.Canvas(output)
    lines = [
        "Supplier: Sharma Distributors",
        "Supplier GSTIN: 27ABCDE1234F1Z5",
        "Customer: ABC Electronics",
        "Customer GSTIN: 29ABCDE1234F1Z3",
        "Invoice Number: SD-1042",
        "Invoice Date: 18-04-2026",
        "Taxable Value: 50000",
        "CGST: 4500",
        "SGST: 4500",
        "IGST: 0",
        "Invoice Total: 59000",
    ]
    y = 780
    for line in lines:
        pdf.drawString(60, y, line)
        y -= 24
    pdf.save()

    text = read_pdf_text(output.getvalue())
    extraction = extract_invoice_from_text(text, "purchase_invoice")

    assert extraction["supplier_name"] == "Sharma Distributors"
    assert extraction["invoice_number"] == "SD-1042"
    assert extraction["invoice_total"] == 59000.0


def test_resolve_demo_data_root_supports_container_layout(tmp_path) -> None:
    app_root = tmp_path / "app"
    module_file = app_root / "app" / "services" / "document_processing" / "processor.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("# synthetic module", encoding="utf-8")
    demo_dir = app_root / "demo_data"
    demo_dir.mkdir()

    assert resolve_demo_data_root(module_file=module_file, working_directory=app_root) == demo_dir


def test_deterministic_document_classification_overrides_ai_row_taxonomy() -> None:
    rows = DocumentProcessor._normalize_rows(
        [
            {
                "document_type": "purchase_invoice",
                "document_number": "PR-1",
                "source_document_id": "model-invented-id",
            }
        ],
        document_id="real-document-id",
        document_type="purchase_register",
    )

    assert rows[0]["document_type"] == "purchase_register"
    assert rows[0]["source_document_id"] == "real-document-id"


@pytest.mark.asyncio
async def test_document_processors_share_one_heavy_work_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two submissions must not run their heavy document graphs concurrently."""
    from app.services.document_processing import processor as processor_module

    active = 0
    peak = 0
    both_started = asyncio.Event()
    release = asyncio.Event()

    class FakeGraph:
        async def ainvoke(self, state: dict[str, object]) -> dict[str, object]:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            if active == 2:
                both_started.set()
            try:
                await asyncio.wait_for(release.wait(), timeout=0.1)
            except TimeoutError:
                pass
            finally:
                active -= 1
            return {**state, "status": "complete"}

    class FakeStore:
        async def update_row(
            self, table: str, row_id: str, data: dict[str, object]
        ) -> dict[str, object]:
            return {"id": row_id, **data}

    graph = FakeGraph()
    monkeypatch.setattr(processor_module, "build_document_graph", lambda _: graph)
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        heavy_processing_concurrency=1,
        _env_file=None,
    )
    first = processor_module.DocumentProcessor(FakeStore(), settings)  # type: ignore[arg-type]
    second = processor_module.DocumentProcessor(FakeStore(), settings)  # type: ignore[arg-type]

    tasks = [
        asyncio.create_task(first.process("document-a")),
        asyncio.create_task(second.process("document-b")),
    ]
    await asyncio.sleep(0.15)
    release.set()
    await asyncio.gather(*tasks)

    assert both_started.is_set() is False
    assert peak == 1


@pytest.mark.asyncio
async def test_live_ai_rate_limit_keeps_deterministic_evidence_for_ca_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.document_processing import processor as processor_module

    class FakeStore:
        async def get_row(self, table: str, row_id: str) -> dict[str, object] | None:
            if table == "applications":
                return {"id": row_id, "period_label": "August 2026"}
            return None

    async def rate_limited(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("provider rate limited")

    monkeypatch.setattr(processor_module, "complete_groq_json", rate_limited)
    monkeypatch.setattr(
        processor_module,
        "read_pdf_text",
        lambda _: "Invoice Number: DN-1\nTaxable Value: 1000\nInvoice Total: 1180",
    )
    monkeypatch.setattr(processor_module, "parse_normalized_pdf_tables", lambda *a, **k: None)
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        ai_mode="live",
        groq_api_key="test",
        groq_heavy_model="test-groq",
        nvidia_api_key="test",
        nvidia_small_model="test-nvidia",
        _env_file=None,
    )
    processor = processor_module.DocumentProcessor(FakeStore(), settings)  # type: ignore[arg-type]

    result = await processor.parse_and_extract(
        {
            "document": {
                "id": "document-id",
                "application_id": "application-id",
                "original_name": "05_Credit_and_Debit_Notes.pdf",
                "mime_type": "application/pdf",
            },
            "document_type": "credit_debit_notes",
            "content": b"%PDF synthetic",
        }
    )

    assert result["provider"] == "deterministic"
    assert result["task_type"] == "text_parse_ai_unavailable"
    assert result["fallback_reason"] == "groq_RuntimeError"
    assert result["invoice_rows"][0]["document_number"] == "DN-1"
