import httpx
import pytest

from halite.salt.client import SaltAPIClient

# Salt SSE frames: blank-line-separated; each frame has "tag:" and "data:" lines.
_SSE_BODY = (
    "retry: 400\n\n"
    "tag: salt/job/20260529120000000000/new\n"
    'data: {"tag": "salt/job/20260529120000000000/new", "data": {"fun": "test.ping"}}\n\n'
    "tag: salt/minion/web01/start\n"
    'data: {"tag": "salt/minion/web01/start", "data": {"id": "web01"}}\n\n'
)


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/login":
        return httpx.Response(
            200, json={"return": [{"token": "t", "expire": 9999999999.0}]}
        )
    if request.url.path == "/events":
        # salt-api's /events authenticates via the ?token= query param. Mirror
        # that here: reject (401) if it's missing, so the test guards the fix
        # for the real-world 401 we hit when only the header was sent.
        if request.url.params.get("token") != "t":
            return httpx.Response(401)
        return httpx.Response(200, text=_SSE_BODY)
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_stream_events_parses_frames():
    client = SaltAPIClient(
        base_url="http://salt",
        username="u",
        password="p",
        transport=httpx.MockTransport(_handler),
    )
    got = []
    async for tag, data in client.stream_events():
        got.append((tag, data.get("id") or data.get("fun")))
        if len(got) == 2:
            break
    await client.aclose()
    assert got[0] == ("salt/job/20260529120000000000/new", "test.ping")
    assert got[1] == ("salt/minion/web01/start", "web01")
