"""Small PDF and CSV exporters for the prototype."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value: Any) -> str:
    try:
        return f"INR {float(value):,.2f}"
    except (TypeError, ValueError):
        return "INR 0.00"


def generate_readiness_pdf(summary: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="OBLIQ GST Readiness Report",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("OBLIQ GST Readiness Report", styles["Title"]),
        Spacer(1, 8),
        Paragraph(
            f"<b>{summary['client']['business_name']}</b> — GSTIN {summary['client'].get('gstin', '-')}",
            styles["Heading2"],
        ),
        Paragraph(
            f"Period: {summary['application']['period_label']} | Status: {summary['application'].get('status', '-')}",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]

    rows = [
        ["Metric", "Value"],
        ["Documents received", f"{summary['documents']['received']} / {summary['documents']['required']}"],
        ["Documents reviewed", str(summary['documents']['reviewed'])],
        ["Sales invoices", str(summary['sales']['invoice_count'])],
        ["Taxable sales", _money(summary['sales']['taxable_value'])],
        ["Output tax", _money(summary['sales']['tax_total'])],
        ["Purchase invoices", str(summary['purchases']['invoice_count'])],
        ["Taxable purchases", _money(summary['purchases']['taxable_value'])],
        ["Potential input tax", _money(summary.get('potential_input_tax', summary['purchases']['tax_total']))],
        ["Estimated liability", _money(summary['estimated_liability'])],
    ]
    table = Table(rows, colWidths=[75 * mm, 90 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#A4C5E5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#191515")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D6DCE3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F7F5")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([table, Spacer(1, 14), Paragraph("Open issues", styles["Heading2"])])
    issues = summary.get("open_issues") or []
    if issues:
        for issue in issues[:20]:
            story.append(Paragraph(f"• {issue.get('message', issue)}", styles["BodyText"]))
    else:
        story.append(Paragraph("No open validation issues are currently recorded.", styles["BodyText"]))

    story.extend(
        [
            Spacer(1, 12),
            Paragraph("GSTR-2B reconciliation", styles["Heading2"]),
            Paragraph(json.dumps(summary.get("reconciliation", {}), indent=2), styles["Code"]),
            Spacer(1, 14),
            Paragraph(summary["disclaimer"], styles["Italic"]),
        ]
    )
    document.build(story)
    return output.getvalue()


def generate_invoice_csv(rows: list[dict[str, Any]]) -> bytes:
    fields = [
        "invoice_category",
        "supplier_name",
        "supplier_gstin",
        "customer_name",
        "customer_gstin",
        "invoice_number",
        "invoice_date",
        "taxable_value",
        "cgst",
        "sgst",
        "igst",
        "cess",
        "invoice_total",
        "review_status",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def generate_reconciliation_csv(rows: list[dict[str, Any]]) -> bytes:
    fields = ["match_status", "match_score", "purchase_invoice_id", "gstr2b_invoice_id", "differences"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        item = dict(row)
        item["differences"] = json.dumps(item.get("differences") or {}, ensure_ascii=False)
        writer.writerow(item)
    return output.getvalue().encode("utf-8")
