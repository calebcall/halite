# backend/src/halite/salt/client.py
"""
SaltAPIClient — async client for salt-api's rest_cherrypy.

Owns the service-account credential. One shared httpx.AsyncClient.
Lazy login — first call does the auth exchange. An asyncio.Lock guards
concurrent token refresh so N concurrent expired-token requests trigger
exactly one re-login. Retries 5xx with exponential backoff (max 3
attempts). Retries 401 exactly once after re-login.

Convenience helpers:
  - wheel_call(fun, **kwargs)
  - local_call(target, fun, target_type='glob', **kwargs)
  - runner_call(fun, **kwargs)
  - list_connected_minions()  -> dict[minion_id, ip]

A SaltAPIError is raised for non-2xx responses; SaltAPIUnavailable for
network / config errors.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Salt-API token lifetime is typically 12 hours by default. Refresh proactively
# when fewer than this many seconds remain on the token.
_TOKEN_REFRESH_MARGIN_S = 60.0

# Retry budget for transient (5xx / network) failures.
_MAX_RETRIES = 3
_BACKOFF_BASE_S = 0.5
_BACKOFF_MAX_S = 4.0


class SaltAPIError(Exception):
    """Raised for non-2xx responses from salt-api."""

    def __init__(self, status: int, body: Any, message: str | None = None) -> None:
        super().__init__(message or f"salt-api responded {status}")
        self.status = status
        self.body = body


class SaltAPIUnavailable(Exception):
    """Raised when salt-api cannot be reached (network, DNS, TLS)."""


class SaltAPIClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        eauth: str = "pam",
        verify: bool | str = True,
        timeout_s: float = 30.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._eauth = eauth
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            verify=verify,
            timeout=timeout_s,
            transport=transport,
            headers={"Accept": "application/json"},
        )
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._login_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---------- low-level ----------

    async def _login(self) -> None:
        """Acquire a fresh token. Caller must hold _login_lock."""
        try:
            resp = await self._client.post(
                "/login",
                json={
                    "username": self._username,
                    "password": self._password,
                    "eauth": self._eauth,
                },
            )
        except httpx.HTTPError as exc:
            raise SaltAPIUnavailable(f"salt-api login failed: {exc!r}") from exc

        if resp.status_code >= 400:
            raise SaltAPIError(resp.status_code, _safe_json(resp), "salt-api login rejected")

        body = resp.json()
        # salt-api returns {return: [{token, expire, start, user, eauth, perms}]}
        record = body["return"][0]
        self._token = record["token"]
        self._token_expires_at = float(record.get("expire", time.time() + 600))
        logger.info(
            "salt-api login ok, token expires in %.0fs",
            self._token_expires_at - time.time(),
        )

    async def _ensure_token(self, force: bool = False) -> str:
        """Return a valid token, logging in if needed. Concurrency-safe."""
        if not force and self._token and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_S:
            return self._token
        async with self._login_lock:
            # Re-check inside the lock — another waiter may have refreshed.
            if not force and self._token and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_S:
                return self._token
            await self._login()
        assert self._token is not None
        return self._token

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /run with the given payload, with retries on 5xx and one
        retry on 401 after re-login."""
        token = await self._ensure_token()

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.post(
                    "/run",
                    json=[{**payload, "token": token}],
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("salt-api network error (attempt %d): %r", attempt + 1, exc)
                await _sleep_backoff(attempt)
                continue

            if resp.status_code == 401:
                # Token may be stale — refresh and retry once.
                token = await self._ensure_token(force=True)
                resp = await self._client.post(
                    "/run",
                    json=[{**payload, "token": token}],
                )
                if resp.status_code == 401:
                    raise SaltAPIError(401, _safe_json(resp), "salt-api auth rejected after refresh")

            if 500 <= resp.status_code < 600:
                logger.warning(
                    "salt-api 5xx (attempt %d, status=%d)", attempt + 1, resp.status_code
                )
                await _sleep_backoff(attempt)
                continue

            if resp.status_code >= 400:
                raise SaltAPIError(resp.status_code, _safe_json(resp))

            return resp.json()

        raise SaltAPIUnavailable(f"salt-api unreachable after {_MAX_RETRIES} attempts: {last_exc!r}")

    # ---------- helpers ----------

    async def wheel_call(self, fun: str, **kwargs: Any) -> Any:
        body = await self._request({"client": "wheel", "fun": fun, **kwargs})
        # wheel return shape: {"return": [{"data": {"return": <X>, ...}}]}
        return body["return"][0]["data"]["return"]

    async def runner_call(self, fun: str, **kwargs: Any) -> Any:
        body = await self._request({"client": "runner", "fun": fun, **kwargs})
        # runner return shape: {"return": [<X>]}
        return body["return"][0]

    async def local_call(
        self,
        target: str,
        fun: str,
        *,
        target_type: str = "glob",
        arg: list[Any] | None = None,
        kwarg: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "client": "local",
            "tgt": target,
            "tgt_type": target_type,
            "fun": fun,
        }
        if arg is not None:
            payload["arg"] = arg
        if kwarg is not None:
            payload["kwarg"] = kwarg
        body = await self._request(payload)
        # local return shape: {"return": [{<minion_id>: <result>, ...}]}
        return body["return"][0]

    async def list_connected_minions(self) -> dict[str, str]:
        """Returns a dict {minion_id: ip} of currently-connected accepted minions."""
        result = await self.wheel_call("minions.connected")
        if not isinstance(result, dict):
            return {}
        return {str(k): str(v) for k, v in result.items()}


# ---------- helpers ----------

def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


async def _sleep_backoff(attempt: int) -> None:
    delay = min(_BACKOFF_BASE_S * (2**attempt), _BACKOFF_MAX_S)
    await asyncio.sleep(delay)
