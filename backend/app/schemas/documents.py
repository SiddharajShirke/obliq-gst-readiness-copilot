from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


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


class ExtractionUpdate(BaseModel):
    structured_data: dict[str, Any]
    review_notes: str | None = None


class ReviewAction(BaseModel):
    notes: str | None = None


class FilingEvidence(BaseModel):
    filing_date: date
    arn: str = Field(min_length=4, max_length=80)
    final_notes: str | None = None
