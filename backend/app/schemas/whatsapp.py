from __future__ import annotations

from pydantic import BaseModel


class ReminderApproval(BaseModel):
    reminder_id: str
    message: str | None = None
