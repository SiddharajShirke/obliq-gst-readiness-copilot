from app.config import Settings
from app.repositories.memory import DEMO_ADMIN_ID, DEMO_FIRM_ID, MemoryStore
from app.services.validation_corrections import create_correction_proposal

APP_ID = "30000000-0000-0000-0000-000000000001"
CLIENT_ID = "20000000-0000-0000-0000-000000000001"


async def test_ai_no_change_proposal_explains_the_selected_wrong_period_evidence(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        ai_mode="mock",
        local_upload_dir=tmp_path / "uploads",
        local_export_dir=tmp_path / "exports",
        _env_file=None,
    )
    store = MemoryStore(settings)
    application = await store.get_row("applications", APP_ID)
    document = await store.insert_row(
        "documents",
        {
            "id": "wrong-period-document",
            "firm_id": DEMO_FIRM_ID,
            "client_id": CLIENT_ID,
            "application_id": APP_ID,
            "document_type": "purchase_expense_invoices",
            "original_name": "04_Purchase_and_Expense_Invoices.pdf",
        },
    )
    record = await store.insert_row(
        "invoice_records",
        {
            "id": "wrong-period-record",
            "firm_id": DEMO_FIRM_ID,
            "client_id": CLIENT_ID,
            "application_id": APP_ID,
            "document_id": document["id"],
            "document_type": "purchase_expense_invoices",
            "invoice_number": "PEI/0826/014",
            "invoice_date": "2026-08-02",
            "review_status": "approved",
        },
    )
    finding = await store.insert_row(
        "validation_findings",
        {
            "id": "wrong-period-finding",
            "firm_id": DEMO_FIRM_ID,
            "application_id": APP_ID,
            "document_id": document["id"],
            "invoice_record_id": record["id"],
            "finding_type": "wrong_period",
            "message": "Invoice does not belong to the selected GST period.",
            "status": "open",
            "details": {
                "invoice_date": "2026-08-02",
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
            },
        },
    )

    proposal = await create_correction_proposal(
        store,
        settings,
        application=application,
        user_id=DEMO_ADMIN_ID,
        record_ids=[record["id"]],
        finding_ids=[finding["id"]],
        mode="ai",
        manual_changes={},
        rationale=None,
    )

    assert proposal["changes"] == []
    assert "2026-08-02" in proposal["rationale"]
    assert "2026-04-01" in proposal["rationale"]
    assert "2026-04-30" in proposal["rationale"]
    assert "verify" in proposal["rationale"].lower()
