import json

import pytest
import structlog

from halite.logging_setup import setup_logging


def test_setup_json_emits_json(capsys):
    setup_logging(level="info", fmt="json")
    log = structlog.get_logger()
    log.info("hello", count=3)
    out = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(out)
    assert data["event"] == "hello"
    assert data["count"] == 3


def test_setup_console_emits_text(capsys):
    setup_logging(level="info", fmt="console")
    log = structlog.get_logger()
    log.info("hi")
    out = capsys.readouterr().out
    assert "hi" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.strip().splitlines()[-1])
