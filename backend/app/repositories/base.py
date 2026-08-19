"""Storage abstraction shared by the Supabase and deterministic demo stores."""

from __future__ import annotations

from typing import Any, Protocol


class DataStore(Protocol):
    name: str

    async def list_rows(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        *,
        order: str | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]: ...

    async def get_row(self, table: str, row_id: str) -> dict[str, Any] | None: ...

    async def insert_row(self, table: str, data: dict[str, Any]) -> dict[str, Any]: ...

    async def update_row(
        self, table: str, row_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    async def delete_row(self, table: str, row_id: str) -> bool: ...

    async def upsert_row(
        self, table: str, data: dict[str, Any], *, on_conflict: str | None = None
    ) -> dict[str, Any]: ...

    async def rpc(self, function_name: str, params: dict[str, Any]) -> list[dict[str, Any]]: ...

    async def upload_file(
        self, bucket: str, path: str, content: bytes, mime_type: str
    ) -> str: ...

    async def download_file(self, bucket: str, path: str) -> bytes: ...

    async def create_signed_url(self, bucket: str, path: str, expires_in: int = 600) -> str: ...

    async def get_user_from_token(self, token: str) -> dict[str, Any] | None: ...
