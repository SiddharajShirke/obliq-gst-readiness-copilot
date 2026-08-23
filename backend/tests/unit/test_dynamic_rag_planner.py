from __future__ import annotations

import pytest

from app.config import Settings
from app.services.rag.query_planner import deterministic_plan, plan_question


def test_count_tax_invoices_is_a_transaction_count_plan() -> None:
    plan = deterministic_plan("What is count of tax invoices?")

    assert plan.domain == "transactions"
    assert plan.operation == "count"
    assert plan.filters[0].field == "record_kind"
    assert plan.filters[0].value == "tax_invoice"


def test_lowest_total_invoice_value_is_an_exact_minimum_plan() -> None:
    plan = deterministic_plan("Which tax invoice has the lowest total invoice value?")

    assert plan.domain == "transactions"
    assert plan.operation == "minimum"
    assert plan.metric == "invoice_total"
    assert plan.order_by == "invoice_total"
    assert plan.limit == 1


def test_bare_lowest_amount_requests_clarification() -> None:
    plan = deterministic_plan("Which tax invoice has the lowest amount?")

    assert plan.operation == "clarify"
    assert plan.clarification is not None
    assert "taxable value" in plan.clarification.lower()
    assert "total gst" in plan.clarification.lower()
    assert "total invoice value" in plan.clarification.lower()


def test_rcm_purchase_threshold_creates_decimal_filter() -> None:
    plan = deterministic_plan("Show RCM purchase records above 50000")

    assert plan.domain == "transactions"
    assert plan.operation == "list"
    assert any(row.field == "rcm_flag" and row.value is True for row in plan.filters)
    assert any(row.field == "invoice_category" and row.value == "purchase" for row in plan.filters)
    assert any(
        row.field == "invoice_total" and row.operator == "gte" and row.value == "50000"
        for row in plan.filters
    )


def test_gstr2b_only_question_routes_to_reconciliation() -> None:
    plan = deterministic_plan("Which invoices are only in GSTR-2B?")

    assert plan.domain == "reconciliation"
    assert plan.operation == "list"
    assert plan.filters[0].field == "match_status"
    assert plan.filters[0].value == "gstr2b_only"


def test_audit_approval_question_routes_to_audit_events() -> None:
    plan = deterministic_plan("Who approved the latest extraction?")

    assert plan.domain == "audit"
    assert plan.operation == "list"
    assert plan.order_by == "created_at"
    assert plan.order_direction == "desc"


def test_prohibited_delete_action_is_not_plannable() -> None:
    plan = deterministic_plan("Delete the purchase register")

    assert plan.operation == "clarify"
    assert plan.action_type is None
    assert "cannot" in (plan.clarification or "").lower()


def test_allowed_review_action_is_a_proposal_not_execution() -> None:
    plan = deterministic_plan("Mark reconciliation item abc-123 as reviewed")

    assert plan.domain == "reconciliation"
    assert plan.operation == "propose_action"
    assert plan.action_type == "mark_reconciliation_reviewed"
    assert plan.action_parameters == {"item_id": "abc-123"}


def test_other_allowed_actions_are_proposals() -> None:
    validation = deterministic_plan("Mark validation finding finding-123 as reviewed")
    alert = deterministic_plan("Raise alert for reconciliation item item-456")
    reminder = deterministic_plan("Draft a reminder for the missing documents")
    approve = deterministic_plan("Approve extraction for document document-789")

    assert validation.action_type == "mark_validation_reviewed"
    assert validation.action_parameters == {"finding_id": "finding-123"}
    assert alert.action_type == "raise_reconciliation_alert"
    assert alert.action_parameters == {"item_id": "item-456"}
    assert reminder.action_type == "draft_reminder"
    assert approve.action_type == "approve_extraction"
    assert approve.action_parameters == {"document_id": "document-789"}


def test_portfolio_validation_and_invoice_lookup_are_structured() -> None:
    portfolio = deterministic_plan("Summarize the Purchase Register")
    validation = deterministic_plan("Which records failed period validation?")
    invoice = deterministic_plan("What is the taxable value for EFI/0826/889?")

    assert portfolio.domain == "transactions"
    assert portfolio.operation == "summarize"
    assert any(
        row.field == "document_type" and row.value == "purchase_register"
        for row in portfolio.filters
    )
    assert validation.domain == "validation"
    assert any(row.field == "finding_type" and row.value == "period" for row in validation.filters)
    assert any(
        row.field == "invoice_number" and row.value == "efi/0826/889"
        for row in invoice.filters
    )


@pytest.mark.asyncio
async def test_ambiguous_dynamic_wording_uses_bounded_validated_planner() -> None:
    async def complete(*args, **kwargs):
        return {
            "domain": "transactions",
            "operation": "maximum",
            "metric": "invoice_total",
            "filters": [{"field": "invoice_category", "value": "purchase"}],
            "order_by": "invoice_total",
            "order_direction": "desc",
            "limit": 1,
        }

    plan = await plan_question(
        "Which supplier represents our largest purchases?",
        Settings(
            app_env="test",
            ai_mode="live",
            groq_api_key="test-key",
            nvidia_api_key="test-key",
            nvidia_small_model="test-model",
            _env_file=None,
        ),
        groq_complete=complete,
    )

    assert plan.domain == "transactions"
    assert plan.operation == "maximum"
    assert plan.metric == "invoice_total"
