from pathlib import Path

from app.api.v1.applications import REQUIREMENTS
from app.services.document_processing.taxonomy import (
    CLIENT_REQUIREMENTS,
    classify_known_filename,
)

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "202608220003_revised_phase3_document_processing.sql"
NULLABLE_AMOUNTS_MIGRATION = (
    ROOT / "supabase" / "migrations" / "202608220004_nullable_invoice_amounts.sql"
)


def test_final_client_taxonomy_has_six_categories_without_gstr2b() -> None:
    assert list(CLIENT_REQUIREMENTS) == [
        "sales_register",
        "purchase_register",
        "sales_invoices",
        "purchase_expense_invoices",
        "credit_debit_notes",
        "gst_special_transactions",
    ]
    assert "gstr2b" not in CLIENT_REQUIREMENTS
    assert "developer_ground_truth" not in CLIENT_REQUIREMENTS
    assert REQUIREMENTS == CLIENT_REQUIREMENTS


def test_synthetic_filename_routing_excludes_ground_truth_and_separates_gstr2b() -> None:
    expected = {
        "00_Set_Index_and_Ground_Truth.pdf": "developer_ground_truth",
        "01_Sales_Register.pdf": "sales_register",
        "02_Purchase_Register.pdf": "purchase_register",
        "03_Sales_Invoices.pdf": "sales_invoices",
        "04_Purchase_and_Expense_Invoices.pdf": "purchase_expense_invoices",
        "05_Credit_and_Debit_Notes.pdf": "credit_debit_notes",
        "06_GST_Special_Transactions.pdf": "gst_special_transactions",
        "07_GSTR-2B_Synthetic.pdf": "gstr2b",
    }
    assert {name: classify_known_filename(name) for name in expected} == expected


def test_phase3_migration_updates_existing_base_and_session_checklists() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for category in (*CLIENT_REQUIREMENTS, "developer_ground_truth", "gstr2b"):
        assert f"'{category}'" in sql
    assert "delete from public.document_requirements" in sql
    assert "requirement_type = 'gstr2b'" in sql
    assert "insert into public.document_requirements" in sql
    assert "cross join" in sql
    assert "processing_status = 'excluded_reference'" in sql
    assert "reconciliation_item_id" in sql
    assert "ai_explanation" in sql


def test_phase3_nullable_amounts_migration_preserves_unknown_values_as_null() -> None:
    sql = NULLABLE_AMOUNTS_MIGRATION.read_text(encoding="utf-8").lower()

    for column in ("taxable_value", "cgst", "sgst", "igst", "cess", "invoice_total"):
        assert f"alter column {column} drop not null" in sql
        assert f"alter column {column} drop default" in sql
