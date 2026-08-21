"""In-memory repository used by the self-contained hosted/local demo mode."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import math
import re
import shutil
import time
import uuid
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.config import Settings

DEMO_FIRM_ID = "11111111-1111-1111-1111-111111111111"
DEMO_ADMIN_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DEMO_PREPARER_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
DEMO_REVIEWER_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"

CLIENT_IDS = {
    "raj": "20000000-0000-0000-0000-000000000001",
    "abc": "20000000-0000-0000-0000-000000000002",
    "nova": "20000000-0000-0000-0000-000000000003",
    "city": "20000000-0000-0000-0000-000000000004",
    "mehta": "20000000-0000-0000-0000-000000000005",
}

_LEXICAL_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "should", "the", "to",
    "what", "when", "where", "which", "with",
}


def _lexical_terms(value: str) -> set[str]:
    normalized = value.lower().replace("gstr-2b", "gstr2b").replace("gstr 2b", "gstr2b")
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", normalized):
        if token in _LEXICAL_STOP_WORDS:
            continue
        if token.endswith("ing") and len(token) > 5:
            token = token[:-3]
        elif token.endswith("ed") and len(token) > 4:
            token = token[:-2]
        elif token.endswith("s") and len(token) > 4:
            token = token[:-1]
        terms.add(token)
    return terms


class MemoryStore:
    name = "memory"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lock = asyncio.Lock()
        self.tables: dict[str, list[dict[str, Any]]] = {}
        settings.local_upload_dir.mkdir(parents=True, exist_ok=True)
        settings.local_export_dir.mkdir(parents=True, exist_ok=True)
        self._seed()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _seed(self) -> None:
        now = self._now()
        self.tables = {
            "profiles": [
                {"id": DEMO_ADMIN_ID, "full_name": "Ananya Sharma", "email": self.settings.demo_admin_email, "created_at": now, "updated_at": now},
                {"id": DEMO_PREPARER_ID, "full_name": "Aman Verma", "email": self.settings.demo_preparer_email, "created_at": now, "updated_at": now},
                {"id": DEMO_REVIEWER_ID, "full_name": "Priya Nair", "email": self.settings.demo_reviewer_email, "created_at": now, "updated_at": now},
            ],
            "firms": [{"id": DEMO_FIRM_ID, "name": "Sharma & Associates", "slug": "sharma-associates", "created_at": now, "updated_at": now}],
            "firm_members": [
                {"id": str(uuid.uuid4()), "firm_id": DEMO_FIRM_ID, "user_id": DEMO_ADMIN_ID, "role": "firm_admin", "created_at": now},
                {"id": str(uuid.uuid4()), "firm_id": DEMO_FIRM_ID, "user_id": DEMO_PREPARER_ID, "role": "gst_preparer", "created_at": now},
                {"id": str(uuid.uuid4()), "firm_id": DEMO_FIRM_ID, "user_id": DEMO_REVIEWER_ID, "role": "reviewer", "created_at": now},
            ],
            "clients": [],
            "applications": [],
            "document_requirements": [],
            "upload_links": [],
            "documents": [],
            "document_extractions": [],
            "invoice_records": [],
            "validation_findings": [],
            "reconciliation_runs": [],
            "reconciliation_items": [],
            "reminders": [],
            "whatsapp_messages": [],
            "whatsapp_demo_sessions": [],
            "integration_settings": [],
            "knowledge_sources": [],
            "knowledge_chunks": [],
            "alerts": [],
            "audit_events": [],
            "workflow_runs": [],
        }
        scenarios = [
            (CLIENT_IDS["raj"], "Raj Traders", "Raj Traders", "27RAJTR1234A1Z5", "Maharashtra", "Retail", "monthly", "Raj Malhotra", "+919810000001", "purchase register missing"),
            (CLIENT_IDS["abc"], "ABC Electronics", "ABC Electronics Private Limited", "29ABCDE1234F1Z3", "Karnataka", "Electronics", "monthly", "Kavya Rao", "+919810000002", "duplicate and wrong-period invoice"),
            (CLIENT_IDS["nova"], "Nova Services", "Nova Professional Services LLP", "07NOVAS1234L1Z4", "Delhi", "Professional services", "monthly", "Rohan Mehta", "+919810000003", "ready for CA review"),
            (CLIENT_IDS["city"], "City Retail", "City Retail Private Limited", "24CITYR1234P1Z2", "Gujarat", "Retail", "quarterly", "Neha Shah", "+919810000004", "GSTR-2B mismatch"),
            (CLIENT_IDS["mehta"], "Mehta Consulting", "Mehta Consulting", "27MEHTA1234C1Z6", "Maharashtra", "Consulting", "monthly", "Arjun Mehta", "+919810000005", "low-confidence scan"),
        ]
        for client_id, business, legal, gstin, state, kind, frequency, contact, phone, scenario in scenarios:
            self.tables["clients"].append({
                "id": client_id,
                "firm_id": DEMO_FIRM_ID,
                "business_name": business,
                "legal_name": legal,
                "gstin": gstin,
                "state": state,
                "business_type": kind,
                "filing_frequency": frequency,
                "contact_name": contact,
                "whatsapp_phone": phone,
                "preferred_language": "English",
                "whatsapp_consent": True,
                "assigned_preparer_id": DEMO_PREPARER_ID,
                "reviewer_id": DEMO_REVIEWER_ID,
                "demo_scenario": scenario,
                "created_at": now,
                "updated_at": now,
            })

        seeded_apps = [
            ("30000000-0000-0000-0000-000000000001", CLIENT_IDS["raj"], "April 2026", "partially_received"),
            ("30000000-0000-0000-0000-000000000002", CLIENT_IDS["abc"], "April 2026", "validation_review"),
            ("30000000-0000-0000-0000-000000000003", CLIENT_IDS["nova"], "April 2026", "ready_for_ca_review"),
            ("30000000-0000-0000-0000-000000000004", CLIENT_IDS["city"], "Q1 2026-27", "reconciliation_review"),
            ("30000000-0000-0000-0000-000000000005", CLIENT_IDS["mehta"], "April 2026", "extraction_review"),
        ]
        for app_id, client_id, label, status in seeded_apps:
            self.tables["applications"].append({
                "id": app_id,
                "firm_id": DEMO_FIRM_ID,
                "client_id": client_id,
                "application_type": "gst_readiness",
                "financial_year": "2026-27",
                "period_label": label,
                "period_start": "2026-04-01",
                "period_end": "2026-06-30" if "Q1" in label else "2026-04-30",
                "filing_frequency": "quarterly" if "Q1" in label else "monthly",
                "due_date": "2026-07-22" if "Q1" in label else "2026-05-20",
                "status": status,
                "assigned_preparer_id": DEMO_PREPARER_ID,
                "reviewer_id": DEMO_REVIEWER_ID,
                "created_at": now,
                "updated_at": now,
            })
            self._add_requirements(app_id, all_missing=client_id == CLIENT_IDS["raj"])

        self._seed_knowledge(now)

    def _seed_knowledge(self, now: str) -> None:
        from app.services.rag.embeddings import DeterministicEmbeddingProvider

        sources = [
            {
                "id": "90000000-0000-0000-0000-000000000001",
                "firm_id": None,
                "source_type": "official_gst",
                "title": "GSTR-2B Reconciliation Guidance",
                "description": "Synthetic paraphrased guidance for the OBLIQ demonstration.",
                "source_url": "https://tutorial.gst.gov.in/userguide/returns/Manual_gstr2b.htm",
                "document_version": "demo-v1",
                "checksum": "demo-gstr2b-guidance",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "90000000-0000-0000-0000-000000000002",
                "firm_id": DEMO_FIRM_ID,
                "source_type": "firm_sop",
                "title": "Sharma & Associates GST Review SOP",
                "description": "Synthetic internal SOP for the hiring prototype.",
                "source_url": None,
                "document_version": "demo-v1",
                "checksum": "demo-firm-sop",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ]
        self.tables["knowledge_sources"].extend(sources)
        contents = [
            (sources[0], "GSTR-2B is an auto-drafted statement used as a reference during input tax credit review. A mismatch means an invoice or amount differs between the purchase register and the uploaded GSTR-2B data. OBLIQ must present these as possible differences requiring CA review, not as automatic approval or rejection of ITC."),
            (sources[1], "When invoice totals do not match the taxable value plus CGST, SGST, IGST and cess, the preparer should compare the original document with extracted fields. Low-confidence data, duplicate invoices, wrong-period dates and missing GSTIN values must remain open until a reviewer resolves or accepts the finding."),
            (sources[1], "Client reminders should identify only the documents still missing, include the secure upload link, and remain short and professional. The CA must approve or edit every outbound reminder before the WhatsApp provider sends it."),
        ]
        embedder = DeterministicEmbeddingProvider(self.settings.embedding_dimension)
        vectors = embedder.embed_texts([content for _, content in contents])
        for index, ((source, content), embedding) in enumerate(zip(contents, vectors, strict=True)):
            self.tables["knowledge_chunks"].append({
                "id": f"91000000-0000-0000-0000-{index + 1:012d}",
                "source_id": source["id"],
                "firm_id": source["firm_id"],
                "chunk_index": index,
                "content": content,
                "metadata": {
                    "title": source["title"],
                    "section": "Prototype guidance",
                    "page": 1,
                    "source_type": source["source_type"],
                    "source_url": source["source_url"],
                    "document_version": "demo-v1",
                },
                "embedding": embedding,
                "created_at": now,
            })

    def _add_requirements(self, application_id: str, *, all_missing: bool = False) -> None:
        labels = {
            "sales_register": "Sales Register",
            "purchase_register": "Purchase Register",
            "sales_invoice": "Sales Invoices",
            "purchase_invoice": "Purchase Invoices",
            "gstr2b": "GSTR-2B",
        }
        now = self._now()
        for requirement_type, label in labels.items():
            status = "missing" if all_missing else "received"
            self.tables["document_requirements"].append({
                "id": str(uuid.uuid4()),
                "application_id": application_id,
                "requirement_type": requirement_type,
                "label": label,
                "required": True,
                "status": status,
                "created_at": now,
                "updated_at": now,
            })

    async def reset_demo(self) -> dict[str, int | str]:
        """Restore deterministic seeded state and remove generated runtime files."""
        async with self.lock:
            for directory in (self.settings.local_upload_dir, self.settings.local_export_dir):
                shutil.rmtree(directory, ignore_errors=True)
                directory.mkdir(parents=True, exist_ok=True)
            self._seed()
            return {
                "status": "reset",
                "clients": len(self.tables["clients"]),
                "applications": len(self.tables["applications"]),
            }

    async def list_rows(self, table: str, filters: dict[str, Any] | None = None, *, order: str | None = None, desc: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
        rows = [deepcopy(row) for row in self.tables.get(table, [])]
        for key, value in (filters or {}).items():
            if isinstance(value, (list, tuple, set)):
                rows = [row for row in rows if row.get(key) in value]
            elif value is None:
                rows = [row for row in rows if row.get(key) is None]
            else:
                rows = [row for row in rows if str(row.get(key)) == str(value)]
        if order:
            rows.sort(key=lambda row: str(row.get(order, "")), reverse=desc)
        return rows[:limit] if limit else rows

    async def get_row(self, table: str, row_id: str) -> dict[str, Any] | None:
        rows = await self.list_rows(table, {"id": row_id}, limit=1)
        return rows[0] if rows else None

    async def insert_row(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self.lock:
            now = self._now()
            row = deepcopy(data)
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", now)
            if table not in {"audit_events", "firm_members", "upload_links", "validation_findings", "reconciliation_items", "knowledge_chunks"}:
                row.setdefault("updated_at", now)
            self.tables.setdefault(table, []).append(row)
            return deepcopy(row)

    async def update_row(self, table: str, row_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        async with self.lock:
            for row in self.tables.get(table, []):
                if str(row.get("id")) == str(row_id):
                    row.update(deepcopy(data))
                    if "updated_at" in row:
                        row["updated_at"] = self._now()
                    return deepcopy(row)
        return None

    async def delete_row(self, table: str, row_id: str) -> bool:
        async with self.lock:
            rows = self.tables.get(table, [])
            before = len(rows)
            self.tables[table] = [row for row in rows if str(row.get("id")) != str(row_id)]
            return len(self.tables[table]) < before

    async def upsert_row(self, table: str, data: dict[str, Any], *, on_conflict: str | None = None) -> dict[str, Any]:
        keys = [item.strip() for item in (on_conflict or "id").split(",")]
        for row in self.tables.get(table, []):
            if all(str(row.get(key)) == str(data.get(key)) for key in keys):
                return (await self.update_row(table, str(row["id"]), data)) or row
        return await self.insert_row(table, data)

    async def rpc(self, function_name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if function_name == "create_whatsapp_demo_session":
            async with self.lock:
                base = next(
                    (
                        row
                        for row in self.tables["applications"]
                        if row["id"] == params["p_base_application_id"]
                        and row["firm_id"] == params["p_firm_id"]
                        and not row.get("demo_session_id")
                    ),
                    None,
                )
                if not base:
                    return []
                now = self._now()
                session_id = str(uuid.uuid4())
                application_id = str(uuid.uuid4())
                session = {
                    "id": session_id,
                    "firm_id": base["firm_id"],
                    "base_client_id": base["client_id"],
                    "base_application_id": base["id"],
                    "session_application_id": application_id,
                    "created_by_user_id": params["p_created_by_user_id"],
                    "start_token_hash": params["p_start_token_hash"],
                    "dashboard_access_token_hash": params[
                        "p_dashboard_access_token_hash"
                    ],
                    "judge_phone_hash": None,
                    "judge_phone_encrypted": None,
                    "judge_phone_last_four": None,
                    "provider_user_id_hash": None,
                    "status": "waiting_for_start",
                    "current_step": "scan_start_qr",
                    "token_expires_at": params["p_token_expires_at"],
                    "expires_at": params["p_expires_at"],
                    "created_at": now,
                    "connected_at": None,
                    "last_activity_at": None,
                    "completed_at": None,
                    "cancelled_at": None,
                    "anonymized_at": None,
                    "metadata": {},
                    "updated_at": now,
                }
                clone = deepcopy(base)
                clone.update(
                    {
                        "id": application_id,
                        "demo_session_id": session_id,
                        "status": "not_started",
                        "filing_date": None,
                        "arn": None,
                        "filed_return_document_id": None,
                        "payment_challan_document_id": None,
                        "final_notes": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                self.tables["whatsapp_demo_sessions"].append(session)
                self.tables["applications"].append(clone)
                requirements = [
                    row
                    for row in self.tables["document_requirements"]
                    if row["application_id"] == base["id"]
                ]
                for requirement in requirements:
                    cloned_requirement = deepcopy(requirement)
                    cloned_requirement.update(
                        {
                            "id": str(uuid.uuid4()),
                            "application_id": application_id,
                            "status": "missing",
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                    self.tables["document_requirements"].append(cloned_requirement)
                return [
                    {
                        "session_id": session_id,
                        "session_application_id": application_id,
                        "base_client_id": base["client_id"],
                    }
                ]
        if function_name == "bind_whatsapp_demo_session":
            async with self.lock:
                now = datetime.fromisoformat(
                    str(params["p_now"]).replace("Z", "+00:00")
                )
                session = next(
                    (
                        row
                        for row in self.tables["whatsapp_demo_sessions"]
                        if row.get("start_token_hash") == params["p_start_token_hash"]
                        and row.get("status") == "waiting_for_start"
                        and datetime.fromisoformat(
                            str(row["token_expires_at"]).replace("Z", "+00:00")
                        )
                        > now
                        and datetime.fromisoformat(
                            str(row["expires_at"]).replace("Z", "+00:00")
                        )
                        > now
                    ),
                    None,
                )
                if not session:
                    return []
                for other in self.tables["whatsapp_demo_sessions"]:
                    if (
                        other["id"] != session["id"]
                        and other.get("judge_phone_hash") == params["p_judge_phone_hash"]
                        and other.get("status") == "active"
                    ):
                        other.update(
                            {
                                "status": "cancelled",
                                "cancelled_at": params["p_now"],
                                "last_activity_at": params["p_now"],
                            }
                        )
                session.update(
                    {
                        "start_token_hash": None,
                        "judge_phone_hash": params["p_judge_phone_hash"],
                        "judge_phone_encrypted": params["p_judge_phone_encrypted"],
                        "judge_phone_last_four": params["p_judge_phone_last_four"],
                        "provider_user_id_hash": params["p_provider_user_id_hash"],
                        "status": "active",
                        "current_step": "checklist_sent",
                        "connected_at": params["p_now"],
                        "last_activity_at": params["p_now"],
                        "updated_at": params["p_now"],
                    }
                )
                return [deepcopy(session)]
        if function_name == "match_knowledge_chunks":
            query = params.get("query_embedding") or []
            firm_id = params.get("user_firm_id")
            minimum = float(params.get("min_similarity", 0.0))
            count = int(params.get("match_count", 12))
            results = []
            for row in self.tables.get("knowledge_chunks", []):
                if row.get("firm_id") not in (None, firm_id):
                    continue
                embedding = row.get("embedding") or []
                if not embedding or len(embedding) != len(query):
                    continue
                dot = sum(float(a) * float(b) for a, b in zip(embedding, query, strict=True))
                qn = math.sqrt(sum(float(a) ** 2 for a in query)) or 1
                en = math.sqrt(sum(float(a) ** 2 for a in embedding)) or 1
                similarity = dot / (qn * en)
                if similarity >= minimum:
                    results.append({"chunk_id": row["id"], "source_id": row["source_id"], "content": row["content"], "metadata": row.get("metadata", {}), "similarity": similarity})
            return sorted(results, key=lambda row: row["similarity"], reverse=True)[:count]
        if function_name == "search_knowledge_chunks_lexical":
            terms = _lexical_terms(str(params.get("query_text", "")))
            firm_id = params.get("user_firm_id")
            count = int(params.get("match_count", 12))
            results = []
            for row in self.tables.get("knowledge_chunks", []):
                if row.get("firm_id") not in (None, firm_id):
                    continue
                metadata = row.get("metadata", {}) or {}
                searchable = " ".join(
                    str(part or "")
                    for part in (row.get("content"), metadata.get("title"), metadata.get("section"))
                )
                words = _lexical_terms(searchable)
                rank = len(terms & words) / max(len(terms), 1)
                if rank:
                    results.append({"chunk_id": row["id"], "source_id": row["source_id"], "content": row["content"], "metadata": metadata, "rank": rank})
            return sorted(results, key=lambda row: row["rank"], reverse=True)[:count]
        return []

    async def upload_file(self, bucket: str, path: str, content: bytes, mime_type: str) -> str:
        target = self.settings.local_upload_dir / bucket / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return path

    async def download_file(self, bucket: str, path: str) -> bytes:
        return (self.settings.local_upload_dir / bucket / path).read_bytes()

    async def create_signed_url(self, bucket: str, path: str, expires_in: int = 600) -> str:
        expires = int(time.time()) + expires_in
        message = f"{bucket}:{path}:{expires}"
        signature = hmac.new(
            self.settings.upload_token_pepper.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return f"/api/v1/local-files/{bucket}/{path}?expires={expires}&signature={signature}"

    async def get_user_from_token(self, token: str) -> dict[str, Any] | None:
        mapping = {
            "demo-admin-token": (DEMO_ADMIN_ID, "firm_admin", self.settings.demo_admin_email),
            "demo-preparer-token": (DEMO_PREPARER_ID, "gst_preparer", self.settings.demo_preparer_email),
            "demo-reviewer-token": (DEMO_REVIEWER_ID, "reviewer", self.settings.demo_reviewer_email),
        }
        match = mapping.get(token)
        if not match:
            return None
        user_id, role, email = match
        return {"id": user_id, "firm_id": DEMO_FIRM_ID, "role": role, "email": email}
