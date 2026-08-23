"""Portable PDF and CSV exporters for OBLIQ's CA working reports."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#5F6B7A")
BRAND = colors.HexColor("#315E8A")
SURFACE = colors.HexColor("#F7F9FC")
BORDER = colors.HexColor("#D7DFE8")
GROUND_TRUTH_TYPES = frozenset({"developer_ground_truth"})


def generate_export_archive(files: dict[str, bytes]) -> bytes:
    """Package deterministic report artifacts into one browser-friendly download."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return output.getvalue()


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _indian_number(value: Any) -> str:
    number = _decimal(value).quantize(Decimal("0.01"))
    sign = "-" if number < 0 else ""
    whole, fraction = f"{abs(number):.2f}".split(".")
    if len(whole) > 3:
        ending = whole[-3:]
        prefix = whole[:-3]
        groups: list[str] = []
        while prefix:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        whole = ",".join([*groups, ending])
    return f"{sign}{whole}.{fraction}"


def _money(value: Any) -> str:
    # ReportLab's built-in Helvetica font does not include the Unicode rupee
    # glyph. ``INR`` keeps exports portable without an OS-specific font.
    return f"INR {_indian_number(value)}"


def _display(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value)


def _styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ObliqTitle", parent=styles["Title"], textColor=INK, fontSize=22, leading=27
        ),
        "subtitle": ParagraphStyle(
            "ObliqSubtitle", parent=styles["Normal"], textColor=MUTED, fontSize=9, leading=13
        ),
        "section": ParagraphStyle(
            "ObliqSection", parent=styles["Heading2"], textColor=INK, fontSize=13, leading=17
        ),
        "body": ParagraphStyle(
            "ObliqBody", parent=styles["BodyText"], textColor=INK, fontSize=8.5, leading=12
        ),
        "small": ParagraphStyle(
            "ObliqSmall", parent=styles["BodyText"], textColor=MUTED, fontSize=7.2, leading=9.5
        ),
        "badge": ParagraphStyle(
            "ObliqBadge", parent=styles["BodyText"], textColor=BRAND, fontSize=7.5, leading=9
        ),
        "disclaimer": ParagraphStyle(
            "ObliqDisclaimer",
            parent=styles["BodyText"],
            textColor=MUTED,
            fontSize=7.5,
            leading=10,
            alignment=TA_CENTER,
        ),
    }


def _p(value: Any, style: ParagraphStyle) -> Paragraph:
    text = _display(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def _table(
    rows: list[list[Any]],
    widths: list[float] | None = None,
    *,
    header: bool = True,
    compact: bool = False,
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.8 if compact else 7.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _footer(canvas: Any, document: Any, text: str) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.line(18 * mm, 12 * mm, document.pagesize[0] - 18 * mm, 12 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 7.5 * mm, text)
    canvas.drawRightString(document.pagesize[0] - 18 * mm, 7.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def _generated_at(summary: dict[str, Any]) -> str:
    raw = summary.get("generated_at") or datetime.now(UTC).isoformat()
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).strftime(
            "%d-%m-%Y %H:%M UTC"
        )
    except ValueError:
        return str(raw)


def _category_label(value: Any) -> str:
    labels = {
        "sales_register": "Sales Register",
        "purchase_register": "Purchase Register",
        "sales_invoices": "Sales Invoices",
        "purchase_expense_invoices": "Purchase & Expense Invoices",
        "credit_debit_notes": "Credit & Debit Notes",
        "gst_special_transactions": "GST Special Transactions",
        "gstr2b": "GSTR-2B",
    }
    text = str(value or "unknown")
    return labels.get(text, text.replace("_", " ").title())


def _business_manifest(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("document_type") not in GROUND_TRUTH_TYPES
        and row.get("category") != "Developer Ground Truth"
    ]


def _comparison_label(
    field: str,
    difference_fields: set[str],
    books: dict[str, Any],
    gstr2b: dict[str, Any],
) -> str:
    if field in difference_fields:
        return "Different - CA review"
    if books.get(field) in (None, "") and gstr2b.get(field) in (None, ""):
        return "Not available"
    return "Exact" if books.get(field) == gstr2b.get(field) else "Not compared"


def generate_readiness_pdf(summary: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title="OBLIQ GST Readiness Preparatory Report",
        author="OBLIQ",
    )
    styles = _styles()
    client = summary.get("client") or {}
    application = summary.get("application") or {}
    firm = summary.get("firm") or {}
    documents = summary.get("documents") or {}
    validation = summary.get("validation") or {}
    readiness = summary.get("readiness") or {}
    reconciliation = summary.get("reconciliation") or {}
    manifest = _business_manifest(summary.get("document_manifest") or [])
    subtitle = (
        f"{client.get('business_name', 'Client')} · GSTIN {client.get('gstin', '—')} · "
        f"{application.get('period_label', 'GST period')}"
    )

    story: list[Any] = [
        _p("OBLIQ · GST READINESS COPILOT", styles["badge"]),
        _p("GST Readiness Preparatory Report", styles["title"]),
        _p(
            subtitle,
            styles["subtitle"],
        ),
        Spacer(1, 6),
        _table(
            [
                [
                    "Client",
                    client.get("legal_name") or client.get("business_name"),
                    "GSTIN",
                    client.get("gstin"),
                ],
                [
                    "GST period",
                    application.get("period_label"),
                    "Financial year",
                    application.get("financial_year"),
                ],
                [
                    "Filing frequency",
                    application.get("filing_frequency") or client.get("filing_frequency"),
                    "Application reference",
                    application.get("id"),
                ],
                ["CA / Firm", firm.get("name"), "Prepared", _generated_at(summary)],
            ],
            [28 * mm, 58 * mm, 31 * mm, 57 * mm],
            header=False,
        ),
        Spacer(1, 12),
        _p("Document Collection", styles["section"]),
        _table(
            [
                ["Required categories", "Received", "Pending", "Collection status"],
                [
                    documents.get("required", 0),
                    documents.get("received", 0),
                    max(int(documents.get("required", 0)) - int(documents.get("received", 0)), 0),
                    "Complete"
                    if documents.get("received") == documents.get("required")
                    else "In progress",
                ],
            ],
            [42 * mm, 42 * mm, 42 * mm, 48 * mm],
        ),
    ]
    requirements = documents.get("requirements") or []
    if requirements:
        story.extend(
            [
                Spacer(1, 6),
                _table(
                    [["Category", "Status"]]
                    + [
                        [
                            _category_label(row.get("type") or row.get("requirement_type")),
                            _display(row.get("status")),
                        ]
                        for row in requirements
                    ],
                    [120 * mm, 54 * mm],
                ),
            ]
        )

    story.extend([Spacer(1, 12), _p("File Manifest / Document References", styles["section"])])
    if manifest:
        manifest_rows = [
            ["Document", "Category", "Uploaded", "Source", "Status", "OBLIQ reference"]
        ]
        for row in manifest:
            manifest_rows.append(
                [
                    row.get("original_name"),
                    row.get("category") or _category_label(row.get("document_type")),
                    str(row.get("uploaded_at") or row.get("created_at") or "")[:10],
                    row.get("source"),
                    row.get("status") or row.get("processing_status"),
                    row.get("document_id") or row.get("id"),
                ]
            )
        story.append(
            _table(
                manifest_rows, [40 * mm, 31 * mm, 19 * mm, 20 * mm, 21 * mm, 43 * mm], compact=True
            )
        )
        story.append(
            _p(
                "Document references require authenticated OBLIQ access; no permanent public "
                "Storage URL is embedded.",
                styles["small"],
            )
        )
    else:
        story.append(_p("No business-document manifest entries are available.", styles["body"]))

    story.extend([Spacer(1, 12), _p("Extracted and Normalized GST Data", styles["section"])])
    for title, values in (
        ("Sales", summary.get("sales") or {}),
        ("Purchases", summary.get("purchases") or {}),
    ):
        story.extend(
            [
                KeepTogether(
                    [
                        _p(title, styles["body"]),
                        _table(
                            [
                                [
                                    "Records",
                                    "Taxable value",
                                    "IGST",
                                    "CGST",
                                    "SGST/UTGST",
                                    "Cess",
                                    "Document total",
                                ],
                                [
                                    values.get("invoice_count", 0),
                                    _money(values.get("taxable_value")),
                                    _money(values.get("igst")),
                                    _money(values.get("cgst")),
                                    _money(values.get("sgst")),
                                    _money(values.get("cess")),
                                    _money(values.get("invoice_total")),
                                ],
                            ],
                            [17 * mm, 29 * mm, 25 * mm, 25 * mm, 28 * mm, 22 * mm, 28 * mm],
                            compact=True,
                        ),
                    ]
                ),
                Spacer(1, 6),
            ]
        )
    category_summaries = summary.get("category_summaries") or {}
    if category_summaries:
        story.append(
            _table(
                [
                    [
                        "Client category",
                        "Records",
                        "Taxable value",
                        "IGST",
                        "CGST",
                        "SGST/UTGST",
                        "Cess",
                        "Document total",
                    ]
                ]
                + [
                    [
                        _category_label(category),
                        values.get("invoice_count", 0),
                        _money(values.get("taxable_value")),
                        _money(values.get("igst")),
                        _money(values.get("cgst")),
                        _money(values.get("sgst")),
                        _money(values.get("cess")),
                        _money(values.get("invoice_total")),
                    ]
                    for category, values in category_summaries.items()
                ],
                [34 * mm, 15 * mm, 25 * mm, 20 * mm, 20 * mm, 24 * mm, 16 * mm, 26 * mm],
                compact=True,
            )
        )

    story.extend(
        [
            Spacer(1, 6),
            _p("Validation Summary", styles["section"]),
            _table(
                [
                    ["Findings", "Reviewed", "Resolved", "Remaining notes", "Completion"],
                    [
                        validation.get("finding_count", 0),
                        validation.get("reviewed_count", 0),
                        validation.get("resolved_count", 0),
                        validation.get("open_count", 0),
                        f"{validation.get('progress_percent', 0)}%",
                    ],
                ],
                [35 * mm, 35 * mm, 35 * mm, 35 * mm, 34 * mm],
            ),
        ]
    )
    finding_rows = validation.get("findings") or []
    if finding_rows:
        story.append(
            _table(
                [["Finding", "Document / Invoice", "Status", "CA review", "Resolution / comment"]]
                + [
                    [
                        row.get("message") or row.get("finding_type"),
                        row.get("invoice_number")
                        or row.get("document_name")
                        or row.get("invoice_record_id"),
                        row.get("status"),
                        row.get("resolved_by")
                        or ("Reviewed" if row.get("status") != "open" else "Pending"),
                        row.get("resolution") or row.get("comment") or "—",
                    ]
                    for row in finding_rows[:100]
                ],
                [50 * mm, 36 * mm, 22 * mm, 27 * mm, 39 * mm],
                compact=True,
            )
        )

    recon_status = str(reconciliation.get("status") or "not_started")
    recon_label = (
        "Not performed / Separate optional review"
        if recon_status == "not_started"
        else (
            f"{recon_status.replace('_', ' ').title()} · "
            f"{reconciliation.get('review_percent', 0)}% reviewed"
        )
    )
    extraction_percent = (
        (summary.get("workflow") or {})
        .get("extraction", {})
        .get(
            "progress_percent",
            100 if documents.get("reviewed") == documents.get("received") else 0,
        )
    )
    story.extend(
        [
            Spacer(1, 12),
            _p("GSTR-2B Reconciliation", styles["section"]),
            _p(recon_label, styles["body"]),
        ]
    )
    recon_summary = reconciliation.get("summary") or {}
    if recon_summary:
        story.append(
            _table(
                [
                    [
                        "Exact matches",
                        "Value mismatches",
                        "Invoice no. mismatches",
                        "Books only",
                        "GSTR-2B only",
                    ],
                    [
                        recon_summary.get("exact_match", 0),
                        recon_summary.get("value_mismatch", 0),
                        recon_summary.get("invoice_number_mismatch", 0),
                        recon_summary.get("books_only", 0),
                        recon_summary.get("gstr2b_only", 0),
                    ],
                ],
                [35 * mm, 35 * mm, 35 * mm, 34 * mm, 35 * mm],
            )
        )

    alerts = summary.get("alerts") or []
    story.extend([Spacer(1, 12), _p("CA-Raised Alerts", styles["section"])])
    if alerts:
        story.append(
            _table(
                [
                    [
                        "Alert type",
                        "Invoice / document",
                        "Status",
                        "Exact evidence / AI assistance",
                        "CA notes",
                    ]
                ]
                + [
                    [
                        row.get("alert_type") or row.get("alert_category"),
                        row.get("invoice_number")
                        or row.get("reconciliation_item_id")
                        or row.get("validation_finding_id"),
                        row.get("status"),
                        (row.get("ai_explanation") or {}).get("short_summary")
                        or row.get("message"),
                        row.get("ca_notes") or "—",
                    ]
                    for row in alerts[:100]
                ],
                [31 * mm, 35 * mm, 20 * mm, 58 * mm, 30 * mm],
                compact=True,
            )
        )
    else:
        story.append(_p("No formal alerts have been raised by the CA.", styles["body"]))

    story.extend(
        [
            Spacer(1, 12),
            _p("GST Preparation Summary", styles["section"]),
            _table(
                [
                    [
                        "Document Collection",
                        "Extraction Review",
                        "Validation Review",
                        "Ready for Filing",
                        "GSTR-2B Reconciliation",
                        "Open CA Alerts",
                    ],
                    [
                        "Complete"
                        if documents.get("received") == documents.get("required")
                        else "In progress",
                        f"{extraction_percent}%",
                        f"{validation.get('progress_percent', 0)}%",
                        "Yes" if readiness.get("ready_for_filing") else "No",
                        recon_status.replace("_", " ").title(),
                        sum(1 for row in alerts if row.get("status") == "open"),
                    ],
                ],
                [29 * mm, 29 * mm, 29 * mm, 29 * mm, 35 * mm, 23 * mm],
                compact=True,
            ),
            Spacer(1, 14),
            _p(
                "GST preparation report generated by OBLIQ for CA review. This report is a "
                "preparatory working document and is not a filed GST return. Final filing and "
                "professional GST decisions remain subject to CA verification.",
                styles["disclaimer"],
            ),
        ]
    )
    footer = "OBLIQ · GST preparation working · Not an official GST Portal document"
    document.build(
        story,
        onFirstPage=lambda canvas, doc: _footer(canvas, doc, footer),
        onLaterPages=lambda canvas, doc: _footer(canvas, doc, footer),
    )
    return output.getvalue()


def generate_reconciliation_pdf(summary: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=18 * mm,
        title="OBLIQ GSTR-2B Reconciliation Working Report",
        author="OBLIQ",
    )
    styles = _styles()
    client = summary.get("client") or {}
    application = summary.get("application") or {}
    firm = summary.get("firm") or {}
    reconciliation = summary.get("reconciliation") or {}
    counts = reconciliation.get("summary") or {}
    subtitle = (
        f"{client.get('business_name', 'Client')} · GSTIN {client.get('gstin', '—')} · "
        f"{application.get('period_label', 'GST period')} · "
        f"{application.get('financial_year', '—')}"
    )
    story: list[Any] = [
        _p("OBLIQ · GST READINESS COPILOT", styles["badge"]),
        _p("GSTR-2B Reconciliation Working Report", styles["title"]),
        _p(
            subtitle,
            styles["subtitle"],
        ),
        _p(
            f"CA / Firm: {firm.get('name', '—')} · Generated: {_generated_at(summary)}",
            styles["subtitle"],
        ),
        Spacer(1, 10),
        _table(
            [
                [
                    "Books records",
                    "GSTR-2B records",
                    "Exact matches",
                    "Value mismatch",
                    "Invoice no. mismatch",
                    "Books only",
                    "GSTR-2B only",
                    "ITC unavailable",
                    "RCM",
                    "Reviewed",
                ],
                [
                    counts.get("books_records", counts.get("books_count", 0)),
                    counts.get("gstr2b_records", counts.get("gstr2b_count", 0)),
                    counts.get("exact_match", 0),
                    counts.get("value_mismatch", 0),
                    counts.get("invoice_number_mismatch", 0),
                    counts.get("books_only", 0),
                    counts.get("gstr2b_only", 0),
                    counts.get("itc_not_available", 0),
                    counts.get("rcm", 0),
                    f"{reconciliation.get('review_percent', 0)}%",
                ],
            ],
            [24 * mm] * 10,
            compact=True,
        ),
        Spacer(1, 12),
        _p("Detailed Books vs GSTR-2B Comparison", styles["section"]),
    ]
    alerts_by_item = {
        str(row.get("reconciliation_item_id")): row for row in summary.get("alerts") or []
    }
    reconciliation_items = summary.get("reconciliation_items") or []
    if not reconciliation_items:
        story.append(_p("No reconciliation comparison records are available.", styles["body"]))

    for index, item in enumerate(reconciliation_items, start=1):
        evidence = item.get("evidence") or {}
        books = evidence.get("books") or {}
        two_b = evidence.get("gstr2b") or {}
        difference_fields = set(evidence.get("difference_fields") or [])

        comparison_rows: list[list[Any]] = [
            ["Field", "Books", "GSTR-2B", "Comparison"],
            [
                "Supplier GSTIN",
                _p(books.get("supplier_gstin"), styles["small"]),
                _p(two_b.get("supplier_gstin"), styles["small"]),
                _comparison_label("supplier_gstin", difference_fields, books, two_b),
            ],
            [
                "Invoice / document number",
                _p(books.get("invoice_number"), styles["small"]),
                _p(two_b.get("invoice_number"), styles["small"]),
                _comparison_label("invoice_number", difference_fields, books, two_b),
            ],
            [
                "Invoice date",
                _display(books.get("invoice_date")),
                _display(two_b.get("invoice_date")),
                _comparison_label("invoice_date", difference_fields, books, two_b),
            ],
        ]
        for field, label in (
            ("taxable_value", "Taxable value"),
            ("igst", "IGST"),
            ("cgst", "CGST"),
            ("sgst", "SGST / UTGST"),
            ("cess", "Cess"),
            ("total_tax", "Total tax"),
            ("total_document_value", "Total document value"),
        ):
            comparison_rows.append(
                [
                    label,
                    _money(books.get(field)),
                    _money(two_b.get(field)),
                    _comparison_label(field, difference_fields, books, two_b),
                ]
            )

        classification = str(item.get("match_status") or "needs_review").replace("_", " ").title()
        review = str(item.get("review_status") or "pending").replace("_", " ").title()
        alert = "Yes" if str(item.get("id")) in alerts_by_item else "No"
        story.append(
            KeepTogether(
                [
                    _p(
                        f"{index}. {classification} | Review: {review} | Alert raised: {alert}",
                        styles["body"],
                    ),
                    _table(
                        comparison_rows,
                        [48 * mm, 58 * mm, 58 * mm, 76 * mm],
                        compact=True,
                    ),
                    _p(
                        "Difference fields: " + (", ".join(sorted(difference_fields)) or "None"),
                        styles["small"],
                    ),
                    Spacer(1, 8),
                ]
            )
        )
    alert_rows = summary.get("alerts") or []
    if alert_rows:
        story.extend(
            [
                PageBreak(),
                _p("Raised Alerts and Assistance", styles["section"]),
                _table(
                    [["Alert type", "Reconciliation item", "Status", "AI explanation", "CA notes"]]
                    + [
                        [
                            row.get("alert_type"),
                            row.get("reconciliation_item_id"),
                            row.get("status"),
                            (row.get("ai_explanation") or {}).get("short_summary")
                            or "AI explanation unavailable",
                            row.get("ca_notes") or "—",
                        ]
                        for row in alert_rows
                    ],
                    [38 * mm, 50 * mm, 23 * mm, 105 * mm, 50 * mm],
                ),
            ]
        )
    story.extend(
        [
            Spacer(1, 14),
            _p(
                "Reconciliation working generated by OBLIQ for CA review. Final ITC treatment "
                "and GST filing decisions remain subject to CA verification.",
                styles["disclaimer"],
            ),
        ]
    )
    footer = "OBLIQ · GSTR-2B reconciliation working · Not an official GST Portal document"
    document.build(
        story,
        onFirstPage=lambda canvas, doc: _footer(canvas, doc, footer),
        onLaterPages=lambda canvas, doc: _footer(canvas, doc, footer),
    )
    return output.getvalue()


def _csv_bytes(rows: Iterable[dict[str, Any]], fields: list[str]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def generate_document_manifest_csv(rows: list[dict[str, Any]]) -> bytes:
    return _csv_bytes(
        _business_manifest(rows),
        ["document_id", "category", "original_name", "uploaded_at", "source", "status"],
    )


def generate_invoice_csv(rows: list[dict[str, Any]]) -> bytes:
    business_rows = [
        row
        for row in rows
        if row.get("source_type") not in {"developer_ground_truth", "gstr2b"}
        and row.get("document_type") not in GROUND_TRUTH_TYPES
    ]
    return _csv_bytes(
        business_rows,
        [
            "document_type",
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
            "sgst_utgst",
            "igst",
            "cess",
            "total_tax",
            "invoice_total",
            "total_document_value",
            "transaction_type",
            "itc_status",
            "rcm_flag",
            "review_status",
            "document_id",
            "source_page",
            "source_row",
        ],
    )


def generate_validation_csv(rows: list[dict[str, Any]]) -> bytes:
    return _csv_bytes(
        rows,
        [
            "finding_type",
            "message",
            "invoice_number",
            "document_name",
            "severity",
            "status",
            "resolution",
            "comment",
            "validation_finding_id",
            "invoice_record_id",
            "document_id",
        ],
    )


def generate_reconciliation_csv(rows: list[dict[str, Any]]) -> bytes:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        evidence = row.get("evidence") or {}
        books = evidence.get("books") or {}
        two_b = evidence.get("gstr2b") or {}
        item: dict[str, Any] = {
            "reconciliation_item_id": row.get("id"),
            "match_status": row.get("match_status"),
            "review_status": row.get("review_status"),
            "supplier_gstin": books.get("supplier_gstin") or two_b.get("supplier_gstin"),
            "books_invoice_number": books.get("invoice_number"),
            "gstr2b_invoice_number": two_b.get("invoice_number"),
            "invoice_date": books.get("invoice_date") or two_b.get("invoice_date"),
            "difference_fields": ",".join(evidence.get("difference_fields") or []),
            "special_flags": ",".join(row.get("special_flags") or []),
        }
        for key in (
            "taxable_value",
            "igst",
            "cgst",
            "sgst",
            "cess",
            "total_tax",
            "total_document_value",
        ):
            item[f"books_{key}"] = books.get(key)
            item[f"gstr2b_{key}"] = two_b.get(key)
        flattened.append(item)
    return _csv_bytes(
        flattened,
        [
            "reconciliation_item_id",
            "match_status",
            "review_status",
            "supplier_gstin",
            "books_invoice_number",
            "gstr2b_invoice_number",
            "invoice_date",
            "books_taxable_value",
            "gstr2b_taxable_value",
            "books_igst",
            "gstr2b_igst",
            "books_cgst",
            "gstr2b_cgst",
            "books_sgst",
            "gstr2b_sgst",
            "books_cess",
            "gstr2b_cess",
            "books_total_tax",
            "gstr2b_total_tax",
            "books_total_document_value",
            "gstr2b_total_document_value",
            "difference_fields",
            "special_flags",
        ],
    )
