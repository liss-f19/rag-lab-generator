"""Bearer tokens: HS256-signed JWTs whose subject is a user id (NFR-05)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

_ALGORITHM = "HS256"
_ISSUER = "rag-lab-generator"


class InvalidTokenError(Exception):
    pass


class TokenService:
    def __init__(self, signing_key: str, ttl_minutes: int) -> None:
        self._key = signing_key
        self._ttl = timedelta(minutes=ttl_minutes)

    def issue(self, user_id: UUID, now: datetime | None = None) -> str:
        issued_at = now or datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "iss": _ISSUER,
            "iat": issued_at,
            "exp": issued_at + self._ttl,
        }
        return jwt.encode(payload, self._key, algorithm=_ALGORITHM)

    def verify(self, token: str) -> UUID:
        """Return the user id of a valid token; the user's role is read from the database."""
        try:
            payload = jwt.decode(
                token,
                self._key,
                algorithms=[_ALGORITHM],
                issuer=_ISSUER,
                options={"require": ["sub", "exp", "iat", "iss"]},
            )
            return UUID(payload["sub"])
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidTokenError(str(exc)) from exc
