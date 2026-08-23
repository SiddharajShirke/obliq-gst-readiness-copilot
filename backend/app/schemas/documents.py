from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class LineItem(BaseModel):
    description: str | None = None
    hsn_sac: str | None = None
    quantity: float | None = None
    rate: float | None = None
    taxable_value: float | None = None
    tax_rate: float | None = None


class InvoiceExtraction(BaseModel):
    document_type: str
    supplier_name: str | None = None
    supplier_gstin: str | None = None
    customer_name: str | None = None
    customer_gstin: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    place_of_supply: str | None = None
    taxable_value: float = 0
    cgst: float = 0
    sgst: float = 0
    igst: float = 0
    cess: float = 0
    invoice_total: float = 0
    hsn_sac: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class NormalizedGSTRecord(BaseModel):
    gstin: str | None = None
    tax_period: str | None = None
    document_type: str
    document_number: str | None = None
    document_date: date | None = None
    supplier_name: str | None = None
    supplier_gstin: str | None = None
    customer_name: str | None = None
    customer_gstin: str | None = None
    place_of_supply: str | None = None
    hsn_sac: str | None = None
    taxable_value: Decimal | None = None
    gst_rate: Decimal | None = None
    igst: Decimal | None = None
    cgst: Decimal | None = None
    sgst_utgst: Decimal | None = None
    cess: Decimal | None = None
    total_tax: Decimal | None = None
    total_document_value: Decimal | None = None
    transaction_type: str | None = None
    itc_status: str | None = None
    rcm_flag: bool | None = None
    original_document_reference: str | None = None
    source_document_id: str
    source_page: int | None = None
    source_row: int | None = None

    @field_validator("document_date", mode="before")
    @classmethod
    def normalize_document_date(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
        for date_format in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, date_format).date()
            except ValueError:
                continue
        return value

    @field_validator("source_page", "source_row", mode="before")
    @classmethod
    def normalize_source_position(cls, value: Any) -> int | None:
        """Keep usable provenance without letting an AI label invalidate GST data."""

        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value > 0 else None
        if isinstance(value, float):
            return int(value) if value.is_integer() and value > 0 else None
        if isinstance(value, str):
            text = value.strip()
            return int(text) if text.isdigit() and int(text) > 0 else None
        return None


class ExtractionUpdate(BaseModel):
    structured_data: dict[str, Any]
    review_notes: str | None = None


class ReviewAction(BaseModel):
    notes: str | None = None


class BulkExtractionReview(BaseModel):
    record_ids: list[str] = Field(min_length=1, max_length=500)
    action: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=1000)


class DocumentReclassification(BaseModel):
    document_type: str


class FilingEvidence(BaseModel):
    filing_date: date
    arn: str = Field(min_length=4, max_length=80)
    final_notes: str | None = None
