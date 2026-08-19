from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _normalize_phone(value: str) -> str:
    cleaned = "".join(character for character in value if character.isdigit() or character == "+")
    if not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    return cleaned


class ClientCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=160)
    legal_name: str = Field(min_length=2, max_length=200)
    gstin: str = Field(min_length=15, max_length=15)
    state: str = Field(min_length=2, max_length=80)
    business_type: str = "business"
    filing_frequency: str = Field(pattern="^(monthly|quarterly)$")
    contact_name: str = Field(min_length=2, max_length=120)
    whatsapp_phone: str = Field(min_length=10, max_length=18)
    preferred_language: str = "English"
    whatsapp_consent: bool = False
    assigned_preparer_id: str | None = None
    reviewer_id: str | None = None

    @field_validator("gstin")
    @classmethod
    def normalize_gstin(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("whatsapp_phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return _normalize_phone(value)


class ClientUpdate(BaseModel):
    business_name: str | None = None
    legal_name: str | None = None
    state: str | None = None
    business_type: str | None = None
    filing_frequency: str | None = Field(default=None, pattern="^(monthly|quarterly)$")
    contact_name: str | None = None
    whatsapp_phone: str | None = None
    preferred_language: str | None = None
    whatsapp_consent: bool | None = None
    assigned_preparer_id: str | None = None
    reviewer_id: str | None = None

    @field_validator("whatsapp_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return _normalize_phone(value) if value is not None else None
