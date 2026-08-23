from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.agents.rag_assistant import RAGAssistant
from app.api.v1.alerts import generate_and_store_explanation
from app.config import Settings, get_settings
from app.dependencies import current_user, require_firm_row, require_roles
from app.repositories import DataStore, get_store
from app.schemas.auth import UserContext
from app.schemas.rag import (
    AssistantActionDecision,
    AssistantAnswer,
    AssistantQuery,
    KnowledgeTextIngest,
)
from app.services.assistant_actions import (
    ActionConflict,
    cancel_action_proposal,
    confirm_action_proposal,
)
from app.services.rag.document_indexing import index_document, remove_document_chunks
from app.services.rag.ingestion import ingest_bytes, ingest_text

router = APIRouter(tags=["rag"])


def _safe_proposal_status(row: dict) -> dict:
    result = row.get("result") or {}
    entity = result.get("entity") or {}
    return {
        "id": row.get("id"),
        "action_type": row.get("action_type"),
        "status": row.get("status"),
        "preview": row.get("preview") or {},
        "expires_at": row.get("expires_at"),
        "result": {
            "entity_type": result.get("entity_type"),
            "entity_id": entity.get("id"),
            "already_existed": bool(result.get("already_existed")),
        }
        if result
        else None,
    }


@router.post("/knowledge/upload", status_code=201)
async def upload_knowledge(
    file: UploadFile = File(...),
    title: str = Form(...),
    source_type: str = Form("firm_sop"),
    source_url: str | None = Form(None),
    document_version: str = Form("demo-v1"),
    user: UserContext = Depends(require_roles("firm_admin")),
    store: DataStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    content = await file.read()
    filename = file.filename or "knowledge.txt"
    digest = hashlib.sha256(content).hexdigest()
    safe_name = "".join(
        character if character.isalnum() or character in ".-_" else "_"
        for character in Path(filename).name
    )
    storage_path = f"{user.firm_id}/knowledge/{digest[:12]}-{safe_name}"
    await store.upload_file(
        settings.supabase_knowledge_bucket,
        storage_path,
        content,
        file.content_type or "application/octet-stream",
    )
    try:
        return await ingest_bytes(
            store,
            settings,
            content=content,
            filename=filename,
            title=title,
            source_type=source_type,
            source_url=source_url,
            firm_id=user.firm_id,
            document_version=document_version,
            storage_path=storage_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge/ingest", status_code=201)
async def ingest_knowledge_text(
    payload: KnowledgeTextIngest,
    user: Annotated[UserContext, Depends(require_roles("firm_admin"))],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if payload.shared_official:
        raise HTTPException(
            status_code=403,
            detail=(
                "Shared official knowledge can only be installed by a trusted seed "
                "or operator process"
            ),
        )
    firm_id = user.firm_id
    return await ingest_text(
        store,
        settings,
        text=payload.text,
        title=payload.title,
        source_type=payload.source_type,
        source_url=payload.source_url,
        firm_id=firm_id,
        document_version=payload.document_version,
    )


@router.get("/knowledge/sources")
async def list_knowledge_sources(
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    all_rows = await store.list_rows("knowledge_sources", order="created_at", desc=True)
    return [row for row in all_rows if row.get("firm_id") in (None, user.firm_id)]


@router.post("/assistant/query", response_model=AssistantAnswer)
async def assistant_query(
    payload: AssistantQuery,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await require_firm_row(store, "applications", payload.application_id, user.firm_id)
    return await RAGAssistant(store, settings).query(
        question=payload.question,
        firm_id=user.firm_id,
        application_id=payload.application_id,
        user_id=user.user_id,
        conversation_id=str(payload.conversation_id),
        source_type=payload.source_type,
        role=user.role,
    )


@router.post("/assistant/actions/{proposal_id}/confirm")
async def confirm_assistant_action(
    proposal_id: str,
    payload: AssistantActionDecision,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        confirmed = await confirm_action_proposal(
            store,
            settings,
            proposal_id=proposal_id,
            firm_id=user.firm_id,
            user_id=user.user_id,
            role=user.role,
            conversation_id=str(payload.conversation_id),
        )
        result = confirmed.get("result") or {}
        if result.get("entity_type") == "document_extraction" and result.get("document_id"):
            if confirmed.get("action_type") == "reject_extraction":
                background_tasks.add_task(
                    remove_document_chunks, store, result["document_id"]
                )
            else:
                background_tasks.add_task(
                    index_document, store, settings, result["document_id"]
                )
        if result.get("entity_type") == "alert" and (result.get("entity") or {}).get("id"):
            background_tasks.add_task(
                generate_and_store_explanation,
                store,
                settings,
                alert_id=result["entity"]["id"],
                firm_id=user.firm_id,
                user_id=user.user_id,
            )
        return _safe_proposal_status(confirmed)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Assistant action proposal not found") from exc
    except ActionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/assistant/actions/{proposal_id}/cancel")
async def cancel_assistant_action(
    proposal_id: str,
    payload: AssistantActionDecision,
    user: Annotated[UserContext, Depends(current_user)],
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    try:
        cancelled = await cancel_action_proposal(
            store,
            proposal_id=proposal_id,
            firm_id=user.firm_id,
            user_id=user.user_id,
            conversation_id=str(payload.conversation_id),
        )
        return _safe_proposal_status(cancelled)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Assistant action proposal not found") from exc
    except ActionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
