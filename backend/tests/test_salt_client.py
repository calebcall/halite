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
    fake_salt_api.run_handler = lambda payload: {
        "return": [{"data": {"return": {"m1": "1.2.3.4"}}}]
    }
    client = _make_client(fake_salt_api)
    try:
        result = await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
    assert result == {"m1": "1.2.3.4"}
    # First call should be /login, second the root LowDataAdapter endpoint.
    assert [p for p, _ in fake_salt_api.calls] == ["/login", "/"]


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
    assert paths.count("/") == 3


@pytest.mark.asyncio
async def test_refreshes_expired_token(fake_salt_api):
    # Token expires immediately — every call should re-login.
    fake_salt_api.login_response = {
        "return": [
            {
                "token": "expired-token",
                "expire": time.time() - 1,
                "start": time.time() - 100,
                "user": "x",
                "eauth": "pam",
                "perms": [],
            }
        ]
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
    assert paths.count("/") == 2


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
    assert paths.count("/") == 3


@pytest.mark.asyncio
async def test_retries_on_5xx(fake_salt_api):
    """5xx triggers retries; if all attempts fail, SaltAPIError surfaces the
    last 5xx status+body so wrap_salt_errors can render a 502 with the salt
    body inline (salt-api IS reachable; the master is choking)."""
    fake_salt_api.run_status = 500
    client = _make_client(fake_salt_api)
    try:
        with pytest.raises(SaltAPIError) as excinfo:
            await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
    # Should have tried _MAX_RETRIES (3) times after the initial login.
    paths = [p for p, _ in fake_salt_api.calls]
    assert paths.count("/") == 3
    assert excinfo.value.status == 500


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
    # runner.manage.present(show_ip=True) returns a sorted list of [id, ip]
    # pairs (Python tuples in the salt runner, JSON arrays over the wire).
    captured: dict = {}

    def handler(payload):
        captured.update(payload)
        return {"return": [[["web-01", "10.0.0.1"], ["db-01", "10.0.0.2"]]]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_connected_minions()
    finally:
        await client.aclose()
    assert result == {"web-01": "10.0.0.1", "db-01": "10.0.0.2"}
    assert captured["client"] == "runner"
    assert captured["fun"] == "manage.present"
    assert captured["show_ip"] is True


@pytest.mark.asyncio
async def test_list_connected_minions_tolerates_flat_list(fake_salt_api):
    """If show_ip is ignored (older salt), fall back to id-only entries."""
    fake_salt_api.run_handler = lambda payload: {"return": [["web-01", "db-01"]]}
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_connected_minions()
    finally:
        await client.aclose()
    assert set(result.keys()) == {"web-01", "db-01"}


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


@pytest.mark.asyncio
async def test_accept_key_calls_wheel_with_include_flags(fake_salt_api):
    """accept_key forwards match + include_rejected + include_denied."""
    captured: dict = {}

    def handler(payload):
        captured.update(payload)
        return {
            "return": [{"data": {"return": {"minions": [payload.get("match")]}, "success": True}}]
        }

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        await client.accept_key("web-01")
    finally:
        await client.aclose()
    assert captured["client"] == "wheel"
    assert captured["fun"] == "key.accept"
    assert captured["match"] == "web-01"
    assert captured["include_rejected"] is True
    assert captured["include_denied"] is True


@pytest.mark.asyncio
async def test_reject_key_calls_wheel_with_include_flags(fake_salt_api):
    captured: dict = {}

    def handler(payload):
        captured.update(payload)
        return {
            "return": [
                {"data": {"return": {"minions_rejected": [payload.get("match")]}, "success": True}}
            ]
        }

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        await client.reject_key("web-01")
    finally:
        await client.aclose()
    assert captured["client"] == "wheel"
    assert captured["fun"] == "key.reject"
    assert captured["match"] == "web-01"
    assert captured["include_accepted"] is True
    assert captured["include_denied"] is True


@pytest.mark.asyncio
async def test_delete_key_calls_wheel_match(fake_salt_api):
    captured: dict = {}

    def handler(payload):
        captured.update(payload)
        return {
            "return": [{"data": {"return": {"minions": [payload.get("match")]}, "success": True}}]
        }

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        await client.delete_key("web-01")
    finally:
        await client.aclose()
    assert captured["client"] == "wheel"
    assert captured["fun"] == "key.delete"
    assert captured["match"] == "web-01"


@pytest.mark.asyncio
async def test_list_jobs_returns_recent_slice(fake_salt_api):
    def handler(payload):
        return {
            "return": [
                {
                    "20251019120000123456": {"Function": "test.ping", "Target": "*"},
                    "20251019110000000000": {"Function": "cmd.run", "Target": "web-01"},
                    "20251019100000000000": {"Function": "state.apply", "Target": "*"},
                }
            ],
        }

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_jobs(limit=2)
    finally:
        await client.aclose()
    assert list(result.keys()) == ["20251019120000123456", "20251019110000000000"]
    assert result["20251019120000123456"]["Function"] == "test.ping"


@pytest.mark.asyncio
async def test_get_job_returns_detail(fake_salt_api):
    captured: dict = {}

    def handler(payload):
        captured.update(payload)
        return {
            "return": [
                {
                    "Function": "test.ping",
                    "Arguments": [],
                    "Target": "*",
                    "Target-type": "glob",
                    "User": "halite-service",
                    "StartTime": "2025-10-19T12:00:00.123456",
                    "Minions": ["web-01"],
                    "Result": {"web-01": {"return": True, "success": True}},
                }
            ],
        }

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.get_job("20251019120000123456")
    finally:
        await client.aclose()
    assert result is not None
    assert result["Function"] == "test.ping"
    assert captured["fun"] == "jobs.list_job"
    assert captured["jid"] == "20251019120000123456"


@pytest.mark.asyncio
async def test_get_job_returns_none_for_unknown_jid(fake_salt_api):
    def handler(payload):
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.get_job("nonexistent")
    finally:
        await client.aclose()
    assert result is None


@pytest.mark.asyncio
async def test_run_local_async_returns_jid_and_minions(fake_salt_api):
    captured: dict = {}

    def handler(payload):
        captured.update(payload)
        return {"return": [{"jid": "20260123120000000000", "minions": ["web-01", "web-02"]}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.run_local_async(
            "web-*",
            "test.ping",
            target_type="glob",
            args=["arg1"],
            kwargs={"k1": "v1"},
        )
    finally:
        await client.aclose()
    assert result == {"jid": "20260123120000000000", "minions": ["web-01", "web-02"]}
    assert captured["client"] == "local_async"
    assert captured["tgt"] == "web-*"
    assert captured["tgt_type"] == "glob"
    assert captured["fun"] == "test.ping"
    assert captured["arg"] == ["arg1"]
    assert captured["kwarg"] == {"k1": "v1"}


@pytest.mark.asyncio
async def test_kill_job_calls_runner_with_jid(fake_salt_api):
    captured: dict = {}

    def handler(payload):
        captured.update(payload)
        return {"return": [{"web-01": True}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        await client.kill_job("20260123120000000000")
    finally:
        await client.aclose()
    assert captured["client"] == "runner"
    assert captured["fun"] == "saltutil.kill_job"
    assert captured["jid"] == "20260123120000000000"


@pytest.mark.asyncio
async def test_list_active_jobs_returns_jids(fake_salt_api):
    def handler(payload):
        return {
            "return": [{
                "20260123120000000000": {"Function": "state.apply", "Target": "*"},
                "20260123110000000000": {"Function": "cmd.run", "Target": "web-01"},
            }],
        }

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_active_jobs()
    finally:
        await client.aclose()
    assert set(result.keys()) == {
        "20260123120000000000",
        "20260123110000000000",
    }
    assert result["20260123120000000000"]["Function"] == "state.apply"


@pytest.mark.asyncio
async def test_repeated_5xx_raises_salt_api_error_with_body(fake_salt_api):
    """After all attempts return 500, _request should raise SaltAPIError
    preserving the last status + body — NOT SaltAPIUnavailable. This is
    what lets wrap_salt_errors produce a 502 with the salt-side message
    inline (Plan 14 UX) instead of a misleading 503 'not configured' panel."""
    fake_salt_api.run_status = 500
    client = _make_client(fake_salt_api)
    try:
        with pytest.raises(SaltAPIError) as exc_info:
            await client.runner_call("saltutil.kill_job", jid="20260101000000000000")
    finally:
        await client.aclose()
    assert exc_info.value.status == 500
    # The body should be captured (not None), even if its exact shape varies
    # based on what FakeSaltAPI returns for non-2xx responses.
    assert exc_info.value.body is not None


@pytest.mark.asyncio
async def test_list_execution_functions_unions_across_minions(fake_salt_api):
    """Targets * with sys.list_functions and unions the per-minion lists.
    Output is sorted, deduped, and non-string entries filtered out."""
    def handler(payload):
        if payload.get("fun") == "sys.list_functions":
            return {"return": [{
                "web-01": ["test.ping", "cmd.run", "pkg.install"],
                "web-02": ["test.ping", "service.start", "custom.minion2_only", 42],
            }]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_execution_functions()
    finally:
        await client.aclose()
    # Sorted, deduped union; the int 42 is filtered out
    assert result == [
        "cmd.run",
        "custom.minion2_only",
        "pkg.install",
        "service.start",
        "test.ping",
    ]


@pytest.mark.asyncio
async def test_list_execution_functions_returns_empty_when_no_minions_respond(fake_salt_api):
    """No minions respond → return [] without raising."""
    def handler(payload):
        if payload.get("fun") == "sys.list_functions":
            return {"return": [{}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        result = await client.list_execution_functions()
    finally:
        await client.aclose()
    assert result == []


@pytest.mark.asyncio
async def test_repeated_network_error_raises_salt_api_unavailable():
    """If every attempt is a network exception (no HTTP response at all),
    exhaustion raises SaltAPIUnavailable. This is the true-unreachable case
    — distinct from the 5xx-with-body case above."""
    import httpx

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated DNS failure")

    client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=httpx.MockTransport(boom),
    )
    try:
        with pytest.raises(SaltAPIUnavailable):
            await client.wheel_call("minions.connected")
    finally:
        await client.aclose()
