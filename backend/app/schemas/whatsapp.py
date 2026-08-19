from __future__ import annotations

from pydantic import BaseModel, Field


class ReminderApproval(BaseModel):
    reminder_id: str
    message: str | None = None


class DemoInboundMessage(BaseModel):
    client_id: str
    text: str = Field(min_length=1, max_length=2000)
    application_id: str | None = None


class MetaCredentialsInput(BaseModel):
    access_token: str = Field(min_length=10)
    phone_number_id: str = Field(min_length=2)
    waba_id: str = Field(min_length=2)
    app_secret: str = Field(min_length=6)
    webhook_verify_token: str = Field(min_length=6)
    graph_api_version: str = "v26.0"
    test_recipient_number: str
    document_request_template: str = "gst_document_request_v1"
    reminder_template: str = "gst_document_reminder_v1"


class WhatsAppTestRequest(BaseModel):
    recipient: str | None = None
    message: str = "OBLIQ WhatsApp integration connected successfully."
