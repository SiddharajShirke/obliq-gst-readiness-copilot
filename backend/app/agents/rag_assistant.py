"""Controlled RAG assistant that routes facts to PostgreSQL and guidance to RAG."""

from __future__ import annotations

from typing import Any, TypedDict

from app.config import Settings
from app.prompts.rag import RAG_SYSTEM_PROMPT
from app.repositories.base import DataStore
from app.services.llm.providers import complete_json
from app.services.rag.retrieval import retrieve_knowledge


class RAGState(TypedDict, total=False):
    question: str
    application_id: str | None
    firm_id: str
    source_type: str | None
    intent: str
    application_data: dict[str, Any]
    retrieved: list[dict[str, Any]]
    answer: dict[str, Any]


class _FallbackGraph:
    def __init__(self, assistant: "RAGAssistant") -> None:
        self.assistant = assistant

    async def ainvoke(self, state: RAGState) -> RAGState:
        current = dict(state)
        for node in (
            self.assistant.classify_intent,
            self.assistant.load_application_data,
            self.assistant.retrieve_context,
            self.assistant.generate_answer,
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
        graph.add_node("classify_intent", self.classify_intent)
        graph.add_node("load_application_data", self.load_application_data)
        graph.add_node("retrieve_context", self.retrieve_context)
        graph.add_node("generate_answer", self.generate_answer)
        graph.add_edge(START, "classify_intent")
        graph.add_edge("classify_intent", "load_application_data")
        graph.add_edge("load_application_data", "retrieve_context")
        graph.add_edge("retrieve_context", "generate_answer")
        graph.add_edge("generate_answer", END)
        return graph.compile()

    async def query(
        self,
        *,
        question: str,
        firm_id: str,
        application_id: str | None,
        source_type: str | None,
    ) -> dict[str, Any]:
        result = await self.graph.ainvoke(
            {
                "question": question,
                "firm_id": firm_id,
                "application_id": application_id,
                "source_type": source_type,
            }
        )
        return result["answer"]

    async def classify_intent(self, state: RAGState) -> dict[str, Any]:
        question = state["question"].lower()
        if any(word in question for word in ("missing", "pending", "checklist")):
            intent = "missing_documents"
        elif any(word in question for word in ("flagged", "validation", "error", "duplicate")):
            intent = "finding_explanation"
        elif any(word in question for word in ("gstr-2b", "gstr2b", "reconcile", "mismatch")):
            intent = "reconciliation_explanation"
        elif any(word in question for word in ("draft", "reminder", "ask the client")):
            intent = "draft_message"
        else:
            intent = "guidance"
        return {"intent": intent}

    async def load_application_data(self, state: RAGState) -> dict[str, Any]:
        application_id = state.get("application_id")
        if not application_id:
            return {"application_data": {}}
        application = await self.store.get_row("applications", application_id)
        if not application or application.get("firm_id") != state["firm_id"]:
            return {"application_data": {"error": "Application not found"}}
        client = await self.store.get_row("clients", application["client_id"])
        checklist = await self.store.list_rows("document_requirements", {"application_id": application_id})
        findings = await self.store.list_rows("validation_findings", {"application_id": application_id, "status": "open"})
        runs = await self.store.list_rows("reconciliation_runs", {"application_id": application_id}, order="created_at", desc=True, limit=1)
        return {
            "application_data": {
                "application": application,
                "client": client,
                "checklist": checklist,
                "findings": findings,
                "reconciliation": runs[0] if runs else None,
            }
        }

    async def retrieve_context(self, state: RAGState) -> dict[str, Any]:
        if state["intent"] == "missing_documents":
            return {"retrieved": []}
        rows = await retrieve_knowledge(
            self.store,
            self.settings,
            question=state["question"],
            firm_id=state["firm_id"],
            source_type=state.get("source_type"),
        )
        return {"retrieved": rows}

    @staticmethod
    def _citations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str | None]] = set()
        citations: list[dict[str, Any]] = []
        for row in rows:
            metadata = row.get("metadata") or {}
            key = (metadata.get("title") or "Knowledge source", metadata.get("section"))
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "title": key[0],
                    "section": key[1],
                    "page": metadata.get("page"),
                    "source_url": metadata.get("source_url"),
                }
            )
        return citations

    async def generate_answer(self, state: RAGState) -> dict[str, Any]:
        data = state.get("application_data", {})
        retrieved = state.get("retrieved", [])
        intent = state["intent"]
        used_application = bool(data and "error" not in data)

        if self.settings.ai_mode == "mock":
            if intent == "missing_documents" and used_application:
                missing = [row["label"] for row in data.get("checklist", []) if row.get("status") == "missing"]
                answer = (
                    f"The following GST document is still missing: {', '.join(missing)}."
                    if missing
                    else "All required GST document categories have been received."
                )
            elif intent == "finding_explanation" and data.get("findings"):
                messages = [row["message"] for row in data["findings"][:5]]
                answer = "The application is flagged because: " + " ".join(messages)
            elif intent == "reconciliation_explanation" and data.get("reconciliation"):
                answer = f"The latest reconciliation summary is {data['reconciliation'].get('summary', {})}. These are review differences, not final ITC decisions."
            elif retrieved:
                answer = retrieved[0]["content"][:700]
            else:
                answer = "I do not have enough retrieved evidence to answer this question."
            return {
                "answer": {
                    "answer": answer,
                    "citations": self._citations(retrieved),
                    "used_application_data": used_application,
                    "confidence": 0.86 if answer and "not have enough" not in answer else 0.35,
                }
            }

        context = "\n\n".join(
            f"SOURCE {index + 1}: {row.get('metadata', {})}\n{row['content']}"
            for index, row in enumerate(retrieved)
        )
        model_answer = await complete_json(
            self.settings,
            system_prompt=RAG_SYSTEM_PROMPT,
            user_prompt=(
                f"Question: {state['question']}\n\n"
                f"Application facts: {data}\n\nRetrieved context:\n{context}"
            ),
        )
        model_answer["citations"] = self._citations(retrieved)
        model_answer["used_application_data"] = used_application
        return {"answer": model_answer}
