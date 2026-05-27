from __future__ import annotations

import pytest

from halite.settings.crypto import decrypt_password, encrypt_password


def test_encrypt_then_decrypt_round_trip():
    enc = encrypt_password("hunter2", cookie_secret="x" * 64)
    assert decrypt_password(enc, cookie_secret="x" * 64) == "hunter2"


def test_decrypt_with_wrong_secret_raises():
    enc = encrypt_password("hunter2", cookie_secret="x" * 64)
    with pytest.raises(ValueError, match="rotate COOKIE_SECRET"):
        decrypt_password(enc, cookie_secret="y" * 64)


def test_ciphertext_is_not_plaintext():
    enc = encrypt_password("hunter2", cookie_secret="x" * 64)
    assert "hunter2" not in enc


def test_empty_cookie_secret_rejected():
    with pytest.raises(ValueError, match="cookie_secret"):
        encrypt_password("hunter2", cookie_secret="")
