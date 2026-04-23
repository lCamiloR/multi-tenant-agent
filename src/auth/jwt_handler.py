from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from src.core.config import settings
from src.auth.models import TokenPayload


def _get_active_keys() -> list[str]:
    """
    Returns a list of keys to try when verifying a token.
    The primary key always comes first — if rotation isn't active,
    this just returns a single-item list and behavior is unchanged.
    """
    keys = [settings.jwt_secret_key]
    if settings.jwt_secret_key_previous:
        keys.append(settings.jwt_secret_key_previous)
    return keys


def create_access_token(subject: str, tenant_id: str, role: str = "user") -> tuple[str, datetime]:
    """
    Always signs with the PRIMARY key only.
    This ensures all new tokens are bound to the latest key.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str) -> TokenPayload:
    """
    Tries each active key in order. This is the core of graceful rotation:
    a token signed with the old key is still accepted during the overlap window.
    The moment all old tokens expire, you can safely remove the previous key.
    """
    last_error = None

    for key in _get_active_keys():
        try:
            raw = jwt.decode(token, key, algorithms=[settings.jwt_algorithm])
            return TokenPayload(**raw)
        except JWTError as e:
            # This key didn't work — try the next one
            last_error = e
            continue

    raise ValueError(f"Invalid or expired token: {last_error}")