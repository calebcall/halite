"""Fernet wrapper for at-rest encryption of the salt-api password.

The Fernet key is derived from COOKIE_SECRET via HKDF, so rotating
COOKIE_SECRET invalidates the stored salt password (operator re-enters
in the UI). That's an acceptable tradeoff — COOKIE_SECRET rotation is
rare and the failure mode (salt client cannot log in until re-entered)
is loud.
"""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_INFO = b"halite/settings/salt-api-password"


def _fernet_key_from_cookie_secret(cookie_secret: str) -> bytes:
    if not cookie_secret:
        raise ValueError("cookie_secret must be set")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_INFO,
    )
    raw = hkdf.derive(cookie_secret.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def encrypt_password(plaintext: str, *, cookie_secret: str) -> str:
    f = Fernet(_fernet_key_from_cookie_secret(cookie_secret))
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_password(ciphertext: str, *, cookie_secret: str) -> str:
    f = Fernet(_fernet_key_from_cookie_secret(cookie_secret))
    try:
        return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("salt-api password could not be decrypted (rotate COOKIE_SECRET?)") from exc
