import hashlib
import hmac

from app.services.whatsapp.security import verify_meta_signature


def test_verify_meta_signature_accepts_valid_hmac() -> None:
    payload = b'{"object":"whatsapp_business_account"}'
    secret = "app-secret"
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_meta_signature(payload, f"sha256={digest}", secret) is True
    assert verify_meta_signature(payload, "sha256=bad", secret) is False
