import hashlib
import hmac
import secrets

from app.core.config import settings


def generate_api_key() -> str:
    return f"tf_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    return hmac.new(
        settings.api_key_pepper.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_api_key(api_key: str, api_key_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(api_key), api_key_hash)
