"""Security helpers for temporary WhatsApp demo sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

START_TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_start_token(length: int = 8) -> str:
    return "".join(secrets.choice(START_TOKEN_ALPHABET) for _ in range(length))


def generate_dashboard_token() -> str:
    return secrets.token_urlsafe(32)


def hash_demo_token(value: str, *, pepper: str, domain: str) -> str:
    payload = f"{domain}:{value}".encode()
    return hmac.new(pepper.encode(), payload, hashlib.sha256).hexdigest()


def normalize_whatsapp_phone(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    while normalized.lower().startswith("whatsapp:"):
        normalized = normalized[len("whatsapp:") :]
    digits = re.sub(r"\D", "", normalized)
    return f"+{digits}" if digits else None


def mask_phone(value: str) -> str:
    normalized = normalize_whatsapp_phone(value)
    if not normalized:
        return ""
    if normalized.startswith("+91") and len(normalized) >= 7:
        return f"+91 ******{normalized[-4:]}"
    return f"+{'*' * max(len(normalized) - 5, 2)}{normalized[-4:]}"


@dataclass(frozen=True, slots=True)
class ProtectedPhone:
    lookup_hash: str
    encrypted: str
    last_four: str


class PhoneProtector:
    def __init__(self, *, hash_pepper: str, encryption_key: str) -> None:
        self.hash_pepper = hash_pepper
        self.fernet = Fernet(encryption_key.encode())

    def protect(self, phone: str) -> ProtectedPhone:
        normalized = normalize_whatsapp_phone(phone)
        if not normalized:
            raise ValueError("A valid E.164 WhatsApp phone number is required")
        lookup_hash = hmac.new(
            self.hash_pepper.encode(),
            f"phone:{normalized}".encode(),
            hashlib.sha256,
        ).hexdigest()
        encrypted = self.fernet.encrypt(normalized.encode()).decode()
        return ProtectedPhone(lookup_hash, encrypted, normalized[-4:])

    def decrypt(self, encrypted_phone: str) -> str:
        try:
            return self.fernet.decrypt(encrypted_phone.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Encrypted phone value is invalid") from exc
