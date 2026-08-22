"""Document intake and controlled processing workflow."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.agents.document_workflow import DocumentState, build_document_graph
from app.config import Settings
from app.prompts.extraction import NORMALIZED_GST_EXTRACTION_SYSTEM_PROMPT
from app.repositories.base import DataStore
from app.schemas.documents import NormalizedGSTRecord
from app.services.document_processing.classifier import classify_document
from app.services.document_processing.parsers import (
    extract_invoice_from_text,
    parse_normalized_table,
    read_docx_text,
    read_image_text,
    read_pdf_text,
    read_scanned_pdf_text,
)
from app.services.document_processing.routing import choose_extraction_route
from app.services.document_processing.taxonomy import ALL_DOCUMENT_TYPES
from app.services.llm.providers import complete_groq_json, complete_nvidia_json
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
        try:
            result = await self.graph.ainvoke(
                {"document_id": document_id, "status": "started"}
            )
            await self.store.update_row("documents", document_id, {"processing_error": None})
            return result
        except Exception as exc:
            await self.store.update_row(
                "documents",
                document_id,
                {
                    "processing_status": "processing_failed",
                    "processing_error": type(exc).__name__,
                },
            )
            raise

    async def load_document(self, state: DocumentState) -> dict[str, Any]:
        document = await self.store.get_row("documents", state["document_id"])
        if not document:
            raise ValueError("Document not found")
        content = await self.store.download_file(
            self.settings.supabase_documents_bucket, document["storage_path"]
        )
        await self.store.update_row(
            "documents", document["id"], {"processing_status": "processing"}
        )
        return {"document": document, "content": content, "status": "loaded"}

    async def classify_document(self, state: DocumentState) -> dict[str, Any]:
        document = state["document"]
        current = document.get("document_type")
        detected = (
            current
            if current in ALL_DOCUMENT_TYPES and current != "unknown"
            else classify_document(
                document["original_name"], document["mime_type"], state["content"]
            )
        )
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
        document_type = state["document_type"]
        if document_type in {"developer_ground_truth", "unknown"}:
            raise ValueError("Excluded or unassigned documents cannot be processed")
        started = datetime.now(UTC)
        started_clock = time.perf_counter()
        fixture = (
            self._fixture(document["original_name"]) if self.settings.ai_mode == "mock" else None
        )
        if fixture:
            raw_text = fixture.get("raw_text", "")
            structured = fixture.get("structured_data", fixture)
            provider, model_name, task_type, fallback_reason = (
                "mock",
                "fixture",
                "fixture_extraction",
                None,
            )
        else:
            extension = Path(document["original_name"]).suffix.lower()
            application = await self.store.get_row("applications", document["application_id"])
            tax_period = (application or {}).get("period_label")
            if extension in {".csv", ".xlsx", ".xls", ".json"}:
                parsed = parse_normalized_table(
                    state["content"],
                    extension,
                    document_type=document_type,
                    source_document_id=document["id"],
                    tax_period=tax_period,
                )
                structured = {
                    "summary": parsed.summary,
                    "rows": [record.model_dump(mode="json") for record in parsed.records],
                    "column_mapping": parsed.column_mapping,
                }
                raw_text = ""
                provider, model_name, task_type, fallback_reason = (
                    "deterministic",
                    "pandas-openpyxl",
                    "structured_parse",
                    None,
                )
            else:
                if extension == ".pdf":
                    raw_text = read_pdf_text(state["content"])
                    if not raw_text and self.settings.ocr_enabled:
                        raw_text = read_scanned_pdf_text(
                            state["content"], tesseract_cmd=self.settings.tesseract_cmd
                        )
                elif extension in {".png", ".jpg", ".jpeg"}:
                    raw_text = (
                        read_image_text(state["content"], tesseract_cmd=self.settings.tesseract_cmd)
                        if self.settings.ocr_enabled
                        else ""
                    )
                elif extension == ".docx":
                    raw_text = read_docx_text(state["content"])
                else:
                    raw_text = state["content"].decode("utf-8", errors="ignore")
                deterministic = extract_invoice_from_text(raw_text, document_type)
                structured = {
                    "rows": [
                        self._normalized_from_legacy(
                            deterministic,
                            document_id=document["id"],
                            document_type=document_type,
                            tax_period=tax_period,
                        ).model_dump(mode="json")
                    ]
                }
                provider, model_name, task_type, fallback_reason = (
                    "deterministic",
                    "pymupdf-python-docx-tesseract",
                    "text_parse",
                    None,
                )
                if self.settings.ai_mode == "live":
                    route = choose_extraction_route(
                        document_type,
                        extension,
                        has_clean_text=bool(raw_text.strip()),
                        vision_capable=bool(self.settings.nvidia_vision_model),
                    )
                    if document_type in {"credit_debit_notes", "gst_special_transactions"}:
                        route = "groq"
                    prompt = (
                        f"Document type: {document_type}. Source document id: {document['id']}. "
                        f"Tax period: {tax_period or 'unknown'}.\n\n"
                        f"Visible content:\n{raw_text[:18000]}"
                    )
                    if route == "nvidia":
                        try:
                            structured = await complete_nvidia_json(
                                self.settings,
                                system_prompt=NORMALIZED_GST_EXTRACTION_SYSTEM_PROMPT,
                                user_prompt=prompt,
                                content=(
                                    state["content"]
                                    if extension in {".png", ".jpg", ".jpeg"}
                                    and self.settings.nvidia_vision_model
                                    else None
                                ),
                                mime_type=(
                                    document.get("mime_type")
                                    if extension in {".png", ".jpg", ".jpeg"}
                                    and self.settings.nvidia_vision_model
                                    else None
                                ),
                            )
                            self._normalize_rows(
                                structured.get("rows", []),
                                document_id=document["id"],
                                document_type=document_type,
                            )
                            provider, model_name, task_type = (
                                "nvidia",
                                (
                                    self.settings.nvidia_vision_model
                                    if extension in {".png", ".jpg", ".jpeg"}
                                    and self.settings.nvidia_vision_model
                                    else self.settings.nvidia_small_model
                                ),
                                (
                                    "vision_structured_extraction"
                                    if extension in {".png", ".jpg", ".jpeg"}
                                    and self.settings.nvidia_vision_model
                                    else "routine_structured_extraction"
                                ),
                            )
                        except Exception as exc:
                            fallback_reason = type(exc).__name__
                            structured = await complete_groq_json(
                                self.settings,
                                system_prompt=NORMALIZED_GST_EXTRACTION_SYSTEM_PROMPT,
                                user_prompt=prompt,
                            )
                            provider, model_name, task_type = (
                                "groq",
                                self.settings.effective_groq_model,
                                "complex_structured_extraction",
                            )
                    elif route == "groq":
                        structured = await complete_groq_json(
                            self.settings,
                            system_prompt=NORMALIZED_GST_EXTRACTION_SYSTEM_PROMPT,
                            user_prompt=prompt,
                        )
                        provider, model_name, task_type = (
                            "groq",
                            self.settings.effective_groq_model,
                            "complex_structured_extraction",
                        )

        raw_rows = structured.get("rows", [])
        if not raw_rows and structured.get("invoice_number"):
            application = await self.store.get_row("applications", document["application_id"])
            raw_rows = [
                self._normalized_from_legacy(
                    structured,
                    document_id=document["id"],
                    document_type=document_type,
                    tax_period=(application or {}).get("period_label"),
                ).model_dump(mode="json")
            ]
            structured = {"rows": raw_rows, "summary": {"record_count": 1}}
        normalized_rows = self._normalize_rows(
            raw_rows,
            document_id=document["id"],
            document_type=document_type,
        )
        structured["rows"] = normalized_rows
        completed = datetime.now(UTC)
        return {
            "raw_text": raw_text,
            "structured_data": structured,
            "invoice_rows": normalized_rows,
            "provider": provider,
            "model_name": model_name,
            "task_type": task_type,
            "fallback_reason": fallback_reason,
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "duration_ms": int((time.perf_counter() - started_clock) * 1000),
            "status": "extracted",
        }

    @staticmethod
    def _normalize_rows(
        raw_rows: list[dict[str, Any]], *, document_id: str, document_type: str
    ) -> list[dict[str, Any]]:
        return [
            NormalizedGSTRecord.model_validate(
                {
                    **source,
                    "document_type": source.get("document_type") or document_type,
                    "source_document_id": document_id,
                }
            ).model_dump(mode="json")
            for source in raw_rows
        ]

    @staticmethod
    def _normalized_from_legacy(
        source: dict[str, Any],
        *,
        document_id: str,
        document_type: str,
        tax_period: str | None,
    ) -> NormalizedGSTRecord:
        taxes = [Decimal(str(source.get(name) or 0)) for name in ("igst", "cgst", "sgst", "cess")]
        return NormalizedGSTRecord(
            tax_period=tax_period,
            document_type=document_type,
            document_number=source.get("invoice_number"),
            document_date=source.get("invoice_date"),
            supplier_name=source.get("supplier_name"),
            supplier_gstin=source.get("supplier_gstin"),
            customer_name=source.get("customer_name"),
            customer_gstin=source.get("customer_gstin"),
            place_of_supply=source.get("place_of_supply"),
            hsn_sac=source.get("hsn_sac"),
            taxable_value=source.get("taxable_value"),
            igst=source.get("igst"),
            cgst=source.get("cgst"),
            sgst_utgst=source.get("sgst"),
            cess=source.get("cess"),
            total_tax=sum(taxes, Decimal("0")),
            total_document_value=source.get("invoice_total"),
            source_document_id=document_id,
        )

    async def persist_extraction(self, state: DocumentState) -> dict[str, Any]:
        document = state["document"]
        structured = state["structured_data"]
        existing = await self.store.list_rows(
            "document_extractions", {"document_id": document["id"]}, limit=1
        )
        extraction_data = {
            "document_id": document["id"],
            "document_type": state["document_type"],
            "raw_text": state.get("raw_text", ""),
            "structured_data": structured,
            "original_structured_data": structured,
            "field_confidences": structured.get("field_confidences", {}),
            "overall_confidence": structured.get(
                "overall_confidence", 0.95 if structured.get("rows") else 0.0
            ),
            "provider": state.get("provider", "deterministic"),
            "model_name": state.get("model_name", "deterministic-parser"),
            "task_type": state.get("task_type", "structured_parse"),
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
            "duration_ms": state.get("duration_ms"),
            "fallback_reason": state.get("fallback_reason"),
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
            "sales_invoices": "sales",
            "purchase_expense_invoices": "purchase",
            "credit_debit_notes": "purchase",
            "gst_special_transactions": "purchase",
            "gstr2b": "gstr2b",
        }.get(state["document_type"], "supporting")
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
                "tax_period": source.get("tax_period"),
                "document_type": source.get("document_type") or state["document_type"],
                "invoice_number": source.get("document_number"),
                "invoice_number_normalized": normalize_invoice_number(
                    source.get("document_number")
                ),
                "invoice_date": source.get("document_date"),
                "place_of_supply": source.get("place_of_supply"),
                "taxable_value": source.get("taxable_value"),
                "gst_rate": source.get("gst_rate"),
                "cgst": source.get("cgst"),
                "sgst": source.get("sgst_utgst"),
                "igst": source.get("igst"),
                "cess": source.get("cess"),
                "total_tax": source.get("total_tax"),
                "invoice_total": source.get("total_document_value"),
                "transaction_type": source.get("transaction_type"),
                "itc_status": source.get("itc_status"),
                "rcm_flag": source.get("rcm_flag"),
                "original_document_reference": source.get("original_document_reference"),
                "source_page": source.get("source_page"),
                "source_row": source.get("source_row"),
                "source_data": source,
                "hsn_sac": source.get("hsn_sac"),
                "line_items": [],
                "source_type": state["document_type"],
                "review_status": "pending",
            }
            inserted.append(await self.store.insert_row("invoice_records", record))
        return {"invoice_rows": inserted, "status": "persisted"}

    async def replace_reviewed_records(
        self,
        document: dict[str, Any],
        structured_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate and synchronize CA-corrected rows without changing original extraction data."""

        document_type = document.get("document_type") or "unknown"
        normalized_rows = [
            NormalizedGSTRecord.model_validate(
                {
                    **source,
                    "document_type": source.get("document_type") or document_type,
                    "source_document_id": document["id"],
                }
            ).model_dump(mode="json")
            for source in structured_data.get("rows", [])
        ]
        old_records = await self.store.list_rows("invoice_records", {"document_id": document["id"]})
        for old in old_records:
            await self.store.delete_row("invoice_records", old["id"])

        category = {
            "sales_register": "sales",
            "purchase_register": "purchase",
            "sales_invoices": "sales",
            "purchase_expense_invoices": "purchase",
            "credit_debit_notes": "purchase",
            "gst_special_transactions": "purchase",
            "gstr2b": "gstr2b",
        }.get(document_type, "supporting")
        inserted: list[dict[str, Any]] = []
        for source in normalized_rows:
            inserted.append(
                await self.store.insert_row(
                    "invoice_records",
                    {
                        "firm_id": document["firm_id"],
                        "client_id": document["client_id"],
                        "application_id": document["application_id"],
                        "document_id": document["id"],
                        "invoice_category": source.get("invoice_category") or category,
                        "supplier_name": source.get("supplier_name"),
                        "supplier_gstin": source.get("supplier_gstin"),
                        "customer_name": source.get("customer_name"),
                        "customer_gstin": source.get("customer_gstin"),
                        "tax_period": source.get("tax_period"),
                        "document_type": source.get("document_type") or document_type,
                        "invoice_number": source.get("document_number"),
                        "invoice_number_normalized": normalize_invoice_number(
                            source.get("document_number")
                        ),
                        "invoice_date": source.get("document_date"),
                        "place_of_supply": source.get("place_of_supply"),
                        "taxable_value": source.get("taxable_value"),
                        "gst_rate": source.get("gst_rate"),
                        "cgst": source.get("cgst"),
                        "sgst": source.get("sgst_utgst"),
                        "igst": source.get("igst"),
                        "cess": source.get("cess"),
                        "total_tax": source.get("total_tax"),
                        "invoice_total": source.get("total_document_value"),
                        "transaction_type": source.get("transaction_type"),
                        "itc_status": source.get("itc_status"),
                        "rcm_flag": source.get("rcm_flag"),
                        "original_document_reference": source.get("original_document_reference"),
                        "source_page": source.get("source_page"),
                        "source_row": source.get("source_row"),
                        "source_data": source,
                        "hsn_sac": source.get("hsn_sac"),
                        "line_items": [],
                        "source_type": document_type,
                        "review_status": "edited_and_approved",
                    },
                )
            )
        return inserted

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

        old_findings = await self.store.list_rows(
            "validation_findings", {"document_id": document["id"]}
        )
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
                expected_customer_gstin=client.get("gstin")
                if row.get("invoice_category") == "sales"
                else None,
            ):
                findings.append(
                    await self.store.insert_row(
                        "validation_findings",
                        {
                            "firm_id": document["firm_id"],
                            "application_id": document["application_id"],
                            "document_id": document["id"],
                            "invoice_record_id": row.get("id"),
                            "finding_type": finding.finding_type,
                            "severity": finding.severity,
                            "message": finding.message,
                            "details": finding.details,
                            "status": "open",
                        },
                    )
                )

        all_records = await self.store.list_rows(
            "invoice_records", {"application_id": document["application_id"]}
        )
        all_inputs = [self._invoice_input(row) for row in all_records]
        for group in detect_duplicate_groups(all_inputs):
            record_ids = [item.metadata.get("record_id") for item in group]
            if not any(row.get("id") in record_ids for row in state.get("invoice_rows", [])):
                continue
            findings.append(
                await self.store.insert_row(
                    "validation_findings",
                    {
                        "firm_id": document["firm_id"],
                        "application_id": document["application_id"],
                        "document_id": document["id"],
                        "finding_type": "duplicate_invoice",
                        "severity": "medium",
                        "message": "A possible duplicate invoice was detected.",
                        "details": {"invoice_record_ids": record_ids},
                        "status": "open",
                    },
                )
            )

        processing_status = "needs_review" if findings else "ready_for_review"
        await self.store.update_row(
            "documents", document["id"], {"processing_status": processing_status}
        )
        if state["document_type"] != "gstr2b":
            await self.store.update_row(
                "applications", document["application_id"], {"status": "extraction_review"}
            )
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
    safe_name = "".join(
        character if character.isalnum() or character in ".-_" else "_"
        for character in Path(filename).name
    )
    path = f"{application['firm_id']}/{client['id']}/{application['id']}/{digest[:12]}-{safe_name}"
    await store.upload_file(settings.supabase_documents_bucket, path, content, mime_type)
    document = await store.insert_row(
        "documents",
        {
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
        },
    )
    if requirement:
        await store.update_row("document_requirements", requirement["id"], {"status": "received"})
    result = await DocumentProcessor(store, settings).process(document["id"])
    return (await store.get_row("documents", document["id"])) or {**document, "workflow": result}
