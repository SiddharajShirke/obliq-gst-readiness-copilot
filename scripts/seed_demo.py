#!/usr/bin/env python3
"""Seed Supabase Auth and PostgreSQL with synthetic OBLIQ demo records."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.repositories.memory import CLIENT_IDS, DEMO_FIRM_ID
from app.repositories.supabase import SupabaseStore
from app.services.document_processing.taxonomy import CLIENT_REQUIREMENTS
from app.services.rag.ingestion import ingest_file

CLIENTS = [
    (
        CLIENT_IDS["raj"],
        "Raj Traders",
        "Raj Traders",
        "27RAJTR1234A1Z5",
        "Maharashtra",
        "Retail",
        "monthly",
        "Raj Malhotra",
        "+919810000001",
        "guided_demo_template",
    ),
]

APPS = [
    (
        "30000000-0000-0000-0000-000000000001",
        CLIENT_IDS["raj"],
        "April 2026",
        "not_started",
    ),
]

REQUIREMENTS = CLIENT_REQUIREMENTS


def _find_user(admin: Any, email: str) -> Any | None:
    result = admin.list_users()
    users = getattr(result, "users", result if isinstance(result, list) else [])
    return next((user for user in users if getattr(user, "email", None) == email), None)


def _ensure_user(client: Any, *, email: str, password: str, full_name: str) -> str:
    user = _find_user(client.auth.admin, email)
    if not user:
        response = client.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            }
        )
        user = response.user
    return str(user.id)


async def seed() -> None:
    settings = Settings()
    if settings.use_in_memory_db:
        print("USE_IN_MEMORY_DB=true: the FastAPI demo store seeds itself on startup.")
        print(
            "Set USE_IN_MEMORY_DB=false and Supabase credentials to seed hosted Supabase."
        )
        return
    store = SupabaseStore(settings)
    client = store.client
    users = {
        "firm_admin": _ensure_user(
            client,
            email=settings.demo_admin_email,
            password=settings.demo_admin_password,
            full_name="Ananya Sharma",
        ),
        "gst_preparer": _ensure_user(
            client,
            email=settings.demo_preparer_email,
            password=settings.demo_preparer_password,
            full_name="Aman Verma",
        ),
        "reviewer": _ensure_user(
            client,
            email=settings.demo_reviewer_email,
            password=settings.demo_reviewer_password,
            full_name="Priya Nair",
        ),
    }
    client.table("firms").upsert(
        {"id": DEMO_FIRM_ID, "name": "Sharma & Associates", "slug": "sharma-associates"}
    ).execute()
    profile_rows = [
        {
            "id": users["firm_admin"],
            "full_name": "Ananya Sharma",
            "email": settings.demo_admin_email,
        },
        {
            "id": users["gst_preparer"],
            "full_name": "Aman Verma",
            "email": settings.demo_preparer_email,
        },
        {
            "id": users["reviewer"],
            "full_name": "Priya Nair",
            "email": settings.demo_reviewer_email,
        },
    ]
    client.table("profiles").upsert(profile_rows).execute()
    membership_rows = [
        {"firm_id": DEMO_FIRM_ID, "user_id": user_id, "role": role}
        for role, user_id in users.items()
    ]
    client.table("firm_members").upsert(
        membership_rows, on_conflict="firm_id,user_id"
    ).execute()

    for (
        client_id,
        business,
        legal,
        gstin,
        state,
        kind,
        frequency,
        contact,
        phone,
        scenario,
    ) in CLIENTS:
        client.table("clients").upsert(
            {
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
                "assigned_preparer_id": users["gst_preparer"],
                "reviewer_id": users["reviewer"],
                "demo_scenario": scenario,
            }
        ).execute()

    for app_id, client_id, label, status in APPS:
        client.table("applications").upsert(
            {
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
                "assigned_preparer_id": users["gst_preparer"],
                "reviewer_id": users["reviewer"],
            }
        ).execute()
        current = (
            client.table("document_requirements")
            .select("id")
            .eq("application_id", app_id)
            .execute()
            .data
            or []
        )
        if not current:
            rows = []
            for requirement_type, display in REQUIREMENTS.items():
                rows.append(
                    {
                        "application_id": app_id,
                        "requirement_type": requirement_type,
                        "label": display,
                        "required": True,
                        "status": "missing"
                        if client_id == CLIENT_IDS["raj"]
                        else "received",
                    }
                )
            client.table("document_requirements").insert(rows).execute()

    for path in sorted((ROOT / "demo_data" / "knowledge").glob("*.md")):
        official = path.name.startswith("gstr2b")
        await ingest_file(
            store,
            settings,
            path,
            source_type="official_gst" if official else "firm_sop",
            source_url="https://tutorial.gst.gov.in/userguide/returns/Manual_gstr2b.htm"
            if official
            else None,
            firm_id=None if official else DEMO_FIRM_ID,
        )
    print(
        "Seeded Sharma & Associates, three users, one Raj Traders Guided Demo client, one GST application, and demo knowledge."
    )
    print(f"Demo admin: {settings.demo_admin_email} / {settings.demo_admin_password}")


if __name__ == "__main__":
    asyncio.run(seed())
