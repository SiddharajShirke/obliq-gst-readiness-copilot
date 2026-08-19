"""Document intake and controlled processing workflow."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import date
from pathlib import Path
from typing import Any

from app.agents.document_workflow import DocumentState, build_document_graph
from app.config import Settings
from app.prompts.extraction import INVOICE_EXTRACTION_SYSTEM_PROMPT
from app.repositories.base import DataStore
from app.schemas.documents import InvoiceExtraction
from app.services.document_processing.classifier import classify_document
from app.services.document_processing.parsers import parse_document_content
from app.services.llm.providers import complete_document_json, complete_json
from app.services.validation import (
    InvoiceInput,
    detect_duplicate_groups,
    normalize_invoice_number,
    validate_invoice,
)


def resolve_demo_data_root(
    *,
    module_file: Path | None = None,
    working_directory: Path | None = None,
) -> Path:
    """Locate the repository/container demo-data directory without hard-coding depth."""

    module_path = (module_file or Path(__file__)).resolve()
    cwd = (working_directory or Path.cwd()).resolve()
    candidates = [cwd, *module_path.parents]
    for root in candidates:
        demo_dir = root / "demo_data"
        if demo_dir.is_dir():
            return demo_dir
    return cwd / "demo_data"


class DocumentProcessor:
    def __init__(self, store: DataStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self.graph = build_document_graph(self)

    async def process(self, document_id: str) -> dict[str, Any]:
        return await self.graph.ainvoke({"document_id": document_id, "status": "started"})

    async def load_document(self, state: DocumentState) -> dict[str, Any]:
        document = await self.store.get_row("documents", state["document_id"])
        if not document:
            raise ValueError("Document not found")
        content = await self.store.download_file(self.settings.supabase_documents_bucket, document["storage_path"])
        await self.store.update_row("documents", document["id"], {"processing_status": "processing"})
        return {"document": document, "content": content, "status": "loaded"}

    async def classify_document(self, state: DocumentState) -> dict[str, Any]:
        document = state["document"]
        detected = classify_document(document["original_name"], document["mime_type"], state["content"])
        await self.store.update_row("documents", document["id"], {"document_type": detected})
        return {"document_type": detected, "status": "classified"}

    def _fixture(self, filename: str) -> dict[str, Any] | None:
        demo_root = resolve_demo_data_root()
        candidates = [
            demo_root / "extractions" / f"{filename}.json",
            demo_root / "extractions" / f"{Path(filename).stem}.json",
        ]
        for path in candidates:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    async def parse_and_extract(self, state: DocumentState) -> dict[str, Any]:
        document = state["document"]
        fixture = self._fixture(document["original_name"]) if self.settings.ai_mode == "mock" else None
        if fixture:
            raw_text = fixture.get("raw_text", "")
            structured = fixture.get("structured_data", fixture)
        else:
            raw_text, structured = parse_document_content(
                document["original_name"],
                state["document_type"],
                document["mime_type"],
                state["content"],
                tesseract_cmd=self.settings.tesseract_cmd,
            )
            if (
                self.settings.ai_mode == "live"
                and state["document_type"] in {"sales_invoice", "purchase_invoice"}
                and float(structured.get("overall_confidence", 0)) < 0.8
            ):
                inferred_mime = (
                    document.get("mime_type")
                    if document.get("mime_type") != "application/octet-stream"
                    else mimetypes.guess_type(document["original_name"])[0]
                ) or "application/octet-stream"
                if (
                    self.settings.vision_llm_provider == "gemini"
                    and inferred_mime.startswith(("image/", "application/pdf"))
                ):
                    structured = await complete_document_json(
                        self.settings,
                        system_prompt=INVOICE_EXTRACTION_SYSTEM_PROMPT,
                        user_prompt=(
                            f"Document type: {state['document_type']}. "
                            "Extract only visible GST invoice fields and return the required JSON object."
                        ),
                        content=state["content"],
                        mime_type=inferred_mime,
                    )
                else:
                    structured = await complete_json(
                        self.settings,
                        system_prompt=INVOICE_EXTRACTION_SYSTEM_PROMPT,
                        user_prompt=f"Document type: {state['document_type']}\n\nInvoice text:\n{raw_text[:18000]}",
                    )

        invoice_rows = structured.get("rows", [])
        if state["document_type"] in {"sales_invoice", "purchase_invoice"}:
            validated = InvoiceExtraction.model_validate(structured)
            structured = validated.model_dump(mode="json")
            invoice_rows = [structured]
        return {
            "raw_text": raw_text,
            "structured_data": structured,
            "invoice_rows": invoice_rows,
            "status": "extracted",
        }

    async def persist_extraction(self, state: DocumentState) -> dict[str, Any]:
        document = state["document"]
        structured = state["structured_data"]
        existing = await self.store.list_rows("document_extractions", {"document_id": document["id"]}, limit=1)
        extraction_data = {
            "document_id": document["id"],
            "document_type": state["document_type"],
            "raw_text": state.get("raw_text", ""),
            "structured_data": structured,
            "original_structured_data": structured,
            "field_confidences": structured.get("field_confidences", {}),
            "overall_confidence": structured.get("overall_confidence", 0.95 if structured.get("rows") else 0.0),
            "provider": "mock" if self.settings.ai_mode == "mock" else self.settings.text_llm_provider,
            "model_name": "deterministic-parser" if self.settings.ai_mode == "mock" else self.settings.groq_model,
            "review_status": "pending",
        }
        if existing:
            await self.store.update_row("document_extractions", existing[0]["id"], extraction_data)
        else:
            await self.store.insert_row("document_extractions", extraction_data)

        old_records = await self.store.list_rows("invoice_records", {"document_id": document["id"]})
        for old in old_records:
            await self.store.delete_row("invoice_records", old["id"])

        category = {
            "sales_register": "sales",
            "purchase_register": "purchase",
            "sales_invoice": "sales",
            "purchase_invoice": "purchase",
            "gstr2b": "gstr2b",
        }.get(state["document_type"], "purchase")
        inserted: list[dict[str, Any]] = []
        for source in state.get("invoice_rows", []):
            record = {
                "firm_id": document["firm_id"],
                "client_id": document["client_id"],
                "application_id": document["application_id"],
                "document_id": document["id"],
                "invoice_category": source.get("invoice_category") or category,
                "supplier_name": source.get("supplier_name"),
                "supplier_gstin": source.get("supplier_gstin"),
                "customer_name": source.get("customer_name"),
                "customer_gstin": source.get("customer_gstin"),
                "invoice_number": source.get("invoice_number"),
                "invoice_number_normalized": normalize_invoice_number(source.get("invoice_number")),
                "invoice_date": source.get("invoice_date"),
                "place_of_supply": source.get("place_of_supply"),
                "taxable_value": source.get("taxable_value", 0),
                "cgst": source.get("cgst", 0),
                "sgst": source.get("sgst", 0),
                "igst": source.get("igst", 0),
                "cess": source.get("cess", 0),
                "invoice_total": source.get("invoice_total", 0),
                "hsn_sac": source.get("hsn_sac"),
                "line_items": source.get("line_items", []),
                "source_type": state["document_type"],
                "review_status": "pending",
            }
            inserted.append(await self.store.insert_row("invoice_records", record))
        return {"invoice_rows": inserted, "status": "persisted"}

    @staticmethod
    def _invoice_input(row: dict[str, Any]) -> InvoiceInput:
        raw_date = row.get("invoice_date")
        parsed_date = date.fromisoformat(str(raw_date)[:10]) if raw_date else None
        return InvoiceInput(
            supplier_name=row.get("supplier_name"),
            supplier_gstin=row.get("supplier_gstin"),
            customer_name=row.get("customer_name"),
            customer_gstin=row.get("customer_gstin"),
            invoice_number=row.get("invoice_number"),
            invoice_date=parsed_date,
            taxable_value=row.get("taxable_value", 0),
            cgst=row.get("cgst", 0),
            sgst=row.get("sgst", 0),
            igst=row.get("igst", 0),
            cess=row.get("cess", 0),
            invoice_total=row.get("invoice_total", 0),
            metadata={"record_id": row.get("id")},
        )

    async def validate_document(self, state: DocumentState) -> dict[str, Any]:
        document = state["document"]
        application = await self.store.get_row("applications", document["application_id"])
        client = await self.store.get_row("clients", document["client_id"])
        if not application or not client:
            raise ValueError("Document application or client not found")

        old_findings = await self.store.list_rows("validation_findings", {"document_id": document["id"]})
        for finding in old_findings:
            await self.store.delete_row("validation_findings", finding["id"])

        findings: list[dict[str, Any]] = []
        inputs: list[InvoiceInput] = []
        for row in state.get("invoice_rows", []):
            invoice = self._invoice_input(row)
            inputs.append(invoice)
            for finding in validate_invoice(
                invoice,
                period_start=date.fromisoformat(str(application["period_start"])[:10]),
                period_end=date.fromisoformat(str(application["period_end"])[:10]),
                expected_customer_gstin=client.get("gstin") if row.get("invoice_category") == "sales" else None,
            ):
                findings.append(await self.store.insert_row("validation_findings", {
                    "firm_id": document["firm_id"],
                    "application_id": document["application_id"],
                    "document_id": document["id"],
                    "invoice_record_id": row.get("id"),
                    "finding_type": finding.finding_type,
                    "severity": finding.severity,
                    "message": finding.message,
                    "details": finding.details,
                    "status": "open",
                }))

        all_records = await self.store.list_rows("invoice_records", {"application_id": document["application_id"]})
        all_inputs = [self._invoice_input(row) for row in all_records]
        for group in detect_duplicate_groups(all_inputs):
            record_ids = [item.metadata.get("record_id") for item in group]
            if not any(row.get("id") in record_ids for row in state.get("invoice_rows", [])):
                continue
            findings.append(await self.store.insert_row("validation_findings", {
                "firm_id": document["firm_id"],
                "application_id": document["application_id"],
                "document_id": document["id"],
                "finding_type": "duplicate_invoice",
                "severity": "medium",
                "message": "A possible duplicate invoice was detected.",
                "details": {"invoice_record_ids": record_ids},
                "status": "open",
            }))

        await self.store.update_row("documents", document["id"], {"processing_status": "needs_review"})
        await self.store.update_row("applications", document["application_id"], {"status": "extraction_review"})
        return {"findings": findings, "status": "awaiting_human_review"}


async def persist_uploaded_document(
    store: DataStore,
    settings: Settings,
    *,
    application: dict[str, Any],
    client: dict[str, Any],
    filename: str,
    mime_type: str,
    content: bytes,
    requirement_type: str,
    source: str,
    uploaded_by_user_id: str | None = None,
    uploaded_from_phone: str | None = None,
) -> dict[str, Any]:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in settings.allowed_extensions:
        raise ValueError(f"Unsupported file extension: {extension}")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")

    digest = hashlib.sha256(content).hexdigest()
    requirement_rows = await store.list_rows(
        "document_requirements",
        {"application_id": application["id"], "requirement_type": requirement_type},
        limit=1,
    )
    requirement = requirement_rows[0] if requirement_rows else None
    if requirement is None:
        raise ValueError(f"Unknown document checklist category: {requirement_type}")
    safe_name = "".join(character if character.isalnum() or character in ".-_" else "_" for character in Path(filename).name)
    path = f"{application['firm_id']}/{client['id']}/{application['id']}/{digest[:12]}-{safe_name}"
    await store.upload_file(settings.supabase_documents_bucket, path, content, mime_type)
    document = await store.insert_row("documents", {
        "firm_id": application["firm_id"],
        "client_id": client["id"],
        "application_id": application["id"],
        "requirement_id": requirement.get("id") if requirement else None,
        "source": source,
        "original_name": filename,
        "mime_type": mime_type or "application/octet-stream",
        "storage_path": path,
        "file_size": len(content),
        "sha256": digest,
        "document_type": classify_document(filename, mime_type, content),
        "processing_status": "uploaded",
        "uploaded_by_user_id": uploaded_by_user_id,
        "uploaded_from_phone": uploaded_from_phone,
    })
    if requirement:
        await store.update_row("document_requirements", requirement["id"], {"status": "received"})
    result = await DocumentProcessor(store, settings).process(document["id"])
    return (await store.get_row("documents", document["id"])) or {**document, "workflow": result}
