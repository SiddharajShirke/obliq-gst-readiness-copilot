"""Controlled application-scoped LangGraph assistant."""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal
from typing import Any, TypedDict

from app.config import Settings
from app.prompts.rag import RAG_SYSTEM_PROMPT
from app.repositories.base import DataStore
from app.schemas.assistant_tools import QueryDomain, QueryOperation, QueryPlan, StructuredToolResult
from app.schemas.rag import AssistantModelOutput
from app.services.assistant_actions import create_action_proposal
from app.services.audit import record_audit
from app.services.llm.providers import complete_groq_json
from app.services.rag.application_context import load_structured_facts
from app.services.rag.query_planner import plan_question
from app.services.rag.retrieval import retrieve_application_documents, retrieve_knowledge
from app.services.rag.structured_tools import execute_structured_plan

logger = logging.getLogger(__name__)

EXACT_FACT_INTENTS = {
    "missing_documents",
    "draft_reminder",
    "transaction_lookup",
    "reconciliation",
    "alerts",
    "alert_explanation",
    "validation",
    "extraction_summary",
    "scope_refusal",
}


class RAGState(TypedDict, total=False):
    question: str
    application_id: str
    firm_id: str
    user_id: str
    conversation_id: str
    source_type: str | None
    intent: str
    query_plan: QueryPlan
    structured_result: StructuredToolResult
    proposed_action: dict[str, Any]
    user_role: str
    application_data: dict[str, Any]
    application_evidence: list[dict[str, Any]]
    knowledge_evidence: list[dict[str, Any]]
    history: list[dict[str, Any]]
    draft_answer: str
    confidence: float
    citations: list[dict[str, Any]]
    source_types: list[str]
    answer: dict[str, Any]


class _FallbackGraph:
    def __init__(self, assistant: RAGAssistant) -> None:
        self.assistant = assistant

    async def ainvoke(self, state: RAGState) -> RAGState:
        current = dict(state)
        for node in (
            self.assistant.validate_access,
            self.assistant.classify_question,
            self.assistant.load_structured_facts,
            self.assistant.execute_structured_tools,
            self.assistant.build_action_proposal,
            self.assistant.retrieve_application_evidence,
            self.assistant.retrieve_knowledge_if_needed,
            self.assistant.generate_grounded_answer,
            self.assistant.verify_scope_and_citations,
            self.assistant.audit,
        ):
            current.update(await node(current))
        return current


class RAGAssistant:
    _PUBLIC_ROW_FIELDS = frozenset(
        {
            "id",
            "document_id",
            "document_type",
            "invoice_category",
            "supplier_name",
            "supplier_gstin",
            "customer_name",
            "customer_gstin",
            "invoice_number",
            "invoice_date",
            "place_of_supply",
            "taxable_value",
            "gst_rate",
            "igst",
            "cgst",
            "sgst",
            "sgst_utgst",
            "cess",
            "total_tax",
            "invoice_total",
            "transaction_type",
            "itc_status",
            "rcm_flag",
            "original_document_reference",
            "source_page",
            "source_row",
            "review_status",
            "finding_type",
            "severity",
            "status",
            "match_status",
            "differences",
            "evidence",
            "special_flags",
            "alert_type",
            "title",
            "message",
            "action",
            "entity_type",
            "entity_id",
            "actor_id",
            "created_at",
        }
    )

    def __init__(self, store: DataStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self.graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return _FallbackGraph(self)
        graph = StateGraph(RAGState)
        nodes = (
            ("validate_access", self.validate_access),
            ("classify_question", self.classify_question),
            ("load_structured_facts", self.load_structured_facts),
            ("execute_structured_tools", self.execute_structured_tools),
            ("build_action_proposal", self.build_action_proposal),
            ("retrieve_application_evidence", self.retrieve_application_evidence),
            ("retrieve_knowledge_if_needed", self.retrieve_knowledge_if_needed),
            ("generate_grounded_answer", self.generate_grounded_answer),
            ("verify_scope_and_citations", self.verify_scope_and_citations),
            ("audit", self.audit),
        )
        for name, node in nodes:
            graph.add_node(name, node)
        graph.add_edge(START, nodes[0][0])
        for (left, _), (right, _) in zip(nodes, nodes[1:], strict=False):
            graph.add_edge(left, right)
        graph.add_edge(nodes[-1][0], END)
        return graph.compile()

    async def query(
        self,
        *,
        question: str,
        firm_id: str,
        application_id: str,
        user_id: str,
        conversation_id: str,
        source_type: str | None,
        role: str = "reviewer",
    ) -> dict[str, Any]:
        history = await self.store.list_rows(
            "assistant_messages",
            {
                "firm_id": firm_id,
                "application_id": application_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
            },
            order="created_at",
            desc=True,
            limit=8,
        )
        history.reverse()
        result = await self.graph.ainvoke(
            {
                "question": question,
                "firm_id": firm_id,
                "application_id": application_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "source_type": source_type,
                "user_role": role,
                "history": history,
            }
        )
        answer = result["answer"]
        application = (result.get("application_data") or {}).get("application") or {}
        demo_session_id = application.get("demo_session_id")
        await asyncio.gather(
            self._store_message(
                firm_id=firm_id,
                application_id=application_id,
                demo_session_id=demo_session_id,
                user_id=user_id,
                conversation_id=conversation_id,
                role="user",
                content=question,
            ),
            self._store_message(
                firm_id=firm_id,
                application_id=application_id,
                demo_session_id=demo_session_id,
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=answer["answer"],
                citations=answer["citations"],
                source_types=answer["source_types"],
            ),
        )
        return answer

    async def _store_message(
        self,
        *,
        firm_id: str,
        application_id: str,
        demo_session_id: str | None,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        citations: list[dict[str, Any]] | None = None,
        source_types: list[str] | None = None,
    ) -> None:
        await self.store.insert_row(
            "assistant_messages",
            {
                "firm_id": firm_id,
                "application_id": application_id,
                "demo_session_id": demo_session_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "citations": citations or [],
                "source_types": source_types or [],
            },
        )

    async def validate_access(self, state: RAGState) -> dict[str, Any]:
        application = await self.store.get_row("applications", state["application_id"])
        if not application or str(application.get("firm_id")) != str(state["firm_id"]):
            return {"application_data": {"error": "Application not found"}}
        return {"application_data": {"application": application}}

    async def classify_question(self, state: RAGState) -> dict[str, Any]:
        question = state["question"].lower()
        if any(
            phrase in question
            for phrase in (
                "another client",
                "other client",
                "different client",
                "all clients",
                "every client",
                "another application",
                "other application",
            )
        ):
            intent = "scope_refusal"
        elif any(word in question for word in ("missing", "pending", "checklist")):
            intent = "missing_documents"
        elif any(word in question for word in ("draft", "reminder", "ask the client")):
            intent = "draft_reminder"
        elif any(
            phrase in question
            for phrase in (
                "what does this response mean",
                "what does this mean",
                "explain this response",
                "explain this issue",
                "explain this result",
            )
        ):
            intent = "alert_explanation"
        elif "alert" in question or "raised" in question:
            intent = "alerts"
        elif any(
            word in question
            for word in ("gstr-2b", "gstr2b", "reconcile", "mismatch", "flagged")
        ):
            intent = "reconciliation"
        elif any(word in question for word in ("validation", "invalid", "finding")):
            intent = "validation"
        elif any(word in question for word in ("summarize", "summary", "extraction")):
            intent = "extraction_summary"
        elif any(character.isdigit() for character in question) and "/" in question:
            intent = "transaction_lookup"
        else:
            intent = "guidance"
        plan = await plan_question(state["question"], self.settings)
        dynamic_domains = {
            QueryDomain.TRANSACTIONS,
            QueryDomain.VALIDATION,
            QueryDomain.ALERTS,
            QueryDomain.AUDIT,
            QueryDomain.DOCUMENTS,
        }
        if intent != "scope_refusal" and plan.operation == QueryOperation.PROPOSE_ACTION:
            intent = "action_proposal"
        elif intent != "scope_refusal" and (
            plan.operation == QueryOperation.CLARIFY
            or plan.domain in dynamic_domains
            or (
                plan.domain == QueryDomain.RECONCILIATION
                and intent != "alert_explanation"
                and "/" not in state["question"]
            )
        ):
            intent = "dynamic_structured"
        return {"intent": intent, "query_plan": plan}

    async def load_structured_facts(self, state: RAGState) -> dict[str, Any]:
        if (state.get("application_data") or {}).get("error"):
            return {}
        data = await load_structured_facts(
            self.store,
            application_id=state["application_id"],
            question=state["question"],
            intent=state["intent"],
            application=(state.get("application_data") or {}).get("application"),
        )
        return {"application_data": data}

    async def execute_structured_tools(self, state: RAGState) -> dict[str, Any]:
        plan = state.get("query_plan")
        if (
            not plan
            or state.get("intent") != "dynamic_structured"
            or (state.get("application_data") or {}).get("error")
        ):
            return {}
        result = await execute_structured_plan(
            self.store,
            application_id=state["application_id"],
            plan=plan,
        )
        return {"structured_result": result}

    async def build_action_proposal(self, state: RAGState) -> dict[str, Any]:
        plan = state.get("query_plan")
        if (
            not plan
            or state.get("intent") != "action_proposal"
            or not plan.action_type
            or (state.get("application_data") or {}).get("error")
        ):
            return {}
        proposal = await create_action_proposal(
            self.store,
            firm_id=state["firm_id"],
            user_id=state["user_id"],
            role=state["user_role"],
            application_id=state["application_id"],
            conversation_id=state["conversation_id"],
            action_type=plan.action_type,
            payload=plan.action_parameters,
        )
        preview = proposal.get("preview") or {}
        return {
            "proposed_action": {
                "id": proposal["id"],
                "action_type": proposal["action_type"],
                "title": preview.get("title")
                or str(proposal["action_type"]).replace("_", " ").title(),
                "preview": preview,
                "affected_count": int(preview.get("affected_count") or 0),
                "warnings": ["No application data changes until you explicitly confirm."],
                "expires_at": proposal["expires_at"],
                "status": proposal["status"],
            }
        }

    async def retrieve_application_evidence(self, state: RAGState) -> dict[str, Any]:
        plan = state.get("query_plan")
        if plan and not plan.needs_text_evidence:
            return {"application_evidence": []}
        if state["intent"] in {
            "missing_documents",
            "draft_reminder",
            "alerts",
            "alert_explanation",
            "scope_refusal",
        }:
            return {"application_evidence": []}
        rows = await retrieve_application_documents(
            self.store,
            self.settings,
            question=state["question"],
            firm_id=state["firm_id"],
            application_id=state["application_id"],
        )
        return {"application_evidence": rows}

    async def retrieve_knowledge_if_needed(self, state: RAGState) -> dict[str, Any]:
        plan = state.get("query_plan")
        if plan and not plan.needs_knowledge:
            return {"knowledge_evidence": []}
        if state["intent"] not in {"guidance", "reconciliation", "validation"}:
            return {"knowledge_evidence": []}
        rows = await retrieve_knowledge(
            self.store,
            self.settings,
            question=state["question"],
            firm_id=state["firm_id"],
            source_type=state.get("source_type"),
        )
        return {"knowledge_evidence": rows}

    @staticmethod
    def _reconciliation_answer(item: dict[str, Any]) -> str:
        evidence = item.get("evidence") or {}
        books = evidence.get("books") or {}
        gstr2b = evidence.get("gstr2b") or {}
        status = item.get("match_status")
        if status == "invoice_number_mismatch":
            return (
                f"The stored Option A reconciliation pairs books invoice "
                f"{books.get('invoice_number')} with GSTR-2B invoice "
                f"{gstr2b.get('invoice_number')}. Their supplier and supporting comparison "
                "fields matched exactly, but the invoice numbers differ, so the item requires "
                "CA review."
            )
        if status == "value_mismatch":
            differences = item.get("differences") or {}
            detail = "; ".join(
                f"{field}: books {values.get('books')} vs GSTR-2B {values.get('gstr2b')}"
                for field, values in differences.items()
                if isinstance(values, dict)
            )
            identity = books.get("invoice_number") or gstr2b.get("invoice_number")
            return (
                f"The deterministic reconciliation found a value mismatch for {identity}: "
                f"{detail}. This requires CA review."
            )
        if status == "gstr2b_only":
            return f"{gstr2b.get('invoice_number')} appears only in GSTR-2B."
        if status == "books_only":
            return f"{books.get('invoice_number')} appears only in the books."
        return f"The stored reconciliation status is {str(status).replace('_', ' ')}."

    @staticmethod
    def _alert_explanation_answer(alert: dict[str, Any]) -> str:
        explanation = alert.get("ai_explanation") or {}
        evidence = alert.get("evidence") or {}
        books = evidence.get("books") or {}
        gstr2b = evidence.get("gstr2b") or {}
        invoice_number = books.get("invoice_number") or gstr2b.get("invoice_number")
        difference_fields = evidence.get("difference_fields") or []
        lines = [str(alert.get("title") or alert.get("alert_type") or "Review alert")]
        if explanation.get("what_happened"):
            lines.append(str(explanation["what_happened"]))
        elif difference_fields:
            comparisons = []
            for field in difference_fields:
                comparisons.append(
                    f"{str(field).replace('_', ' ')}: books {books.get(field)} vs "
                    f"GSTR-2B {gstr2b.get(field)}"
                )
            lines.append("OBLIQ found " + "; ".join(comparisons) + ".")
        if explanation.get("why_flagged"):
            lines.append("Why flagged: " + str(explanation["why_flagged"]))
        if explanation.get("what_ca_should_review"):
            lines.append("CA review: " + str(explanation["what_ca_should_review"]))
        elif invoice_number:
            lines.append(
                f"CA review: compare invoice {invoice_number}, the books record, and the "
                "GSTR-2B entry before deciding the GST/ITC treatment."
            )
        lines.append(
            "AI-generated explanation for review assistance. Final GST and ITC treatment "
            "remains subject to CA verification."
        )
        return "\n\n".join(lines)

    def _mock_answer(self, state: RAGState) -> tuple[str, float]:
        data = state.get("application_data") or {}
        intent = state["intent"]
        if data.get("error"):
            return "I cannot access that GST application.", 0.0
        if intent == "scope_refusal":
            return (
                "I can only answer about the currently opened GST application. "
                "Open the permitted application workspace to ask about a different client.",
                1.0,
            )
        if intent == "missing_documents":
            missing = [
                row["label"]
                for row in data["collection"]["requirements"]
                if row["status"] != "received"
            ]
            answer = (
                "The following client document categories are still missing: "
                + ", ".join(missing)
                if missing
                else "All required client document categories have been received."
            )
            return answer, 1.0
        if intent == "draft_reminder":
            return str(data.get("draft_reminder")), 1.0
        if intent == "transaction_lookup" and data.get("transactions"):
            record = data["transactions"][0]
            return (
                f"{record.get('invoice_number')} has taxable value "
                f"₹{record.get('taxable_value')}. This comes from the stored extracted record."
            ), 1.0
        if intent == "reconciliation":
            if data.get("reconciliation_item"):
                return self._reconciliation_answer(data["reconciliation_item"]), 1.0
            if "/" in state["question"]:
                return (
                    "I do not have enough stored reconciliation evidence for that invoice "
                    "in this GST application.",
                    1.0,
                )
            summary = (data.get("reconciliation") or {}).get("summary") or {}
            if summary:
                return (
                    f"The latest deterministic reconciliation summary is {summary}. "
                    "These are review findings, not final ITC decisions."
                ), 0.95
        if intent == "alerts":
            alerts = data.get("alerts") or []
            if alerts:
                answer = "The CA explicitly raised these Alerts Dashboard items: " + "; ".join(
                    f"{row['title']} ({row.get('status', 'open')})" for row in alerts
                )
                return answer, 1.0
            return "No findings have been explicitly raised as alerts.", 1.0
        if intent == "alert_explanation":
            alerts = data.get("alerts") or []
            if alerts:
                return self._alert_explanation_answer(alerts[0]), 1.0
            return (
                "I do not have a raised alert in this GST application to explain.",
                0.25,
            )
        if intent == "validation" and data.get("validation_findings"):
            answer = "The current validation findings are: " + "; ".join(
                row.get("message", "Review finding")
                for row in data["validation_findings"][:8]
            )
            return answer, 0.98
        if intent == "extraction_summary" and data.get("extraction_summary"):
            categories = data["extraction_summary"].get("categories") or []
            if categories:
                answer = "The extracted portfolio contains: " + "; ".join(
                    f"{row['document_type']}: {row['record_count']} records, taxable value "
                    f"₹{row['taxable_value']}"
                    for row in categories
                )
                return answer, 0.98
        if intent == "guidance" and data.get("collection"):
            collection = data["collection"]
            categories = (data.get("extraction_summary") or {}).get("categories") or []
            record_count = sum(int(row.get("record_count") or 0) for row in categories)
            review_count = sum(int(row.get("needs_review") or 0) for row in categories)
            validation_count = len(data.get("validation_findings") or [])
            reconciliation_review = int(
                ((data.get("reconciliation") or {}).get("summary") or {}).get(
                    "needs_review", 0
                )
                or 0
            )
            alert_count = len(data.get("alerts") or [])
            client_name = (data.get("client") or {}).get("business_name") or "This client"
            period = (data.get("application") or {}).get("period_label") or "this GST period"
            return (
                f"Application review snapshot for {client_name} ({period}): document "
                f"collection is {collection.get('received_count', 0)}/"
                f"{collection.get('required_count', 0)} "
                f"({collection.get('progress_percent', 0)}%). The extracted portfolio has "
                f"{record_count} records; {review_count} need CA review. There are "
                f"{validation_count} validation findings, {reconciliation_review} "
                f"reconciliation items needing review, and {alert_count} raised alert"
                f"{'s' if alert_count != 1 else ''}. Review the flagged source evidence "
                "before making the final GST or ITC decision.",
                0.8,
            )
        evidence = state.get("application_evidence") or state.get("knowledge_evidence") or []
        if evidence:
            return str(evidence[0]["content"])[:700], 0.8
        return (
            "I do not have enough evidence in this GST application to answer that question.",
            0.25,
        )

    @staticmethod
    def _money_label(metric: str | None) -> str:
        return {
            "taxable_value": "taxable value",
            "total_tax": "total GST",
            "invoice_total": "total invoice value",
            "igst": "IGST",
            "cgst": "CGST",
            "sgst_utgst": "SGST/UTGST",
            "cess": "cess",
        }.get(metric or "", (metric or "value").replace("_", " "))

    @staticmethod
    def _sum_metric(rows: list[dict[str, Any]], field: str) -> Decimal:
        return sum(
            (
                Decimal(str(row[field]))
                for row in rows
                if row.get(field) not in (None, "")
            ),
            Decimal("0"),
        )

    def _structured_answer(self, state: RAGState) -> tuple[str, float]:
        plan = state["query_plan"]
        result = state["structured_result"]
        if plan.operation == QueryOperation.CLARIFY:
            return plan.clarification or "Please clarify the requested application value.", 1.0
        if plan.operation == QueryOperation.COUNT:
            subject = (
                "tax invoice records"
                if plan.domain == QueryDomain.TRANSACTIONS
                else "records"
            )
            return f"This GST application contains {result.value} {subject}.", 1.0
        if plan.operation in {QueryOperation.MINIMUM, QueryOperation.MAXIMUM}:
            if not result.data or result.value is None:
                return "No matching records were found in this GST application.", 1.0
            record = result.data[0]
            direction = "lowest" if plan.operation == QueryOperation.MINIMUM else "highest"
            identity = (
                record.get("invoice_number")
                or record.get("document_number")
                or record.get("id")
            )
            return (
                f"The tax invoice with the {direction} {self._money_label(plan.metric)} is "
                f"{identity} at ₹{result.value}."
            ), 1.0
        if plan.operation in {QueryOperation.SUM, QueryOperation.AVERAGE}:
            label = "total" if plan.operation == QueryOperation.SUM else "average"
            return (
                f"The {label} {self._money_label(plan.metric)} across {result.row_count} "
                f"matching records is ₹{result.value or 0}."
            ), 1.0
        if plan.domain == QueryDomain.TRANSACTIONS and plan.operation == QueryOperation.SUMMARIZE:
            rows = result.data or []
            taxable = self._sum_metric(rows, "taxable_value")
            total_tax = self._sum_metric(rows, "total_tax")
            invoice_total = self._sum_metric(rows, "invoice_total")
            return (
                f"The scoped extracted portfolio has {result.row_count} records, taxable "
                f"value ₹{taxable}, total GST ₹{total_tax}, and total invoice value "
                f"₹{invoice_total}."
            ), 1.0
        if plan.domain == QueryDomain.TRANSACTIONS:
            if not result.data:
                return "No matching extracted GST records were found.", 1.0
            records = [
                f"{row.get('invoice_number') or row.get('id')} — "
                f"taxable ₹{row.get('taxable_value')}, "
                f"GST ₹{row.get('total_tax')}, invoice value ₹{row.get('invoice_total')}"
                for row in result.data[:20]
            ]
            return "The matching extracted records are: " + "; ".join(records) + ".", 1.0
        if plan.domain == QueryDomain.VALIDATION:
            if not result.data:
                return "No matching validation findings were found.", 1.0
            findings = [
                f"{row.get('message') or row.get('finding_type')} ({row.get('status')})"
                for row in result.data[:20]
            ]
            return "The matching validation findings are: " + "; ".join(findings) + ".", 1.0
        if plan.domain == QueryDomain.RECONCILIATION:
            if not result.data:
                return "No matching reconciliation items were found.", 1.0
            identities = []
            for row in result.data[:20]:
                evidence = row.get("evidence") or {}
                books = evidence.get("books") or {}
                gstr2b = evidence.get("gstr2b") or {}
                identity = books.get("invoice_number") or gstr2b.get("invoice_number")
                identities.append(f"{identity or row.get('id')} ({row.get('match_status')})")
            return "The matching reconciliation items are: " + "; ".join(identities) + ".", 1.0
        if plan.domain == QueryDomain.AUDIT:
            if not result.data:
                return "No matching audit events were found for this application.", 1.0
            rows = [
                f"{row.get('action')} at {row.get('created_at')}"
                for row in result.data[:20]
            ]
            return "The application audit trail shows: " + "; ".join(rows) + ".", 1.0
        if plan.domain == QueryDomain.ALERTS:
            if not result.data:
                return "No findings have been explicitly raised as alerts.", 1.0
            rows = [
                f"{row.get('title') or row.get('alert_type')} ({row.get('status', 'open')})"
                for row in result.data[:20]
            ]
            return "The CA explicitly raised these Alerts Dashboard items: " + "; ".join(rows), 1.0
        if not result.data:
            return "No matching records were found in this GST application.", 1.0
        return f"I found {result.row_count} matching application records.", 1.0

    @staticmethod
    def _compact_model_payload(state: RAGState) -> dict[str, Any]:
        application_data = state.get("application_data") or {}
        reconciliation = application_data.get("reconciliation") or {}
        compact_facts = {
            "application": application_data.get("application"),
            "client": application_data.get("client"),
            "collection": application_data.get("collection"),
            "extraction_summary": application_data.get("extraction_summary"),
            "validation_findings": (application_data.get("validation_findings") or [])[:10],
            "reconciliation": {
                "status": reconciliation.get("status"),
                "summary": reconciliation.get("summary") or {},
            },
            "alerts": [
                {
                    key: row.get(key)
                    for key in ("id", "title", "alert_type", "status", "severity", "message")
                }
                for row in (application_data.get("alerts") or [])[:10]
            ],
        }

        def compact_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "content": str(row.get("content") or "")[:1200],
                    "document_id": row.get("document_id"),
                    "document_type": row.get("document_type"),
                    "section": row.get("section"),
                    "page_number": row.get("page_number"),
                    "sheet_name": row.get("sheet_name"),
                    "row_start": row.get("row_start"),
                    "row_end": row.get("row_end"),
                    "metadata": {
                        key: (row.get("metadata") or {}).get(key)
                        for key in ("title", "section", "page", "source_url")
                    },
                }
                for row in rows[:6]
            ]

        return {
            "question": state["question"],
            "conversation_history": [
                {
                    "role": row.get("role"),
                    "content": str(row.get("content") or "")[:1000],
                }
                for row in (state.get("history") or [])[-6:]
            ],
            "application_facts": compact_facts,
            "application_evidence": compact_evidence(
                state.get("application_evidence") or []
            ),
            "knowledge_evidence": compact_evidence(state.get("knowledge_evidence") or []),
        }

    async def generate_grounded_answer(self, state: RAGState) -> dict[str, Any]:
        if state.get("intent") == "action_proposal" and state.get("proposed_action"):
            action = state["proposed_action"]
            return {
                "draft_answer": (
                    f"Review the proposed action: {action['title']}. Nothing has changed yet. "
                    "Confirm it below to execute, or cancel it."
                ),
                "confidence": 1.0,
            }
        if state.get("intent") == "dynamic_structured" and state.get("structured_result"):
            answer, confidence = self._structured_answer(state)
            return {"draft_answer": answer, "confidence": confidence}
        has_text_evidence = bool(
            state.get("application_evidence") or state.get("knowledge_evidence")
        )
        if (
            self.settings.ai_mode == "mock"
            or state["intent"] in EXACT_FACT_INTENTS
            or (state["intent"] == "guidance" and not has_text_evidence)
        ):
            answer, confidence = self._mock_answer(state)
            return {"draft_answer": answer, "confidence": confidence}
        payload = self._compact_model_payload(state)
        try:
            output = await asyncio.wait_for(
                complete_groq_json(
                    self.settings,
                    model=self.settings.effective_groq_rag_model,
                    max_tokens=self.settings.rag_max_output_tokens,
                    system_prompt=RAG_SYSTEM_PROMPT,
                    user_prompt=(
                        "Answer from this scoped evidence only.\n"
                        f"<application_evidence>{json.dumps(payload, default=str)}"
                        "</application_evidence>"
                    ),
                ),
                timeout=self.settings.rag_generation_timeout_seconds,
            )
            validated = AssistantModelOutput.model_validate(output)
            return {"draft_answer": validated.answer, "confidence": validated.confidence}
        except Exception as exc:
            response = getattr(exc, "response", None)
            provider_error: dict[str, Any] = {}
            if response is not None:
                try:
                    provider_error = (response.json() or {}).get("error") or {}
                except (TypeError, ValueError):
                    provider_error = {}
            logger.error(
                "Grounded assistant generation failed: type=%s status=%s code=%s message=%s",
                type(exc).__name__,
                getattr(response, "status_code", None),
                provider_error.get("code"),
                provider_error.get("message"),
            )
            answer, confidence = self._mock_answer(state)
            return {
                "draft_answer": answer,
                "confidence": min(confidence, 0.8),
            }

    @staticmethod
    def _unique_citations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, str | None]] = set()
        result: list[dict[str, Any]] = []
        for row in rows:
            key = (str(row.get("source_type")), str(row.get("title")), row.get("reference"))
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result

    def _citations(self, state: RAGState) -> list[dict[str, Any]]:
        data = state.get("application_data") or {}
        citations: list[dict[str, Any]] = []
        if state.get("structured_result"):
            citations.extend(state["structured_result"].citations)
        intent = state["intent"]
        period = str((data.get("application") or {}).get("period_label") or "GST period")
        has_collection_facts = bool(data.get("collection"))
        if intent in {"missing_documents", "draft_reminder"} or (
            intent == "guidance" and has_collection_facts
        ):
            citations.append(
                {
                    "source_type": "structured_fact",
                    "title": f"Document checklist · {period}",
                    "reference": "Current application checklist",
                }
            )
        for record in data.get("transactions") or []:
            source_row = record.get("source_row")
            citations.append(
                {
                    "source_type": "structured_fact",
                    "title": (
                        "Extracted record · "
                        f"{record.get('invoice_number') or record.get('id')}"
                    ),
                    "reference": "Normalized GST transaction",
                    "document_id": record.get("document_id"),
                    "page": record.get("source_page"),
                    "row_start": source_row,
                    "row_end": source_row,
                }
            )
        item = data.get("reconciliation_item")
        if item:
            evidence = item.get("evidence") or {}
            books = evidence.get("books") or {}
            gstr2b = evidence.get("gstr2b") or {}
            identity = books.get("invoice_number") or gstr2b.get("invoice_number")
            citations.append(
                {
                    "source_type": "reconciliation",
                    "title": f"Reconciliation · {identity or item.get('id')}",
                    "reference": "Books vs GSTR-2B",
                }
            )
        for alert in data.get("alerts") or []:
            citations.append(
                {
                    "source_type": "alert",
                    "title": f"Alert · {alert.get('title') or alert.get('id')}",
                    "reference": str(alert.get("id")),
                }
            )
        for row in state.get("application_evidence") or []:
            metadata = row.get("metadata") or {}
            citations.append(
                {
                    "source_type": "document",
                    "title": metadata.get("title") or "Application document",
                    "reference": row.get("section"),
                    "document_id": row.get("document_id"),
                    "section": row.get("section"),
                    "page": row.get("page_number"),
                    "sheet_name": row.get("sheet_name"),
                    "row_start": row.get("row_start"),
                    "row_end": row.get("row_end"),
                }
            )
        for row in state.get("knowledge_evidence") or []:
            metadata = row.get("metadata") or {}
            citations.append(
                {
                    "source_type": "knowledge",
                    "title": metadata.get("title") or "Knowledge source",
                    "section": metadata.get("section"),
                    "page": metadata.get("page"),
                    "source_url": metadata.get("source_url"),
                }
            )
        return self._unique_citations(citations)

    async def verify_scope_and_citations(self, state: RAGState) -> dict[str, Any]:
        citations = [
            row
            for row in self._citations(state)
            if "ground_truth" not in json.dumps(row, default=str).lower()
        ]
        source_types = list(dict.fromkeys(str(row["source_type"]) for row in citations))
        draft_answer = state["draft_answer"]
        confidence = state.get("confidence", 0.7)
        plan = state.get("query_plan")
        safe_uncited = bool(
            plan
            and plan.operation in {
                QueryOperation.CLARIFY,
                QueryOperation.PROPOSE_ACTION,
            }
        ) or any(
            phrase in draft_answer.lower()
            for phrase in (
                "do not have enough",
                "temporarily unavailable",
                "only answer about the currently opened",
            )
        )
        if not citations and not safe_uncited:
            draft_answer = (
                "I do not have enough scoped evidence in this GST application to answer "
                "that question."
            )
            confidence = min(confidence, 0.25)
        answer = {
            "answer": draft_answer,
            "citations": citations,
            "conversation_id": state["conversation_id"],
            "source_types": source_types,
            "used_application_data": bool(state.get("application_data")),
            "confidence": confidence,
        }
        if state.get("proposed_action"):
            answer["proposed_action"] = state["proposed_action"]
        result = state.get("structured_result")
        if result and plan:
            if plan.operation in {
                QueryOperation.COUNT,
                QueryOperation.SUM,
                QueryOperation.MINIMUM,
                QueryOperation.MAXIMUM,
                QueryOperation.AVERAGE,
            }:
                answer["calculation"] = {
                    "operation": plan.operation,
                    "metric": plan.metric,
                    "value": result.value,
                    "record_count": result.row_count,
                }
            raw_rows = result.data if isinstance(result.data, list) else []
            answer["rows"] = [
                {
                    key: value
                    for key, value in row.items()
                    if key in self._PUBLIC_ROW_FIELDS
                }
                for row in raw_rows[:50]
            ]
            answer["clarification"] = (
                plan.clarification if plan.operation == QueryOperation.CLARIFY else None
            )
            answer["tool_trace"] = [
                {
                    "tool": "execute_structured_plan",
                    "domain": plan.domain,
                    "operation": plan.operation,
                    "row_count": result.row_count,
                }
            ]
        return {"citations": citations, "source_types": source_types, "answer": answer}

    async def audit(self, state: RAGState) -> dict[str, Any]:
        data = state.get("application_data") or {}
        application = data.get("application") or {}
        await record_audit(
            self.store,
            firm_id=state["firm_id"],
            user_id=state["user_id"],
            action=(
                "rag_scope_refused"
                if state.get("intent") == "scope_refusal"
                else "rag_answer_generated"
            ),
            entity_type="application",
            entity_id=state["application_id"],
            client_id=application.get("client_id"),
            application_id=state["application_id"],
            demo_session_id=application.get("demo_session_id"),
            metadata={
                "question": state["question"],
                "conversation_id": state["conversation_id"],
                "source_types": state.get("source_types", []),
                "citation_count": len(state.get("citations", [])),
                "model": (
                    "mock"
                    if self.settings.ai_mode == "mock"
                    else self.settings.effective_groq_rag_model
                ),
                "status": "generated",
            },
        )
        return {}
