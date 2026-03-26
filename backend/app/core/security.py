import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone


def get_jwt_secret() -> str:
    return os.getenv("AUTH_JWT_SECRET", "dev-only-change-me")


def get_access_token_expire_minutes() -> int:
    return int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("utf-8"))


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_raw),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(*, subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=get_access_token_expire_minutes())
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    signature = hmac.new(get_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        header_part, payload_part, signature_part = token.split(".")
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc

    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    expected_signature = hmac.new(get_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _b64url_decode(signature_part)

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_part))
    exp = payload.get("exp")
    if exp is None or int(exp) < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Token expired")

    return payload
