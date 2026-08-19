#!/usr/bin/env python3
"""Remove the synthetic demo firm and users from a configured Supabase project."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings  # noqa: E402
from supabase import create_client  # noqa: E402


def main() -> None:
    settings = Settings()
    if settings.use_in_memory_db:
        print("In-memory demo resets whenever FastAPI restarts.")
        return
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    firms = client.table("firms").select("id").eq("slug", "sharma-associates").execute().data or []
    for firm in firms:
        client.table("firms").delete().eq("id", firm["id"]).execute()
    result = client.auth.admin.list_users()
    users = getattr(result, "users", result if isinstance(result, list) else [])
    demo_emails = {settings.demo_admin_email, settings.demo_preparer_email, settings.demo_reviewer_email}
    for user in users:
        if getattr(user, "email", None) in demo_emails:
            client.auth.admin.delete_user(str(user.id))
    print("Removed synthetic OBLIQ demo records from Supabase.")


if __name__ == "__main__":
    main()
