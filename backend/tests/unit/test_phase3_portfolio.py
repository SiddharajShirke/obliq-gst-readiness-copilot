from decimal import Decimal

from app.services.document_processing.portfolio import build_portfolio


def _record(record_id: str, category: str, taxable: str, tax: str, **extra):
    return {
        "id": record_id,
        "document_id": f"doc-{record_id}",
        "document_type": category,
        "invoice_category": category,
        "taxable_value": taxable,
        "total_tax": tax,
        "invoice_total": str(Decimal(taxable) + Decimal(tax)),
        "review_status": extra.pop("review_status", "pending"),
        **extra,
    }


def test_category_portfolio_uses_only_selected_live_records() -> None:
    result = build_portfolio(
        [
            _record("sale-1", "sales_register", "1000.10", "180.02"),
            _record("purchase-1", "purchase_register", "900.00", "162.00"),
        ],
        "sales_register",
    )

    assert [row["id"] for row in result["records"]] == ["sale-1"]
    assert result["summary"]["record_count"] == 1
    assert result["summary"]["taxable_value"] == Decimal("1000.10")
    assert result["summary"]["total_tax"] == Decimal("180.02")


def test_combined_portfolio_does_not_duplicate_rows_and_reports_review_coverage() -> None:
    rows = [
        _record("sale-1", "sales_register", "1000", "180", review_status="approved"),
        _record("purchase-1", "purchase_register", "900", "162", rcm_flag=True),
    ]

    result = build_portfolio(rows, "combined")

    assert [row["id"] for row in result["records"]] == ["sale-1", "purchase-1"]
    assert result["summary"] == {
        "record_count": 2,
        "taxable_value": Decimal("1900"),
        "total_tax": Decimal("342"),
        "document_value": Decimal("2242"),
        "approved_count": 1,
        "needs_review_count": 1,
        "rcm_count": 1,
    }


def test_portfolio_rejects_non_business_scope() -> None:
    try:
        build_portfolio([], "developer_ground_truth")
    except ValueError as exc:
        assert "Unsupported portfolio scope" in str(exc)
    else:
        raise AssertionError("developer ground truth must never be a portfolio scope")


def test_portfolio_marks_only_pending_client_records_as_bulk_review_eligible() -> None:
    result = build_portfolio(
        [
            _record("pending-client", "sales_register", "1000", "180"),
            _record(
                "pending-transaction-type",
                "Regular",
                "950",
                "171",
                source_type="purchase_register",
            ),
            _record(
                "pending-gstr2b",
                "gstr2b",
                "900",
                "162",
                source_type="gstr2b",
            ),
            _record(
                "needs-review-client",
                "purchase_register",
                "800",
                "144",
                review_status="needs_review",
            ),
            _record(
                "approved-client",
                "purchase_register",
                "700",
                "126",
                review_status="approved",
            ),
        ],
        "combined",
    )

    eligibility = {row["id"]: row["review_eligible"] for row in result["records"]}
    assert eligibility == {
        "pending-client": True,
        "pending-transaction-type": True,
        "pending-gstr2b": False,
        "needs-review-client": False,
        "approved-client": False,
    }
