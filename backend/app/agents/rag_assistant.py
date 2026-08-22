"""Controlled application-scoped LangGraph assistant."""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from app.config import Settings
from app.prompts.rag import RAG_SYSTEM_PROMPT
from app.repositories.base import DataStore
from app.schemas.rag import AssistantModelOutput
from app.services.audit import record_audit
from app.services.llm.providers import complete_groq_json
from app.services.rag.application_context import load_structured_facts
from app.services.rag.document_indexing import sync_application_documents
from app.services.rag.retrieval import retrieve_application_documents, retrieve_knowledge

logger = logging.getLogger(__name__)

EXACT_FACT_INTENTS = {
    "missing_documents",
    "draft_reminder",
    "transaction_lookup",
    "reconciliation",
    "alerts",
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
            self.assistant.retrieve_application_evidence,
            self.assistant.retrieve_knowledge_if_needed,
            self.assistant.generate_grounded_answer,
            self.assistant.verify_scope_and_citations,
            self.assistant.audit,
        ):
            current.update(await node(current))
        return current


class RAGAssistant:
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
        await self._store_message(
            firm_id=firm_id,
            application_id=application_id,
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        result = await self.graph.ainvoke(
            {
                "question": question,
                "firm_id": firm_id,
                "application_id": application_id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "source_type": source_type,
                "history": history,
            }
        )
        answer = result["answer"]
        await self._store_message(
            firm_id=firm_id,
            application_id=application_id,
            user_id=user_id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer["answer"],
            citations=answer["citations"],
            source_types=answer["source_types"],
        )
        return answer

    async def _store_message(
        self,
        *,
        firm_id: str,
        application_id: str,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        citations: list[dict[str, Any]] | None = None,
        source_types: list[str] | None = None,
    ) -> None:
        application = await self.store.get_row("applications", application_id)
        await self.store.insert_row(
            "assistant_messages",
            {
                "firm_id": firm_id,
                "application_id": application_id,
                "demo_session_id": (application or {}).get("demo_session_id"),
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
        return {}

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
        return {"intent": intent}

    async def load_structured_facts(self, state: RAGState) -> dict[str, Any]:
        if (state.get("application_data") or {}).get("error"):
            return {}
        data = await load_structured_facts(
            self.store,
            application_id=state["application_id"],
            question=state["question"],
            intent=state["intent"],
        )
        return {"application_data": data}

    async def retrieve_application_evidence(self, state: RAGState) -> dict[str, Any]:
        if state["intent"] in {
            "missing_documents",
            "draft_reminder",
            "alerts",
            "scope_refusal",
        }:
            return {"application_evidence": []}
        await sync_application_documents(self.store, self.settings, state["application_id"])
        rows = await retrieve_application_documents(
            self.store,
            self.settings,
            question=state["question"],
            firm_id=state["firm_id"],
            application_id=state["application_id"],
        )
        return {"application_evidence": rows}

    async def retrieve_knowledge_if_needed(self, state: RAGState) -> dict[str, Any]:
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
        evidence = state.get("application_evidence") or state.get("knowledge_evidence") or []
        if evidence:
            return str(evidence[0]["content"])[:700], 0.8
        return (
            "I do not have enough evidence in this GST application to answer that question.",
            0.25,
        )

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
        if self.settings.ai_mode == "mock" or state["intent"] in EXACT_FACT_INTENTS:
            answer, confidence = self._mock_answer(state)
            return {"draft_answer": answer, "confidence": confidence}
        payload = self._compact_model_payload(state)
        try:
            output = await complete_groq_json(
                self.settings,
                system_prompt=RAG_SYSTEM_PROMPT,
                user_prompt=(
                    "Answer from this scoped evidence only.\n"
                    f"<application_evidence>{json.dumps(payload, default=str)}"
                    "</application_evidence>"
                ),
            )
            validated = AssistantModelOutput.model_validate(output)
            return {"draft_answer": validated.answer, "confidence": validated.confidence}
        except Exception as exc:
            logger.error("Grounded assistant generation failed: %s", type(exc).__name__)
            return {
                "draft_answer": (
                    "Grounded AI guidance is temporarily unavailable. No application data "
                    "was changed; please retry this question."
                ),
                "confidence": 0.0,
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
        intent = state["intent"]
        period = str((data.get("application") or {}).get("period_label") or "GST period")
        if intent in {"missing_documents", "draft_reminder"}:
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
        safe_uncited = any(
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
                    else self.settings.effective_groq_model
                ),
                "status": "generated",
            },
        )
        return {}
