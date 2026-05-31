from fastapi.testclient import TestClient

from mock_salt.app import create_app


def _client():
    return TestClient(create_app())


def test_login_then_lowstate():
    c = _client()
    r = c.post("/login", json={"username": "halite-demo", "password": "demo",
                               "eauth": "pam"})
    assert r.status_code == 200
    token = r.json()["return"][0]["token"]
    r2 = c.post("/", json=[{"client": "wheel", "fun": "key.list_all"}],
                headers={"X-Auth-Token": token})
    assert r2.status_code == 200
    assert "minions_pre" in r2.json()["return"][0]["data"]["return"]


def test_lowstate_accepts_single_object_or_list():
    c = _client()
    r = c.post("/", json={"client": "runner", "fun": "manage.present"},
               headers={"X-Auth-Token": "x"})
    assert r.status_code == 200
    assert isinstance(r.json()["return"][0], list)


def test_events_stream_headers():
    """Check SSE headers via a real uvicorn instance (TestClient cannot handle
    infinite streaming generators — the ASGI transport blocks until the
    response body completes)."""
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    app = create_app()

    # Pick a free port.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be ready.
    deadline = time.monotonic() + 5
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start in time")
        time.sleep(0.05)

    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}") as hc:
            with hc.stream("GET", "/events", params={"token": "x"}) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
    finally:
        server.should_exit = True
        thread.join(timeout=3)
