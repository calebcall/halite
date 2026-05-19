from halite.auth.password import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password(h, "correct horse battery staple") is True


def test_verify_rejects_wrong_password():
    h = hash_password("good")
    assert verify_password(h, "bad") is False


def test_hashes_are_salted():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b


def test_verify_handles_malformed_hash():
    assert verify_password("not-a-hash", "anything") is False
