from __future__ import annotations

from pydantic import BaseModel, EmailStr


class UserContext(BaseModel):
    user_id: str
    firm_id: str
    role: str
    email: EmailStr | str
