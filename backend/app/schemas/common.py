from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class MessageResponse(APIModel):
    message: str


class PaginatedResponse(APIModel):
    items: list[dict[str, Any]]
    total: int
