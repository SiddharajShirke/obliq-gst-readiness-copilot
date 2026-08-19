"""Thin async facade around the synchronous Supabase Python client."""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings


class SupabaseStore:
    name = "supabase"

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("Supabase URL and service-role key are required")
        from supabase import create_client

        self.settings = settings
        self.client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    async def list_rows(self, table: str, filters: dict[str, Any] | None = None, *, order: str | None = None, desc: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
        def run() -> list[dict[str, Any]]:
            query = self.client.table(table).select("*")
            for key, value in (filters or {}).items():
                if isinstance(value, (list, tuple, set)):
                    query = query.in_(key, list(value))
                elif value is None:
                    query = query.is_(key, "null")
                else:
                    query = query.eq(key, value)
            if order:
                query = query.order(order, desc=desc)
            if limit:
                query = query.limit(limit)
            return query.execute().data or []
        return await asyncio.to_thread(run)

    async def get_row(self, table: str, row_id: str) -> dict[str, Any] | None:
        rows = await self.list_rows(table, {"id": row_id}, limit=1)
        return rows[0] if rows else None

    async def insert_row(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            rows = self.client.table(table).insert(data).execute().data or []
            if not rows:
                raise RuntimeError(f"No row returned after insert into {table}")
            return rows[0]
        return await asyncio.to_thread(run)

    async def update_row(self, table: str, row_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        def run() -> dict[str, Any] | None:
            rows = self.client.table(table).update(data).eq("id", row_id).execute().data or []
            return rows[0] if rows else None
        return await asyncio.to_thread(run)

    async def delete_row(self, table: str, row_id: str) -> bool:
        def run() -> bool:
            rows = self.client.table(table).delete().eq("id", row_id).execute().data or []
            return bool(rows)
        return await asyncio.to_thread(run)

    async def upsert_row(self, table: str, data: dict[str, Any], *, on_conflict: str | None = None) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            rows = self.client.table(table).upsert(data, on_conflict=on_conflict).execute().data or []
            if not rows:
                raise RuntimeError(f"No row returned after upsert into {table}")
            return rows[0]
        return await asyncio.to_thread(run)

    async def rpc(self, function_name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return await asyncio.to_thread(lambda: self.client.rpc(function_name, params).execute().data or [])

    async def upload_file(self, bucket: str, path: str, content: bytes, mime_type: str) -> str:
        def run() -> str:
            self.client.storage.from_(bucket).upload(
                path,
                content,
                file_options={"content-type": mime_type, "upsert": "true"},
            )
            return path
        return await asyncio.to_thread(run)

    async def download_file(self, bucket: str, path: str) -> bytes:
        return await asyncio.to_thread(lambda: self.client.storage.from_(bucket).download(path))

    async def create_signed_url(self, bucket: str, path: str, expires_in: int = 600) -> str:
        def run() -> str:
            result = self.client.storage.from_(bucket).create_signed_url(path, expires_in)
            return result.get("signedURL") or result.get("signedUrl") or ""
        return await asyncio.to_thread(run)

    async def get_user_from_token(self, token: str) -> dict[str, Any] | None:
        def run() -> dict[str, Any] | None:
            response = self.client.auth.get_user(token)
            user = response.user
            if not user:
                return None
            memberships = (
                self.client.table("firm_members")
                .select("firm_id,role")
                .eq("user_id", str(user.id))
                .limit(1)
                .execute()
                .data
                or []
            )
            if not memberships:
                return None
            return {
                "id": str(user.id),
                "firm_id": memberships[0]["firm_id"],
                "role": memberships[0]["role"],
                "email": user.email or "",
            }
        return await asyncio.to_thread(run)
