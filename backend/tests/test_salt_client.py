# backend/tests/test_salt_client.py
import time

import pytest

from halite.salt.client import SaltAPIClient, SaltAPIError, SaltAPIUnavailable


def _make_client(fake_salt_api) -> SaltAPIClient:
    return SaltAPIClient(
        base_url="http://salt-api.test",
        username="halite-service",
        password="pw",
        eauth="pam",
        transport=fake_salt_api.transport,
    )


@pytest.mark.asyncio
async def test_logs_in_on_first_call(fake_salt_api):
    fake_salt_api.run_handler = lambda payload: {"return": [{"data": {"return": {"m1": "1.2.3.4"}}}]}
    client = _make_client(fake_salt_api)
    try:
        result = await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
    assert result == {"m1": "1.2.3.4"}
    # First call should be /login, second /run
    assert [p for p, _ in fake_salt_api.calls] == ["/login", "/run"]


@pytest.mark.asyncio
async def test_reuses_token_across_calls(fake_salt_api):
    fake_salt_api.run_handler = lambda payload: {"return": [{"data": {"return": {}}}]}
    client = _make_client(fake_salt_api)
    try:
        await client.wheel_call("minions.connected")
        await client.wheel_call("minions.connected")
        await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
    # One login, three runs — token reused.
    paths = [p for p, _ in fake_salt_api.calls]
    assert paths.count("/login") == 1
    assert paths.count("/run") == 3


@pytest.mark.asyncio
async def test_refreshes_expired_token(fake_salt_api):
    # Token expires immediately — every call should re-login.
    fake_salt_api.login_response = {
        "return": [{"token": "expired-token", "expire": time.time() - 1, "start": time.time() - 100, "user": "x", "eauth": "pam", "perms": []}]
    }
    fake_salt_api.run_handler = lambda payload: {"return": [{"data": {"return": {}}}]}
    client = _make_client(fake_salt_api)
    try:
        await client.wheel_call("minions.connected")
        await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
    paths = [p for p, _ in fake_salt_api.calls]
    assert paths.count("/login") == 2


@pytest.mark.asyncio
async def test_concurrent_calls_share_one_login(fake_salt_api):
    import asyncio
    fake_salt_api.run_handler = lambda payload: {"return": [{"data": {"return": {}}}]}
    client = _make_client(fake_salt_api)
    try:
        await asyncio.gather(
            client.wheel_call("minions.connected"),
            client.wheel_call("minions.connected"),
            client.wheel_call("minions.connected"),
        )
    finally:
        await client.aclose()
    paths = [p for p, _ in fake_salt_api.calls]
    assert paths.count("/login") == 1
    assert paths.count("/run") == 3


@pytest.mark.asyncio
async def test_retries_on_5xx(fake_salt_api):
    """5xx triggers retries; if all attempts fail, SaltAPIUnavailable."""
    fake_salt_api.run_status = 500
    client = _make_client(fake_salt_api)
    try:
        with pytest.raises(SaltAPIUnavailable):
            await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
    # Should have tried _MAX_RETRIES (3) times after the initial login.
    paths = [p for p, _ in fake_salt_api.calls]
    assert paths.count("/run") == 3


@pytest.mark.asyncio
async def test_raises_on_login_rejection(fake_salt_api):
    fake_salt_api.login_status = 401
    client = _make_client(fake_salt_api)
    try:
        with pytest.raises(SaltAPIError) as excinfo:
            await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
    assert excinfo.value.status == 401


@pytest.mark.asyncio
async def test_list_connected_minions_returns_dict(fake_salt_api):
    fake_salt_api.run_handler = lambda payload: {
        "return": [{"data": {"return": {"web-01": "10.0.0.1", "db-01": "10.0.0.2"}}}]
    }
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_connected_minions()
    finally:
        await client.aclose()
    assert result == {"web-01": "10.0.0.1", "db-01": "10.0.0.2"}


@pytest.mark.asyncio
async def test_list_minion_keys_returns_dict(fake_salt_api):
    fake_salt_api.run_handler = lambda payload: {
        "return": [
            {
                "data": {
                    "return": {
                        "minions": ["web-01", "db-01"],
                        "minions_pre": ["new-host"],
                        "minions_rejected": [],
                        "minions_denied": [],
                        "local": [],
                    }
                }
            }
        ]
    }
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_minion_keys()
    finally:
        await client.aclose()
    assert result == {
        "minions": ["web-01", "db-01"],
        "minions_pre": ["new-host"],
        "minions_rejected": [],
        "minions_denied": [],
        "local": [],
    }


@pytest.mark.asyncio
async def test_get_minion_grains_returns_dict(fake_salt_api):
    fake_salt_api.run_handler = lambda payload: {
        "return": [{"web-01": {"os": "Ubuntu", "osrelease": "22.04", "kernel": "Linux"}}]
    }
    client = _make_client(fake_salt_api)
    try:
        result = await client.get_minion_grains("web-01")
    finally:
        await client.aclose()
    assert result == {"os": "Ubuntu", "osrelease": "22.04", "kernel": "Linux"}


@pytest.mark.asyncio
async def test_get_minion_grains_returns_none_when_offline(fake_salt_api):
    """salt-api returns an empty dict when the targeted minion didn't respond."""
    fake_salt_api.run_handler = lambda payload: {"return": [{}]}
    client = _make_client(fake_salt_api)
    try:
        result = await client.get_minion_grains("web-01")
    finally:
        await client.aclose()
    assert result is None
