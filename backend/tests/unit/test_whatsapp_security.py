from __future__ import annotations

import re

from cryptography.fernet import Fernet

from app.services.whatsapp.security import (
    PhoneProtector,
    generate_dashboard_token,
    generate_start_token,
    hash_demo_token,
    mask_phone,
    normalize_whatsapp_phone,
)


def test_start_tokens_are_human_readable_random_and_fixed_length() -> None:
    tokens = {generate_start_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(re.fullmatch(r"[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}", token) for token in tokens)


def test_demo_token_hmac_uses_domain_separation() -> None:
    start_hash = hash_demo_token("A7K2P9DX", pepper="pepper", domain="start")
    dashboard_hash = hash_demo_token("A7K2P9DX", pepper="pepper", domain="dashboard")

    assert start_hash == "4d98af251226acd1b2eb98da41f7449c95f081edc9503834f5c36700a7c9f70c"
    assert dashboard_hash != start_hash
    assert len(generate_dashboard_token()) >= 43


def test_phone_protection_encrypts_hashes_and_masks_without_plaintext_storage() -> None:
    phone = "+919876543210"
    protector = PhoneProtector(
        hash_pepper="phone-pepper",
        encryption_key=Fernet.generate_key().decode(),
    )

    protected = protector.protect(phone)

    assert protected.lookup_hash != phone
    assert protected.encrypted != phone
    assert protected.last_four == "3210"
    assert protector.decrypt(protected.encrypted) == phone
    assert mask_phone(phone) == "+91 ******3210"


def test_whatsapp_phone_normalization_never_duplicates_scheme() -> None:
    assert normalize_whatsapp_phone("whatsapp:+919876543210") == "+919876543210"
    assert normalize_whatsapp_phone("+91 98765 43210") == "+919876543210"
    assert normalize_whatsapp_phone("whatsapp:whatsapp:+919876543210") == "+919876543210"
