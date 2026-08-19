#!/usr/bin/env python3
"""Generate synthetic GST files and deterministic extraction fixtures."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "demo_data" / "documents"
FIXTURES = ROOT / "demo_data" / "extractions"
FRONTEND_DOCS = ROOT / "frontend" / "public" / "demo-documents"
CLIENT_GSTIN = "27RAJTR1234A1Z5"


def rows() -> list[dict]:
    return [
        {"Invoice Number": "SD-1042", "Invoice Date": "2026-04-18", "Supplier Name": "Sharma Distributors", "Supplier GSTIN": "27ABCDE1234F1Z5", "Customer Name": "Raj Traders", "Customer GSTIN": CLIENT_GSTIN, "Taxable Value": 50000, "CGST": 4500, "SGST": 4500, "IGST": 0, "Cess": 0, "Invoice Total": 59000},
        {"Invoice Number": "JP-881", "Invoice Date": "2026-04-21", "Supplier Name": "Jupiter Papers", "Supplier GSTIN": "27JUPIT1234R1Z7", "Customer Name": "Raj Traders", "Customer GSTIN": CLIENT_GSTIN, "Taxable Value": 20000, "CGST": 1800, "SGST": 1800, "IGST": 0, "Cess": 0, "Invoice Total": 23600},
        {"Invoice Number": "TS-220", "Invoice Date": "2026-03-29", "Supplier Name": "Tech Supplies", "Supplier GSTIN": "29TECHS1234T1Z2", "Customer Name": "Raj Traders", "Customer GSTIN": CLIENT_GSTIN, "Taxable Value": 10000, "CGST": 0, "SGST": 0, "IGST": 1800, "Cess": 0, "Invoice Total": 11800},
        {"Invoice Number": "DUP-001", "Invoice Date": "2026-04-12", "Supplier Name": "Metro Wholesale", "Supplier GSTIN": "27METRO1234M1Z4", "Customer Name": "Raj Traders", "Customer GSTIN": CLIENT_GSTIN, "Taxable Value": 15000, "CGST": 1350, "SGST": 1350, "IGST": 0, "Cess": 0, "Invoice Total": 17700},
        {"Invoice Number": "DUP-001", "Invoice Date": "2026-04-12", "Supplier Name": "Metro Wholesale", "Supplier GSTIN": "27METRO1234M1Z4", "Customer Name": "Raj Traders", "Customer GSTIN": CLIENT_GSTIN, "Taxable Value": 15000, "CGST": 1350, "SGST": 1350, "IGST": 0, "Cess": 0, "Invoice Total": 17700},
    ]


def write_pdf(path: Path, data: dict, *, total_override: float | None = None) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(54, height - 60, "TAX INVOICE — SYNTHETIC DEMO")
    c.setFont("Helvetica", 10)
    fields = [
        ("Supplier", data["Supplier Name"]),
        ("Supplier GSTIN", data["Supplier GSTIN"]),
        ("Customer", data["Customer Name"]),
        ("Customer GSTIN", data["Customer GSTIN"]),
        ("Invoice Number", data["Invoice Number"]),
        ("Invoice Date", data["Invoice Date"]),
        ("Place of Supply", "Maharashtra"),
        ("Taxable Value", f"{data['Taxable Value']:.2f}"),
        ("CGST", f"{data['CGST']:.2f}"),
        ("SGST", f"{data['SGST']:.2f}"),
        ("IGST", f"{data['IGST']:.2f}"),
        ("Cess", f"{data['Cess']:.2f}"),
        ("Invoice Total", f"{(total_override if total_override is not None else data['Invoice Total']):.2f}"),
        ("HSN/SAC", "9983"),
    ]
    y = height - 105
    for label, value in fields:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(190, y, str(value))
        y -= 24
    c.setFillColorRGB(0.25, 0.25, 0.25)
    c.drawString(60, 60, "Synthetic file generated for the OBLIQ hiring prototype. Not a real tax document.")
    c.save()


def write_fixture(filename: str, data: dict, *, confidence: float = 0.94, total_override: float | None = None, document_type: str = "purchase_invoice") -> None:
    structured = {
        "document_type": document_type,
        "supplier_name": data["Supplier Name"],
        "supplier_gstin": data["Supplier GSTIN"],
        "customer_name": data["Customer Name"],
        "customer_gstin": data["Customer GSTIN"],
        "invoice_number": data["Invoice Number"],
        "invoice_date": data["Invoice Date"],
        "place_of_supply": "Maharashtra",
        "taxable_value": data["Taxable Value"],
        "cgst": data["CGST"],
        "sgst": data["SGST"],
        "igst": data["IGST"],
        "cess": data["Cess"],
        "invoice_total": total_override if total_override is not None else data["Invoice Total"],
        "hsn_sac": "9983",
        "line_items": [],
        "field_confidences": {"invoice_number": confidence, "invoice_total": confidence},
        "overall_confidence": confidence,
        "warnings": ["Low-quality scan requires review"] if confidence < 0.7 else [],
    }
    (FIXTURES / f"{filename}.json").write_text(json.dumps({"raw_text": "Synthetic invoice fixture", "structured_data": structured}, indent=2), encoding="utf-8")



def sync_frontend_demo_documents(source: Path = DOCS, target: Path = FRONTEND_DOCS) -> int:
    """Mirror generated synthetic files into the browser demo asset folder."""
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in source.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)
            copied += 1
    return copied

def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    records = rows()
    purchases = pd.DataFrame(records)
    purchases.to_excel(DOCS / "Purchase_Register_April.xlsx", index=False)
    sales = purchases.copy()
    sales["Invoice Number"] = [f"RT-{501 + index}" for index in range(len(sales))]
    sales["Supplier Name"] = "Raj Traders"
    sales["Supplier GSTIN"] = CLIENT_GSTIN
    sales["Customer Name"] = ["Walk-in Customer", "Acme Stores", "North Retail", "City Mart", "City Mart"]
    sales["Customer GSTIN"] = ["", "27ACMES1234A1Z8", "07NORTH1234N1Z3", "24CITYM1234C1Z9", "24CITYM1234C1Z9"]
    sales.to_csv(DOCS / "Sales_Register_April.csv", index=False)
    gstr2b = [dict(record) for record in records[:4]]
    gstr2b[1]["Invoice Total"] = 23550
    (DOCS / "GSTR2B_April.json").write_text(json.dumps({"records": gstr2b}, indent=2), encoding="utf-8")

    write_pdf(DOCS / "Purchase_Invoice_SD-1042.pdf", records[0])
    write_fixture("Purchase_Invoice_SD-1042.pdf", records[0])
    sales_invoice = records[0] | {"Supplier Name": "Raj Traders", "Supplier GSTIN": CLIENT_GSTIN, "Customer Name": "Acme Stores", "Customer GSTIN": "27ACMES1234A1Z8", "Invoice Number": "RT-501"}
    write_pdf(DOCS / "Sales_Invoice_RT-501.pdf", sales_invoice)
    write_fixture("Sales_Invoice_RT-501.pdf", sales_invoice, document_type="sales_invoice")
    write_pdf(DOCS / "Purchase_Invoice_Arithmetic_Mismatch.pdf", records[1], total_override=24900)
    write_fixture("Purchase_Invoice_Arithmetic_Mismatch.pdf", records[1], total_override=24900)
    write_pdf(DOCS / "Purchase_Invoice_Wrong_Period.pdf", records[2])
    write_fixture("Purchase_Invoice_Wrong_Period.pdf", records[2])
    write_pdf(DOCS / "Purchase_Invoice_Duplicate_A.pdf", records[3])
    write_fixture("Purchase_Invoice_Duplicate_A.pdf", records[3])
    write_pdf(DOCS / "Purchase_Invoice_Duplicate_B.pdf", records[4])
    write_fixture("Purchase_Invoice_Duplicate_B.pdf", records[4])

    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    text = "LOW QUALITY SYNTHETIC INVOICE\nSupplier: Mehta Office Supplies\nSupplier GSTIN: 27MEHT1234M1Z2\nCustomer: Raj Traders\nCustomer GSTIN: 27RAJTR1234A1Z5\nInvoice Number: MOS-19\nInvoice Date: 22-04-2026\nTaxable Value: 9000\nCGST: 810\nSGST: 810\nInvoice Total: 10620"
    draw.multiline_text((90, 120), text, fill="black", spacing=35, font=ImageFont.load_default())
    image = image.filter(ImageFilter.GaussianBlur(radius=1.4))
    image.save(DOCS / "Purchase_Invoice_Low_Quality.jpg", quality=52)
    low = records[0] | {"Supplier Name": "Mehta Office Supplies", "Supplier GSTIN": "27MEHTA1234M1Z2", "Invoice Number": "MOS-19", "Invoice Date": "2026-04-22", "Taxable Value": 9000, "CGST": 810, "SGST": 810, "Invoice Total": 10620}
    write_fixture("Purchase_Invoice_Low_Quality.jpg", low, confidence=0.58)

    mirrored = sync_frontend_demo_documents()
    print(f"Generated {len(list(DOCS.iterdir()))} synthetic documents in {DOCS}")
    print(f"Mirrored {mirrored} synthetic documents into {FRONTEND_DOCS}")
    print(f"Generated {len(list(FIXTURES.iterdir()))} deterministic extraction fixtures in {FIXTURES}")


if __name__ == "__main__":
    main()
