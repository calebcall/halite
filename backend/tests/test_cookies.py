from halite.auth.cookies import CookieCodec


def test_codec_roundtrip():
    codec = CookieCodec(secret="x" * 64)
    token = codec.sign("session-id-123")
    assert codec.unsign(token) == "session-id-123"


def test_codec_rejects_modified_token():
    codec = CookieCodec(secret="x" * 64)
    token = codec.sign("hi")
    bad = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    assert codec.unsign(bad) is None


def test_codec_rejects_other_secret():
    a = CookieCodec(secret="x" * 64)
    b = CookieCodec(secret="y" * 64)
    token = a.sign("hi")
    assert b.unsign(token) is None
