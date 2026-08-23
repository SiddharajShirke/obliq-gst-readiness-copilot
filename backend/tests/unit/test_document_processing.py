from io import BytesIO

import pandas as pd
from reportlab.pdfgen import canvas

from app.services.document_processing.classifier import classify_document
from app.services.document_processing.parsers import (
    extract_invoice_from_text,
    parse_tabular_document,
    read_pdf_text,
)
from app.services.document_processing.processor import resolve_demo_data_root


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
