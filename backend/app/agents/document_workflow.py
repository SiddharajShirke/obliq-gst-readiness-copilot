"""Controlled LangGraph workflow for document processing.

A tiny fallback runner keeps unit tests and mock mode usable before optional LangGraph
packages are installed. When LangGraph is installed, the exact same nodes are compiled
into a StateGraph.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class DocumentState(TypedDict, total=False):
    document_id: str
    document: dict[str, Any]
    content: bytes
    document_type: str
    raw_text: str
    structured_data: dict[str, Any]
    invoice_rows: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    provider: str
    model_name: str
    task_type: str
    fallback_reason: str | None
    started_at: str
    completed_at: str
    duration_ms: int
    status: str


class DocumentNodes(Protocol):
    async def load_document(self, state: DocumentState) -> dict[str, Any]: ...
    async def classify_document(self, state: DocumentState) -> dict[str, Any]: ...
    async def parse_and_extract(self, state: DocumentState) -> dict[str, Any]: ...
    async def persist_extraction(self, state: DocumentState) -> dict[str, Any]: ...
    async def validate_document(self, state: DocumentState) -> dict[str, Any]: ...


class _FallbackGraph:
    def __init__(self, nodes: DocumentNodes) -> None:
        self.nodes = nodes

    async def ainvoke(self, state: DocumentState) -> DocumentState:
        current: DocumentState = dict(state)
        for node in (
            self.nodes.load_document,
            self.nodes.classify_document,
            self.nodes.parse_and_extract,
            self.nodes.persist_extraction,
            self.nodes.validate_document,
        ):
            current.update(await node(current))
        return current


def build_document_graph(nodes: DocumentNodes):
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _FallbackGraph(nodes)

    graph = StateGraph(DocumentState)
    graph.add_node("load_document", nodes.load_document)
    graph.add_node("classify_document", nodes.classify_document)
    graph.add_node("parse_and_extract", nodes.parse_and_extract)
    graph.add_node("persist_extraction", nodes.persist_extraction)
    graph.add_node("validate_document", nodes.validate_document)
    graph.add_edge(START, "load_document")
    graph.add_edge("load_document", "classify_document")
    graph.add_edge("classify_document", "parse_and_extract")
    graph.add_edge("parse_and_extract", "persist_extraction")
    graph.add_edge("persist_extraction", "validate_document")
    graph.add_edge("validate_document", END)
    return graph.compile()
