# backend/tests/test_salt_deps.py
from halite.salt.deps import _extract_salt_message


def test_extracts_first_p_from_cherrypy_html():
    body = """<!DOCTYPE html>
<html><body>
<h2>400 Bad Request</h2>
<p>Client disabled: 'wheel'. Add to 'netapi_enable_clients' master config option to enable.</p>
<pre id="traceback"></pre>
</body></html>"""
    msg = _extract_salt_message(body)
    assert msg is not None
    assert msg.startswith("Client disabled: 'wheel'.")
    assert "netapi_enable_clients" in msg


def test_strips_inner_tags_from_html_p():
    body = '<p>Error <strong>at line 3</strong>: <em>bad</em> request</p>'
    assert _extract_salt_message(body) == "Error at line 3: bad request"


def test_collapses_whitespace_in_html_p():
    body = '<p>line one\n\n   line two\t\ttabbed</p>'
    assert _extract_salt_message(body) == "line one line two tabbed"


def test_returns_none_for_html_without_p():
    assert _extract_salt_message("<html><body>no paragraph</body></html>") is None


def test_json_detail_key():
    assert _extract_salt_message({"detail": "Authentication required"}) == "Authentication required"


def test_json_message_key_fallback():
    assert _extract_salt_message({"message": "Pillar render failed"}) == "Pillar render failed"


def test_json_error_key_fallback():
    assert _extract_salt_message({"error": "Salt master not responding"}) == "Salt master not responding"


def test_json_no_recognized_key_returns_none():
    assert _extract_salt_message({"unrelated": "garbage"}) is None


def test_empty_dict_returns_none():
    assert _extract_salt_message({}) is None


def test_empty_string_returns_none():
    assert _extract_salt_message("") is None


def test_none_returns_none():
    assert _extract_salt_message(None) is None


def test_caps_long_messages_at_500_chars():
    long = "x" * 1000
    msg = _extract_salt_message({"detail": long})
    assert msg is not None
    assert len(msg) == 500


def test_caps_long_html_messages_at_500_chars():
    long = "x" * 1000
    msg = _extract_salt_message(f"<p>{long}</p>")
    assert msg is not None
    assert len(msg) == 500
