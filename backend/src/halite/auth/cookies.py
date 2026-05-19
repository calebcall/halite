from __future__ import annotations

from itsdangerous import BadSignature, URLSafeSerializer


class CookieCodec:
    """
    Sign and verify cookie payloads.

    The payload we put in cookies is just the opaque session id from the sessions
    table. The codec signs it so we can detect tampering, but it does not encrypt.
    """

    def __init__(self, secret: str, salt: str = "halite-session") -> None:
        self._serializer = URLSafeSerializer(secret, salt=salt)

    def sign(self, payload: str) -> str:
        return self._serializer.dumps(payload)

    def unsign(self, token: str) -> str | None:
        try:
            value = self._serializer.loads(token)
        except BadSignature:
            return None
        if not isinstance(value, str):
            return None
        return value
